---
title: Voice Cleaner
emoji: 🎙️
colorFrom: indigo
colorTo: blue
sdk: gradio
sdk_version: 6.31.0
app_file: app.py
pinned: false
license: mit
---

# 🎙️ Voice Cleaner — Rimozione Rumore Vocale (Web & Desktop Windows)

Applicazione per la rimozione intelligente dei rumori di fondo (fruscio, ventole, condizionatori, traffico, riverbero e ronzii di rete) da registrazioni di parlato (interviste, podcast, riunioni, lezioni e video).

**100% in locale**: i tuoi file audio e video non vengono mai inviati su server o servizi cloud esterni.

Disponibile in due modalità:
1. **Applicazione Desktop Nativa per Windows 10/11 (PySide6 / Qt)** con elaborazione batch, drag & drop e player A/B istantaneo.
2. **Applicazione Web Locale (Gradio)** accessibile da qualsiasi browser.

Entrambe le versioni condividono lo stesso motore modulare in [`core/`](file:///c:/Antigravity/Audio/core/).

---

## ✨ Funzionalità Principali

- **Supporto Audio e Video Completo**:
  - Audio: `.wav`, `.mp3`, `.m4a`, `.aac`, `.flac`, `.ogg`, `.opus`.
  - Video: `.mp4`, `.mov`, `.mkv`, `.webm`, `.avi`.
- **Doppio Motore di Pulizia**:
  - **DeepFilterNet 3** *(Consigliato)*: Rete neurale profonda addestrata per la voce umana. Elimina il rumore preservando il timbro naturale, senza l'effetto "metallico" o "robotico".
  - **Spectral Gating (`noisereduce`)**: Motore spettrale leggero di fallback.
- **Slider Intensità Riduzione (Dry / Wet da 0 a 100%)**:
  - Dosaggio fine del rumore residuo: impostando ad es. l'80-90% si conserva un lieve residuo dell'ambiente naturale della stanza.
- **File Lunghi (1-2 ore) con Overlapped Chunking (OLA)**:
  - Suddivisione a blocchi di 30s con 2s di sovrapposizione e crossfade Hann. Uso della RAM basso e costante, zero interruzioni e continuità perfetta del segnale.
- **Lettore Integrato con Confronto A/B Istantaneo**:
  - Nella versione desktop, puoi alternare in tempo reale tra **🔊 Originale** e **✨ Ripulito** mentre l'audio è in riproduzione, **mantenendo la stessa esatta posizione temporale**.
- **Coda di Elaborazione Batch (Desktop)**:
  - Trascina più file contemporaneamente, monitora l'avanzamento individuale e complessivo con pulsante **Annulla** funzionante e sicuro.
- **Muxing Video Lossless**:
  - Nei video, la traccia audio pulita viene rimontata copiando il flusso video originale (`-c:v copy`), garantendo massima velocità e zero perdita di qualità visiva.
- **Tema Chiaro / Scuro Dinamico**:
  - La versione desktop rileva automaticamente la preferenza di tema di Windows.
- **Salvataggio Sessione**:
  - Memorizza automaticamente l'ultimo motore, intensità, impostazioni di volume e cartella di destinazione.

---

## 📂 Architettura del Progetto

```
c:/Antigravity/Audio/
│
├── core/                           # Modulo condiviso (Web + Desktop)
│   ├── __init__.py                 # Compatibility shim torchaudio
│   ├── config.py                   # Risoluzione percorsi (PyInstaller sys._MEIPASS, modelli, binari)
│   ├── audio_io.py                 # I/O audio/video, gestione FFmpeg e muxing lossless
│   ├── chunking.py                 # Algoritmo Overlap-Add con crossfade Hann e token di cancellazione
│   └── denoise.py                  # Motori DeepFilterNet3, noisereduce, blending e normalizzazione
│
├── desktop/                        # Interfaccia Desktop nativa PySide6 (Qt)
│   ├── __init__.py
│   ├── main_window.py              # Finestra principale con gestione coda e layout moderno
│   ├── worker.py                   # QThread asincrono per elaborazione batch e cancellazione
│   ├── player.py                   # Player A/B sincronizzato alla stessa posizione temporale
│   ├── widgets.py                  # Area Drag & Drop e tabella della coda
│   └── theme.py                    # Rilevamento tema Windows (Chiaro/Scuro) e QSS
│
├── desktop_app.py                  # Entry point applicazione Desktop
├── app.py                          # Entry point applicazione Web (Gradio)
│
├── models/DeepFilterNet3/          # Checkpoint e configurazione offline inclusi nel bundle
├── bin/ffmpeg.exe                  # Binario statico FFmpeg per Windows incluso nel bundle
├── assets/                         # Icone applicazione (.ico / .png)
│
├── build_windows.bat               # Script di compilazione one-click per Windows
├── voice_cleaner.spec              # Specifiche PyInstaller per pacchetto standalone (--onedir)
├── installer.iss                   # Script Inno Setup per creare il file di installazione .exe
├── requirements.txt                # Dipendenze testate
└── README.md                       # Questa documentazione
```

---

## 🖥️ Avvio da Sorgente (Sviluppo)

### Prerequisiti
- **Python 3.10 o 3.11** *(consigliato 3.11 per i binari precompilati DeepFilterNet su Windows)*.
- Gestore ambienti consigliato: `uv` (oppure `py -3.11 -m venv`).

### Installazione Dipendenze
```powershell
# Dalla cartella c:\Antigravity\Audio
uv venv .venv --python 3.11
uv pip install -r requirements.txt --python .\.venv\Scripts\python.exe
```

### Avvio Versione Desktop
```powershell
.\.venv\Scripts\python.exe desktop_app.py
```

### Avvio Versione Web
```powershell
.\.venv\Scripts\python.exe app.py
```
Oppure fai doppio clic su [`avvia.bat`](file:///c:/Antigravity/Audio/avvia.bat) e apri nel browser `http://127.0.0.1:7860`.

---

## 📦 Compilazione Pacchetto Desktop Standalone (PyInstaller)

Per distribuire l'applicazione su qualsiasi PC Windows (anche senza Python, PyTorch o FFmpeg installati):

1. **Esegui lo script di compilazione**:
   Fai doppio clic su [`build_windows.bat`](file:///c:/Antigravity/Audio/build_windows.bat) oppure da PowerShell:
   ```powershell
   .\build_windows.bat
   ```
2. **Risultato della build**:
   Il pacchetto completo in modalità cartella (`--onedir`) viene generato in:
   ```
   dist\VoiceCleaner\VoiceCleaner.exe
   ```
   Questa cartella è autonoma: include Python, PyTorch CPU, DeepFilterNet3, FFmpeg (`bin/ffmpeg.exe`), i pesi del modello neurale e tutte le librerie Qt necessarie. Può essere zippata e copiata su qualsiasi PC Windows 10/11 a 64 bit.

### Contenuto del Pacchetto Autonomo
Grazie alla raccolta automatica completa di PyTorch, Torchaudio e DeepFilterNet (con esclusione dei moduli non necessari come QtWebEngine, Quick, Qml e Gradio web):
- Include: PyTorch CPU completo con estensioni C++ native (`torch._C`), modello neurale DeepFilterNet3, binario statico FFmpeg (`bin/ffmpeg.exe`), librerie PySide6 (Qt) e codec.
- Dimensione complessiva della cartella standalone: **~1.4 GB** (completamente autonoma, pronta per l'uso immediato senza internet e senza dipendenze sul PC di destinazione).

---

## 💿 Creazione dell'Installer Windows (Inno Setup)

Se desideri distribuire un unico file di installazione setup (es. `VoiceCleaner_Setup_v1.0.exe` con procedura guidata, icone nel menu Start e sul Desktop):

1. Installa Inno Setup (se non lo hai già):
   ```powershell
   winget install JRSoftware.InnoSetup
   ```
2. Compila l'installer:
   Fai clic destro sul file [`installer.iss`](file:///c:/Antigravity/Audio/installer.iss) e seleziona **"Compile"**, oppure esegui da terminale:
   ```powershell
   & "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" installer.iss
   ```
3. Troverai l'installer finale pronto per l'utente in `dist_installer\VoiceCleaner_Setup_v1.0.exe`.

---

## 🧪 Test Automatizzati

Puoi verificare l'intero stack in qualsiasi momento eseguendo la suite di test:
```powershell
.\.venv\Scripts\python.exe test_denoise.py
```
I test verificano:
- Rimozione del rumore sintetico con DeepFilterNet3 e Spectral Gating.
- Funzionamento del dry/wet blending e della normalizzazione.
- Elaborazione a blocchi (chunking) su un file lungo da 10 minuti (28.8M campioni, elaborato a 13.7x rispetto al tempo reale su CPU, con continuità perfetta e zero click).
