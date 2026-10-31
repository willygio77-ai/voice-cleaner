"""
Applicazione Web Locale per la Rimozione del Rumore di Fondo da Registrazioni Vocali.
Interfaccia realizzata con Gradio.
Supporta DeepFilterNet3, Spectral Gating, elaborazione a blocchi per file lunghi,
slider di intensita (dry/wet), normalizzazione e sostituzione audio nei video senza ricodifica.
"""

import os
import shutil
import tempfile
import time
from typing import Optional, Tuple
import gradio as gr
import numpy as np

import audio_io
import denoise


OUTPUT_DIR = os.path.abspath("outputs")
os.makedirs(OUTPUT_DIR, exist_ok=True)


def get_system_badge() -> str:
    """Genera una stringa HTML con lo stato di CPU/GPU e FFmpeg."""
    device_info = denoise.get_device_info()
    ffmpeg_ok, ffmpeg_msg = audio_io.check_ffmpeg_available()
    ffmpeg_status = "Pronto" if ffmpeg_ok else "Non rilevato"
    color_device = "#22c55e" if "GPU" in device_info else "#3b82f6"
    color_ffmpeg = "#22c55e" if ffmpeg_ok else "#ef4444"

    return f"""
    <div style="display: flex; gap: 12px; margin-bottom: 12px; font-size: 0.9em; flex-wrap: wrap;">
        <span style="background: rgba(59, 130, 246, 0.1); border: 1px solid {color_device}; padding: 4px 10px; border-radius: 6px; color: #1e293b; font-weight: 500;">
            ⚙️ Dispositivo: <strong>{device_info}</strong>
        </span>
        <span style="background: rgba(34, 197, 94, 0.1); border: 1px solid {color_ffmpeg}; padding: 4px 10px; border-radius: 6px; color: #1e293b; font-weight: 500;">
            🎬 FFmpeg: <strong>{ffmpeg_status}</strong>
        </span>
    </div>
    """


def process_uploaded_file(
    file_obj,
    engine_choice: str,
    intensity: float,
    normalize: bool,
    output_format: str,
    progress=gr.Progress(track_tqdm=False)
):
    """
    Funzione principale invocata al clic di elaborazione.
    """
    if file_obj is None:
        raise gr.Error("Per favore, carica un file audio o video prima di procedere.")

    input_path = file_obj.name if hasattr(file_obj, "name") else str(file_obj)
    if not os.path.isfile(input_path):
        raise gr.Error("File non valido o non trovato.")

    # Verifica FFmpeg
    ffmpeg_ok, ffmpeg_detail = audio_io.check_ffmpeg_available()
    if not ffmpeg_ok:
        instructions = audio_io.get_os_ffmpeg_instructions()
        raise gr.Error(f"FFmpeg mancante!\n{instructions}")

    is_video = audio_io.is_video_file(input_path)
    base_name = os.path.splitext(os.path.basename(input_path))[0]
    timestamp = int(time.time())

    progress(0.05, desc="Caricamento ed estrazione traccia audio...")
    t_start = time.time()

    try:
        # Carica audio normalizzato
        audio_data, sr = audio_io.load_audio(input_path)
    except Exception as e:
        raise gr.Error(f"Errore durante la lettura del file: {str(e)}")

    total_samples = audio_data.shape[1]
    duration_sec = total_samples / float(sr)
    channels = audio_data.shape[0]

    # Prepara callback di avanzamento per il chunking
    def on_chunk_progress(frac: float, msg: str):
        # Mappa l'avanzamento tra il 10% e il 90%
        mapped_progress = 0.10 + frac * 0.80
        progress(mapped_progress, desc=f"Riduzione rumore: {msg}")

    # Determina il motore
    engine_key = "deepfilternet" if "DeepFilterNet" in engine_choice else "noisereduce"

    progress(0.10, desc=f"Avvio elaborazione con {engine_choice} ({duration_sec:.1f}s)...")

    try:
        cleaned_audio = denoise.process_audio(
            audio=audio_data,
            sr=sr,
            engine=engine_key,
            intensity=float(intensity),
            normalize=normalize,
            chunk_size_sec=30.0,
            overlap_sec=2.0,
            progress_callback=on_chunk_progress,
        )
    except Exception as e:
        raise gr.Error(f"Errore durante il processo di denoising: {str(e)}")

    progress(0.92, desc="Salvataggio ed esportazione dei file...")

    # Determina l'estensione di output richiesta
    orig_ext = os.path.splitext(input_path)[1].lower()
    if output_format == "WAV":
        out_audio_ext = ".wav"
    elif output_format == "MP3":
        out_audio_ext = ".mp3"
    else:  # "Stesso formato dell'originale" o WAV se era un video
        if is_video or orig_ext not in audio_io.AUDIO_EXTENSIONS:
            out_audio_ext = ".wav"
        else:
            out_audio_ext = orig_ext

    cleaned_audio_filename = f"{base_name}_ripulito_{timestamp}{out_audio_ext}"
    cleaned_audio_path = os.path.join(OUTPUT_DIR, cleaned_audio_filename)

    audio_io.save_audio(cleaned_audio_path, cleaned_audio, sr, format_hint=out_audio_ext)

    # Se input video, crea video con audio sostituito (muxing lossless video stream)
    cleaned_video_path = None
    if is_video:
        progress(0.96, desc="Sostituzione traccia audio nel video (senza ricodifica)...")
        cleaned_video_filename = f"{base_name}_ripulito_{timestamp}{orig_ext}"
        cleaned_video_path = os.path.join(OUTPUT_DIR, cleaned_video_filename)
        try:
            audio_io.replace_video_audio(
                video_in_path=input_path,
                audio_in_path=cleaned_audio_path,
                video_out_path=cleaned_video_path,
            )
        except Exception as e:
            gr.Warning(f"Attenzione: creazione del video finale non riuscita: {str(e)}. L'audio ripulito e comunque disponibile.")
            cleaned_video_path = None

    elapsed_time = time.time() - t_start
    rtf = elapsed_time / duration_sec if duration_sec > 0 else 0

    progress(1.0, desc="Completato!")

    # Prepara riassunto statistiche
    summary_md = f"""
    ### ✅ Elaborazione Completata con Successo
    - **Durata audio**: `{duration_sec:.1f} secondi` ({duration_sec/60:.2f} min)
    - **Canali**: `{'Stereo' if channels == 2 else 'Mono'}` | **Sample Rate**: `{sr} Hz`
    - **Tempo impiegato**: `{elapsed_time:.2f}s` (Velocità: **{1/rtf:.1f}x** tempo reale, RTF: `{rtf:.3f}`)
    - **Motore utilizzato**: `{engine_choice}`
    - **Intensità riduzione (Dry/Wet)**: `{intensity}%`
    - **Normalizzazione volume**: `{'Abilitata (-1 dBFS)' if normalize else 'Disabilitata'}`
    """

    # Gradio audio components supportano (sample_rate, numpy_array_transposed) oppure il path al file
    # Il path al file garantisce perfetta riproduzione da browser per qualsiasi codec
    return (
        input_path if not is_video else None,  # audio originale
        cleaned_audio_path,                    # audio ripulito
        cleaned_audio_path,                    # download audio
        gr.update(visible=is_video, value=input_path if is_video else None),        # video originale
        gr.update(visible=is_video, value=cleaned_video_path if is_video else None), # video ripulito
        gr.update(visible=is_video, value=cleaned_video_path if is_video else None), # download video
        summary_md                             # sommario informativo
    )


def create_ui():
    """Costruisce l'interfaccia utente con Gradio Blocks."""
    with gr.Blocks(title="Voice Cleaner - Rimozione Rumore Vocale") as demo:
        gr.Markdown(
            """
            # 🎙️ Voice Cleaner — Pulizia Vocale Intelligente
            Rimuovi rumori di fondo (fruscii, ventole, traffico, ronzii) da registrazioni di parlato 
            (interviste, riunioni, podcast e video) preservando il timbro naturale della voce.
            **100% in locale: nessun dato viene inviato all'esterno.**
            """
        )

        gr.HTML(get_system_badge())

        with gr.Row():
            with gr.Column(scale=1):
                gr.Markdown("### 1. Carica File Audio o Video")
                file_input = gr.File(
                    label="Seleziona o trascina qui il file",
                    file_types=[
                        "audio",
                        "video",
                        ".wav", ".mp3", ".m4a", ".aac", ".flac", ".ogg", ".opus",
                        ".mp4", ".mov", ".mkv", ".webm", ".avi"
                    ],
                )

                gr.Markdown("### 2. Impostazioni di Elaborazione")
                available_engines = denoise.get_available_engines()
                default_engine = available_engines[0] if available_engines else "DeepFilterNet (Ottimizzato per la voce)"

                engine_selector = gr.Dropdown(
                    label="Motore di riduzione rumore",
                    choices=available_engines,
                    value=default_engine,
                    info="DeepFilterNet rimuove il rumore preservando la voce; Spectral Gating agisce tramite noise gate spettrale."
                )

                intensity_slider = gr.Slider(
                    label="Intensità riduzione (Dry / Wet)",
                    minimum=0,
                    maximum=100,
                    value=100,
                    step=1,
                    info="100% = massima pulizia; valori intermedi (es. 80-90%) preservano l'ambiente per un suono più naturale."
                )

                with gr.Row():
                    normalize_check = gr.Checkbox(
                        label="Normalizza volume finale",
                        value=True,
                        info="Livella il volume a -1 dBFS prevenendo clipping e cali di volume."
                    )
                    format_selector = gr.Dropdown(
                        label="Formato audio output",
                        choices=["WAV", "MP3", "Stesso dell'originale"],
                        value="WAV",
                        info="WAV e consigliato per la massima qualita senza compressione."
                    )

                btn_process = gr.Button("✨ Avvia Rimozione Rumore", variant="primary", size="lg")

            with gr.Column(scale=1):
                gr.Markdown("### 3. Risultato e Confronto Prima / Dopo")

                summary_output = gr.Markdown("Carica un file e premi **Avvia Rimozione Rumore** per iniziare.")

                with gr.Tabs():
                    with gr.TabItem("🔊 Confronto Audio"):
                        with gr.Row():
                            orig_audio_player = gr.Audio(label="Audio Originale", interactive=False)
                            cleaned_audio_player = gr.Audio(label="Audio Ripulito", interactive=False)
                        download_audio_btn = gr.File(label="⬇️ Scarica File Audio Ripulito", interactive=False)

                    with gr.TabItem("🎬 Video (se applicabile)"):
                        with gr.Row():
                            orig_video_player = gr.Video(label="Video Originale", interactive=False, visible=False)
                            cleaned_video_player = gr.Video(label="Video con Audio Ripulito", interactive=False, visible=False)
                        download_video_btn = gr.File(label="⬇️ Scarica Video con Audio Sostituito", interactive=False, visible=False)

        # Evento di click
        btn_process.click(
            fn=process_uploaded_file,
            inputs=[
                file_input,
                engine_selector,
                intensity_slider,
                normalize_check,
                format_selector,
            ],
            outputs=[
                orig_audio_player,
                cleaned_audio_player,
                download_audio_btn,
                orig_video_player,
                cleaned_video_player,
                download_video_btn,
                summary_output,
            ]
        )

        gr.Markdown(
            """
            ---
            <div style="text-align: center; color: #64748b; font-size: 0.85em;">
                Elaborazione sicura e locale con <strong>DeepFilterNet 3</strong> e <strong>noisereduce</strong> | Powered by Gradio & FFmpeg
            </div>
            """
        )

    return demo


if __name__ == "__main__":
    app = create_ui()
    theme = gr.themes.Soft(primary_hue="indigo", secondary_hue="slate")
    # Avvio locale su 127.0.0.1 porta 7860
    app.queue().launch(server_name="127.0.0.1", server_port=7860, inbrowser=False, theme=theme)
