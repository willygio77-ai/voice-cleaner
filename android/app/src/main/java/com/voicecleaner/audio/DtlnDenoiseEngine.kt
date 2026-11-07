package com.voicecleaner.audio

import android.content.Context
import org.tensorflow.lite.Interpreter
import java.io.FileInputStream
import java.nio.ByteBuffer
import java.nio.channels.FileChannel

/**
 * Motore di denoise 100% offline basato sul modello neurale DTLN (Dual-signal Transformation LSTM Network).
 * Esegue in sequenza:
 * 1. Stadio STFT e mascheratura della magnitudo (model_1.tflite)
 * 2. Stadio temporale e sintesi OLA con decodifica profonda (model_2.tflite)
 * Include supporto per Dry/Wet blending (slider intensità 0-100%) e cancellazione asincrona.
 */
class DtlnDenoiseEngine(context: Context) : AutoCloseable {

    companion object {
        const val BLOCK_LEN = 512
        const val BLOCK_SHIFT = 128
        const val NUM_BINS = BLOCK_LEN / 2 + 1 // 257 bin spettrali
        const val NUM_LAYERS = 2
        const val NUM_UNITS = 128
    }

    private var interpreter1: Interpreter? = null
    private var interpreter2: Interpreter? = null
    private val fft = FastFourierTransform(BLOCK_LEN)

    // Mappatura dinamica degli indici dei tensori per robustezza
    private var model1MagInputIndex = 0
    private var model1StatesInputIndex = 1
    private var model1MaskOutputIndex = 0
    private var model1StatesOutputIndex = 1

    private var model2FrameInputIndex = 0
    private var model2StatesInputIndex = 1
    private var model2FrameOutputIndex = 0
    private var model2StatesOutputIndex = 1

    init {
        val options = Interpreter.Options().apply {
            setNumThreads(4) // Sfrutta i core multipli dello smartphone
        }

        val model1Buffer = loadModelFile(context, "model_1.tflite")
        val model2Buffer = loadModelFile(context, "model_2.tflite")

        val i1 = Interpreter(model1Buffer, options)
        val i2 = Interpreter(model2Buffer, options)

        // Rileva dinamicamente la posizione dei tensori del modello 1
        val i1In0Shape = i1.getInputTensor(0).shape()
        if (i1In0Shape.last() == NUM_BINS) {
            model1MagInputIndex = 0
            model1StatesInputIndex = 1
        } else {
            model1MagInputIndex = 1
            model1StatesInputIndex = 0
        }

        val i1Out0Shape = i1.getOutputTensor(0).shape()
        if (i1Out0Shape.last() == NUM_BINS) {
            model1MaskOutputIndex = 0
            model1StatesOutputIndex = 1
        } else {
            model1MaskOutputIndex = 1
            model1StatesOutputIndex = 0
        }

        // Rileva dinamicamente la posizione dei tensori del modello 2
        val i2In0Shape = i2.getInputTensor(0).shape()
        if (i2In0Shape.last() == BLOCK_LEN) {
            model2FrameInputIndex = 0
            model2StatesInputIndex = 1
        } else {
            model2FrameInputIndex = 1
            model2StatesInputIndex = 0
        }

        val i2Out0Shape = i2.getOutputTensor(0).shape()
        if (i2Out0Shape.last() == BLOCK_LEN) {
            model2FrameOutputIndex = 0
            model2StatesOutputIndex = 1
        } else {
            model2FrameOutputIndex = 1
            model2StatesOutputIndex = 0
        }

        interpreter1 = i1
        interpreter2 = i2
    }

    private fun loadModelFile(context: Context, modelName: String): ByteBuffer {
        val fileDescriptor = context.assets.openFd(modelName)
        val inputStream = FileInputStream(fileDescriptor.fileDescriptor)
        val fileChannel = inputStream.channel
        val startOffset = fileDescriptor.startOffset
        val declaredLength = fileDescriptor.declaredLength
        return fileChannel.map(FileChannel.MapMode.READ_ONLY, startOffset, declaredLength)
    }

    /**
     * Ripulisce il flusso audio completo con DTLN.
     * @param audio Campioni float normalizzati a 16 kHz
     * @param intensity Intensità di pulizia da 0.0 (originale) a 1.0 (massima pulizia)
     * @param onProgress Callback per la percentuale di avanzamento (0.0 .. 1.0)
     * @param isCancelled Callback per verificare se l'utente ha premuto Annulla
     */
    fun processAudio(
        audio: FloatArray,
        intensity: Float = 1.0f,
        onProgress: ((Float) -> Unit)? = null,
        isCancelled: () -> Boolean = { false }
    ): FloatArray {
        val i1 = interpreter1 ?: throw IllegalStateException("Model 1 non inizializzato")
        val i2 = interpreter2 ?: throw IllegalStateException("Model 2 non inizializzato")

        val totalSamples = audio.size
        val numBlocks = (totalSamples - (BLOCK_LEN - BLOCK_SHIFT)) / BLOCK_SHIFT
        if (numBlocks <= 0) return audio.copyOf()

        val output = FloatArray(totalSamples)

        val inBuffer = FloatArray(BLOCK_LEN)
        val outBuffer = FloatArray(BLOCK_LEN)

        val inMag = FloatArray(NUM_BINS)
        val inPhase = FloatArray(NUM_BINS)
        val estimatedComplexMag = FloatArray(NUM_BINS)
        val estimatedBlock = FloatArray(BLOCK_LEN)

        // Tensori di input/output per model 1
        val inMagTensor = Array(1) { Array(1) { FloatArray(NUM_BINS) } }
        var states1 = Array(1) { Array(NUM_LAYERS) { Array(NUM_UNITS) { FloatArray(2) } } }
        val outMaskTensor = Array(1) { Array(1) { FloatArray(NUM_BINS) } }
        var outStates1 = Array(1) { Array(NUM_LAYERS) { Array(NUM_UNITS) { FloatArray(2) } } }

        // Tensori di input/output per model 2
        val inFrameTensor = Array(1) { Array(1) { FloatArray(BLOCK_LEN) } }
        var states2 = Array(1) { Array(NUM_LAYERS) { Array(NUM_UNITS) { FloatArray(2) } } }
        val outFrameTensor = Array(1) { Array(1) { FloatArray(BLOCK_LEN) } }
        var outStates2 = Array(1) { Array(NUM_LAYERS) { Array(NUM_UNITS) { FloatArray(2) } } }

        val clampedIntensity = intensity.coerceIn(0.0f, 1.0f)
        val dryWeight = 1.0f - clampedIntensity

        for (idx in 0 until numBlocks) {
            if (isCancelled()) {
                throw InterruptedException("Elaborazione annullata dall'utente")
            }

            val offset = idx * BLOCK_SHIFT

            // 1. Shift del buffer di ingresso e inserimento dei nuovi campioni
            System.arraycopy(inBuffer, BLOCK_SHIFT, inBuffer, 0, BLOCK_LEN - BLOCK_SHIFT)
            System.arraycopy(audio, offset, inBuffer, BLOCK_LEN - BLOCK_SHIFT, BLOCK_SHIFT)

            // 2. RFFT del blocco temporale di 512 campioni
            fft.rfft(inBuffer, inMag, inPhase)

            // 3. Inferenza Modello 1 (Stima maschera su magnitudo)
            System.arraycopy(inMag, 0, inMagTensor[0][0], 0, NUM_BINS)

            val inputs1 = if (model1MagInputIndex == 0) {
                arrayOf<Any>(inMagTensor, states1)
            } else {
                arrayOf<Any>(states1, inMagTensor)
            }

            val outputs1 = mutableMapOf<Int, Any>()
            outputs1[model1MaskOutputIndex] = outMaskTensor
            outputs1[model1StatesOutputIndex] = outStates1

            i1.runForMultipleInputsOutputs(inputs1, outputs1)
            states1 = outStates1

            // 4. Moltiplicazione per la maschera e IRFFT
            val mask = outMaskTensor[0][0]
            for (k in 0 until NUM_BINS) {
                estimatedComplexMag[k] = inMag[k] * mask[k]
            }
            fft.irfft(estimatedComplexMag, inPhase, estimatedBlock)

            // 5. Inferenza Modello 2 (Raffinamento nel dominio del tempo)
            System.arraycopy(estimatedBlock, 0, inFrameTensor[0][0], 0, BLOCK_LEN)

            val inputs2 = if (model2FrameInputIndex == 0) {
                arrayOf<Any>(inFrameTensor, states2)
            } else {
                arrayOf<Any>(states2, inFrameTensor)
            }

            val outputs2 = mutableMapOf<Int, Any>()
            outputs2[model2FrameOutputIndex] = outFrameTensor
            outputs2[model2StatesOutputIndex] = outStates2

            i2.runForMultipleInputsOutputs(inputs2, outputs2)
            states2 = outStates2

            // 6. Overlap-Add su outBuffer
            System.arraycopy(outBuffer, BLOCK_SHIFT, outBuffer, 0, BLOCK_LEN - BLOCK_SHIFT)
            outBuffer.fill(0f, BLOCK_LEN - BLOCK_SHIFT, BLOCK_LEN)

            val frameOut = outFrameTensor[0][0]
            for (i in 0 until BLOCK_LEN) {
                outBuffer[i] += frameOut[i]
            }

            // 7. Scrittura e miscelazione Dry/Wet sui campioni di output
            for (i in 0 until BLOCK_SHIFT) {
                val cleanSample = outBuffer[i]
                val rawSample = audio[offset + i]
                output[offset + i] = (dryWeight * rawSample + clampedIntensity * cleanSample)
            }

            if (idx % 20 == 0 || idx == numBlocks - 1) {
                onProgress?.invoke((idx + 1).toFloat() / numBlocks.toFloat())
            }
        }

        // Copia residuo non multiplo del blocco
        val processedLength = numBlocks * BLOCK_SHIFT
        if (processedLength < totalSamples) {
            System.arraycopy(audio, processedLength, output, processedLength, totalSamples - processedLength)
        }

        return output
    }

    override fun close() {
        interpreter1?.close()
        interpreter2?.close()
        interpreter1 = null
        interpreter2 = null
    }
}
