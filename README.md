# FLOPROAST DOWNLOADER
### SIGNAL ACQUISITION TERMINAL

> *floppy · bacon · sushi*

A YouTube downloader wrapped in a Deus Ex green terminal aesthetic with a Skinny Puppy industrial soul. Features a real-time Mandelbrot fractal background that breathes and pulses to the background music, a download library browser with thumbnail grids, and a Windows 98-style setup wizard.

---

## FEATURES

- **YouTube download** — video (best/1080p/720p/480p/360p) or audio MP3 via yt-dlp
- **Fractal background** — Cython + OpenMP Mandelbrot kernel with dual-frequency sine coloriser; sine-wave breathing zoom; concentric ripple warp
- **Music reactive** — fractal pulse driven by audio RMS tracking (fast attack, slow decay)
- **Background music** — looping audio with volume slider and mute toggle
- **Download library** — scrollable thumbnail grid of all past downloads, organised by date
- **Auto-organised downloads** — saved to `Downloads/YYYY-MM-DD/` next to the exe
- **Open folder** — one-click reveal of the last download location in Explorer
- **Resizable window** — fractal renders at native canvas resolution

---

## INSTALL

Download `FloproastSetup.exe` from [Releases](https://github.com/Floproast500/FloproastDownloader/releases) and run it. The wizard installs to a directory of your choice and creates a desktop shortcut.

**Requirements (bundled):** yt-dlp, ffmpeg, Pillow, numpy, miniaudio

---

## BUILD FROM SOURCE

**Prerequisites:** Python 3.14, MinGW-w64 GCC, Cython, numpy

```
pip install -r requirements.txt
```

Compile the Cython fractal kernel (Windows, MinGW GCC):
```
python setup_fractal.py build_ext --inplace
```

Or compile manually with GCC:
```
cython --c fractal.pyx
gcc -O3 -march=native -fopenmp -shared -static-libgcc \
    -I<python_include> -I<numpy_include> fractal.c \
    -L<python_libs> -lpython314 -o fractal.cp314-win_amd64.pyd
```

Build the exe:
```
pyinstaller --noconfirm --onefile --windowed --icon floproast.ico --name YTDownloader \
    --add-data "music.mp3;." \
    --add-binary "fractal.cp314-win_amd64.pyd;." \
    --add-binary "<site-packages>/_miniaudio.pyd;." \
    --add-binary "<site-packages>/_cffi_backend.cp314-win_amd64.pyd;." \
    --hidden-import miniaudio --hidden-import _cffi_backend \
    downloader.py
```

Build the installer:
```
pyinstaller --noconfirm FloproastSetup.spec
```

---

## PROJECT STRUCTURE

```
downloader.py              — main application
fractal.pyx                — Cython fractal kernel (mandelbrot + colorize)
setup_fractal.py           — Cython build script
installer.py               — Win98-style setup wizard
FloproastSetup.spec        — PyInstaller spec for installer
YTDownloader.spec          — PyInstaller spec for main exe
music.mp3                  — background audio (Skinny Puppy cover)
floproast.ico              — application icon
dist/FloproastSetup.exe    — distributable installer
```

---

## SIGNAL ESTABLISHED

Made by Floproast
