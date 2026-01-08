# DefaceIT Qt-Edition

<p align="center">
  <a href="#defaceit-فارسی">راهنمای فارسی</a> | <a href="#defaceit-فارسی">Persian Guide</a>
</p>

DefaceIT is a cross-platform application for blurring faces and license plates in videos using YOLOv11. The app supports both English and Persian languages and is available for desktop (macOS, Linux, Windows).

## Features

- Modern Qt graphical inrerface.
- Easy and flexible inrerface to use.
- Saving the the blurred videos using H264 codec
- Some bugs have been fixed
- Automatically checks if system Graphics Card is supported and falling back to CPU if not
- Fast processing with GPU acceleration support (CUDA, MPS, CPU)
- Accurate detection using YOLOv11-based face and license plate detection
- Audio preservation with automatic audio merging
- Audio pitch shifting with preview functionality
- Cross-platform support (macOS, Linux, Windows)
- Bilingual interface (English and Persian)
- Customizable settings (blur strength, confidence, blur type)

## Requirements

- Python 3.8 or higher python-3.11.6 has been tested successfully. Latest python has compatbility issues and failed to install numpy in Windows.
- ffmpeg (for video re-encoding and audio preservation)
  - macOS: `brew install ffmpeg`
  - Linux: 
    Fedora/Rocky/AlmaLinux:  sudo dnf install python3-pyqt5 qt5-qtbase ffmpeg mesa-libGL
    Ubuntu/Debian: sudo apt update && sudo apt install python3-pyqt5 ffmpeg libgl1-mesa-glx    
  - Windows: see Windows section under Installation

## Installation

### macOS / Linux

1. Open Terminal
2. Navigate to the DefaceIT directory:
   ```bash
   cd DefaceIT
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
- Handle PyQt5 detection and errors

### Windows

FFMPEG Installation:
Download the latest ffmpeg from
https://github.com/BtbN/FFmpeg-Builds/releases
and unzip and rename the directory to ffmpeg and copy to C:\

Download the Python-3.11.6 installation file for your system from 
https://www.python.org/downloads/windows/

Latest Python has compatibility issues.
Python installer does not add python to your Environment Variables after installation. You need to add them to your path manually. 
Find your python installation path. They are under:
C:\Users\Mark\AppData\Local\Programs\Python\Python311

In Windows Search field type: SystemPropertiesAdvanced.exe
This brings up the System Properties
click on
Environment Variables
Click on New for each of these
C:\Users\xxx\AppData\Local\Programs\Python\Python311
C:\Users\xxx\AppData\Local\Programs\Python\Python311\Scripts
Note: xxx is your user
C:\ffmpeg\bin

Move Up all three lines to the top
OK
OK

Navigate to the DefaceIT directory:
either,
double click on setup.bat
or,
1. Open Command Prompt or PowerShell
2. Navigate to the DefaceIT directory:
   ```cmd
   cd DefaceIT
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
- Handle PyQt detection and errors

#### Using GPU (NVIDIA)

To enable GPU acceleration for faster processing:

- Install NVIDIA Driver for your Nvidia Graphics Card https://www.nvidia.com/en-us/drivers/


## Issues and Troubleshooting
Window version may have issues with ffmpeg and may crash. Investigating...
macOS version has not been tested yet
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

**Developer:** [Starling226]Qt-Edition
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
# DefaceIT Qt-Edition (فارسی)
 
**DefaceIT** یک برنامه چندپلتفرمی برای تار کردن (بلور کردن) چهره‌ها و پلاک خودروها در ویدیوها با استفاده از **YOLOv11** است. این برنامه از زبان‌های انگلیسی و فارسی پشتیبانی می‌کند و برای دسکتاپ (macOS، لینوکس، ویندوز) در دسترس است.

## ویژگی‌ها
- رابط گرافیکی مدرن مبتنی بر Qt  
- رابط کاربری ساده و انعطاف‌پذیر  
- ذخیره ویدیوهای تار شده با کدک H264  
- رفع برخی باگ‌ها  
- بررسی خودکار پشتیبانی کارت گرافیک سیستم و بازگشت به CPU در صورت عدم پشتیبانی  
- پردازش سریع با پشتیبانی از شتاب‌دهی GPU (CUDA، MPS، CPU)  
- تشخیص دقیق با استفاده از مدل تشخیص چهره و پلاک مبتنی بر YOLOv11  
- حفظ صدا با ادغام خودکار صدا  
- تغییر زیر و بم صدا (Pitch Shifting) با قابلیت پیش‌نمایش  
- پشتیبانی چندپلتفرمی (macOS، لینوکس، ویندوز)  
- رابط کاربری دو زبانه (انگلیسی و فارسی)  
- تنظیمات قابل سفارشی‌سازی (قدرت تار کردن، آستانه اطمینان، نوع تار شدن)

## نیازمندی‌ها
- **پایتون** ۳٫۸ یا بالاتر (نسخه ۳٫۱۱٫۶ با موفقیت تست شده است. نسخه‌های جدیدتر پایتون در ویندوز با نصب numpy مشکل دارند)  
- **ffmpeg** (برای بازکدگذاری ویدیو و حفظ صدا)  
  - macOS: `brew install ffmpeg`  
  - لینوکس:  
    Fedora/Rocky/AlmaLinux: `sudo dnf install python3-pyqt5 qt5-qtbase ffmpeg mesa-libGL`  
    Ubuntu/Debian: `sudo apt update && sudo apt install python3-pyqt5 ffmpeg libgl1-mesa-glx`  
  - ویندوز: به بخش نصب ویندوز مراجعه کنید

## نصب

### macOS / لینوکس
۱. ترمینال را باز کنید  
۲. به پوشه DefaceIT بروید:  
   ```bash
   cd DefaceIT
   ```  
۳. اسکریپت نصب را اجرا کنید:  
   ```bash
   chmod +x setup.sh
   ./setup.sh
   ```  
۴. برنامه را اجرا کنید:  
   ```bash
   python run.py
   ```

اسکریپت `run.py` به صورت خودکار موارد زیر را انجام می‌دهد:  
- تشخیص سیستم‌عامل شما  
- استفاده از محیط مجازی در صورت وجود  
- بازگشت به پایتون سیستمی در صورت نیاز  
- مدیریت تشخیص PyQt5 و خطاها

### ویندوز

**نصب FFMPEG:**  
آخرین نسخه ffmpeg را از آدرس زیر دانلود کنید:  
https://github.com/BtbN/FFmpeg-Builds/releases  
فایل را از حالت فشرده خارج کنید، نام پوشه را به `ffmpeg` تغییر دهید و به درایو C:\ کپی کنید.

**نصب پایتون:**  
فایل نصبی **Python 3.11.6** را متناسب با سیستم خود از اینجا دانلود کنید:  
https://www.python.org/downloads/windows/  
(نسخه‌های جدیدتر پایتون مشکلات سازگاری دارند)

> **توجه:** نصب‌کننده پایتون به‌طور خودکار مسیر پایتون را به متغیرهای محیطی (Environment Variables) اضافه نمی‌کند. باید به‌صورت دستی اضافه کنید.

مسیر نصب پایتون معمولاً در این آدرس است:  
`C:\Users\Mark\AppData\Local\Programs\Python\Python311`

۱. در نوار جستجوی ویندوز عبارت `SystemPropertiesAdvanced.exe` را تایپ کنید  
۲. در بخش **Environment Variables** روی **New** کلیک کنید و مسیرهای زیر را اضافه کنید:  
   - `C:\Users\xxx\AppData\Local\Programs\Python\Python311`  
   - `C:\Users\xxx\AppData\Local\Programs\Python\Python311\Scripts`  
   - `C:\ffmpeg\bin`  
   (به جای xxx نام کاربری خود را قرار دهید)  

۳. هر سه مسیر را به بالای لیست منتقل کنید (Move Up)  
۴. OK → OK

**اجرای نصب:**  
به پوشه DefaceIT بروید و یکی از روش‌های زیر را انجام دهید:  
- دوبار کلیک روی فایل `setup.bat`  
یا  
۱. Command Prompt یا PowerShell را باز کنید  
۲. به پوشه DefaceIT بروید:  
   ```cmd
   cd DefaceIT
   ```  
۳. اسکریپت نصب را اجرا کنید:  
   ```cmd
   setup.bat
   ```  
۴. برنامه را اجرا کنید:  
   ```cmd
   python run.py
   ```

#### استفاده از GPU (انویدیا)
برای فعال‌سازی شتاب‌دهی GPU و پردازش سریع‌تر:  
- درایور NVIDIA مناسب کارت گرافیک خود را نصب کنید:  
  https://www.nvidia.com/en-us/drivers/

## مشکلات و رفع اشکال
نسخه ویندوز ممکن است با ffmpeg مشکل داشته باشد و کرش کند (در حال بررسی است...)  
نسخه macOS هنوز تست نشده است

### مشکلات رایج دیگر
- **عدم وجود صدا در خروجی**: مطمئن شوید ffmpeg نصب شده و در PATH سیستم قرار دارد  
- **پردازش کند**: از شتاب‌دهی GPU استفاده کنید یا رزولوشن ویدیو را کاهش دهید  
- **تشخیص نشدن برخی چهره‌ها**: آستانه اطمینان (confidence) را کاهش دهید (مثلاً به ۰٫۱)  
- **تار شدن بیش از حد**: قدرت تار کردن (blur strength) را کاهش دهید  
- **برنامه اجرا می‌شود اما کند است**: مطمئن شوید شتاب‌دهی GPU فعال است (در تنظیمات دستگاه گزینه "Auto" یا "GPU" را انتخاب کنید)  
- **تشخیص نشدن چهره‌ها**: آستانه اطمینان را کاهش دهید، قدرت تار کردن را افزایش دهید، مطمئن شوید گزینه "Detect Faces" فعال است  
- **عدم نصب librosa**: برای قابلیت تغییر زیر و بم صدا اجرا کنید:  
  `pip install librosa soundfile`

## نکات
- در اجرای اول، مدل YOLOv11n (~۵٫۴ مگابایت) دانلود می‌شود  
- سرعت پردازش به سخت‌افزار شما بستگی دارد (GPU توصیه می‌شود)  
- حفظ صدا نیازمند نصب ffmpeg است  
- ویدیوهای بزرگ به زمان بیشتری برای پردازش نیاز دارند

## اعتبارات
**توسعه‌دهنده (نسخه Qt):** Starling226  
**توسعه‌دهنده (نسخه Tk):** [Shin](https://x.com/hey_itsmyturn)  

- **توییتر (X):** [@hey_itsmyturn](https://x.com/hey_itsmyturn)  
- **وب‌سایت:** [https://sh1n.org](https://sh1n.org)  
- **تلگرام:** [https://t.me/itsthealephyouknowfromtwitter](https://t.me/itsthealephyouknowfromtwitter)

### حمایت از توسعه‌دهنده
- **حمایت مالی (کریپتو):** [https://nowpayments.io/donation/shin](https://nowpayments.io/donation/shin)  
- **حمایت مالی (کارت اعتباری):** [https://buymeacoffee.com/hey_itsmyturn](https://buymeacoffee.com/hey_itsmyturn)

**توجه:** ترجمه و فایل Readme توسط Cursor AI تولید شده است.

موفق باشید! 🚀
