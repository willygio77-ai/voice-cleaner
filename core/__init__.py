"""
Package core: Modulo condiviso per l'elaborazione audio, motori di denoising e gestione I/O.
Utilizzato sia dall'applicazione Web (Gradio) che dall'applicazione Desktop (PySide6).
"""

import sys
import types

# Torchaudio backend compatibility shim per torchaudio >= 2.1
try:
    import torchaudio
    if not hasattr(torchaudio, "backend"):
        backend = types.ModuleType("torchaudio.backend")
        common = types.ModuleType("torchaudio.backend.common")
        common.AudioMetaData = getattr(torchaudio, "AudioMetaData", None)
        backend.common = common
        sys.modules["torchaudio.backend"] = backend
        sys.modules["torchaudio.backend.common"] = common
except Exception:
    pass
