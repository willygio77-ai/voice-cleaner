"""
Modulo core/denoise.py: Motori di denoising vocale.
Include DeepFilterNet (motore principale per parlato) e Spectral Gating (noisereduce),
miscelazione dry/wet per preservare la naturalezza della voce e normalizzazione del volume.
Supporta modelli offline inclusi nel bundle PyInstaller e cancellazione sicura.
"""

import sys
import types
from pathlib import Path
from typing import Callable, Optional, Tuple
import numpy as np

# Torchaudio backend compatibility shim
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

import torch
from core.config import get_bundled_model_dir

# Cache globale del modello DeepFilterNet
_DF_MODEL = None
_DF_STATE = None
_DF_AVAILABLE = False
_DF_ERROR = None

try:
    from df.enhance import enhance, init_df
    _DF_AVAILABLE = True
except Exception as e:
    _DF_AVAILABLE = False
    _DF_ERROR = str(e)

try:
    import noisereduce as nr
    _NOISEREDUCE_AVAILABLE = True
except Exception as e:
    _NOISEREDUCE_AVAILABLE = False


def get_available_engines() -> list:
    """Restituisce l'elenco dei motori disponibili nel sistema."""
    engines = []
    if _DF_AVAILABLE:
        engines.append("DeepFilterNet (Ottimizzato per la voce)")
    if _NOISEREDUCE_AVAILABLE:
        engines.append("Spectral Gating (noisereduce)")
    return engines


def get_device_info() -> str:
    """Restituisce le informazioni sul dispositivo di calcolo in uso (GPU / CPU)."""
    if torch.cuda.is_available():
        gpu_name = torch.cuda.get_device_name(0)
        return f"GPU ({gpu_name})"
    return "CPU (Elaborazione multi-thread ad alte prestazioni)"


def load_df_model():
    """Carica e memorizza nella cache il modello DeepFilterNet3."""
    global _DF_MODEL, _DF_STATE
    if not _DF_AVAILABLE:
        raise RuntimeError(f"DeepFilterNet non disponibile: {_DF_ERROR}")

    if _DF_MODEL is None or _DF_STATE is None:
        # Verifica se esiste la cartella del modello inclusa nel bundle
        model_dir = get_bundled_model_dir("DeepFilterNet3")
        model_dir_str = str(model_dir.resolve()) if model_dir.exists() else None
        
        # Inizializza DeepFilterNet con la cartella locale
        model, df_state, _ = init_df(model_base_dir=model_dir_str)
        _DF_MODEL = model
        _DF_STATE = df_state

    return _DF_MODEL, _DF_STATE


def denoise_with_deepfilternet(audio: np.ndarray, sr: int) -> np.ndarray:
    """
    Ripulisce l'audio con DeepFilterNet3.
    Parametri:
        audio: ndarray float32 (channels, samples)
        sr: frequenza di campionamento
    """
    model, df_state = load_df_model()
    target_sr = df_state.sr()

    channels, total_samples = audio.shape

    needs_resample = (sr != target_sr)
    if needs_resample:
        from scipy.signal import resample_poly
        from math import gcd
        g = gcd(sr, target_sr)
        up = target_sr // g
        down = sr // g
        audio_resampled = resample_poly(audio, up, down, axis=-1).astype(np.float32)
    else:
        audio_resampled = audio

    cleaned_channels = []
    for ch in range(channels):
        ch_data = audio_resampled[ch:ch+1, :]
        ch_tensor = torch.from_numpy(ch_data)
        with torch.no_grad():
            enhanced_tensor = enhance(model, df_state, ch_tensor)
        enhanced_np = enhanced_tensor.cpu().numpy()
        cleaned_channels.append(enhanced_np)

    cleaned = np.concatenate(cleaned_channels, axis=0)

    if needs_resample:
        g = gcd(target_sr, sr)
        up = sr // g
        down = target_sr // g
        cleaned = resample_poly(cleaned, up, down, axis=-1).astype(np.float32)

        if cleaned.shape[1] > total_samples:
            cleaned = cleaned[:, :total_samples]
        elif cleaned.shape[1] < total_samples:
            pad = total_samples - cleaned.shape[1]
            cleaned = np.pad(cleaned, ((0, 0), (0, pad)), mode="edge")

    return np.ascontiguousarray(cleaned, dtype=np.float32)


def denoise_with_noisereduce(audio: np.ndarray, sr: int) -> np.ndarray:
    """
    Ripulisce l'audio con noisereduce (Spectral Gating non-stazionario).
    Supporta mono e stereo (channels, samples).
    """
    if not _NOISEREDUCE_AVAILABLE:
        raise RuntimeError("La libreria noisereduce non e installata.")

    channels = audio.shape[0]
    cleaned_channels = []
    for ch in range(channels):
        ch_audio = audio[ch, :]
        reduced = nr.reduce_noise(
            y=ch_audio,
            sr=sr,
            stationary=False,
            prop_decrease=1.0,
            n_fft=2048,
            hop_length=512,
        )
        cleaned_channels.append(reduced[np.newaxis, :])

    cleaned = np.concatenate(cleaned_channels, axis=0)
    return np.ascontiguousarray(cleaned, dtype=np.float32)


def blend_audio(original: np.ndarray, cleaned: np.ndarray, intensity_percent: float) -> np.ndarray:
    """
    Mescola audio originale e ripulito in base all'intensita specificata (0-100%).
    """
    alpha = max(0.0, min(100.0, float(intensity_percent))) / 100.0
    return alpha * cleaned + (1.0 - alpha) * original


def normalize_volume(audio: np.ndarray, target_peak_db: float = -1.0) -> np.ndarray:
    """
    Normalizza l'audio di picco al valore target_peak_db (default -1.0 dBFS).
    """
    peak = np.max(np.abs(audio))
    if peak <= 1e-6:
        return audio

    target_linear = 10.0 ** (target_peak_db / 20.0)
    gain = target_linear / peak
    normalized = audio * gain
    return np.clip(normalized, -1.0, 1.0)


def process_audio(
    audio: np.ndarray,
    sr: int,
    engine: str = "deepfilternet",
    intensity: float = 100.0,
    normalize: bool = True,
    chunk_size_sec: float = 30.0,
    overlap_sec: float = 2.0,
    progress_callback: Optional[Callable[[float, str], None]] = None,
    cancel_check: Optional[Callable[[], bool]] = None,
) -> np.ndarray:
    """
    Pipeline completa di denoising:
    1. Selezione motore (DeepFilterNet o Spectral Gating).
    2. Elaborazione a blocchi con crossfade e supporto cancellazione.
    3. Dry/Wet blend.
    4. Normalizzazione volume.
    """
    from core.chunking import process_in_chunks

    engine_lower = engine.lower()
    if "deepfilter" in engine_lower:
        if not _DF_AVAILABLE:
            raise RuntimeError(f"DeepFilterNet non disponibile: {_DF_ERROR}. Seleziona Spectral Gating.")
        core_denoise = denoise_with_deepfilternet
    else:
        if not _NOISEREDUCE_AVAILABLE:
            raise RuntimeError("noisereduce non disponibile.")
        core_denoise = denoise_with_noisereduce

    cleaned = process_in_chunks(
        audio=audio,
        sr=sr,
        process_fn=core_denoise,
        chunk_size_sec=chunk_size_sec,
        overlap_sec=overlap_sec,
        progress_callback=progress_callback,
        cancel_check=cancel_check,
    )

    if cancel_check and cancel_check():
        raise InterruptedError("Operazione annullata dall'utente.")

    if intensity < 100.0:
        cleaned = blend_audio(audio, cleaned, intensity)

    if normalize:
        cleaned = normalize_volume(cleaned)

    return cleaned
