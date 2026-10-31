"""
Modulo desktop/main_window.py: Finestra principale nativa PySide6 (Qt) per Windows 10/11.
Integra drag & drop, coda batch, controlli motore/intensita, player A/B,
gestione thread asincrono, salvataggio impostazioni di sessione e tema chiaro/scuro.
"""

import os
import shutil
import sys
from pathlib import Path
from typing import Optional

from PySide6.QtCore import QSettings, Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSlider,
    QSplitter,
    QStatusBar,
    QVBoxLayout,
    QWidget,
)

from core import audio_io, config, denoise
from desktop.player import ABAudioPlayer
from desktop.theme import get_stylesheet, is_windows_dark_mode
from desktop.widgets import DropArea, FileQueueTable
from desktop.worker import DenoiseTask, DenoiseWorker


class MainWindow(QMainWindow):
    """Finestra principale dell'applicazione desktop Voice Cleaner."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Voice Cleaner — Rimozione Rumore Vocale")
        self.resize(1150, 780)
        self.setMinimumSize(850, 600)

        self.settings = QSettings("VoiceCleaner", "VoiceCleanerDesktop")
        self.worker: Optional[DenoiseWorker] = None

        self._set_app_icon()
        self._setup_ui()
        self._load_settings()
        self._check_environment()

    def _set_app_icon(self):
        icon_path = config.get_asset_path("icon.ico")
        if not icon_path.exists():
            icon_path = config.get_asset_path("icon.png")
        if icon_path.exists():
            self.setWindowIcon(QIcon(str(icon_path)))

    def _setup_ui(self):
        # Imposta tema scuro o chiaro coerente con Windows
        dark_mode = is_windows_dark_mode()
        self.setStyleSheet(get_stylesheet(dark_mode))

        central_widget = QWidget(self)
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(16, 14, 16, 10)
        main_layout.setSpacing(12)

        # Splitter orizzontale principale
        splitter = QSplitter(Qt.Horizontal)

        # === PANNELLO SINISTRO: Drop Area e Coda Batch ===
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(10)

        # 1. Area Drag & Drop
        self.drop_area = DropArea(self)
        self.drop_area.files_added.connect(self._on_files_added)
        left_layout.addWidget(self.drop_area)

        # 2. Coda dei file
        queue_header_layout = QHBoxLayout()
        lbl_queue = QLabel("📋 Coda di Elaborazione")
        lbl_queue.setStyleSheet("font-weight: 600; font-size: 14px;")
        queue_header_layout.addWidget(lbl_queue)
        queue_header_layout.addStretch()

        self.btn_remove_file = QPushButton("➖ Rimuovi")
        self.btn_remove_file.clicked.connect(self._on_remove_selected_file)
        self.btn_clear_queue = QPushButton("🗑️ Svuota Coda")
        self.btn_clear_queue.clicked.connect(self._on_clear_queue)

        queue_header_layout.addWidget(self.btn_remove_file)
        queue_header_layout.addWidget(self.btn_clear_queue)
        left_layout.addLayout(queue_header_layout)

        self.queue_table = FileQueueTable(self)
        self.queue_table.file_selected_for_playback.connect(self._on_file_selected_for_playback)
        left_layout.addWidget(self.queue_table)

        splitter.addWidget(left_widget)

        # === PANNELLO DESTRO: Impostazioni, Azioni e Player A/B ===
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(12)

        # Gruppo Impostazioni
        group_settings = QGroupBox("⚙️ Impostazioni di Elaborazione")
        settings_layout = QVBoxLayout(group_settings)
        settings_layout.setSpacing(10)

        # Motore
        lbl_engine = QLabel("Motore di riduzione:")
        self.combo_engine = QComboBox()
        available = denoise.get_available_engines()
        self.combo_engine.addItems(available)
        settings_layout.addWidget(lbl_engine)
        settings_layout.addWidget(self.combo_engine)

        # Slider Intensita
        intensity_header = QHBoxLayout()
        lbl_intensity = QLabel("Intensità riduzione (Dry/Wet):")
        self.lbl_intensity_val = QLabel("100%")
        self.lbl_intensity_val.setStyleSheet("font-weight: 600; color: #3b82f6;")
        intensity_header.addWidget(lbl_intensity)
        intensity_header.addStretch()
        intensity_header.addWidget(self.lbl_intensity_val)
        settings_layout.addLayout(intensity_header)

        self.slider_intensity = QSlider(Qt.Horizontal)
        self.slider_intensity.setRange(0, 100)
        self.slider_intensity.setValue(100)
        self.slider_intensity.valueChanged.connect(lambda v: self.lbl_intensity_val.setText(f"{v}%"))
        settings_layout.addWidget(self.slider_intensity)

        # Checkbox Normalizzazione
        self.chk_normalize = QCheckBox("Normalizza volume finale (-1 dBFS)")
        self.chk_normalize.setChecked(True)
        settings_layout.addWidget(self.chk_normalize)

        # Formato di esportazione
        lbl_format = QLabel("Formato audio di output:")
        self.combo_format = QComboBox()
        self.combo_format.addItems(["WAV (Massima qualità)", "MP3 (Compresso)", "Stesso dell'originale"])
        settings_layout.addWidget(lbl_format)
        settings_layout.addWidget(self.combo_format)

        # Cartella di output
        lbl_out_dir = QLabel("Cartella di salvataggio:")
        settings_layout.addWidget(lbl_out_dir)

        out_dir_row = QHBoxLayout()
        self.txt_out_dir = QLineEdit()
        default_out = str(config.get_base_dir() / "outputs")
        self.txt_out_dir.setText(default_out)
        self.btn_browse_out = QPushButton("Sfoglia...")
        self.btn_browse_out.clicked.connect(self._browse_output_dir)
        self.btn_open_out = QPushButton("📂 Apri")
        self.btn_open_out.clicked.connect(self._open_output_dir)

        out_dir_row.addWidget(self.txt_out_dir)
        out_dir_row.addWidget(self.btn_browse_out)
        out_dir_row.addWidget(self.btn_open_out)
        settings_layout.addLayout(out_dir_row)

        right_layout.addWidget(group_settings)

        # Gruppo Azioni
        group_actions = QGroupBox("🚀 Elaborazione")
        actions_layout = QVBoxLayout(group_actions)
        actions_layout.setSpacing(10)

        btn_row = QHBoxLayout()
        self.btn_start = QPushButton("✨ Avvia Elaborazione")
        self.btn_start.setObjectName("primaryBtn")
        self.btn_start.clicked.connect(self._start_processing)

        self.btn_cancel = QPushButton("🛑 Annulla")
        self.btn_cancel.setObjectName("cancelBtn")
        self.btn_cancel.setEnabled(False)
        self.btn_cancel.clicked.connect(self._cancel_processing)

        btn_row.addWidget(self.btn_start)
        btn_row.addWidget(self.btn_cancel)
        actions_layout.addLayout(btn_row)

        self.overall_progress = QProgressBar()
        self.overall_progress.setRange(0, 100)
        self.overall_progress.setValue(0)
        self.overall_progress.setTextVisible(True)
        actions_layout.addWidget(self.overall_progress)

        self.lbl_task_status = QLabel("Pronto. Aggiungi file per iniziare.")
        self.lbl_task_status.setStyleSheet("color: #64748b; font-size: 12px;")
        actions_layout.addWidget(self.lbl_task_status)

        right_layout.addWidget(group_actions)

        # Gruppo Player A/B
        group_player = QGroupBox("🎧 Lettore di Confronto A/B (Istantaneo)")
        player_layout = QVBoxLayout(group_player)
        self.ab_player = ABAudioPlayer(self)
        player_layout.addWidget(self.ab_player)

        # Pulsante Salva con nome per file attivo
        save_as_row = QHBoxLayout()
        self.btn_save_as = QPushButton("💾 Salva risultato con nome...")
        self.btn_save_as.setEnabled(False)
        self.btn_save_as.clicked.connect(self._on_save_as)
        save_as_row.addStretch()
        save_as_row.addWidget(self.btn_save_as)
        player_layout.addLayout(save_as_row)

        right_layout.addWidget(group_player)
        right_layout.addStretch()

        splitter.addWidget(right_widget)
        splitter.setSizes([600, 480])
        main_layout.addWidget(splitter)

        # === STATUS BAR ===
        self.statusBar = QStatusBar()
        self.setStatusBar(self.statusBar)
        self._setup_status_bar()

    def _setup_status_bar(self):
        device = denoise.get_device_info()
        ffmpeg_ok, _ = audio_io.check_ffmpeg_available()

        color_dev = "#22c55e" if "GPU" in device else "#3b82f6"
        color_ff = "#22c55e" if ffmpeg_ok else "#ef4444"
        ff_txt = "FFmpeg: Pronto" if ffmpeg_ok else "FFmpeg: Mancante"

        self.lbl_status_device = QLabel(f" ⚙️ {device} ")
        self.lbl_status_device.setStyleSheet(f"color: {color_dev}; font-weight: 500;")

        self.lbl_status_ffmpeg = QLabel(f" 🎬 {ff_txt} ")
        self.lbl_status_ffmpeg.setStyleSheet(f"color: {color_ff}; font-weight: 500;")

        self.statusBar.addWidget(self.lbl_status_device)
        self.statusBar.addWidget(self.lbl_status_ffmpeg)
        self.statusBar.showMessage("Voice Cleaner Desktop pronto.", 5000)

    def _check_environment(self):
        ffmpeg_ok, msg = audio_io.check_ffmpeg_available()
        if not ffmpeg_ok:
            QMessageBox.critical(
                self,
                "FFmpeg non trovato",
                f"{msg}\n\nL'elaborazione di alcuni formati audio e video potrebbe non funzionare.",
                QMessageBox.Ok
            )

    def _on_files_added(self, paths: list):
        self.queue_table.add_files(paths)
        count = self.queue_table.rowCount()
        self.lbl_task_status.setText(f"{count} file presenti nella coda.")

    def _on_remove_selected_file(self):
        self.queue_table.remove_selected()
        count = self.queue_table.rowCount()
        self.lbl_task_status.setText(f"{count} file presenti nella coda.")

    def _on_clear_queue(self):
        if self.worker and self.worker.isRunning():
            QMessageBox.warning(self, "Attenzione", "Impossibile svuotare la coda durante l'elaborazione.")
            return
        self.queue_table.clear_queue()
        self.ab_player.set_audio_files(None, None)
        self.btn_save_as.setEnabled(False)
        self.lbl_task_status.setText("Coda svuotata.")

    def _on_file_selected_for_playback(self, original_path: str, cleaned_path: str):
        self.ab_player.set_audio_files(original_path, cleaned_path if cleaned_path else None)
        self.btn_save_as.setEnabled(bool(cleaned_path and os.path.isfile(cleaned_path)))

    def _browse_output_dir(self):
        folder = QFileDialog.getExistingDirectory(self, "Seleziona cartella di salvataggio", self.txt_out_dir.text())
        if folder:
            self.txt_out_dir.setText(folder)

    def _open_output_dir(self):
        folder = self.txt_out_dir.text().strip()
        if not os.path.exists(folder):
            os.makedirs(folder, exist_ok=True)
        if sys.platform == "win32":
            os.startfile(folder)
        else:
            import subprocess
            subprocess.run(["xdg-open", folder])

    def _on_save_as(self):
        """Salva con nome il file ripulito attualmente selezionato."""
        if not self.ab_player.cleaned_path or not os.path.isfile(self.ab_player.cleaned_path):
            return

        src_path = self.ab_player.cleaned_path
        orig_name = os.path.basename(src_path)
        ext = os.path.splitext(orig_name)[1].lower()

        dest_path, _ = QFileDialog.getSaveFileName(
            self,
            "Salva file ripulito con nome",
            orig_name,
            f"File (*{ext});;Tutti i file (*.*)"
        )
        if dest_path:
            try:
                shutil.copy2(src_path, dest_path)
                QMessageBox.information(self, "Salvataggio completato", f"File salvato con successo in:\n{dest_path}")
            except Exception as e:
                QMessageBox.critical(self, "Errore salvataggio", f"Impossibile salvare il file:\n{str(e)}")

    def _start_processing(self):
        if self.worker and self.worker.isRunning():
            return

        count = self.queue_table.rowCount()
        if count == 0:
            QMessageBox.information(self, "Coda vuota", "Trascina o apri almeno un file prima di avviare l'elaborazione.")
            return

        out_dir = self.txt_out_dir.text().strip()
        if not out_dir:
            QMessageBox.warning(self, "Cartella mancante", "Seleziona una cartella di output valida.")
            return

        # Verifica spazio su disco
        try:
            os.makedirs(out_dir, exist_ok=True)
            usage = shutil.disk_usage(out_dir)
            if usage.free < 200 * 1024 * 1024:  # meno di 200MB
                QMessageBox.critical(
                    self,
                    "Spazio disco insufficiente",
                    "Lo spazio libero nell'unità di destinazione è inferiore a 200 MB. Libera spazio prima di procedere."
                )
                return
        except Exception as e:
            QMessageBox.warning(self, "Attenzione", f"Impossibile verificare lo spazio su disco:\n{str(e)}")

        # Salva le impostazioni correnti
        self._save_settings()

        # Determina impostazioni
        engine_str = "deepfilternet" if "DeepFilter" in self.combo_engine.currentText() else "noisereduce"
        intensity = float(self.slider_intensity.value())
        normalize = self.chk_normalize.isChecked()

        fmt_choice = self.combo_format.currentText()
        if "WAV" in fmt_choice:
            out_fmt = "WAV"
        elif "MP3" in fmt_choice:
            out_fmt = "MP3"
        else:
            out_fmt = "ORIGINAL"

        # Crea la lista di task
        tasks = []
        for row in range(count):
            file_path = self.queue_table.file_records[row]["path"]
            task = DenoiseTask(
                input_path=file_path,
                engine=engine_str,
                intensity=intensity,
                normalize=normalize,
                output_format=out_fmt,
                output_dir=out_dir
            )
            tasks.append(task)
            self.queue_table.set_file_status(row, "In attesa")
            self.queue_table.set_file_progress(row, 0.0)

        # Configura e avvia il worker
        self.worker = DenoiseWorker(tasks)
        self.worker.file_started.connect(self._on_worker_file_started)
        self.worker.file_progress.connect(self._on_worker_file_progress)
        self.worker.file_completed.connect(self._on_worker_file_completed)
        self.worker.file_error.connect(self._on_worker_file_error)
        self.worker.all_completed.connect(self._on_worker_all_completed)
        self.worker.cancelled.connect(self._on_worker_cancelled)

        self.btn_start.setEnabled(False)
        self.btn_cancel.setEnabled(True)
        self.overall_progress.setValue(0)
        self.lbl_task_status.setText("Avvio elaborazione in corso...")

        self.worker.start()

    def _cancel_processing(self):
        if self.worker and self.worker.isRunning():
            self.lbl_task_status.setText("Annullamento in corso, attesa blocco corrente...")
            self.btn_cancel.setEnabled(False)
            self.worker.cancel()

    def _on_worker_file_started(self, idx: int, file_path: str):
        name = os.path.basename(file_path)
        self.queue_table.set_file_status(idx, "In elaborazione...", "#3b82f6")
        self.lbl_task_status.setText(f"Elaborazione file {idx + 1}/{self.queue_table.rowCount()}: {name}")

    def _on_worker_file_progress(self, idx: int, frac: float, msg: str):
        self.queue_table.set_file_progress(idx, frac)
        # Avanzamento complessivo
        total_files = self.queue_table.rowCount()
        overall = ((idx + frac) / total_files) * 100.0
        self.overall_progress.setValue(int(overall))
        self.lbl_task_status.setText(f"File {idx + 1}/{total_files}: {msg}")

    def _on_worker_file_completed(self, idx: int, out_audio: str, out_video: str, stats: dict):
        self.queue_table.set_file_status(idx, "Completato", "#22c55e")
        self.queue_table.set_file_progress(idx, 1.0)
        self.queue_table.set_file_result(idx, out_audio, out_video)

        # Se e il primo completato o selezionato, caricalo nel player
        rec = self.queue_table.file_records[idx]
        self.ab_player.set_audio_files(rec["path"], out_audio)
        self.btn_save_as.setEnabled(True)

    def _on_worker_file_error(self, idx: int, err_msg: str):
        self.queue_table.set_file_status(idx, "Errore", "#ef4444")
        self.lbl_task_status.setText(f"Errore nel file {idx + 1}: {err_msg}")
        QMessageBox.warning(
            self,
            "Errore durante l'elaborazione",
            f"Errore durante l'elaborazione del file:\n{self.queue_table.file_records[idx]['path']}\n\nMotivo:\n{err_msg}"
        )

    def _on_worker_cancelled(self):
        self.btn_start.setEnabled(True)
        self.btn_cancel.setEnabled(False)
        self.lbl_task_status.setText("Elaborazione annullata dall'utente.")
        self.statusBar.showMessage("Operazione annullata.", 5000)

        # Marca come annullati i task rimasti
        for row in range(self.queue_table.rowCount()):
            status = self.queue_table.file_records[row]["status"]
            if status in ("In attesa", "In elaborazione..."):
                self.queue_table.set_file_status(row, "Annullato", "#f59e0b")

    def _on_worker_all_completed(self):
        self.btn_start.setEnabled(True)
        self.btn_cancel.setEnabled(False)
        self.overall_progress.setValue(100)
        self.lbl_task_status.setText("Tutti i file sono stati elaborati con successo!")
        self.statusBar.showMessage("Elaborazione batch completata.", 5000)

        QMessageBox.information(
            self,
            "Elaborazione Completata",
            "Tutti i file della coda sono stati ripuliti e salvati con successo!\n"
            "Puoi ascoltare il confronto nel player o aprire la cartella di destinazione."
        )

    def _load_settings(self):
        """Carica le impostazioni dell'ultima sessione."""
        engine = self.settings.value("engine", "DeepFilterNet (Ottimizzato per la voce)")
        idx = self.combo_engine.findText(engine)
        if idx >= 0:
            self.combo_engine.setCurrentIndex(idx)

        intensity = self.settings.value("intensity", 100, type=int)
        self.slider_intensity.setValue(intensity)

        normalize = self.settings.value("normalize", True, type=bool)
        self.chk_normalize.setChecked(normalize)

        fmt = self.settings.value("format", "WAV (Massima qualità)")
        idx_fmt = self.combo_format.findText(fmt)
        if idx_fmt >= 0:
            self.combo_format.setCurrentIndex(idx_fmt)

        out_dir = self.settings.value("output_dir", str(config.get_base_dir() / "outputs"))
        self.txt_out_dir.setText(out_dir)

    def _save_settings(self):
        """Salva le impostazioni correnti nel registro Windows / QSettings."""
        self.settings.setValue("engine", self.combo_engine.currentText())
        self.settings.setValue("intensity", self.slider_intensity.value())
        self.settings.setValue("normalize", self.chk_normalize.isChecked())
        self.settings.setValue("format", self.combo_format.currentText())
        self.settings.setValue("output_dir", self.txt_out_dir.text().strip())

    def closeEvent(self, event):
        """Salva impostazioni prima di chiudere e interrompe eventuali worker attivi."""
        self._save_settings()
        if self.worker and self.worker.isRunning():
            reply = QMessageBox.question(
                self,
                "Elaborazione in corso",
                "Un'elaborazione è attualmente in corso. Vuoi annullarla e chiudere l'applicazione?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )
            if reply == QMessageBox.Yes:
                self.worker.cancel()
                self.worker.wait(2000)
                event.accept()
            else:
                event.ignore()
        else:
            event.accept()
