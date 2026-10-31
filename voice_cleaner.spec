# -*- mode: python ; coding: utf-8 -*-
"""
File di configurazione PyInstaller per Voice Cleaner Desktop.
Modalità: onedir (cartella per avvio rapido).
Ottimizzato per escludere moduli pesanti non utilizzati (QtWebEngine, Gradio, ecc.).
"""

import sys
import os
from pathlib import Path
from PyInstaller.utils.hooks import collect_all

block_cipher = None
base_dir = os.path.abspath(SPECPATH)

# Raccoglie in modo affidabile tutte le dipendenze binarie e moduli di PyTorch, Torchaudio e DeepFilterNet
torch_datas, torch_binaries, torch_hidden = collect_all('torch')
df_datas, df_binaries, df_hidden = collect_all('df')
ta_datas, ta_binaries, ta_hidden = collect_all('torchaudio')

datas = [
    (os.path.join(base_dir, 'models', 'DeepFilterNet3'), os.path.join('models', 'DeepFilterNet3')),
    (os.path.join(base_dir, 'assets'), 'assets'),
] + torch_datas + df_datas + ta_datas

binaries = [
    (os.path.join(base_dir, 'bin', 'ffmpeg.exe'), 'bin'),
] + torch_binaries + df_binaries + ta_binaries

hiddenimports = list(set([
    'torch',
    'torch._C',
    'deepfilterlib',
    'df',
    'df.enhance',
    'df.io',
    'df.model',
    'df.modules',
    'df.checkpoint',
    'df.config',
    'noisereduce',
    'soundfile',
    'scipy.signal',
    'scipy.special',
    'torchaudio',
    'torchaudio.backend',
    'torchaudio.backend.common',
    'PySide6.QtCore',
    'PySide6.QtGui',
    'PySide6.QtWidgets',
    'PySide6.QtMultimedia',
] + torch_hidden + df_hidden + ta_hidden))

# Esclusioni mirate per ridurre la dimensione del pacchetto senza rompere PyTorch
excludes = [
    # Moduli pesanti di PySide6 non utilizzati
    'PySide6.QtWebEngine',
    'PySide6.QtWebEngineCore',
    'PySide6.QtWebEngineWidgets',
    'PySide6.QtWebEngineQuick',
    'PySide6.QtQuick',
    'PySide6.QtQuickWidgets',
    'PySide6.QtQml',
    'PySide6.QtPdf',
    'PySide6.QtPdfWidgets',
    'PySide6.Qt3DCore',
    'PySide6.Qt3DRender',
    'PySide6.Qt3DInput',
    'PySide6.QtVirtualKeyboard',
    'PySide6.QtSensors',
    'PySide6.QtPositioning',
    'PySide6.QtDesigner',
    'PySide6.QtUiTools',

    # Moduli di sviluppo di PyTorch non necessari all'inferenza CPU
    'caffe2',
    'functorch',

    # Moduli dell'interfaccia web Gradio (non necessari nell'app desktop nativa)
    'gradio',
    'gradio_client',
    'fastapi',
    'uvicorn',
    'starlette',
    'pandas',
    'matplotlib',
    'tkinter',
    'IPython',
    'notebook',
    'jupyter',
    'markdown_it',
]

a = Analysis(
    ['desktop_app.py'],
    pathex=[base_dir],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=['rthook_torch.py'],
    excludes=excludes,
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
    name='VoiceCleaner',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=os.path.join(base_dir, 'assets', 'icon.ico'),
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='VoiceCleaner',
)
