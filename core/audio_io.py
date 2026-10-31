"""
Modulo core/audio_io.py: Gestione universale di I/O audio e video e integrazione FFmpeg.
Supporta caricamento ed esportazione di file audio (mp3, wav, m4a, flac, ogg, opus)
ed estrazione/muxing lossless da file video (mp4, mov, mkv, webm, avi).
Gestisce correttamente percorsi con spazi e caratteri accentati (Unicode).
"""

import os
import platform
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Optional, Tuple
import numpy as np
import soundfile as sf

from core.config import get_bundled_ffmpeg

VIDEO_EXTENSIONS = {".mp4", ".mov", ".mkv", ".avi", ".webm", ".flv", ".m4v"}
AUDIO_EXTENSIONS = {".wav", ".mp3", ".m4a", ".aac", ".flac", ".ogg", ".wma", ".opus"}
SUPPORTED_EXTENSIONS = VIDEO_EXTENSIONS | AUDIO_EXTENSIONS


def get_os_ffmpeg_instructions() -> str:
    """Restituisce le istruzioni di installazione di FFmpeg per il sistema operativo corrente."""
    current_os = platform.system()
    if current_os == "Windows":
        return (
            "FFmpeg non trovato nel sistema.\n"
            "Per installarlo su Windows apri il terminale ed esegui:\n"
            "   winget install Gyan.FFmpeg\n"
            "Oppure scarica i binari da https://www.gyan.dev/ffmpeg/builds/"
        )
    elif current_os == "Darwin":
        return (
            "FFmpeg non trovato nel sistema.\n"
            "Per installarlo su macOS con Homebrew, esegui nel terminale:\n"
            "   brew install ffmpeg"
        )
    else:
        return (
            "FFmpeg non trovato nel sistema.\n"
            "Per installarlo su Linux (Debian/Ubuntu), esegui nel terminale:\n"
            "   sudo apt update && sudo apt install ffmpeg"
        )


def get_ffmpeg_exe() -> str:
    """
    Individua l'eseguibile di FFmpeg.
    Ordine di ricerca:
    1. Binario FFmpeg incluso nel pacchetto/applicazione (cartella bin/ o root)
    2. FFmpeg installato nel PATH di sistema
    3. Fallback su imageio-ffmpeg se disponibile
    """
    # 1. Verifica binario incluso nel pacchetto
    bundled = get_bundled_ffmpeg()
    if bundled.is_file():
        return str(bundled.resolve())

    # 2. Verifica PATH di sistema
    sys_ffmpeg = shutil.which("ffmpeg")
    if sys_ffmpeg:
        return sys_ffmpeg

    # 3. Fallback su imageio-ffmpeg
    try:
        import imageio_ffmpeg
        bundled_img = imageio_ffmpeg.get_ffmpeg_exe()
        if bundled_img and os.path.isfile(bundled_img):
            return bundled_img
    except ImportError:
        pass

    raise FileNotFoundError(get_os_ffmpeg_instructions())


def check_ffmpeg_available() -> Tuple[bool, str]:
    """Verifica la presenza di FFmpeg e restituisce lo stato e il percorso o messaggio."""
    try:
        exe = get_ffmpeg_exe()
        return True, f"FFmpeg rilevato: {exe}"
    except FileNotFoundError as e:
        return False, str(e)


def is_video_file(filepath: str) -> bool:
    """Controlla se il file ha un'estensione video comune."""
    ext = os.path.splitext(filepath)[1].lower()
    return ext in VIDEO_EXTENSIONS


def is_supported_file(filepath: str) -> bool:
    """Verifica se il file ha un'estensione supportata dall'applicazione."""
    ext = os.path.splitext(filepath)[1].lower()
    return ext in SUPPORTED_EXTENSIONS


def get_audio_info(filepath: str) -> dict:
    """
    Ottiene informazioni su canali, sample rate e durata dell'audio usando FFmpeg.
    """
    ffmpeg_exe = get_ffmpeg_exe()
    cmd = [ffmpeg_exe, "-hide_banner", "-i", os.path.abspath(filepath)]
    # Usiamo creationflags su Windows per non mostrare finestre console se eseguito da app GUI
    creationflags = 0
    if platform.system() == "Windows":
        creationflags = subprocess.CREATE_NO_WINDOW if hasattr(subprocess, "CREATE_NO_WINDOW") else 0x08000000

    result = subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        errors="replace",
        creationflags=creationflags
    )
    output = result.stderr

    sr = 48000
    channels = 1
    duration = 0.0

    import re
    # Durata: Duration: 00:01:23.45
    dur_match = re.search(r"Duration:\s*(\d+):(\d+):(\d+\.\d+)", output)
    if dur_match:
        hours = int(dur_match.group(1))
        minutes = int(dur_match.group(2))
        seconds = float(dur_match.group(3))
        duration = hours * 3600 + minutes * 60 + seconds

    sr_match = re.search(r"(\d{4,6})\s*Hz", output)
    if sr_match:
        sr = int(sr_match.group(1))

    if "stereo" in output:
        channels = 2
    elif "mono" in output:
        channels = 1
    elif re.search(r"(\d+)\s*channels", output):
        m = re.search(r"(\d+)\s*channels", output)
        channels = int(m.group(1))

    return {"sr": sr, "channels": channels, "duration": duration}


def load_audio(filepath: str, target_sr: Optional[int] = None) -> Tuple[np.ndarray, int]:
    """
    Carica un file audio o estrae la traccia audio da un file video.
    Restituisce:
        audio: ndarray float32 normalizzato in [-1.0, 1.0], shape (channels, samples)
        sr: frequenza di campionamento
    """
    abs_path = os.path.abspath(filepath)
    if not os.path.isfile(abs_path):
        raise FileNotFoundError(f"File non trovato: {abs_path}")

    # Prova lettura diretta con soundfile se formato audio comune non-video
    if not is_video_file(abs_path):
        try:
            data, sr = sf.read(abs_path, dtype="float32", always_2d=True)
            audio = data.T  # (channels, samples)
            if target_sr is not None and sr != target_sr:
                from scipy.signal import resample_poly
                from math import gcd
                g = gcd(sr, target_sr)
                up = target_sr // g
                down = sr // g
                audio = resample_poly(audio, up, down, axis=-1).astype(np.float32)
                sr = target_sr
            return np.ascontiguousarray(audio, dtype=np.float32), sr
        except Exception:
            pass

    # Lettura universale tramite FFmpeg stream pipe
    ffmpeg_exe = get_ffmpeg_exe()
    info = get_audio_info(abs_path)
    channels = min(max(info["channels"], 1), 2)
    sr = target_sr if target_sr is not None else info["sr"]

    cmd = [
        ffmpeg_exe,
        "-y",
        "-hide_banner",
        "-loglevel", "error",
        "-i", abs_path,
        "-vn",
        "-ac", str(channels),
        "-ar", str(sr),
        "-f", "f32le",
        "pipe:1"
    ]

    creationflags = 0
    if platform.system() == "Windows":
        creationflags = subprocess.CREATE_NO_WINDOW if hasattr(subprocess, "CREATE_NO_WINDOW") else 0x08000000

    process = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        creationflags=creationflags
    )
    raw_data, err = process.communicate()

    if process.returncode != 0:
        raise RuntimeError(f"Errore nella decodifica audio con FFmpeg: {err.decode('utf-8', errors='replace')}")

    audio = np.frombuffer(raw_data, dtype=np.float32)
    if channels > 1:
        audio = audio.reshape(-1, channels).T
    else:
        audio = audio.reshape(1, -1)

    return np.ascontiguousarray(audio, dtype=np.float32), sr


def save_audio(filepath: str, audio: np.ndarray, sr: int, format_hint: Optional[str] = None):
    """
    Salva un ndarray audio (channels, samples) su file (.wav, .mp3, .flac, .ogg, .m4a).
    """
    abs_path = os.path.abspath(filepath)
    os.makedirs(os.path.dirname(abs_path), exist_ok=True)
    ext = (format_hint or os.path.splitext(abs_path)[1]).lower()
    if not ext.startswith("."):
        ext = "." + ext

    if audio.ndim == 1:
        audio_out = audio[:, np.newaxis]
    elif audio.shape[0] <= 8 and audio.shape[0] < audio.shape[1]:
        audio_out = audio.T
    else:
        audio_out = audio

    audio_out = np.clip(audio_out, -1.0, 1.0)

    # Scrittura diretta se WAV, FLAC o OGG
    if ext in {".wav", ".flac", ".ogg"}:
        sf.write(abs_path, audio_out, sr)
        return

    # Per MP3, M4A o altri usiamo FFmpeg
    ffmpeg_exe = get_ffmpeg_exe()
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp_wav:
        tmp_wav_path = tmp_wav.name

    try:
        sf.write(tmp_wav_path, audio_out, sr)
        cmd = [
            ffmpeg_exe,
            "-y",
            "-hide_banner",
            "-loglevel", "error",
            "-i", tmp_wav_path,
        ]

        if ext == ".mp3":
            cmd.extend(["-c:a", "libmp3lame", "-b:a", "256k", "-q:a", "0"])
        elif ext in {".m4a", ".aac"}:
            cmd.extend(["-c:a", "aac", "-b:a", "192k"])
        elif ext == ".opus":
            cmd.extend(["-c:a", "libopus", "-b:a", "128k"])

        cmd.append(abs_path)

        creationflags = 0
        if platform.system() == "Windows":
            creationflags = subprocess.CREATE_NO_WINDOW if hasattr(subprocess, "CREATE_NO_WINDOW") else 0x08000000

        subprocess.run(
            cmd,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            creationflags=creationflags
        )
    finally:
        if os.path.exists(tmp_wav_path):
            try:
                os.remove(tmp_wav_path)
            except Exception:
                pass


def replace_video_audio(video_in_path: str, audio_in_path: str, video_out_path: str):
    """
    Sostituisce la traccia audio in un video copiando il flusso video originale senza ricodifica
    (-c:v copy -c:a aac -b:a 192k -shortest).
    Garantisce zero perdita di qualita video e operazione immediata.
    """
    ffmpeg_exe = get_ffmpeg_exe()
    abs_video_in = os.path.abspath(video_in_path)
    abs_audio_in = os.path.abspath(audio_in_path)
    abs_video_out = os.path.abspath(video_out_path)
    os.makedirs(os.path.dirname(abs_video_out), exist_ok=True)

    cmd = [
        ffmpeg_exe,
        "-y",
        "-hide_banner",
        "-loglevel", "error",
        "-i", abs_video_in,
        "-i", abs_audio_in,
        "-map", "0:v:0",
        "-map", "1:a:0",
        "-c:v", "copy",
        "-c:a", "aac",
        "-b:a", "192k",
        "-shortest",
        abs_video_out
    ]

    creationflags = 0
    if platform.system() == "Windows":
        creationflags = subprocess.CREATE_NO_WINDOW if hasattr(subprocess, "CREATE_NO_WINDOW") else 0x08000000

    result = subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        errors="replace",
        creationflags=creationflags
    )
    if result.returncode != 0:
        raise RuntimeError(f"Errore durante il muxing video con FFmpeg: {result.stderr}")
