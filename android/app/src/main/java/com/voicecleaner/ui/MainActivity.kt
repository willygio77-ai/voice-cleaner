package com.voicecleaner.ui

import android.Manifest
import android.content.Intent
import android.content.pm.PackageManager
import android.net.Uri
import android.os.Bundle
import android.view.View
import android.widget.SeekBar
import android.widget.Toast
import androidx.activity.result.contract.ActivityResultContracts
import androidx.appcompat.app.AppCompatActivity
import androidx.core.content.ContextCompat
import androidx.core.content.FileProvider
import androidx.lifecycle.lifecycleScope
import com.google.android.material.button.MaterialButton
import com.voicecleaner.R
import com.voicecleaner.audio.*
import com.voicecleaner.databinding.ActivityMainBinding
import kotlinx.coroutines.*
import java.io.File
import java.util.Locale

class MainActivity : AppCompatActivity() {

    private lateinit var binding: ActivityMainBinding
    private val audioRecorder = AudioRecorder()
    private var denoiseEngine: DtlnDenoiseEngine? = null
    private var playerHelper: AudioPlayerHelper? = null

    private var currentOriginalFile: File? = null
    private var currentCleanedFile: File? = null
    private var currentOriginalAudioData: WavUtils.AudioData? = null

    private var denoiseJob: Job? = null
    private var isDenoiseCancelled = false

    // Launcher per richiesta permessi
    private val requestRecordAudioPermission =
        registerForActivityResult(ActivityResultContracts.RequestPermission()) { isGranted ->
            if (isGranted) {
                toggleRecording()
            } else {
                Toast.makeText(this, R.string.permission_mic_required, Toast.LENGTH_LONG).show()
            }
        }

    // Launcher per scelta file da memoria
    private val selectAudioFile =
        registerForActivityResult(ActivityResultContracts.GetContent()) { uri: Uri? ->
            if (uri != null) {
                loadAudioFromUri(uri)
            }
        }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        binding = ActivityMainBinding.inflate(layoutInflater)
        setContentView(binding.root)

        // Inizializza il motore AI DTLN in background
        lifecycleScope.launch(Dispatchers.IO) {
            try {
                denoiseEngine = DtlnDenoiseEngine(applicationContext)
            } catch (e: Exception) {
                withContext(Dispatchers.Main) {
                    Toast.makeText(this@MainActivity, "Errore caricamento modelli AI: ${e.message}", Toast.LENGTH_LONG).show()
                }
            }
        }

        setupUI()
        setupPlayer()
    }

    private fun setupUI() {
        // Pulsante Registra
        binding.btnRecord.setOnClickListener {
            checkAndToggleRecording()
        }

        // Pulsante Scegli File
        binding.btnOpenFile.setOnClickListener {
            selectAudioFile.launch("audio/*")
        }

        // Slider intensità
        binding.sliderIntensity.addOnChangeListener { _, value, _ ->
            binding.tvIntensityLabel.text = String.format(
                Locale.ITALIAN,
                getString(R.string.intensity_label),
                value.toInt()
            )
        }

        // Pulsante Avvia Pulizia
        binding.btnDenoise.setOnClickListener {
            startDenoiseProcess()
        }

        // Pulsante Annulla
        binding.btnCancel.setOnClickListener {
            cancelDenoiseProcess()
        }

        // Callback registratore vocale
        audioRecorder.onDurationListener = { elapsedMs ->
            val seconds = (elapsedMs / 1000) % 60
            val minutes = (elapsedMs / (1000 * 60))
            val timeStr = String.format(Locale.ITALIAN, "%02d:%02d", minutes, seconds)
            binding.tvAudioStatus.text = String.format(Locale.ITALIAN, getString(R.string.recording_active), timeStr)
        }

        audioRecorder.onRecordingFinished = { file ->
            loadAudioFromFile(file)
        }
    }

    private fun setupPlayer() {
        playerHelper = AudioPlayerHelper(
            onPlaybackStateChanged = { isPlaying ->
                binding.fabPlayPause.setImageResource(
                    if (isPlaying) R.drawable.ic_pause else R.drawable.ic_play
                )
            },
            onProgressUpdate = { currentMs, totalMs ->
                binding.seekBarPlayer.max = totalMs
                binding.seekBarPlayer.progress = currentMs
                binding.tvCurrentTime.text = formatTime(currentMs)
                binding.tvTotalTime.text = formatTime(totalMs)
            }
        )

        binding.fabPlayPause.setOnClickListener {
            playerHelper?.togglePlayPause()
        }

        binding.toggleSource.addOnButtonCheckedListener { _, checkedId, isChecked ->
            if (isChecked) {
                when (checkedId) {
                    R.id.btnSourceOriginal -> playerHelper?.switchSource(AudioPlayerHelper.TrackSource.ORIGINAL)
                    R.id.btnSourceCleaned -> playerHelper?.switchSource(AudioPlayerHelper.TrackSource.CLEANED)
                }
            }
        }

        binding.seekBarPlayer.setOnSeekBarChangeListener(object : SeekBar.OnSeekBarChangeListener {
            override fun onProgressChanged(seekBar: SeekBar?, progress: Int, fromUser: Boolean) {
                if (fromUser) {
                    playerHelper?.seekTo(progress)
                }
            }
            override fun onStartTrackingTouch(seekBar: SeekBar?) {}
            override fun onStopTrackingTouch(seekBar: SeekBar?) {}
        })

        // Condivisione file pulito
        binding.btnShare.setOnClickListener {
            shareCleanedAudio()
        }
    }

    private fun checkAndToggleRecording() {
        val permission = Manifest.permission.RECORD_AUDIO
        if (ContextCompat.checkSelfPermission(this, permission) == PackageManager.PERMISSION_GRANTED) {
            toggleRecording()
        } else {
            requestRecordAudioPermission.launch(permission)
        }
    }

    private fun toggleRecording() {
        if (!audioRecorder.isRecording) {
            val recordFile = File(cacheDir, "recording_${System.currentTimeMillis()}.wav")
            audioRecorder.startRecording(recordFile, lifecycleScope)

            binding.btnRecord.setText(R.string.btn_stop_record)
            binding.btnRecord.setIconResource(R.drawable.ic_stop)
            binding.btnRecord.setBackgroundColor(ContextCompat.getColor(this, R.color.accent_record))
            binding.btnOpenFile.isEnabled = false
            binding.btnDenoise.isEnabled = false
            currentOriginalFile = recordFile
        } else {
            audioRecorder.stopRecording()
            binding.btnRecord.setText(R.string.btn_record)
            binding.btnRecord.setIconResource(R.drawable.ic_mic)
            binding.btnRecord.setBackgroundColor(ContextCompat.getColor(this, R.color.primary))
            binding.btnOpenFile.isEnabled = true
        }
    }

    private fun loadAudioFromUri(uri: Uri) {
        lifecycleScope.launch(Dispatchers.IO) {
            try {
                val tempFile = File(cacheDir, "input_audio_${System.currentTimeMillis()}.wav")
                contentResolver.openInputStream(uri)?.use { input ->
                    tempFile.outputStream().use { output ->
                        input.copyTo(output)
                    }
                }
                withContext(Dispatchers.Main) {
                    loadAudioFromFile(tempFile)
                }
            } catch (e: Exception) {
                withContext(Dispatchers.Main) {
                    Toast.makeText(this@MainActivity, "Errore apertura file: ${e.message}", Toast.LENGTH_LONG).show()
                }
            }
        }
    }

    private fun loadAudioFromFile(file: File) {
        currentOriginalFile = file
        lifecycleScope.launch(Dispatchers.IO) {
            try {
                file.inputStream().use { stream ->
                    val data = WavUtils.readWav(stream)
                    currentOriginalAudioData = data
                }
                withContext(Dispatchers.Main) {
                    val durationSec = currentOriginalAudioData!!.samples.size / WavUtils.TARGET_SAMPLE_RATE
                    binding.tvAudioStatus.text = String.format(
                        Locale.ITALIAN,
                        "File pronto: %s (Durata: %02d:%02d, 16 kHz mono)",
                        file.name,
                        durationSec / 60,
                        durationSec % 60
                    )
                    binding.btnDenoise.isEnabled = true
                    // Reset stato player
                    binding.cardPlayer.visibility = View.GONE
                }
            } catch (e: Exception) {
                withContext(Dispatchers.Main) {
                    Toast.makeText(this@MainActivity, "Formato non supportato: ${e.message}", Toast.LENGTH_LONG).show()
                }
            }
        }
    }

    private fun startDenoiseProcess() {
        val audioData = currentOriginalAudioData
        if (audioData == null) {
            Toast.makeText(this, R.string.error_no_audio, Toast.LENGTH_SHORT).show()
            return
        }
        val engine = denoiseEngine
        if (engine == null) {
            Toast.makeText(this, "Motore AI in fase di inizializzazione, riprova tra un secondo.", Toast.LENGTH_SHORT).show()
            return
        }

        val intensity = binding.sliderIntensity.value / 100.0f
        isDenoiseCancelled = false

        binding.btnDenoise.isEnabled = false
        binding.btnRecord.isEnabled = false
        binding.btnOpenFile.isEnabled = false
        binding.layoutProgress.visibility = View.VISIBLE
        binding.progressIndicator.progress = 0
        binding.tvProgressPercent.text = "Elaborazione neurale in corso: 0%"

        denoiseJob = lifecycleScope.launch(Dispatchers.Default) {
            try {
                val cleanedSamples = engine.processAudio(
                    audio = audioData.samples,
                    intensity = intensity,
                    onProgress = { progress ->
                        val percent = (progress * 100).toInt()
                        lifecycleScope.launch(Dispatchers.Main) {
                            binding.progressIndicator.progress = percent
                            binding.tvProgressPercent.text = String.format(Locale.ITALIAN, getString(R.string.processing_audio), percent)
                        }
                    },
                    isCancelled = { isDenoiseCancelled }
                )

                // Salva il file WAV ripulito
                val cleanFile = File(cacheDir, "cleaned_${System.currentTimeMillis()}.wav")
                WavUtils.writeWav(cleanFile, cleanedSamples, WavUtils.TARGET_SAMPLE_RATE)
                currentCleanedFile = cleanFile

                withContext(Dispatchers.Main) {
                    binding.layoutProgress.visibility = View.GONE
                    binding.btnDenoise.isEnabled = true
                    binding.btnRecord.isEnabled = true
                    binding.btnOpenFile.isEnabled = true

                    Toast.makeText(this@MainActivity, R.string.processing_complete, Toast.LENGTH_SHORT).show()

                    // Mostra la card del player e imposta i file
                    binding.cardPlayer.visibility = View.VISIBLE
                    binding.toggleSource.check(R.id.btnSourceCleaned)
                    playerHelper?.setFiles(currentOriginalFile, currentCleanedFile)
                }
            } catch (e: InterruptedException) {
                withContext(Dispatchers.Main) {
                    binding.layoutProgress.visibility = View.GONE
                    binding.btnDenoise.isEnabled = true
                    binding.btnRecord.isEnabled = true
                    binding.btnOpenFile.isEnabled = true
                    Toast.makeText(this@MainActivity, "Elaborazione annullata.", Toast.LENGTH_SHORT).show()
                }
            } catch (e: Exception) {
                withContext(Dispatchers.Main) {
                    binding.layoutProgress.visibility = View.GONE
                    binding.btnDenoise.isEnabled = true
                    binding.btnRecord.isEnabled = true
                    binding.btnOpenFile.isEnabled = true
                    Toast.makeText(this@MainActivity, "Errore elaborazione: ${e.message}", Toast.LENGTH_LONG).show()
                }
            }
        }
    }

    private fun cancelDenoiseProcess() {
        isDenoiseCancelled = true
        denoiseJob?.cancel()
    }

    private fun shareCleanedAudio() {
        val file = currentCleanedFile ?: return
        if (!file.exists()) return

        val uri: Uri = FileProvider.getUriForFile(
            this,
            "${packageName}.fileprovider",
            file
        )

        val shareIntent = Intent(Intent.ACTION_SEND).apply {
            type = "audio/wav"
            putExtra(Intent.EXTRA_STREAM, uri)
            addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
        }
        startActivity(Intent.createChooser(shareIntent, "Condividi Audio Pulito"))
    }

    private fun formatTime(ms: Int): String {
        val totalSeconds = ms / 1000
        val minutes = totalSeconds / 60
        val seconds = totalSeconds % 60
        return String.format(Locale.ITALIAN, "%02d:%02d", minutes, seconds)
    }

    override fun onDestroy() {
        super.onDestroy()
        playerHelper?.release()
        denoiseEngine?.close()
        audioRecorder.stopRecording()
    }
}
