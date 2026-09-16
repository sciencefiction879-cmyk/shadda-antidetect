# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_all

datas = [('static', 'static'), ('releases', 'releases'), ('anti_detect_extension', 'anti_detect_extension'), ('bootstrap_config.json', '.'), ('github_client.pyc', '.'), ('github_accounts.json', '.')]
binaries = []
hiddenimports = ['proxies_pool', 'ads_manager', 'auto_updater', 'country_proxies', 'automation_controller', 'browser_runner', 'stealth_injector', 'github_client', 'youtube_uploader_manager', 'webview', 'objc', 'WebKit', 'Foundation', 'AppKit', 'websocket', 'bottle', 'proxy_tools']
tmp_ret = collect_all('webview')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]


a = Analysis(
    ['server.py'],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='Shadda Anti Detect',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['ShaddaAntiDetect.icns'],
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='Shadda Anti Detect',
)
app = BUNDLE(
    coll,
    name='Shadda Anti Detect.app',
    icon='ShaddaAntiDetect.icns',
    bundle_identifier='com.shadda.antidetect',
)
