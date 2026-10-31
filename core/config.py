"""
Modulo core/config.py: Gestione percorsi per risorse, modelli e binari,
supportando sia l'esecuzione da sorgente che il bundle PyInstaller (--onedir / sys._MEIPASS).
"""

import os
import sys
from pathlib import Path


def get_base_dir() -> Path:
    """
    Restituisce la cartella base dell'applicazione.
    - In modalità pacchettizzata (PyInstaller): sys._MEIPASS o cartella dell'eseguibile
    - In modalità script: directory radice del progetto
    """
    if getattr(sys, "frozen", False):
        # Se impacchettato con PyInstaller
        if hasattr(sys, "_MEIPASS"):
            return Path(sys._MEIPASS).resolve()
        return Path(sys.executable).parent.resolve()
    
    # Directory del modulo corrente -> cartella padre (radice del progetto)
    return Path(__file__).parent.parent.resolve()


def get_app_data_dir() -> Path:
    """Restituisce la cartella per i dati utente persistenti e output predefiniti."""
    base_user = Path(os.environ.get("LOCALAPPDATA", Path.home()))
    app_data = base_user / "VoiceCleaner"
    app_data.mkdir(parents=True, exist_ok=True)
    return app_data


def get_bundled_model_dir(model_name: str = "DeepFilterNet3") -> Path:
    """
    Restituisce il percorso del modello pre-addestrato incluso nel pacchetto.
    Cerca in base_dir/models/<model_name>, altrimenti usa la cache predefinita di DeepFilterNet.
    """
    bundled = get_base_dir() / "models" / model_name
    if bundled.exists() and (bundled / "config.ini").exists():
        return bundled
    
    # Fallback su cartella locale appdata
    appdata_cache = Path(os.environ.get("LOCALAPPDATA", "")) / "DeepFilterNet" / "DeepFilterNet" / "Cache" / model_name
    if appdata_cache.exists():
        return appdata_cache
        
    return bundled


def get_bundled_ffmpeg() -> Path:
    """
    Restituisce il percorso dell'eseguibile FFmpeg incluso.
    Verifica prima la sottocartella bin/ dell'applicazione.
    """
    base = get_base_dir()
    # Verifica base/bin/ffmpeg.exe
    candidate1 = base / "bin" / "ffmpeg.exe"
    if candidate1.is_file():
        return candidate1
        
    # Verifica base/ffmpeg.exe
    candidate2 = base / "ffmpeg.exe"
    if candidate2.is_file():
        return candidate2

    # Verifica rispetto a sys.executable
    if getattr(sys, "frozen", False):
        exe_dir = Path(sys.executable).parent
        candidate3 = exe_dir / "bin" / "ffmpeg.exe"
        if candidate3.is_file():
            return candidate3
        candidate4 = exe_dir / "ffmpeg.exe"
        if candidate4.is_file():
            return candidate4

    return candidate1


def get_asset_path(filename: str) -> Path:
    """Restituisce il percorso di un asset grafico (icona, logo, ecc.)."""
    asset = get_base_dir() / "assets" / filename
    return asset
