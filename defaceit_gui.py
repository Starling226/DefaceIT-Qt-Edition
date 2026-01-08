#!/usr/bin/env python3
import sys
import os
import threading
import time
import tempfile
import subprocess
import platform
import webbrowser
import librosa
import shutil
import soundfile as sf
import re
import torch

from pathlib import Path
from superqt import QLabeledDoubleSlider,QLabeledSlider

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QSlider,
    QLineEdit, QPushButton, QRadioButton, QCheckBox, QProgressBar, QGroupBox,
    QFormLayout, QFrame, QMessageBox, QFileDialog, QComboBox, QButtonGroup
)
from PyQt5.QtCore import Qt, QTimer, QThread, pyqtSignal, QObject, QProcess, QLocale
from PyQt5.QtGui import QDoubleValidator
from video_blur_core import VideoBlurrer
from languages import LANGUAGES, CREDITS

class PreviewAudioWorker(QObject):
    """Worker for audio preview in a separate thread"""
    progress = pyqtSignal(str)      # Any status/output messages
    finished = pyqtSignal(int)      # Exit code (0 = success)
    error = pyqtSignal(str)         # Error messages

    def __init__(self, input_file, pitch_val, ffmpeg_path, prev_length):
        super().__init__()
        self.input_file = input_file
        self.pitch_val = pitch_val
        self.ffmpeg_path = ffmpeg_path
        self.prev_length = prev_length
        self.is_cancelled = False
        self.process = None
        self.temp_audio_path = None
        self.shifted_audio_path = None

    def run(self):

        if abs(self.pitch_val) < 0.01:
            self.error.emit("No pitch shift applied.")
            self.finished.emit(1)
            return

        self.progress.emit("Extracting audio...")

        # Step 1: Extract 10s audio with FFmpeg (non-blocking)
        self.temp_audio_path = tempfile.mktemp(suffix='.wav')

        extract_cmd = [
            self.ffmpeg_path,
            '-i', self.input_file,
            '-vn', '-acodec', 'pcm_s16le',
            '-t', str(self.prev_length),
            '-y', self.temp_audio_path
        ]

        self.process = QProcess()
        self.process.setProcessChannelMode(QProcess.MergedChannels)

        # Connect signals
        self.process.readyReadStandardOutput.connect(self._handle_output)        
        self.process.finished.connect(self._on_extract_finished)

#        print("DEBUG: FFmpeg path:", self.ffmpeg_path)
#        print("DEBUG: Exists?", os.path.exists(self.ffmpeg_path))
#        print("DEBUG: Is file?", os.path.isfile(self.ffmpeg_path))
#        print("DEBUG: Executable?", os.access(self.ffmpeg_path, os.X_OK))

        started = self.process.start(extract_cmd[0], extract_cmd[1:])

    def _handle_output(self):
        data = self.process.readAllStandardOutput().data().decode().strip()
        if data:
            self.progress.emit(data)

    def _on_extract_finished(self, exit_code, exit_status):
        if os.path.exists(self.temp_audio_path):
            size = os.path.getsize(self.temp_audio_path)
            self.progress.emit(f"Audio extracted OK (size: {size} bytes)")
        else:
            self.error.emit("Temp audio file not created")
            self.finished.emit(1)
            return            

        if self.is_cancelled:
            self._cleanup()
            self.finished.emit(0)
            return

        if exit_code != 0:
            self.error.emit(f"FFmpeg extraction failed (code {exit_code})")
            self._cleanup()
            self.finished.emit(exit_code)
            return

        self.progress.emit("Audio extracted. Applying pitch shift...")

        try:
            y, sr = librosa.load(self.temp_audio_path, sr=None)
            y_shifted = librosa.effects.pitch_shift(y, sr=sr, n_steps=self.pitch_val)

            self.shifted_audio_path = tempfile.mktemp(suffix='.wav')
            sf.write(self.shifted_audio_path, y_shifted, sr)

            self.progress.emit("Pitch shift complete. Starting playback...")

            os_type = platform.system().lower()
            # Play the shifted audio
            if os_type == 'darwin':
                player = 'afplay'
            elif os_type == 'linux':
                player = 'aplay'
            else:
                player = 'start'

            if os_type == 'windows':
                subprocess.Popen([player, self.shifted_audio_path], shell=True)
            else:
                subprocess.Popen([player, self.shifted_audio_path])

            # Wait for playback duration (in thread)
            duration = len(y_shifted) / sr
            print('duration: ',duration,y_shifted,sr)
            time.sleep(min(duration + 1, 11))

            self._cleanup()
            self.finished.emit(0)

        except Exception as e:
            self.error.emit(f"Preview error: {str(e)}")
            self._cleanup()
            self.finished.emit(1)

    def _on_process_error(self, error):
        self.error.emit(f"FFmpeg process error: {error}")
        self._cleanup()
        self.finished.emit(1)

    def _handle_error(self, error):
        """Handle QProcess errorOccurred signal"""
        error_msg = f"FFmpeg process error: {error}"
        self.parent().error_preview.emit(error_msg)
        if self.process.state() == QProcess.Running:
            self.process.terminate()
        self._cleanup()

    def _cleanup(self):
        for path in [self.temp_audio_path, self.shifted_audio_path]:
            if path and os.path.exists(path):
                try:
                    os.remove(path)
                except Exception:
                    pass

    def cancel(self):
        self.is_cancelled = True
        if self.process and self.process.state() == QProcess.Running:
            self.process.terminate()
        self.progress.emit("Preview cancelled")
        self.finished.emit(0)


class CustomLabeledSlider(QWidget):
    """
    Custom slider with editable label supporting float values and custom step.
    Example: CustomLabeledSlider(min_val=-12.0, max_val=12.0, def_val=0.0, step=0.1)
    """
    valueChanged = pyqtSignal(float)  # Emits real float value

    def __init__(self, orientation=Qt.Horizontal, min_val=-12.0, max_val=12.0, def_val=0.0, step=0.1, parent=None):
        super().__init__(parent)

        self.is_float = isinstance(min_val, float) or isinstance(max_val, float) or isinstance(step, float)

        self.step = step
        self.precision = int(1 / step) if step != 0 else 10  # e.g. 0.1 → 10, 0.01 → 100

        # Slider (scaled to integers internally)
        self.slider = QSlider(orientation, self)
        self.slider.setRange(int(min_val * self.precision), int(max_val * self.precision))
        self.slider.setSingleStep(1)  # Internal step is always 1 (precision handles decimals)

        # Clamp and set default value
        def_val = max(min_val, min(def_val, max_val))
        scaled_def = int(round(def_val * self.precision))
        self.slider.setValue(scaled_def)

        # Editable line edit
        self.line_edit = QLineEdit(self)
        self.line_edit.setFixedWidth(60)
        self.line_edit.setMaxLength(8)
        self.line_edit.setAlignment(Qt.AlignCenter)
        self.line_edit.setText(f"{def_val:.1f}")

        if self.is_float:
            validator = QDoubleValidator(min_val, max_val, 1)  # 1 decimal place
            validator.setNotation(QDoubleValidator.StandardNotation)
            validator.setLocale(QLocale.c())  # Ensures dot (.) as decimal separator
        else:
            validator = QIntValidator(min_val, max_val)
        self.line_edit.setValidator(validator)

        self.line_edit.setValidator(validator)

        self.line_edit.setStyleSheet("""
            QLineEdit {
                background-color: palette(window);
                border: none;               /* ← No border */
                padding: 2px 4px;
                selection-background-color: palette(highlight);
            }
            QLineEdit:focus {
                background-color: palette(base);
                border: none;               /* ← No border on focus too */
            }
        """)

        # Layout
        layout = QHBoxLayout(self)
        layout.addWidget(self.slider, stretch=1)
        layout.addWidget(self.line_edit)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        # Connections
        self.slider.valueChanged.connect(self._slider_to_edit)
        self.slider.valueChanged.connect(self._emit_value)

        self.line_edit.returnPressed.connect(self._edit_to_slider)
        self.line_edit.editingFinished.connect(self._edit_to_slider)

        # Initial sync
        self._slider_to_edit(self.slider.value())

    def _slider_to_edit(self, scaled_value):
        """Update line edit when slider moves."""
        self.line_edit.blockSignals(True)
        real_value = scaled_value / self.precision
        self.line_edit.setText(f"{real_value:.1f}")
        self.line_edit.blockSignals(False)

    def _emit_value(self, scaled_value):
        """Emit real float value to external listeners."""
        real_value = scaled_value / self.precision
        self.valueChanged.emit(real_value)

    def _edit_to_slider(self):
        """Update slider when user finishes editing."""
        text = self.line_edit.text().strip()
        try:
            value = float(text)
            # Round to nearest valid step
            value = round(value / self.step) * self.step
            scaled = int(round(value * self.precision))

            if self.slider.minimum() <= scaled <= self.slider.maximum():
                self.slider.setValue(scaled)
            else:
                self._slider_to_edit(self.slider.value())
        except ValueError:
            self._slider_to_edit(self.slider.value())

    # Proxy methods (use real float values)
    def setRange(self, min_val, max_val):
        self.slider.setRange(int(min_val * self.precision), int(max_val * self.precision))

    def setValue(self, value):
        value = round(value / self.step) * self.step  # enforce step
        scaled = int(round(value * self.precision))
        self.slider.setValue(scaled)
        self._emit_value(scaled)

    def value(self):
        return self.slider.value() / self.precision

    def minimum(self):
        return self.slider.minimum() / self.precision

    def maximum(self):
        return self.slider.maximum() / self.precision

class DefaceITApp(QMainWindow):

    progress_preview = pyqtSignal(str)
    finished_preview = pyqtSignal(int)
    error_preview = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.language = "en"
        self.texts = LANGUAGES[self.language]
        self.setWindowTitle(self.texts["title"])
        self.resize(650, 825)
        self.setFixedSize(650, 825)
        self.ffmpeg_path = ""
        self.input_file = ""
        self.output_file = ""
        self.blur_strength = 51
        self.confidence = 0.15
        self.crf_value = 22
        self.blur_type = "gaussian"
        self.detect_faces = True
        self.detect_license_plates = True
        self.device = "cpu"
        self.pitch_shift = -4.0
        self.prev_length = 10 # seconds
        self.audio_preview_playing = False
        self.is_processing = False
        self.blurrer = None

        # Thread & worker
        self.thread = None
        self.worker = None

        self.preview_active = False
        self.preview_thread = None
        self.preview_worker = None
        self.preview_cooldown = False

        self.ffmpeg_browse_text = ""
        self.get_ffmpeg_brows_text()
        self.ffmpeg_path = self.get_ffmpeg_path()

        self.init_ui()

    def get_ffmpeg_brows_text(self):
        import platform

        os_type = platform.system().lower()
        if os_type == "linux":
            self.ffmpeg_browse_text = "*.*"

        elif os_type == "darwin":  # macOS
            self.ffmpeg_browse_text = "*.*"

        elif os_type == "windows":
            self.ffmpeg_browse_text = "exe files (*.exe)"
        else:
            self.ffmpeg_browse_text = "*.*"

    def init_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(8)

        # Title
        title_label = QLabel("DefaceIT", self)
        title_label.setAlignment(Qt.AlignCenter)
        title_label.setStyleSheet("font-size: 18px; font-weight: bold;")
        main_layout.addWidget(title_label)

        # Language selection
        lang_layout = QHBoxLayout()
        lang_label = QLabel(f"{self.texts['language']}:")
        lang_layout.addWidget(lang_label)

        self.lang_group = QButtonGroup(self)
        en_radio = QRadioButton(self.texts["english"])
        fa_radio = QRadioButton(self.texts["persian"])
        en_radio.setObjectName("en_radio")
        fa_radio.setObjectName("fa_radio")
        self.lang_group.addButton(en_radio)
        self.lang_group.addButton(fa_radio)

        # Set initial checked state
        if self.language == "en":
            en_radio.setChecked(True)
        else:
            fa_radio.setChecked(True)

        # Connect signals (initial connection)
        en_radio.toggled.connect(lambda checked: self.change_language("en") if checked else None)
        fa_radio.toggled.connect(lambda checked: self.change_language("fa") if checked else None)

        lang_layout.addWidget(en_radio)
        lang_layout.addWidget(fa_radio)
        main_layout.addLayout(lang_layout)

        # Input file row
        input_layout = QHBoxLayout()
        input_label = QLabel(self.texts["input_video"])
        self.input_edit = QLineEdit()  # ← Save reference
        input_browse = QPushButton(self.texts["browse"])
        input_browse.clicked.connect(self.browse_input)
        input_layout.addWidget(input_label)
        input_layout.addWidget(self.input_edit)
        input_layout.addWidget(input_browse)
        main_layout.addLayout(input_layout)

        # Output file row
        output_layout = QHBoxLayout()
        output_label = QLabel(self.texts["output_video"])
        self.output_edit = QLineEdit()  # ← Save reference
        output_browse = QPushButton(self.texts["browse"])
        output_browse.clicked.connect(self.browse_output)
        output_layout.addWidget(output_label)
        output_layout.addWidget(self.output_edit)
        output_layout.addWidget(output_browse)
        main_layout.addLayout(output_layout)

        # ffmpeg path
        ffmpeg_layout = QHBoxLayout()
        ffmpeg_label = QLabel(self.texts["ffmpeg_path"])
        self.ffmpeg_edit = QLineEdit()  # ← Save reference
        ffmpeg_browse = QPushButton(self.texts["browse"])
        ffmpeg_browse.clicked.connect(self.browse_ffmpeg)
        ffmpeg_layout.addWidget(ffmpeg_label)
        ffmpeg_layout.addWidget(self.ffmpeg_edit)
        ffmpeg_layout.addWidget(ffmpeg_browse)
        main_layout.addLayout(ffmpeg_layout)
        if self.ffmpeg_path != "":
            self.ffmpeg_edit.setText(self.ffmpeg_path)

        main_layout.addWidget(QFrame())  # Separator

        # Settings group
        settings_group = QGroupBox(self.texts["settings"])
        settings_layout = QFormLayout(settings_group)
        main_layout.addWidget(settings_group)

        # Blur strength slider (using superqt)
        self.blur_slider = QLabeledSlider(Qt.Horizontal)
        self.blur_slider.setRange(21, 101)
        self.blur_slider.setValue(self.blur_strength)
        self.blur_slider.valueChanged.connect(self.update_blur_label)
        self.blur_label = QLabel(str(self.blur_strength))
        settings_layout.addRow(self.texts["blur_strength"], self.blur_slider)

        # Confidence slider
        self.conf_slider = QLabeledDoubleSlider(Qt.Horizontal)
        self.conf_slider.setRange(0.05, 0.5)
        self.conf_slider.setValue(self.confidence)
        self.conf_slider.valueChanged.connect(self.update_conf_label)
        self.conf_label = QLabel(f"{self.confidence:.2f}")
        settings_layout.addRow(self.texts["confidence"], self.conf_slider)

        # Blur type radio buttons
        blur_type_layout = QHBoxLayout()
        gaussian_radio = QRadioButton(self.texts["gaussian"])
        pixelate_radio = QRadioButton(self.texts["pixelate"])
        gaussian_radio.setChecked(True)

        blur_type_group = QGroupBox(self.texts["blur_type"])
        blur_type_layout = QHBoxLayout(blur_type_group)

        gaussian_radio = QRadioButton(self.texts["gaussian"])
        pixelate_radio = QRadioButton(self.texts["pixelate"])

        self.blur_type_group = QButtonGroup(self)
        self.blur_type_group.addButton(gaussian_radio, 0)   # ID 0 = gaussian
        self.blur_type_group.addButton(pixelate_radio, 1)   # ID 1 = pixelate

        gaussian_radio.setChecked(True)  # default to gaussian
        self.blur_type_group.idClicked.connect(self.on_blur_type_selected)

        blur_type_layout.addWidget(gaussian_radio)
        blur_type_layout.addWidget(pixelate_radio)
        settings_layout.addRow(blur_type_group)

        # Detect checkboxes
        detect_layout = QHBoxLayout()
        self.faces_check = QCheckBox(self.texts["faces"])
        self.faces_check.setChecked(True)
        self.faces_check.stateChanged.connect(lambda state: setattr(self, "detect_faces", state == Qt.Checked))
        self.plates_check = QCheckBox(self.texts["license_plates"])
        self.plates_check.setChecked(True)
        self.plates_check.stateChanged.connect(lambda state: setattr(self, "detect_license_plates", state == Qt.Checked))
        detect_layout.addWidget(self.faces_check)
        detect_layout.addWidget(self.plates_check)
        settings_layout.addRow(self.texts["detect"], detect_layout)

        # Device radio buttons
        device_layout = QHBoxLayout()
        self.cpu_radio = QRadioButton(self.texts["cpu"])
        self.gpu_radio = QRadioButton(self.texts["gpu"])
        self.gpu_radio.setChecked(True)

        self.device_group = QButtonGroup(self)
        self.device_group.addButton(self.cpu_radio, 0)    # id 0 = cpu
        self.device_group.addButton(self.gpu_radio, 1)    # id 1 = cuda, mps

        self.device_group.idClicked.connect(self.on_device_id_selected)

        device_layout.addWidget(self.cpu_radio)
        device_layout.addWidget(self.gpu_radio)
        settings_layout.addRow(self.texts["device"], device_layout)

        self.reencode_to_h264 = True
        # NEW: Re-encode to H.264 checkbox
        reencode_layout = QHBoxLayout()
        self.reencode_checkbox = QCheckBox(self.texts["re_encode"])
#        self.reencode_checkbox = QCheckBox("Re-encode to H.264 (better quality, smaller file)")
        self.reencode_checkbox.setChecked(self.reencode_to_h264)  # Default checked
        self.reencode_checkbox.stateChanged.connect(self.on_reencode_changed)
        reencode_layout.addWidget(self.reencode_checkbox)
        settings_layout.addRow(reencode_layout)

        # Video Quality slider
        self.crf_slider = QLabeledSlider(Qt.Horizontal)
        self.crf_slider.setRange(10, 28)
        self.crf_slider.setValue(self.crf_value)
        self.crf_slider.valueChanged.connect(self.update_crf_value)
        self.crf_slider.setToolTip(self.texts["crf_def"])
        settings_layout.addRow(self.texts["crf_value"], self.crf_slider)

        main_layout.addWidget(QFrame())  # Separator

        # Audio pitch shift
        audio_group = QGroupBox(self.texts["audio_pitch_shift"])
        audio_layout = QFormLayout(audio_group)
        main_layout.addWidget(audio_group)

        self.pitch_slider = CustomLabeledSlider(Qt.Horizontal, min_val=-12.0, max_val=12.0, def_val = self.pitch_shift, step=0.1)
        self.pitch_slider.valueChanged.connect(self.update_pitch_label)
        self.pitch_label = QLabel(f"{self.pitch_shift:+.1f}")
        audio_layout.addRow(self.texts["pitch_semitones"], self.pitch_slider)

        # Blur strength slider (using superqt)
        self.prev_slider = QLabeledSlider(Qt.Horizontal)
        self.prev_slider.setRange(1, 60)
        self.prev_slider.setValue(self.prev_length)
        self.prev_slider.valueChanged.connect(self.update_prev_length)
#        self.prev_label = QLabel(str(self.prev_length))
        audio_layout.addRow(self.texts["prev_length"], self.prev_slider)

        preview_layout = QHBoxLayout()
        self.preview_button = QPushButton(self.texts["preview_audio"])
        self.preview_button.clicked.connect(self.preview_audio)
        self.stop_preview_button = QPushButton(self.texts["stop_preview"])
        self.stop_preview_button.clicked.connect(self.stop_preview)
        self.stop_preview_button.setEnabled(False)
        preview_layout.addWidget(self.preview_button)
        preview_layout.addWidget(self.stop_preview_button)
        audio_layout.addRow(preview_layout)

        main_layout.addWidget(QFrame())  # Separator

        # Progress
        progress_layout = QHBoxLayout()
        progress_label = QLabel(self.texts["progress"])
        self.progress_bar = QProgressBar()
        self.progress_bar.setMaximum(100)
        progress_layout.addWidget(progress_label)
        progress_layout.addWidget(self.progress_bar)
        main_layout.addLayout(progress_layout)

        self.status_label = QLabel(self.texts["ready"])
        self.status_label.setStyleSheet("color: green;")
        main_layout.addWidget(self.status_label)

        self.fps_label = QLabel("")
        main_layout.addWidget(self.fps_label)

        # Buttons
        button_layout = QHBoxLayout()
        self.process_button = QPushButton(self.texts["start_processing"])
        self.process_button.clicked.connect(self.start_processing)
        self.cancel_button = QPushButton(self.texts["cancel"])
        self.cancel_button.clicked.connect(self.cancel_processing)
        self.cancel_button.setEnabled(False)
        button_layout.addWidget(self.process_button)
        button_layout.addWidget(self.cancel_button)
        main_layout.addLayout(button_layout)

        main_layout.addWidget(QFrame())  # Separator

        # Credits section
        credits_label = QLabel(self.texts["credits"])
        credits_label.setStyleSheet("font-weight: bold; font-size: 10px;")
        main_layout.addWidget(credits_label)

        # Developer credit
        dev_layout = QHBoxLayout()
        dev_label = QLabel(f"{self.texts['developer']} ")
        dev_label.setStyleSheet("font-size: 10px;")
        dev_layout.addWidget(dev_label)

        dev_link = QLabel(CREDITS["original_author"])
        dev_link.setStyleSheet("color: red; text-decoration: underline; font-size: 10px;")
        dev_link.setCursor(Qt.PointingHandCursor)
        dev_link.mousePressEvent = lambda event: webbrowser.open(CREDITS["original_x"])
        dev_layout.addWidget(dev_link)
        dev_layout.addStretch()
        main_layout.addLayout(dev_layout)

        dev_link = QLabel(CREDITS["fork_author"])
        dev_link.setStyleSheet("color: red; text-decoration: underline; font-size: 10px;")
        dev_link.setCursor(Qt.PointingHandCursor)
        dev_link.mousePressEvent = lambda event: webbrowser.open(CREDITS["original_x"])
        dev_layout.addWidget(dev_link)
        dev_layout.addStretch()
        main_layout.addLayout(dev_layout)

        # Website credit
        website_layout = QHBoxLayout()
        website_label = QLabel(f"{self.texts['website']} ")
        website_label.setStyleSheet("font-size: 10px;")
        website_layout.addWidget(website_label)

        website_link = QLabel(CREDITS["original_website"])
        website_link.setStyleSheet("color: red; text-decoration: underline; font-size: 10px;")
        website_link.setCursor(Qt.PointingHandCursor)
        website_link.mousePressEvent = lambda event: webbrowser.open(CREDITS["original_website"])
        website_layout.addWidget(website_link)
        website_layout.addStretch()
        main_layout.addLayout(website_layout)

        # Telegram credit
        telegram_layout = QHBoxLayout()
        telegram_label = QLabel(f"{self.texts['telegram']} ")
        telegram_label.setStyleSheet("font-size: 10px;")
        telegram_layout.addWidget(telegram_label)

        telegram_link = QLabel(CREDITS["original_telegram"])
        telegram_link.setStyleSheet("color: red; text-decoration: underline; font-size: 10px;")
        telegram_link.setCursor(Qt.PointingHandCursor)
        telegram_link.mousePressEvent = lambda event: webbrowser.open(CREDITS["original_telegram"])
        telegram_layout.addWidget(telegram_link)
        telegram_layout.addStretch()
        main_layout.addLayout(telegram_layout)

        # Donate Crypto credit
        crypto_layout = QHBoxLayout()
        crypto_label = QLabel(f"{self.texts['donate_crypto']} ")
        crypto_label.setStyleSheet("font-size: 10px;")
        crypto_layout.addWidget(crypto_label)

        crypto_link = QLabel(CREDITS["original_donate_crypto"])
        crypto_link.setStyleSheet("color: red; text-decoration: underline; font-size: 10px;")
        crypto_link.setCursor(Qt.PointingHandCursor)
        crypto_link.mousePressEvent = lambda event: webbrowser.open(CREDITS["original_donate_crypto"])
        crypto_layout.addWidget(crypto_link)
        crypto_layout.addStretch()
        main_layout.addLayout(crypto_layout)

        # Donate Card credit
        card_layout = QHBoxLayout()
        card_label = QLabel(f"{self.texts['donate_card']} ")
        card_label.setStyleSheet("font-size: 10px;")
        card_layout.addWidget(card_label)

        card_link = QLabel(CREDITS["original_donate_card"])
        card_link.setStyleSheet("color: red; text-decoration: underline; font-size: 10px;")
        card_link.setCursor(Qt.PointingHandCursor)
        card_link.mousePressEvent = lambda event: webbrowser.open(CREDITS["original_donate_card"])
        card_layout.addWidget(card_link)
        card_layout.addStretch()
        main_layout.addLayout(card_layout)

        main_layout.addStretch()

        has_nvidia, has_mps, msg = self.has_nvidia_gpu()
        if has_nvidia:
            if has_mps:
                self.status_label.setText("GPU (MPS) ready")
                self.device = "mps"                            
                self.gpu_radio.setChecked(True)

            else:
                is_compatible, msg = self.check_gpu_compatibility()  # your previous method
                self.status_label.setText(msg)
                if is_compatible:
                    self.device = "cuda"
                    self.gpu_radio.setChecked(True)
                    self.status_label.setText("GPU ready")
                else:
                    self.cpu_radio.setChecked(True)
                    self.device = "cpu"

        else:
            self.device = "cpu"
            self.cpu_radio.setChecked(True)
            self.status_label.setText(msg)

    def on_blur_type_selected(self, button_id):
        """Called when user selects a blur type radio button"""
        if button_id == 0:
            self.blur_type = "gaussian"
        elif button_id == 1:
            self.blur_type = "pixelate"

    def on_device_id_selected(self, id):
        if id == 0:
            self.device = "cpu"
            self.status_label.setText("Using CPU")

        else:
            has_nvidia, has_mps, msg = self.has_nvidia_gpu()
            if has_nvidia:
                if has_mps:
                    self.status_label.setText("GPU (MPS) ready")
                    self.device = "mps"
                else:
                    is_compatible, msg = self.check_gpu_compatibility()  # your previous method
                    self.status_label.setText(msg)
                    if is_compatible:
                        self.device = "cuda"
                        self.status_label.setText("GPU ready")
                    else:
                        self.device = "cpu"
                        self.cpu_radio.setChecked(True)                        
                        QMessageBox.information(self, "Device Info", msg)

            else:
                self.device = "cpu"
                self.cpu_radio.setChecked(True)
                self.status_label.setText(msg)
                QMessageBox.warning(self, "GPU Check", msg + "\nFalling back to CPU.")


    def on_reencode_changed(self, state):
        """Called when user toggles the re-encode checkbox"""
        self.reencode_to_h264 = (state == Qt.Checked)
#        print(f"Re-encode to H.264: {self.reencode_to_h264}")  # Optional debug

    def change_language(self, lang):
        self.language = lang
        self.texts = LANGUAGES[lang]
        self.setWindowTitle(self.texts["title"])
    
        # Rebuild UI
        self.init_ui()
    
        # After rebuilding, find the language radio buttons again and reconnect them
        # Assuming you gave them object names in init_ui (add this if not already)
        # In init_ui, add:
        # en_radio.setObjectName("en_radio")
        # fa_radio.setObjectName("fa_radio")
    
        # Now reconnect (find by object name)
        en_radio = self.findChild(QRadioButton, "en_radio")
        fa_radio = self.findChild(QRadioButton, "fa_radio")
    
        if en_radio and fa_radio:
            # Disconnect any old connections (optional safety)
            en_radio.toggled.disconnect()
            fa_radio.toggled.disconnect()
        
            # Reconnect
            en_radio.toggled.connect(lambda checked: self.change_language("en") if checked else None)
            fa_radio.toggled.connect(lambda checked: self.change_language("fa") if checked else None)
        
            # Set checked state based on current language
            if lang == "en":
                en_radio.setChecked(True)
            else:
                fa_radio.setChecked(True)

    def change_language(self, lang):
        self.language = lang
        self.texts = LANGUAGES[lang]
        self.setWindowTitle(self.texts["title"])
        self.init_ui()  # Refresh UI with new language

    def update_blur_label(self):
        self.blur_label.setText(str(self.blur_strength))

    def update_conf_label(self):
        self.conf_label.setText(f"{self.confidence:.2f}")

    def update_pitch_label(self):
        self.pitch_label.setText(f"{self.pitch_shift:+.1f}")

    def update_prev_length(self):
        self.prev_length = int(self.prev_slider.value())

    def update_crf_value(self):
        self.crf_value = int(self.crf_slider.value())

    def browse_input(self):
        filename, _ = QFileDialog.getOpenFileName(
            self,
            self.texts["input_video"],
            "",
            "Video files (*.mp4 *.avi *.mov *.mkv *.flv *.wmv);;MP4 files (*.mp4);;All files (*.*)"
        )
        if filename:
            self.input_file = filename  # Assuming self.input_file is now a string (not tk.StringVar)
            self.input_edit.setText(filename)  # ← Update the display!

#            if not self.output_file:
            input_path = Path(filename)
            output_path = input_path.parent / f"{input_path.stem}_blurred{input_path.suffix}"
            output_path = str(Path(output_path).with_suffix(".mp4"))
            self.output_file = str(output_path)
            self.output_edit.setText(self.output_file) 

    def browse_output(self):
        filename, _ = QFileDialog.getSaveFileName(
            self,
            self.texts["output_video"],
            "",
            "MP4 files (*.mp4);;Video files (*.mp4 *.avi *.mov);;All files (*.*)",
            options=QFileDialog.DontUseNativeDialog
        )
        if filename:
            self.output_file = filename
            self.output_edit.setText(filename)  # ← Update the display!

    def browse_ffmpeg(self):
        filename, _ = QFileDialog.getOpenFileName(
            self,
            self.texts["ffmpeg_exe"],
            "",
            self.ffmpeg_browse_text,
            options=QFileDialog.DontUseNativeDialog
        )
        if filename:
            self.ffmpeg_path = filename
            self.ffmpeg_edit.setText(filename)

    def update_progress(self, progress, fps, status):
        self.progress_bar.setValue(int(progress))
        self.status_label.setText(status)
        if fps > 0:
            self.fps_label.setText(f"{self.texts['processing_speed']} {fps:.1f} {self.texts['fps']}")
        QApplication.processEvents()  # Force UI update (similar to update_idletasks)

    def check_gpu_compatibility(self):
        """Check GPU compatibility and update GUI radio buttons accordingly"""
        import torch

        if not torch.cuda.is_available():
            msg = "No CUDA GPU detected - falling back to CPU"
            return False, msg

        # Get GPU info
        device_name = torch.cuda.get_device_name(0)
        capability = torch.cuda.get_device_capability(0)
        major, minor = capability
        cc = major * 10 + minor

        print(f"Detected GPU: {device_name} (compute {major}.{minor})")

        min_cc = 70  # Minimum supported by modern PyTorch
        if cc < min_cc:
            msg = f"GPU too old (compute {major}.{minor}, requires >=7.0) - using CPU"
            return False, msg

        # GPU is compatible
        msg = f"GPU ready: {device_name} (compute {major}.{minor})"
        return True, msg

    def has_nvidia_gpu(self):
        """
        Check if the machine has an NVIDIA GPU (Windows, Linux, macOS).
        Returns: (bool: has_nvidia, str: message)
        """
        os_type = platform.system().lower()
        message = "No GPU acceleration detected (using CPU)"

        # 1. Try nvidia-smi first (works on all OS with NVIDIA drivers)
        try:
            result = subprocess.run(
                ["nvidia-smi", "--query-gpu=name", "--format=csv,noheader"],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0 and result.stdout.strip():
                gpu_name = result.stdout.strip().splitlines()[0]
                return True, False, f"NVIDIA GPU detected: {gpu_name}"
        except (FileNotFoundError, subprocess.TimeoutExpired, subprocess.CalledProcessError):
            pass

        # 2. Linux-specific checks
        if os_type == "linux":
            try:
                # lspci (list PCI devices)
                result = subprocess.run(
                    ["lspci", "-vmm"],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                if "NVIDIA" in result.stdout.upper():
                    return True, False, "NVIDIA GPU detected via lspci"
            except Exception:
                pass

            # Check loaded NVIDIA kernel module
            try:
                result = subprocess.run(
                    ["lsmod"],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                if re.search(r"nvidia\s", result.stdout):
                    return True, False, "NVIDIA driver module loaded"
            except Exception:
                pass

        # 3. Windows-specific check
        if os_type == "windows":
            try:
                # WMIC - list video controllers
                result = subprocess.run(
                    "wmic path win32_VideoController get name",
                    shell=True,
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                if "NVIDIA" in result.stdout.upper():
                    return True, False, "NVIDIA GPU detected via WMIC"
            except Exception:
                pass

            # Alternative: dxdiag fallback (parse output)
            try:
                result = subprocess.run(
                    "dxdiag /t dxdiag.txt",
                    shell=True,
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                if os.path.exists("dxdiag.txt"):
                    with open("dxdiag.txt", "r") as f:
                        content = f.read()
                    if "NVIDIA" in content.upper():
                        return True, False, "NVIDIA GPU detected via dxdiag"
                    os.remove("dxdiag.txt")
            except Exception:
                pass

        # 4. macOS-specific check
        if os_type == "darwin":  # macOS
            try:
                result = subprocess.run(
                    ["system_profiler", "SPDisplaysDataType"],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                if "NVIDIA" in result.stdout.upper():
                    return True, False, "NVIDIA GPU detected via system_profiler (rare on modern Macs)"
            except Exception:
                pass

            # Check for Apple MPS (M1/M2/M3/M4 - modern Macs)
            if hasattr(torch.backends, 'mps') and torch.backends.mps.is_available():
                return True, True, "Apple GPU acceleration (MPS) detected - using Metal on Apple Silicon"

        # 5. Final fallback: no NVIDIA found
        return False, False, message

    def get_ffmpeg_path(self):
        '''
        try:
            which = subprocess.check_output(["which", "ffmpeg"], text=True).strip()
            print("which ffmpeg →", which)
        except Exception as e:
            print("which failed:", e)
        '''

        ffmpeg_path = shutil.which("ffmpeg")
        if ffmpeg_path:
            print("Found FFmpeg:", ffmpeg_path)
            return ffmpeg_path
      
        print("ffmpeg was not detected")
        return ""

    def check_if_ffmpeg_exist(self,ffmpeg_path):
        # Try to run ffmpeg -version
        try:
            result = subprocess.run(
                [ffmpeg_path, "-version"],
                capture_output=True,
                text=True,
                check=False
            )
            return True
        except FileNotFoundError:
            print("FileNotFoundError: ffmpeg executable not found by subprocess!")
            return False

    def start_processing(self):

        if self.is_processing:
            return

        if self.thread and self.thread.isRunning():
            return
        
        ffmpeg_edit = self.ffmpeg_edit.text().strip()
        if ffmpeg_edit == "":
            QMessageBox.warning(self, "Error", "ffmpeg is not set")
            return

        if not Path(ffmpeg_edit).exists():
            QMessageBox.warning(self, "Error", self.texts["error_file_not_found"])
            self.ffmpeg_edit.setStyleSheet("color: rgb(255, 0, 0);")
            return

        self.ffmpeg_edit.setStyleSheet("color: rgb(0, 0, 0);")
        self.ffmpeg_path = ffmpeg_edit
#        self.ffmpeg_path = self.get_ffmpeg_path()
        if not self.check_if_ffmpeg_exist(self.ffmpeg_path):
            return

        self.input_file = self.input_edit.text().strip()
        if not self.input_file:
            QMessageBox.warning(self, "Error", self.texts["error_no_input"])
            return

        self.output_file = self.output_edit.text().strip()
        if not self.output_file:
            QMessageBox.warning(self, "Error", self.texts["error_no_output"])
            return

        if not Path(self.input_file).exists():
            QMessageBox.warning(self, "Error", self.texts["error_file_not_found"])
            return

        self.is_processing = True
        self.process_button.setEnabled(False)
        self.cancel_button.setEnabled(True)
        self.progress_bar.setValue(0)
        self.status_label.setText("Initializing...")
        self.status_label.setStyleSheet("color: blue;")
        self.fps_label.setText("")
        

        self.blur_strength = int(self.blur_slider.value())
        self.confidence = float(self.conf_slider.value())
        self.pitch_shift = float(self.pitch_slider.value())
        
        self.process_video_Qthread()

    def process_video_Qthread(self):        

        self.thread = QThread()
        self.worker = VideoBlurrer(
            device=self.device,
            blur_strength=self.blur_strength,
            blur_type=self.blur_type,
            confidence=self.confidence,
            detect_faces=self.detect_faces,
            detect_license_plates=self.detect_license_plates,
            progress_callback=self.update_progress,
            pitch_shift=self.pitch_shift,
            reencode_to_h264=self.reencode_to_h264,
            input_file = self.input_file,
            output_file = self.output_file,
            ffmpeg_path = self.ffmpeg_path,
            crf_value = self.crf_value
        )

        self.worker.moveToThread(self.thread)

        # Connections
#        self.thread.started.connect(self.worker.process_video)
        self.thread.started.connect(self.worker.start)  # ← call start()
        self.worker.progress.connect(self.append_output)
        self.worker.finished.connect(self.processing_complete)
        self.worker.error.connect(self.on_error)
        self.thread.finished.connect(self.cleanup_thread)

        self.thread.start()
        
    def processing_complete(self, exit_code):
        self.is_processing = False
        self.process_button.setEnabled(True)
        self.cancel_button.setEnabled(False)

        if exit_code == 0:
            self.status_label.setText("Complete!")
            self.status_label.setStyleSheet("color: green;")
            QMessageBox.information(
                self, "Success",
                f"{self.texts['success_complete']}\n\n"
                f"{self.texts['output_video']}:\n{self.output_file}"
            )
        else:
            self.status_label.setText("Failed")
            self.status_label.setStyleSheet("color: red;")
            QMessageBox.critical(self, "Error", f"{exit_code}")

        self.cleanup_thread()

    def cancel_processing(self):
        if self.worker:
            self.worker.cancel()
        self.is_processing = False
        self.process_button.setEnabled(True)
        self.cancel_button.setEnabled(False)
        self.status_label.setText("Cancelling...")
        self.status_label.setStyleSheet("color: orange;")

        # Force thread cleanup (non-blocking)
        if self.thread and self.thread.isRunning():
            self.thread.quit()
            # No wait() - let finished signal handle deletion
        self.cleanup_thread()

    def on_error(self, msg):
        print(f"\nERROR: {msg}")
        self.status_label.setText("Error occurred")
        self.status_label.setStyleSheet("color: red;")
        QMessageBox.critical(self, "Processing Error", msg)
    
        self.is_processing = False
        self.process_button.setEnabled(True)
        self.cancel_button.setEnabled(False)

    def cleanup_thread(self):
        if self.thread:
            self.thread.quit()
            self.thread.wait(5000)  # wait up to 5s
            self.thread.deleteLater()
        self.thread = None
        self.worker = None

    def append_output(self, text):
        print(text)

    def preview_audio(self):

        self.input_file = self.input_edit.text().strip()
        if not self.input_file or not Path(self.input_file).exists():
            QMessageBox.warning(self, "Error", self.texts["error_preview_no_file"])
            return

        self.pitch_shift = float(self.pitch_slider.value())
        pitch_val = self.pitch_shift
        if abs(pitch_val) < 0.01:
            QMessageBox.information(self, "Info", self.texts["info_no_pitch"])
            return

        # Force stop any old preview first (if running)
        if self.audio_preview_playing or (self.preview_thread and self.preview_thread.isRunning()):
            self.stop_preview()
            # Small delay to let cleanup finish (non-blocking)
            QTimer.singleShot(500, lambda: self._start_preview(pitch_val))
            return

        # Normal start (no old preview)
        self._start_preview(pitch_val)

    def _start_preview(self, pitch_val):

        self.audio_preview_playing = True
        self.preview_button.setEnabled(False)
        self.stop_preview_button.setEnabled(True)
        self.status_label.setText("Loading audio preview...")
        self.status_label.setStyleSheet("color: blue;")

        ffmpeg_edit = self.ffmpeg_edit.text().strip()
        if ffmpeg_edit == "":
            QMessageBox.warning(self, "Error", "ffmpeg is not set")
            return

        if not Path(ffmpeg_edit).exists():
            QMessageBox.warning(self, "Error", self.texts["error_file_not_found"])
            self.ffmpeg_edit.setStyleSheet("color: rgb(255, 0, 0);")
            return

        self.ffmpeg_edit.setStyleSheet("color: rgb(0, 0, 0);")
        self.ffmpeg_path = ffmpeg_edit
#        self.ffmpeg_path = self.get_ffmpeg_path()
        if not self.check_if_ffmpeg_exist(self.ffmpeg_path):
            return

        try:
            self.preview_thread = QThread()
            self.preview_worker = PreviewAudioWorker(self.input_file, pitch_val, self.ffmpeg_path, self.prev_length)

            self.preview_worker.moveToThread(self.preview_thread)

            self.preview_worker.progress.connect(self.progress_preview.emit)
            self.preview_worker.finished.connect(self.on_preview_finished)
            self.preview_worker.error.connect(self.on_preview_error)

            self.preview_thread.started.connect(self.preview_worker.run)
            self.preview_thread.finished.connect(self.cleanup_preview_thread)
 
            self.preview_thread.start()

        except Exception as e:
            print("Preview setup error:", str(e))
            self.audio_preview_playing = False
            self.preview_button.setEnabled(True)
            self.stop_preview_button.setEnabled(False)
            QMessageBox.critical(self, "Error", f"Preview failed to start: {str(e)}")

    def _end_cooldown(self):
        self.preview_cooldown = False
        print("Cooldown ended - ready for next preview")


    def on_preview_finished(self, exit_code):
        print(f"Preview finished with code {exit_code}")
        self.preview_active = False
        self.audio_preview_playing = False
        self.preview_button.setEnabled(True)
        self.stop_preview_button.setEnabled(False)
        if exit_code == 0:
            self.status_label.setText("Preview complete")
            self.status_label.setStyleSheet("color: green;")
        else:
            self.status_label.setText("Preview failed")
            self.status_label.setStyleSheet("color: red;")

    def on_preview_error(self, message):
        QMessageBox.warning(self, "Preview Error", message)
        self.audio_preview_playing = False
        self.preview_button.setEnabled(True)
        self.stop_preview_button.setEnabled(False)

    def cleanup_preview_thread(self):
        print(" Cleaning up preview thread")
        if self.preview_thread:
            self.preview_thread.quit()
            # NO wait() here - let Qt handle deletion
            self.preview_thread.deleteLater()
        self.preview_thread = None
        self.preview_worker = None

    def stop_preview(self):
        print("Stopping preview")
        if self.preview_worker:
            self.preview_worker.cancel()
        if self.preview_thread and self.preview_thread.isRunning():
            self.preview_thread.quit()

        self.preview_active = False
        self.audio_preview_playing = False
        self.preview_button.setEnabled(True)
        self.stop_preview_button.setEnabled(False)
        self.status_label.setText("Preview stopped")
        self.status_label.setStyleSheet("color: orange;")

    def on_progress_preview(self,message):
        print(message)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = DefaceITApp()
    window.show()
    sys.exit(app.exec_())