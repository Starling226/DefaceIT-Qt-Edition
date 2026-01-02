package com.shin.defaceit

import android.graphics.Bitmap
import android.graphics.Canvas
import android.graphics.Paint
import android.graphics.Rect
import android.graphics.BitmapShader
import android.graphics.Shader
import android.graphics.Matrix
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext

class VideoProcessor(
    private val blurStrength: Int = 51,
    private val blurType: String = "gaussian"
) {
    private fun blurRegion(bitmap: Bitmap, rect: Rect, padding: Float = 0.2f): Bitmap {
        val width = rect.width()
        val height = rect.height()
        val padX = (width * padding).toInt()
        val padY = (height * padding).toInt()
        
        val x1 = (rect.left - padX).coerceAtLeast(0)
        val y1 = (rect.top - padY).coerceAtLeast(0)
        val x2 = (rect.right + padX).coerceAtMost(bitmap.width)
        val y2 = (rect.bottom + padY).coerceAtMost(bitmap.height)
        
        if (x2 <= x1 || y2 <= y1) return bitmap
        
        // Calculate region dimensions and ensure they don't exceed bitmap bounds
        val roiWidth = (x2 - x1).coerceAtMost(bitmap.width - x1).coerceAtLeast(1)
        val roiHeight = (y2 - y1).coerceAtMost(bitmap.height - y1).coerceAtLeast(1)
        
        // Final safety check: ensure x1 + roiWidth <= bitmap.width and y1 + roiHeight <= bitmap.height
        if (x1 + roiWidth > bitmap.width || y1 + roiHeight > bitmap.height) {
            return bitmap
        }
        
        val roi = Bitmap.createBitmap(bitmap, x1, y1, roiWidth, roiHeight)
        val blurred = when (blurType) {
            "pixelate" -> pixelate(roi)
            else -> simpleBlur(roi, blurStrength)
        }
        
        val canvas = Canvas(bitmap)
        canvas.drawBitmap(blurred, x1.toFloat(), y1.toFloat(), null)
        roi.recycle()
        blurred.recycle()
        
        return bitmap
    }
    
    private fun simpleBlur(bitmap: Bitmap, radius: Int): Bitmap {
        val scale = 1.0f / (radius / 3.0f + 1.0f)
        val scaledWidth = (bitmap.width * scale).toInt().coerceAtLeast(1)
        val scaledHeight = (bitmap.height * scale).toInt().coerceAtLeast(1)
        
        val scaled = Bitmap.createScaledBitmap(bitmap, scaledWidth, scaledHeight, true)
        val result = Bitmap.createScaledBitmap(scaled, bitmap.width, bitmap.height, false)
        
        if (scaled != result) {
            scaled.recycle()
        }
        return result
    }
    
    private fun pixelate(bitmap: Bitmap): Bitmap {
        val small = Bitmap.createScaledBitmap(bitmap, (bitmap.width / 10).coerceAtLeast(1), (bitmap.height / 10).coerceAtLeast(1), true)
        return Bitmap.createScaledBitmap(small, bitmap.width, bitmap.height, false)
    }

    private data class TrackedFace(
        var id: Int,
        var rect: Rect,
        var velocityX: Float = 0f,
        var velocityY: Float = 0f,
        var lostFrames: Int = 0
    )

    private class FaceTracker {
        private val tracks = mutableListOf<TrackedFace>()
        private var nextId = 0
        private val MAX_LOST_FRAMES = 15
        private val IOU_THRESHOLD = 0.3f
        private val SMOOTHING_FACTOR = 0.6f
        private val MAX_FACE_RATIO = 0.4f

        fun update(detectedFaces: List<Rect>): List<Rect> {
            tracks.forEach { face ->
                face.rect = Rect(
                    (face.rect.left + face.velocityX).toInt(),
                    (face.rect.top + face.velocityY).toInt(),
                    (face.rect.right + face.velocityX).toInt(),
                    (face.rect.bottom + face.velocityY).toInt()
                )
                face.lostFrames++
            }

            val usedDetections = BooleanArray(detectedFaces.size)
            tracks.forEach { track ->
                var bestIoU = 0f
                var bestIdx = -1

                for (i in detectedFaces.indices) {
                    if (usedDetections[i]) continue
                    val iou = calculateIoU(track.rect, detectedFaces[i])
                    if (iou > bestIoU && iou > IOU_THRESHOLD) {
                        bestIoU = iou
                        bestIdx = i
                    }
                }

                if (bestIdx != -1) {
                    val detected = detectedFaces[bestIdx]
                    val dx = detected.centerX() - track.rect.centerX()
                    val dy = detected.centerY() - track.rect.centerY()
                    track.velocityX = track.velocityX * SMOOTHING_FACTOR + dx * (1 - SMOOTHING_FACTOR)
                    track.velocityY = track.velocityY * SMOOTHING_FACTOR + dy * (1 - SMOOTHING_FACTOR)

                    track.rect = Rect(
                        (track.rect.left * SMOOTHING_FACTOR + detected.left * (1 - SMOOTHING_FACTOR)).toInt(),
                        (track.rect.top * SMOOTHING_FACTOR + detected.top * (1 - SMOOTHING_FACTOR)).toInt(),
                        (track.rect.right * SMOOTHING_FACTOR + detected.right * (1 - SMOOTHING_FACTOR)).toInt(),
                        (track.rect.bottom * SMOOTHING_FACTOR + detected.bottom * (1 - SMOOTHING_FACTOR)).toInt()
                    )
                    track.lostFrames = 0
                    usedDetections[bestIdx] = true
                }
            }

            for (i in detectedFaces.indices) {
                if (!usedDetections[i]) {
                    tracks.add(TrackedFace(nextId++, detectedFaces[i]))
                }
            }

            tracks.removeAll { it.lostFrames > MAX_LOST_FRAMES }

            return tracks.mapNotNull { track ->
                val rect = inflateRect(track.rect)
                if (rect.width() > 0 && rect.height() > 0) rect else null
            }
        }

        private fun inflateRect(rect: Rect): Rect {
            val width = rect.width()
            val height = rect.height()
            val dw = (width * 0.10f).toInt()
            val dh = (height * 0.10f).toInt()
            return Rect(
                rect.left - dw,
                rect.top - dh,
                rect.right + dw,
                rect.bottom + dh
            )
        }

        private fun calculateIoU(r1: Rect, r2: Rect): Float {
            val intersection = Rect()
            if (!intersection.setIntersect(r1, r2)) return 0f
            val union = r1.width() * r1.height() + r2.width() * r2.height() - intersection.width() * intersection.height()
            return if (union > 0) intersection.width() * intersection.height().toFloat() / union else 0f
        }
    }

    private val faceTracker = FaceTracker()

    suspend fun processFrame(bitmap: Bitmap, faceRects: List<Rect>): Bitmap {
        return withContext(Dispatchers.Default) {
            var processed = bitmap.copy(bitmap.config ?: Bitmap.Config.ARGB_8888, true)
            
            val maxFaceWidth = (bitmap.width * 0.35f).toInt()
            val maxFaceHeight = (bitmap.height * 0.35f).toInt()
            val validFaces = faceRects.filter { rect ->
                rect.width() < maxFaceWidth && rect.height() < maxFaceHeight && rect.width() > 0 && rect.height() > 0
            }
            
            val stableFaces = faceTracker.update(validFaces)
            
            stableFaces.forEach { rect ->
                val clampedRect = Rect(
                    maxOf(0, rect.left),
                    maxOf(0, rect.top),
                    minOf(bitmap.width, rect.right),
                    minOf(bitmap.height, rect.bottom)
                )
                if (clampedRect.width() > 0 && clampedRect.height() > 0) {
                    processed = blurRegion(processed, clampedRect)
                }
            }
            processed
        }
    }
}
