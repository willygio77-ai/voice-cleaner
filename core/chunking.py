"""
Modulo core/chunking.py: Elaborazione a blocchi con dissolvenza incrociata (Overlap-Add)
per file audio lunghi (fino a 1-2 ore) per evitare la saturazione della RAM
e garantire l'assenza di discontinuità o click udibili tra i blocchi.
Include supporto per cancellazione immediata e sicura dell'elaborazione.
"""

from typing import Callable, Optional
import numpy as np


def process_in_chunks(
    audio: np.ndarray,
    sr: int,
    process_fn: Callable[[np.ndarray, int], np.ndarray],
    chunk_size_sec: float = 30.0,
    overlap_sec: float = 2.0,
    progress_callback: Optional[Callable[[float, str], None]] = None,
    cancel_check: Optional[Callable[[], bool]] = None,
) -> np.ndarray:
    """
    Divide l'audio (channels, samples) in blocchi sovrapposti, li elabora con process_fn
    e li ricombina con una finestra di crossfade (Hann / equal-gain).

    Parametri:
        audio: ndarray float32 (channels, samples)
        sr: frequenza di campionamento (Hz)
        process_fn: funzione f(chunk_audio, sr) -> cleaned_chunk_audio
        chunk_size_sec: dimensione di ciascun blocco in secondi (default 30s)
        overlap_sec: intervallo di sovrapposizione in secondi (default 2s)
        progress_callback: callback opzionale (frazione 0..1, messaggio)
        cancel_check: callback opzionale che restituisce True se l'utente ha chiesto l'annullamento
    """
    if cancel_check and cancel_check():
        raise InterruptedError("Operazione annullata prima dell'avvio.")

    total_samples = audio.shape[1]
    channels = audio.shape[0]

    chunk_samples = int(chunk_size_sec * sr)
    overlap_samples = int(overlap_sec * sr)
    hop_samples = chunk_samples - overlap_samples

    # Se l'audio e breve, elabora direttamente in una sola passata
    if total_samples <= chunk_samples:
        if progress_callback:
            progress_callback(0.2, "Elaborazione audio...")
        if cancel_check and cancel_check():
            raise InterruptedError("Operazione annullata.")
        result = process_fn(audio, sr)
        if cancel_check and cancel_check():
            raise InterruptedError("Operazione annullata.")
        if progress_callback:
            progress_callback(1.0, "Completato.")
        return result

    starts = list(range(0, total_samples, hop_samples))
    total_chunks = len(starts)

    output = np.zeros((channels, total_samples), dtype=np.float32)

    fade_t = np.linspace(0, np.pi, overlap_samples, endpoint=False, dtype=np.float32)
    fade_in = 0.5 * (1.0 - np.cos(fade_t))
    fade_out = 1.0 - fade_in

    fade_in = np.tile(fade_in, (channels, 1))
    fade_out = np.tile(fade_out, (channels, 1))

    for idx, start_sample in enumerate(starts):
        # Controllo cancellazione prima di ogni blocco
        if cancel_check and cancel_check():
            raise InterruptedError("Operazione annullata dall'utente.")

        end_sample = min(start_sample + chunk_samples, total_samples)
        chunk = audio[:, start_sample:end_sample]

        min_samples = int(0.5 * sr)
        orig_len = chunk.shape[1]
        if orig_len < min_samples:
            pad_len = min_samples - orig_len
            chunk = np.pad(chunk, ((0, 0), (0, pad_len)), mode="reflect")

        if progress_callback:
            fraction = (idx + 1) / total_chunks
            progress_callback(fraction, f"Elaborazione blocco {idx + 1}/{total_chunks}...")

        processed_chunk = process_fn(chunk, sr)

        if cancel_check and cancel_check():
            raise InterruptedError("Operazione annullata dall'utente.")

        if orig_len < min_samples:
            processed_chunk = processed_chunk[:, :orig_len]

        chunk_len = processed_chunk.shape[1]

        if idx == 0:
            output[:, :chunk_len] = processed_chunk
        else:
            actual_overlap = min(overlap_samples, chunk_len)
            w_out = fade_out[:, :actual_overlap]
            w_in = fade_in[:, :actual_overlap]

            output[:, start_sample:start_sample + actual_overlap] = (
                output[:, start_sample:start_sample + actual_overlap] * w_out
                + processed_chunk[:, :actual_overlap] * w_in
            )

            if chunk_len > actual_overlap:
                output[:, start_sample + actual_overlap:start_sample + chunk_len] = (
                    processed_chunk[:, actual_overlap:]
                )

    if progress_callback:
        progress_callback(1.0, "Elaborazione completata.")

    return output
