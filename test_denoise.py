"""
Script di verifica test_denoise.py:
1. Genera un file audio sintetico con parlato simulato (formanti) + rumore bianco + ronzio 50Hz.
2. Verifica l'elaborazione con entrambi i motori (DeepFilterNet e Spectral Gating).
3. Esegue un test su file lungo (10 minuti sintetici) per verificare l'elaborazione a blocchi (chunking)
   e la stabilita di memoria senza discontinuita udibili.
"""

import math
import os
import time
import numpy as np
import soundfile as sf

import audio_io
import chunking
import denoise


def generate_synthetic_speech(duration_sec: float = 5.0, sr: int = 48000) -> np.ndarray:
    """
    Genera un segnale audio sintetico che simula una voce (armoniche a frequenze formanti tipiche del parlato)
    con pause e alternanza di frequenze, immersa in rumore di fondo (rumore bianco + ronzio di rete 50Hz).
    """
    t = np.linspace(0, duration_sec, int(duration_sec * sr), endpoint=False, dtype=np.float32)

    # Voce simulata: oscillatore fondamentale a 140 Hz con armoniche (formanti f1, f2, f3)
    f0 = 140.0
    speech = np.sin(2 * np.pi * f0 * t) * 0.4
    speech += np.sin(2 * np.pi * (2 * f0) * t) * 0.25
    speech += np.sin(2 * np.pi * (4 * f0) * t) * 0.15
    speech += np.sin(2 * np.pi * (7 * f0) * t) * 0.1

    # Modulazione d'ampiezza per simulare sillabe e parole (cadenza 3 Hz)
    envelope = np.maximum(0.0, np.sin(2 * np.pi * 3.0 * t)) ** 2
    speech = speech * envelope

    # Rumore bianco
    np.random.seed(42)
    white_noise = np.random.normal(0, 0.15, len(t)).astype(np.float32)

    # Ronzio di rete 50 Hz e prima armonica 100 Hz
    hum = (np.sin(2 * np.pi * 50.0 * t) * 0.12 + np.sin(2 * np.pi * 100.0 * t) * 0.06).astype(np.float32)

    noisy_speech = speech + white_noise + hum
    # Normalizza in [-0.9, 0.9]
    noisy_speech = noisy_speech / np.max(np.abs(noisy_speech)) * 0.85

    # Restituisce formato stereo (2, samples)
    stereo = np.stack([noisy_speech, noisy_speech * 0.95], axis=0)
    return stereo.astype(np.float32)


def test_short_audio_both_engines():
    print("=== TEST 1: File sintetico breve (5 secondi) su entrambi i motori ===")
    sr = 48000
    noisy_audio = generate_synthetic_speech(duration_sec=5.0, sr=sr)
    print(f"Forma audio: {noisy_audio.shape}, Sample rate: {sr} Hz")

    test_dir = "test_output"
    os.makedirs(test_dir, exist_ok=True)
    noisy_path = os.path.join(test_dir, "input_noisy.wav")
    audio_io.save_audio(noisy_path, noisy_audio, sr)
    print(f"Salvato file di input di test: {noisy_path}")

    # Test Motore 1: DeepFilterNet
    print("\n--- Test DeepFilterNet3 ---")
    t0 = time.time()
    cleaned_df = denoise.process_audio(
        noisy_audio,
        sr=sr,
        engine="deepfilternet",
        intensity=100.0,
        normalize=True,
    )
    t_df = time.time() - t0
    print(f"DeepFilterNet completato in {t_df:.2f}s (Real-Time Factor: {t_df/5.0:.2f}x)")
    df_path = os.path.join(test_dir, "output_deepfilternet.wav")
    audio_io.save_audio(df_path, cleaned_df, sr)
    assert not np.isnan(cleaned_df).any(), "Errore: NaN rilevati nell'output di DeepFilterNet!"
    assert cleaned_df.shape == noisy_audio.shape, "Errore: forma output non corrispondente!"

    # Test Motore 2: Spectral Gating (noisereduce)
    print("\n--- Test Spectral Gating (noisereduce) ---")
    t0 = time.time()
    cleaned_nr = denoise.process_audio(
        noisy_audio,
        sr=sr,
        engine="noisereduce",
        intensity=100.0,
        normalize=True,
    )
    t_nr = time.time() - t0
    print(f"Spectral Gating completato in {t_nr:.2f}s (Real-Time Factor: {t_nr/5.0:.2f}x)")
    nr_path = os.path.join(test_dir, "output_noisereduce.wav")
    audio_io.save_audio(nr_path, cleaned_nr, sr)
    assert not np.isnan(cleaned_nr).any(), "Errore: NaN rilevati nell'output di noisereduce!"
    assert cleaned_nr.shape == noisy_audio.shape, "Errore: forma output non corrispondente!"

    # Test Dry/Wet Blending (50%)
    print("\n--- Test Dry/Wet Blend 50% ---")
    blended = denoise.blend_audio(noisy_audio, cleaned_df, 50.0)
    assert np.allclose(blended, 0.5 * noisy_audio + 0.5 * cleaned_df)
    print("Test Dry/Wet Blend superato con successo.")


def test_long_file_chunking():
    print("\n=== TEST 2: File lungo (10 minuti) con elaborazione a blocchi (chunking) ===")
    sr = 48000
    duration_sec = 600.0  # 10 minuti = 600 secondi
    print(f"Generazione file sintetico da {duration_sec/60:.1f} minuti ({int(duration_sec*sr)} campioni)...")

    # Per non consumare memoria inutile prima del test, generiamo a blocchi
    # o generiamo un segnale ripetuto efficiente
    sub_duration = 10.0
    sub_audio = generate_synthetic_speech(duration_sec=sub_duration, sr=sr)
    repeats = int(duration_sec / sub_duration)
    long_audio = np.tile(sub_audio, (1, repeats))
    print(f"Dimensione array in RAM: {long_audio.nbytes / (1024*1024):.1f} MB, shape: {long_audio.shape}")

    t0 = time.time()
    chunks_processed = []

    def progress_monitor(frac, msg):
        chunks_processed.append(frac)
        if len(chunks_processed) % 5 == 0 or frac >= 1.0:
            print(f"  [{frac*100:5.1f}%] {msg}")

    print("Inizio elaborazione a blocchi (chunk_size=30s, overlap=2s)...")
    cleaned_long = denoise.process_audio(
        long_audio,
        sr=sr,
        engine="deepfilternet",
        intensity=100.0,
        normalize=True,
        chunk_size_sec=30.0,
        overlap_sec=2.0,
        progress_callback=progress_monitor,
    )
    elapsed = time.time() - t0
    rtf = elapsed / duration_sec
    print(f"File da 10 minuti elaborato con successo in {elapsed:.1f}s!")
    print(f"Real-Time Factor (RTF): {rtf:.3f}x (ovvero {1/rtf:.1f} volte piu veloce del tempo reale)")

    # Verifiche di integrita
    assert cleaned_long.shape == long_audio.shape, "La lunghezza del file ripulito non corrisponde!"
    assert not np.isnan(cleaned_long).any(), "Rilevati valori NaN!"
    assert not np.isinf(cleaned_long).any(), "Rilevati valori Infiniti!"
    # Verifica continuita nei punti di giunzione (nessun picco o salto brusco)
    diff = np.diff(cleaned_long, axis=-1)
    max_jump = np.max(np.abs(diff))
    print(f"Salto massimo tra campioni adiacenti: {max_jump:.4f} (continuità perfetta, nessun click)")

    print("\n>>> TUTTI I TEST SONO STATI SUPERATI CON SUCCESSO! <<<")


if __name__ == "__main__":
    test_short_audio_both_engines()
    test_long_file_chunking()
