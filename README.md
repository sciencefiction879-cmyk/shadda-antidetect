# Shadda Anti Detect v0.3 🛡️

**Shadda Anti Detect** is a high-performance multi-profile anti-detection browser and fingerprint manager designed for advanced automation, multi-channel operations, YouTube workflow orchestration, and account security.

---

## 🌟 Key Features

- 🎭 **Advanced Fingerprint Protection**: Deep spoofing of WebGL, AudioContext, Canvas, Client Rects, Navigator properties, Screen geometry, and Hardware Concurrency.
- 👤 **In-Browser Profile Identity**: Displays the profile name clearly in the window title (`[Page Title] — [Profile Name]`) and via an interactive, draggable, collapsible status pill badge inside every profile window.
- 🔒 **Permanent Specific Proxy Selection & Locking**: Numbered Master Proxy Pool (`Proxy #1` to `Proxy #43+`) with per-profile permanent locking. Once assigned, a proxy stays locked to its profile indefinitely—zero random switching or silent fallback rotations.
- 📊 **Real-Time Assignment Tracking**: Interactive proxy selector shows live availability (`🟢 Available`, `🔒 Locked to this Profile`, `🔒 Assigned to: [Profile Name]`) with search, filter tabs, and one-click unassign.
- ▶️ **Dedicated YouTube Automation**: Tailored GitHub Actions automation workflows exclusively for YouTube:
  - `Studio Upload & Management` (`studio`)
  - `Video Watch & Engagement` (`watch`)
  - `Full Automation Pipeline` (`full`)
- 🤖 **In-Browser Guided Automation HUD**: Live overlay banner displaying current profile, locked proxy, stage progress, and manual checkpoint approvals.
- 📱 **Mobile & Desktop Emulation**: Authentic Android devices (Google Nexus 5, Nexus 7, Nexus 4, Nexus 10, Samsung Galaxy S24) and macOS / Windows desktop profiles.
- 🛡️ **Zero-Leak Kill Switch**:
  - **Pre-Flight Gatekeeper**: Verifies proxy socket reachability before browser launch.
  - **Loopback Proxy Bypass Protection**: Prevents internal DevTools/extension connection breakage while routing all external web traffic through the proxy.
  - **WebRTC Protection**: Strict UDP proxy routing (`disable_non_proxied_udp`) preventing STUN/TURN leaks.
- 🌐 **Comprehensive World Timezones**: Auto-sync local timezones to proxy geo-locations across all global regions.
- ⚡ **Zero Unnecessary Bloat**: Clean, modern, responsive interface.

---

## 📥 Downloads & Releases

Official binaries are compiled and published directly via GitHub Actions:

| Platform | Package | Download Link |
| :--- | :--- | :--- |
| **Android Mobile (Direct)** | `Shadda-Anti-Detect.apk` (Android 7.0 - 15+) | [📲 **Download Android APK (Direct)**](https://raw.githubusercontent.com/sciencefiction879-cmyk/shadda-antidetect/main/releases/Shadda-Anti-Detect.apk) |
| **Android Mobile (Release Mirror)** | `Shadda-Anti-Detect.apk` (Alternative Mirror) | [📲 **GitHub Release Mirror**](https://github.com/sciencefiction879-cmyk/shadda-antidetect/releases/download/v0.3/Shadda-Anti-Detect.apk) |
| **Windows 10 / 11 (64-bit)** | `Shadda-Anti-Detect.exe` (Standalone Executable) | [💻 **Download Windows EXE**](https://github.com/sciencefiction879-cmyk/shadda-antidetect/releases/download/v0.3/Shadda-Anti-Detect.exe) |
| **Windows Portable** | `Shadda-Anti-Detect-Windows-x64.zip` (Portable ZIP) | [📦 **Download Windows Portable ZIP**](https://github.com/sciencefiction879-cmyk/shadda-antidetect/releases/download/v0.3/Shadda-Anti-Detect-Windows-x64.zip) |
| **macOS (Apple Silicon & Intel)** | `Shadda-Anti-Detect-0.3.dmg` (Disk Image Installer) | [🍏 **Download macOS DMG**](https://github.com/sciencefiction879-cmyk/shadda-antidetect/releases/download/v0.3/Shadda-Anti-Detect-0.3.dmg) |

👉 **Full Release Details**: [https://github.com/sciencefiction879-cmyk/shadda-antidetect/releases/tag/v0.3](https://github.com/sciencefiction879-cmyk/shadda-antidetect/releases/tag/v0.3)

---

## 🚀 Installation & Usage

### macOS:
1. Download **`Shadda Anti Detect-0.3.dmg`**.
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
