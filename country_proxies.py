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
        {'host': '58.65.142.254', 'port': 8081, 'protocol': 'http', 'city': 'Karachi', 'latencyMs': 120},
        {'host': '111.119.162.248', 'port': 10973, 'protocol': 'socks5', 'city': 'Karachi', 'latencyMs': 135},
        {'host': '111.119.162.248', 'port': 10946, 'protocol': 'socks5', 'city': 'Lahore', 'latencyMs': 140},
        {'host': '111.119.162.248', 'port': 10969, 'protocol': 'socks5', 'city': 'Islamabad', 'latencyMs': 130},
        {'host': '111.119.162.248', 'port': 10900, 'protocol': 'socks5', 'city': 'Rawalpindi', 'latencyMs': 145},
        {'host': '182.184.119.180', 'port': 1080, 'protocol': 'socks5', 'city': 'Karachi', 'latencyMs': 125},
        {'host': '39.40.118.91', 'port': 8080, 'protocol': 'http', 'city': 'Faisalabad', 'latencyMs': 150},
        {'host': '119.160.119.34', 'port': 8080, 'protocol': 'http', 'city': 'Multan', 'latencyMs': 160}
    ],
    'IN': [
        {'host': '45.195.159.160', 'port': 80, 'protocol': 'http', 'city': 'Mumbai', 'latencyMs': 110},
        {'host': '103.83.28.216', 'port': 5678, 'protocol': 'socks5', 'city': 'Mumbai', 'latencyMs': 120},
        {'host': '163.53.204.178', 'port': 9813, 'protocol': 'socks5', 'city': 'Delhi', 'latencyMs': 115},
        {'host': '175.101.240.38', 'port': 80, 'protocol': 'http', 'city': 'Hyderabad', 'latencyMs': 130},
        {'host': '103.14.120.106', 'port': 8080, 'protocol': 'http', 'city': 'Delhi', 'latencyMs': 125},
        {'host': '103.159.46.10', 'port': 8080, 'protocol': 'http', 'city': 'Bengaluru', 'latencyMs': 118},
        {'host': '103.241.227.103', 'port': 8080, 'protocol': 'http', 'city': 'Kolkata', 'latencyMs': 140}
    ],
    'US': [
        {'host': '97.74.87.226', 'port': 80, 'protocol': 'http', 'city': 'New York', 'latencyMs': 85},
        {'host': '38.127.179.42', 'port': 37234, 'protocol': 'http', 'city': 'Washington', 'latencyMs': 90},
        {'host': '157.245.29.92', 'port': 1081, 'protocol': 'socks5', 'city': 'San Francisco', 'latencyMs': 105},
        {'host': '70.166.65.160', 'port': 4145, 'protocol': 'socks5', 'city': 'Los Angeles', 'latencyMs': 95},
        {'host': '198.23.239.134', 'port': 6543, 'protocol': 'socks5', 'city': 'Chicago', 'latencyMs': 92},
        {'host': '68.185.57.14', 'port': 80, 'protocol': 'http', 'city': 'Dallas', 'latencyMs': 98},
        {'host': '104.238.135.17', 'port': 8080, 'protocol': 'http', 'city': 'Miami', 'latencyMs': 110}
    ],
    'GB': [
        {'host': '82.9.133.51', 'port': 9150, 'protocol': 'socks5', 'city': 'London', 'latencyMs': 95},
        {'host': '89.191.226.51', 'port': 1081, 'protocol': 'socks5', 'city': 'London', 'latencyMs': 92},
        {'host': '91.107.122.209', 'port': 1080, 'protocol': 'socks5', 'city': 'Manchester', 'latencyMs': 105},
        {'host': '51.159.115.233', 'port': 3128, 'protocol': 'http', 'city': 'London', 'latencyMs': 98},
        {'host': '178.62.193.19', 'port': 1080, 'protocol': 'socks5', 'city': 'Edinburgh', 'latencyMs': 115}
    ],
    'DE': [
        {'host': '49.13.22.249', 'port': 10811, 'protocol': 'socks5', 'city': 'Frankfurt', 'latencyMs': 88},
        {'host': '41.216.188.132', 'port': 9050, 'protocol': 'socks5', 'city': 'Düsseldorf', 'latencyMs': 95},
        {'host': '168.119.138.89', 'port': 1080, 'protocol': 'socks5', 'city': 'Berlin', 'latencyMs': 90},
        {'host': '159.69.218.156', 'port': 1080, 'protocol': 'socks5', 'city': 'Munich', 'latencyMs': 102},
        {'host': '85.214.132.117', 'port': 8080, 'protocol': 'http', 'city': 'Hamburg', 'latencyMs': 94}
    ],
    'PH': [
        {'host': '111.119.162.248', 'port': 10920, 'protocol': 'socks5', 'city': 'Manila', 'latencyMs': 140},
        {'host': '103.239.201.50', 'port': 58765, 'protocol': 'socks5', 'city': 'San Juan', 'latencyMs': 155},
        {'host': '180.191.137.251', 'port': 5050, 'protocol': 'http', 'city': 'Lahug', 'latencyMs': 145},
        {'host': '161.49.215.28', 'port': 10101, 'protocol': 'socks5', 'city': 'Manila', 'latencyMs': 138},
        {'host': '112.198.115.11', 'port': 8080, 'protocol': 'http', 'city': 'Cebu', 'latencyMs': 160},
        {'host': '120.28.66.196', 'port': 8080, 'protocol': 'http', 'city': 'Davao', 'latencyMs': 165}
    ],
    'RU': [
        {'host': '141.98.85.49', 'port': 1080, 'protocol': 'socks5', 'city': 'Moscow', 'latencyMs': 110},
        {'host': '188.113.182.218', 'port': 1080, 'protocol': 'socks5', 'city': 'Saint Petersburg', 'latencyMs': 118},
        {'host': '84.54.217.219', 'port': 1080, 'protocol': 'socks5', 'city': 'Kazan', 'latencyMs': 125},
        {'host': '31.43.194.184', 'port': 1081, 'protocol': 'socks5', 'city': 'Moscow', 'latencyMs': 115},
        {'host': '95.182.124.78', 'port': 1080, 'protocol': 'socks5', 'city': 'Novosibirsk', 'latencyMs': 135}
    ],
    'CA': [
        {'host': '142.93.158.125', 'port': 1080, 'protocol': 'socks5', 'city': 'Toronto', 'latencyMs': 92},
        {'host': '198.50.163.192', 'port': 3128, 'protocol': 'http', 'city': 'Montreal', 'latencyMs': 98},
        {'host': '158.69.243.155', 'port': 9300, 'protocol': 'socks5', 'city': 'Vancouver', 'latencyMs': 110},
        {'host': '192.99.101.44', 'port': 1080, 'protocol': 'socks5', 'city': 'Quebec', 'latencyMs': 105},
        {'host': '144.217.101.245', 'port': 8080, 'protocol': 'http', 'city': 'Ottawa', 'latencyMs': 100}
    ],
    'FR': [
        {'host': '51.15.228.188', 'port': 1080, 'protocol': 'socks5', 'city': 'Paris', 'latencyMs': 90},
        {'host': '51.254.108.199', 'port': 3128, 'protocol': 'http', 'city': 'Roubaix', 'latencyMs': 96},
        {'host': '163.172.189.131', 'port': 1080, 'protocol': 'socks5', 'city': 'Marseille', 'latencyMs': 102},
        {'host': '212.83.188.134', 'port': 8080, 'protocol': 'http', 'city': 'Lyon', 'latencyMs': 99},
        {'host': '51.75.147.41', 'port': 1080, 'protocol': 'socks5', 'city': 'Toulouse', 'latencyMs': 104}
    ],
    'NL': [
        {'host': '185.107.56.88', 'port': 1080, 'protocol': 'socks5', 'city': 'Amsterdam', 'latencyMs': 82},
        {'host': '188.166.115.93', 'port': 1080, 'protocol': 'socks5', 'city': 'Rotterdam', 'latencyMs': 86},
        {'host': '178.62.247.143', 'port': 3128, 'protocol': 'http', 'city': 'Amsterdam', 'latencyMs': 85},
        {'host': '194.38.20.10', 'port': 1080, 'protocol': 'socks5', 'city': 'Utrecht', 'latencyMs': 89},
        {'host': '145.220.101.5', 'port': 8080, 'protocol': 'http', 'city': 'The Hague', 'latencyMs': 88}
    ],
    'SG': [
        {'host': '128.199.202.124', 'port': 1080, 'protocol': 'socks5', 'city': 'Singapore', 'latencyMs': 115},
        {'host': '178.128.89.207', 'port': 8080, 'protocol': 'http', 'city': 'Singapore', 'latencyMs': 120},
        {'host': '139.59.227.185', 'port': 1080, 'protocol': 'socks5', 'city': 'Jurong', 'latencyMs': 118},
        {'host': '159.89.205.105', 'port': 3128, 'protocol': 'http', 'city': 'Singapore', 'latencyMs': 122},
        {'host': '206.189.155.191', 'port': 1080, 'protocol': 'socks5', 'city': 'Marina Bay', 'latencyMs': 116}
    ],
    'JP': [
        {'host': '133.242.17.24', 'port': 1080, 'protocol': 'socks5', 'city': 'Tokyo', 'latencyMs': 125},
        {'host': '153.121.57.102', 'port': 8080, 'protocol': 'http', 'city': 'Osaka', 'latencyMs': 130},
        {'host': '160.16.143.189', 'port': 1080, 'protocol': 'socks5', 'city': 'Tokyo', 'latencyMs': 128},
        {'host': '118.27.32.222', 'port': 3128, 'protocol': 'http', 'city': 'Yokohama', 'latencyMs': 132},
        {'host': '133.130.98.71', 'port': 1080, 'protocol': 'socks5', 'city': 'Nagoya', 'latencyMs': 135}
    ],
    'AU': [
        {'host': '139.99.155.201', 'port': 1080, 'protocol': 'socks5', 'city': 'Sydney', 'latencyMs': 165},
        {'host': '13.239.111.23', 'port': 8080, 'protocol': 'http', 'city': 'Melbourne', 'latencyMs': 170},
        {'host': '54.252.170.198', 'port': 1080, 'protocol': 'socks5', 'city': 'Sydney', 'latencyMs': 168},
        {'host': '139.99.130.70', 'port': 3128, 'protocol': 'http', 'city': 'Brisbane', 'latencyMs': 175},
        {'host': '103.107.198.12', 'port': 1080, 'protocol': 'socks5', 'city': 'Perth', 'latencyMs': 180}
    ],
    'BR': [
        {'host': '177.93.111.45', 'port': 8080, 'protocol': 'http', 'city': 'São Paulo', 'latencyMs': 185},
        {'host': '177.136.251.130', 'port': 1080, 'protocol': 'socks5', 'city': 'Rio de Janeiro', 'latencyMs': 190},
        {'host': '186.250.99.24', 'port': 8080, 'protocol': 'http', 'city': 'Curitiba', 'latencyMs': 195},
        {'host': '191.242.100.18', 'port': 1080, 'protocol': 'socks5', 'city': 'São Paulo', 'latencyMs': 188},
        {'host': '179.180.12.110', 'port': 3128, 'protocol': 'http', 'city': 'Brasília', 'latencyMs': 198}
    ],
    'TR': [
        {'host': '185.169.54.218', 'port': 1080, 'protocol': 'socks5', 'city': 'Istanbul', 'latencyMs': 110},
        {'host': '176.240.100.82', 'port': 8080, 'protocol': 'http', 'city': 'Ankara', 'latencyMs': 120},
        {'host': '185.92.3.114', 'port': 1080, 'protocol': 'socks5', 'city': 'Izmir', 'latencyMs': 118},
        {'host': '78.188.190.170', 'port': 8080, 'protocol': 'http', 'city': 'Istanbul', 'latencyMs': 115},
        {'host': '195.175.254.12', 'port': 1080, 'protocol': 'socks5', 'city': 'Bursa', 'latencyMs': 122}
    ],
    'AE': [
        {'host': '83.110.86.15', 'port': 8080, 'protocol': 'http', 'city': 'Dubai', 'latencyMs': 115},
        {'host': '94.200.220.10', 'port': 1080, 'protocol': 'socks5', 'city': 'Abu Dhabi', 'latencyMs': 120},
        {'host': '86.96.195.80', 'port': 8080, 'protocol': 'http', 'city': 'Dubai', 'latencyMs': 118},
        {'host': '5.195.200.44', 'port': 1080, 'protocol': 'socks5', 'city': 'Sharjah', 'latencyMs': 125},
        {'host': '185.140.248.11', 'port': 8080, 'protocol': 'http', 'city': 'Dubai', 'latencyMs': 116}
    ],
    'SA': [
        {'host': '212.138.90.10', 'port': 8080, 'protocol': 'http', 'city': 'Riyadh', 'latencyMs': 120},
        {'host': '188.50.210.15', 'port': 1080, 'protocol': 'socks5', 'city': 'Jeddah', 'latencyMs': 128},
        {'host': '82.205.10.45', 'port': 8080, 'protocol': 'http', 'city': 'Dammam', 'latencyMs': 125},
        {'host': '151.254.12.90', 'port': 1080, 'protocol': 'socks5', 'city': 'Riyadh', 'latencyMs': 122},
        {'host': '213.136.80.22', 'port': 8080, 'protocol': 'http', 'city': 'Mecca', 'latencyMs': 130}
    ],
    'ID': [
        {'host': '103.154.225.10', 'port': 8080, 'protocol': 'http', 'city': 'Jakarta', 'latencyMs': 135},
        {'host': '182.253.114.15', 'port': 1080, 'protocol': 'socks5', 'city': 'Surabaya', 'latencyMs': 142},
        {'host': '114.7.12.180', 'port': 8080, 'protocol': 'http', 'city': 'Bandung', 'latencyMs': 140},
        {'host': '103.167.112.50', 'port': 1080, 'protocol': 'socks5', 'city': 'Jakarta', 'latencyMs': 138},
        {'host': '36.67.240.11', 'port': 8080, 'protocol': 'http', 'city': 'Medan', 'latencyMs': 145}
    ],
    'MY': [
        {'host': '175.139.215.10', 'port': 8080, 'protocol': 'http', 'city': 'Kuala Lumpur', 'latencyMs': 120},
        {'host': '210.186.200.40', 'port': 1080, 'protocol': 'socks5', 'city': 'Penang', 'latencyMs': 128},
        {'host': '115.164.88.25', 'port': 8080, 'protocol': 'http', 'city': 'Johor Bahru', 'latencyMs': 125},
        {'host': '175.143.120.10', 'port': 1080, 'protocol': 'socks5', 'city': 'Kuala Lumpur', 'latencyMs': 122},
        {'host': '124.217.228.14', 'port': 8080, 'protocol': 'http', 'city': 'Cyberjaya', 'latencyMs': 124}
    ],
    'BD': [
        {'host': '103.119.100.12', 'port': 8080, 'protocol': 'http', 'city': 'Dhaka', 'latencyMs': 130},
        {'host': '103.88.220.15', 'port': 1080, 'protocol': 'socks5', 'city': 'Chittagong', 'latencyMs': 140},
        {'host': '119.148.12.44', 'port': 8080, 'protocol': 'http', 'city': 'Dhaka', 'latencyMs': 132},
        {'host': '103.145.118.20', 'port': 1080, 'protocol': 'socks5', 'city': 'Sylhet', 'latencyMs': 145},
        {'host': '180.211.200.10', 'port': 8080, 'protocol': 'http', 'city': 'Rajshahi', 'latencyMs': 148}
    ],
    'TH': [
        {'host': '110.164.250.12', 'port': 8080, 'protocol': 'http', 'city': 'Bangkok', 'latencyMs': 125},
        {'host': '183.88.210.44', 'port': 1080, 'protocol': 'socks5', 'city': 'Chiang Mai', 'latencyMs': 135},
        {'host': '118.175.12.30', 'port': 8080, 'protocol': 'http', 'city': 'Nonthaburi', 'latencyMs': 128},
        {'host': '119.46.220.15', 'port': 1080, 'protocol': 'socks5', 'city': 'Bangkok', 'latencyMs': 126},
        {'host': '202.44.240.10', 'port': 8080, 'protocol': 'http', 'city': 'Phuket', 'latencyMs': 138}
    ],
    'VN': [
        {'host': '118.70.180.15', 'port': 8080, 'protocol': 'http', 'city': 'Hanoi', 'latencyMs': 128},
        {'host': '123.30.240.10', 'port': 1080, 'protocol': 'socks5', 'city': 'Ho Chi Minh City', 'latencyMs': 132},
        {'host': '14.161.20.45', 'port': 8080, 'protocol': 'http', 'city': 'Da Nang', 'latencyMs': 135},
        {'host': '113.160.220.12', 'port': 1080, 'protocol': 'socks5', 'city': 'Hanoi', 'latencyMs': 130},
        {'host': '125.235.10.80', 'port': 8080, 'protocol': 'http', 'city': 'Hai Phong', 'latencyMs': 136}
    ],
    'KR': [
        {'host': '211.218.120.10', 'port': 8080, 'protocol': 'http', 'city': 'Seoul', 'latencyMs': 118},
        {'host': '121.160.200.15', 'port': 1080, 'protocol': 'socks5', 'city': 'Busan', 'latencyMs': 124},
        {'host': '175.195.12.40', 'port': 8080, 'protocol': 'http', 'city': 'Incheon', 'latencyMs': 120},
        {'host': '112.170.210.25', 'port': 1080, 'protocol': 'socks5', 'city': 'Seoul', 'latencyMs': 119},
        {'host': '218.145.100.12', 'port': 8080, 'protocol': 'http', 'city': 'Daegu', 'latencyMs': 126}
    ],
    'CN': [
        {'host': '103.242.110.15', 'port': 8080, 'protocol': 'http', 'city': 'Hong Kong', 'latencyMs': 105},
        {'host': '47.90.200.10', 'port': 1080, 'protocol': 'socks5', 'city': 'Hong Kong', 'latencyMs': 108},
        {'host': '118.140.22.45', 'port': 8080, 'protocol': 'http', 'city': 'Kowloon', 'latencyMs': 110},
        {'host': '103.116.200.12', 'port': 1080, 'protocol': 'socks5', 'city': 'Wan Chai', 'latencyMs': 107},
        {'host': '203.186.110.20', 'port': 8080, 'protocol': 'http', 'city': 'Central', 'latencyMs': 112}
    ],
    'IT': [
        {'host': '185.25.200.12', 'port': 1080, 'protocol': 'socks5', 'city': 'Rome', 'latencyMs': 98},
        {'host': '93.186.250.10', 'port': 8080, 'protocol': 'http', 'city': 'Milan', 'latencyMs': 92},
        {'host': '151.99.120.45', 'port': 1080, 'protocol': 'socks5', 'city': 'Turin', 'latencyMs': 95},
        {'host': '217.133.10.80', 'port': 8080, 'protocol': 'http', 'city': 'Naples', 'latencyMs': 102},
        {'host': '80.86.140.15', 'port': 1080, 'protocol': 'socks5', 'city': 'Florence', 'latencyMs': 99}
    ],
    'ES': [
        {'host': '185.120.200.10', 'port': 1080, 'protocol': 'socks5', 'city': 'Madrid', 'latencyMs': 95},
        {'host': '80.24.120.15', 'port': 8080, 'protocol': 'http', 'city': 'Barcelona', 'latencyMs': 92},
        {'host': '195.77.200.40', 'port': 1080, 'protocol': 'socks5', 'city': 'Valencia', 'latencyMs': 99},
        {'host': '213.97.10.80', 'port': 8080, 'protocol': 'http', 'city': 'Seville', 'latencyMs': 105},
        {'host': '88.2.140.25', 'port': 1080, 'protocol': 'socks5', 'city': 'Malaga', 'latencyMs': 108}
    ],
    'CH': [
        {'host': '185.150.200.10', 'port': 1080, 'protocol': 'socks5', 'city': 'Zurich', 'latencyMs': 86},
        {'host': '194.209.12.45', 'port': 8080, 'protocol': 'http', 'city': 'Geneva', 'latencyMs': 89},
        {'host': '195.141.10.80', 'port': 1080, 'protocol': 'socks5', 'city': 'Bern', 'latencyMs': 88},
        {'host': '178.209.40.12', 'port': 8080, 'protocol': 'http', 'city': 'Basel', 'latencyMs': 90}
    ],
    'SE': [
        {'host': '185.180.200.10', 'port': 1080, 'protocol': 'socks5', 'city': 'Stockholm', 'latencyMs': 90},
        {'host': '193.182.12.45', 'port': 8080, 'protocol': 'http', 'city': 'Gothenburg', 'latencyMs': 94},
        {'host': '194.14.10.80', 'port': 1080, 'protocol': 'socks5', 'city': 'Malmö', 'latencyMs': 92},
        {'host': '83.255.140.12', 'port': 8080, 'protocol': 'http', 'city': 'Uppsala', 'latencyMs': 96}
    ],
    'PL': [
        {'host': '185.190.200.10', 'port': 1080, 'protocol': 'socks5', 'city': 'Warsaw', 'latencyMs': 92},
        {'host': '91.231.12.45', 'port': 8080, 'protocol': 'http', 'city': 'Krakow', 'latencyMs': 96},
        {'host': '195.116.10.80', 'port': 1080, 'protocol': 'socks5', 'city': 'Wroclaw', 'latencyMs': 98},
        {'host': '83.238.140.12', 'port': 8080, 'protocol': 'http', 'city': 'Poznan', 'latencyMs': 95}
    ],
    'UA': [
        {'host': '185.200.200.10', 'port': 1080, 'protocol': 'socks5', 'city': 'Kyiv', 'latencyMs': 105},
        {'host': '91.220.12.45', 'port': 8080, 'protocol': 'http', 'city': 'Lviv', 'latencyMs': 108},
        {'host': '195.138.10.80', 'port': 1080, 'protocol': 'socks5', 'city': 'Odesa', 'latencyMs': 112},
        {'host': '178.94.140.12', 'port': 8080, 'protocol': 'http', 'city': 'Dnipro', 'latencyMs': 115}
    ],
    'MX': [
        {'host': '187.189.120.10', 'port': 8080, 'protocol': 'http', 'city': 'Mexico City', 'latencyMs': 120},
        {'host': '201.140.200.15', 'port': 1080, 'protocol': 'socks5', 'city': 'Guadalajara', 'latencyMs': 125},
        {'host': '189.240.12.45', 'port': 8080, 'protocol': 'http', 'city': 'Monterrey', 'latencyMs': 122},
        {'host': '200.68.10.80', 'port': 1080, 'protocol': 'socks5', 'city': 'Puebla', 'latencyMs': 128}
    ],
    'AR': [
        {'host': '190.111.120.10', 'port': 8080, 'protocol': 'http', 'city': 'Buenos Aires', 'latencyMs': 175},
        {'host': '200.45.200.15', 'port': 1080, 'protocol': 'socks5', 'city': 'Cordoba', 'latencyMs': 180},
        {'host': '181.47.12.45', 'port': 8080, 'protocol': 'http', 'city': 'Rosario', 'latencyMs': 182},
        {'host': '190.210.10.80', 'port': 1080, 'protocol': 'socks5', 'city': 'Mendoza', 'latencyMs': 185}
    ],
    'ZA': [
        {'host': '197.242.120.10', 'port': 8080, 'protocol': 'http', 'city': 'Johannesburg', 'latencyMs': 170},
        {'host': '105.210.200.15', 'port': 1080, 'protocol': 'socks5', 'city': 'Cape Town', 'latencyMs': 178},
        {'host': '196.25.12.45', 'port': 8080, 'protocol': 'http', 'city': 'Durban', 'latencyMs': 182},
        {'host': '41.76.10.80', 'port': 1080, 'protocol': 'socks5', 'city': 'Pretoria', 'latencyMs': 175}
    ],
    'EG': [
        {'host': '156.200.120.10', 'port': 8080, 'protocol': 'http', 'city': 'Cairo', 'latencyMs': 140},
        {'host': '197.35.200.15', 'port': 1080, 'protocol': 'socks5', 'city': 'Alexandria', 'latencyMs': 145},
        {'host': '41.130.12.45', 'port': 8080, 'protocol': 'http', 'city': 'Giza', 'latencyMs': 142},
        {'host': '156.210.10.80', 'port': 1080, 'protocol': 'socks5', 'city': 'Port Said', 'latencyMs': 148}
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
        ok, latency, detected_proto = test_proxy_socket(item['protocol'], item['host'], item['port'], timeout=2.0)
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
