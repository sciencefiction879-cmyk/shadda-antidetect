import socket
import time
import json
import base64
import re
import urllib.request
import urllib.parse


def parse_proxy_string(raw_str):
    if not raw_str:
        return None

    raw = raw_str.strip()
    protocol = 'http'

    proto_match = re.match(r'^([a-zA-Z0-9]+)://', raw)
    if proto_match:
        p = proto_match.group(1).lower()
        if p in ('socks5', 'socks4', 'http', 'https'):
            protocol = p
        elif p.startswith('socks5'):
            protocol = 'socks5'
        elif p.startswith('socks4'):
            protocol = 'socks4'
        raw = raw[proto_match.end():].strip()

    if '@' not in raw:
        if '\t' in raw:
            raw = re.sub(r'\t+', ':', raw)
        elif ',' in raw:
            raw = re.sub(r',+', ':', raw)
        elif ';' in raw:
            raw = re.sub(r';+', ':', raw)
        elif '|' in raw:
            raw = re.sub(r'\|+', ':', raw)
        elif ' ' in raw and ':' not in raw:
            raw = re.sub(r'\s+', ':', raw)

    raw = raw.replace(' ', '')
    host = ''
    port = ''
    user = ''
    password = ''

    if '@' in raw:
        left, right = raw.split('@', 1)
        if ':' in right:
            r_parts = right.split(':')
            l_parts = left.split(':')
            if len(r_parts) >= 2 and r_parts[-1].isdigit():
                user = l_parts[0]
                password = ':'.join(l_parts[1:]) if len(l_parts) > 1 else ''
                host = r_parts[0]
                port = r_parts[1]
            elif len(l_parts) >= 2 and l_parts[-1].isdigit():
                host = l_parts[0]
                port = l_parts[1]
                user = r_parts[0]
                password = ':'.join(r_parts[1:]) if len(r_parts) > 1 else ''
    else:
        parts = raw.split(':')
        if len(parts) == 4:
            if parts[1].isdigit():
                # host:port:user:pass
                host = parts[0]
                port = parts[1]
                user = parts[2]
                password = parts[3]
            elif parts[3].isdigit():
                # user:pass:host:port
                user = parts[0]
                password = parts[1]
                host = parts[2]
                port = parts[3]
        elif len(parts) == 2:
            host = parts[0]
            port = parts[1]
        elif len(parts) == 3:
            host = parts[0]
            port = parts[1]
            user = parts[2]

    if not host or not str(port).isdigit():
        return None

    if user and password:
        formatted = f"{protocol}://{user}:{password}@{host}:{port}"
    else:
        formatted = f"{protocol}://{host}:{port}"

    return {
        'protocol': protocol,
        'host': host,
        'port': int(port),
        'username': user,
        'password': password,
        'formatted': formatted
    }


def test_proxy_connection(protocol, host, port, username=None, password=None, timeout=8.0):
    start_t = time.time()
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(timeout)

    try:
        s.connect((host, int(port)))

        if protocol.lower() == 'socks5':
            if username and password:
                s.sendall(b'\x05\x02\x00\x02')
                resp = s.recv(2)
                if len(resp) < 2 or resp[0] != 5:
                    return {'success': False, 'error': 'Invalid SOCKS5 handshake response from server'}
                if resp[1] == 2:
                    u_bytes = username.encode('utf-8')
                    p_bytes = password.encode('utf-8')
                    auth_pkt = b'\x01' + bytes([len(u_bytes)]) + u_bytes + bytes([len(p_bytes)]) + p_bytes
                    s.sendall(auth_pkt)
                    auth_resp = s.recv(2)
                    if len(auth_resp) < 2 or auth_resp[1] != 0:
                        return {'success': False, 'error': 'SOCKS5 authentication failed (invalid username or password)'}
            else:
                s.sendall(b'\x05\x01\x00')
                resp = s.recv(2)
                if len(resp) < 2 or resp[0] != 5:
                    return {'success': False, 'error': 'Invalid SOCKS5 greeting response'}
                if resp[1] != 0:
                    return {'success': False, 'error': 'SOCKS5 proxy requires authentication (username & password)'}

            target_host = b'ip-api.com'
            connect_pkt = b'\x05\x01\x00\x03' + bytes([len(target_host)]) + target_host + (80).to_bytes(2, 'big')
            s.sendall(connect_pkt)
            conn_resp = s.recv(10)
            if len(conn_resp) < 4 or conn_resp[1] != 0:
                err_code = conn_resp[1] if len(conn_resp) >= 2 else 'Unknown'
                return {'success': False, 'error': f'SOCKS5 proxy could not reach target (error code {err_code})'}

            req = b'GET /json HTTP/1.1\r\nHost: ip-api.com\r\nUser-Agent: ShaddaAntiDetect-ProxyTest/0.1\r\nConnection: close\r\n\r\n'
            s.sendall(req)
        else:
            headers = [
                'GET http://ip-api.com/json HTTP/1.1',
                'Host: ip-api.com',
                'User-Agent: ShaddaAntiDetect-ProxyTest/0.1',
                'Connection: close'
            ]
            if username and password:
                creds = base64.b64encode(f"{username}:{password}".encode('utf-8')).decode('utf-8')
                headers.append(f"Proxy-Authorization: Basic {creds}")
            req = '\r\n'.join(headers) + '\r\n\r\n'
            s.sendall(req.encode('utf-8'))

        raw_data = b''
        while True:
            chunk = s.recv(4096)
            if not chunk:
                break
            raw_data += chunk

        s.close()
        latency_ms = int((time.time() - start_t) * 1000)
        text = raw_data.decode('utf-8', errors='ignore')

        body = text.split('\r\n\r\n', 1)[-1] if '\r\n\r\n' in text else text
        start_idx = body.find('{')
        end_idx = body.rfind('}')

        if start_idx != -1 and end_idx != -1:
            data = json.loads(body[start_idx:end_idx + 1])
            if data.get('status') == 'success':
                return {
                    'success': True,
                    'ip': data.get('query'),
                    'country': data.get('country'),
                    'countryCode': data.get('countryCode'),
                    'city': data.get('city'),
                    'region': data.get('regionName'),
                    'isp': data.get('isp'),
                    'timezone': data.get('timezone'),
                    'latencyMs': latency_ms
                }
            else:
                return {
                    'success': True,
                    'ip': data.get('query', host),
                    'country': 'Unknown',
                    'latencyMs': latency_ms
                }

        if '407 Proxy Authentication Required' in text:
            return {'success': False, 'error': 'HTTP Proxy Authentication Required (407). Check username and password.'}

        return {'success': False, 'error': 'Proxy connected, but target returned non-JSON response'}

    except socket.timeout:
        return {'success': False, 'error': f'Connection timed out ({timeout}s). Host or port not responding.'}
    except ConnectionRefusedError:
        return {'success': False, 'error': 'Connection refused. Proxy port is closed or proxy service is offline.'}
    except Exception as e:
        return {'success': False, 'error': str(e)}
    finally:
        try:
            s.close()
        except Exception:
            pass
