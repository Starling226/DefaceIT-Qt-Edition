package com.shin.defaceit

import android.graphics.Bitmap
import android.graphics.Rect
import com.google.mlkit.vision.common.InputImage
import com.google.mlkit.vision.face.FaceDetection
import com.google.mlkit.vision.face.FaceDetectorOptions
import kotlinx.coroutines.tasks.await

class FaceDetector(private val minConfidence: Float = 0.05f) {
    private val options = FaceDetectorOptions.Builder()
        .setPerformanceMode(FaceDetectorOptions.PERFORMANCE_MODE_ACCURATE)
        .enableTracking()
        .setLandmarkMode(FaceDetectorOptions.LANDMARK_MODE_NONE)
        .setClassificationMode(FaceDetectorOptions.CLASSIFICATION_MODE_NONE)
        .setMinFaceSize(minConfidence)
        .build()

    private val detector = FaceDetection.getClient(options)

    suspend fun detectFaces(bitmap: Bitmap, rotationDegrees: Int): List<Rect> {
        val image = InputImage.fromBitmap(bitmap, rotationDegrees)
        val faces = detector.process(image).await()
        return faces.map { face ->
            face.boundingBox
        }
    }

    fun close() {
        detector.close()
    }
}

