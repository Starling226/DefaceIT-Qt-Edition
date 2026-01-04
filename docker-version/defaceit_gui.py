#!/usr/bin/env python3

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from pathlib import Path
import threading
import sys
import os
import webbrowser
import platform
import subprocess
import tempfile
import time

from video_blur_core import VideoBlurrer
from languages import LANGUAGES, CREDITS


class DefaceITApp:
    def __init__(self, root):
        self.root = root
        self.language = tk.StringVar(value="en")
        self.texts = LANGUAGES["en"]
        self.root.title(self.texts["title"])
        self.root.geometry("650x750")
        self.root.resizable(False, False)
        
        self.input_file = tk.StringVar()
        self.output_file = tk.StringVar()
        self.blur_strength = tk.IntVar(value=51)
        self.confidence = tk.DoubleVar(value=0.15)
        self.blur_type = tk.StringVar(value="gaussian")
        self.detect_faces = tk.BooleanVar(value=True)
        self.detect_license_plates = tk.BooleanVar(value=True)
        self.device = tk.StringVar(value="auto")
        self.pitch_shift = tk.DoubleVar(value=0.0)
        self.audio_preview_playing = False
        self.is_processing = False
        self.blurrer = None
        
        self.setup_ui()
        self.center_window()
    
    def center_window(self):
        self.root.update_idletasks()
        width = self.root.winfo_width()
        height = self.root.winfo_height()
        x = (self.root.winfo_screenwidth() // 2) - (width // 2)
        y = (self.root.winfo_screenheight() // 2) - (height // 2)
        self.root.geometry(f'{width}x{height}+{x}+{y}')
    
    def change_language(self, lang):
        self.language.set(lang)
        self.texts = LANGUAGES[lang]
        self.root.title(self.texts["title"])
        self.refresh_ui()
    
    def refresh_ui(self):
        for widget in self.main_frame.winfo_children():
            widget.destroy()
        self.setup_ui()
    
    def setup_ui(self):
        self.main_frame = ttk.Frame(self.root, padding="8")
        self.main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        self.main_frame.columnconfigure(1, weight=1)
        
        row = 0
        
        title_label = ttk.Label(self.main_frame, text="DefaceIT", font=("Arial", 18, "bold"))
        title_label.grid(row=row, column=0, columnspan=3, pady=(0, 5))
        row += 1
        
        lang_frame = ttk.Frame(self.main_frame)
        lang_frame.grid(row=row, column=0, columnspan=3, pady=2)
        ttk.Label(lang_frame, text=f"{self.texts['language']}:").pack(side=tk.LEFT, padx=5)
        ttk.Radiobutton(lang_frame, text=self.texts["english"], variable=self.language, value="en", command=lambda: self.change_language("en")).pack(side=tk.LEFT, padx=5)
        ttk.Radiobutton(lang_frame, text=self.texts["persian"], variable=self.language, value="fa", command=lambda: self.change_language("fa")).pack(side=tk.LEFT, padx=5)
        row += 1
        
        ttk.Label(self.main_frame, text=self.texts["input_video"], font=("Arial", 9)).grid(row=row, column=0, sticky=tk.W, pady=2)
        ttk.Entry(self.main_frame, textvariable=self.input_file, width=35).grid(row=row, column=1, sticky=(tk.W, tk.E), padx=3, pady=2)
        ttk.Button(self.main_frame, text=self.texts["browse"], command=self.browse_input, width=10).grid(row=row, column=2, pady=2, padx=2)
        row += 1
        
        ttk.Label(self.main_frame, text=self.texts["output_video"], font=("Arial", 9)).grid(row=row, column=0, sticky=tk.W, pady=2)
        ttk.Entry(self.main_frame, textvariable=self.output_file, width=35).grid(row=row, column=1, sticky=(tk.W, tk.E), padx=3, pady=2)
        ttk.Button(self.main_frame, text=self.texts["browse"], command=self.browse_output, width=10).grid(row=row, column=2, pady=2, padx=2)
        row += 1
        
        ttk.Separator(self.main_frame, orient=tk.HORIZONTAL).grid(row=row, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=8)
        row += 1
        
        settings_label = ttk.Label(self.main_frame, text=self.texts["settings"], font=("Arial", 10, "bold"))
        settings_label.grid(row=row, column=0, columnspan=3, sticky=tk.W, pady=(0, 5))
        row += 1
        
        ttk.Label(self.main_frame, text=self.texts["blur_strength"]).grid(row=row, column=0, sticky=tk.W, pady=2)
        blur_frame = ttk.Frame(self.main_frame)
        blur_frame.grid(row=row, column=1, columnspan=2, sticky=(tk.W, tk.E), padx=3, pady=2)
        blur_scale = ttk.Scale(blur_frame, from_=21, to=101, variable=self.blur_strength, orient=tk.HORIZONTAL, length=200, command=self.update_blur_label)
        blur_scale.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.blur_label = ttk.Label(blur_frame, text="51", font=("Arial", 8))
        self.blur_label.pack(side=tk.LEFT, padx=3)
        row += 1
        
        ttk.Label(self.main_frame, text=self.texts["confidence"]).grid(row=row, column=0, sticky=tk.W, pady=2)
        conf_frame = ttk.Frame(self.main_frame)
        conf_frame.grid(row=row, column=1, columnspan=2, sticky=(tk.W, tk.E), padx=3, pady=2)
        conf_scale = ttk.Scale(conf_frame, from_=0.05, to=0.5, variable=self.confidence, orient=tk.HORIZONTAL, length=200, command=self.update_conf_label)
        conf_scale.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.conf_label = ttk.Label(conf_frame, text="0.15", font=("Arial", 8))
        self.conf_label.pack(side=tk.LEFT, padx=3)
        row += 1
        
        ttk.Label(self.main_frame, text=self.texts["blur_type"]).grid(row=row, column=0, sticky=tk.W, pady=2)
        blur_type_frame = ttk.Frame(self.main_frame)
        blur_type_frame.grid(row=row, column=1, columnspan=2, sticky=tk.W, padx=3, pady=2)
        ttk.Radiobutton(blur_type_frame, text=self.texts["gaussian"], variable=self.blur_type, value="gaussian").pack(side=tk.LEFT, padx=3)
        ttk.Radiobutton(blur_type_frame, text=self.texts["pixelate"], variable=self.blur_type, value="pixelate").pack(side=tk.LEFT, padx=3)
        row += 1
        
        ttk.Label(self.main_frame, text=self.texts["detect"]).grid(row=row, column=0, sticky=tk.W, pady=2)
        detect_frame = ttk.Frame(self.main_frame)
        detect_frame.grid(row=row, column=1, columnspan=2, sticky=tk.W, padx=3, pady=2)
        ttk.Checkbutton(detect_frame, text=self.texts["faces"], variable=self.detect_faces).pack(side=tk.LEFT, padx=3)
        ttk.Checkbutton(detect_frame, text=self.texts["license_plates"], variable=self.detect_license_plates).pack(side=tk.LEFT, padx=3)
        row += 1
        
        ttk.Label(self.main_frame, text=self.texts["device"]).grid(row=row, column=0, sticky=tk.W, pady=2)
        device_frame = ttk.Frame(self.main_frame)
        device_frame.grid(row=row, column=1, columnspan=2, sticky=tk.W, padx=3, pady=2)
        ttk.Radiobutton(device_frame, text=self.texts["auto"], variable=self.device, value="auto").pack(side=tk.LEFT, padx=3)
        ttk.Radiobutton(device_frame, text=self.texts["cpu"], variable=self.device, value="cpu").pack(side=tk.LEFT, padx=3)
        ttk.Radiobutton(device_frame, text=self.texts["gpu"], variable=self.device, value="cuda").pack(side=tk.LEFT, padx=3)
        row += 1
        
        ttk.Separator(self.main_frame, orient=tk.HORIZONTAL).grid(row=row, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=6)
        row += 1
        
        audio_label = ttk.Label(self.main_frame, text=self.texts["audio_pitch_shift"], font=("Arial", 10, "bold"))
        audio_label.grid(row=row, column=0, columnspan=3, sticky=tk.W, pady=(0, 3))
        row += 1
        
        ttk.Label(self.main_frame, text=self.texts["pitch_semitones"]).grid(row=row, column=0, sticky=tk.W, pady=2)
        pitch_frame = ttk.Frame(self.main_frame)
        pitch_frame.grid(row=row, column=1, columnspan=2, sticky=(tk.W, tk.E), padx=3, pady=2)
        pitch_scale = ttk.Scale(pitch_frame, from_=-12, to=12, variable=self.pitch_shift, orient=tk.HORIZONTAL, length=200, command=self.update_pitch_label)
        pitch_scale.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.pitch_label = ttk.Label(pitch_frame, text="0.0", font=("Arial", 8))
        self.pitch_label.pack(side=tk.LEFT, padx=3)
        row += 1
        
        preview_frame = ttk.Frame(self.main_frame)
        preview_frame.grid(row=row, column=1, columnspan=2, sticky=tk.W, padx=3, pady=2)
        self.preview_button = ttk.Button(preview_frame, text=self.texts["preview_audio"], command=self.preview_audio, width=12)
        self.preview_button.pack(side=tk.LEFT, padx=2)
        self.stop_preview_button = ttk.Button(preview_frame, text=self.texts["stop_preview"], command=self.stop_preview, width=12, state=tk.DISABLED)
        self.stop_preview_button.pack(side=tk.LEFT, padx=2)
        row += 1
        
        ttk.Separator(self.main_frame, orient=tk.HORIZONTAL).grid(row=row, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=6)
        row += 1
        
        self.progress_var = tk.DoubleVar()
        ttk.Label(self.main_frame, text=self.texts["progress"], font=("Arial", 9)).grid(row=row, column=0, sticky=tk.W, pady=2)
        self.progress_bar = ttk.Progressbar(self.main_frame, variable=self.progress_var, maximum=100, length=300)
        self.progress_bar.grid(row=row, column=1, columnspan=2, sticky=(tk.W, tk.E), padx=3, pady=2)
        row += 1
        
        self.status_label = ttk.Label(self.main_frame, text=self.texts["ready"], foreground="green", font=("Arial", 8))
        self.status_label.grid(row=row, column=0, columnspan=3, pady=2)
        row += 1
        
        self.fps_label = ttk.Label(self.main_frame, text="", font=("Arial", 8))
        self.fps_label.grid(row=row, column=0, columnspan=3, pady=1)
        row += 1
        
        button_frame = ttk.Frame(self.main_frame)
        button_frame.grid(row=row, column=0, columnspan=3, pady=8)
        
        self.process_button = ttk.Button(button_frame, text=self.texts["start_processing"], command=self.start_processing, width=18)
        self.process_button.pack(side=tk.LEFT, padx=3)
        
        self.cancel_button = ttk.Button(button_frame, text=self.texts["cancel"], command=self.cancel_processing, width=18, state=tk.DISABLED)
        self.cancel_button.pack(side=tk.LEFT, padx=3)
        row += 1
        
        ttk.Separator(self.main_frame, orient=tk.HORIZONTAL).grid(row=row, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=6)
        row += 1
        
        credits_label = ttk.Label(self.main_frame, text=self.texts["credits"], font=("Arial", 10, "bold"))
        credits_label.grid(row=row, column=0, columnspan=3, sticky=tk.W, pady=(0, 3))
        row += 1
        
        credits_frame = ttk.Frame(self.main_frame)
        credits_frame.grid(row=row, column=0, columnspan=3, sticky=tk.W, padx=3)
        
        dev_frame = ttk.Frame(credits_frame)
        dev_frame.grid(row=0, column=0, sticky=tk.W, pady=1)
        ttk.Label(dev_frame, text=f"{self.texts['developer']} ", font=("Arial", 8)).pack(side=tk.LEFT)
        dev_link = ttk.Label(dev_frame, text=CREDITS["developer"], font=("Arial", 8), foreground="red", cursor="hand2")
        dev_link.pack(side=tk.LEFT)
        dev_link.bind("<Button-1>", lambda e: webbrowser.open(CREDITS["x"]))
        
        link_frame = ttk.Frame(credits_frame)
        link_frame.grid(row=1, column=0, sticky=tk.W, pady=1)
        ttk.Label(link_frame, text=f"{self.texts['website']} ", font=("Arial", 8), foreground="red", cursor="hand2").pack(side=tk.LEFT)
        website_link = ttk.Label(link_frame, text=CREDITS["website"], font=("Arial", 8), foreground="red", cursor="hand2")
        website_link.pack(side=tk.LEFT)
        website_link.bind("<Button-1>", lambda e: webbrowser.open(CREDITS["website"]))
        
        link_frame2 = ttk.Frame(credits_frame)
        link_frame2.grid(row=2, column=0, sticky=tk.W, pady=1)
        ttk.Label(link_frame2, text=f"{self.texts['telegram']} ", font=("Arial", 8), foreground="red", cursor="hand2").pack(side=tk.LEFT)
        telegram_link = ttk.Label(link_frame2, text=CREDITS["telegram"], font=("Arial", 8), foreground="red", cursor="hand2")
        telegram_link.pack(side=tk.LEFT)
        telegram_link.bind("<Button-1>", lambda e: webbrowser.open(CREDITS["telegram"]))
        
        link_frame3 = ttk.Frame(credits_frame)
        link_frame3.grid(row=3, column=0, sticky=tk.W, pady=1)
        ttk.Label(link_frame3, text=f"{self.texts['donate_crypto']} ", font=("Arial", 8), foreground="red", cursor="hand2").pack(side=tk.LEFT)
        crypto_link = ttk.Label(link_frame3, text=CREDITS["donate_crypto"], font=("Arial", 8), foreground="red", cursor="hand2")
        crypto_link.pack(side=tk.LEFT)
        crypto_link.bind("<Button-1>", lambda e: webbrowser.open(CREDITS["donate_crypto"]))
        
        link_frame4 = ttk.Frame(credits_frame)
        link_frame4.grid(row=4, column=0, sticky=tk.W, pady=1)
        ttk.Label(link_frame4, text=f"{self.texts['donate_card']} ", font=("Arial", 8), foreground="red", cursor="hand2").pack(side=tk.LEFT)
        card_link = ttk.Label(link_frame4, text=CREDITS["donate_card"], font=("Arial", 8), foreground="red", cursor="hand2")
        card_link.pack(side=tk.LEFT)
        card_link.bind("<Button-1>", lambda e: webbrowser.open(CREDITS["donate_card"]))
        
        for i in range(row + 1):
            self.main_frame.rowconfigure(i, weight=0)
    
    def update_blur_label(self, value=None):
        self.blur_label.config(text=str(self.blur_strength.get()))
    
    def update_conf_label(self, value=None):
        self.conf_label.config(text=f"{self.confidence.get():.2f}")
    
    def update_pitch_label(self, value=None):
        pitch_val = self.pitch_shift.get()
        self.pitch_label.config(text=f"{pitch_val:+.1f}")
    
    def browse_input(self):
        filename = filedialog.askopenfilename(
            title="Select Input Video",
            filetypes=[
                ("Video files", "*.mp4 *.avi *.mov *.mkv *.flv *.wmv"),
                ("MP4 files", "*.mp4"),
                ("All files", "*.*")
            ]
        )
        if filename:
            self.input_file.set(filename)
            if not self.output_file.get():
                input_path = Path(filename)
                output_path = input_path.parent / f"{input_path.stem}_blurred{input_path.suffix}"
                self.output_file.set(str(output_path))
    
    def browse_output(self):
        filename = filedialog.asksaveasfilename(
            title="Save Output Video As",
            defaultextension=".mp4",
            filetypes=[
                ("MP4 files", "*.mp4"),
                ("Video files", "*.mp4 *.avi *.mov"),
                ("All files", "*.*")
            ]
        )
        if filename:
            self.output_file.set(filename)
    
    def update_progress(self, progress, fps, status):
        self.progress_var.set(progress)
        self.status_label.config(text=status)
        if fps > 0:
            self.fps_label.config(text=f"{self.texts['processing_speed']} {fps:.1f} {self.texts['fps']}")
        self.root.update_idletasks()
    
    def start_processing(self):
        if not self.input_file.get():
            messagebox.showerror("Error", self.texts["error_no_input"])
            return
        
        if not self.output_file.get():
            messagebox.showerror("Error", self.texts["error_no_output"])
            return
        
        if not Path(self.input_file.get()).exists():
            messagebox.showerror("Error", self.texts["error_file_not_found"])
            return
        
        self.is_processing = True
        self.process_button.config(state=tk.DISABLED)
        self.cancel_button.config(state=tk.NORMAL)
        self.progress_var.set(0)
        self.status_label.config(text="Initializing...", foreground="blue")
        self.fps_label.config(text="")
        
        thread = threading.Thread(target=self.process_video_thread, daemon=True)
        thread.start()
    
    def process_video_thread(self):
        try:
            self.blurrer = VideoBlurrer(
                device=self.device.get(),
                blur_strength=self.blur_strength.get(),
                blur_type=self.blur_type.get(),
                confidence=self.confidence.get(),
                detect_faces=self.detect_faces.get(),
                detect_license_plates=self.detect_license_plates.get(),
                progress_callback=self.update_progress,
                pitch_shift=self.pitch_shift.get()
            )
            
            success, message = self.blurrer.process_video(
                self.input_file.get(),
                self.output_file.get()
            )
            
            self.root.after(0, self.processing_complete, success, message)
            
        except Exception as e:
            self.root.after(0, self.processing_complete, False, f"Error: {str(e)}")
    
    def processing_complete(self, success, message):
        self.is_processing = False
        self.process_button.config(state=tk.NORMAL)
        self.cancel_button.config(state=tk.DISABLED)
        
        if success:
            self.status_label.config(text="Complete!", foreground="green")
            messagebox.showinfo("Success", f"{self.texts['success_complete']}\n\n{message}\n\n{self.texts['output_video']}:\n{self.output_file.get()}")
        else:
            self.status_label.config(text="Failed", foreground="red")
            messagebox.showerror("Error", message)
    
    def cancel_processing(self):
        if self.blurrer:
            self.blurrer.cancel()
        self.status_label.config(text="Cancelling...", foreground="orange")
    
    def preview_audio(self):
        if not self.input_file.get() or not Path(self.input_file.get()).exists():
            messagebox.showerror("Error", self.texts["error_preview_no_file"])
            return
        
        if self.audio_preview_playing:
            self.stop_preview()
            return
        
        pitch_val = self.pitch_shift.get()
        if abs(pitch_val) < 0.01:
            messagebox.showinfo("Info", self.texts["info_no_pitch"])
            return
        
        self.audio_preview_playing = True
        self.preview_button.config(state=tk.DISABLED)
        self.stop_preview_button.config(state=tk.NORMAL)
        self.status_label.config(text="Loading audio preview...", foreground="blue")
        
        thread = threading.Thread(target=self._preview_audio_thread, daemon=True)
        thread.start()
    
    def _preview_audio_thread(self):
        try:
            import librosa
            import soundfile as sf
            
            input_path = self.input_file.get()
            pitch_val = self.pitch_shift.get()
            
            temp_audio = tempfile.NamedTemporaryFile(suffix='.wav', delete=False)
            temp_audio.close()
            
            extract_cmd = [
                'ffmpeg', '-i', input_path,
                '-vn', '-acodec', 'pcm_s16le',
                '-t', '10',
                '-y', temp_audio.name
            ]
            
            result = subprocess.run(
                extract_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            if result.returncode != 0:
                self.root.after(0, lambda: self._preview_error("Could not extract audio from video"))
                return
            
            y, sr = librosa.load(temp_audio.name, sr=None)
            y_shifted = librosa.effects.pitch_shift(y, sr=sr, n_steps=pitch_val)
            
            shifted_audio = tempfile.NamedTemporaryFile(suffix='.wav', delete=False)
            shifted_audio.close()
            sf.write(shifted_audio.name, y_shifted, sr)
            
            if platform.system() == 'Darwin':
                player = 'afplay'
            elif platform.system() == 'Linux':
                player = 'aplay'
            else:
                player = 'start'
            
            if platform.system() == 'Windows':
                subprocess.Popen([player, shifted_audio.name], shell=True)
            else:
                subprocess.Popen([player, shifted_audio.name])
            
            self.root.after(0, lambda: self.status_label.config(text="Playing preview...", foreground="green"))
            
            duration = len(y_shifted) / sr
            time.sleep(min(duration + 1, 11))
            
            if os.path.exists(temp_audio.name):
                os.remove(temp_audio.name)
            if os.path.exists(shifted_audio.name):
                os.remove(shifted_audio.name)
            
            self.root.after(0, self._preview_complete)
            
        except ImportError:
            self.root.after(0, lambda: self._preview_error("librosa not installed. Run: pip install librosa soundfile"))
        except Exception as e:
            self.root.after(0, lambda: self._preview_error(f"Preview error: {str(e)}"))
    
    def _preview_error(self, message):
        self.audio_preview_playing = False
        self.preview_button.config(state=tk.NORMAL)
        self.stop_preview_button.config(state=tk.DISABLED)
        self.status_label.config(text=self.texts["ready"], foreground="green")
        messagebox.showerror("Preview Error", message)
    
    def _preview_complete(self):
        self.audio_preview_playing = False
        self.preview_button.config(state=tk.NORMAL)
        self.stop_preview_button.config(state=tk.DISABLED)
        self.status_label.config(text="Preview complete", foreground="green")
    
    def stop_preview(self):
        self.audio_preview_playing = False
        self.preview_button.config(state=tk.NORMAL)
        self.stop_preview_button.config(state=tk.DISABLED)
        self.status_label.config(text=self.texts["ready"], foreground="green")


def main():
    root = tk.Tk()
    app = DefaceITApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()

