"""
Runtime hook per PyInstaller su Windows.
Viene eseguito PRIMA di qualsiasi modulo dell'applicazione per configurare
la ricerca dei binari DLL nativi di PyTorch (torch/lib, torch/bin), DeepFilterLib, numpy e Qt.
"""

import os
import sys

if sys.platform == "win32":
    if getattr(sys, "frozen", False):
        base_dir = getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))
    else:
        base_dir = os.path.dirname(os.path.abspath(__file__))

    dll_paths = [
        base_dir,
        os.path.join(base_dir, "torch", "lib"),
        os.path.join(base_dir, "torch", "bin"),
        os.path.join(base_dir, "torch"),
        os.path.join(base_dir, "DeepFilterLib.libs"),
        os.path.join(base_dir, "numpy.libs"),
        os.path.join(base_dir, "scipy.libs"),
        os.path.join(base_dir, "PySide6"),
        os.path.join(base_dir, "bin"),
    ]

    for p in dll_paths:
        if os.path.isdir(p):
            try:
                os.add_dll_directory(p)
            except Exception:
                pass
            os.environ["PATH"] = p + os.pathsep + os.environ.get("PATH", "")
