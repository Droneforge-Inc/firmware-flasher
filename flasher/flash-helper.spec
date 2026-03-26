# -*- mode: python ; coding: utf-8 -*-
import os
from pathlib import Path

from PyInstaller.utils.hooks import collect_all


ROOT = Path(SPECPATH).resolve()
TARGET_ARCH = os.environ.get("FLASH_HELPER_TARGET_ARCH") or None

datas = []
binaries = []
hiddenimports = []
tmp_ret = collect_all('esptool')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]

def add_vendor_dir(source_dir, dest_root):
    if not source_dir.exists():
        return
    for path in source_dir.rglob("*"):
        if not path.is_file():
            continue
        rel_parent = path.relative_to(source_dir).parent
        dest_dir = str(Path(dest_root) / rel_parent)
        name = path.name
        if name in ("dfu-util", "dfu-util.exe") or name.endswith((".dylib", ".dll", ".so")) or ".so." in name:
            binaries.append((str(path), dest_dir))
        else:
            datas.append((str(path), dest_dir))


add_vendor_dir(ROOT / "vendor" / "dfu-util", "flasher/vendor/dfu-util")


a = Analysis(
    ['simple_usb_upload.py'],
    pathex=[str(ROOT)],
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
    a.binaries,
    a.datas,
    [],
    name='flash-helper',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=TARGET_ARCH,
    codesign_identity=None,
    entitlements_file=None,
)
