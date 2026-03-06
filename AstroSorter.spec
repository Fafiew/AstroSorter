# -*- mode: python ; coding: utf-8 -*-

import os
import sys

block_cipher = None

# Get the project root
root_dir = os.path.dirname(os.path.abspath(SPEC))

a = Analysis(
    [os.path.join(root_dir, 'AstroSorter', 'main.py')],
    pathex=[root_dir],
    binaries=[],
    datas=[
        (os.path.join(root_dir, 'AstroSorter', 'version.py'), 'AstroSorter'),
        # Include entire assets folder
        (os.path.join(root_dir, 'assets'), 'assets'),
    ],
    hiddenimports=[
        # Main dependencies
        'customtkinter',
        'customtkinter.*',
        'PIL',
        'PIL.Image',
        'PIL.ImageFilter',
        'PIL.ExifTags',
        'PIL.TiffImagePlugin',
        'rawpy',
        'numpy',
        'numpy.core',
        'numpy.lib',
        'skimage',
        'skimage.io',
        'skimage.color',
        'skimage.exposure',
        'tqdm',
        'tqdm.auto',
        'darkdetect',
        'darkdetect._detector',
        'psutil',
        # Tkinter
        'tkinter',
        'tkinter.ttk',
        'tkinter.filedialog',
        'tkinter.messagebox',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='AstroSorter',
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
    icon=os.path.join(root_dir, 'assets', 'fullres.ico'),
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='AstroSorter',
)
