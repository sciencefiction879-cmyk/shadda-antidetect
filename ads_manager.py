import json
import os
import sys

APP_VERSION = "0.1"

BASE_DIR = os.path.dirname(sys.executable) if getattr(sys, 'frozen', False) else os.path.dirname(os.path.abspath(__file__))
BOOTSTRAP_FILE = os.path.join(getattr(sys, '_MEIPASS', BASE_DIR), 'bootstrap_config.json')

DEFAULT_CONFIG = {
    "updates": {
        "enabled": False,
        "latestVersion": APP_VERSION,
        "mandatory": False,
        "title": "⚡ Shadda Anti Detect v0.1",
        "changelog": "• Official macOS Release v0.1\n• 100% Anti-detection shield active\n• Multi-profile isolation & proxy tools",
        "downloadUrl": "",
        "buttonText": "Up to date",
        "assetUrl": "",
        "sha256": "",
        "size": 0
    },
    "banner": {
        "enabled": True,
        "badge": "SHADDA PRO",
        "title": "Welcome to Shadda Anti Detect v0.1",
        "description": "Multi-profile anti-detect browser setup for Facebook, YouTube, TikTok and creator automation.",
        "buttonText": "Ready",
        "linkUrl": "#",
        "imageUrl": ""
    },
    "popup": {
        "enabled": False,
        "id": "popup_shadda_01",
        "badge": "INFO",
        "title": "Welcome to Shadda Anti Detect",
        "message": "Manage multiple isolated browser fingerprints with proxies.",
        "buttonText": "Got It",
        "linkUrl": "",
        "imageUrl": "",
        "showOncePerSession": True
    },
    "donation": {
        "enabled": True,
        "title": "Support Shadda Anti Detect",
        "subtitle": "Help us keep this tool 100% free and maintained for macOS.",
        "usdtBep20": "0x3e8eec2f6c5618f9cf3c180d7632d46415b660e1",
        "usdtTrc20": "TRrmgUiPdbHm1zJUNx6Meq3eJ5mi4aBvcf",
        "coffeeUrl": "https://buymeacoffee.com",
        "customNote": "Thank you for supporting continuous development!",
        "showUsdtTrc20": True,
        "showUsdtBep20": True,
        "showCoffee": True
    }
}


def load_ads_config():
    if os.path.exists(BOOTSTRAP_FILE):
        try:
            with open(BOOTSTRAP_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                data.pop('telemetry', None)
                data['updates']['enabled'] = False
                data['updates']['mandatory'] = False
                data['updates']['latestVersion'] = APP_VERSION
                return data
        except Exception:
            pass
    return DEFAULT_CONFIG.copy()


def display_config():
    config = load_ads_config()
    config.pop('telemetry', None)
    config['currentAppVersion'] = APP_VERSION
    config['updates'] = {
        "enabled": False,
        "latestVersion": APP_VERSION,
        "mandatory": False,
        "title": "⚡ Shadda Anti Detect v0.1"
    }
    return config
