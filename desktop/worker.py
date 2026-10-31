"""
Modulo desktop/worker.py: QThread worker per l'elaborazione asincrona
della coda di file audio/video con supporto completo all'annullamento (cancel).
"""

import os
import time
from typing import List, Optional
from PySide6.QtCore import QThread, Signal

from core import audio_io, denoise


class DenoiseTask:
    """Descrive un singolo task di denoising all'interno della coda."""
    def __init__(
        self,
        input_path: str,
        engine: str,
        intensity: float,
        normalize: bool,
        output_format: str,
        output_dir: str
    ):
        self.input_path = input_path
        self.engine = engine
        self.intensity = intensity
        self.normalize = normalize
        self.output_format = output_format
        self.output_dir = output_dir
        self.out_audio_path: Optional[str] = None
        self.out_video_path: Optional[str] = None
        self.error: Optional[str] = None
        self.duration_sec: float = 0.0


class DenoiseWorker(QThread):
    """Worker in background per l'elaborazione batch senza bloccare la GUI."""
    
    file_started = Signal(int, str)                # task_index, input_path
    file_progress = Signal(int, float, str)        # task_index, fraction (0..1), message
    file_completed = Signal(int, str, str, dict)   # task_index, out_audio, out_video, stats
    file_error = Signal(int, str)                  # task_index, error_message
    cancelled = Signal()
    all_completed = Signal()

    def __init__(self, tasks: List[DenoiseTask]):
        super().__init__()
        self.tasks = tasks
        self._is_cancelled = False

    def cancel(self):
        """Richiede l'annullamento dell'elaborazione in corso."""
        self._is_cancelled = True

    def is_cancelled(self) -> bool:
        """Restituisce True se e stato richiesto l'annullamento."""
        return self._is_cancelled

    def run(self):
        """Esecuzione principale nel thread separato."""
        for idx, task in enumerate(self.tasks):
            if self._is_cancelled:
                self.cancelled.emit()
                return

            self.file_started.emit(idx, task.input_path)
            t_start = time.time()

            try:
                # 1. Carica audio
                self.file_progress.emit(idx, 0.05, "Caricamento audio ed estrazione...")
                if self._is_cancelled:
                    self.cancelled.emit()
                    return

                audio_data, sr = audio_io.load_audio(task.input_path)
                total_samples = audio_data.shape[1]
                duration_sec = total_samples / float(sr)
                task.duration_sec = duration_sec

                # Callback di avanzamento agganciato al chunking
                def on_chunk_progress(frac: float, msg: str):
                    if not self._is_cancelled:
                        mapped = 0.10 + frac * 0.80
                        self.file_progress.emit(idx, mapped, msg)

                # 2. Elaborazione denoising con cancel check
                self.file_progress.emit(idx, 0.10, "Elaborazione rumore...")
                cleaned_audio = denoise.process_audio(
                    audio=audio_data,
                    sr=sr,
                    engine=task.engine,
                    intensity=task.intensity,
                    normalize=task.normalize,
                    chunk_size_sec=30.0,
                    overlap_sec=2.0,
                    progress_callback=on_chunk_progress,
                    cancel_check=self.is_cancelled,
                )

                if self._is_cancelled:
                    self.cancelled.emit()
                    return

                # 3. Salvataggio su disco
                self.file_progress.emit(idx, 0.92, "Esportazione file audio...")
                os.makedirs(task.output_dir, exist_ok=True)
                base_name = os.path.splitext(os.path.basename(task.input_path))[0]
                timestamp = int(time.time())
                is_video = audio_io.is_video_file(task.input_path)
                orig_ext = os.path.splitext(task.input_path)[1].lower()

                if task.output_format.upper() == "WAV":
                    out_ext = ".wav"
                elif task.output_format.upper() == "MP3":
                    out_ext = ".mp3"
                else:
                    out_ext = ".wav" if is_video else orig_ext

                cleaned_audio_name = f"{base_name}_ripulito_{timestamp}{out_ext}"
                out_audio_path = os.path.join(task.output_dir, cleaned_audio_name)
                audio_io.save_audio(out_audio_path, cleaned_audio, sr, format_hint=out_ext)
                task.out_audio_path = out_audio_path

                # 4. Muxing video se input era video
                out_video_path = None
                if is_video:
                    self.file_progress.emit(idx, 0.96, "Muxing video lossless...")
                    cleaned_video_name = f"{base_name}_ripulito_{timestamp}{orig_ext}"
                    out_video_path = os.path.join(task.output_dir, cleaned_video_name)
                    try:
                        audio_io.replace_video_audio(
                            video_in_path=task.input_path,
                            audio_in_path=out_audio_path,
                            video_out_path=out_video_path,
                        )
                        task.out_video_path = out_video_path
                    except Exception as e:
                        out_video_path = None

                elapsed = time.time() - t_start
                rtf = elapsed / duration_sec if duration_sec > 0 else 0
                stats = {
                    "duration_sec": duration_sec,
                    "elapsed_sec": elapsed,
                    "rtf": rtf,
                    "channels": audio_data.shape[0],
                    "sr": sr
                }

                self.file_progress.emit(idx, 1.0, "Completato.")
                self.file_completed.emit(idx, out_audio_path, out_video_path or "", stats)

            except InterruptedError:
                self.cancelled.emit()
                return
            except Exception as e:
                task.error = str(e)
                self.file_error.emit(idx, str(e))

        if not self._is_cancelled:
            self.all_completed.emit()
