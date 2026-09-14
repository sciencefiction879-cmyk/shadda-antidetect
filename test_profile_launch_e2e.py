import os
import sys
import time
import json
import base64
import socket
import urllib.request
from urllib.parse import urlparse
import browser_runner

class SimpleDevToolsClient:
    def __init__(self, ws_url):
        p = urlparse(ws_url)
        self.host = p.hostname or '127.0.0.1'
        self.port = p.port or 80
        self.path = p.path
        self.sock = socket.create_connection((self.host, self.port), timeout=10)
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
                raise ConnectionError("WebSocket handshake failed")
            resp += chunk

    def send(self, payload_dict):
        data = json.dumps(payload_dict).encode('utf-8')
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

    def close(self):
        try:
            self.sock.close()
        except Exception:
            pass


def test_e2e():
    profile_id = "test_e2e_profile_99"
    profile_name = "YouTube Profile 01"
    profile_dir = os.path.join(browser_runner.PROFILES_DIR, profile_id)
    os.makedirs(profile_dir, exist_ok=True)

    profile = {
        'id': profile_id,
        'name': profile_name,
        'color': '#10b981',
        'proxyType': 'none',
        'startUrl': 'https://example.com'
    }

    print(f"[TEST] Launching profile '{profile_name}'...")
    success, msg = browser_runner.launch_profile_browser(profile, url_override='https://example.com')
    print(f"[TEST] Launch result: success={success}, msg={msg}")
    assert success, f"Launch failed: {msg}"

    run_info = browser_runner.RUNNING_PROFILES.get(profile_id)
    assert run_info is not None, "Profile not registered in RUNNING_PROFILES"
    debug_port = run_info['debug_port']
    print(f"[TEST] Profile running on debug port {debug_port}")

    # Connect via DevTools protocol to inspect DOM and title
    time.sleep(2.5)
    ws_url = None
    for _ in range(25):
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{debug_port}/json", timeout=1) as resp:
                targets = json.loads(resp.read().decode('utf-8'))
                for t in targets:
                    if t.get('type') == 'page' and 'webSocketDebuggerUrl' in t:
                        ws_url = t['webSocketDebuggerUrl']
                        break
            if ws_url:
                break
        except Exception:
            pass
        time.sleep(0.5)

    assert ws_url, f"Could not find page webSocketDebuggerUrl on port {debug_port}"
    print(f"[TEST] Found DevTools WebSocket: {ws_url}")

    ws = SimpleDevToolsClient(ws_url)

    _msg_id = 1
    def cdp_eval(expr):
        nonlocal _msg_id
        _msg_id += 1
        req = {
            "id": _msg_id,
            "method": "Runtime.evaluate",
            "params": {"expression": expr, "returnByValue": True}
        }
        ws.send(req)
        start_wait = time.time()
        while time.time() - start_wait < 5.0:
            raw = ws.recv()
            if not raw:
                continue
            resp = json.loads(raw)
            if resp.get("id") == _msg_id:
                return resp.get("result", {}).get("result", {}).get("value")
        return None

    # Wait 2 seconds for page load & scripts to execute
    time.sleep(2.5)

    # 1. Verify Page Title contains [YouTube Profile 01]
    title = cdp_eval("document.title")
    print(f"[TEST] Current document.title: {title}")
    assert title and profile_name in title, f"Expected '{profile_name}' in title, got '{title}'"

    # 2. Verify Profile Badge DOM element
    badge_exists = cdp_eval("!!document.getElementById('shadda-profile-indicator')")
    print(f"[TEST] Badge element exists in DOM: {badge_exists}")
    assert badge_exists, "Profile badge '#shadda-profile-indicator' was not found in DOM!"

    badge_name = cdp_eval("document.getElementById('shadda-badge-name-text') ? document.getElementById('shadda-badge-name-text').textContent : ''")
    print(f"[TEST] Badge name text content: '{badge_name}'")
    assert badge_name == profile_name, f"Expected badge name '{profile_name}', got '{badge_name}'"

    badge_proxy = cdp_eval("document.getElementById('shadda-badge-proxy-text') ? document.getElementById('shadda-badge-proxy-text').textContent : ''")
    print(f"[TEST] Badge proxy label: '{badge_proxy}'")
    assert badge_proxy == "Direct", f"Expected proxy 'Direct', got '{badge_proxy}'"

    # 3. Test Live Navigation
    print("[TEST] Testing live page navigation to https://httpbin.org/ip...")
    ws.send({
        "id": 999,
        "method": "Page.navigate",
        "params": {"url": "https://httpbin.org/ip"}
    })
    time.sleep(3.5)

    nav_title = cdp_eval("document.title")
    print(f"[TEST] Navigated document.title: {nav_title}")
    assert nav_title and profile_name in nav_title, f"Expected '{profile_name}' in navigated title, got '{nav_title}'"

    nav_badge = cdp_eval("!!document.getElementById('shadda-profile-indicator')")
    print(f"[TEST] After navigation badge exists: {nav_badge}")
    assert nav_badge, "Profile badge missing after navigation!"

    ws.close()

    # 4. Test Browser Stop & Window Close recovery
    print("[TEST] Stopping profile browser...")
    stop_ok = browser_runner.stop_profile_browser(profile_id)
    print(f"[TEST] Stopped profile browser: {stop_ok}")
    assert stop_ok, "Failed to stop browser"
    assert profile_id not in browser_runner.RUNNING_PROFILES, "Profile still listed in RUNNING_PROFILES"

    print("\n✅ DIRECT PROFILE LAUNCH & NAVIGATION TEST PASSED!\n")


def test_proxy_e2e():
    import country_proxies

    print("[TEST] Finding best verified live US proxy...")
    best_px = country_proxies.get_best_country_proxy('US')
    if not best_px:
        print("[!] No US proxy available at this moment, skipping proxy network test.")
        return

    print(f"[TEST] Selected live US proxy: {best_px['formatted']} (latency {best_px['latencyMs']}ms)")

    profile_id = "test_e2e_proxy_profile_88"
    profile_name = "US Proxy Profile 02"
    profile_dir = os.path.join(browser_runner.PROFILES_DIR, profile_id)
    os.makedirs(profile_dir, exist_ok=True)

    profile = {
        'id': profile_id,
        'name': profile_name,
        'color': '#3b82f6',
        'proxyType': 'country',
        'countryCode': 'US',
        'countryProxy': best_px['formatted'],
        'countryName': 'United States',
        'startUrl': 'https://example.com'
    }

    print(f"[TEST] Launching proxy profile '{profile_name}'...")
    success, msg = browser_runner.launch_profile_browser(profile, url_override='https://example.com')
    print(f"[TEST] Launch result: success={success}, msg={msg}")
    assert success, f"Proxy launch failed: {msg}"

    run_info = browser_runner.RUNNING_PROFILES.get(profile_id)
    assert run_info is not None, "Profile not in RUNNING_PROFILES"
    debug_port = run_info['debug_port']

    time.sleep(3)
    ws_url = None
    for _ in range(25):
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{debug_port}/json", timeout=1) as resp:
                targets = json.loads(resp.read().decode('utf-8'))
                for t in targets:
                    if t.get('type') == 'page' and 'webSocketDebuggerUrl' in t:
                        ws_url = t['webSocketDebuggerUrl']
                        break
            if ws_url:
                break
        except Exception:
            pass
        time.sleep(0.5)

    assert ws_url, f"Could not find page webSocketDebuggerUrl on port {debug_port}"
    ws = SimpleDevToolsClient(ws_url)

    _msg_id = 200
    def cdp_eval(expr):
        nonlocal _msg_id
        _msg_id += 1
        req = {
            "id": _msg_id,
            "method": "Runtime.evaluate",
            "params": {"expression": expr, "returnByValue": True}
        }
        ws.send(req)
        start_wait = time.time()
        while time.time() - start_wait < 6.0:
            raw = ws.recv()
            if not raw:
                continue
            resp = json.loads(raw)
            if resp.get("id") == _msg_id:
                return resp.get("result", {}).get("result", {}).get("value")
        return None

    time.sleep(2.5)

    title = cdp_eval("document.title")
    print(f"[TEST PROXY] Current document.title: {title}")
    assert title and profile_name in title, f"Expected '{profile_name}' in title, got '{title}'"

    badge_exists = cdp_eval("!!document.getElementById('shadda-profile-indicator')")
    print(f"[TEST PROXY] Badge exists: {badge_exists}")
    assert badge_exists, "Profile badge was not found in DOM!"

    badge_name = cdp_eval("document.getElementById('shadda-badge-name-text') ? document.getElementById('shadda-badge-name-text').textContent : ''")
    assert badge_name == profile_name, f"Expected '{profile_name}', got '{badge_name}'"

    badge_proxy = cdp_eval("document.getElementById('shadda-badge-proxy-text') ? document.getElementById('shadda-badge-proxy-text').textContent : ''")
    print(f"[TEST PROXY] Badge proxy text: '{badge_proxy}'")
    assert "United States" in badge_proxy or "US" in badge_proxy, f"Unexpected badge proxy '{badge_proxy}'"

    ws.close()

    print("[TEST PROXY] Stopping proxy profile browser...")
    stop_ok = browser_runner.stop_profile_browser(profile_id)
    assert stop_ok, "Failed to stop browser"

    print("\n✅ PROXY LAUNCH & VERIFICATION TEST PASSED!\n")


if __name__ == '__main__':
    try:
        test_e2e()
        test_proxy_e2e()
        print("\n🎉 ALL SUITE TESTS PASSED COMPLETELY!\n")
    finally:
        for pid in list(browser_runner.RUNNING_PROFILES.keys()):
            browser_runner.stop_profile_browser(pid)
            browser_runner.stop_profile_browser(pid)
