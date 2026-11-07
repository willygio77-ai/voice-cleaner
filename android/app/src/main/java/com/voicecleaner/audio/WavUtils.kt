package com.voicecleaner.audio

import java.io.*
import java.nio.ByteBuffer
import java.nio.ByteOrder
import kotlin.math.roundToInt

/**
 * Utility per la lettura e scrittura di file audio WAV PCM standard a 16 kHz.
 * Include conversione stereo -> mono e ricampionamento lineare ad alta fedeltà.
 */
object WavUtils {

    const val TARGET_SAMPLE_RATE = 16000

    data class AudioData(
        val samples: FloatArray,
        val sampleRate: Int
    )

    /**
     * Legge un file WAV da uno stream e restituisce i campioni float normalizzati (-1.0f .. 1.0f) a 16 kHz mono.
     */
    fun readWav(inputStream: InputStream): AudioData {
        val bytes = inputStream.readBytes()
        val buffer = ByteBuffer.wrap(bytes).order(ByteOrder.LITTLE_ENDIAN)

        // Verifica intestazione "RIFF" e "WAVE"
        val riff = ByteArray(4)
        buffer.get(riff)
        if (String(riff) != "RIFF") throw IllegalArgumentException("Formato WAV non valido (manca RIFF)")

        buffer.int // ChunkSize (salta)

        val wave = ByteArray(4)
        buffer.get(wave)
        if (String(wave) != "WAVE") throw IllegalArgumentException("Formato WAV non valido (manca WAVE)")

        var channels = 1
        var sampleRate = TARGET_SAMPLE_RATE
        var bitsPerSample = 16
        var audioFormat = 1 // 1 = PCM

        var pcmData: ByteArray? = null

        // Itera sui chunk per trovare "fmt " e "data"
        while (buffer.hasRemaining() && buffer.remaining() >= 8) {
            val chunkId = ByteArray(4)
            buffer.get(chunkId)
            val chunkName = String(chunkId)
            val chunkSize = buffer.int

            if (chunkName == "fmt ") {
                audioFormat = buffer.short.toInt()
                channels = buffer.short.toInt()
                sampleRate = buffer.int
                buffer.int // byteRate
                buffer.short // blockAlign
                bitsPerSample = buffer.short.toInt()

                // Salta eventuali byte extra del formato
                val extraBytes = chunkSize - 16
                if (extraBytes > 0) {
                    buffer.position(buffer.position() + extraBytes)
                }
            } else if (chunkName == "data") {
                val dataBytes = ByteArray(chunkSize.coerceAtMost(buffer.remaining()))
                buffer.get(dataBytes)
                pcmData = dataBytes
                break
            } else {
                // Salta chunk sconosciuti
                val toSkip = chunkSize.coerceAtMost(buffer.remaining())
                buffer.position(buffer.position() + toSkip)
            }
        }

        if (pcmData == null) {
            throw IllegalArgumentException("Nessun chunk dati audio trovato nel file WAV")
        }

        // Conversione PCM in float mono
        val rawFloatSamples = convertPcmToFloat(pcmData, channels, bitsPerSample, audioFormat)

        // Se il sample rate differisce da 16 kHz, esegui il resampling
        val resampled = if (sampleRate != TARGET_SAMPLE_RATE) {
            resampleLinear(rawFloatSamples, sampleRate, TARGET_SAMPLE_RATE)
        } else {
            rawFloatSamples
        }

        return AudioData(resampled, TARGET_SAMPLE_RATE)
    }

    /**
     * Salva un array di campioni float in formato WAV PCM 16-bit standard (riproducibile ovunque).
     */
    fun writeWav(file: File, samples: FloatArray, sampleRate: Int = TARGET_SAMPLE_RATE) {
        val numSamples = samples.size
        val numChannels = 1
        val bitsPerSample = 16
        val byteRate = sampleRate * numChannels * (bitsPerSample / 8)
        val blockAlign = numChannels * (bitsPerSample / 8)
        val subChunk2Size = numSamples * (bitsPerSample / 8)
        val chunkSize = 36 + subChunk2Size

        FileOutputStream(file).use { fos ->
            val out = BufferedOutputStream(fos)
            val header = ByteBuffer.allocate(44).order(ByteOrder.LITTLE_ENDIAN)

            // RIFF header
            header.put("RIFF".toByteArray())
            header.putInt(chunkSize)
            header.put("WAVE".toByteArray())

            // fmt subchunk
            header.put("fmt ".toByteArray())
            header.putInt(16) // Subchunk1Size per PCM
            header.putShort(1.toShort()) // AudioFormat = 1 (PCM)
            header.putShort(numChannels.toShort())
            header.putInt(sampleRate)
            header.putInt(byteRate)
            header.putShort(blockAlign.toShort())
            header.putShort(bitsPerSample.toShort())

            // data subchunk
            header.put("data".toByteArray())
            header.putInt(subChunk2Size)

            out.write(header.array())

            // Scrittura campioni PCM a 16 bit
            val sampleBuffer = ByteBuffer.allocate(numSamples * 2).order(ByteOrder.LITTLE_ENDIAN)
            for (sample in samples) {
                // Clamping -1.0f .. 1.0f
                val clamped = sample.coerceIn(-1.0f, 1.0f)
                val pcmValue = (clamped * 32767.0f).roundToInt().toShort()
                sampleBuffer.putShort(pcmValue)
            }
            out.write(sampleBuffer.array())
            out.flush()
        }
    }

    private fun convertPcmToFloat(
        data: ByteArray,
        channels: Int,
        bitsPerSample: Int,
        audioFormat: Int
    ): FloatArray {
        val buffer = ByteBuffer.wrap(data).order(ByteOrder.LITTLE_ENDIAN)

        return when {
            bitsPerSample == 16 && audioFormat == 1 -> {
                val totalFrames = data.size / (channels * 2)
                val out = FloatArray(totalFrames)
                for (i in 0 until totalFrames) {
                    var sum = 0f
                    for (ch in 0 until channels) {
                        sum += buffer.short.toFloat() / 32768.0f
                    }
                    out[i] = sum / channels.toFloat() // Mix in mono
                }
                out
            }
            bitsPerSample == 32 && audioFormat == 3 -> { // IEEE Float
                val totalFrames = data.size / (channels * 4)
                val out = FloatArray(totalFrames)
                for (i in 0 until totalFrames) {
                    var sum = 0f
                    for (ch in 0 until channels) {
                        sum += buffer.float
                    }
                    out[i] = sum / channels.toFloat()
                }
                out
            }
            else -> {
                // Fallback su 16-bit
                val totalFrames = data.size / (channels * 2)
                val out = FloatArray(totalFrames)
                for (i in 0 until totalFrames) {
                    var sum = 0f
                    for (ch in 0 until channels) {
                        sum += if (buffer.remaining() >= 2) buffer.short.toFloat() / 32768.0f else 0f
                    }
                    out[i] = sum / channels.toFloat()
                }
                out
            }
        }
    }

    /**
     * Resampling lineare ad alta precisione
     */
    fun resampleLinear(input: FloatArray, inRate: Int, outRate: Int): FloatArray {
        if (inRate == outRate) return input
        val ratio = inRate.toDouble() / outRate.toDouble()
        val outLength = (input.size / ratio).toInt()
        val output = FloatArray(outLength)

        for (i in 0 until outLength) {
            val srcPos = i * ratio
            val srcIndex = srcPos.toInt()
            val fraction = (srcPos - srcIndex).toFloat()

            val s0 = input[srcIndex.coerceIn(0, input.size - 1)]
            val s1 = input[(srcIndex + 1).coerceIn(0, input.size - 1)]

            output[i] = s0 + fraction * (s1 - s0)
        }
        return output
    }
}
