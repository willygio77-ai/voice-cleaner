import sys
import os

# Configurazione immediata delle DLL native per Windows e PyInstaller
if sys.platform == "win32":
    if getattr(sys, "frozen", False):
        base_dir = getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))
    else:
        base_dir = os.path.dirname(os.path.abspath(__file__))

    dll_paths = [
        base_dir,
        os.path.join(base_dir, "torch", "lib"),
        os.path.join(base_dir, "torch", "bin"),
        os.path.join(base_dir, "torch"),
        os.path.join(base_dir, "DeepFilterLib.libs"),
        os.path.join(base_dir, "numpy.libs"),
        os.path.join(base_dir, "scipy.libs"),
        os.path.join(base_dir, "PySide6"),
        os.path.join(base_dir, "bin"),
    ]

    for p in dll_paths:
        if os.path.isdir(p):
            try:
                os.add_dll_directory(p)
            except Exception:
                pass
            os.environ["PATH"] = p + os.pathsep + os.environ.get("PATH", "")

# Assicura che la directory radice sia nel sys.path
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

# Importa core per attivare compatibility shim
import core

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt
from desktop.main_window import MainWindow


def main():
    # Abilita High-DPI scaling su schermi 4K/Retina
    if hasattr(Qt, "AA_EnableHighDpiScaling"):
        QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    if hasattr(Qt, "AA_UseHighDpiPixmaps"):
        QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)

    app = QApplication(sys.argv)
    app.setApplicationName("VoiceCleaner")
    app.setOrganizationName("Antigravity")
    app.setApplicationDisplayName("Voice Cleaner")

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
