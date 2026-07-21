# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_submodules

hiddenimports = ['fitz', 'PIL', 'PIL.Image', 'PIL.ImageTk', 'sv_ttk', 'darkdetect', 'win32com', 'win32com.client', 'pythoncom', 'core', 'core.config', 'core.i18n', 'core.theme', 'modules', 'modules.pdf_tools_tab', 'modules.psd_tools_tab']
hiddenimports += collect_submodules('core')
hiddenimports += collect_submodules('modules')


a = Analysis(
    ['C:\\Users\\Admin\\Desktop\\tools_app\\main.py'],
    pathex=['C:\\Users\\Admin\\Desktop\\tools_app'],
    binaries=[],
    datas=[('C:\\Users\\Admin\\Desktop\\tools_app\\assets', 'assets')],
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
    name='PrizmaStudio',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['C:\\Users\\Admin\\Desktop\\tools_app\\assets\\icon.ico'],
)
