# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path
from PyInstaller.utils.hooks import collect_all

SPEC_DIR = Path(SPECPATH).resolve()
ROOT = SPEC_DIR.parent
APP = ROOT / "app"
ASSETS = ROOT / "assets"

# Fail early with a useful message if the project layout is not what the
# build expects. SPECPATH is the directory containing this .spec file.
LAUNCHER = APP / "launcher.py"
if not LAUNCHER.exists():
    raise FileNotFoundError(
        f"Launcher nao encontrado: {LAUNCHER}. "
        f"SPECPATH={SPEC_DIR}; ROOT calculado={ROOT}"
    )

datas = [
    (str(ROOT / "VERSAO.txt"), "."),
    (str(ASSETS), "assets"),
]
binaries = []
hiddenimports = []

for pacote in ("tkinterdnd2", "playwright"):
    d, b, h = collect_all(pacote)
    datas += d
    binaries += b
    hiddenimports += h

a = Analysis(
    [str(LAUNCHER)],
    pathex=[str(APP)],
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
    name="AutomacaoAgilize",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    icon=str(ASSETS / "automacao-agilize.ico"),
    version=str(ROOT / "build" / "version_info.txt"),
    uac_admin=False,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="AutomacaoAgilize",
)
