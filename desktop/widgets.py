"""
Modulo desktop/widgets.py: Componenti personalizzati per l'interfaccia Qt:
- Area Drag & Drop con pulsante Sfoglia
- Tabella coda batch con indicatori di stato e pulsanti di azione
"""

import os
from typing import List, Optional
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QDragEnterEvent, QDropEvent
from PySide6.QtWidgets import (
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMenu,
    QProgressBar,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from core.audio_io import SUPPORTED_EXTENSIONS, is_supported_file, is_video_file


class DropArea(QFrame):
    """Area di trascinamento file con supporto Drag & Drop e pulsante Sfoglia."""

    files_added = Signal(list)

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self._setup_ui()

    def _setup_ui(self):
        self.setObjectName("dropArea")
        self.setStyleSheet("""
            QFrame#dropArea {
                border: 2px dashed #64748b;
                border-radius: 10px;
                padding: 16px;
                background-color: rgba(100, 116, 139, 0.05);
            }
            QFrame#dropArea:hover {
                border-color: #3b82f6;
                background-color: rgba(59, 130, 246, 0.08);
            }
        """)

        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignCenter)
        layout.setSpacing(10)

        lbl_icon = QLabel("📁")
        lbl_icon.setStyleSheet("font-size: 32px;")
        lbl_icon.setAlignment(Qt.AlignCenter)

        lbl_text = QLabel("Trascina qui i tuoi file audio o video, oppure")
        lbl_text.setStyleSheet("font-size: 14px; font-weight: 500;")
        lbl_text.setAlignment(Qt.AlignCenter)

        self.btn_browse = QPushButton("📂 Sfoglia File...")
        self.btn_browse.setFixedWidth(150)
        self.btn_browse.clicked.connect(self._browse_files)

        lbl_formats = QLabel("Formati supportati: MP3, WAV, M4A, FLAC, OGG, OPUS, MP4, MOV, MKV, WEBM")
        lbl_formats.setStyleSheet("font-size: 11px; color: #94a3b8;")
        lbl_formats.setAlignment(Qt.AlignCenter)

        layout.addWidget(lbl_icon)
        layout.addWidget(lbl_text)
        layout.addWidget(self.btn_browse, alignment=Qt.AlignCenter)
        layout.addWidget(lbl_formats)

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragMoveEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event: QDropEvent):
        urls = event.mimeData().urls()
        valid_paths = []
        for url in urls:
            path = url.toLocalFile()
            if os.path.isfile(path) and is_supported_file(path):
                valid_paths.append(path)
            elif os.path.isdir(path):
                for root, _, files in os.walk(path):
                    for f in files:
                        fp = os.path.join(root, f)
                        if is_supported_file(fp):
                            valid_paths.append(fp)

        if valid_paths:
            self.files_added.emit(valid_paths)
            event.acceptProposedAction()

    def _browse_files(self):
        filter_str = (
            "File Multimediali (*.wav *.mp3 *.m4a *.aac *.flac *.ogg *.opus *.mp4 *.mov *.mkv *.webm *.avi);;"
            "File Audio (*.wav *.mp3 *.m4a *.aac *.flac *.ogg *.opus);;"
            "File Video (*.mp4 *.mov *.mkv *.webm *.avi);;"
            "Tutti i file (*.*)"
        )
        files, _ = QFileDialog.getOpenFileNames(
            self,
            "Seleziona file audio o video da ripulire",
            "",
            filter_str
        )
        if files:
            self.files_added.emit(files)


class FileQueueTable(QTableWidget):
    """Tabella interattiva per visualizzare la coda batch e lo stato di ciascun file."""

    file_selected_for_playback = Signal(str, str)  # original_path, cleaned_path

    COL_NAME = 0
    COL_TYPE = 1
    COL_STATUS = 2
    COL_PROGRESS = 3
    COL_OUTPUT = 4

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.file_records = []  # Lista di dict con info su ciascun file
        self._setup_table()

    def _setup_table(self):
        self.setColumnCount(5)
        self.setHorizontalHeaderLabels([
            "Nome File",
            "Tipo",
            "Stato",
            "Avanzamento",
            "File Ripulito"
        ])
        header = self.horizontalHeader()
        header.setSectionResizeMode(self.COL_NAME, QHeaderView.Stretch)
        header.setSectionResizeMode(self.COL_TYPE, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(self.COL_STATUS, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(self.COL_PROGRESS, QHeaderView.Fixed)
        header.resizeSection(self.COL_PROGRESS, 140)
        header.setSectionResizeMode(self.COL_OUTPUT, QHeaderView.Stretch)

        self.setSelectionBehavior(QTableWidget.SelectRows)
        self.setSelectionMode(QTableWidget.SingleSelection)
        self.setAlternatingRowColors(True)
        self.itemSelectionChanged.connect(self._on_selection_changed)

    def add_files(self, paths: List[str]):
        """Aggiunge una lista di percorsi alla coda evitando duplicati."""
        existing_paths = {r["path"] for r in self.file_records}
        for path in paths:
            abs_p = os.path.abspath(path)
            if abs_p in existing_paths:
                continue

            row = self.rowCount()
            self.insertRow(row)

            name = os.path.basename(abs_p)
            file_type = "🎬 Video" if is_video_file(abs_p) else "🔊 Audio"

            item_name = QTableWidgetItem(name)
            item_name.setToolTip(abs_p)
            item_type = QTableWidgetItem(file_type)
            item_status = QTableWidgetItem("In attesa")
            item_status.setTextAlignment(Qt.AlignCenter)
            item_output = QTableWidgetItem("-")

            bar = QProgressBar()
            bar.setRange(0, 100)
            bar.setValue(0)
            bar.setTextVisible(True)

            self.setItem(row, self.COL_NAME, item_name)
            self.setItem(row, self.COL_TYPE, item_type)
            self.setItem(row, self.COL_STATUS, item_status)
            self.setCellWidget(row, self.COL_PROGRESS, bar)
            self.setItem(row, self.COL_OUTPUT, item_output)

            record = {
                "path": abs_p,
                "out_audio": None,
                "out_video": None,
                "status": "In attesa"
            }
            self.file_records.append(record)
            existing_paths.add(abs_p)

    def set_file_status(self, row: int, status: str, color_hex: Optional[str] = None):
        if 0 <= row < self.rowCount():
            item = self.item(row, self.COL_STATUS)
            if item:
                item.setText(status)
                if color_hex:
                    item.setForeground(QColor(color_hex))
            self.file_records[row]["status"] = status

    def set_file_progress(self, row: int, fraction: float):
        if 0 <= row < self.rowCount():
            bar = self.cellWidget(row, self.COL_PROGRESS)
            if isinstance(bar, QProgressBar):
                bar.setValue(int(fraction * 100))

    def set_file_result(self, row: int, out_audio: str, out_video: Optional[str] = None):
        if 0 <= row < self.rowCount():
            self.file_records[row]["out_audio"] = out_audio
            self.file_records[row]["out_video"] = out_video
            item = self.item(row, self.COL_OUTPUT)
            disp_path = out_video if out_video else out_audio
            if item:
                item.setText(os.path.basename(disp_path))
                item.setToolTip(disp_path)

    def clear_queue(self):
        self.setRowCount(0)
        self.file_records.clear()

    def remove_selected(self):
        rows = sorted(set(index.row() for index in self.selectedIndexes()), reverse=True)
        for r in rows:
            self.removeRow(r)
            del self.file_records[r]

    def _on_selection_changed(self):
        selected_rows = self.selectedIndexes()
        if not selected_rows:
            return
        row = selected_rows[0].row()
        if 0 <= row < len(self.file_records):
            rec = self.file_records[row]
            self.file_selected_for_playback.emit(rec["path"], rec["out_audio"] or "")
