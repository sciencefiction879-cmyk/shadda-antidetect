"""
Runs evasion.js in every tab and frame of a launched profile through Chrome's DevTools protocol.

Chrome 137+ ignores --load-extension in branded builds, so on Google Chrome the extension never
loads and this is the only way the shield reaches pages.

Chrome is launched on about:blank. The injector connects to the browser and auto-attaches to
every page and cross-site iframe with waitForDebuggerOnStart, so each new target is paused until
the script is registered - new tabs and popups included, not only the first tab. Pages already
open when it attaches (restored tabs) are reloaded, and the first blank tab is sent to the
profile's start URL once the script is in place.
"""

import json
import threading
import time
import urllib.request

try:
    import websocket
except ImportError:
    websocket = None

SHIELDED_TYPES = ('page', 'iframe')


def available():
    return websocket is not None


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
            self._ws = websocket.create_connection(ws_url, timeout=15, suppress_origin=True)
            self._ws.settimeout(None)
            self._auto_attach("")
            print(f"[+] Stealth shield armed for every tab of profile {self.label} (port {self.port})")

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
            "waitForDebuggerOnStart": True,
            "flatten": True
        }, session_id=session_id)

    def _on_attached(self, params):
        sid = params.get("sessionId")
        info = params.get("targetInfo", {})
        kind = info.get("type")

        if kind == "tab" or kind in SHIELDED_TYPES:
            self._auto_attach(sid)
            self._send("Page.enable", {}, session_id=sid)
            self._send("Page.addScriptToEvaluateOnNewDocument", {"source": self.source}, session_id=sid)
            if self.proxy_auth:
                self._send("Fetch.enable", {"handleAuthRequests": True}, session_id=sid)

            if kind == "page":
                if info.get("waitingForDebugger"):
                    if not self._start_page_sent and self.start_url:
                        url = info.get("url", "")
                        if url in ("", "about:blank"):
                            self._send("Page.navigate", {"url": self.start_url}, session_id=sid)
                            self._start_page_sent = True
                        elif url.startswith(("http://", "https://")):
                            self._send("Page.reload", {}, session_id=sid)
                    self._send("Runtime.runIfWaitingForDebugger", {}, session_id=sid)
        else:
            self._send("Target.detachFromTarget", {"sessionId": sid})
