"""
Modulo desktop/theme.py: Gestione del tema chiaro/scuro coerente con Windows
e fogli di stile (QSS) moderni e professionali.
"""

import sys
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication


def is_windows_dark_mode() -> bool:
    """Verifica se il sistema Windows e configurato in Dark Mode per le app."""
    if sys.platform != "win32":
        return False
    try:
        import winreg
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize"
        )
        val, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")
        winreg.CloseKey(key)
        return val == 0
    except Exception:
        # Fallback su QStyleHints se disponibile
        app = QApplication.instance()
        if app and hasattr(app, "styleHints"):
            return app.styleHints().colorScheme().name == "Dark"
        return False


def get_stylesheet(dark: bool = False) -> str:
    """Restituisce il foglio di stile QSS per l'applicazione."""
    if dark:
        return """
        QMainWindow, QDialog {
            background-color: #0f172a;
            color: #f8fafc;
        }
        QWidget {
            color: #f8fafc;
            font-family: "Segoe UI", system-ui, -apple-system, sans-serif;
            font-size: 13px;
        }
        QGroupBox {
            background-color: #1e293b;
            border: 1px solid #334155;
            border-radius: 8px;
            margin-top: 12px;
            padding-top: 16px;
            font-weight: 600;
        }
        QGroupBox::title {
            subcontrol-origin: margin;
            left: 14px;
            padding: 0 6px;
            color: #94a3b8;
        }
        QPushButton {
            background-color: #334155;
            color: #f8fafc;
            border: 1px solid #475569;
            border-radius: 6px;
            padding: 6px 14px;
            font-weight: 500;
        }
        QPushButton:hover {
            background-color: #475569;
            border-color: #64748b;
        }
        QPushButton:pressed {
            background-color: #1e293b;
        }
        QPushButton:disabled {
            background-color: #1e293b;
            color: #64748b;
            border-color: #334155;
        }
        QPushButton#primaryBtn {
            background-color: #2563eb;
            color: #ffffff;
            border: 1px solid #3b82f6;
            font-weight: 600;
            font-size: 14px;
            padding: 8px 18px;
        }
        QPushButton#primaryBtn:hover {
            background-color: #1d4ed8;
            border-color: #60a5fa;
        }
        QPushButton#cancelBtn {
            background-color: #dc2626;
            color: #ffffff;
            border: 1px solid #ef4444;
            font-weight: 600;
            padding: 8px 18px;
        }
        QPushButton#cancelBtn:hover {
            background-color: #b91c1c;
        }
        QPushButton#cancelBtn:disabled {
            background-color: #334155;
            color: #64748b;
            border-color: #334155;
        }
        QTableWidget {
            background-color: #1e293b;
            border: 1px solid #334155;
            border-radius: 6px;
            gridline-color: #334155;
            selection-background-color: #3b82f6;
            selection-color: #ffffff;
        }
        QHeaderView::section {
            background-color: #0f172a;
            color: #94a3b8;
            border: none;
            border-bottom: 1px solid #334155;
            padding: 6px;
            font-weight: 600;
        }
        QProgressBar {
            border: 1px solid #334155;
            border-radius: 4px;
            text-align: center;
            background-color: #0f172a;
            color: #f8fafc;
            height: 18px;
        }
        QProgressBar::chunk {
            background-color: #3b82f6;
            border-radius: 3px;
        }
        QSlider::groove:horizontal {
            height: 6px;
            background: #334155;
            border-radius: 3px;
        }
        QSlider::sub-page:horizontal {
            background: #3b82f6;
            border-radius: 3px;
        }
        QSlider::handle:horizontal {
            background: #f8fafc;
            border: 1px solid #94a3b8;
            width: 16px;
            margin: -5px 0;
            border-radius: 8px;
        }
        QComboBox, QLineEdit {
            background-color: #1e293b;
            border: 1px solid #334155;
            border-radius: 6px;
            padding: 5px 8px;
            color: #f8fafc;
        }
        QComboBox:hover, QLineEdit:hover {
            border-color: #475569;
        }
        QComboBox::drop-down {
            border: none;
            width: 20px;
        }
        QStatusBar {
            background-color: #0f172a;
            border-top: 1px solid #334155;
            color: #94a3b8;
        }
        """
    else:
        return """
        QMainWindow, QDialog {
            background-color: #f8fafc;
            color: #0f172a;
        }
        QWidget {
            color: #0f172a;
            font-family: "Segoe UI", system-ui, -apple-system, sans-serif;
            font-size: 13px;
        }
        QGroupBox {
            background-color: #ffffff;
            border: 1px solid #e2e8f0;
            border-radius: 8px;
            margin-top: 12px;
            padding-top: 16px;
            font-weight: 600;
        }
        QGroupBox::title {
            subcontrol-origin: margin;
            left: 14px;
            padding: 0 6px;
            color: #64748b;
        }
        QPushButton {
            background-color: #f1f5f9;
            color: #0f172a;
            border: 1px solid #cbd5e1;
            border-radius: 6px;
            padding: 6px 14px;
            font-weight: 500;
        }
        QPushButton:hover {
            background-color: #e2e8f0;
            border-color: #94a3b8;
        }
        QPushButton:pressed {
            background-color: #cbd5e1;
        }
        QPushButton:disabled {
            background-color: #f1f5f9;
            color: #94a3b8;
            border-color: #e2e8f0;
        }
        QPushButton#primaryBtn {
            background-color: #2563eb;
            color: #ffffff;
            border: 1px solid #1d4ed8;
            font-weight: 600;
            font-size: 14px;
            padding: 8px 18px;
        }
        QPushButton#primaryBtn:hover {
            background-color: #1d4ed8;
        }
        QPushButton#cancelBtn {
            background-color: #dc2626;
            color: #ffffff;
            border: 1px solid #b91c1c;
            font-weight: 600;
            padding: 8px 18px;
        }
        QPushButton#cancelBtn:hover {
            background-color: #b91c1c;
        }
        QPushButton#cancelBtn:disabled {
            background-color: #f1f5f9;
            color: #94a3b8;
            border-color: #e2e8f0;
        }
        QTableWidget {
            background-color: #ffffff;
            border: 1px solid #e2e8f0;
            border-radius: 6px;
            gridline-color: #f1f5f9;
            selection-background-color: #3b82f6;
            selection-color: #ffffff;
        }
        QHeaderView::section {
            background-color: #f8fafc;
            color: #64748b;
            border: none;
            border-bottom: 1px solid #e2e8f0;
            padding: 6px;
            font-weight: 600;
        }
        QProgressBar {
            border: 1px solid #cbd5e1;
            border-radius: 4px;
            text-align: center;
            background-color: #f1f5f9;
            color: #0f172a;
            height: 18px;
        }
        QProgressBar::chunk {
            background-color: #2563eb;
            border-radius: 3px;
        }
        QSlider::groove:horizontal {
            height: 6px;
            background: #e2e8f0;
            border-radius: 3px;
        }
        QSlider::sub-page:horizontal {
            background: #2563eb;
            border-radius: 3px;
        }
        QSlider::handle:horizontal {
            background: #ffffff;
            border: 1px solid #94a3b8;
            width: 16px;
            margin: -5px 0;
            border-radius: 8px;
        }
        QComboBox, QLineEdit {
            background-color: #ffffff;
            border: 1px solid #cbd5e1;
            border-radius: 6px;
            padding: 5px 8px;
            color: #0f172a;
        }
        QComboBox:hover, QLineEdit:hover {
            border-color: #94a3b8;
        }
        QComboBox::drop-down {
            border: none;
            width: 20px;
        }
        QStatusBar {
            background-color: #f8fafc;
            border-top: 1px solid #e2e8f0;
            color: #64748b;
        }
        """
