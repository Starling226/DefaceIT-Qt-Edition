#!/usr/bin/env python3

import cv2
import numpy as np
from ultralytics import YOLO
from pathlib import Path
from typing import List, Tuple, Optional
import time
import subprocess
import os

try:
    try:
        from mediapipe.python.solutions import face_detection as mp_face_detection
        MEDIAPIPE_AVAILABLE = True
        MEDIAPIPE_NEW_API = True
    except ImportError:
        import mediapipe as mp
        if hasattr(mp, 'solutions'):
            MEDIAPIPE_AVAILABLE = True
            MEDIAPIPE_NEW_API = False
        else:
            MEDIAPIPE_AVAILABLE = False
            MEDIAPIPE_NEW_API = False
except ImportError:
    MEDIAPIPE_AVAILABLE = False
    MEDIAPIPE_NEW_API = False


class VideoBlurrer:
    
    def __init__(
        self,
        face_model_path: Optional[str] = None,
        license_plate_model_path: Optional[str] = None,
        device: str = "auto",
        blur_strength: int = 51,
        blur_type: str = "gaussian",
        confidence: float = 0.15,
        detect_faces: bool = True,
        detect_license_plates: bool = True,
        progress_callback=None,
        pitch_shift: float = 0.0
    ):
        self.blur_strength = blur_strength if blur_strength % 2 == 1 else blur_strength + 1
        self.blur_type = blur_type
        self.confidence = confidence
        self.detect_faces = detect_faces
        self.detect_license_plates = detect_license_plates
        self.progress_callback = progress_callback
        self.pitch_shift = pitch_shift
        self.face_padding = 0.2
        self.is_cancelled = False
        
        if device == "auto":
            import torch
            if torch.cuda.is_available():
                device = "cuda"
            elif hasattr(torch.backends, 'mps') and torch.backends.mps.is_available():
                device = "mps"
            else:
                device = "cpu"
        
        self.device = device
        self.models = []
        self.face_detector = None
        
        if detect_faces:
            if MEDIAPIPE_AVAILABLE:
                if MEDIAPIPE_NEW_API:
                    self.face_detector = mp_face_detection.FaceDetection(
                        model_selection=1,
                        min_detection_confidence=self.confidence
                    )
                else:
                    self.mp_face_detection = mp.solutions.face_detection
                    self.face_detector = self.mp_face_detection.FaceDetection(
                        model_selection=1,
                        min_detection_confidence=self.confidence
                    )
            else:
                if face_model_path:
                    face_model = YOLO(face_model_path)
                else:
                    face_model = YOLO("yolo11n.pt")
                face_model.to(device)
                self.models.append(("face", face_model))
        
        if detect_license_plates:
            if license_plate_model_path:
                lp_model = YOLO(license_plate_model_path)
            else:
                lp_model = YOLO("yolo11n.pt")
            lp_model.to(device)
            self.models.append(("license_plate", lp_model))
    
    def cancel(self):
        self.is_cancelled = True
    
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
        if self.detect_faces and self.face_detector is not None:
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            results = self.face_detector.process(rgb_frame)
            
            if results.detections:
                h, w = frame.shape[:2]
                for detection in results.detections:
                    bbox = detection.location_data.relative_bounding_box
                    x1 = int(bbox.xmin * w)
                    y1 = int(bbox.ymin * h)
                    x2 = int((bbox.xmin + bbox.width) * w)
                    y2 = int((bbox.ymin + bbox.height) * h)
                    
                    x1 = max(0, x1)
                    y1 = max(0, y1)
                    x2 = min(w, x2)
                    y2 = min(h, y2)
                    
                    if x2 > x1 and y2 > y1:
                        self.blur_region(frame, (x1, y1, x2, y2), padding=self.face_padding)
        
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
                        self.blur_region(frame, (x1, y1, x2, y2), padding=self.face_padding)
                    
                    elif model_type == "license_plate":
                        self.blur_region(frame, (x1, y1, x2, y2), padding=0.1)
        
        return frame
    
    def _check_ffmpeg(self) -> bool:
        try:
            subprocess.run(['ffmpeg', '-version'], 
                         stdout=subprocess.DEVNULL, 
                         stderr=subprocess.DEVNULL,
                         check=True)
            return True
        except (subprocess.CalledProcessError, FileNotFoundError):
            return False
    
    def _shift_audio_pitch(self, input_audio_path: str, output_audio_path: str, semitones: float) -> bool:
        try:
            import librosa
            import soundfile as sf
            
            y, sr = librosa.load(input_audio_path, sr=None)
            y_shifted = librosa.effects.pitch_shift(y, sr=sr, n_steps=semitones)
            sf.write(output_audio_path, y_shifted, sr)
            return True
        except ImportError:
            return self._shift_audio_pitch_ffmpeg(input_audio_path, output_audio_path, semitones)
        except Exception as e:
            print(f"Error shifting pitch: {e}")
            return False
    
    def _shift_audio_pitch_ffmpeg(self, input_audio_path: str, output_audio_path: str, semitones: float) -> bool:
        if not self._check_ffmpeg():
            return False
        
        try:
            pitch_ratio = 2 ** (semitones / 12.0)
            
            cmd = [
                'ffmpeg',
                '-i', input_audio_path,
                '-af', f'rubberband=pitch={pitch_ratio}',
                '-y',
                output_audio_path
            ]
            
            result = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            if result.returncode != 0:
                cmd = [
                    'ffmpeg',
                    '-i', input_audio_path,
                    '-af', f'asetrate={44100 * pitch_ratio},aresample=44100',
                    '-y',
                    output_audio_path
                ]
                result = subprocess.run(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True
                )
            
            return result.returncode == 0
        except Exception:
            return False
    
    def _merge_audio(self, input_video: str, output_video: str, pitch_shift: float = 0.0) -> Optional[str]:
        if not self._check_ffmpeg():
            return None
        
        output_path = Path(output_video)
        temp_audio = str(output_path.parent / f"{output_path.stem}_temp_audio.wav")
        final_output = str(output_path.parent / f"{output_path.stem}_with_audio{output_path.suffix}")
        
        try:
            extract_cmd = [
                'ffmpeg',
                '-i', input_video,
                '-vn', '-acodec', 'pcm_s16le',
                '-y',
                temp_audio
            ]
            
            result = subprocess.run(
                extract_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            if result.returncode != 0:
                os.replace(output_video, final_output)
                return final_output
            
            if abs(pitch_shift) > 0.01:
                shifted_audio = str(output_path.parent / f"{output_path.stem}_shifted_audio.wav")
                if self._shift_audio_pitch(temp_audio, shifted_audio, pitch_shift):
                    temp_audio = shifted_audio
                if os.path.exists(str(output_path.parent / f"{output_path.stem}_temp_audio.wav")):
                    os.remove(str(output_path.parent / f"{output_path.stem}_temp_audio.wav"))
            
            merge_cmd = [
                'ffmpeg',
                '-i', output_video,
                '-i', temp_audio,
                '-c:v', 'copy',
                '-c:a', 'aac',
                '-map', '0:v:0',
                '-map', '1:a:0',
                '-shortest',
                '-y',
                final_output
            ]
            
            result = subprocess.run(
                merge_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            if os.path.exists(temp_audio):
                os.remove(temp_audio)
            
            if result.returncode == 0:
                os.replace(final_output, output_video)
                return output_video
            else:
                return None
                
        except Exception as e:
            print(f"Error merging audio: {e}")
            return None
    
    def process_video(self, input_path: str, output_path: str) -> Tuple[bool, str]:
        self.is_cancelled = False
        
        if self.progress_callback:
            self.progress_callback(0, 0, "Opening video...")
        
        cap = cv2.VideoCapture(input_path)
        
        if not cap.isOpened():
            return False, f"Could not open video: {input_path}"
        
        fps = int(cap.get(cv2.CAP_PROP_FPS))
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        out = cv2.VideoWriter(output_path, fourcc, fps, (width, height))
        
        frame_count = 0
        processed_count = 0
        start_time = time.time()
        
        if self.progress_callback:
            self.progress_callback(0, 0, f"Processing {total_frames} frames...")
        
        while True:
            if self.is_cancelled:
                cap.release()
                out.release()
                if os.path.exists(output_path):
                    os.remove(output_path)
                return False, "Processing cancelled"
            
            ret, frame = cap.read()
            if not ret:
                break
            
            processed_frame = self.process_frame(frame.copy())
            out.write(processed_frame)
            
            processed_count += 1
            frame_count += 1
            
            if self.progress_callback and frame_count % 5 == 0:
                elapsed = time.time() - start_time
                fps_actual = processed_count / elapsed if elapsed > 0 else 0
                progress = (frame_count / total_frames) * 100
                self.progress_callback(progress, fps_actual, f"Processing frame {frame_count}/{total_frames}")
        
        cap.release()
        out.release()
        
        elapsed = time.time() - start_time
        
        if self.progress_callback:
            self.progress_callback(95, processed_count / elapsed if elapsed > 0 else 0, "Merging audio...")
        
        audio_result = self._merge_audio(input_path, output_path, self.pitch_shift)
        
        if self.progress_callback:
            if audio_result:
                self.progress_callback(100, processed_count / elapsed if elapsed > 0 else 0, "Complete!")
            else:
                self.progress_callback(100, processed_count / elapsed if elapsed > 0 else 0, "Complete! (no audio - ffmpeg not found)")
        
        return True, f"Processing complete! Speed: {processed_count / elapsed:.2f} FPS"
