import os
import sys
import json
import uuid
import mimetypes
import subprocess
import threading
import time
import socket
import hashlib
import secrets
import urllib.request
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

import user_agents
import browser_runner
import github_client
import ads_manager
import auto_updater
import proxy_tester
import country_proxies
import proxies_pool
import automation_controller
import youtube_uploader_manager

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

UPDATE_MANAGER = auto_updater.UpdateManager(ads_manager.load_ads_config, "0.3")

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


USERS_DB_FILE = os.path.join(DATA_DIR, 'users_db.json')
SESSION_FILE = os.path.join(DATA_DIR, 'session_config.json')

def hash_password(password: str, salt: str) -> str:
    return hashlib.sha256((password + ":" + salt).encode('utf-8')).hexdigest()

def load_users() -> list:
    if os.path.exists(USERS_DB_FILE):
        try:
            with open(USERS_DB_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if isinstance(data, list):
                    return data
        except Exception:
            pass
    return []

def save_users(users: list):
    try:
        with open(USERS_DB_FILE, 'w', encoding='utf-8') as f:
            json.dump(users, f, indent=2)
    except Exception as e:
        print(f"[!] Warning: failed to save users: {e}")

def get_session():
    if os.path.exists(SESSION_FILE):
        try:
            with open(SESSION_FILE, 'r', encoding='utf-8') as f:
                sess = json.load(f)
                if isinstance(sess, dict) and sess.get('token'):
                    return sess
        except Exception:
            pass
    return None

def save_session(sess):
    try:
        if sess is None:
            if os.path.exists(SESSION_FILE):
                os.remove(SESSION_FILE)
        else:
            with open(SESSION_FILE, 'w', encoding='utf-8') as f:
                json.dump(sess, f, indent=2)
    except Exception as e:
        print(f"[!] Warning: failed to write session: {e}")

def fetch_cloud_user(username_or_email: str):
    try:
        raw_key = username_or_email.lower().strip()
        safe_key = "".join(c for c in raw_key if c.isalnum() or c in ('_', '-'))
        if not safe_key:
            return None
        cfg = load_cloud_sync_config()
        fb_url = (cfg.get('firebaseUrl') or DEFAULT_FIREBASE_URL).rstrip('/')
        url = f"{fb_url}/users/{safe_key}.json"
        req = urllib.request.Request(url, headers={'User-Agent': 'ShaddaAntiDetect/0.3'})
        with urllib.request.urlopen(req, timeout=5) as resp:
            raw = resp.read().decode('utf-8')
            if raw and raw != 'null':
                data = json.loads(raw)
                if isinstance(data, dict) and data.get('username'):
                    return data
    except Exception as e:
        pass
    return None

def save_cloud_user(user_record: dict):
    try:
        username = user_record.get('username', '').lower().strip()
        safe_key = "".join(c for c in username if c.isalnum() or c in ('_', '-'))
        if not safe_key:
            return False
        cfg = load_cloud_sync_config()
        fb_url = (cfg.get('firebaseUrl') or DEFAULT_FIREBASE_URL).rstrip('/')
        url = f"{fb_url}/users/{safe_key}.json"
        body = json.dumps(user_record).encode('utf-8')
        req = urllib.request.Request(url, data=body, headers={'Content-Type': 'application/json'}, method='PUT')
        with urllib.request.urlopen(req, timeout=5) as resp:
            return resp.status in (200, 204)
    except Exception as e:
        pass
    return False


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

    def do_HEAD(self):
        return self.do_GET()

    def do_GET(self):
        parsed_url = urlparse(self.path)
        path = parsed_url.path

        if path in ('/download/apk', '/Shadda-Anti-Detect.apk', '/download/Shadda-Anti-Detect.apk'):
            apk_candidates = [
                os.path.join(BASE_DIR, 'releases', 'Shadda-Anti-Detect.apk'),
                os.path.join(BASE_DIR, 'dist', 'Shadda-Anti-Detect.apk'),
                os.path.join(BUNDLE_DIR, 'releases', 'Shadda-Anti-Detect.apk'),
                os.path.join(BUNDLE_DIR, 'dist', 'Shadda-Anti-Detect.apk'),
                os.path.join(DATA_DIR, 'Shadda-Anti-Detect.apk'),
                os.path.join(BASE_DIR, 'Shadda-Anti-Detect.apk'),
            ]
            for ap in apk_candidates:
                if os.path.exists(ap) and os.path.getsize(ap) > 1000000:
                    try:
                        with open(ap, 'rb') as f:
                            data = f.read()
                        self.send_response(200)
                        self.send_header('Content-Type', 'application/vnd.android.package-archive')
                        self.send_header('Content-Disposition', 'attachment; filename="Shadda-Anti-Detect.apk"')
                        self.send_header('Content-Length', str(len(data)))
                        self.send_header('Access-Control-Allow-Origin', '*')
                        self.end_headers()
                        self.wfile.write(data)
                        return
                    except Exception:
                        pass
            self.send_response(302)
            self.send_header('Location', 'https://github.com/sciencefiction879-cmyk/shadda-antidetect/releases/download/v0.3/Shadda-Anti-Detect.apk')
            self.end_headers()
            return

        if path == '/api/apk/info':
            local_ip = "127.0.0.1"
            try:
                import socket
                s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                s.connect(("8.8.8.8", 80))
                local_ip = s.getsockname()[0]
                s.close()
            except Exception:
                pass
            return self._send_json({
                'filename': 'Shadda-Anti-Detect.apk',
                'directLocalUrl': f"http://{local_ip}:{PORT}/download/apk",
                'githubReleaseUrl': 'https://github.com/sciencefiction879-cmyk/shadda-antidetect/releases/download/v0.3/Shadda-Anti-Detect.apk',
                'rawGitUrl': 'https://raw.githubusercontent.com/sciencefiction879-cmyk/shadda-antidetect/main/releases/Shadda-Anti-Detect.apk',
                'localIp': local_ip,
                'port': PORT
            })

        if path == '/api/proxies/pool':
            profiles = load_db()
            return self._send_json(proxies_pool.get_pool_with_assignments(profiles))

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

        if path == '/api/youtube-uploader/config':
            return self._send_json(youtube_uploader_manager.load_config())

        if path == '/api/youtube-uploader/status':
            return self._send_json(youtube_uploader_manager.get_workflow_runs())

        if path == '/api/auth/session':
            sess = get_session()
            if sess and sess.get('username'):
                return self._send_json({
                    'authenticated': True,
                    'user': {
                        'id': sess.get('userId', ''),
                        'username': sess.get('username', ''),
                        'email': sess.get('email', ''),
                        'workspaceId': sess.get('workspaceId', 'ws_' + sess.get('username', ''))
                    }
                })
            return self._send_json({'authenticated': False, 'user': None})

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

        if path == '/api/automation/active-session':
            for pid in browser_runner.RUNNING_PROFILES:
                st = automation_controller.get_session_state(pid)
                if st and st.get('active'):
                    return self._send_json(st)
            return self._send_json({'active': False})

        if path.startswith('/api/automation/') and path.endswith('/state'):
            pid = path.split('/')[3]
            return self._send_json(automation_controller.get_session_state(pid))

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
            return self._send_json({'success': True, 'message': 'Running latest version 0.3'})

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
            with_automation = body.get('withAutomation', None)
            profile_to_launch = dict(profile)
            if force_direct:
                profile_to_launch['proxyType'] = 'none'

            try:
                success, msg = browser_runner.launch_profile_browser(
                    profile_to_launch,
                    url_override=url_override,
                    with_automation=with_automation
                )
                if not success:
                    return self._send_json({'success': False, 'error': msg, 'message': msg})
                return self._send_json({'success': True, 'message': msg})
            except Exception as e:
                import traceback
                traceback.print_exc()
                err_str = str(e)
                return self._send_json({'success': False, 'error': err_str, 'message': err_str})

        if path.startswith('/api/automation/') and path.endswith('/action'):
            pid = path.split('/')[3]
            action = body.get('action', 'continue')
            ok, msg = automation_controller.advance_step(pid, user_action=action)
            return self._send_json({'success': ok, 'message': msg})

        if path.startswith('/api/automation/') and path.endswith('/start'):
            pid = path.split('/')[3]
            yt_mode = body.get('youtubeMode') or body.get('mode', 'studio')
            custom_url = body.get('customUrl', '')
            gh_acc = body.get('githubAccountId')

            profiles = load_db()
            prof = next((p for p in profiles if p.get('id') == pid), {})
            p_name = prof.get('name') or f"Profile {pid[:8]}"
            p_label = prof.get('assignedProxyLabel') or (f"Proxy #{prof.get('assignedProxyNumber')}" if prof.get('assignedProxyNumber') else "Assigned Proxy")

            sess = automation_controller.start_automation_session(
                pid,
                platforms=['youtube'],
                custom_url=custom_url,
                github_account_id=gh_acc,
                youtube_mode=yt_mode,
                profile_name=p_name,
                assigned_proxy=p_label
            )
            return self._send_json({'success': True, 'session': sess})

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

        if path == '/api/youtube-uploader/config':
            ok, cfg = youtube_uploader_manager.save_config(body)
            return self._send_json({'success': ok, 'config': cfg})

        if path == '/api/youtube-uploader/verify-github':
            res = youtube_uploader_manager.verify_github_repo(token=body.get('token'), repo=body.get('repo'))
            return self._send_json(res)

        if path == '/api/youtube-uploader/trigger':
            res = youtube_uploader_manager.trigger_workflow(
                slot=body.get('slot', 'slot1'),
                dry_run=body.get('dry_run', False),
                force_video=body.get('force_video', ''),
                token=body.get('token'),
                repo=body.get('repo'),
                workflow_file=body.get('workflow_file'),
                branch=body.get('branch')
            )
            return self._send_json(res)

        if path == '/api/proxies/pool/add':
            raw = body.get('proxy') or body.get('raw', '')
            cc = body.get('countryCode', 'US')
            ok, res = proxies_pool.add_proxy_to_pool(raw, country_code=cc)
            if ok:
                return self._send_json({'success': True, 'proxy': res})
            return self._send_json({'success': False, 'error': res}, status=400)

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

        if path == '/api/auth/register':
            username = (body.get('username') or '').strip()
            email = (body.get('email') or '').strip().lower()
            password = body.get('password') or ''

            if len(username) < 3 or len(username) > 30:
                return self._send_json({'error': 'Username must be between 3 and 30 characters.'}, status=400)
            if not all(c.isalnum() or c in ('_', '-') for c in username):
                return self._send_json({'error': 'Username can only contain letters, numbers, hyphens, and underscores.'}, status=400)
            if not email or '@' not in email or '.' not in email:
                return self._send_json({'error': 'Please enter a valid email address.'}, status=400)
            if len(password) < 6:
                return self._send_json({'error': 'Password must be at least 6 characters.'}, status=400)

            users = load_users()
            for u in users:
                if u.get('username', '').lower() == username.lower():
                    return self._send_json({'error': f'Username "{username}" is already taken.'}, status=409)
                if u.get('email', '').lower() == email:
                    return self._send_json({'error': f'Email "{email}" is already registered.'}, status=409)

            # Check Firebase cloud user
            cloud_existing = fetch_cloud_user(username)
            if cloud_existing:
                return self._send_json({'error': f'Username "{username}" is already taken on Cloud.'}, status=409)

            salt = secrets.token_hex(16)
            pwd_hash = hash_password(password, salt)
            uid = str(uuid.uuid4())[:8]
            clean_uname = "".join(c for c in username.lower() if c.isalnum() or c in ('_', '-'))
            ws_id = f"ws_{clean_uname}"

            user_record = {
                'id': uid,
                'username': username,
                'email': email,
                'salt': salt,
                'passwordHash': pwd_hash,
                'workspaceId': ws_id,
                'createdAt': int(time.time())
            }

            users.append(user_record)
            save_users(users)
            save_cloud_user(user_record)

            token = secrets.token_hex(32)
            session_data = {
                'token': token,
                'userId': uid,
                'username': username,
                'email': email,
                'workspaceId': ws_id,
                'loginAt': int(time.time())
            }
            save_session(session_data)

            # Automatically bind Cloud Sync to user workspace
            cfg = load_cloud_sync_config()
            cfg['enabled'] = True
            cfg['roomKey'] = ws_id
            save_cloud_sync_config(cfg)

            return self._send_json({
                'success': True,
                'user': {
                    'id': uid,
                    'username': username,
                    'email': email,
                    'workspaceId': ws_id
                },
                'token': token
            })

        if path == '/api/auth/login':
            identifier = (body.get('usernameOrEmail') or '').strip()
            password = body.get('password') or ''
            remember_me = bool(body.get('rememberMe', True))

            if not identifier or not password:
                return self._send_json({'error': 'Please enter both Username/Email and Password.'}, status=400)

            users = load_users()
            matched_user = None
            for u in users:
                if u.get('username', '').lower() == identifier.lower() or u.get('email', '').lower() == identifier.lower():
                    matched_user = u
                    break

            # If not local, search cloud
            if not matched_user:
                cloud_user = fetch_cloud_user(identifier)
                if cloud_user:
                    matched_user = cloud_user
                    if not any(u.get('username', '').lower() == cloud_user.get('username', '').lower() for u in users):
                        users.append(cloud_user)
                        save_users(users)

            if not matched_user:
                return self._send_json({'error': 'Account not found. Please check your username/email or create an account.'}, status=404)

            salt = matched_user.get('salt', '')
            expected_hash = matched_user.get('passwordHash', '')
            if hash_password(password, salt) != expected_hash:
                return self._send_json({'error': 'Incorrect password. Please try again.'}, status=401)

            uid = matched_user.get('id', '')
            uname = matched_user.get('username', '')
            email = matched_user.get('email', '')
            ws_id = matched_user.get('workspaceId') or f"ws_{uname.lower()}"

            token = secrets.token_hex(32)
            session_data = {
                'token': token,
                'userId': uid,
                'username': uname,
                'email': email,
                'workspaceId': ws_id,
                'loginAt': int(time.time()),
                'rememberMe': remember_me
            }
            if remember_me:
                save_session(session_data)
            else:
                save_session(None)

            # Auto-bind Cloud Sync to user workspace
            cfg = load_cloud_sync_config()
            cfg['enabled'] = True
            cfg['roomKey'] = ws_id
            save_cloud_sync_config(cfg)

            return self._send_json({
                'success': True,
                'user': {
                    'id': uid,
                    'username': uname,
                    'email': email,
                    'workspaceId': ws_id
                },
                'token': token
            })

        if path == '/api/auth/logout':
            save_session(None)
            return self._send_json({'success': True})

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
    print("  🚀 Shadda Anti Detect v0.3 running at:")
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
