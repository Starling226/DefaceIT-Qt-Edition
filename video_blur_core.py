import cv2
import numpy as np
from ultralytics import YOLO
from pathlib import Path
from typing import List, Tuple, Optional
import time
import platform
import librosa
import soundfile as sf
import subprocess
import os
import shutil
from PyQt5.QtCore import Qt, QTimer, pyqtSignal, QObject,  QProcess

class VideoBlurrer(QObject):
    """Asynchronous video blurring worker using OpenCV VideoWriter"""
    progress = pyqtSignal(str)       # status messages
    finished = pyqtSignal(int)       # exit code (0 = success)
    error = pyqtSignal(str)          # error messages

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
        crf_value: int = 22
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
        self.progress_callback = progress_callback
        self.current_step = "init"
        self.temp_files = []
        self.cap = None
        self.writer = None
        self.temp_audio = None
        self.shifted_audio = None
        self.frame_count = 0
        self.start_time = 0.0
        self.total_frames = 0
        self.fps = 0.0
        self.width = 0
        self.height = 0
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
            self.fps = float(self.cap.get(cv2.CAP_PROP_FPS))
            self.width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            self.height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            self.total_frames = int(self.cap.get(cv2.CAP_PROP_FRAME_COUNT))
            self.progress.emit(f"Processing {self.total_frames} frames at {self.fps:.1f} FPS...")
            if self.progress_callback:
                self.progress_callback(0, 0, f"Processing {self.total_frames} frames...")
            self.current_step = "process_frames"
            self._start_frame_processing()
        except Exception as e:
            self.error.emit(f"Open video error: {str(e)}")
            self.finished.emit(1)

    def _start_frame_processing(self):
        """Initialize OpenCV VideoWriter for direct MP4 writing"""
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')  # Safe fallback codec
        self.writer = cv2.VideoWriter(
            self.output_path,
            fourcc,
            self.fps,
            (self.width, self.height)
        )
        if not self.writer.isOpened():
            self.error.emit("Failed to open OpenCV VideoWriter! Check codec support or file permissions.")
            self.finished.emit(1)
            return

        self.progress.emit(f"Writing processed frames directly to MP4: {self.output_path}")
        self.frame_count = 0
        self.start_time = time.time()
        QTimer.singleShot(0, self._process_next_frame)

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

    def _process_next_frame(self):
        if self.is_cancelled:
            self._cleanup()
            self.finished.emit(0)
            return

        ret, frame = self.cap.read()
        if not ret:
            self.cap.release()
            if hasattr(self, 'writer') and self.writer:
                self.writer.release()
                self.progress.emit("All frames written to MP4.")
                if self.progress_callback:
                    self.progress_callback(100, 0, "All frames processed.")
            QTimer.singleShot(100, self._finalize_video)
            return

        processed_frame = self.process_frame(frame.copy())
        self.writer.write(processed_frame)

        self.frame_count += 1

        if self.frame_count % 10 == 0:
            elapsed = time.time() - self.start_time
            fps_actual = self.frame_count / elapsed if elapsed > 0 else 0
            progress = (self.frame_count / self.total_frames) * 100
            self.progress.emit(f"Processed & written frame {self.frame_count}/{self.total_frames} ({fps_actual:.1f} FPS)")
            if self.progress_callback:
                self.progress_callback(progress, fps_actual, f"Frame {self.frame_count}/{self.total_frames}")

        QTimer.singleShot(0, self._process_next_frame)

    def _finalize_video(self):
        if not self.reencode_to_h264:
            self.progress.emit("Processing complete! (No final re-encode)")
            self.finished.emit(0)
            return

        self.progress.emit("Finalizing video with FFmpeg (H.264 optimization)...")

        temp_mp4 = self.output_path
        path = Path(temp_mp4)
        final_mp4 = str(path.with_name(f"{path.stem}_final{path.suffix}"))
        self.temp_files.append(final_mp4)

        reencode_cmd = [
            self.ffmpeg_path,
            '-i', temp_mp4,
            '-c:v', 'libx264',
            '-preset', 'medium',
            '-crf', str(self.crf_value),
            '-pix_fmt', 'yuv420p',
            '-movflags', '+faststart',
            '-y',
            final_mp4
        ]

        if platform.system().lower() == 'windows':
            # Windows: use subprocess.run (more stable)

            try:
                result = subprocess.run(
                    reencode_cmd,
                    capture_output=True,
                    text=True,
                    check=True,
                    creationflags=subprocess.CREATE_NO_WINDOW
                )                

                self.progress.emit("FFmpeg finalization complete!")
                # Replace original with optimized version
                os.replace(final_mp4, self.output_path)
                self.current_step = "merge_audio"
                self._merge_audio_async()
#                self.finished.emit(0)
            except subprocess.CalledProcessError as e:
                self.error.emit(f"FFmpeg finalization failed (code {e.returncode})\n{e.stderr}")
                self.finished.emit(1)
            except Exception as e:
                self.error.emit(f"Unexpected error during finalization: {str(e)}")
                self.finished.emit(1)                
        else:
            # Linux/macOS: use QProcess
            reencode_process = QProcess(self)
            reencode_process.setProcessChannelMode(QProcess.MergedChannels)
            reencode_process.readyReadStandardOutput.connect(
                lambda proc=reencode_process: self._handle_output(proc)
            )
            reencode_process.finished.connect(lambda code, status: self._on_finalize_finished(code, final_mp4))
            reencode_process.errorOccurred.connect(self._on_process_error)
            self.current_step = "merge_audio"
            reencode_process.start(reencode_cmd[0], reencode_cmd[1:])        

    def _on_finalize_finished(self, exit_code, final_mp4):
        if exit_code == 0:
            self.progress.emit("FFmpeg finalization complete!")
            os.replace(final_mp4, self.output_path)
            self._merge_audio_async()
#            self.finished.emit(0)
        else:
            self.error.emit(f"FFmpeg finalization failed (code {exit_code})")
            self.finished.emit(1)

    def _merge_audio_async(self):

        temp_audio = str(Path(self.output_path).with_suffix('.temp_audio.wav'))
        self.temp_files.append(temp_audio)

        extract_cmd = [
            self.ffmpeg_path,
            '-i', self.input_path,
            '-vn', '-acodec', 'pcm_s16le',
            '-y', temp_audio
        ]
        print(extract_cmd)

        extract_process = QProcess(self)
        extract_process.setProcessChannelMode(QProcess.MergedChannels)
        extract_process.readyReadStandardOutput.connect(
            lambda proc=extract_process: self._handle_output(proc)
        )
        extract_process.finished.connect(lambda code, status: self._on_audio_extract_finished(code, temp_audio))
        extract_process.errorOccurred.connect(self._on_process_error)
        extract_process.start(extract_cmd[0], extract_cmd[1:])

    def _on_audio_extract_finished(self, exit_code, temp_audio):
        
        if self.is_cancelled:
            self._cleanup()
            self.finished.emit(0)
            return

        if exit_code != 0:
            self.error.emit(f"Audio extraction failed (code {exit_code})")
            self.finished.emit(exit_code)
            return

        if abs(self.pitch_shift) >= 0.1:
            shifted_audio = str(Path(temp_audio).with_suffix('.shifted.wav'))
            self.temp_files.append(shifted_audio)
            self.current_step = "shift_audio"

            QTimer.singleShot(100, lambda: self._shift_audio_async(temp_audio, shifted_audio))
        else:
            self.current_step = "final_merge"
            QTimer.singleShot(100, lambda: self._final_merge(temp_audio, temp_audio))

    def _shift_audio_async(self, input_audio, output_audio):   

        pitch_ratio = 2 ** (self.pitch_shift / 12.0)

        cmd = [
            self.ffmpeg_path,
            '-i', input_audio,
            '-af', f'rubberband=pitch={pitch_ratio}',
            '-y', output_audio
        ]

        shift_process = QProcess(self)
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

        audio_falback_process = QProcess(self)
        audio_falback_process.setProcessChannelMode(QProcess.MergedChannels)
        audio_falback_process.readyReadStandardOutput.connect(
            lambda proc=audio_falback_process: self._handle_output(proc)
        )          
        audio_falback_process.finished.connect(self._on_fallback_extract_finished)
        audio_falback_process.errorOccurred.connect(self._on_process_error)
        started = audio_falback_process.start(extract_cmd[0], extract_cmd[1:])

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

        final_merge_process = QProcess(self)
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

    def _cleanup(self):
        if hasattr(self, 'writer') and self.writer:
            self.writer.release()
        for f in self.temp_files:
            if os.path.exists(f):
                try:
                    if os.path.isdir(f):
                        shutil.rmtree(f)
                    else:
                        os.remove(f)
                except:
                    pass

        self.temp_files.clear()
        self.temp_files = []
        if self.cap:
            self.cap.release()

    def cancel(self):
        """Cancel the entire processing pipeline safely"""
        if self.is_cancelled:
            return
        self.is_cancelled = True
        self.progress.emit("Processing cancelled by user")

        # Terminate any active audio-related QProcess
        audio_processes = [
            getattr(self, attr, None)
            for attr in [
                'reencode_process', 'extract_process', 'shift_process',
                'audio_fallback_process', 'final_merge_process'
            ]
            if hasattr(self, attr)
        ]

        for proc in audio_processes:
            if proc and isinstance(proc, QProcess) and proc.state() == QProcess.Running:
                proc.terminate()
                # Force kill after 2s if still running
                QTimer.singleShot(2000, lambda p=proc: p.kill() if p.state() == QProcess.Running else None)

        # No video pipe anymore — nothing to closeWriteChannel()
        if self.progress_callback:
            self.progress_callback(0, 0, "Processing cancelled")
        self.finished.emit(0)  # Success code for cancel

    def _force_kill_process(self):
        """Force kill any hung audio FFmpeg process (called by timer)"""
        # You can keep this as-is, or make it more specific to audio
        for attr in ['reencode_process', 'extract_process', 'shift_process', 'audio_fallback_process', 'final_merge_process']:
            proc = getattr(self, attr, None)
            if proc and isinstance(proc, QProcess) and proc.state() == QProcess.Running:
                proc.kill()
                self.progress.emit("Force killed hung FFmpeg process")

    def _handle_output(self, process: QProcess):
        """Handle output from audio-related QProcess instances"""
        data = process.readAllStandardOutput().data().decode(errors='ignore').strip()
        if data:
            self.progress.emit(data)

    def _on_process_error(self, error):
        """Handle QProcess errorOccurred signal (for audio steps)"""
        if error in (0, 1):  # Ignore common false positives
            return
        self.error.emit(f"FFmpeg process error: {error}")
        self.finished.emit(1)             