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
import urllib.request

import github_client
import proxy_tester
import stealth_injector
import country_proxies
import automation_controller
import proxies_pool

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


def check_browser_window_alive(debug_port):
    """Checks whether Chromium at debug_port has at least one open page window."""
    if not debug_port:
        return False
    try:
        url = f"http://127.0.0.1:{debug_port}/json/list"
        req = urllib.request.Request(url, headers={"User-Agent": "ShaddaWindowWatcher/1.0"})
        with urllib.request.urlopen(req, timeout=1.5) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            pages = [t for t in data if t.get('type') == 'page']
            return len(pages) > 0
    except Exception:
        return False


def cleanup_profile(profile_id):
    RUNNING_PROFILES.pop(profile_id, None)


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

    try:
        automation_controller.stop_automation_session(profile_id)
    except Exception:
        pass

    cleanup_profile(profile_id)
    return True, "Profile stopped."


def is_profile_running(profile_id):
    if profile_id not in RUNNING_PROFILES:
        return False
    info = RUNNING_PROFILES[profile_id]
    proc = info.get('proc')
    if proc is None or proc.poll() is not None:
        cleanup_profile(profile_id)
        return False
    return True


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


def configure_chrome_profile_identity(profile_dir, profile_name, color=None):
    try:
        os.makedirs(profile_dir, exist_ok=True)
        local_state_file = os.path.join(profile_dir, 'Local State')
        local_state = {}
        if os.path.exists(local_state_file):
            try:
                with open(local_state_file, 'r', encoding='utf-8') as f:
                    local_state = json.load(f)
            except Exception:
                local_state = {}

        if not isinstance(local_state, dict):
            local_state = {}
        if 'profile' not in local_state:
            local_state['profile'] = {}
        if 'info_cache' not in local_state['profile']:
            local_state['profile']['info_cache'] = {}
        if 'Default' not in local_state['profile']['info_cache']:
            local_state['profile']['info_cache']['Default'] = {}

        local_state['profile']['info_cache']['Default']['name'] = profile_name
        local_state['profile']['info_cache']['Default']['user_name'] = profile_name
        local_state['profile']['info_cache']['Default']['is_using_default_name'] = False

        with open(local_state_file, 'w', encoding='utf-8') as f:
            json.dump(local_state, f, indent=2)

        default_dir = os.path.join(profile_dir, 'Default')
        os.makedirs(default_dir, exist_ok=True)
        pref_file = os.path.join(default_dir, 'Preferences')
        prefs = {}
        if os.path.exists(pref_file):
            try:
                with open(pref_file, 'r', encoding='utf-8') as f:
                    prefs = json.load(f)
            except Exception:
                prefs = {}
        if not isinstance(prefs, dict):
            prefs = {}
        if 'profile' not in prefs:
            prefs['profile'] = {}
        prefs['profile']['name'] = profile_name
        with open(pref_file, 'w', encoding='utf-8') as f:
            json.dump(prefs, f, indent=2)
    except Exception as e:
        print(f"[!] Warning: failed to configure Chrome profile identity: {e}")


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
            p_name = profile.get('name') or f"Profile {p_id[:8]}"
            p_color = profile.get('color', '#0ea5e9')
            p_proxy_type = profile.get('proxyType', 'none')
            p_proxy_label = profile.get('assignedProxyLabel')
            if not p_proxy_label:
                if profile.get('assignedProxyNumber'):
                    p_proxy_label = f"Proxy #{profile.get('assignedProxyNumber')}"
                elif p_proxy_type == 'country':
                    p_proxy_label = profile.get('countryName') or profile.get('countryCode') or 'Country Proxy'
                elif p_proxy_type == 'github':
                    p_proxy_label = "GitHub Cloud IP"
                elif p_proxy_type == 'custom':
                    p_proxy_label = "Custom Proxy"
                else:
                    p_proxy_label = "Direct"

            api_port = 5055
            try:
                import server
                api_port = getattr(server, 'PORT', 5055)
            except Exception:
                pass

            p_seed = (int(hashlib.md5(p_id.encode('utf-8')).hexdigest()[:6], 16) % 9999) + 1

            header = f"window.__SHADDA_PROFILE_ID__ = '{p_id}';\n"
            header += f"window.__SHADDA_PROFILE_NAME__ = {json.dumps(p_name)};\n"
            header += f"window.__SHADDA_PROFILE_COLOR__ = '{p_color}';\n"
            header += f"window.__SHADDA_PROXY_LABEL__ = {json.dumps(p_proxy_label)};\n"
            header += f"window.__SHADDA_API_PORT__ = {int(api_port)};\n"
            header += f"window.__SHADDA_APP_API__ = 'http://127.0.0.1:{int(api_port)}';\n"

            content = header + content
            content = content.replace('__PROFILE_TIMEZONE__', tz)
            content = content.replace('__PROFILE_ALLOCATED_IP__', allocated_ip or '')
            content = content.replace('__PROFILE_SEED__', str(p_seed))

            with open(evasion_path, 'w', encoding='utf-8') as f:
                f.write(content)

            badge_path = os.path.join(profile_ext_dir, 'profile_badge.js')
            if os.path.exists(badge_path):
                try:
                    with open(badge_path, 'r', encoding='utf-8') as bf:
                        b_content = bf.read()
                    b_content = header + b_content
                    with open(badge_path, 'w', encoding='utf-8') as bf:
                        bf.write(b_content)
                except Exception as be:
                    print(f"[!] Failed to customize profile_badge.js: {be}")

            hud_path = os.path.join(profile_ext_dir, 'automation_hud.js')
            if os.path.exists(hud_path):
                try:
                    with open(hud_path, 'r', encoding='utf-8') as hf:
                        h_content = hf.read()
                    h_content = header + h_content
                    with open(hud_path, 'w', encoding='utf-8') as hf:
                        hf.write(h_content)
                except Exception as he:
                    print(f"[!] Failed to customize automation_hud.js: {he}")
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


def activate_browser_process(proc_pid):
    """Brings Chrome window to the foreground on macOS."""
    if sys.platform == 'darwin' and proc_pid:
        script = f'''
        tell application "System Events"
            try
                set p to (first process whose unix id is {proc_pid})
                set frontmost of p to true
                try
                    perform action "AXRaise" of window 1 of p
                end try
            end try
        end tell
        try
            tell application "Google Chrome" to activate
        end try
        '''
        try:
            subprocess.Popen(['osascript', '-e', script], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception:
            pass


def schedule_window_activation(proc_pid):
    """Schedules multiple activation attempts to ensure the Chrome window is frontmost once rendered."""
    def _act():
        for delay in (0.3, 1.2, 2.5):
            time.sleep(delay)
            activate_browser_process(proc_pid)
    threading.Thread(target=_act, daemon=True).start()


def launch_profile_browser(profile, url_override=None, on_status_change=None, with_automation=False):
    profile_id = profile['id']
    if is_profile_running(profile_id):
        info = RUNNING_PROFILES.get(profile_id, {})
        proc = info.get('proc')
        if proc and proc.pid:
            activate_browser_process(proc.pid)
        return True, "Profile is already running (brought window to front)."

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

    # Handle Guided YouTube Automation initialization
    auto_cfg = profile.get('automation') or {}
    if with_automation or (with_automation is None and auto_cfg.get('enabled')):
        yt_mode = auto_cfg.get('youtubeMode') or auto_cfg.get('mode', 'studio')
        custom_url = auto_cfg.get('customUrl', '')
        gh_acc = profile.get('githubAccountId') or auto_cfg.get('githubAccountId')
        p_name = profile.get('name') or f"Profile {profile_id[:8]}"
        p_label = profile.get('assignedProxyLabel') or (f"Proxy #{profile.get('assignedProxyNumber')}" if profile.get('assignedProxyNumber') else "Assigned Proxy")
        automation_controller.start_automation_session(
            profile_id,
            platforms=['youtube'],
            custom_url=custom_url,
            github_account_id=gh_acc,
            youtube_mode=yt_mode,
            profile_name=p_name,
            assigned_proxy=p_label
        )
        steps = automation_controller.build_workflow_steps(['youtube'], custom_url=custom_url, youtube_mode=yt_mode)
        if steps and steps[0].get('targetUrl') and not url_override:
            start_url = steps[0]['targetUrl']

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
            proxy_port = parsed.port
        except Exception as e:
            return False, f"GitHub Cloud Runner failed: {e}"
    assigned_label = profile.get('assignedProxyLabel')

    # Resolve permanently assigned proxy from pool if assigned
    pool_entry = None
    if profile.get('assignedProxyId'):
        pool_entry = proxies_pool.get_proxy_by_id(profile.get('assignedProxyId'))
    if not pool_entry and profile.get('assignedProxyNumber'):
        pool_entry = proxies_pool.get_proxy_by_number(profile.get('assignedProxyNumber'))

    if pool_entry:
        px_url = pool_entry.get('formatted')
        allocated_ip = pool_entry.get('host')
        if not assigned_label:
            assigned_label = pool_entry.get('label') or f"Proxy #{pool_entry.get('number')}"
        if pool_entry.get('timezone') and profile.get('timezone', 'auto') in ('auto', '', None):
            profile['timezone'] = pool_entry.get('timezone')
    else:
        px_url = profile.get('countryProxy') or profile.get('customProxy')
        if not assigned_label and profile.get('assignedProxyNumber'):
            assigned_label = f"Proxy #{profile.get('assignedProxyNumber')}"

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
            proxy_port = parsed.port
        except Exception as e:
            return False, f"GitHub Cloud Runner failed: {e}"
    elif px_url or proxy_type in ('country', 'pool', 'custom'):
        # STRICT PERMANENT ASSIGNED PROXY LOGIC:
        # Never randomly switch to another proxy!
        if not px_url and proxy_type == 'country':
            country_code = profile.get('countryCode', 'US')
            best_px = country_proxies.get_best_country_proxy(country_code)
            if best_px:
                px_url = best_px.get('formatted')
                allocated_ip = best_px.get('host')
                profile['countryProxy'] = px_url
                profile['customProxy'] = px_url
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
                    print(f"[!] Warning: failed to lock initial country proxy: {e}")

        if not px_url:
            kill_switch = profile.get('killSwitch', True)
            if kill_switch:
                c_name = country_proxies.COUNTRIES.get((profile.get('countryCode') or 'US').upper(), {}).get('name', profile.get('countryCode', 'US'))
                return False, f"🛡️ Kill Switch Protected: No proxy is currently assigned to this profile. Your real IP is protected from leaking. Please assign a proxy from the Proxy Pool in profile settings."

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

        c_meta = country_proxies.COUNTRIES.get((profile.get('countryCode') or 'US').upper(), {})
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
    # If proxy is configured, verify reachability before allowing browser to open.
    # NEVER auto-switch or randomly change the user's assigned proxy!
    kill_switch = profile.get('killSwitch', True)
    if (proxy_type in ('country', 'github', 'custom', 'pool') or profile.get('assignedProxyId') or px_url) and proxy_arg and kill_switch:
        if not proxy_host:
            return False, "🛡️ Kill Switch Blocked Launch: Profile is set to use a proxy, but host could not be resolved. Internet traffic is locked to prevent leaking your real IP."

        target_port = int(proxy_port) if ('proxy_port' in locals() and proxy_port) else (443 if 'pinggy' in str(proxy_host) else 1080)
        s_test = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s_test.settimeout(3.5)
        try:
            s_test.connect((proxy_host, target_port))
            s_test.close()
        except Exception as e:
            s_test.close()
            disp_name = assigned_label or (f"Proxy #{pool_entry.get('number')}" if pool_entry else f"Proxy ({proxy_host}:{target_port})")
            return False, f"🛡️ Kill Switch Protected: Permanently assigned {disp_name} is currently unreachable ({e}). The browser was prevented from opening so your real network and IP are never leaked. Check your network connection or select another proxy."

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
                    if assigned_label and not p_item.get('assignedProxyLabel'):
                        p_item['assignedProxyLabel'] = assigned_label
                        updated = True
            if updated:
                with open(db_path, 'w', encoding='utf-8') as dbf:
                    json.dump(p_list, dbf, indent=2)
    except Exception as e:
        print(f"[!] Warning: failed to save allocated IP/proxy to db: {e}")

    configure_chrome_profile_identity(profile_dir, profile.get('name') or f"Profile {profile_id[:8]}", profile.get('color'))

    ext_dir = prepare_profile_extension(profile_dir, profile, allocated_ip=allocated_ip, proxy_auth=proxy_auth)

    debug_port = _find_free_port()

    browser_bin = find_system_browser()
    if not os.path.exists(browser_bin):
        return False, f"Browser executable not found: {browser_bin}. Please install Google Chrome or Brave."

    target_start_url = start_url or 'https://www.google.com'

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
        chrome_cmd.append("--proxy-bypass-list=localhost;127.0.0.1;*.local")
        chrome_cmd.append("--force-webrtc-ip-handling-policy=disable_non_proxied_udp")
        chrome_cmd.append("--enforce-webrtc-ip-permission-check")
        chrome_cmd.append("--disable-direct-sockets")

    chrome_cmd.append(target_start_url)

    print(f"[+] Launching browser for {profile.get('name', profile_id)} on port {debug_port}")
    proc = subprocess.Popen(chrome_cmd)
    schedule_window_activation(proc.pid)

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

        badge_js_path = os.path.join(ext_dir, 'profile_badge.js')
        if os.path.exists(badge_js_path):
            try:
                with open(badge_js_path, 'r', encoding='utf-8') as bf:
                    evasion_code += "\n;\n" + bf.read()
            except Exception as e:
                print(f"[!] Failed to append profile_badge script: {e}")

        injector = stealth_injector.StealthInjector(
            port=debug_port,
            source=evasion_code,
            start_url=start_url if start_url != 'about:blank' else '',
            label=profile.get('name', profile_id),
            proxy_auth=proxy_auth
        )
        injector.start()

    def monitor():
        start_t = time.time()
        seen_pages = False
        consecutive_closed = 0

        while proc.poll() is None:
            time.sleep(1.0)
            now = time.time()
            if not seen_pages:
                if check_browser_window_alive(debug_port):
                    seen_pages = True
                continue

            # Verify if all browser windows were closed by the user (only after initial render succeeded)
            if not check_browser_window_alive(debug_port):
                consecutive_closed += 1
                if consecutive_closed >= 4:
                    print(f"[*] Window closed by user for profile {profile_id}. Terminating Chrome process...")
                    break
            else:
                consecutive_closed = 0

        # Terminate proc if still lingering in background
        if proc.poll() is None:
            try:
                proc.terminate()
                try:
                    proc.wait(timeout=2)
                except Exception:
                    proc.kill()
            except Exception:
                pass

        try:
            automation_controller.stop_automation_session(profile_id)
        except Exception:
            pass

        cleanup_profile(profile_id)
        if on_status_change:
            try:
                on_status_change(profile_id, 'stopped')
            except Exception:
                pass

    t = threading.Thread(target=monitor, daemon=True)
    t.start()

    return True, "Profile browser launched successfully."
