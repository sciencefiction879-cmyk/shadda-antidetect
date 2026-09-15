import os
import sys
import time
import json
import country_proxies
import proxy_tester

BASE_DIR = os.path.dirname(sys.executable) if getattr(sys, 'frozen', False) else os.path.dirname(os.path.abspath(__file__))

if sys.platform == 'darwin':
    DATA_DIR = os.path.expanduser('~/Library/Application Support/ShaddaAntiDetect')
else:
    DATA_DIR = BASE_DIR

POOL_FILE = os.path.join(DATA_DIR, 'proxies_pool.json')


def _init_default_pool():
    """Builds a rich, numbered master proxy pool from country seeds and cache."""
    proxies = []
    seen_addresses = set()
    proxy_idx = 1

    # 1. Pull verified proxies from country cache
    try:
        c_cache = country_proxies.load_cache()
        for cc, data in c_cache.items():
            c_meta = country_proxies.COUNTRIES.get(cc, {})
            for p in data.get('proxies', []):
                host = p.get('host')
                port = p.get('port')
                key = f"{host}:{port}"
                if key not in seen_addresses:
                    seen_addresses.add(key)
                    proxies.append({
                        'id': f"proxy_{proxy_idx}",
                        'number': proxy_idx,
                        'label': f"Proxy #{proxy_idx}",
                        'formatted': p.get('formatted') or f"{p.get('protocol', 'socks5')}://{host}:{port}",
                        'host': host,
                        'port': int(port),
                        'protocol': p.get('protocol', 'socks5'),
                        'countryCode': cc,
                        'country': c_meta.get('name', cc),
                        'flag': c_meta.get('flag', '🌐'),
                        'city': p.get('city') or c_meta.get('city', ''),
                        'timezone': p.get('timezone') or c_meta.get('timezone', 'UTC'),
                        'latencyMs': p.get('latencyMs', 150),
                        'status': 'online',
                        'addedAt': int(time.time()),
                        'source': 'verified_country_cache'
                    })
                    proxy_idx += 1
    except Exception as e:
        print(f"[!] Notice loading country cache into pool: {e}")

    # 2. Add fallback seeds for diverse coverage
    for cc, seeds in country_proxies.FALLBACK_SEEDS.items():
        c_meta = country_proxies.COUNTRIES.get(cc, {})
        for s in seeds:
            host = s.get('host')
            port = s.get('port')
            key = f"{host}:{port}"
            if key not in seen_addresses:
                seen_addresses.add(key)
                proto = s.get('protocol', 'socks5')
                proxies.append({
                    'id': f"proxy_{proxy_idx}",
                    'number': proxy_idx,
                    'label': f"Proxy #{proxy_idx}",
                    'formatted': f"{proto}://{host}:{port}",
                    'host': host,
                    'port': int(port),
                    'protocol': proto,
                    'countryCode': cc,
                    'country': c_meta.get('name', cc),
                    'flag': c_meta.get('flag', '🌐'),
                    'city': s.get('city') or c_meta.get('city', ''),
                    'timezone': c_meta.get('timezone', 'UTC'),
                    'latencyMs': s.get('latencyMs', 180),
                    'status': 'online',
                    'addedAt': int(time.time()),
                    'source': 'seed'
                })
                proxy_idx += 1

    return proxies


def load_pool():
    if not os.path.exists(POOL_FILE):
        pool = _init_default_pool()
        save_pool(pool)
        return pool

    try:
        with open(POOL_FILE, 'r', encoding='utf-8') as f:
            pool = json.load(f)
        if not pool or not isinstance(pool, list):
            pool = _init_default_pool()
            save_pool(pool)
        return pool
    except Exception as e:
        print(f"[!] Error loading proxies pool from {POOL_FILE}: {e}")
        pool = _init_default_pool()
        save_pool(pool)
        return pool


def save_pool(pool):
    os.makedirs(DATA_DIR, exist_ok=True)
    try:
        with open(POOL_FILE, 'w', encoding='utf-8') as f:
            json.dump(pool, f, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        print(f"[!] Error saving proxies pool to {POOL_FILE}: {e}")
        return False


def get_pool_with_assignments(profiles):
    """Enriches each proxy in the pool with real-time assignment data from all profiles."""
    pool = load_pool()

    proxy_usage = {}
    for p in profiles:
        p_id = p.get('id')
        p_name = p.get('name') or f"Profile {p_id[:8]}"

        assigned_id = p.get('assignedProxyId')
        assigned_num = p.get('assignedProxyNumber')
        p_px = p.get('countryProxy') or p.get('customProxy') or ''

        for item in pool:
            match = False
            if assigned_id and item.get('id') == assigned_id:
                match = True
            elif assigned_num and item.get('number') == assigned_num:
                match = True
            elif p_px:
                p_parsed = proxy_tester.parse_proxy_string(p_px)
                if p_parsed:
                    p_host = p_parsed.get('host')
                    p_port = str(p_parsed.get('port'))
                    if item.get('host') == p_host and str(item.get('port')) == p_port:
                        match = True

            if match and item['id'] not in proxy_usage:
                proxy_usage[item['id']] = {
                    'profileId': p_id,
                    'profileName': p_name
                }

    enriched = []
    for item in pool:
        copy_item = dict(item)
        usage = proxy_usage.get(item['id'])
        if usage:
            copy_item['isAssigned'] = True
            copy_item['assignedToProfileId'] = usage['profileId']
            copy_item['assignedToProfileName'] = usage['profileName']
            copy_item['statusBadge'] = f"Assigned to {usage['profileName']}"
        else:
            copy_item['isAssigned'] = False
            copy_item['assignedToProfileId'] = None
            copy_item['assignedToProfileName'] = None
            copy_item['statusBadge'] = "Available"
        enriched.append(copy_item)

    return enriched


def add_proxy_to_pool(raw_proxy_string, country_code='US'):
    pool = load_pool()
    parsed = proxy_tester.parse_proxy_string(raw_proxy_string)
    if not parsed or not parsed.get('host') or not parsed.get('port'):
        return False, "Invalid proxy format. Please use protocol://host:port or host:port:user:pass"

    host = parsed['host']
    port = int(parsed['port'])
    proto = parsed.get('protocol', 'socks5')

    for p in pool:
        if p.get('host') == host and int(p.get('port')) == port:
            return True, p

    next_num = 1
    if pool:
        next_num = max(p.get('number', 0) for p in pool) + 1

    cc = (country_code or 'US').upper()
    c_meta = country_proxies.COUNTRIES.get(cc, country_proxies.COUNTRIES.get('US', {}))

    ok, latency, detected = country_proxies.test_proxy_socket(proto, host, port, timeout=2.5)
    lat = latency if (ok and latency) else 250

    new_proxy = {
        'id': f"proxy_{next_num}",
        'number': next_num,
        'label': f"Proxy #{next_num}",
        'formatted': f"{proto}://{host}:{port}",
        'host': host,
        'port': port,
        'protocol': proto,
        'countryCode': cc,
        'country': c_meta.get('name', cc),
        'flag': c_meta.get('flag', '🌐'),
        'city': c_meta.get('city', ''),
        'timezone': c_meta.get('timezone', 'UTC'),
        'latencyMs': lat,
        'status': 'online' if ok else 'unverified',
        'addedAt': int(time.time()),
        'source': 'custom'
    }

    pool.append(new_proxy)
    save_pool(pool)
    return True, new_proxy


def get_proxy_by_id(proxy_id):
    pool = load_pool()
    for p in pool:
        if p.get('id') == proxy_id:
            return p
    return None


def get_proxy_by_number(number):
    try:
        num = int(number)
    except Exception:
        return None
    pool = load_pool()
    for p in pool:
        if p.get('number') == num:
            return p
    return None
