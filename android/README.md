# 📱 Voice Cleaner Android (100% Offline AI Denoise)

Applicazione nativa per Android per la rimozione intelligente dei rumori di fondo da registrazioni vocali, basata sul modello neurale profondo **DTLN (Dual-signal Transformation LSTM Network)** eseguito in locale tramite **TensorFlow Lite**.

---

## ✨ Funzionalità

- **100% Offline**: Nessun invio dati su server o cloud. Tutta l'inferenza AI gira direttamente sulla CPU dello smartphone.
- **Modello Neurale Ultraleggero (DTLN TFLite)**: I due modelli (`model_1.tflite` e `model_2.tflite`) pesano complessivamente **meno di 4 MB**.
- **🎙️ Registratore Vocale Diretto**: Registra campioni dal microfono a 16 kHz mono con visualizzazione del tempo trascorso.
- **📂 Caricamento File Audio**: Supporta file WAV dalla memoria del telefono con resampling automatico a 16 kHz.
- **🎚️ Slider Intensità Dry / Wet (0 - 100%)**: Regola la quantità di abbattimento del rumore preservando il timbro naturale della stanza.
- **🔊 Player con Confronto A/B Istantaneo**: Alterna tra "Originale" e "Ripulito" mantenendo la stessa esatta posizione temporale al millisecondo.
- **📤 Condivisione Diretta**: Invia il file audio ripulito (`.wav`) via WhatsApp, Telegram, Gmail, Drive o salvalo nel dispositivo.

---

## 🛠️ Come Aprire e Compilare con Android Studio

Il progetto è pronto per essere aperto con **Android Studio** (già installato nel tuo sistema).

### 1. Apri il Progetto
1. Avvia **Android Studio** dal menu Start di Windows.
2. Clicca su **Open** (o *File > Open*).
3. Seleziona la cartella:
   ```
   C:\Antigravity\Audio\android
   ```
4. Attendi che Android Studio completi la sincronizzazione iniziale di Gradle (*Gradle Sync*).

### 2. Genera il file APK installabile (.apk)
Per generare il file `.apk` da trasferire e installare su qualsiasi telefono Android:
1. Nel menu in alto di Android Studio, seleziona:
   ```
   Build > Build Bundle(s) / APK(s) > Build APK(s)
   ```
2. Al termine della compilazione (pochi secondi), apparirà una notifica in basso a destra con il link **"locate"**.
3. Troverai il file pronto in:
   ```
   android/app/build/outputs/apk/debug/app-debug.apk
   ```
4. Puoi copiare questo file sul tuo smartphone Android e aprirlo per installarlo direttamente!

### 3. Esegui direttamente su uno Smartphone collegato
1. Collega lo smartphone al computer via cavo USB con il **Debug USB** abilitato (nelle *Opzioni sviluppatore* di Android).
2. Seleziona il tuo dispositivo nel menu a tendina in alto in Android Studio.
3. Clicca sul pulsante verde **Run** (oppure premi `Shift + F10`).
4. L'app verrà compilata, installata e avviata automaticamente sullo smartphone!

---

## 📂 Struttura del Progetto

```
android/
│
├── build.gradle.kts                     # Root build configuration
├── settings.gradle.kts                  # Configurazione moduli e repository
├── gradle.properties
│
└── app/
    ├── build.gradle.kts                 # Dipendenze (TensorFlow Lite, Coroutine, Material 3)
    ├── proguard-rules.pro
    │
    └── src/main/
        ├── AndroidManifest.xml          # Permessi microfono e storage + FileProvider
        │
        ├── assets/                      # Modelli neurali TFLite (~3.9 MB totali)
        │   ├── model_1.tflite           # Stadio 1: Maschera su spettrogramma STFT
        │   └── model_2.tflite           # Stadio 2: Raffinamento e sintesi temporale
        │
        ├── java/com/voicecleaner/
        │   ├── audio/
        │   │   ├── FastFourierTransform.kt  # Algoritmo FFT/IFFT Radix-2 a 512 punti
        │   │   ├── WavUtils.kt              # Lettura, scrittura e resampling WAV a 16 kHz
        │   │   ├── AudioRecorder.kt         # Registratore microfonico nativo a 16 kHz
        │   │   └── DtlnDenoiseEngine.kt     # Pipeline di inferenza TFLite con Dry/Wet blending
        │   │
        │   └── ui/
        │       ├── MainActivity.kt          # Controller principale con Material Design 3
        │       └── AudioPlayerHelper.kt     # Player con switch A/B istantaneo
        │
        └── res/
            ├── layout/activity_main.xml     # Interfaccia grafica completa con card
            ├── values/strings.xml           # Testi e messaggi in italiano
            ├── values/colors.xml            # Palette Material 3
            ├── values/themes.xml            # Tema Day/Night
            └── drawable/                    # Icone vettoriali (mic, stop, play, share, ecc.)
```
