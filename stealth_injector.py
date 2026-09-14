"""
Runs evasion.js and profile_badge.js in every tab and frame of a launched profile
through Chrome's DevTools protocol.

Provides a pure standard-library WebSocket implementation so it works out of the box
on all platforms with zero third-party dependencies.
"""

import os
import sys
import json
import base64
import socket
import threading
import time
import urllib.request
import urllib.parse

try:
    import websocket as _third_party_ws
except ImportError:
    _third_party_ws = None

SHIELDED_TYPES = ('page', 'iframe')


class BuiltinWebSocketClient:
    """Pure standard library WebSocket client for DevTools CDP."""
    def __init__(self, ws_url, timeout=15):
        p = urllib.parse.urlparse(ws_url)
        self.host = p.hostname or '127.0.0.1'
        self.port = p.port or 80
        self.path = p.path
        if p.query:
            self.path += f"?{p.query}"
        self.sock = socket.create_connection((self.host, self.port), timeout=timeout)
        self._handshake()

    def _handshake(self):
        key = base64.b64encode(os.urandom(16)).decode('ascii')
        req = (
            f"GET {self.path} HTTP/1.1\r\n"
            f"Host: {self.host}:{self.port}\r\n"
            "Upgrade: websocket\r\n"
            "Connection: Upgrade\r\n"
            f"Sec-WebSocket-Key: {key}\r\n"
            "Sec-WebSocket-Version: 13\r\n\r\n"
        )
        self.sock.sendall(req.encode('ascii'))
        resp = b""
        while b"\r\n\r\n" not in resp:
            chunk = self.sock.recv(1024)
            if not chunk:
                raise ConnectionError("DevTools WebSocket handshake failed")
            resp += chunk

    def settimeout(self, timeout):
        self.sock.settimeout(timeout)

    def send(self, data):
        if isinstance(data, str):
            data = data.encode('utf-8')
        length = len(data)
        mask = os.urandom(4)
        if length <= 125:
            header = bytes([0x81, 0x80 | length]) + mask
        elif length <= 65535:
            header = bytes([0x81, 0x80 | 126]) + length.to_bytes(2, 'big') + mask
        else:
            header = bytes([0x81, 0x80 | 127]) + length.to_bytes(8, 'big') + mask
        masked = bytes([b ^ mask[i % 4] for i, b in enumerate(data)])
        self.sock.sendall(header + masked)

    def recv(self):
        try:
            head = self.sock.recv(2)
            if not head or len(head) < 2:
                return None
            masked = (head[1] & 0x80) != 0
            length = head[1] & 0x7f
            if length == 126:
                length = int.from_bytes(self.sock.recv(2), 'big')
            elif length == 127:
                length = int.from_bytes(self.sock.recv(8), 'big')
            mask = self.sock.recv(4) if masked else None
            data = b""
            while len(data) < length:
                chunk = self.sock.recv(length - len(data))
                if not chunk:
                    break
                data += chunk
            if masked and mask:
                data = bytes([b ^ mask[i % 4] for i, b in enumerate(data)])
            return data.decode('utf-8', errors='ignore')
        except Exception:
            return None

    def close(self):
        try:
            self.sock.close()
        except Exception:
            pass


def _connect_ws(ws_url, timeout=15):
    if _third_party_ws is not None:
        try:
            return _third_party_ws.create_connection(ws_url, timeout=timeout, suppress_origin=True)
        except Exception:
            pass
    return BuiltinWebSocketClient(ws_url, timeout=timeout)


def available():
    return True


class StealthInjector(threading.Thread):
    def __init__(self, port, source, start_url="", label="", proxy_auth=None):
        super().__init__(daemon=True, name=f"stealth-{port}")
        self.port = port
        self.source = source
        self.start_url = start_url
        self.label = label
        self.proxy_auth = proxy_auth
        self._ws = None
        self._next_id = 1
        self._start_page_sent = False

    def run(self):
        ws_url = self._browser_ws_url()
        if not ws_url:
            print(f"[!] DevTools port {self.port} never came up; profile {self.label} is unshielded")
            return

        try:
            self._ws = _connect_ws(ws_url, timeout=15)
            self._ws.settimeout(None)
            self._auto_attach("")
            print(f"[+] Stealth shield & profile badge armed for every tab of profile {self.label} (port {self.port})")

            while True:
                raw = self._ws.recv()
                if not raw:
                    break
                msg = json.loads(raw)
                method = msg.get("method")
                if method == "Target.attachedToTarget":
                    self._on_attached(msg.get("params", {}))
                elif method == "Fetch.authRequired" and self.proxy_auth:
                    params = msg.get("params", {})
                    req_id = params.get("requestId")
                    sid = msg.get("sessionId")
                    u, p = self.proxy_auth
                    self._send("Fetch.continueWithAuth", {
                        "requestId": req_id,
                        "authChallengeResponse": {
                            "response": "ProvideCredentials",
                            "username": u,
                            "password": p
                        }
                    }, session_id=sid)
                elif method == "Fetch.requestPaused":
                    req_id = msg.get("params", {}).get("requestId")
                    sid = msg.get("sessionId")
                    self._send("Fetch.continueRequest", {"requestId": req_id}, session_id=sid)
        except Exception as e:
            print(f"[!] Could not attach to profile {self.label} on port {self.port}: {e}")

    def _browser_ws_url(self, timeout=15):
        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                url = f"http://127.0.0.1:{self.port}/json/version"
                with urllib.request.urlopen(url, timeout=0.5) as r:
                    data = json.loads(r.read().decode('utf-8'))
                    ws_url = data.get("webSocketDebuggerUrl")
                    if ws_url:
                        return ws_url
            except Exception:
                time.sleep(0.2)
        return None

    def _send(self, method, params=None, session_id=None):
        msg_id = self._next_id
        self._next_id += 1
        payload = {"id": msg_id, "method": method}
        if params is not None:
            payload["params"] = params
        if session_id:
            payload["sessionId"] = session_id
        self._ws.send(json.dumps(payload))

    def _auto_attach(self, session_id):
        self._send("Target.setAutoAttach", {
            "autoAttach": True,
            "waitForDebuggerOnStart": False,
            "flatten": True
        }, session_id=session_id)

    def _on_attached(self, params):
        sid = params.get("sessionId")
        info = params.get("targetInfo", {})
        kind = info.get("type")

        if kind == "tab" or kind in SHIELDED_TYPES:
            self._auto_attach(sid)
            self._send("Page.enable", {}, session_id=sid)
            if self.source:
                self._send("Page.addScriptToEvaluateOnNewDocument", {"source": self.source}, session_id=sid)
                if kind == "page":
                    # Also immediately inject into current document so already loaded tab gets badge & title
                    self._send("Runtime.evaluate", {"expression": self.source}, session_id=sid)

            if self.proxy_auth:
                self._send("Fetch.enable", {"handleAuthRequests": True}, session_id=sid)

            if info.get("waitingForDebugger"):
                self._send("Runtime.runIfWaitingForDebugger", {}, session_id=sid)
        else:
            if info.get("waitingForDebugger"):
                self._send("Runtime.runIfWaitingForDebugger", {}, session_id=sid)
            self._send("Target.detachFromTarget", {"sessionId": sid})
