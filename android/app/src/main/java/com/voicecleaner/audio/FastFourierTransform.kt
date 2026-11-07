package com.voicecleaner.audio

import kotlin.math.atan2
import kotlin.math.cos
import kotlin.math.sin
import kotlin.math.sqrt

/**
 * Algoritmo Cooley-Tukey Radix-2 FFT/IFFT altamente ottimizzato per blocchi N = 512.
 * Esegue la trasformata di Fourier reale (RFFT da 512 campioni a 257 bin spettrali)
 * e l'antitrasformata (IRFFT da 257 bin spettrali a 512 campioni temporali).
 */
class FastFourierTransform(private val n: Int = 512) {

    init {
        require((n > 0) && ((n and (n - 1)) == 0)) { "La dimensione FFT deve essere una potenza di 2" }
    }

    private val tempReal = FloatArray(n)
    private val tempImag = FloatArray(n)

    /**
     * Esegue la RFFT di un segnale reale a 512 campioni.
     * Restituisce magnitudo e fase per i primi (N/2 + 1) = 257 coefficienti di frequenza.
     */
    fun rfft(input: FloatArray, outMag: FloatArray, outPhase: FloatArray) {
        val numBins = n / 2 + 1
        require(input.size == n) { "L'array di input deve avere dimensione $n" }
        require(outMag.size == numBins && outPhase.size == numBins) {
            "Gli array di output per magnitudo e fase devono avere dimensione $numBins"
        }

        // Copia il segnale reale, parte immaginaria azzerata
        System.arraycopy(input, 0, tempReal, 0, n)
        tempImag.fill(0f)

        // Esegue FFT complessa in-place
        transform(tempReal, tempImag, invert = false)

        // Calcola magnitudo e fase per i primi 257 bin
        for (k in 0 until numBins) {
            val r = tempReal[k]
            val i = tempImag[k]
            outMag[k] = sqrt(r * r + i * i)
            outPhase[k] = atan2(i, r)
        }
    }

    /**
     * Esegue la IRFFT partendo da magnitudo e fase dei 257 bin.
     * Ricostruisce la simmetria hermitiana per i 512 bin ed esegue la trasformata inversa.
     */
    fun irfft(mag: FloatArray, phase: FloatArray, outReal: FloatArray) {
        val numBins = n / 2 + 1
        require(mag.size == numBins && phase.size == numBins) {
            "Gli array di magnitudo e fase devono avere dimensione $numBins"
        }
        require(outReal.size == n) { "L'array di output deve avere dimensione $n" }

        // Ricostruisce la parte positiva dello spettro
        for (k in 0 until numBins) {
            val m = mag[k]
            val p = phase[k]
            tempReal[k] = m * cos(p)
            tempImag[k] = m * sin(p)
        }

        // Ricostruisce la simmetria hermitiana per i coefficienti speculari (k = 257..511)
        for (k in numBins until n) {
            val mirrorIndex = n - k
            tempReal[k] = tempReal[mirrorIndex]
            tempImag[k] = -tempImag[mirrorIndex] // Coniugato complesso
        }

        // Esegue IFFT in-place
        transform(tempReal, tempImag, invert = true)

        // La parte reale risultante è il segnale audio ricostruito
        System.arraycopy(tempReal, 0, outReal, 0, n)
    }

    /**
     * Algoritmo Radix-2 Cooley-Tukey FFT / IFFT in-place
     */
    private fun transform(real: FloatArray, imag: FloatArray, invert: Boolean) {
        // Bit-reversal permutation
        var j = 0
        for (i in 0 until n) {
            if (j > i) {
                val tr = real[i]
                real[i] = real[j]
                real[j] = tr

                val ti = imag[i]
                imag[i] = imag[j]
                imag[j] = ti
            }
            var m = n shr 1
            while (m >= 1 && j >= m) {
                j -= m
                m = m shr 1
            }
            j += m
        }

        // Cooley-Tukey decimation in time
        var step = 2
        while (step <= n) {
            val half = step shr 1
            val angle = (if (!invert) -2.0 * Math.PI else 2.0 * Math.PI) / step
            val wStepR = cos(angle).toFloat()
            val wStepI = sin(angle).toFloat()

            var i = 0
            while (i < n) {
                var wR = 1.0f
                var wI = 0.0f
                for (k in 0 until half) {
                    val uR = real[i + k]
                    val uI = imag[i + k]

                    val vR = real[i + k + half] * wR - imag[i + k + half] * wI
                    val vI = real[i + k + half] * wI + imag[i + k + half] * wR

                    real[i + k] = uR + vR
                    imag[i + k] = uI + vI

                    real[i + k + half] = uR - vR
                    imag[i + k + half] = uI - vI

                    val nextWR = wR * wStepR - wI * wStepI
                    wI = wR * wStepI + wI * wStepR
                    wR = nextWR
                }
                i += step
            }
            step = step shl 1
        }

        // Normalizzazione per IFFT
        if (invert) {
            val invN = 1.0f / n
            for (i in 0 until n) {
                real[i] *= invN
                imag[i] *= invN
            }
        }
    }
}
