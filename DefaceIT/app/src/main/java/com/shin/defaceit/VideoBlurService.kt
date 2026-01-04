package com.shin.defaceit

import android.content.ContentValues
import android.content.Context
import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.graphics.Canvas
import android.graphics.Matrix
import android.graphics.Paint
import android.graphics.PixelFormat
import android.graphics.Rect
import android.graphics.SurfaceTexture
import android.media.MediaCodec
import android.media.MediaCodecInfo
import android.media.MediaExtractor
import android.media.MediaFormat
import android.media.MediaMuxer
import android.media.MediaMetadataRetriever
import android.net.Uri
import android.os.Build
import android.provider.MediaStore
import android.util.Log
import android.view.Surface
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import java.io.File
import java.io.FileInputStream
import java.io.FileOutputStream
import java.nio.ByteBuffer
import java.nio.ByteOrder
import java.nio.channels.FileChannel

class VideoBlurService(
    private val context: Context,
    private val blurStrength: Int = 51,
    private val blurType: String = "gaussian",
    private val confidence: Float = 0.15f,
    private val detectFaces: Boolean = true,
    private val pitchShift: Float = 0.0f
) {
    private var isCancelled = false
    private val faceDetector = FaceDetector(confidence)
    private val videoProcessor = VideoProcessor(blurStrength, blurType)
    private val notificationHelper = NotificationHelper(context)
    private val TAG = "VideoBlurService"

    fun cancel() {
        isCancelled = true
        notificationHelper.cancel()
    }

    private fun updateProgress(progress: Float, status: String, onProgress: (Float, String) -> Unit) {
        onProgress(progress, status)
        notificationHelper.showProgress(progress.toInt(), status)
    }

    private fun calculateTargetDimensions(sourceWidth: Int, sourceHeight: Int, maxDimension: Int = 720): Pair<Int, Int> {
        val aspectRatio = sourceWidth.toFloat() / sourceHeight.toFloat()
        val targetWidth: Int
        val targetHeight: Int
        
        if (sourceWidth >= sourceHeight) {
            // Landscape or square
            targetWidth = minOf(sourceWidth, maxDimension)
            targetHeight = (targetWidth / aspectRatio).toInt()
        } else {
            // Portrait
            targetHeight = minOf(sourceHeight, maxDimension)
            targetWidth = (targetHeight * aspectRatio).toInt()
        }
        
        // Ensure dimensions are even (required for YUV420)
        return Pair(targetWidth and 0xFFFE, targetHeight and 0xFFFE)
    }

    suspend fun processVideo(
        inputUri: Uri,
        onProgress: (Float, String) -> Unit
    ): Result<String> = withContext(Dispatchers.IO) {
        try {
            isCancelled = false
            updateProgress(0f, "Initializing...", onProgress)

            val retriever = MediaMetadataRetriever()
            retriever.setDataSource(context, inputUri)

            val width = retriever.extractMetadata(MediaMetadataRetriever.METADATA_KEY_VIDEO_WIDTH)?.toInt() ?: 1920
            val height = retriever.extractMetadata(MediaMetadataRetriever.METADATA_KEY_VIDEO_HEIGHT)?.toInt() ?: 1080
            val duration = retriever.extractMetadata(MediaMetadataRetriever.METADATA_KEY_DURATION)?.toLong() ?: 0
            val originalFrameRate = retriever.extractMetadata(MediaMetadataRetriever.METADATA_KEY_CAPTURE_FRAMERATE)?.toFloat() 
                ?: retriever.extractMetadata(MediaMetadataRetriever.METADATA_KEY_VIDEO_FRAME_COUNT)?.toFloat()?.let { 
                    it / (duration / 1000.0).toFloat()
                } ?: 30f
            
            // Cap frame rate at 30fps for faster processing
            val frameRate = minOf(originalFrameRate, 30f)
            Log.d(TAG, "Original FPS: $originalFrameRate, Processing at: ${frameRate}fps")
            
            val rotation = retriever.extractMetadata(MediaMetadataRetriever.METADATA_KEY_VIDEO_ROTATION)?.toInt() ?: 0

            val frameTimeUs = (1000000.0 / frameRate).toLong()
            val totalFrames = if (duration > 0) ((duration / 1000.0) * frameRate.toDouble()).toInt() else 100
            var processedFrames = 0

            updateProgress(5f, "Processing frames...", onProgress)

            val audioFile = if (pitchShift != 0.0f) {
                Log.d(TAG, "Using Sonic with pitch shift: $pitchShift semitones")
                processAudioWithSonic(inputUri, context)
            } else {
                Log.d(TAG, "No pitch shift, using vanilla audio extraction")
                extractAudio(inputUri, context)
            }
            Log.d(TAG, "Audio file created: ${audioFile?.absolutePath}, size: ${audioFile?.length()}")
            
            val outputStatsName = "DefaceIT_${System.currentTimeMillis()}"
            val outputFile = File(context.getExternalFilesDir(null), "${outputStatsName}.mp4")
            
            val tempOutputFile = File(context.cacheDir, "temp_video_${System.currentTimeMillis()}.mp4")
            val muxer = MediaMuxer(tempOutputFile.absolutePath, MediaMuxer.OutputFormat.MUXER_OUTPUT_MPEG_4)

            muxer.setOrientationHint(0) 
            
            // Calculate dimensions after rotation
            val (rotatedWidth, rotatedHeight) = if (rotation == 90 || rotation == 270) {
                height to width
            } else {
                width to height
            }
            
            // Resize to max 720p while preserving aspect ratio
            val (finalWidth, finalHeight) = calculateTargetDimensions(rotatedWidth, rotatedHeight, 720)
            Log.d(TAG, "Original: ${width}x${height}, After rotation: ${rotatedWidth}x${rotatedHeight}, Target: ${finalWidth}x${finalHeight}")

            val videoFormat = MediaFormat.createVideoFormat(MediaFormat.MIMETYPE_VIDEO_AVC, finalWidth, finalHeight)
            videoFormat.setInteger(MediaFormat.KEY_COLOR_FORMAT, MediaCodecInfo.CodecCapabilities.COLOR_FormatYUV420SemiPlanar)
            videoFormat.setInteger(MediaFormat.KEY_BIT_RATE, finalWidth * finalHeight * 3)
            videoFormat.setInteger(MediaFormat.KEY_FRAME_RATE, frameRate.toInt())
            videoFormat.setInteger(MediaFormat.KEY_I_FRAME_INTERVAL, 1)
            videoFormat.setInteger(MediaFormat.KEY_REPEAT_PREVIOUS_FRAME_AFTER, 0)
            videoFormat.setInteger(MediaFormat.KEY_MAX_INPUT_SIZE, finalWidth * finalHeight * 3 / 2)
            videoFormat.setString(MediaFormat.KEY_MIME, MediaFormat.MIMETYPE_VIDEO_AVC)

            val encoder = MediaCodec.createEncoderByType(MediaFormat.MIMETYPE_VIDEO_AVC)
            Log.d(TAG, "Using encoder: ${encoder.name}")
            try {
                encoder.configure(videoFormat, null, null, MediaCodec.CONFIGURE_FLAG_ENCODE)
            } catch (e: Exception) {
                Log.e(TAG, "Failed to configure with YUV420SemiPlanar, trying Flexible: ${e.message}")
                videoFormat.setInteger(MediaFormat.KEY_COLOR_FORMAT, MediaCodecInfo.CodecCapabilities.COLOR_FormatYUV420Flexible)
                encoder.configure(videoFormat, null, null, MediaCodec.CONFIGURE_FLAG_ENCODE)
            }
            encoder.start()

            val bufferInfo = MediaCodec.BufferInfo()
            var videoTrackIndex = -1
            var audioTrackIndex = -1
            var muxerStarted = false
            var presentationTimeUs = 0L
            var audioExtractor: MediaExtractor? = null
            var formatReceived = false

            try {
                if (audioFile != null) {
                    audioExtractor = MediaExtractor()
                    audioExtractor.setDataSource(audioFile.absolutePath)
                    for (i in 0 until audioExtractor.trackCount) {
                        val format = audioExtractor.getTrackFormat(i)
                        val mime = format.getString(MediaFormat.KEY_MIME) ?: continue
                        if (mime.startsWith("audio/")) {
                            audioExtractor.selectTrack(i)
                            break
                        }
                    }
                }

                var codecConfigReceived = false
                while (!formatReceived && !isCancelled) {
                    val outputBufferIndex = encoder.dequeueOutputBuffer(bufferInfo, 10000)
                    if (outputBufferIndex == MediaCodec.INFO_OUTPUT_FORMAT_CHANGED) {
                        val newFormat = encoder.outputFormat
                        Log.d(TAG, "Output format: $newFormat")
                        videoTrackIndex = muxer.addTrack(newFormat)
                        if (audioExtractor != null) {
                            try {
                                val audioFormat = audioExtractor.getTrackFormat(0)
                                audioTrackIndex = muxer.addTrack(audioFormat)
                                Log.d(TAG, "Audio track added: $audioTrackIndex")
                            } catch (e: Exception) {
                                Log.e(TAG, "Failed to add audio track: ${e.message}")
                            }
                        }
                        muxer.start()
                        muxerStarted = true
                        formatReceived = true
                        Log.d(TAG, "Muxer started, format received")
                    } else if (outputBufferIndex >= 0) {
                        val outputBuffer = encoder.getOutputBuffer(outputBufferIndex)
                        if (outputBuffer != null) {
                            if (bufferInfo.flags and MediaCodec.BUFFER_FLAG_CODEC_CONFIG != 0) {
                                if (!codecConfigReceived && muxerStarted) {
                                    // Do NOT write codec config as a sample. MediaMuxer handles this via addTrack format.
                                    // Just mark as received.
                                    codecConfigReceived = true
                                    Log.d(TAG, "Codec config buffer received (ignored for write): ${bufferInfo.size} bytes")
                                }
                            }
                        }
                        encoder.releaseOutputBuffer(outputBufferIndex, false)
                    }
                }

                if (!formatReceived) {
                    throw RuntimeException("Failed to receive output format")
                }

                var currentTimeUs = 0L
                var firstFrameQueued = false
                while (currentTimeUs < duration * 1000 && !isCancelled) {
                    val bitmap = retriever.getFrameAtTime(currentTimeUs, MediaMetadataRetriever.OPTION_CLOSEST)
                    if (bitmap != null) {
                        val rotatedBitmap = if (rotation != 0) {
                            val matrix = Matrix()
                            matrix.postRotate(rotation.toFloat())
                            Bitmap.createBitmap(bitmap, 0, 0, bitmap.width, bitmap.height, matrix, true)
                        } else {
                            bitmap
                        }

                        val processedBitmap = if (detectFaces) {
                            val faceRects = faceDetector.detectFaces(rotatedBitmap, 0)
                            videoProcessor.processFrame(rotatedBitmap, faceRects)
                        } else {
                            rotatedBitmap.copy(rotatedBitmap.config ?: Bitmap.Config.ARGB_8888, true)
                        }
                        
                        if (rotation != 0 && bitmap != rotatedBitmap) {
                            bitmap.recycle()
                        }

                        // bitmapToYuv420 will handle scaling if dimensions don't match
                        val yuvBuffer = bitmapToYuv420(processedBitmap, finalWidth, finalHeight)
                        var inputBufferIndex = encoder.dequeueInputBuffer(10000)
                        while (inputBufferIndex >= 0) {
                            val inputBuffer = encoder.getInputBuffer(inputBufferIndex)
                            if (inputBuffer != null) {
                                inputBuffer.clear()
                                inputBuffer.put(yuvBuffer)
                                val flags = if (!firstFrameQueued) {
                                    MediaCodec.BUFFER_FLAG_KEY_FRAME
                                } else {
                                    0
                                }
                                val timestamp = if (!firstFrameQueued) {
                                    0L
                                } else {
                                    presentationTimeUs
                                }
                                encoder.queueInputBuffer(
                                    inputBufferIndex,
                                    0,
                                    yuvBuffer.size,
                                    timestamp,
                                    flags
                                )
                                if (!firstFrameQueued) {
                                    firstFrameQueued = true
                                    Log.d(TAG, "First frame queued with KEY_FRAME flag at timestamp 0")
                                }
                            }
                            inputBufferIndex = encoder.dequeueInputBuffer(0)
                        }

                        processedBitmap.recycle()
                        bitmap.recycle()

                        while (true) {
                            val outputBufferIndex = encoder.dequeueOutputBuffer(bufferInfo, 10000)
                            if (outputBufferIndex == MediaCodec.INFO_TRY_AGAIN_LATER) {
                                break
                            } else if (outputBufferIndex == MediaCodec.INFO_OUTPUT_FORMAT_CHANGED) {
                                Log.w(TAG, "Format changed again, should not happen")
                            } else if (outputBufferIndex >= 0) {
                                val outputBuffer = encoder.getOutputBuffer(outputBufferIndex)
                                if (outputBuffer != null && muxerStarted) {
                                    if (bufferInfo.flags and MediaCodec.BUFFER_FLAG_CODEC_CONFIG != 0) {
                                        Log.d(TAG, "Skipping codec config buffer in frame loop: ${bufferInfo.size} bytes")
                                    } else if (bufferInfo.size > 0) {
                                        outputBuffer.position(bufferInfo.offset)
                                        outputBuffer.limit(bufferInfo.offset + bufferInfo.size)
                                        if (bufferInfo.presentationTimeUs < 0) {
                                            bufferInfo.presentationTimeUs = if (processedFrames == 0) 0L else presentationTimeUs
                                        }
                                        if (processedFrames == 0 && bufferInfo.presentationTimeUs != 0L) {
                                            bufferInfo.presentationTimeUs = 0L
                                            Log.d(TAG, "Forcing first frame timestamp to 0")
                                        }
                                        val isKeyFrame = bufferInfo.flags and MediaCodec.BUFFER_FLAG_KEY_FRAME != 0
                                        if (isKeyFrame) {
                                            Log.d(TAG, "Writing key frame at ${bufferInfo.presentationTimeUs}us")
                                        }
                                        if (processedFrames == 0) {
                                            if (!isKeyFrame) {
                                                Log.w(TAG, "First frame is not a key frame! Forcing key frame flag.")
                                                bufferInfo.flags = bufferInfo.flags or MediaCodec.BUFFER_FLAG_KEY_FRAME
                                            } else {
                                                Log.d(TAG, "First frame is a key frame at ${bufferInfo.presentationTimeUs}us")
                                            }
                                        }
                                        muxer.writeSampleData(videoTrackIndex, outputBuffer, bufferInfo)
                                    }
                                }
                                encoder.releaseOutputBuffer(outputBufferIndex, false)
                            }
                        }


                        presentationTimeUs += frameTimeUs
                        processedFrames++

                        if (processedFrames % 5 == 0) {
                            val progress = 5f + (processedFrames.toFloat() / totalFrames.coerceAtLeast(1) * 90f)
                            updateProgress(progress.coerceAtMost(95f), "Processed $processedFrames frames", onProgress)
                        }
                    }
                    currentTimeUs += frameTimeUs
                }

                var inputBufferIndex = encoder.dequeueInputBuffer(10000)
                var eosQueued = false
                while (inputBufferIndex >= 0 && !eosQueued) {
                    val inputBuffer = encoder.getInputBuffer(inputBufferIndex)
                    inputBuffer?.clear()
                    encoder.queueInputBuffer(
                        inputBufferIndex,
                        0,
                        0,
                        presentationTimeUs,
                        MediaCodec.BUFFER_FLAG_END_OF_STREAM
                    )
                    eosQueued = true
                    inputBufferIndex = encoder.dequeueInputBuffer(0)
                }

                var sawOutputEOS = false
                while (!sawOutputEOS) {
                    val outputBufferIndex = encoder.dequeueOutputBuffer(bufferInfo, 10000)
                    when (outputBufferIndex) {
                        MediaCodec.INFO_TRY_AGAIN_LATER -> {
                            continue
                        }
                        MediaCodec.INFO_OUTPUT_FORMAT_CHANGED -> {
                            continue
                        }
                        else -> {
                            val outputBuffer = encoder.getOutputBuffer(outputBufferIndex)
                            if (outputBuffer != null && bufferInfo.size > 0 && muxerStarted) {
                                if (bufferInfo.flags and MediaCodec.BUFFER_FLAG_CODEC_CONFIG == 0) {
                                    outputBuffer.position(bufferInfo.offset)
                                    outputBuffer.limit(bufferInfo.offset + bufferInfo.size)
                                    muxer.writeSampleData(videoTrackIndex, outputBuffer, bufferInfo)
                                }
                            }
                            val isEOS = bufferInfo.flags and MediaCodec.BUFFER_FLAG_END_OF_STREAM != 0
                            encoder.releaseOutputBuffer(outputBufferIndex, false)
                            if (isEOS) {
                                sawOutputEOS = true
                            }
                        }
                    }
                }

                if (audioExtractor != null && muxerStarted && audioTrackIndex >= 0) {
                    val audioBuffer = ByteBuffer.allocate(64 * 1024)
                    val audioBufferInfo = MediaCodec.BufferInfo()
                    audioExtractor.seekTo(0, MediaExtractor.SEEK_TO_CLOSEST_SYNC)
                    // Track is already selected correctly above, no need to re-select
                    var audioSamplesWritten = 0
                    while (true) {
                        val sampleSize = audioExtractor.readSampleData(audioBuffer, 0)
                        if (sampleSize < 0) break
                        audioBuffer.position(0)
                        audioBuffer.limit(sampleSize)
                        audioBufferInfo.size = sampleSize
                        val audioTime = audioExtractor.sampleTime
                        if (audioTime >= 0) {
                            audioBufferInfo.presentationTimeUs = audioTime
                        } else {
                            break
                        }
                        audioBufferInfo.flags = 0
                        muxer.writeSampleData(audioTrackIndex, audioBuffer, audioBufferInfo)
                        audioExtractor.advance()
                        audioSamplesWritten++
                    }
                    Log.d(TAG, "Written $audioSamplesWritten audio samples")
                }

                encoder.stop()
                encoder.release()
                audioExtractor?.release()
                
                if (muxerStarted) {
                    try {
                        muxer.stop()
                        Log.d(TAG, "Muxer stopped successfully")
                    } catch (e: Exception) {
                        Log.e(TAG, "Error stopping muxer: ${e.message}", e)
                    }
                } else {
                    Log.w(TAG, "Muxer was never started")
                }
                try {
                    muxer.release()
                } catch (e: Exception) {
                    Log.e(TAG, "Error releasing muxer: ${e.message}")
                }
                retriever.release()
                audioFile?.delete()
                
                updateProgress(95f, "Saving video...", onProgress)
                
                if (!tempOutputFile.exists() || tempOutputFile.length() == 0L) {
                    Log.e(TAG, "Temp output file does not exist or is empty!")
                    tempOutputFile.delete()
                    notificationHelper.showError("Video encoding failed - output file is empty")
                    return@withContext Result.failure(RuntimeException("Video encoding failed - output file is empty"))
                }
                
                try {
                    updateProgress(96f, "Copying video file...", onProgress)
                    tempOutputFile.copyTo(outputFile, overwrite = true)
                    tempOutputFile.delete()
                    Log.d(TAG, "Output file created: ${outputFile.length()} bytes")
                    
                    if (!outputFile.exists() || outputFile.length() == 0L) {
                        Log.e(TAG, "Output file is empty after copy!")
                        notificationHelper.showError("Failed to save video - file is empty")
                        return@withContext Result.failure(RuntimeException("Failed to save video - file is empty"))
                    }
                    
                    updateProgress(97f, "Validating video...", onProgress)
                    val testRetriever = MediaMetadataRetriever()
                    try {
                        testRetriever.setDataSource(outputFile.absolutePath)
                        val testDuration = testRetriever.extractMetadata(MediaMetadataRetriever.METADATA_KEY_DURATION)
                        val testWidth = testRetriever.extractMetadata(MediaMetadataRetriever.METADATA_KEY_VIDEO_WIDTH)
                        Log.d(TAG, "Video metadata - Duration: $testDuration ms, Width: $testWidth")
                    } catch (e: Exception) {
                        Log.e(TAG, "Failed to validate video: ${e.message}", e)
                        testRetriever.release()
                        notificationHelper.showError("Video file is corrupted: ${e.message}")
                        return@withContext Result.failure(RuntimeException("Video file is corrupted: ${e.message}"))
                    }
                    testRetriever.release()
                    
                    updateProgress(98f, "Registering in gallery...", onProgress)
                    if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
                        val values = ContentValues().apply {
                            put(MediaStore.Video.Media.RELATIVE_PATH, android.os.Environment.DIRECTORY_MOVIES)
                            put(MediaStore.Video.Media.DISPLAY_NAME, outputFile.name)
                            put(MediaStore.Video.Media.MIME_TYPE, "video/mp4")
                            put(MediaStore.Video.Media.IS_PENDING, 1)
                        }
                        val uri = context.contentResolver.insert(
                            MediaStore.Video.Media.EXTERNAL_CONTENT_URI,
                            values
                        )
                        if (uri != null) {
                            try {
                                context.contentResolver.openOutputStream(uri)?.use { os ->
                                    outputFile.inputStream().use { it.copyTo(os) }
                                }
                                val finalValues = ContentValues().apply {
                                    put(MediaStore.Video.Media.IS_PENDING, 0)
                                }
                                context.contentResolver.update(uri, finalValues, null, null)
                            } catch (e: Exception) {
                                Log.e(TAG, "Failed to write to MediaStore: ${e.message}", e)
                                // Continue - file is still saved in external files dir
                            }
                        }
                    } else {
                        try {
                            val values = ContentValues().apply {
                                put(MediaStore.Video.Media.DATA, outputFile.absolutePath)
                                put(MediaStore.Video.Media.MIME_TYPE, "video/mp4")
                            }
                            context.contentResolver.insert(MediaStore.Video.Media.EXTERNAL_CONTENT_URI, values)
                        } catch (e: Exception) {
                            Log.e(TAG, "Failed to register in MediaStore: ${e.message}", e)
                            // Continue - file is still saved in external files dir
                        }
                    }
                    
                    updateProgress(100f, "Complete!", onProgress)
                    notificationHelper.showComplete("Video processing completed successfully")
                    Result.success(outputFile.absolutePath)
                } catch (e: Exception) {
                    Log.e(TAG, "Failed to save video: ${e.message}", e)
                    notificationHelper.showError("Failed to save video: ${e.message}")
                    tempOutputFile.delete()
                    if (outputFile.exists()) {
                        outputFile.delete()
                    }
                    Result.failure(e)
                }
            } catch (e: Exception) {
                try {
                    encoder.stop()
                    encoder.release()
                } catch (ex: Exception) {}
                audioExtractor?.release()
                if (muxerStarted) {
                    try {
                        muxer.stop()
                    } catch (ex: Exception) {}
                }
                try {
                    muxer.release()
                } catch (ex: Exception) {}
                retriever.release()
                audioFile?.delete()
                tempOutputFile.delete()
                notificationHelper.showError("Processing failed: ${e.message}")
                Result.failure(e)
            }
        } catch (e: Exception) {
            notificationHelper.showError("Processing failed: ${e.message}")
            Result.failure(e)
        } finally {
            faceDetector.close()
        }
    }

    private suspend fun extractAudio(inputUri: Uri, context: Context): File? = withContext(Dispatchers.IO) {
        try {
            val extractor = MediaExtractor()
            extractor.setDataSource(context, inputUri, null)

            var audioTrackIndex = -1
            for (i in 0 until extractor.trackCount) {
                val format = extractor.getTrackFormat(i)
                val mime = format.getString(MediaFormat.KEY_MIME) ?: continue
                if (mime.startsWith("audio/")) {
                    audioTrackIndex = i
                    break
                }
            }

            if (audioTrackIndex == -1) {
                extractor.release()
                return@withContext null
            }

            extractor.selectTrack(audioTrackIndex)
            val format = extractor.getTrackFormat(audioTrackIndex)
            val mime = format.getString(MediaFormat.KEY_MIME) ?: "audio/mp4a-latm"

            val audioFile = File(context.cacheDir, "audio_${System.currentTimeMillis()}.m4a")
            val muxer = MediaMuxer(audioFile.absolutePath, MediaMuxer.OutputFormat.MUXER_OUTPUT_MPEG_4)
            val trackIndex = muxer.addTrack(format)
            muxer.start()

            val buffer = ByteBuffer.allocate(64 * 1024)
            val bufferInfo = MediaCodec.BufferInfo()

            while (true) {
                if (isCancelled) {
                    extractor.release()
                    muxer.stop()
                    muxer.release()
                    audioFile.delete()
                    return@withContext null
                }

                val sampleSize = extractor.readSampleData(buffer, 0)
                if (sampleSize < 0) break

                bufferInfo.size = sampleSize
                bufferInfo.presentationTimeUs = extractor.sampleTime
                bufferInfo.flags = extractor.sampleFlags

                muxer.writeSampleData(trackIndex, buffer, bufferInfo)
                extractor.advance()
            }

            extractor.release()
            muxer.stop()
            muxer.release()
            audioFile
        } catch (e: Exception) {
            Log.e(TAG, "Audio extraction failed", e)
            null
        }
    }
    
    private suspend fun processAudioWithSonic(inputUri: Uri, context: Context): File? = withContext(Dispatchers.IO) {
        try {
            val extractor = MediaExtractor()
            extractor.setDataSource(context, inputUri, null)
            
            var audioTrackIndex = -1
            for (i in 0 until extractor.trackCount) {
                val format = extractor.getTrackFormat(i)
                val mime = format.getString(MediaFormat.KEY_MIME) ?: continue
                if (mime.startsWith("audio/")) {
                    audioTrackIndex = i
                    break
                }
            }
            
            if (audioTrackIndex == -1) {
                extractor.release()
                return@withContext null
            }
            
            extractor.selectTrack(audioTrackIndex)
            val format = extractor.getTrackFormat(audioTrackIndex)
            
            // Setup Decoder
            val mime = format.getString(MediaFormat.KEY_MIME)!!
            val decoder = MediaCodec.createDecoderByType(mime)
            decoder.configure(format, null, null, 0)
            decoder.start()
            
            // Setup Sonic
            val sampleRate = format.getInteger(MediaFormat.KEY_SAMPLE_RATE)
            val channelCount = format.getInteger(MediaFormat.KEY_CHANNEL_COUNT)
            val sonic = Sonic(sampleRate, channelCount)
            val pitchScale = Math.pow(2.0, pitchShift.toDouble() / 12.0).toFloat()
            sonic.pitch = pitchScale
            sonic.speed = 1.0f
            sonic.rate = 1.0f
            
            // Setup Encoder (AAC)
            val outputAudioFile = File(context.cacheDir, "processed_audio_${System.currentTimeMillis()}.m4a")
            val muxer = MediaMuxer(outputAudioFile.absolutePath, MediaMuxer.OutputFormat.MUXER_OUTPUT_MPEG_4)
            
            val outputFormat = MediaFormat.createAudioFormat(MediaFormat.MIMETYPE_AUDIO_AAC, sampleRate, channelCount)
            outputFormat.setInteger(MediaFormat.KEY_BIT_RATE, 128000)
            outputFormat.setInteger(MediaFormat.KEY_AAC_PROFILE, MediaCodecInfo.CodecProfileLevel.AACObjectLC)
            
            val encoder = MediaCodec.createEncoderByType(MediaFormat.MIMETYPE_AUDIO_AAC)
            encoder.configure(outputFormat, null, null, MediaCodec.CONFIGURE_FLAG_ENCODE)
            encoder.start()
            
            val bufferInfo = MediaCodec.BufferInfo()
            var inputDone = false
            var outputDone = false
            var trackIndex = -1
            var muxerStarted = false
            
            val inputBuffer = ByteBuffer.allocate(64 * 1024)
            val pcmBuffer = ShortArray(1024 * channelCount) // Smaller buffer to avoid overflow
            var totalSamplesWritten = 0L
            var sonicFlushed = false
            var encoderEosSent = false
            
            while (!outputDone && !isCancelled) {
                // 1. Feed decoder
                if (!inputDone) {
                    val inputBufferIndex = decoder.dequeueInputBuffer(10000)
                    if (inputBufferIndex >= 0) {
                        val decoderInputBuffer = decoder.getInputBuffer(inputBufferIndex)
                        val sampleSize = extractor.readSampleData(decoderInputBuffer!!, 0)
                        if (sampleSize < 0) {
                            decoder.queueInputBuffer(inputBufferIndex, 0, 0, 0, MediaCodec.BUFFER_FLAG_END_OF_STREAM)
                            inputDone = true
                            Log.d(TAG, "Audio decoder input EOS")
                        } else {
                            val presentationTimeUs = extractor.sampleTime
                            decoder.queueInputBuffer(inputBufferIndex, 0, sampleSize, presentationTimeUs, 0)
                            extractor.advance()
                        }
                    }
                }
                
                // 2. Read decoded PCM and feed to Sonic
                val outputBufferIndex = decoder.dequeueOutputBuffer(bufferInfo, 10000)
                if (outputBufferIndex >= 0) {
                    val decoderOutputBuffer = decoder.getOutputBuffer(outputBufferIndex)
                    if (bufferInfo.size > 0 && decoderOutputBuffer != null) {
                        decoderOutputBuffer.position(bufferInfo.offset)
                        decoderOutputBuffer.limit(bufferInfo.offset + bufferInfo.size)
                        
                        val bytes = ByteArray(bufferInfo.size)
                        decoderOutputBuffer.get(bytes)
                        
                        val shorts = ShortArray(bytes.size / 2)
                        ByteBuffer.wrap(bytes).order(ByteOrder.LITTLE_ENDIAN).asShortBuffer().get(shorts)
                        
                        sonic.writeShortToStream(shorts, shorts.size / channelCount)
                    }
                    decoder.releaseOutputBuffer(outputBufferIndex, false)
                    
                    if (bufferInfo.flags and MediaCodec.BUFFER_FLAG_END_OF_STREAM != 0) {
                        Log.d(TAG, "Audio decoder output EOS, flushing Sonic")
                        sonic.flushStream()
                        sonicFlushed = true
                    }
                }
                
                // 3. Read from Sonic and encode
                var samplesRead = sonic.readShortFromStream(pcmBuffer, pcmBuffer.size / channelCount)
                while (samplesRead > 0) {
                    val bytes = ByteArray(samplesRead * channelCount * 2)
                    ByteBuffer.wrap(bytes).order(ByteOrder.LITTLE_ENDIAN).asShortBuffer().put(pcmBuffer, 0, samplesRead * channelCount)
                    
                    val encoderInputIndex = encoder.dequeueInputBuffer(10000)
                    if (encoderInputIndex >= 0) {
                        val encoderInputBuffer = encoder.getInputBuffer(encoderInputIndex)
                        encoderInputBuffer!!.clear()
                        // Only write what fits in the buffer
                        val bytesToWrite = minOf(bytes.size, encoderInputBuffer.capacity())
                        encoderInputBuffer.put(bytes, 0, bytesToWrite)
                        val presentationTimeUs = (totalSamplesWritten * 1_000_000L) / sampleRate
                        encoder.queueInputBuffer(encoderInputIndex, 0, bytesToWrite, presentationTimeUs, 0)
                        totalSamplesWritten += bytesToWrite / (2 * channelCount)
                    }
                    samplesRead = sonic.readShortFromStream(pcmBuffer, pcmBuffer.size / channelCount)
                }
                
                // 4. Signal encoder EOS after Sonic is flushed and empty
                if (sonicFlushed && sonic.samplesAvailable() == 0 && !encoderEosSent) {
                    val encoderInputIndex = encoder.dequeueInputBuffer(10000)
                    if (encoderInputIndex >= 0) {
                        encoder.queueInputBuffer(encoderInputIndex, 0, 0, 0, MediaCodec.BUFFER_FLAG_END_OF_STREAM)
                        encoderEosSent = true
                        Log.d(TAG, "Audio encoder EOS sent, totalSamples: $totalSamplesWritten")
                    }
                }
                
                // 5. Drain encoder
                var encoderOutputIndex = encoder.dequeueOutputBuffer(bufferInfo, 10000)
                while (encoderOutputIndex >= 0) {
                    val encoderOutputBuffer = encoder.getOutputBuffer(encoderOutputIndex)
                    if (bufferInfo.flags and MediaCodec.BUFFER_FLAG_CODEC_CONFIG != 0) {
                        bufferInfo.size = 0
                    }
                    if (bufferInfo.size != 0 && muxerStarted) {
                        encoderOutputBuffer!!.position(bufferInfo.offset)
                        encoderOutputBuffer.limit(bufferInfo.offset + bufferInfo.size)
                        muxer.writeSampleData(trackIndex, encoderOutputBuffer, bufferInfo)
                    }
                    encoder.releaseOutputBuffer(encoderOutputIndex, false)
                    if (bufferInfo.flags and MediaCodec.BUFFER_FLAG_END_OF_STREAM != 0) {
                        outputDone = true
                        Log.d(TAG, "Audio encoder output EOS")
                    }
                    encoderOutputIndex = encoder.dequeueOutputBuffer(bufferInfo, 0)
                }
                if (encoderOutputIndex == MediaCodec.INFO_OUTPUT_FORMAT_CHANGED) {
                    trackIndex = muxer.addTrack(encoder.outputFormat)
                    muxer.start()
                    muxerStarted = true
                    Log.d(TAG, "Audio muxer started")
                }
            }
            
            decoder.stop()
            decoder.release()
            encoder.stop()
            encoder.release()
            extractor.release()
            
            if (muxerStarted) {
                 muxer.stop()
            }
            muxer.release()
            
            outputAudioFile
        } catch (e: Exception) {
            Log.e(TAG, "Audio processing failed", e)
            null
        }
    }

    private fun bitmapToYuv420(bitmap: Bitmap, width: Int, height: Int): ByteArray {
        val bitmapWidth = bitmap.width
        val bitmapHeight = bitmap.height
        
        val sourceBitmap: Bitmap
        val needsCleanup: Boolean
        
        if (bitmapWidth == width && bitmapHeight == height) {
            sourceBitmap = bitmap
            needsCleanup = false
        } else {
            // Scale while preserving aspect ratio (letterbox/pillarbox)
            val aspectRatio = bitmapWidth.toFloat() / bitmapHeight.toFloat()
            val targetAspectRatio = width.toFloat() / height.toFloat()
            
            val scaledWidth: Int
            val scaledHeight: Int
            var offsetX = 0
            var offsetY = 0
            
            if (aspectRatio > targetAspectRatio) {
                // Source is wider - fit to width, letterbox top/bottom
                scaledWidth = width
                scaledHeight = (width / aspectRatio).toInt()
                offsetY = (height - scaledHeight) / 2
            } else {
                // Source is taller - fit to height, pillarbox left/right
                scaledHeight = height
                scaledWidth = (height * aspectRatio).toInt()
                offsetX = (width - scaledWidth) / 2
            }
            
            // Scale bitmap
            val scaledBitmap = Bitmap.createScaledBitmap(bitmap, scaledWidth, scaledHeight, true)
            
            // Create target bitmap with black background
            sourceBitmap = Bitmap.createBitmap(width, height, Bitmap.Config.ARGB_8888)
            val canvas = Canvas(sourceBitmap)
            canvas.drawARGB(255, 0, 0, 0) // Black background
            canvas.drawBitmap(scaledBitmap, offsetX.toFloat(), offsetY.toFloat(), null)
            
            scaledBitmap.recycle()
            needsCleanup = true
        }
        
        val yuv = ByteArray(width * height * 3 / 2)
        val argb = IntArray(width * height)
        sourceBitmap.getPixels(argb, 0, width, 0, 0, width, height)
        
        // Clean up scaled bitmap if we created one
        if (needsCleanup) {
            sourceBitmap.recycle()
        }

        val yPlaneSize = width * height
        var yIndex = 0
        var uvIndex = yPlaneSize

        for (j in 0 until height) {
            for (i in 0 until width) {
                val pixel = argb[j * width + i]
                val r = (pixel shr 16) and 0xFF
                val g = (pixel shr 8) and 0xFF
                val b = pixel and 0xFF

                val y = ((66 * r + 129 * g + 25 * b + 128) shr 8) + 16
                yuv[yIndex++] = y.toByte()

                if (j % 2 == 0 && i % 2 == 0) {
                    val u = ((-38 * r - 74 * g + 112 * b + 128) shr 8) + 128
                    val v = ((112 * r - 94 * g - 18 * b + 128) shr 8) + 128
                    yuv[uvIndex++] = u.toByte()
                    yuv[uvIndex++] = v.toByte()
                }
            }
        }
        return yuv
    }
}

