package com.voicecleaner.audio

import android.annotation.SuppressLint
import android.media.AudioFormat
import android.media.AudioRecord
import android.media.MediaRecorder
import kotlinx.coroutines.*
import java.io.File
import java.io.FileOutputStream
import java.io.RandomAccessFile
import java.nio.ByteBuffer
import java.nio.ByteOrder

/**
 * Gestore della registrazione vocale microfonica nativa in formato PCM 16-bit 16kHz mono.
 */
class AudioRecorder {

    companion object {
        const val SAMPLE_RATE = 16000
        const val CHANNEL_CONFIG = AudioFormat.CHANNEL_IN_MONO
        const val AUDIO_FORMAT = AudioFormat.ENCODING_PCM_16BIT
    }

    private var audioRecord: AudioRecord? = null
    private var recordingJob: Job? = null
    var isRecording = false
        private set

    var onAmplitudeListener: ((Float) -> Unit)? = null
    var onDurationListener: ((Long) -> Unit)? = null

    @SuppressLint("MissingPermission")
    fun startRecording(outputFile: File, coroutineScope: CoroutineScope) {
        if (isRecording) return

        val minBufferSize = AudioRecord.getMinBufferSize(SAMPLE_RATE, CHANNEL_CONFIG, AUDIO_FORMAT)
        val bufferSize = (minBufferSize * 2).coerceAtLeast(4096)

        audioRecord = AudioRecord(
            MediaRecorder.AudioSource.MIC,
            SAMPLE_RATE,
            CHANNEL_CONFIG,
            AUDIO_FORMAT,
            bufferSize
        )

        audioRecord?.startRecording()
        isRecording = true

        recordingJob = coroutineScope.launch(Dispatchers.IO) {
            val audioBuffer = ShortArray(bufferSize / 2)
            val byteBuffer = ByteBuffer.allocate(audioBuffer.size * 2).order(ByteOrder.LITTLE_ENDIAN)

            // Scrittura intestazione provvisoria WAV
            FileOutputStream(outputFile).use { fos ->
                val emptyHeader = ByteArray(44)
                fos.write(emptyHeader)

                var totalBytesRead = 0L
                val startTime = System.currentTimeMillis()

                while (isActive && isRecording) {
                    val readCount = audioRecord?.read(audioBuffer, 0, audioBuffer.size) ?: 0
                    if (readCount > 0) {
                        byteBuffer.clear()
                        var maxAmp = 0f
                        for (i in 0 until readCount) {
                            val sample = audioBuffer[i]
                            byteBuffer.putShort(sample)
                            val abs = kotlin.math.abs(sample.toFloat()) / 32768.0f
                            if (abs > maxAmp) maxAmp = abs
                        }
                        fos.write(byteBuffer.array(), 0, readCount * 2)
                        totalBytesRead += readCount * 2

                        val elapsed = System.currentTimeMillis() - startTime
                        withContext(Dispatchers.Main) {
                            onAmplitudeListener?.invoke(maxAmp)
                            onDurationListener?.invoke(elapsed)
                        }
                    }
                }
                fos.flush()

                // Aggiorna l'header WAV finale con le dimensioni reali
                fixWavHeader(outputFile, totalBytesRead)
            }
        }
    }

    fun stopRecording() {
        if (!isRecording) return
        isRecording = false
        try {
            audioRecord?.stop()
            audioRecord?.release()
        } catch (_: Exception) {}
        audioRecord = null
        recordingJob?.cancel()
        recordingJob = null
    }

    private fun fixWavHeader(file: File, totalAudioBytes: Long) {
        val totalDataLen = totalAudioBytes + 36
        val sampleRate = SAMPLE_RATE
        val channels = 1
        val bitsPerSample = 16
        val byteRate = sampleRate * channels * (bitsPerSample / 8)
        val blockAlign = channels * (bitsPerSample / 8)

        val header = ByteBuffer.allocate(44).order(ByteOrder.LITTLE_ENDIAN)
        header.put("RIFF".toByteArray())
        header.putInt(totalDataLen.toInt())
        header.put("WAVE".toByteArray())
        header.put("fmt ".toByteArray())
        header.putInt(16) // Subchunk1Size
        header.putShort(1.toShort()) // PCM
        header.putShort(channels.toShort())
        header.putInt(sampleRate)
        header.putInt(byteRate)
        header.putShort(blockAlign.toShort())
        header.putShort(bitsPerSample.toShort())
        header.put("data".toByteArray())
        header.putInt(totalAudioBytes.toInt())

        RandomAccessFile(file, "rw").use { raf ->
            raf.seek(0)
            raf.write(header.array())
        }
    }
}
