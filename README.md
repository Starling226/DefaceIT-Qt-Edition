# DefaceIT

<p align="center">
  <a href="#defaceit-فارسی">راهنمای فارسی</a> | <a href="#defaceit-فارسی">Persian Guide</a>
</p>

DefaceIT is a cross-platform application for blurring faces and license plates in videos using YOLOv11. The app supports both English and Persian languages and is available for desktop (macOS, Linux, Windows) and Android.

## Features

- Easy to use graphical interface
- Fast processing with GPU acceleration support (CUDA, MPS, CPU)
- Accurate detection using YOLOv11-based face and license plate detection
- Audio preservation with automatic audio merging
- Audio pitch shifting with preview functionality
- Cross-platform support (macOS, Linux, Windows, Android)
- Bilingual interface (English and Persian)
- Customizable settings (blur strength, confidence, blur type)
- Native Android app with modern Material Design UI

## Requirements

- Python 3.8 or higher
- ffmpeg (for audio preservation)
  - macOS: `brew install ffmpeg`
  - Linux: `sudo apt-get install ffmpeg` (Ubuntu/Debian) or `sudo yum install ffmpeg` (RHEL/CentOS)
  - Windows: Download from [ffmpeg.org](https://ffmpeg.org/download.html)

## Installation

### macOS / Linux

1. Open Terminal
2. Navigate to the faceblur_app directory:
   ```bash
   cd faceblur_app
   ```
3. Run the setup script:
   ```bash
   chmod +x setup.sh
   ./setup.sh
   ```
4. Run the application:
   ```bash
   python run.py
   ```

The `run.py` script will automatically:
- Detect your operating system
- Use the virtual environment if available
- Fall back to system Python if needed
- Handle tkinter detection and errors

### Windows

1. Open Command Prompt or PowerShell
2. Navigate to the faceblur_app directory:
   ```cmd
   cd faceblur_app
   ```
3. Run the setup script:
   ```cmd
   setup.bat
   ```
4. Run the application:
   ```cmd
   python run.py
   ```

The `run.py` script will automatically:
- Detect your operating system
- Use the virtual environment if available
- Fall back to system Python if needed
- Handle tkinter detection and errors

### Docker (Web Interface - Recommended)

The easiest way to run DefaceIT is using Docker with a simple web interface. No need to install Python, dependencies, or deal with GUI complications.

#### Prerequisites

- Docker and Docker Compose installed ([Get Docker](https://docs.docker.com/get-docker/))

#### Quick Start

1. Clone the repository:
   ```bash
   git clone https://github.com/pourmand1376/DefaceIT.git
   cd DefaceIT
   ```

2. Start the application:
   ```bash
   docker-compose up
   ```

3. Open your browser and go to:
   ```
   http://localhost:8080
   ```

4. Upload your video, adjust settings, and process!

The web interface provides:
- Drag-and-drop video upload
- All processing settings (blur strength, confidence, device, etc.)
- Real-time progress tracking
- Direct download of processed videos

#### Using GPU (NVIDIA)

To enable GPU acceleration for faster processing:

1. Install [NVIDIA Container Toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/install-guide.html)

2. Uncomment the GPU section in `docker-compose.yml`:
   ```yaml
   deploy:
     resources:
       reservations:
         devices:
           - driver: nvidia
             count: all
             capabilities: [gpu]
   ```

3. Restart the application:
   ```bash
   docker-compose down
   docker-compose up
   ```

#### Stopping the Application

```bash
docker-compose down
```

## Usage

1. Launch the application using the instructions above
2. Click "Browse..." next to "Input Video" to select your video file
3. Optionally set the output location (auto-generated if not set)
4. Adjust settings:
   - **Blur Strength**: Higher values = more blur (21-101)
   - **Confidence**: Lower values = more detections (0.05-0.5)
   - **Blur Type**: Gaussian or Pixelate
   - **Detect**: Choose faces and/or license plates
   - **Device**: Auto-detect, CPU, or GPU
   - **Audio Pitch Shift**: Adjust pitch in semitones (-12 to +12)
5. Click "Preview Audio" to test the pitch shift (optional)
6. Click "Start Processing"
7. Wait for processing to complete
8. Your blurred video will be saved with audio preserved

## Android App

DefaceIT is also available as a native Android application with a modern Material Design interface.

### Download

Download the latest release APK from the [Releases](https://github.com/therealaleph/DefaceIT/releases) page or build it yourself.

### Requirements

- Android 7.0 (API level 24) or higher
- Camera permission (optional, for future camera features)
- Storage permission (for reading and saving videos)

### Installation

1. Download the `DefaceIT-release.apk` from the releases page
2. Enable "Install from Unknown Sources" in your Android settings
3. Open the downloaded APK file
4. Follow the installation prompts

### Features

- Modern Material Design 3 UI built with Jetpack Compose
- Face detection using Google ML Kit
- Real-time video processing
- Audio pitch shifting support
- Bilingual interface (English and Persian)
- Same powerful blurring capabilities as the desktop version

### Building from Source

To build the Android app from source:

1. Open the project in Android Studio
2. Sync Gradle dependencies
3. Build the release APK:
   ```bash
   cd DefaceIT
   ./gradlew assembleRelease
   ```
4. The APK will be located at `DefaceIT/app/build/outputs/apk/release/`

## Building Standalone Executable

### Using PyInstaller

```bash
pip install pyinstaller
pyinstaller --onefile --windowed --name DefaceIT defaceit_gui.py
```

The executable will be in the `dist` folder.

## Troubleshooting

### Tkinter Not Found Error

If you see: `ModuleNotFoundError: No module named '_tkinter'`

**macOS Solutions:**
- Option 1: Use System Python (Recommended)
  ```bash
  /usr/bin/python3 defaceit_gui.py
  ```
- Option 2: Install python-tk for Homebrew Python
  ```bash
  brew install python-tk
  ```
- Option 3: Use the macOS launcher script
  ```bash
  ./run_macos.sh
  ```

**Linux Solutions:**
```bash
# Ubuntu/Debian
sudo apt-get install python3-tk

# RHEL/CentOS/Fedora
sudo yum install python3-tk
# or
sudo dnf install python3-tk
```

**Windows Solutions:**
Tkinter should be included with Python. If not:
1. Reinstall Python from python.org
2. Make sure "tcl/tk and IDLE" is checked during installation

### Virtual Environment Issues

If tkinter doesn't work in your venv:

**Option 1: Use system Python directly**
```bash
python3 defaceit_gui.py
```

**Option 2: Install dependencies globally (not recommended)**
```bash
pip3 install -r requirements.txt
python3 defaceit_gui.py
```

### Other Common Issues

- **No audio in output**: Make sure ffmpeg is installed and in your PATH
- **Slow processing**: Try using GPU acceleration or lower video resolution
- **Missing faces**: Lower the confidence threshold (try 0.1)
- **Too much blur**: Reduce blur strength
- **App runs but is slow**: Make sure GPU acceleration is enabled (select "Auto" or "GPU" in device settings)
- **Faces not being detected**: Lower the confidence threshold, increase blur strength for better coverage, make sure "Detect Faces" is checked
- **librosa not installed**: Run `pip install librosa soundfile` for audio pitch shifting features

## Notes

- First run will download YOLOv11n model (~5.4MB)
- Processing speed depends on your hardware (GPU recommended)
- Audio preservation requires ffmpeg to be installed
- Large videos may take some time to process

## Credits

**Developer:** [Shin](https://x.com/hey_itsmyturn)

- **X (Twitter):** [@hey_itsmyturn](https://x.com/hey_itsmyturn)
- **Website:** [https://sh1n.org](https://sh1n.org)
- **Telegram:** [https://t.me/itsthealephyouknowfromtwitter](https://t.me/itsthealephyouknowfromtwitter)

### Support the Developer

- **Donate (Crypto):** [https://nowpayments.io/donation/shin](https://nowpayments.io/donation/shin)
- **Donate (Card):** [https://buymeacoffee.com/hey_itsmyturn](https://buymeacoffee.com/hey_itsmyturn)

**Note:** Translation and Readme was generated by Cursor AI

---

<a id="defaceit-فارسی"></a>
# DefaceIT (فارسی)

DefaceIT یک برنامه چند پلتفرمی برای تار کردن چهره‌ها و پلاک‌ها در ویدیوها با استفاده از YOLOv11 است. این برنامه از زبان‌های انگلیسی و فارسی پشتیبانی می‌کند و برای دسکتاپ (macOS, Linux, Windows) و اندروید در دسترس است.

## ویژگی‌ها

- رابط گرافیکی ساده
- پردازش سریع با پشتیبانی از شتاب GPU (CUDA, MPS, CPU)
- تشخیص دقیق با استفاده از YOLOv11
- حفظ صدا با ادغام خودکار صدا
- تغییر زیر و بم صدا با قابلیت پیش‌نمایش
- پشتیبانی از چند پلتفرم (macOS, Linux, Windows, Android)
- رابط دو زبانه (انگلیسی و فارسی)
- تنظیمات قابل تنظیم
- برنامه اندروید بومی با رابط کاربری Material Design مدرن

## نیازمندی‌ها

- Python 3.8 یا بالاتر
- ffmpeg (برای حفظ صدا)
  - macOS: `brew install ffmpeg`
  - Linux: `sudo apt-get install ffmpeg` (Ubuntu/Debian) یا `sudo yum install ffmpeg` (RHEL/CentOS)
  - Windows: از [ffmpeg.org](https://ffmpeg.org/download.html) دانلود کنید

## نصب

### macOS / Linux

1. Terminal را باز کنید
2. به پوشه faceblur_app بروید:
   ```bash
   cd faceblur_app
   ```
3. اسکریپت نصب را اجرا کنید:
   ```bash
   chmod +x setup.sh
   ./setup.sh
   ```
4. برنامه را اجرا کنید:
   ```bash
   python run.py
   ```

اسکریپت `run.py` به صورت خودکار:
- سیستم عامل شما را تشخیص می‌دهد
- در صورت وجود از محیط مجازی استفاده می‌کند
- در صورت نیاز به Python سیستم بازمی‌گردد
- تشخیص tkinter و خطاها را مدیریت می‌کند

### Windows

1. Command Prompt یا PowerShell را باز کنید
2. به پوشه faceblur_app بروید:
   ```cmd
   cd faceblur_app
   ```
3. اسکریپت نصب را اجرا کنید:
   ```cmd
   setup.bat
   ```
4. برنامه را اجرا کنید:
   ```cmd
   python run.py
   ```

اسکریپت `run.py` به صورت خودکار:
- سیستم عامل شما را تشخیص می‌دهد
- در صورت وجود از محیط مجازی استفاده می‌کند
- در صورت نیاز به Python سیستم بازمی‌گردد
- تشخیص tkinter و خطاها را مدیریت می‌کند

### Docker (رابط وب - توصیه می‌شود)

ساده‌ترین راه برای اجرای DefaceIT استفاده از Docker با یک رابط وب ساده است. نیازی به نصب Python، وابستگی‌ها یا مشکلات رابط گرافیکی نیست.

#### پیش‌نیازها

- Docker و Docker Compose نصب شده باشد ([دریافت Docker](https://docs.docker.com/get-docker/))

#### شروع سریع

1. مخزن را کلون کنید:
   ```bash
   git clone https://github.com/pourmand1376/DefaceIT.git
   cd DefaceIT
   ```

2. برنامه را اجرا کنید:
   ```bash
   docker-compose up
   ```

3. مرورگر خود را باز کنید و به آدرس زیر بروید:
   ```
   http://localhost:8080
   ```

4. ویدیوی خود را آپلود کنید، تنظیمات را تنظیم کنید و پردازش کنید!

رابط وب شامل موارد زیر است:
- آپلود ویدیو با کشیدن و رها کردن
- تمام تنظیمات پردازش (قدرت تار کردن، اعتماد، دستگاه و غیره)
- پیگیری پیشرفت در زمان واقعی
- دانلود مستقیم ویدیوهای پردازش شده

#### استفاده از GPU (NVIDIA)

برای فعال‌سازی شتاب GPU برای پردازش سریع‌تر:

1. [NVIDIA Container Toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/install-guide.html) را نصب کنید

2. بخش GPU را در `docker-compose.yml` از حالت توضیح خارج کنید:
   ```yaml
   deploy:
     resources:
       reservations:
         devices:
           - driver: nvidia
             count: all
             capabilities: [gpu]
   ```

3. برنامه را مجدداً راه‌اندازی کنید:
   ```bash
   docker-compose down
   docker-compose up
   ```

#### متوقف کردن برنامه

```bash
docker-compose down
```

## استفاده

1. برنامه را با دستورالعمل‌های بالا اجرا کنید
2. روی "مرور..." کنار "ویدیوی ورودی" کلیک کنید تا فایل ویدیوی خود را انتخاب کنید
3. به صورت اختیاری مکان خروجی را تنظیم کنید (در صورت عدم تنظیم، به صورت خودکار تولید می‌شود)
4. تنظیمات را تنظیم کنید:
   - **قدرت تار کردن**: مقادیر بالاتر = تار بیشتر (21-101)
   - **اعتماد**: مقادیر پایین‌تر = تشخیص بیشتر (0.05-0.5)
   - **نوع تار کردن**: گاوسی یا پیکسلی
   - **تشخیص**: چهره‌ها و/یا پلاک‌ها را انتخاب کنید
   - **دستگاه**: خودکار، CPU، یا GPU
   - **تغییر زیر و بم صدا**: زیر و بم را در نیم‌پرده تنظیم کنید (-12 تا +12)
5. روی "پیش‌نمایش صدا" کلیک کنید تا تغییر زیر و بم را تست کنید (اختیاری)
6. روی "شروع پردازش" کلیک کنید
7. منتظر بمانید تا پردازش کامل شود
8. ویدیوی تار شده شما با صدا حفظ شده ذخیره می‌شود

## برنامه اندروید

DefaceIT همچنین به عنوان یک برنامه اندروید بومی با رابط کاربری Material Design مدرن در دسترس است.

### دانلود

آخرین نسخه APK را از صفحه [Releases](https://github.com/therealaleph/DefaceIT/releases) دانلود کنید یا خودتان آن را بسازید.

### نیازمندی‌ها

- اندروید 7.0 (سطح API 24) یا بالاتر
- مجوز دوربین (اختیاری، برای ویژگی‌های آینده دوربین)
- مجوز ذخیره‌سازی (برای خواندن و ذخیره ویدیوها)

### نصب

1. فایل `DefaceIT-release.apk` را از صفحه releases دانلود کنید
2. "نصب از منابع ناشناخته" را در تنظیمات اندروید خود فعال کنید
3. فایل APK دانلود شده را باز کنید
4. دستورالعمل‌های نصب را دنبال کنید

### ویژگی‌ها

- رابط کاربری Material Design 3 مدرن ساخته شده با Jetpack Compose
- تشخیص چهره با استفاده از Google ML Kit
- پردازش ویدیو در زمان واقعی
- پشتیبانی از تغییر زیر و بم صدا
- رابط دو زبانه (انگلیسی و فارسی)
- همان قابلیت‌های قدرتمند تار کردن نسخه دسکتاپ

### ساخت از منبع

برای ساخت برنامه اندروید از منبع:

1. پروژه را در Android Studio باز کنید
2. وابستگی‌های Gradle را همگام‌سازی کنید
3. APK نسخه release را بسازید:
   ```bash
   cd DefaceIT
   ./gradlew assembleRelease
   ```
4. فایل APK در مسیر `DefaceIT/app/build/outputs/apk/release/` قرار خواهد گرفت

## ساخت فایل اجرایی مستقل

### استفاده از PyInstaller

```bash
pip install pyinstaller
pyinstaller --onefile --windowed --name DefaceIT defaceit_gui.py
```

فایل اجرایی در پوشه `dist` خواهد بود.

## عیب‌یابی

### خطای Tkinter پیدا نشد

اگر این خطا را می‌بینید: `ModuleNotFoundError: No module named '_tkinter'`

**راه‌حل‌های macOS:**
- گزینه 1: استفاده از Python سیستم (توصیه می‌شود)
  ```bash
  /usr/bin/python3 defaceit_gui.py
  ```
- گزینه 2: نصب python-tk برای Homebrew Python
  ```bash
  brew install python-tk
  ```
- گزینه 3: استفاده از اسکریپت راه‌انداز macOS
  ```bash
  ./run_macos.sh
  ```

**راه‌حل‌های Linux:**
```bash
# Ubuntu/Debian
sudo apt-get install python3-tk

# RHEL/CentOS/Fedora
sudo yum install python3-tk
# یا
sudo dnf install python3-tk
```

**راه‌حل‌های Windows:**
Tkinter باید با Python همراه باشد. اگر نیست:
1. Python را از python.org دوباره نصب کنید
2. مطمئن شوید "tcl/tk and IDLE" در طول نصب انتخاب شده است

### مشکلات محیط مجازی

اگر tkinter در venv شما کار نمی‌کند:

**گزینه 1: استفاده مستقیم از Python سیستم**
```bash
python3 defaceit_gui.py
```

**گزینه 2: نصب وابستگی‌ها به صورت سراسری (توصیه نمی‌شود)**
```bash
pip3 install -r requirements.txt
python3 defaceit_gui.py
```

### مشکلات رایج دیگر

- **بدون صدا در خروجی**: مطمئن شوید ffmpeg نصب شده و در PATH است
- **پردازش کند**: از شتاب GPU استفاده کنید یا وضوح ویدیو را کاهش دهید
- **چهره‌های از دست رفته**: آستانه اعتماد را کاهش دهید (0.1 را امتحان کنید)
- **تار بیش از حد**: قدرت تار کردن را کاهش دهید
- **برنامه کند اجرا می‌شود**: مطمئن شوید شتاب GPU فعال است (در تنظیمات دستگاه "Auto" یا "GPU" را انتخاب کنید)
- **چهره‌ها تشخیص داده نمی‌شوند**: آستانه اعتماد را کاهش دهید، قدرت تار کردن را برای پوشش بهتر افزایش دهید، مطمئن شوید "تشخیص چهره‌ها" انتخاب شده است
- **librosa نصب نشده**: برای ویژگی‌های تغییر زیر و بم صدا `pip install librosa soundfile` را اجرا کنید

## یادداشت‌ها

- اولین اجرا مدل YOLOv11n را دانلود می‌کند (~5.4MB)
- سرعت پردازش به سخت‌افزار شما بستگی دارد (GPU توصیه می‌شود)
- حفظ صدا نیاز به نصب ffmpeg دارد
- ویدیوهای بزرگ ممکن است زمان زیادی ببرد

## Credits

**توسعه‌دهنده:** [Shin](https://x.com/hey_itsmyturn)

- **X (توییتر):** [@hey_itsmyturn](https://x.com/hey_itsmyturn)
- **وب‌سایت:** [https://sh1n.org](https://sh1n.org)
- **تلگرام:** [https://t.me/itsthealephyouknowfromtwitter](https://t.me/itsthealephyouknowfromtwitter)

### حمایت از توسعه‌دهنده

- **حمایت (ارز دیجیتال):** [https://nowpayments.io/donation/shin](https://nowpayments.io/donation/shin)
- **حمایت (کارت):** [https://buymeacoffee.com/hey_itsmyturn](https://buymeacoffee.com/hey_itsmyturn)

**یادداشت:** ترجمه و راهنما توسط Cursor AI تولید شده است
