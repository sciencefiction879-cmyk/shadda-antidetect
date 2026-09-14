import os
import sys
import json
import uuid
import mimetypes
import subprocess
import threading
import time
import socket
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

import user_agents
import browser_runner
import github_client
import ads_manager
import auto_updater
import proxy_tester
import country_proxies

PORT = 5055

BASE_DIR = os.path.dirname(sys.executable) if getattr(sys, 'frozen', False) else os.path.dirname(os.path.abspath(__file__))
BUNDLE_DIR = getattr(sys, '_MEIPASS', BASE_DIR)

if sys.platform == 'darwin':
    DATA_DIR = os.path.expanduser('~/Library/Application Support/ShaddaAntiDetect')
else:
    DATA_DIR = BASE_DIR

os.makedirs(DATA_DIR, exist_ok=True)
github_client.ACCOUNTS_FILE = os.path.join(DATA_DIR, 'github_accounts.json')
if not os.path.exists(github_client.ACCOUNTS_FILE):
    seed_acc = os.path.join(BASE_DIR, 'github_accounts.json')
    if os.path.exists(seed_acc):
        import shutil
        try:
            shutil.copy2(seed_acc, github_client.ACCOUNTS_FILE)
        except Exception:
            pass

DB_FILE = os.path.join(DATA_DIR, 'profiles_db.json')
STATIC_DIR = os.path.join(BUNDLE_DIR, 'static')

UPDATE_MANAGER = auto_updater.UpdateManager(ads_manager.load_ads_config, "0.1")

CLOUD_SYNC_CONFIG_FILE = os.path.join(DATA_DIR, 'cloud_sync_config.json')
DEFAULT_FIREBASE_URL = "https://user-ananlytics-default-rtdb.firebaseio.com"

def load_cloud_sync_config():
    if os.path.exists(CLOUD_SYNC_CONFIG_FILE):
        try:
            with open(CLOUD_SYNC_CONFIG_FILE, 'r', encoding='utf-8') as f:
                cfg = json.load(f)
                if isinstance(cfg, dict):
                    if not cfg.get('firebaseUrl'):
                        cfg['firebaseUrl'] = DEFAULT_FIREBASE_URL
                    return cfg
        except Exception:
            pass
    return {
        "enabled": False,
        "firebaseUrl": DEFAULT_FIREBASE_URL,
        "roomKey": "",
        "lastSync": 0
    }

def save_cloud_sync_config(cfg):
    try:
        with open(CLOUD_SYNC_CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(cfg, f, indent=2)
    except Exception as e:
        print(f"[!] Warning: failed to save cloud sync config: {e}")


class AppHTTPServer(ThreadingHTTPServer):
    allow_reuse_address = True

    def server_bind(self):
        super().server_bind()


def create_app_server():
    global PORT
    for candidate in range(5055, 5076):
        try:
            server = AppHTTPServer(('127.0.0.1', candidate), ProfileHandler)
            PORT = server.server_port
            return server
        except OSError as error:
            if error.errno not in (48, 98, 10048) and getattr(error, 'winerror', None) != 10048:
                raise
    raise RuntimeError("No local app port is available. Close an older Shadda Anti Detect window and try again.")


def load_db():
    if not os.path.exists(DB_FILE):
        sample = [
            {
                "id": "profile_1",
                "name": "Shadda Profile 1 — YouTube & FB",
                "color": "#0ea5e9",
                "notes": "Main upload profile with fresh residential IP",
                "userAgentId": "mac_chrome",
                "userAgent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
                "isMobile": False,
                "proxyType": "none",
                "customProxy": "",
                "startUrl": "https://studio.youtube.com",
                "createdAt": "2026-09-13"
            },
            {
                "id": "profile_2",
                "name": "Shadda Profile 2 — Mobile (iPhone)",
                "color": "#ec4899",
                "notes": "iPhone 16 Pro Max fingerprint for social media & TikTok",
                "userAgentId": "iphone_16_pro",
                "userAgent": "Mozilla/5.0 (iPhone; CPU iPhone OS 18_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.1 Mobile/15E148 Safari/604.1",
                "isMobile": True,
                "proxyType": "none",
                "customProxy": "",
                "startUrl": "https://m.facebook.com",
                "createdAt": "2026-09-13"
            }
        ]
        save_db(sample)
        return sample

    try:
        with open(DB_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return []


def save_db(data):
    with open(DB_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2)


class ProfileHandler(BaseHTTPRequestHandler):
    def _send_json(self, data, status=200):
        body = json.dumps(data).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, PUT, DELETE, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type, X-App-Request')
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self._send_json({'status': 'ok'})

    def do_GET(self):
        parsed_url = urlparse(self.path)
        path = parsed_url.path

        if path == '/api/country-proxies':
            return self._send_json(country_proxies.get_countries_summary())

        if path.startswith('/api/country-proxies/'):
            parts = [p for p in path.strip('/').split('/') if p]
            if len(parts) >= 3:
                cc = parts[2].upper()
                if len(parts) >= 4 and parts[3] == 'best':
                    best = country_proxies.get_best_country_proxy(cc)
                    return self._send_json(best or {})
                proxies = country_proxies.verify_country_proxies(cc, max_test=20)
                return self._send_json(proxies)

        if path == '/api/user-agents':
            return self._send_json(user_agents.USER_AGENTS)

        if path == '/api/github-accounts':
            accounts = github_client.get_accounts()
            masked_accounts = []
            for acc in accounts:
                item = dict(acc)
                tok = item.get('token', '')
                if tok and len(tok) > 8:
                    item['token_masked'] = tok[:4] + '...' + tok[-4:]
                else:
                    item['token_masked'] = '***'
                item.pop('token', None)
                masked_accounts.append(item)
            return self._send_json(masked_accounts)

        if path.startswith('/api/github-accounts/') and path.endswith('/verify'):
            acc_id = path.split('/')[3]
            acc = github_client.get_account(acc_id)
            if not acc:
                return self._send_json({'error': 'Account not found'}, status=404)
            v = github_client.verify_token(acc.get('token', ''))
            return self._send_json(v)

        if path == '/api/ads':
            return self._send_json(ads_manager.display_config())

        if path == '/api/update/status':
            return self._send_json(UPDATE_MANAGER.status())

        if path == '/api/admin-mode':
            return self._send_json({'isAdmin': False})

        if path == '/api/cloud-sync/config':
            return self._send_json(load_cloud_sync_config())

        if path == '/api/profiles':
            profiles = load_db()
            for p in profiles:
                pid = p.get('id')
                p['isRunning'] = browser_runner.is_profile_running(pid)
                if pid in browser_runner.RUNNING_PROFILES:
                    p['allocatedIp'] = browser_runner.RUNNING_PROFILES[pid].get('allocated_ip')
                else:
                    p['allocatedIp'] = None
            return self._send_json(profiles)

        # Serve static files
        req_path = path.lstrip('/')
        if not req_path or req_path == 'index.html':
            req_path = 'index.html'

        file_path = os.path.join(STATIC_DIR, req_path)
        if os.path.exists(file_path) and os.path.isfile(file_path):
            mime_type, _ = mimetypes.guess_type(file_path)
            self.send_response(200)
            self.send_header('Content-Type', mime_type or 'application/octet-stream')
            with open(file_path, 'rb') as f:
                content = f.read()
            self.send_header('Content-Length', str(len(content)))
            self.end_headers()
            self.wfile.write(content)
            return

        self.send_response(404)
        self.send_header('Content-Type', 'text/plain')
        self.end_headers()
        self.wfile.write(b'Not Found')

    def do_POST(self):
        parsed_url = urlparse(self.path)
        path = parsed_url.path

        length = int(self.headers.get('Content-Length', 0))
        raw_body = self.rfile.read(length).decode('utf-8') if length > 0 else '{}'
        body = json.loads(raw_body) if raw_body else {}

        if path in ('/api/update/download', '/api/update/apply'):
            return self._send_json({'success': True, 'message': 'Running latest version 0.1'})

        if path == '/api/profiles':
            profiles = load_db()
            profile_id = 'profile_' + uuid.uuid4().hex[:8]
            body['id'] = profile_id
            body['createdAt'] = time.strftime('%Y-%m-%d')
            profiles.append(body)
            save_db(profiles)

            if body.get('proxyType') == 'github' and body.get('githubAccountId'):
                threading.Thread(
                    target=browser_runner.prewarm_github_runner,
                    args=(profile_id, body.get('githubAccountId')),
                    daemon=True
                ).start()

            return self._send_json({'success': True, 'profile': body})

        if path.startswith('/api/profiles/') and path.endswith('/launch'):
            pid = path.split('/')[3]
            profiles = load_db()
            profile = next((p for p in profiles if p.get('id') == pid), None)
            if not profile:
                return self._send_json({'success': False, 'error': 'Profile not found', 'message': 'Profile not found'}, status=404)

            url_override = body.get('url')
            force_direct = body.get('direct', False)
            profile_to_launch = dict(profile)
            if force_direct:
                profile_to_launch['proxyType'] = 'none'

            try:
                success, msg = browser_runner.launch_profile_browser(profile_to_launch, url_override=url_override)
                if not success:
                    return self._send_json({'success': False, 'error': msg, 'message': msg})
                return self._send_json({'success': True, 'message': msg})
            except Exception as e:
                import traceback
                traceback.print_exc()
                err_str = str(e)
                return self._send_json({'success': False, 'error': err_str, 'message': err_str})

        if path.startswith('/api/profiles/') and path.endswith('/stop'):
            pid = path.split('/')[3]
            success, msg = browser_runner.stop_profile_browser(pid)
            return self._send_json({'success': success, 'message': msg})

        if path.startswith('/api/profiles/') and path.endswith('/open-folder'):
            pid = path.split('/')[3]
            p_dir = browser_runner.get_profile_dir(pid)
            if sys.platform == 'darwin':
                subprocess.run(['open', p_dir])
            elif sys.platform == 'win32':
                subprocess.run(['explorer.exe', p_dir])
            else:
                subprocess.run(['xdg-open', p_dir])
            return self._send_json({'success': True})

        if path.startswith('/api/profiles/') and path.endswith('/reassign-country-proxy'):
            pid = path.split('/')[3]
            profiles = load_db()
            profile = next((p for p in profiles if p.get('id') == pid), None)
            if not profile:
                return self._send_json({'success': False, 'error': 'Profile not found'}, status=404)

            country_code = profile.get('countryCode', 'PK')
            best = country_proxies.get_best_country_proxy(country_code)
            if not best or not best.get('formatted'):
                proxies = country_proxies.verify_country_proxies(country_code, force_refresh=True)
                if proxies:
                    best = proxies[0]

            if best and best.get('formatted'):
                profile['countryProxy'] = best['formatted']
                profile['customProxy'] = best['formatted']
                profile['allocatedIp'] = best.get('host')
                if best.get('timezone'):
                    profile['timezone'] = best['timezone']
                save_db(profiles)
                return self._send_json({'success': True, 'profile': profile, 'newProxy': best['formatted'], 'latencyMs': best.get('latencyMs')})
            else:
                return self._send_json({'success': False, 'error': f'No verified live proxy currently active for {country_code}. Please pick one from Country Hub.'})

        if path == '/api/profiles/switch-all-direct':
            profiles = load_db()
            for p in profiles:
                p['proxyType'] = 'none'
            save_db(profiles)
            return self._send_json({'success': True, 'profiles': profiles})

        if path == '/api/github-accounts':
            token = body.get('token', '').strip()
            label = body.get('label', '').strip()
            is_default = bool(body.get('is_default', False))
            if not token:
                return self._send_json({'error': 'GitHub Personal Access Token is required'}, status=400)
            try:
                acc = github_client.add_account(token, label=label, is_default=is_default)
                return self._send_json({'success': True, 'account': acc})
            except Exception as e:
                return self._send_json({'error': str(e)}, status=400)

        if path.startswith('/api/github-accounts/') and path.endswith('/set-default'):
            acc_id = path.split('/')[3]
            github_client.set_default_account(acc_id)
            return self._send_json({'success': True})

        if path == '/api/proxy/parse':
            raw = body.get('raw', '')
            parsed = proxy_tester.parse_proxy_string(raw)
            if parsed:
                return self._send_json({'success': True, 'data': parsed})
            return self._send_json({'success': False, 'error': 'Could not parse proxy format'}, status=400)

        if path == '/api/proxy/test':
            raw = body.get('raw')
            if raw:
                parsed = proxy_tester.parse_proxy_string(raw)
                if not parsed:
                    return self._send_json({'success': False, 'error': 'Invalid proxy format'}, status=400)
                res = proxy_tester.test_proxy_connection(
                    parsed['protocol'],
                    parsed['host'],
                    parsed['port'],
                    username=parsed.get('username'),
                    password=parsed.get('password')
                )
                return self._send_json(res)

            proto = body.get('protocol', 'http').lower()
            host = body.get('host', '').strip()
            port = body.get('port', 8080)
            user = body.get('username')
            pwd = body.get('password')
            if not host:
                return self._send_json({'success': False, 'error': 'Proxy Host / IP is required'}, status=400)

            res = proxy_tester.test_proxy_connection(proto, host, port, username=user, password=pwd)
            return self._send_json(res)

        if path.startswith('/api/country-proxies/') and path.endswith('/refresh'):
            parts = [p for p in path.strip('/').split('/') if p]
            cc = parts[2].upper() if len(parts) >= 3 else ''
            proxies = country_proxies.verify_country_proxies(cc, max_test=25, force_refresh=True)
            return self._send_json({'success': True, 'proxies': proxies})

        if path == '/api/cloud-sync/config':
            cfg = load_cloud_sync_config()
            cfg['enabled'] = bool(body.get('enabled', cfg.get('enabled', False)))
            if 'firebaseUrl' in body and body['firebaseUrl'].strip():
                cfg['firebaseUrl'] = body['firebaseUrl'].strip().rstrip('/')
            if 'roomKey' in body:
                cfg['roomKey'] = body['roomKey'].strip()
            if 'lastSync' in body:
                cfg['lastSync'] = int(body['lastSync'])
            save_cloud_sync_config(cfg)
            return self._send_json({'success': True, 'config': cfg})

        if path == '/api/cloud-sync/apply':
            incoming_profiles = body.get('profiles')
            if not isinstance(incoming_profiles, list):
                return self._send_json({'error': 'Profiles list is required'}, status=400)
            
            # Save to local DB
            save_db(incoming_profiles)
            
            # Update lastSync timestamp
            cfg = load_cloud_sync_config()
            now_ts = int(time.time())
            cfg['lastSync'] = now_ts
            save_cloud_sync_config(cfg)
            
            return self._send_json({'success': True, 'count': len(incoming_profiles), 'lastSync': now_ts})

        return self._send_json({'error': 'Endpoint not found'}, status=404)

    def do_PUT(self):
        parsed_url = urlparse(self.path)
        path = parsed_url.path

        if path.startswith('/api/profiles/'):
            pid = path.split('/')[3]
            length = int(self.headers.get('Content-Length', 0))
            raw_body = self.rfile.read(length).decode('utf-8') if length > 0 else '{}'
            body = json.loads(raw_body)

            profiles = load_db()
            found = False
            for p in profiles:
                if p.get('id') == pid:
                    p.update(body)
                    found = True
                    break
            if found:
                save_db(profiles)
                return self._send_json({'success': True})
            return self._send_json({'error': 'Profile not found'}, status=404)

        return self._send_json({'error': 'Endpoint not found'}, status=404)

    def do_DELETE(self):
        parsed_url = urlparse(self.path)
        path = parsed_url.path

        if path.startswith('/api/profiles/'):
            pid = path.split('/')[3]
            browser_runner.stop_profile_browser(pid)
            profiles = load_db()
            profiles = [p for p in profiles if p.get('id') != pid]
            save_db(profiles)
            return self._send_json({'success': True})

        if path.startswith('/api/github-accounts/'):
            acc_id = path.split('/')[3]
            github_client.remove_account(acc_id)
            return self._send_json({'success': True})

        return self._send_json({'error': 'Endpoint not found'}, status=404)


def run_server():
    server = create_app_server()
    print("=" * 60)
    print("  🚀 Shadda Anti Detect v0.1 running at:")
    print(f"     http://127.0.0.1:{PORT}")
    print("=" * 60)

    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()

    # Launch Native Cocoa WebKit window via pywebview
    try:
        import webview
        window = webview.create_window(
            title="Shadda Anti Detect",
            url=f"http://127.0.0.1:{PORT}",
            width=1320,
            height=880,
            min_size=(950, 650),
            text_select=True,
            confirm_close=False
        )
        webview.start()
        os._exit(0)
    except Exception as e:
        print(f"[!] pywebview GUI exited or fallback to browser: {e}")
        try:
            import webbrowser
            webbrowser.open(f"http://127.0.0.1:{PORT}")
            server_thread.join()
        except KeyboardInterrupt:
            server.server_close()


if __name__ == '__main__':
    run_server()
