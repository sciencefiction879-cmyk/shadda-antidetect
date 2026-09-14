# Shadda Anti Detect v0.1 🛡️

**Shadda Anti Detect** is a high-performance multi-profile anti-detection browser and fingerprint manager designed for advanced automation, social media management, multi-channel operations, and account security.

---

## 🌟 Key Features

- 🎭 **Advanced Fingerprint Protection**: Deep spoofing of WebGL, AudioContext, Canvas, Client Rects, Navigator properties, Screen geometry, and Hardware Concurrency.
- 📱 **Mobile & Desktop Emulation**: Emulate authentic Android devices (Google Nexus 5, Nexus 7, Nexus 4, Nexus 10, Samsung Galaxy S24) as well as macOS and Windows Chrome/Safari profiles.
- 🌍 **Global Country Proxies Hub**: Live residential & datacenter proxy scraper and connector covering 34 countries (Pakistan, India, USA, UK, Germany, Philippines, Russia, Japan, and more).
- 🔒 **Permanent Proxy Locking**: Selected country proxies are permanently locked to profiles to eliminate IP rotation and suspicious shifts.
- 🛡️ **Zero-Leak Kill Switch**:
  - **Pre-Flight Gatekeeper**: Verifies proxy socket reachability before browser launch.
  - **Chromium DNS Lockdown**: DNS resolution is locked strictly to the proxy node (`--host-resolver-rules="MAP * ~NOTFOUND , EXCLUDE <host>"`), ensuring no local IP leaks even if connection drops.
  - **WebRTC Protection**: Strict UDP proxy routing (`disable_non_proxied_udp`) preventing STUN/TURN leaks.
- 🌐 **Comprehensive World Timezones**: Auto-sync local timezones to proxy geo-locations across all global regions.
- ⚡ **Zero Unnecessary Bloat**: No ads, no donation modals, clean and focused interface.

---

## 📥 Downloads & Releases

Official binaries are compiled and published directly via GitHub Actions:

| Platform | Package | Download Link |
| :--- | :--- | :--- |
| **Android Mobile** | `Shadda-Anti-Detect.apk` (Android 7.0 - 15+) | [📲 **Download Android APK**](https://github.com/sciencefiction879-cmyk/shadda-antidetect/releases/download/v0.1/Shadda-Anti-Detect.apk) |
| **Windows 10 / 11 (64-bit)** | `Shadda-Anti-Detect.exe` (Standalone Executable) | [💻 **Download Windows EXE**](https://github.com/sciencefiction879-cmyk/shadda-antidetect/releases/download/v0.1/Shadda-Anti-Detect.exe) |
| **Windows Portable** | `Shadda-Anti-Detect-Windows-x64.zip` (Portable ZIP) | [📦 **Download Windows Portable ZIP**](https://github.com/sciencefiction879-cmyk/shadda-antidetect/releases/download/v0.1/Shadda-Anti-Detect-Windows-x64.zip) |
| **macOS (Apple Silicon & Intel)** | `Shadda-Anti-Detect-0.1.dmg` (Disk Image Installer) | [🍏 **Download macOS DMG**](https://github.com/sciencefiction879-cmyk/shadda-antidetect/releases/download/v0.1/Shadda-Anti-Detect-0.1.dmg) |

👉 **Full Release Details**: [https://github.com/sciencefiction879-cmyk/shadda-antidetect/releases/tag/v0.1](https://github.com/sciencefiction879-cmyk/shadda-antidetect/releases/tag/v0.1)

---

## 🚀 Installation & Usage

### macOS:
1. Download **`Shadda Anti Detect-0.1.dmg`**.
2. Open the DMG and drag **Shadda Anti Detect** into your **Applications** folder.
3. Launch the application. If macOS Gatekeeper prompts on first launch, right-click the app and choose **Open**.

### Windows:
1. Download **`Shadda-Anti-Detect.exe`** (or extract `Shadda-Anti-Detect-Windows-x64.zip`).
2. Run **`Shadda-Anti-Detect.exe`**.

---

## 🛠️ Build from Source

### Prerequisites:
- Python 3.11+
- Google Chrome or Brave Browser installed on your system

```bash
git clone https://github.com/sciencefiction879-cmyk/shadda-antidetect.git
cd shadda-antidetect

# Install dependencies
python3 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -r requirements.txt

# Run development mode
python server.py

# Build macOS DMG
./build_dmg.sh
```

---

## 📄 License
Copyright © 2026 Shadda Anti Detect. All rights reserved.
