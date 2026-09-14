import os
import sys
import time
import json
import socket
import urllib.request
import urllib.parse
from concurrent.futures import ThreadPoolExecutor

BASE_DIR = os.path.dirname(sys.executable) if getattr(sys, 'frozen', False) else os.path.dirname(os.path.abspath(__file__))

if sys.platform == 'darwin':
    DATA_DIR = os.path.expanduser('~/Library/Application Support/ShaddaAntiDetect')
else:
    DATA_DIR = BASE_DIR

CACHE_FILE = os.path.join(DATA_DIR, 'country_proxies_cache.json')

COUNTRIES = {
    'PK': {'name': 'Pakistan', 'flag': '🇵🇰', 'timezone': 'Asia/Karachi', 'locale': 'ur-PK,en-US', 'city': 'Islamabad'},
    'IN': {'name': 'India', 'flag': '🇮🇳', 'timezone': 'Asia/Kolkata', 'locale': 'hi-IN,en-IN,en', 'city': 'New Delhi'},
    'US': {'name': 'United States', 'flag': '🇺🇸', 'timezone': 'America/New_York', 'locale': 'en-US,en', 'city': 'Washington'},
    'GB': {'name': 'United Kingdom', 'flag': '🇬🇧', 'timezone': 'Europe/London', 'locale': 'en-GB,en', 'city': 'London'},
    'DE': {'name': 'Germany', 'flag': '🇩🇪', 'timezone': 'Europe/Berlin', 'locale': 'de-DE,de,en-US', 'city': 'Berlin'},
    'PH': {'name': 'Philippines', 'flag': '🇵🇭', 'timezone': 'Asia/Manila', 'locale': 'fil-PH,tl-PH,en-US', 'city': 'Manila'},
    'RU': {'name': 'Russia', 'flag': '🇷🇺', 'timezone': 'Europe/Moscow', 'locale': 'ru-RU,ru,en-US', 'city': 'Moscow'},
    'CA': {'name': 'Canada', 'flag': '🇨🇦', 'timezone': 'America/Toronto', 'locale': 'en-CA,fr-CA,en', 'city': 'Toronto'},
    'FR': {'name': 'France', 'flag': '🇫🇷', 'timezone': 'Europe/Paris', 'locale': 'fr-FR,fr,en-US', 'city': 'Paris'},
    'NL': {'name': 'Netherlands', 'flag': '🇳🇱', 'timezone': 'Europe/Amsterdam', 'locale': 'nl-NL,nl,en-US', 'city': 'Amsterdam'},
    'SG': {'name': 'Singapore', 'flag': '🇸🇬', 'timezone': 'Asia/Singapore', 'locale': 'en-SG,en,zh-SG', 'city': 'Singapore'},
    'JP': {'name': 'Japan', 'flag': '🇯🇵', 'timezone': 'Asia/Tokyo', 'locale': 'ja-JP,ja,en-US', 'city': 'Tokyo'},
    'AU': {'name': 'Australia', 'flag': '🇦🇺', 'timezone': 'Australia/Sydney', 'locale': 'en-AU,en', 'city': 'Sydney'},
    'BR': {'name': 'Brazil', 'flag': '🇧🇷', 'timezone': 'America/Sao_Paulo', 'locale': 'pt-BR,pt,en-US', 'city': 'São Paulo'},
    'TR': {'name': 'Turkey', 'flag': '🇹🇷', 'timezone': 'Europe/Istanbul', 'locale': 'tr-TR,tr,en-US', 'city': 'Istanbul'},
    'AE': {'name': 'United Arab Emirates', 'flag': '🇦🇪', 'timezone': 'Asia/Dubai', 'locale': 'ar-AE,en-US', 'city': 'Dubai'},
    'SA': {'name': 'Saudi Arabia', 'flag': '🇸🇦', 'timezone': 'Asia/Riyadh', 'locale': 'ar-SA,en', 'city': 'Riyadh'},
    'ID': {'name': 'Indonesia', 'flag': '🇮🇩', 'timezone': 'Asia/Jakarta', 'locale': 'id-ID,en-US', 'city': 'Jakarta'},
    'MY': {'name': 'Malaysia', 'flag': '🇲🇾', 'timezone': 'Asia/Kuala_Lumpur', 'locale': 'ms-MY,en-US', 'city': 'Kuala Lumpur'},
    'BD': {'name': 'Bangladesh', 'flag': '🇧🇩', 'timezone': 'Asia/Dhaka', 'locale': 'bn-BD,en-US', 'city': 'Dhaka'},
    'TH': {'name': 'Thailand', 'flag': '🇹🇭', 'timezone': 'Asia/Bangkok', 'locale': 'th-TH,en-US', 'city': 'Bangkok'},
    'VN': {'name': 'Vietnam', 'flag': '🇻🇳', 'timezone': 'Asia/Ho_Chi_Minh', 'locale': 'vi-VN,en-US', 'city': 'Hanoi'},
    'KR': {'name': 'South Korea', 'flag': '🇰🇷', 'timezone': 'Asia/Seoul', 'locale': 'ko-KR,en-US', 'city': 'Seoul'},
    'CN': {'name': 'China / HK', 'flag': '🇭🇰', 'timezone': 'Asia/Hong_Kong', 'locale': 'zh-HK,zh-CN,en', 'city': 'Hong Kong'},
    'IT': {'name': 'Italy', 'flag': '🇮🇹', 'timezone': 'Europe/Rome', 'locale': 'it-IT,en-US', 'city': 'Rome'},
    'ES': {'name': 'Spain', 'flag': '🇪🇸', 'timezone': 'Europe/Madrid', 'locale': 'es-ES,en-US', 'city': 'Madrid'},
    'CH': {'name': 'Switzerland', 'flag': '🇨🇭', 'timezone': 'Europe/Zurich', 'locale': 'de-CH,fr-CH,en', 'city': 'Zurich'},
    'SE': {'name': 'Sweden', 'flag': '🇸🇪', 'timezone': 'Europe/Stockholm', 'locale': 'sv-SE,en-US', 'city': 'Stockholm'},
    'PL': {'name': 'Poland', 'flag': '🇵🇱', 'timezone': 'Europe/Warsaw', 'locale': 'pl-PL,en-US', 'city': 'Warsaw'},
    'UA': {'name': 'Ukraine', 'flag': '🇺🇦', 'timezone': 'Europe/Kyiv', 'locale': 'uk-UA,en-US', 'city': 'Kyiv'},
    'MX': {'name': 'Mexico', 'flag': '🇲🇽', 'timezone': 'America/Mexico_City', 'locale': 'es-MX,en', 'city': 'Mexico City'},
    'AR': {'name': 'Argentina', 'flag': '🇦🇷', 'timezone': 'America/Argentina/Buenos_Aires', 'locale': 'es-AR,en', 'city': 'Buenos Aires'},
    'ZA': {'name': 'South Africa', 'flag': '🇿🇦', 'timezone': 'Africa/Johannesburg', 'locale': 'en-ZA,en', 'city': 'Johannesburg'},
    'EG': {'name': 'Egypt', 'flag': '🇪🇬', 'timezone': 'Africa/Cairo', 'locale': 'ar-EG,en', 'city': 'Cairo'}
}

FALLBACK_SEEDS = {
    'PK': [
        {'host': '58.65.142.254', 'port': 8081, 'protocol': 'http', 'city': 'Karachi'},
        {'host': '111.119.162.248', 'port': 10973, 'protocol': 'socks5', 'city': 'Karachi'},
        {'host': '111.119.162.248', 'port': 10946, 'protocol': 'socks5', 'city': 'Lahore'},
        {'host': '111.119.162.248', 'port': 10969, 'protocol': 'socks5', 'city': 'Islamabad'},
        {'host': '111.119.162.248', 'port': 10900, 'protocol': 'socks5', 'city': 'Rawalpindi'},
        {'host': '182.184.119.180', 'port': 1080, 'protocol': 'socks5', 'city': 'Karachi'}
    ],
    'IN': [
        {'host': '45.195.159.160', 'port': 80, 'protocol': 'http', 'city': 'Mumbai'},
        {'host': '103.83.28.216', 'port': 5678, 'protocol': 'socks5', 'city': 'Mumbai'},
        {'host': '163.53.204.178', 'port': 9813, 'protocol': 'socks5', 'city': 'Delhi'},
        {'host': '175.101.240.38', 'port': 80, 'protocol': 'http', 'city': 'Hyderabad'},
        {'host': '103.14.120.106', 'port': 8080, 'protocol': 'http', 'city': 'Delhi'},
        {'host': '103.159.46.10', 'port': 8080, 'protocol': 'http', 'city': 'Bengaluru'}
    ],
    'US': [
        {'host': '97.74.87.226', 'port': 80, 'protocol': 'http', 'city': 'New York'},
        {'host': '38.127.179.42', 'port': 37234, 'protocol': 'http', 'city': 'Washington'},
        {'host': '157.245.29.92', 'port': 1081, 'protocol': 'socks5', 'city': 'San Francisco'}
    ],
    'GB': [
        {'host': '82.9.133.51', 'port': 9150, 'protocol': 'socks5', 'city': 'London'},
        {'host': '89.191.226.51', 'port': 1081, 'protocol': 'socks5', 'city': 'London'},
        {'host': '91.107.122.209', 'port': 1080, 'protocol': 'socks5', 'city': 'Manchester'}
    ],
    'DE': [
        {'host': '49.13.22.249', 'port': 10811, 'protocol': 'socks5', 'city': 'Frankfurt'},
        {'host': '41.216.188.132', 'port': 9050, 'protocol': 'socks5', 'city': 'Düsseldorf'}
    ],
    'PH': [
        {'host': '111.119.162.248', 'port': 10920, 'protocol': 'socks5', 'city': 'Manila'},
        {'host': '103.239.201.50', 'port': 58765, 'protocol': 'socks5', 'city': 'San Juan'},
        {'host': '180.191.137.251', 'port': 5050, 'protocol': 'http', 'city': 'Lahug'},
        {'host': '161.49.215.28', 'port': 10101, 'protocol': 'socks5', 'city': 'Manila'}
    ],
    'RU': [
        {'host': '141.98.85.49', 'port': 1080, 'protocol': 'socks5', 'city': 'Moscow'},
        {'host': '188.113.182.218', 'port': 1080, 'protocol': 'socks5', 'city': 'Saint Petersburg'},
        {'host': '84.54.217.219', 'port': 1080, 'protocol': 'socks5', 'city': 'Kazan'},
        {'host': '31.43.194.184', 'port': 1081, 'protocol': 'socks5', 'city': 'Moscow'}
    ]
}


def load_cache():
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def save_cache(cache):
    try:
        os.makedirs(os.path.dirname(CACHE_FILE), exist_ok=True)
        with open(CACHE_FILE, 'w', encoding='utf-8') as f:
            json.dump(cache, f, indent=2)
    except Exception as e:
        print(f"[!] Warning: failed to save country proxy cache: {e}")


def test_proxy_socket(protocol, host, port, timeout=3.5):
    start = time.time()
    proto = (protocol or '').lower().strip()
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(timeout)

    try:
        s.connect((host, int(port)))

        if proto == 'socks5':
            # 1. Greet
            s.sendall(b'\x05\x01\x00')
            resp = s.recv(2)
            if len(resp) < 2 or resp[0] != 5 or resp[1] != 0:
                return False, None, 'socks5'
            # 2. Tunnel connect to HTTPS port 443
            target_host = b'www.google.com'
            connect_pkt = b'\x05\x01\x00\x03' + bytes([len(target_host)]) + target_host + (443).to_bytes(2, 'big')
            s.sendall(connect_pkt)
            conn_resp = s.recv(10)
            if len(conn_resp) < 4 or conn_resp[1] != 0:
                return False, None, 'socks5'
            latency = max(1, int((time.time() - start) * 1000))
            return True, latency, 'socks5'

        if proto == 'socks4':
            # SOCKS4 connect to port 443
            s.sendall(b'\x04\x01\x01\xbb\x08\x08\x08\x08\x00')
            resp = s.recv(8)
            if len(resp) >= 2 and resp[1] == 90:
                latency = max(1, int((time.time() - start) * 1000))
                return True, latency, 'socks4'
            return False, None, 'socks4'

        # Default / HTTP / HTTPS proxy check
        # Must support HTTPS CONNECT tunnel to port 443
        s.sendall(b'CONNECT www.google.com:443 HTTP/1.1\r\nHost: www.google.com:443\r\nProxy-Connection: keep-alive\r\nUser-Agent: Mozilla/5.0\r\n\r\n')
        resp = s.recv(256)
        if b'407' in resp or b'401' in resp or b'403' in resp:
            # Requires authentication or blocked — strictly reject
            return False, None, 'http'
        if b'HTTP' in resp and (b' 200' in resp or b'Connection established' in resp or b'Connection Established' in resp):
            latency = max(1, int((time.time() - start) * 1000))
            return True, latency, 'http'

        return False, None, 'http'
    except Exception:
        return False, None, proto or 'http'
    finally:
        try:
            s.close()
        except Exception:
            pass
            pass


_PROXIFLY_CACHE = {'timestamp': 0, 'data': []}

def get_proxifly_list():
    now = time.time()
    if _PROXIFLY_CACHE['data'] and (now - _PROXIFLY_CACHE['timestamp'] < 1800):
        return _PROXIFLY_CACHE['data']
    try:
        url = 'https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/all/data.json'
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=4) as r:
            data = json.loads(r.read().decode())
            if isinstance(data, list):
                _PROXIFLY_CACHE['data'] = data
                _PROXIFLY_CACHE['timestamp'] = now
                return data
    except Exception as e:
        print(f"[-] Proxifly fetch notice: {e}")
    return _PROXIFLY_CACHE.get('data', [])


def fetch_raw_proxies_for_country(country_code):
    cc = country_code.upper()
    c_meta = COUNTRIES.get(cc, {})
    raw_list = []
    seen = set()

    # 1. Fallback seeds (prioritized)
    seeds = FALLBACK_SEEDS.get(cc, [])
    for seed in seeds:
        k = f"{seed['host']}:{seed['port']}"
        if k not in seen:
            seen.add(k)
            raw_list.append({
                'host': seed['host'],
                'port': seed['port'],
                'protocol': seed.get('protocol', 'socks5'),
                'city': seed.get('city') or c_meta.get('city', ''),
                'source': 'seed'
            })

    # 2. Proxifly high-speed global repo
    p_data = get_proxifly_list()
    for item in p_data:
        if item.get('geolocation', {}).get('country') == cc:
            ip = item.get('ip')
            port = item.get('port')
            proto = item.get('protocol') or 'http'
            city = item.get('geolocation', {}).get('city') or c_meta.get('city', '')
            k = f"{ip}:{port}"
            if k not in seen:
                seen.add(k)
                raw_list.append({
                    'host': ip,
                    'port': int(port),
                    'protocol': proto,
                    'city': city,
                    'source': 'proxifly'
                })

    # 3. GeoNode API
    try:
        u = f"https://proxylist.geonode.com/api/proxy-list?country={cc}&limit=40&page=1&sort_by=lastChecked&sort_type=desc"
        req = urllib.request.Request(u, headers={'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)'})
        with urllib.request.urlopen(req, timeout=4) as r:
            res = json.loads(r.read().decode())
            data = res.get('data', [])
            for item in data:
                ip = item.get('ip')
                port = item.get('port')
                proto = item.get('protocols', ['http'])[0]
                city = item.get('city') or c_meta.get('city', '')
                k = f"{ip}:{port}"
                if k not in seen:
                    seen.add(k)
                    raw_list.append({
                        'host': ip,
                        'port': int(port),
                        'protocol': proto,
                        'city': city,
                        'source': 'geonode'
                    })
    except Exception as e:
        print(f"[-] GeoNode fetch notice for {cc}: {e}")

    # 3. ProxyScrape API
    try:
        u = f"https://api.proxyscrape.com/v2/?request=displayproxies&protocol=http,socks4,socks5&timeout=10000&country={cc.lower()}&ssl=all&anonymity=all"
        req = urllib.request.Request(u, headers={'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)'})
        with urllib.request.urlopen(req, timeout=4) as r:
            lines = [l.strip() for l in r.read().decode().splitlines() if l.strip()]
            for line in lines[:25]:
                if ':' in line:
                    ip, port = line.split(':', 1)
                    k = f"{ip}:{port}"
                    if k not in seen:
                        seen.add(k)
                        raw_list.append({
                            'host': ip,
                            'port': int(port),
                            'protocol': 'socks5',
                            'city': c_meta.get('city', ''),
                            'source': 'proxyscrape'
                        })
    except Exception as e:
        print(f"[-] ProxyScrape fetch notice for {cc}: {e}")

    return raw_list


def verify_country_proxies(country_code, max_test=25, force_refresh=False):
    cc = country_code.upper()
    cache = load_cache()
    cached = cache.get(cc)

    if not force_refresh and cached and (time.time() - cached.get('timestamp', 0) < 600):
        if cached.get('proxies'):
            return cached['proxies']

    candidates = fetch_raw_proxies_for_country(cc)
    if not candidates:
        return []

    verified = []
    c_meta = COUNTRIES.get(cc, {})

    def do_test(item):
        ok, latency, detected_proto = test_proxy_socket(item['protocol'], item['host'], item['port'])
        if ok:
            formatted = f"{detected_proto}://{item['host']}:{item['port']}"
            return {
                'countryCode': cc,
                'country': c_meta.get('name', cc),
                'flag': c_meta.get('flag', '🌐'),
                'city': item.get('city') or c_meta.get('city', ''),
                'host': item['host'],
                'port': item['port'],
                'protocol': detected_proto,
                'latencyMs': latency,
                'formatted': formatted,
                'timezone': c_meta.get('timezone', 'UTC'),
                'locale': c_meta.get('locale', 'en-US,en'),
                'verifiedAt': int(time.time()),
                'status': 'active'
            }
        return None

    with ThreadPoolExecutor(max_workers=15) as executor:
        futs = [executor.submit(do_test, c) for c in candidates[:max_test]]
        for f in futs:
            try:
                res = f.result()
                if res:
                    verified.append(res)
            except Exception:
                pass


    verified.sort(key=lambda x: x.get('latencyMs', 9999))

    cache[cc] = {
        'timestamp': time.time(),
        'proxies': verified
    }
    save_cache(cache)

    return verified


def get_best_country_proxy(country_code):
    cc = country_code.upper()
    proxies = verify_country_proxies(cc, max_test=15)
    for px in proxies:
        ok, latency, _ = test_proxy_socket(px.get('protocol'), px.get('host'), px.get('port'), timeout=1.8)
        if ok:
            px['latencyMs'] = latency
            return px
    # If all cached proxies failed, force fresh verification
    fresh = verify_country_proxies(cc, max_test=25, force_refresh=True)
    if fresh:
        return fresh[0]
    return None


def get_countries_summary():
    cache = load_cache()
    summary = []
    for code, meta in COUNTRIES.items():
        cached_entry = cache.get(code, {})
        plist = cached_entry.get('proxies', [])
        count = len(plist) if plist else (len(FALLBACK_SEEDS.get(code, [])) + 8)
        summary.append({
            'code': code,
            'name': meta['name'],
            'flag': meta['flag'],
            'timezone': meta['timezone'],
            'city': meta['city'],
            'availableCount': count,
            'bestLatencyMs': plist[0].get('latencyMs') if plist else None
        })
    return summary
