import os
import sys
import time
import json
import socket
import shutil
import hashlib
import subprocess
import threading
from urllib.parse import urlparse

import github_client
import proxy_tester
import stealth_injector
import country_proxies

RUNNING_PROFILES = {}

BASE_DIR = os.path.dirname(sys.executable) if getattr(sys, 'frozen', False) else os.path.dirname(os.path.abspath(__file__))
BUNDLE_DIR = getattr(sys, '_MEIPASS', BASE_DIR)

if sys.platform == 'darwin':
    DATA_DIR = os.path.expanduser('~/Library/Application Support/ShaddaAntiDetect')
else:
    DATA_DIR = BASE_DIR

os.makedirs(DATA_DIR, exist_ok=True)
github_client.ACCOUNTS_FILE = os.path.join(DATA_DIR, 'github_accounts.json')

PROFILES_DIR = os.path.join(DATA_DIR, 'profiles')
os.makedirs(PROFILES_DIR, exist_ok=True)

EXTENSION_DIR = os.path.join(BUNDLE_DIR, 'anti_detect_extension')


def find_system_browser():
    """Detects available Chromium browser on macOS and other systems."""
    if sys.platform == 'darwin':
        candidates = [
            "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
            os.path.expanduser("~/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"),
            "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser",
            os.path.expanduser("~/Applications/Brave Browser.app/Contents/MacOS/Brave Browser"),
            "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
            os.path.expanduser("~/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge"),
            "/Applications/Chromium.app/Contents/MacOS/Chromium",
            os.path.expanduser("~/Applications/Chromium.app/Contents/MacOS/Chromium"),
            "/Applications/Arc.app/Contents/MacOS/Arc",
            "/Applications/Vivaldi.app/Contents/MacOS/Vivaldi"
        ]
        for p in candidates:
            if p and os.path.exists(p):
                return p

    for name in ["google-chrome", "chromium", "brave-browser", "msedge"]:
        f = shutil.which(name)
        if f:
            return f

    return "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"


CHROME_PATH = find_system_browser()


def get_profile_dir(profile_id):
    p_dir = os.path.join(PROFILES_DIR, profile_id)
    os.makedirs(p_dir, exist_ok=True)
    return p_dir


def is_profile_running(profile_id):
    if profile_id not in RUNNING_PROFILES:
        return False
    proc = RUNNING_PROFILES[profile_id].get('proc')
    if proc is None:
        return False
    if proc.poll() is not None:
        cleanup_profile(profile_id)
        return False
    return True


def cleanup_profile(profile_id):
    RUNNING_PROFILES.pop(profile_id, None)


def _get_github_account(account_id=None):
    if not account_id or account_id == 'default':
        return github_client.get_default_account()
    return github_client.get_account(account_id) or github_client.get_default_account()


def prewarm_github_runner(profile_id, account_id=None):
    try:
        acc = _get_github_account(account_id)
        if not acc:
            return
        token = acc.get('token')
        repo = acc.get('repo')
        active_px, _ = github_client.get_active_live_proxy(token, repo, profile_id)
        if not active_px:
            github_client.dispatch_runner(token, repo, profile_id)
    except Exception as e:
        print(f"[!] Prewarm runner failed: {e}")


def launch_github_runner(profile_id, account_id=None):
    acc = _get_github_account(account_id)
    if not acc:
        raise RuntimeError("No GitHub Account configured. Please add a GitHub account in Settings.")

    token = acc.get('token', '').strip()
    repo = acc.get('repo', '').strip()
    username = acc.get('username') or acc.get('user', '')

    try:
        v = github_client.verify_token(token)
        if not v.get('success'):
            raise RuntimeError(f"GitHub Account (@{username}) Error: {v.get('error')}")
    except Exception as e:
        print(f"[!] Token verification error: {e}")

    active_px, active_ip = github_client.get_active_live_proxy(token, repo, profile_id)
    if active_px:
        print(f"[⚡ INSTANT LAUNCH] Reusing active live GitHub Proxy for {profile_id}: {active_px} ({active_ip})")
        return active_px, active_ip, None, token, repo

    run_id = github_client.dispatch_runner(token, repo, profile_id)
    start_time = time.time() - 30
    px, ip = github_client.poll_proxy_file(token, repo, profile_id, min_timestamp=start_time, timeout=140, run_id=run_id)
    return px, ip, run_id, token, repo


def prepare_profile_extension(user_data_dir, profile, allocated_ip=None, proxy_auth=None):
    profile_ext_dir = os.path.join(user_data_dir, 'anti_detect_extension')
    os.makedirs(profile_ext_dir, exist_ok=True)

    if os.path.exists(EXTENSION_DIR):
        for item in os.listdir(EXTENSION_DIR):
            s = os.path.join(EXTENSION_DIR, item)
            d = os.path.join(profile_ext_dir, item)
            if os.path.isfile(s):
                shutil.copy2(s, d)

    tz = profile.get('timezone', 'auto')
    if not tz or tz == 'auto':
        tz = 'America/New_York'

    evasion_path = os.path.join(profile_ext_dir, 'evasion.js')
    if os.path.exists(evasion_path):
        try:
            with open(evasion_path, 'r', encoding='utf-8') as f:
                content = f.read()

            p_id = str(profile.get('id', 'default'))
            p_seed = (int(hashlib.md5(p_id.encode('utf-8')).hexdigest()[:6], 16) % 9999) + 1

            content = content.replace('__PROFILE_TIMEZONE__', tz)
            content = content.replace('__PROFILE_ALLOCATED_IP__', allocated_ip or '')
            content = content.replace('__PROFILE_SEED__', str(p_seed))

            with open(evasion_path, 'w', encoding='utf-8') as f:
                f.write(content)
        except Exception as e:
            print(f"[!] Failed to customize evasion.js: {e}")

    if proxy_auth and len(proxy_auth) == 2:
        u, p = proxy_auth
        bg_path = os.path.join(profile_ext_dir, 'background.js')
        manifest_path = os.path.join(profile_ext_dir, 'manifest.json')

        auth_script = f"""
chrome.webRequest.onAuthRequired.addListener(
    function(details, callback) {{
        return {{ authCredentials: {{ username: {json.dumps(u)}, password: {json.dumps(p)} }} }};
    }},
    {{ urls: ["<all_urls>"] }},
    ["blocking"]
);
"""
        try:
            with open(bg_path, 'a', encoding='utf-8') as f:
                f.write("\n" + auth_script)
            with open(manifest_path, 'r', encoding='utf-8') as f:
                mf = json.load(f)
            perms = mf.get('permissions', [])
            for req_perm in ['webRequest', 'webRequestAuthProvider']:
                if req_perm not in perms:
                    perms.append(req_perm)
            mf['permissions'] = perms
            with open(manifest_path, 'w', encoding='utf-8') as f:
                json.dump(mf, f, indent=2)
        except Exception as e:
            print(f"[!] Failed to inject proxy auth: {e}")

    return profile_ext_dir


def _find_free_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(('', 0))
        return s.getsockname()[1]


def launch_profile_browser(profile, url_override=None, on_status_change=None):
    profile_id = profile['id']
    if is_profile_running(profile_id):
        return True, "Profile is already running."

    profile_dir = get_profile_dir(profile_id)

    # Remove stale locks
    for lf in ['lockfile', 'SingletonLock', 'SingletonSocket', 'SingletonCookie']:
        lp = os.path.join(profile_dir, lf)
        if os.path.exists(lp):
            try:
                os.remove(lp)
            except Exception:
                pass

    ua_string = profile.get('userAgent', '')
    proxy_type = profile.get('proxyType', 'none')
    custom_proxy = profile.get('customProxy', '')
    start_url = url_override or profile.get('startUrl', 'https://studio.youtube.com')
    is_mobile = profile.get('isMobile', False)

    proxy_arg = None
    proxy_host = None
    proxy_auth = None
    allocated_ip = None
    runner_id = None
    gh_token = None
    gh_repo = None

    if proxy_type == 'github':
        acc = _get_github_account(profile.get('githubAccountId'))
        if not acc:
            return False, "No GitHub Account configured. Please add a GitHub Account in 'GitHub Accounts' or switch this profile to Direct."
        try:
            if on_status_change:
                on_status_change(profile_id, 'allocating_ip')
            proxy_url, runner_ip, runner_id, gh_token, gh_repo = launch_github_runner(
                profile_id, profile.get('githubAccountId')
            )
            allocated_ip = runner_ip
            proxy_arg = f"--proxy-server={proxy_url}"
            parsed = urlparse(proxy_url if "://" in proxy_url else f"socks5://{proxy_url}")
            proxy_host = parsed.hostname
        except Exception as e:
            return False, f"GitHub Cloud Runner failed: {e}"
    elif proxy_type == 'country':
        country_code = profile.get('countryCode', 'PK')
        px_url = profile.get('countryProxy') or profile.get('customProxy')
        if not px_url:
            best_px = country_proxies.get_best_country_proxy(country_code)
            if best_px:
                px_url = best_px.get('formatted')
                allocated_ip = best_px.get('host')
                profile['countryProxy'] = px_url
                profile['customProxy'] = px_url
                # Lock and persist into DB so it stays permanently fixed
                try:
                    db_path = os.path.join(DATA_DIR, 'profiles_db.json')
                    if os.path.exists(db_path):
                        with open(db_path, 'r', encoding='utf-8') as dbf:
                            p_list = json.load(dbf)
                        for p_item in p_list:
                            if p_item.get('id') == profile_id:
                                p_item['countryProxy'] = px_url
                                p_item['customProxy'] = px_url
                                p_item['countryCode'] = country_code
                                p_item['allocatedIp'] = allocated_ip
                        with open(db_path, 'w', encoding='utf-8') as dbf:
                            json.dump(p_list, dbf, indent=2)
                except Exception as e:
                    print(f"[!] Warning: failed to lock country proxy: {e}")

        if px_url:
            parsed_px = proxy_tester.parse_proxy_string(px_url)
            if parsed_px:
                proto = parsed_px.get('protocol', 'socks5')
                h = parsed_px.get('host')
                pt = parsed_px.get('port')
                u = parsed_px.get('username')
                p = parsed_px.get('password')
                proxy_arg = f"--proxy-server={proto}://{h}:{pt}"
                proxy_host = h
                proxy_port = pt
                if not allocated_ip:
                    allocated_ip = h
                if u and p:
                    proxy_auth = (u, p)
            else:
                proxy_arg = f"--proxy-server={px_url}"
                parsed = urlparse(px_url if "://" in px_url else f"socks5://{px_url}")
                proxy_host = parsed.hostname
                proxy_port = parsed.port or 1080
                if not allocated_ip:
                    allocated_ip = proxy_host
        c_meta = country_proxies.COUNTRIES.get(country_code.upper(), {})
        if c_meta.get('timezone') and profile.get('timezone', 'auto') in ('auto', '', None):
            profile['timezone'] = c_meta['timezone']
    elif proxy_type in ('custom', 'direct') and custom_proxy:
        parsed_px = proxy_tester.parse_proxy_string(custom_proxy)
        if parsed_px:
            proto = parsed_px.get('protocol', 'http')
            h = parsed_px.get('host')
            pt = parsed_px.get('port')
            u = parsed_px.get('username')
            p = parsed_px.get('password')
            proxy_arg = f"--proxy-server={proto}://{h}:{pt}"
            proxy_host = h
            proxy_port = pt
            if u and p:
                proxy_auth = (u, p)
        else:
            proxy_arg = f"--proxy-server={custom_proxy}"
            parsed = urlparse(custom_proxy if "://" in custom_proxy else f"http://{custom_proxy}")
            proxy_host = parsed.hostname
            proxy_port = parsed.port or 8080

    # STRICT KILL SWITCH:
    # If proxy is configured, verify reachability first.
    # If proxy is offline, strictly block launch so no direct traffic or real IP ever leaks!
    kill_switch = profile.get('killSwitch', True)
    if proxy_type in ('country', 'github', 'custom') and kill_switch:
        if not proxy_host or not proxy_arg:
            return False, "🛡️ Kill Switch Blocked Launch: Profile is set to use a proxy, but none was allocated. Internet traffic is locked to prevent leaking your real IP."

        # Verify proxy socket reachability before allowing browser to open
        target_port = int(proxy_port) if ('proxy_port' in locals() and proxy_port) else (443 if 'pinggy' in str(proxy_host) else 1080)
        s_test = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s_test.settimeout(4.5)
        try:
            s_test.connect((proxy_host, target_port))
            s_test.close()
        except Exception as e:
            s_test.close()
            return False, f"🛡️ Kill Switch Protected: Proxy ({proxy_host}:{target_port}) is unreachable ({e}). The browser was prevented from opening so your real network and IP are never leaked."

    try:
        db_path = os.path.join(DATA_DIR, 'profiles_db.json')
        if os.path.exists(db_path):
            with open(db_path, 'r', encoding='utf-8') as dbf:
                p_list = json.load(dbf)
            updated = False
            for p_item in p_list:
                if p_item.get('id') == profile_id:
                    if allocated_ip and p_item.get('allocatedIp') != allocated_ip:
                        p_item['allocatedIp'] = allocated_ip
                        updated = True
                    if proxy_type == 'country' and px_url:
                        if p_item.get('countryProxy') != px_url:
                            p_item['countryProxy'] = px_url
                            updated = True
                        if p_item.get('customProxy') != px_url:
                            p_item['customProxy'] = px_url
                            updated = True
                        if p_item.get('countryCode') != country_code:
                            p_item['countryCode'] = country_code
                            updated = True
            if updated:
                with open(db_path, 'w', encoding='utf-8') as dbf:
                    json.dump(p_list, dbf, indent=2)
    except Exception as e:
        print(f"[!] Warning: failed to save allocated IP/proxy to db: {e}")

    ext_dir = prepare_profile_extension(profile_dir, profile, allocated_ip=allocated_ip, proxy_auth=proxy_auth)

    debug_port = _find_free_port()

    browser_bin = find_system_browser()
    if not os.path.exists(browser_bin):
        return False, f"Browser executable not found: {browser_bin}. Please install Google Chrome or Brave."

    # Using about:blank at startup so stealth injector attaches before page loads
    target_start_url = 'about:blank' if (stealth_injector and stealth_injector.available()) else (start_url or 'about:blank')

    chrome_cmd = [
        browser_bin,
        f"--user-data-dir={profile_dir}",
        "--no-first-run",
        "--no-default-browser-check",
        "--disable-blink-features=AutomationControlled",
        "--test-type",
        "--password-store=basic",
        "--lang=en-US,en",
        f"--remote-debugging-port={debug_port}",
        "--remote-allow-origins=*",
        f"--load-extension={ext_dir}",
        f"--disable-extensions-except={ext_dir}",
    ]

    if ua_string:
        chrome_cmd.append(f"--user-agent={ua_string}")

    if is_mobile:
        chrome_cmd.append("--enable-viewport")
        if "Nexus 5" in ua_string or "nexus_5" in profile.get('userAgentId', ''):
            chrome_cmd.append("--window-size=380,720")
        elif "Nexus 4" in ua_string or "nexus_4" in profile.get('userAgentId', ''):
            chrome_cmd.append("--window-size=400,720")
        elif "Nexus 7" in ua_string or "nexus_7" in profile.get('userAgentId', ''):
            chrome_cmd.append("--window-size=620,1020")
        elif "Nexus 10" in ua_string or "nexus_10" in profile.get('userAgentId', ''):
            chrome_cmd.append("--window-size=820,1340")
        elif "iPhone" in ua_string or "iphone" in profile.get('userAgentId', ''):
            chrome_cmd.append("--window-size=414,896")
        else:
            chrome_cmd.append("--window-size=430,932")

    if proxy_arg:
        chrome_cmd.append(proxy_arg)
        if proxy_host:
            # MAP * ~NOTFOUND strictly disables any direct DNS query on the local network
            chrome_cmd.append(f"--host-resolver-rules=MAP * ~NOTFOUND , EXCLUDE {proxy_host}")
        chrome_cmd.append("--proxy-bypass-list=<-loopback>")
        chrome_cmd.append("--force-webrtc-ip-handling-policy=disable_non_proxied_udp")
        chrome_cmd.append("--enforce-webrtc-ip-permission-check")
        chrome_cmd.append("--disable-direct-sockets")

    chrome_cmd.append(target_start_url)

    print(f"[+] Launching browser for {profile.get('name', profile_id)} on port {debug_port}")
    proc = subprocess.Popen(chrome_cmd)

    RUNNING_PROFILES[profile_id] = {
        'proc': proc,
        'debug_port': debug_port,
        'runner_id': runner_id,
        'token': gh_token,
        'repo': gh_repo,
        'allocated_ip': allocated_ip,
        'start_time': time.time()
    }

    if stealth_injector and stealth_injector.available():
        evasion_js_path = os.path.join(ext_dir, 'evasion.js')
        evasion_code = ""
        if os.path.exists(evasion_js_path):
            try:
                with open(evasion_js_path, 'r', encoding='utf-8') as ef:
                    evasion_code = ef.read()
            except Exception as e:
                print(f"[!] Failed to read evasion script: {e}")

        injector = stealth_injector.StealthInjector(
            port=debug_port,
            source=evasion_code,
            start_url=start_url if start_url != 'about:blank' else '',
            label=profile.get('name', profile_id),
            proxy_auth=proxy_auth
        )
        injector.start()

    def monitor():
        proc.wait()
        cleanup_profile(profile_id)
        if on_status_change:
            on_status_change(profile_id, 'stopped')

    t = threading.Thread(target=monitor, daemon=True)
    t.start()

    return True, "Profile browser launched successfully."


def stop_profile_browser(profile_id):
    if profile_id not in RUNNING_PROFILES:
        return False, "Profile is not running."

    info = RUNNING_PROFILES[profile_id]
    proc = info.get('proc')
    if proc:
        try:
            proc.terminate()
            try:
                proc.wait(timeout=2)
            except Exception:
                proc.kill()
        except Exception as e:
            print(f"[!] Failed to stop profile {profile_id}: {e}")

    cleanup_profile(profile_id)
    return True, "Profile stopped."
