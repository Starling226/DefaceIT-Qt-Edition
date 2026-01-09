import cv2
import numpy as np
from ultralytics import YOLO
from pathlib import Path
from typing import List, Tuple, Optional
import time
import librosa
import soundfile as sf
import subprocess
import os
import shutil
from PyQt5.QtCore import Qt, QTimer, pyqtSignal, QObject, QProcess, QProcessEnvironment

class VideoBlurrer(QObject):
    """Fully asynchronous video blurring worker using QProcess signals"""

    progress = pyqtSignal(str)      # status messages
    finished = pyqtSignal(int)      # exit code (0 = success)
    error = pyqtSignal(str)         # error messages

    def __init__(
        self,
        face_model_path: Optional[str] = None,
        license_plate_model_path: Optional[str] = None,
        device: str = "cpu",
        blur_strength: int = 51,
        blur_type: str = "gaussian",
        confidence: float = 0.15,
        detect_faces: bool = True,
        detect_license_plates: bool = True,
        progress_callback=None,
        pitch_shift: float = 0.0,
        reencode_to_h264: bool = True,
        input_file: str = "",
        output_file: str = "",
        ffmpeg_path: str = "",
        crf_value: int = 16
    ):
        super().__init__()
        self.blur_strength = blur_strength if blur_strength % 2 == 1 else blur_strength + 1
        self.blur_type = blur_type
        self.confidence = confidence
        self.detect_faces = detect_faces
        self.detect_license_plates = detect_license_plates
        self.pitch_shift = pitch_shift
        self.reencode_to_h264 = reencode_to_h264
        self.face_padding = 0.2
        self.is_cancelled = False
        self.input_path = input_file
        self.output_path = output_file
        self.ffmpeg_path = ffmpeg_path
        self.crf_value = crf_value
        self.progress_callback = progress_callback  # optional direct callback

        # Async state
        self.current_step = "init"
        self.temp_files = []  # cleanup list
        self.cap = None
        self.out = None
        self.process = None  # current QProcess
        self.temp_audio = None
        self.shifted_audio = None
        self.reencoded_video = None

        self.frame_queue = []           # list of bytes
        self._writing_started = False   # flag to start writer only once
        self._write_timer_active = False

        # Device auto-detection
        '''
        if device == "auto":
            import torch
            if torch.cuda.is_available():
                device = "cuda"
            elif hasattr(torch.backends, 'mps') and torch.backends.mps.is_available():
                device = "mps"
            else:
                device = "cpu"
        '''

        self.device = device

        # Load models
        self.models = []
        if self.detect_faces:
            face_model = YOLO(face_model_path or "yolo11n.pt")
            face_model.to(self.device)
            self.models.append(("face", face_model))
        if self.detect_license_plates:
            lp_model = YOLO(license_plate_model_path or "yolo11n.pt")
            lp_model.to(self.device)
            self.models.append(("license_plate", lp_model))

    def start(self):
        """Public method to start the async processing"""
        if self.is_cancelled:
            self.finished.emit(0)
            return
        self.current_step = "open_video"
        self._open_video()

    def _open_video(self):
        self.progress.emit("Opening video...")
        if self.progress_callback:
            self.progress_callback(0, 0, "Opening video...")

        try:
            self.cap = cv2.VideoCapture(self.input_path)
            if not self.cap.isOpened():
                raise Exception(f"Could not open video: {self.input_path}")

            fps = int(self.cap.get(cv2.CAP_PROP_FPS))
            width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            self.total_frames = int(self.cap.get(cv2.CAP_PROP_FRAME_COUNT))

            self.progress.emit(f"Processing {self.total_frames} frames...")
            if self.progress_callback:
                self.progress_callback(0, 0, f"Processing {self.total_frames} frames...")


            self.current_step = "process_frames"
            self._start_frame_processing_pipe(fps, width, height)

        except Exception as e:
            self.error.emit(f"Open video error: {str(e)}")
            self.finished.emit(1)

    def blur_region(self, frame: np.ndarray, bbox: Tuple[int, int, int, int], padding: float = 0.0) -> np.ndarray:
        x1, y1, x2, y2 = bbox

        if padding > 0:
            width = x2 - x1
            height = y2 - y1
            pad_x = int(width * padding)
            pad_y = int(height * padding)
            x1 = max(0, x1 - pad_x)
            y1 = max(0, y1 - pad_y)
            x2 = min(frame.shape[1], x2 + pad_x)
            y2 = min(frame.shape[0], y2 + pad_y)

        x1, y1 = max(0, x1), max(0, y1)
        x2, y2 = min(frame.shape[1], x2), min(frame.shape[0], y2)

        if x2 <= x1 or y2 <= y1:
            return frame

        roi = frame[y1:y2, x1:x2]

        if self.blur_type == "gaussian":
            blurred_roi = cv2.GaussianBlur(roi, (self.blur_strength, self.blur_strength), 0)
        elif self.blur_type == "pixelate":
            h, w = roi.shape[:2]
            small = cv2.resize(roi, (max(1, w // 10), max(1, h // 10)), interpolation=cv2.INTER_LINEAR)
            blurred_roi = cv2.resize(small, (w, h), interpolation=cv2.INTER_NEAREST)
        else:
            blurred_roi = cv2.GaussianBlur(roi, (self.blur_strength, self.blur_strength), 0)

        frame[y1:y2, x1:x2] = blurred_roi
        return frame

    def process_frame(self, frame: np.ndarray) -> np.ndarray:
        for model_type, model in self.models:
            results = model(frame, conf=self.confidence, iou=0.5, verbose=False)

            for result in results:
                boxes = result.boxes
                if len(boxes) == 0:
                    continue

                for box in boxes:
                    x1, y1, x2, y2 = box.xyxy[0].cpu().numpy().astype(int)
                    cls = int(box.cls[0].cpu().numpy())

                    if model_type == "face":
                        if cls == 0:
                            height = y2 - y1
                            width = x2 - x1
                            face_y1 = y1
                            face_y2 = y1 + int(height * 0.5)
                            face_x1 = max(0, x1 - int(width * 0.1))
                            face_x2 = min(frame.shape[1], x2 + int(width * 0.1))
                            self.blur_region(frame, (face_x1, face_y1, face_x2, face_y2), padding=self.face_padding)
                        else:
                            self.blur_region(frame, (x1, y1, x2, y2), padding=self.face_padding)

                    elif model_type == "license_plate":
                        self.blur_region(frame, (x1, y1, x2, y2), padding=0.1)

        return frame

    def _start_frame_processing_pipe(self, fps, width, height):
        '''
        if self.device == "cpu" or self.device == "mps":
            cmd = [
                self.ffmpeg_path,
                '-y',
                '-f', 'rawvideo',
                '-vcodec', 'rawvideo',
                '-pix_fmt', 'bgr24',
                '-s', f"{width}x{height}",
                '-r', str(fps),
                '-i', '-',
                '-c:v', 'libx264',
                '-preset', 'medium',
                '-crf', str(self.crf_value),
                '-threads', '0',
                '-pix_fmt', 'yuv420p',
                '-movflags', '+faststart',
                self.output_path
            ]

        else: # GPU
            self.crf_value = min(self.crf_value + 3, 28)
            cmd = [
                self.ffmpeg_path,
                '-y',
                '-f', 'rawvideo',
                '-vcodec', 'rawvideo',
                '-pix_fmt', 'bgr24',
                '-s', f"{width}x{height}",
                '-r', str(fps),
                '-i', '-',
                '-c:v', 'h264_nvenc',             # NVIDIA hardware encoder
                '-preset', 'p7',                  # p7 = highest quality (slowest), p1 = fastest
                '-rc', 'vbr',                     # Variable bitrate (recommended for quality)
                '-cq', str(self.crf_value),       # Constant quality (like CRF, 19–23 is excellent)
                '-b:v', '3000k',                     # Target bitrate (5 Mbps) - adjust for resolution
                '-maxrate', '6000k',                # Max bitrate (optional, prevents spikes)
                '-bufsize', '12000k',                # Buffer size (match maxrate)
                '-pix_fmt', 'yuv420p',
                '-movflags', '+faststart',
                '-threads', '0',                  # NVENC ignores threads anyway
                self.output_path
            ]
        '''
        cmd = [
            self.ffmpeg_path,
            '-y',
            '-f', 'rawvideo',
            '-vcodec', 'rawvideo',
            '-pix_fmt', 'bgr24',
            '-s', f"{width}x{height}",
            '-r', str(fps),
            '-i', '-',
            '-c:v', 'libx264',
            '-preset', 'medium',
            '-crf', str(self.crf_value),
            '-threads', '0',
            '-pix_fmt', 'yuv420p',
            '-movflags', '+faststart',
            self.output_path
        ]

        self.process = QProcess()
        self.process.setProcessChannelMode(QProcess.MergedChannels)
        self.process.readyReadStandardOutput.connect(
            lambda proc=self.process: self._handle_output(proc)
        )         
#        self.process.readyReadStandardOutput.connect(self._handle_output)
        self.process.finished.connect(self._on_encoding_finished)
        self.process.errorOccurred.connect(self._on_process_error)

        self.process.start(cmd[0], cmd[1:])

        self.frame_count = 0
        self.start_time = time.time()
        QTimer.singleShot(0, self._process_next_frame)

    def _process_next_frame(self):
        if self.is_cancelled:
            self._cleanup()
            self.finished.emit(0)
            return

        ret, frame = self.cap.read()
        if not ret:
            self.cap.release()
#            self.process.close()
            self.process.closeWriteChannel()  # Signals EOF to FFmpeg
            self.progress.emit("All frames processed. Waiting for encoding...")
            if self.progress_callback:
                self.progress_callback(0, 0, "All frames processed. Waiting for encoding...")

            return

        processed_frame = self.process_frame(frame.copy())

        # Step 1-3: Collect frames in queue (add to buffer instead of direct write)
        self.frame_queue.append(processed_frame.tobytes())  # ← Add to queue

        self.frame_count += 1
        if self.frame_count % 5 == 0:
            elapsed = time.time() - self.start_time
            fps_actual = self.frame_count / elapsed if elapsed > 0 else 0
            progress = (self.frame_count / self.total_frames) * 100 if self.total_frames > 0 else 0
            self.progress.emit(f"Processing frame {self.frame_count}/{self.total_frames} ({fps_actual:.1f} FPS)")
            if self.progress_callback:
                self.progress_callback(progress, fps_actual, f"Processing frame {self.frame_count}/{self.total_frames}")        

        # Step 4: Start writing queued frames in batches (only once, on first call)
#        if not hasattr(self, '_writing_started') or not self._writing_started:
        if not self._write_timer_active:
            self._writing_started = True
            QTimer.singleShot(20, self._write_batch)  # Start batch writer

        # Schedule next frame read
        QTimer.singleShot(0, self._process_next_frame)

    def _write_batch(self):
        if self.is_cancelled or self.process.state() != QProcess.Running:
            self._write_timer_active = False
            return

        batch_size = 5  # Write 5 frames at a time (adjust 5-20)
        batch = self.frame_queue[:batch_size]
        self.frame_queue = self.frame_queue[batch_size:]

        for frame_bytes in batch:
            try:
                self.process.write(frame_bytes)
            except Exception as e:
                self.error.emit(f"Pipe write error: {str(e)}")
                self.finished.emit(1)
                return

        # If more frames, schedule next batch
        if self.frame_queue:
            QTimer.singleShot(50, self._write_batch)
        else:
            self._write_timer_active = False

    def _on_encoding_finished(self, exit_code, exit_status):
        if self.is_cancelled:
            self._cleanup()
            self.finished.emit(0)
            return

        if exit_code != 0:
            self.error.emit(f"Encoding failed (code {exit_code})")
            self.finished.emit(exit_code)
            return

        self.progress.emit("Encoding complete. Merging audio...")
        if self.progress_callback:
            self.progress_callback(0, 0, "Encoding complete. Merging audio...")

        self.current_step = "merge_audio"
        self._merge_audio_async()

    def _check_ffmpeg(self) -> bool:
        """Non-blocking check (but we can call it sync since it's fast)"""
        try:
            result = subprocess.run([self.ffmpeg_path, "-version"], capture_output=True, text=True, check=False)
            return result.returncode == 0
        except:
            return False

    def _merge_audio_async(self):

        if self.process:
            self.process.finished.disconnect() # Disconnect old signals
            self.process.deleteLater()

#        print("_merge_audio_async")
        temp_audio = str(Path(self.output_path).with_suffix('.temp_audio.wav'))
        self.temp_files.append(temp_audio)

        extract_cmd = [
            self.ffmpeg_path,
            '-i', self.input_path,
            '-vn', '-acodec', 'pcm_s16le',
            '-y', temp_audio
        ]
        print(extract_cmd)

        extract_process = QProcess()
        extract_process.setProcessChannelMode(QProcess.MergedChannels)
        extract_process.readyReadStandardOutput.connect(
            lambda proc=extract_process: self._handle_output(proc)
        )
        extract_process.finished.connect(lambda code, status: self._on_audio_extract_finished(code, temp_audio))
        extract_process.errorOccurred.connect(self._on_process_error)
        extract_process.start(extract_cmd[0], extract_cmd[1:])

    def _on_audio_extract_finished(self, exit_code, temp_audio):
#        print("_on_audio_extract_finished")
        
        if self.is_cancelled:
            self._cleanup()
            self.finished.emit(0)
            return
#        print("A1 ",exit_code)
        if exit_code != 0:
            self.error.emit(f"Audio extraction failed (code {exit_code})")
            self.finished.emit(exit_code)
            return
#        print("A2")
        if abs(self.pitch_shift) >= 0.1:
            shifted_audio = str(Path(temp_audio).with_suffix('.shifted.wav'))
            self.temp_files.append(shifted_audio)
            self.current_step = "shift_audio"
#            print("A3")
            QTimer.singleShot(100, lambda: self._shift_audio_async(temp_audio, shifted_audio))
#            self._shift_audio_async(temp_audio, shifted_audio)
        else:
            self.current_step = "final_merge"
            QTimer.singleShot(100, lambda: self._final_merge(temp_audio, temp_audio))
#            self._final_merge(temp_audio, temp_audio)

    def _shift_audio_async(self, input_audio, output_audio):   
#        print("_shift_audio_async")
        pitch_ratio = 2 ** (self.pitch_shift / 12.0)

        cmd = [
            self.ffmpeg_path,
            '-i', input_audio,
            '-af', f'rubberband=pitch={pitch_ratio}',
            '-y', output_audio
        ]

        shift_process = QProcess()
        shift_process.setProcessChannelMode(QProcess.MergedChannels)
        shift_process.readyReadStandardOutput.connect(
            lambda proc=shift_process: self._handle_output(proc)
        )        

        shift_process.finished.connect(lambda code, status: self._on_shift_finished(code, output_audio))
        shift_process.errorOccurred.connect(self._on_process_error)
        shift_process.start(cmd[0], cmd[1:])

    def _on_shift_finished(self, exit_code, output_audio):
        if self.is_cancelled:
            self._cleanup()
            self.finished.emit(0)
            return

        if exit_code != 0:            
            # Fallback to asetrate (sync fallback)
            print("Rubberband pitch shift failed. Falling back to extraction + librosa...")
            self.progress.emit("Rubberband pitch shift failed. Falling back to extraction + librosa...")
            self._extract_audio_for_fallback(output_audio)
        else:
            self.current_step = "final_merge"
#            self._final_merge(output_audio, output_audio)
            QTimer.singleShot(50, lambda: self._final_merge(output_audio, output_audio))

    def _extract_audio_for_fallback(self, final_shifted_path):
        """Extract raw audio when rubberband failed, then apply librosa pitch shift"""
        self.progress.emit("Extracting raw audio for fallback pitch shift...")
        self.temp_audio_path = str(Path(self.output_path).with_suffix('.fallback_raw_.wav'))
        self.temp_files.append(self.temp_audio_path)
        self.shifted_audio_path = final_shifted_path  # reuse the intended output path

        extract_cmd = [
            self.ffmpeg_path,
            '-i', self.input_path,
            '-acodec', 'pcm_s16le', # Raw 16-bit little-endian PCM (compatible with librosa)
            '-vn',                  # No video
            '-ac', '2',
            '-y',
            self.temp_audio_path
        ]

        audio_falback_process = QProcess()
        audio_falback_process.setProcessChannelMode(QProcess.MergedChannels)
        audio_falback_process.readyReadStandardOutput.connect(
            lambda proc=audio_falback_process: self._handle_output(proc)
        )          
        audio_falback_process.finished.connect(self._on_fallback_extract_finished)
        audio_falback_process.errorOccurred.connect(self._on_process_error)
        started = audio_falback_process.start(extract_cmd[0], extract_cmd[1:])

#        if not started:
#            self.error.emit("Failed to start FFmpeg for fallback extraction")
#            self._cleanup()
#            self.finished.emit(1)

    def _on_fallback_extract_finished(self, exit_code, exit_status):
        if self.is_cancelled:
            self._cleanup()
            self.finished.emit(0)
            return

        if exit_code != 0 or not os.path.exists(self.temp_audio_path):
            self.error.emit(f"Fallback audio extraction failed (code {exit_code})")
            self._cleanup()
            self.finished.emit(1)
            return

        self.progress.emit("Applying pitch shift using librosa (fallback)...")
        pitch_ratio = 2 ** (self.pitch_shift / 12.0)
        try:
            y, sr = librosa.load(self.temp_audio_path, sr=None)
            y_shifted = librosa.effects.pitch_shift(y, sr=sr, n_steps=self.pitch_shift)
            sf.write(self.shifted_audio_path, y_shifted, sr)
            self.progress.emit("Fallback pitch shift complete.")
            self.current_step = "final_merge"
#            self._final_merge(self.shifted_audio_path, self.shifted_audio_path)
            QTimer.singleShot(50, lambda: self._final_merge(self.shifted_audio_path, self.shifted_audio_path))
        except Exception as e:
            self.error.emit(f"Librosa fallback failed: {str(e)}")
            self._cleanup()
            self.finished.emit(1)

    def _final_merge(self, audio_file, temp_audio):
        final_output = str(Path(self.output_path).with_suffix('.final.mp4'))
        self.temp_files.append(final_output)

        merge_cmd = [
            self.ffmpeg_path,
            '-i', self.output_path,
            '-i', audio_file,
            '-c:v', 'copy',
            '-c:a', 'aac',
            '-map', '0:v:0',
            '-map', '1:a:0',
            '-shortest',
            '-y',
            final_output
        ]

        final_merge_process = QProcess()
        final_merge_process.finished.connect(lambda code, status: self._on_final_merge_finished(code, final_output, temp_audio))
        final_merge_process.errorOccurred.connect(self._on_process_error)
        final_merge_process.readyReadStandardOutput.connect(
            lambda proc=final_merge_process: self._handle_output(proc)
        )          
        final_merge_process.start(merge_cmd[0], merge_cmd[1:])

    def _on_final_merge_finished(self, exit_code, final_output, temp_audio):
        if self.is_cancelled:
            self._cleanup()
            self.finished.emit(0)
            return

        if exit_code == 0:
            os.replace(final_output, self.output_path)
            self.progress.emit("Processing complete!")
            if self.progress_callback:
                self.progress_callback(0, 0, "Processing complete!")

            self.finished.emit(0)
        else:
            self.error.emit(f"Audio merge failed (code {exit_code})")
            self.finished.emit(exit_code)

        self._cleanup()

    def _on_process_error(self, error):
        if error == 0 or error == 1:  # Ignore common false positives
            return
        self.error.emit(f"FFmpeg process error: {error}")
        self.finished.emit(1)

    def cancel(self):
        """Cancel the entire processing pipeline safely"""
        if self.is_cancelled:
            return  # already cancelled

        self.is_cancelled = True
#        print("DEBUG: Cancel requested - terminating current process")

        # Terminate any active QProcess
        if self.process and self.process.state() == QProcess.Running:
            self.process.terminate()  # polite terminate
            # Optional: give it 2 seconds to terminate gracefully
            QTimer.singleShot(2000, self._force_kill_process)

        # Close any open write channel (for piped encoding)
        if self.process and self.process.state() != QProcess.NotRunning:
            self.process.closeWriteChannel()

        # Emit feedback
        self.progress.emit("Processing cancelled")
        if self.progress_callback:
            self.progress_callback(0, 0, "Processing cancelled")

        self.finished.emit(0)  # success exit code for cancel

    def _force_kill_process(self):
        """Force kill if terminate() didn't work"""
        if self.process and self.process.state() == QProcess.Running:
#            print("DEBUG: Force killing FFmpeg process")
            self.process.kill()

    def _cleanup(self):
        for f in self.temp_files:
            if os.path.exists(f):
                try:
                    os.remove(f)
                except:
                    pass
        self.temp_files = []
        if self.cap:
            self.cap.release()

    def _handle_output(self, process: QProcess):
        """Handle output from a specific QProcess instance"""
        data = process.readAllStandardOutput().data().decode(errors='ignore').strip()
        if data:
            self.progress.emit(data)

    def _handle_output2(self):
        """Handle QProcess readyReadStandardOutput signal for progress/output"""
        if self.process:
            data = self.process.readAllStandardOutput().data().decode().strip()
            if data:
                self.progress.emit(data)            