"""
Modulo desktop/player.py: Lettore audio A/B per il confronto istantaneo
tra audio originale e audio ripulito mantenendo lo stesso punto di riproduzione.
"""

from typing import Optional
from PySide6.QtCore import QTime, QUrl, Qt
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
from PySide6.QtWidgets import (
    QButtonGroup,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSlider,
    QVBoxLayout,
    QWidget,
)


class ABAudioPlayer(QWidget):
    """
    Widget con lettore integrato per confronto A/B.
    Consente di alternare istantaneamente tra Originale e Ripulito
    mantenendo la stessa esatta posizione temporale di riproduzione.
    """

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.original_path: Optional[str] = None
        self.cleaned_path: Optional[str] = None
        self.current_mode: str = "cleaned"  # 'original' oppure 'cleaned'
        self._user_is_seeking = False

        # Inizializza QMediaPlayer e QAudioOutput
        self.player = QMediaPlayer(self)
        self.audio_output = QAudioOutput(self)
        self.player.setAudioOutput(self.audio_output)
        self.audio_output.setVolume(1.0)

        self._setup_ui()
        self._connect_signals()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(8)

        # Barra superiore: Selettore A/B e pulsante Play/Pausa
        top_row = QHBoxLayout()
        top_row.setSpacing(10)

        self.btn_play = QPushButton("▶ Riproduci")
        self.btn_play.setFixedWidth(110)
        self.btn_play.setEnabled(False)

        # Gruppo di pulsanti A/B
        self.btn_group = QButtonGroup(self)
        self.btn_original = QPushButton("🔊 Originale")
        self.btn_original.setCheckable(True)
        self.btn_cleaned = QPushButton("✨ Ripulito")
        self.btn_cleaned.setCheckable(True)
        self.btn_cleaned.setChecked(True)

        self.btn_group.addButton(self.btn_original)
        self.btn_group.addButton(self.btn_cleaned)

        self.btn_original.setEnabled(False)
        self.btn_cleaned.setEnabled(False)

        top_row.addWidget(self.btn_play)
        top_row.addWidget(self.btn_original)
        top_row.addWidget(self.btn_cleaned)
        top_row.addStretch()

        self.lbl_mode_indicator = QLabel("Modalità attiva: <strong>✨ Ripulito</strong>")
        top_row.addWidget(self.lbl_mode_indicator)

        layout.addLayout(top_row)

        # Barra inferiore: Slider di avanzamento e tempi
        bottom_row = QHBoxLayout()
        bottom_row.setSpacing(10)

        self.lbl_current_time = QLabel("00:00")
        self.lbl_current_time.setFixedWidth(45)

        self.slider_pos = QSlider(Qt.Horizontal)
        self.slider_pos.setRange(0, 1000)
        self.slider_pos.setValue(0)
        self.slider_pos.setEnabled(False)

        self.lbl_total_time = QLabel("00:00")
        self.lbl_total_time.setFixedWidth(45)

        bottom_row.addWidget(self.lbl_current_time)
        bottom_row.addWidget(self.slider_pos)
        bottom_row.addWidget(self.lbl_total_time)

        layout.addLayout(bottom_row)

    def _connect_signals(self):
        self.btn_play.clicked.connect(self._toggle_play)
        self.btn_original.clicked.connect(lambda: self._switch_track("original"))
        self.btn_cleaned.clicked.connect(lambda: self._switch_track("cleaned"))

        self.player.positionChanged.connect(self._on_position_changed)
        self.player.durationChanged.connect(self._on_duration_changed)
        self.player.playbackStateChanged.connect(self._on_state_changed)

        self.slider_pos.sliderPressed.connect(self._on_slider_pressed)
        self.slider_pos.sliderReleased.connect(self._on_slider_released)
        self.slider_pos.sliderMoved.connect(self._on_slider_moved)

    def set_audio_files(self, original_path: Optional[str], cleaned_path: Optional[str]):
        """Imposta i file audio da confrontare."""
        self.player.stop()
        self.original_path = original_path
        self.cleaned_path = cleaned_path

        has_files = bool(self.original_path or self.cleaned_path)
        self.btn_play.setEnabled(has_files)
        self.slider_pos.setEnabled(has_files)
        self.btn_original.setEnabled(bool(self.original_path))
        self.btn_cleaned.setEnabled(bool(self.cleaned_path))

        # Imposta la sorgente iniziale (preferenza per cleaned se disponibile)
        if self.cleaned_path:
            self.current_mode = "cleaned"
            self.btn_cleaned.setChecked(True)
            self._load_source(self.cleaned_path)
            self.lbl_mode_indicator.setText("Modalità attiva: <strong>✨ Ripulito</strong>")
        elif self.original_path:
            self.current_mode = "original"
            self.btn_original.setChecked(True)
            self._load_source(self.original_path)
            self.lbl_mode_indicator.setText("Modalità attiva: <strong>🔊 Originale</strong>")

    def _load_source(self, path: str):
        url = QUrl.fromLocalFile(path)
        self.player.setSource(url)

    def _toggle_play(self):
        if self.player.playbackState() == QMediaPlayer.PlayingState:
            self.player.pause()
        else:
            self.player.play()

    def _switch_track(self, new_mode: str):
        """
        Cambia traccia mantenendo la stessa identica posizione temporale (A/B switch istantaneo).
        """
        if new_mode == self.current_mode:
            return

        target_path = self.original_path if new_mode == "original" else self.cleaned_path
        if not target_path:
            return

        current_pos = self.player.position()
        was_playing = (self.player.playbackState() == QMediaPlayer.PlayingState)

        self.current_mode = new_mode
        self._load_source(target_path)
        self.player.setPosition(current_pos)

        if was_playing:
            self.player.play()

        mode_text = "🔊 Originale" if new_mode == "original" else "✨ Ripulito"
        self.lbl_mode_indicator.setText(f"Modalità attiva: <strong>{mode_text}</strong>")

    def _on_state_changed(self, state):
        if state == QMediaPlayer.PlayingState:
            self.btn_play.setText("⏸ Pausa")
        else:
            self.btn_play.setText("▶ Riproduci")

    def _on_position_changed(self, position_ms: int):
        if not self._user_is_seeking:
            duration_ms = self.player.duration()
            if duration_ms > 0:
                slider_val = int((position_ms / duration_ms) * 1000)
                self.slider_pos.setValue(slider_val)
            self.lbl_current_time.setText(self._format_time(position_ms))

    def _on_duration_changed(self, duration_ms: int):
        self.lbl_total_time.setText(self._format_time(duration_ms))

    def _on_slider_pressed(self):
        self._user_is_seeking = True

    def _on_slider_released(self):
        self._user_is_seeking = False
        duration_ms = self.player.duration()
        if duration_ms > 0:
            target_ms = int((self.slider_pos.value() / 1000.0) * duration_ms)
            self.player.setPosition(target_ms)

    def _on_slider_moved(self, value: int):
        duration_ms = self.player.duration()
        if duration_ms > 0:
            target_ms = int((value / 1000.0) * duration_ms)
            self.lbl_current_time.setText(self._format_time(target_ms))

    @staticmethod
    def _format_time(ms: int) -> str:
        seconds = int((ms / 1000) % 60)
        minutes = int((ms / (1000 * 60)) % 60)
        hours = int((ms / (1000 * 60 * 60)))
        if hours > 0:
            return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
        return f"{minutes:02d}:{seconds:02d}"
