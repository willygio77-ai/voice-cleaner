package com.voicecleaner.ui

import android.media.MediaPlayer
import kotlinx.coroutines.*
import java.io.File

/**
 * Gestore del lettore audio con switch A/B istantaneo sincronizzato al millisecondo.
 */
class AudioPlayerHelper(
    private val onPlaybackStateChanged: (isPlaying: Boolean) -> Unit,
    private val onProgressUpdate: (currentMs: Int, totalMs: Int) -> Unit
) {

    enum class TrackSource {
        ORIGINAL,
        CLEANED
    }

    private var mediaPlayer: MediaPlayer? = null
    private var originalFile: File? = null
    private var cleanedFile: File? = null

    var currentSource = TrackSource.ORIGINAL
        private set

    private var progressJob: Job? = null
    private val scope = CoroutineScope(Dispatchers.Main + Job())

    fun setFiles(original: File?, cleaned: File?) {
        originalFile = original
        cleanedFile = cleaned
        // Default su cleaned se disponibile, altrimenti originale
        currentSource = if (cleaned != null && cleaned.exists()) TrackSource.CLEANED else TrackSource.ORIGINAL
        preparePlayer(currentSource, startPlaying = false, seekPositionMs = 0)
    }

    fun isPlaying(): Boolean = mediaPlayer?.isPlaying == true

    fun togglePlayPause() {
        val player = mediaPlayer ?: return
        if (player.isPlaying) {
            player.pause()
            stopProgressTracking()
            onPlaybackStateChanged(false)
        } else {
            player.start()
            startProgressTracking()
            onPlaybackStateChanged(true)
        }
    }

    /**
     * Alterna la traccia tra Originale e Ripulito mantenendo la stessa esatta posizione temporale.
     */
    fun switchSource(targetSource: TrackSource) {
        if (currentSource == targetSource) return
        val currentPosition = mediaPlayer?.currentPosition ?: 0
        val wasPlaying = mediaPlayer?.isPlaying == true

        currentSource = targetSource
        preparePlayer(currentSource, startPlaying = wasPlaying, seekPositionMs = currentPosition)
    }

    fun seekTo(positionMs: Int) {
        mediaPlayer?.seekTo(positionMs)
    }

    private fun preparePlayer(source: TrackSource, startPlaying: Boolean, seekPositionMs: Int) {
        val targetFile = if (source == TrackSource.ORIGINAL) originalFile else cleanedFile
        if (targetFile == null || !targetFile.exists()) return

        stopProgressTracking()
        mediaPlayer?.release()
        mediaPlayer = null

        try {
            val player = MediaPlayer().apply {
                setDataSource(targetFile.absolutePath)
                prepare()
                seekTo(seekPositionMs)
                setOnCompletionListener {
                    stopProgressTracking()
                    onPlaybackStateChanged(false)
                    onProgressUpdate(duration, duration)
                }
            }
            mediaPlayer = player

            if (startPlaying) {
                player.start()
                startProgressTracking()
                onPlaybackStateChanged(true)
            } else {
                onPlaybackStateChanged(false)
                onProgressUpdate(seekPositionMs, player.duration)
            }
        } catch (_: Exception) {
            onPlaybackStateChanged(false)
        }
    }

    private fun startProgressTracking() {
        stopProgressTracking()
        progressJob = scope.launch {
            while (isActive) {
                val player = mediaPlayer
                if (player != null && player.isPlaying) {
                    onProgressUpdate(player.currentPosition, player.duration)
                }
                delay(100)
            }
        }
    }

    private fun stopProgressTracking() {
        progressJob?.cancel()
        progressJob = null
    }

    fun release() {
        stopProgressTracking()
        scope.cancel()
        mediaPlayer?.release()
        mediaPlayer = null
    }
}
