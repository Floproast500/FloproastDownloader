"""
Floproast Downloader — Setup Wizard
Windows 98 style installer wizard
"""
import tkinter as tk
from tkinter import filedialog, messagebox
import threading
import os
import sys
import subprocess
import shutil
import zipfile
import tempfile
import time
import urllib.request
import winreg

# ── Win98 palette ─────────────────────────────────────────────────────────────
W_BG    = "#d4d0c8"   # classic Windows gray
W_NAVY  = "#000080"   # title / sidebar blue
W_WHITE = "#ffffff"
W_DARK  = "#808080"   # border shadow
W_LIGHT = "#ffffff"   # border highlight
W_TEXT  = "#000000"
W_DIM   = "#444444"
W_GREEN = "#007700"
W_RED   = "#cc0000"

FN   = ("MS Sans Serif", 8)
FN_B = ("MS Sans Serif", 8, "bold")
FN_L = ("MS Sans Serif", 10, "bold")
FN_T = ("MS Sans Serif", 14, "bold")
FN_C = ("Courier New", 8)

# ── App / URL constants ───────────────────────────────────────────────────────
APP_NAME    = "Floproast Downloader"
APP_VER     = "2.0"
FFMPEG_URL           = "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip"
FFMPEG_VER_URL       = "https://www.gyan.dev/ffmpeg/builds/release-version"
PYTHON_VER_URL       = "https://endoflife.date/api/python.json"
PYTHON_FALLBACK_VER  = "3.13.3"
DEFAULT_DIR = os.path.join(os.environ.get("LOCALAPPDATA", "C:\\Users\\Public"),
                           "FloproastDownloader")


def get_resource(name: str) -> str:
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, name)


def find_python() -> str | None:
    for cmd in ("python", "python3", "py"):
        try:
            r = subprocess.run([cmd, "--version"], capture_output=True,
                               text=True, timeout=5)
            if r.returncode == 0:
                return (r.stdout + r.stderr).strip().replace("Python ", "")
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass
    return None


def find_ffmpeg() -> str | None:
    try:
        r = subprocess.run(["ffmpeg", "-version"], capture_output=True,
                           text=True, timeout=5)
        if r.returncode == 0:
            parts = r.stdout.splitlines()[0].split()
            return parts[2] if len(parts) > 2 else "installed"
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    return None


def add_to_user_path(directory: str) -> None:
    key = winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                         "Environment", 0, winreg.KEY_ALL_ACCESS)
    try:
        current, _ = winreg.QueryValueEx(key, "Path")
    except FileNotFoundError:
        current = ""
    paths = [p for p in current.split(";") if p and p != directory]
    paths.append(directory)
    winreg.SetValueEx(key, "Path", 0, winreg.REG_EXPAND_SZ, ";".join(paths))
    winreg.CloseKey(key)


def create_shortcut(target: str, link_path: str, working_dir: str = "") -> None:
    script = (
        f'$ws = New-Object -ComObject WScript.Shell; '
        f'$sc = $ws.CreateShortcut("{link_path}"); '
        f'$sc.TargetPath = "{target}"; '
        f'$sc.WorkingDirectory = "{working_dir}"; '
        f'$sc.Save()'
    )
    subprocess.run(["powershell", "-Command", script],
                   capture_output=True, timeout=15)


# ── Version helpers ───────────────────────────────────────────────────────────

def _parse_ver(s: str) -> tuple:
    try:
        return tuple(int(x) for x in s.strip().split(".")[:3])
    except (ValueError, AttributeError):
        return (0, 0, 0)


def _fetch_python_latest() -> str | None:
    """Return latest stable Python version string from endoflife.date API."""
    try:
        import json
        req = urllib.request.Request(PYTHON_VER_URL,
                                     headers={"User-Agent": "FloproastSetup/2.0"})
        with urllib.request.urlopen(req, timeout=6) as r:
            data = json.loads(r.read())
        # eol is False for active cycles
        active = [d for d in data if d.get("eol") is False]
        pool = active or data
        best = max(pool, key=lambda d: _parse_ver(d["latest"]))
        return best["latest"]
    except Exception:
        return None


def _python_installer_url(version: str) -> str:
    return (f"https://www.python.org/ftp/python/{version}/"
            f"python-{version}-amd64.exe")


def _fetch_ffmpeg_latest() -> str | None:
    """Return latest gyan.dev release version string (e.g. '7.1.1')."""
    try:
        req = urllib.request.Request(FFMPEG_VER_URL,
                                     headers={"User-Agent": "FloproastSetup/2.0"})
        with urllib.request.urlopen(req, timeout=6) as r:
            return r.read().decode().strip()
    except Exception:
        return None


def _extract_semver(version_str: str) -> str | None:
    """Pull X.Y.Z from a release ffmpeg version string; None for git builds."""
    import re
    m = re.match(r"^(\d+\.\d+\.?\d*)", version_str or "")
    return m.group(1) if m else None


# ── Reusable Win98 widget helpers ─────────────────────────────────────────────

def raised_btn(parent, text, command, width=10, **kw):
    kw.setdefault("bg", W_BG)
    kw.setdefault("fg", W_TEXT)
    kw.setdefault("font", FN)
    kw.setdefault("relief", "raised")
    kw.setdefault("bd", 2)
    kw.setdefault("cursor", "arrow")
    kw.setdefault("width", width)
    return tk.Button(parent, text=text, command=command, **kw)


def sunken_frame(parent, **kw):
    """A sunken inset panel (Win98 list/text area border)."""
    kw.setdefault("bg", W_WHITE)
    kw.setdefault("relief", "sunken")
    kw.setdefault("bd", 2)
    return tk.Frame(parent, **kw)


def rule(parent, row=None, col=0, colspan=1, padx=0, pady=0):
    """Thin horizontal separator (dark + light lines = Win98 groove rule)."""
    tk.Frame(parent, bg=W_DARK,  height=1).grid(
        row=row, column=col, columnspan=colspan,
        sticky="ew", padx=padx, pady=(pady, 0))
    tk.Frame(parent, bg=W_LIGHT, height=1).grid(
        row=row + 1, column=col, columnspan=colspan,
        sticky="ew", padx=padx, pady=(0, pady))


# ── Win98 segmented progress bar ──────────────────────────────────────────────

class Win98Bar(tk.Canvas):
    def __init__(self, parent, **kw):
        kw.setdefault("height", 20)
        kw.setdefault("bg", W_WHITE)
        kw.setdefault("highlightthickness", 0)
        kw.setdefault("bd", 0)
        super().__init__(parent, **kw)
        self._pct = 0.0
        self.bind("<Configure>", lambda _: self._draw())

    def set(self, pct: float):
        self._pct = max(0.0, min(100.0, pct))
        self._draw()

    def _draw(self):
        self.delete("all")
        w, h = self.winfo_width(), self.winfo_height()
        if w < 4:
            return
        filled = int(w * self._pct / 100)
        bw = 10   # block width
        gap = 1
        x = 0
        while x < filled:
            x1 = min(x + bw, filled)
            self.create_rectangle(x, 0, x1, h, fill=W_NAVY, outline="")
            x += bw + gap


# ── Wizard shell ──────────────────────────────────────────────────────────────

class Wizard(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(f"{APP_NAME} Setup")
        self.resizable(False, False)
        self.configure(bg=W_BG)

        ico = get_resource("floproast.ico")
        if os.path.exists(ico):
            try:
                self.iconbitmap(ico)
            except Exception:
                pass

        # ── State ─────────────────────────────────────────────────────────────
        self.python_ver: str | None = None
        self.ffmpeg_ver: str | None = None
        self.python_latest: str | None = None
        self.ffmpeg_latest: str | None = None
        self.python_needs_update = False
        self.ffmpeg_needs_update = False
        self.consent_python   = tk.BooleanVar(value=True)
        self.consent_ffmpeg   = tk.BooleanVar(value=True)
        self.consent_ytdlp    = tk.BooleanVar(value=True)
        self.install_dir      = tk.StringVar(value=DEFAULT_DIR)
        self.want_desktop     = tk.BooleanVar(value=True)
        self.want_startmenu   = tk.BooleanVar(value=True)
        self.want_launch      = tk.BooleanVar(value=True)

        self._page_idx = 0
        self._pages = [
            self._pg_welcome,
            self._pg_scan,
            self._pg_python,
            self._pg_ffmpeg,
            self._pg_ytdlp,
            self._pg_location,
            self._pg_shortcuts,
            self._pg_installing,
            self._pg_finish,
        ]

        self._build_shell()
        self._go(0)
        self._center()

    # ── Shell (permanent outer frame) ─────────────────────────────────────────

    def _build_shell(self):
        # Fixed window size — explicit geometry avoids the blank-render bug
        # caused by pack_propagate(False) frames with no height specified.
        self.geometry("660x420")

        # Grid: col 0 = sidebar (164 px fixed), col 1 = content (fills rest)
        #       row 0 = content zone (expands), rows 1-2 = separator, row 3 = buttons
        self.columnconfigure(0, minsize=164)
        self.columnconfigure(1, weight=1)
        self.rowconfigure(0, weight=1)

        # ── Left sidebar ──────────────────────────────────────────────────────
        sb = tk.Frame(self, bg=W_NAVY, width=164)
        sb.grid(row=0, column=0, rowspan=4, sticky="nsew")
        sb.grid_propagate(False)
        self._build_sidebar(sb)

        # ── Content swap-zone (pages render here) ─────────────────────────────
        self._zone = tk.Frame(self, bg=W_BG)
        self._zone.grid(row=0, column=1, sticky="nsew")

        # ── Separator (Win98 groove rule) ─────────────────────────────────────
        tk.Frame(self, bg=W_DARK,  height=1).grid(row=1, column=1, sticky="ew")
        tk.Frame(self, bg=W_WHITE, height=1).grid(row=2, column=1, sticky="ew")

        # ── Button bar ────────────────────────────────────────────────────────
        bb = tk.Frame(self, bg=W_BG, pady=8, padx=10)
        bb.grid(row=3, column=1, sticky="ew")
        bb.columnconfigure(0, weight=1)

        self._btn_back = raised_btn(bb, "< Back", self._back)
        self._btn_back.grid(row=0, column=1, padx=(0, 4))

        self._btn_next = raised_btn(bb, "Next >", self._next)
        self._btn_next.grid(row=0, column=2, padx=(0, 8))

        self._btn_cancel = raised_btn(bb, "Cancel", self._cancel)
        self._btn_cancel.grid(row=0, column=3)

    def _build_sidebar(self, parent):
        # Gradient canvas (dark navy → near-black)
        c = tk.Canvas(parent, width=164, height=380,
                      bg=W_NAVY, highlightthickness=0)
        c.pack(fill="both", expand=True)

        # Manual gradient: top #000080 → bottom #000028
        for y in range(380):
            b = int(0x80 - (0x58 * y / 380))
            c.create_line(0, y, 164, y, fill=f"#0000{b:02x}")

        # ASCII "floppy bacon sushi" art
        art = [
            "   ___________   ",
            "  /           \\  ",
            " |  ~ bacon ~  | ",
            " |  ~ sushi ~  | ",
            "  \\___________/  ",
            "",
            "  [  floppy  ]   ",
        ]
        for i, line in enumerate(art):
            col = "#4ade4a" if "bacon" in line or "sushi" in line else "#7799bb"
            c.create_text(82, 80 + i * 14, text=line,
                          fill=col, font=("Courier New", 7), anchor="center")

        # Brand text near bottom
        c.create_text(82, 310, text="FLOPROAST",
                      fill="#4ade4a", font=("Courier New", 11, "bold"), anchor="center")
        c.create_text(82, 328, text="DOWNLOADER",
                      fill="#aaaacc", font=("Courier New", 8),  anchor="center")
        c.create_text(82, 344, text=f"v{APP_VER}",
                      fill="#555577", font=("Courier New", 7),  anchor="center")

    # ── Zone helpers ──────────────────────────────────────────────────────────

    def _clear(self):
        for w in self._zone.winfo_children():
            w.destroy()

    def _hdr(self, title: str, sub: str):
        """Dark navy header band at the top of each page."""
        h = tk.Frame(self._zone, bg=W_NAVY, height=58)
        h.pack(fill="x")
        h.pack_propagate(False)
        tk.Label(h, text=title, bg=W_NAVY, fg=W_WHITE,
                 font=FN_L, anchor="w").place(x=12, y=8)
        tk.Label(h, text=sub,   bg=W_NAVY, fg="#9999cc",
                 font=FN,   anchor="w", wraplength=560,
                 justify="left").place(x=12, y=30)
        # Bottom rule on header
        tk.Frame(self._zone, bg="#4444aa", height=1).pack(fill="x")

    def _body(self) -> tk.Frame:
        f = tk.Frame(self._zone, bg=W_BG, padx=16, pady=10)
        f.pack(fill="both", expand=True)
        return f

    def _info_box(self, parent, text: str) -> tk.Frame:
        """Win98-style sunken info panel."""
        box = sunken_frame(parent, padx=8, pady=6)
        box.pack(fill="x", pady=(0, 10))
        tk.Label(box, text=text, font=FN_C, bg=W_WHITE,
                 justify="left", anchor="nw").pack(anchor="w")
        return box

    # ── Navigation ────────────────────────────────────────────────────────────

    def _center(self):
        self.update_idletasks()
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        self.geometry(f"660x420+{(sw - 660) // 2}+{(sh - 420) // 2}")

    def _should_show(self, idx: int) -> bool:
        pg = self._pages[idx]
        if pg == self._pg_python:
            return self.python_ver is None or self.python_needs_update
        if pg == self._pg_ffmpeg:
            return self.ffmpeg_ver is None or self.ffmpeg_needs_update
        return True

    def _go(self, idx: int):
        self._page_idx = idx
        self._clear()
        # Reset button defaults
        self._btn_back.config(state="normal" if idx > 0 else "disabled",
                              text="< Back", command=self._back)
        self._btn_next.config(state="normal", text="Next >", command=self._next)
        self._btn_cancel.config(state="normal", text="Cancel", command=self._cancel)
        self._pages[idx]()

    def _next(self):
        idx = self._page_idx + 1
        while idx < len(self._pages) and not self._should_show(idx):
            idx += 1
        if idx < len(self._pages):
            self._go(idx)

    def _back(self):
        idx = self._page_idx - 1
        while idx >= 0 and not self._should_show(idx):
            idx -= 1
        if idx >= 0:
            self._go(idx)

    def _cancel(self):
        if messagebox.askyesno("Cancel Setup",
                               "Are you sure you want to cancel?\n\n"
                               f"{APP_NAME} will not be installed.",
                               icon="warning"):
            self.destroy()

    # ── Page 0: Welcome ───────────────────────────────────────────────────────

    def _pg_welcome(self):
        self._hdr("Floproast Youtube Downloader",
                  "it also has cheese")
        b = self._body()

        tk.Label(b, text=f"Welcome to {APP_NAME} Setup",
                 font=FN_T, bg=W_BG, wraplength=460).pack(anchor="w", pady=(0, 10))

        intro = (
            "This program will guide you through the installation\n"
            "of Floproast Downloader and its dependencies.\n\n"
            "You will be asked to give consent before each\n"
            "component is downloaded or installed:\n"
        )
        tk.Label(b, text=intro, font=FN, bg=W_BG, justify="left").pack(anchor="w")

        deps = tk.Frame(b, bg=W_BG)
        deps.pack(anchor="w", padx=16)
        for dep in ("Python 3.13", "ffmpeg", "yt-dlp", "Floproast Downloader"):
            tk.Label(deps, text=f"•  {dep}", font=FN, bg=W_BG,
                     justify="left").pack(anchor="w")

        tk.Label(b, text="\nClick Next to continue.",
                 font=FN, bg=W_BG).pack(anchor="w")

        self._btn_back.config(state="disabled")

    # ── Page 1: Dependency scan ───────────────────────────────────────────────

    def _pg_scan(self):
        self._hdr("Checking System Requirements",
                  "Scanning your computer for installed components...")
        b = self._body()

        tk.Label(b, text="Scanning for required components:",
                 font=FN_B, bg=W_BG).pack(anchor="w", pady=(0, 8))

        tbl = tk.Frame(b, bg=W_BG)
        tbl.pack(anchor="w", fill="x")

        rows = {}
        for i, key in enumerate(("Python", "ffmpeg")):
            tk.Label(tbl, text=f"{key}:", font=FN_B, bg=W_BG,
                     width=12, anchor="w").grid(row=i, column=0, sticky="w")
            lbl = tk.Label(tbl, text="Scanning...", font=FN, bg=W_BG,
                           fg=W_DIM, anchor="w")
            lbl.grid(row=i, column=1, sticky="w", pady=3)
            rows[key] = lbl

        # Add a third row for the update-check phase
        tk.Label(tbl, text="Updates:", font=FN_B, bg=W_BG,
                 width=12, anchor="w").grid(row=2, column=0, sticky="w")
        update_lbl = tk.Label(tbl, text="Waiting...", font=FN, bg=W_BG,
                              fg=W_DIM, anchor="w")
        update_lbl.grid(row=2, column=1, sticky="w", pady=3)

        self._btn_next.config(state="disabled")
        self._btn_back.config(state="disabled")

        def scan():
            time.sleep(0.4)

            # ── Detect installed versions ──────────────────────────────────────
            pv = find_python()
            self.python_ver = pv
            if pv:
                self.after(0, lambda v=pv: rows["Python"].config(
                    text=f"✔  Found  (Python {v})", fg=W_GREEN))
            else:
                self.after(0, lambda: rows["Python"].config(
                    text="✘  Not found  — will offer installation", fg=W_RED))

            time.sleep(0.3)

            fv = find_ffmpeg()
            self.ffmpeg_ver = fv
            if fv:
                self.after(0, lambda v=fv: rows["ffmpeg"].config(
                    text=f"✔  Found  ({v})", fg=W_GREEN))
            else:
                self.after(0, lambda: rows["ffmpeg"].config(
                    text="✘  Not found  — will offer installation", fg=W_RED))

            time.sleep(0.3)

            # ── Check for latest versions online ──────────────────────────────
            self.after(0, lambda: update_lbl.config(
                text="Checking online for latest versions...", fg=W_DIM))

            update_msgs = []

            # Python
            latest_py = _fetch_python_latest() or PYTHON_FALLBACK_VER
            self.python_latest = latest_py
            if pv and _parse_ver(pv) < _parse_ver(latest_py):
                self.python_needs_update = True
                self.consent_python.set(True)
                update_msgs.append(f"Python {pv} → {latest_py}")
                self.after(0, lambda v=pv, l=latest_py: rows["Python"].config(
                    text=f"⚠  Python {v}  (update available: {l})",
                    fg="#cc6600"))
            elif pv:
                self.consent_python.set(False)

            # ffmpeg — only compare if installed version is a clean semver
            latest_ff = _fetch_ffmpeg_latest()
            self.ffmpeg_latest = latest_ff
            if fv and latest_ff:
                installed_semver = _extract_semver(fv)
                if installed_semver and _parse_ver(installed_semver) < _parse_ver(latest_ff):
                    self.ffmpeg_needs_update = True
                    self.consent_ffmpeg.set(True)
                    update_msgs.append(f"ffmpeg {installed_semver} → {latest_ff}")
                    self.after(0, lambda v=installed_semver, l=latest_ff:
                               rows["ffmpeg"].config(
                                   text=f"⚠  ffmpeg {v}  (update available: {l})",
                                   fg="#cc6600"))
                elif fv:
                    self.consent_ffmpeg.set(False)

            if update_msgs:
                msg = "Updates available: " + ",  ".join(update_msgs)
                self.after(0, lambda m=msg: update_lbl.config(text=m, fg="#cc6600"))
            else:
                self.after(0, lambda: update_lbl.config(
                    text="✔  All installed components are up to date.", fg=W_GREEN))

            time.sleep(0.2)
            self.after(0, lambda: self._btn_next.config(state="normal"))
            self.after(0, lambda: self._btn_back.config(state="normal"))

        threading.Thread(target=scan, daemon=True).start()

    # ── Page 2: Python consent ────────────────────────────────────────────────

    def _pg_python(self):
        latest = self.python_latest or PYTHON_FALLBACK_VER

        if self.python_ver and self.python_needs_update:
            self._hdr("Python Update Available",
                      f"Python {self.python_ver} is installed but {latest} is available.")
            b = self._body()
            tk.Label(b, text=f"A newer version of Python is available.",
                     font=FN_B, bg=W_BG).pack(anchor="w", pady=(0, 6))
            self._info_box(b,
                           f"Installed :  Python {self.python_ver}\n"
                           f"Available :  Python {latest}\n"
                           f"Source    :  python.org  (official)\n"
                           f"Size      :  ~25 MB download")
            tk.Label(b,
                     text="Your existing Python installation will be upgraded.\n"
                          "pip and PATH will be preserved.",
                     font=FN, bg=W_BG, justify="left").pack(anchor="w", pady=(0, 12))
            tk.Checkbutton(b,
                           text=f"I consent to updating Python to {latest}",
                           variable=self.consent_python,
                           font=FN, bg=W_BG, activebackground=W_BG).pack(anchor="w")
        else:
            self._hdr(f"Install Python {latest}",
                      "Python is required to run the downloader engine.")
            b = self._body()
            tk.Label(b, text="Python was not found on this computer.",
                     font=FN_B, bg=W_BG).pack(anchor="w", pady=(0, 6))
            self._info_box(b,
                           f"Package  :  Python {latest} (64-bit)\n"
                           f"Source   :  python.org  (official)\n"
                           f"Size     :  ~25 MB download\n"
                           f"Scope    :  Current user only (no admin needed)")
            tk.Label(b,
                     text="Python will be added to your PATH automatically.\n"
                          "pip will also be installed.",
                     font=FN, bg=W_BG, justify="left").pack(anchor="w", pady=(0, 12))
            tk.Checkbutton(b,
                           text=f"I consent to downloading and installing Python {latest}",
                           variable=self.consent_python,
                           font=FN, bg=W_BG, activebackground=W_BG).pack(anchor="w")

    # ── Page 3: ffmpeg consent ────────────────────────────────────────────────

    def _pg_ffmpeg(self):
        latest = self.ffmpeg_latest or "latest"

        if self.ffmpeg_ver and self.ffmpeg_needs_update:
            installed_sv = _extract_semver(self.ffmpeg_ver) or self.ffmpeg_ver
            self._hdr("ffmpeg Update Available",
                      f"ffmpeg {installed_sv} is installed but {latest} is available.")
            b = self._body()
            tk.Label(b, text="A newer version of ffmpeg is available.",
                     font=FN_B, bg=W_BG).pack(anchor="w", pady=(0, 6))
            self._info_box(b,
                           f"Installed :  ffmpeg {installed_sv}\n"
                           f"Available :  ffmpeg {latest}\n"
                           f"Source    :  gyan.dev  (trusted community build)\n"
                           f"Size      :  ~75 MB download")
            tk.Label(b,
                     text="The existing ffmpeg installation will be replaced.\n"
                          "Your PATH entry will be updated automatically.",
                     font=FN, bg=W_BG, justify="left").pack(anchor="w", pady=(0, 12))
            tk.Checkbutton(b,
                           text=f"I consent to updating ffmpeg to {latest}",
                           variable=self.consent_ffmpeg,
                           font=FN, bg=W_BG, activebackground=W_BG).pack(anchor="w")
        else:
            self._hdr("Install ffmpeg",
                      "ffmpeg is required for audio extraction and MP3 conversion.")
            b = self._body()
            tk.Label(b, text="ffmpeg was not found on this computer.",
                     font=FN_B, bg=W_BG).pack(anchor="w", pady=(0, 6))
            self._info_box(b,
                           f"Package  :  ffmpeg release essentials (win64)\n"
                           f"Source   :  gyan.dev  (trusted community build)\n"
                           f"Size     :  ~75 MB download\n"
                           f"Location :  %LOCALAPPDATA%\\FloproastDownloader\\ffmpeg\\")
            tk.Label(b,
                     text="ffmpeg will be added to your user PATH so that\n"
                          "the Audio Only (MP3) format option works correctly.",
                     font=FN, bg=W_BG, justify="left").pack(anchor="w", pady=(0, 12))
            tk.Checkbutton(b,
                           text="I consent to downloading and installing ffmpeg",
                           variable=self.consent_ffmpeg,
                           font=FN, bg=W_BG, activebackground=W_BG).pack(anchor="w")

    # ── Page 4: yt-dlp consent ────────────────────────────────────────────────

    def _pg_ytdlp(self):
        self._hdr("Install yt-dlp",
                  "yt-dlp is the YouTube download engine used by Floproast.")
        b = self._body()

        tk.Label(b, text="yt-dlp will be installed via pip (Python package manager).",
                 font=FN_B, bg=W_BG).pack(anchor="w", pady=(0, 6))

        self._info_box(b,
                       "Package  :  yt-dlp  (latest release)\n"
                       "Source   :  PyPI  (pip install yt-dlp)\n"
                       "Size     :  ~5 MB download\n"
                       "Requires :  Python (installed in previous step)")

        tk.Label(b,
                 text="yt-dlp provides support for downloading video and\n"
                      "audio from YouTube and thousands of other sites.\n\n"
                      "It is open source and free software.",
                 font=FN, bg=W_BG, justify="left").pack(anchor="w", pady=(0, 12))

        tk.Checkbutton(b,
                       text="I consent to downloading and installing yt-dlp",
                       variable=self.consent_ytdlp,
                       font=FN, bg=W_BG, activebackground=W_BG).pack(anchor="w")

    # ── Page 5: Install location ──────────────────────────────────────────────

    def _pg_location(self):
        self._hdr("Choose Install Location",
                  "Select the folder where Floproast Downloader will be installed.")
        b = self._body()

        tk.Label(b, text="Destination folder:", font=FN_B, bg=W_BG).pack(
            anchor="w", pady=(0, 4))

        row = tk.Frame(b, bg=W_BG)
        row.pack(fill="x", pady=(0, 10))

        ent = tk.Entry(row, textvariable=self.install_dir, font=FN,
                       relief="sunken", bd=2, width=30)
        ent.pack(side="left", padx=(0, 6))

        def browse():
            d = filedialog.askdirectory(initialdir=self.install_dir.get())
            if d:
                self.install_dir.set(d.replace("/", "\\"))

        raised_btn(row, "Browse...", browse, width=9).pack(side="left")

        tk.Label(b,
                 text="Disk space required:  ~20 MB\n\n"
                      "No administrator rights are required\n"
                      "for the default installation location.",
                 font=FN, bg=W_BG, justify="left").pack(anchor="w")

    # ── Page 6: Shortcuts ─────────────────────────────────────────────────────

    def _pg_shortcuts(self):
        self._hdr("Create Shortcuts",
                  "Choose which shortcuts to create for Floproast Downloader.")
        b = self._body()

        tk.Label(b, text="Create shortcuts:", font=FN_B, bg=W_BG).pack(
            anchor="w", pady=(0, 10))

        for text, var in (
            ("Desktop shortcut",    self.want_desktop),
            ("Start Menu shortcut", self.want_startmenu),
        ):
            tk.Checkbutton(b, text=text, variable=var, font=FN,
                           bg=W_BG, activebackground=W_BG).pack(
                anchor="w", pady=2)

        tk.Label(b,
                 text="\n\nReady to install. Click Install to begin.\n"
                      "This may take several minutes depending on\n"
                      "your internet connection speed.",
                 font=FN, bg=W_BG, justify="left").pack(anchor="w")

        self._btn_next.config(text="Install")

    # ── Page 7: Installing ────────────────────────────────────────────────────

    def _pg_installing(self):
        self._hdr("Installing...",
                  "Please wait while the components are installed.")
        b = self._body()

        self._step_lbl = tk.Label(b, text="Preparing...",
                                  font=FN_B, bg=W_BG, anchor="w")
        self._step_lbl.pack(fill="x", pady=(0, 4))

        # Progress bar (sunken border + canvas inside)
        prog_outer = tk.Frame(b, bg=W_DARK, relief="sunken", bd=2)
        prog_outer.pack(fill="x", pady=(0, 10))
        inner = tk.Frame(prog_outer, bg=W_WHITE)
        inner.pack(fill="x", padx=2, pady=2)
        self._bar = Win98Bar(inner, height=18)
        self._bar.pack(fill="x")

        # Log
        log_outer = sunken_frame(b)
        log_outer.pack(fill="both", expand=True)
        self._log = tk.Text(log_outer, font=("Courier New", 7),
                            bg=W_WHITE, fg=W_TEXT, relief="flat", bd=4,
                            state="disabled", wrap="word", height=9)
        self._log.pack(fill="both", expand=True)
        sb = tk.Scrollbar(log_outer, command=self._log.yview)
        sb.pack(side="right", fill="y")
        self._log["yscrollcommand"] = sb.set

        # Lock navigation during install
        self._btn_back.config(state="disabled")
        self._btn_next.config(state="disabled", text="Next >")
        self._btn_cancel.config(state="disabled")

        threading.Thread(target=self._do_install, daemon=True).start()

    def _log_write(self, msg: str):
        def _w():
            self._log.config(state="normal")
            self._log.insert("end", msg + "\n")
            self._log.see("end")
            self._log.config(state="disabled")
        self.after(0, _w)

    def _set_step(self, text: str, pct: float):
        self.after(0, lambda t=text: self._step_lbl.config(text=t))
        self.after(0, lambda p=pct: self._bar.set(p))

    def _do_install(self):
        install_dir = self.install_dir.get()
        os.makedirs(install_dir, exist_ok=True)

        steps = []
        if self.consent_python.get() and (not self.python_ver or self.python_needs_update):
            ver = self.python_latest or PYTHON_FALLBACK_VER
            label = (f"Updating Python to {ver}..." if self.python_needs_update
                     else f"Installing Python {ver}...")
            steps.append((label, self._inst_python))
        if self.consent_ffmpeg.get() and (not self.ffmpeg_ver or self.ffmpeg_needs_update):
            label = ("Updating ffmpeg..." if self.ffmpeg_needs_update
                     else "Installing ffmpeg...")
            steps.append((label, self._inst_ffmpeg))
        if self.consent_ytdlp.get():
            steps.append(("Installing yt-dlp...", self._inst_ytdlp))
        steps.append(("Copying Floproast Downloader...",
                       lambda: self._inst_app(install_dir)))
        steps.append(("Creating shortcuts...",
                       lambda: self._inst_shortcuts(install_dir)))

        n = len(steps)
        failed = False
        for i, (label, fn) in enumerate(steps):
            pct_lo = i / n * 95
            pct_hi = (i + 1) / n * 95
            self._set_step(label, pct_lo)
            self._log_write(f"\n> {label}")
            try:
                fn()
                self._set_step(label, pct_hi)
            except Exception as exc:
                self._log_write(f"  [ERROR] {exc}")
                failed = True

        if failed:
            self._set_step("Completed with errors — see log above.", 100)
            self._log_write("\n> Installation finished with errors.")
        else:
            self._set_step("Installation complete!", 100)
            self._log_write("\n> All components installed successfully.")

        self.after(600, lambda: self._btn_next.config(state="normal",
                                                      text="Next >",
                                                      command=self._next))

    # ── Install helpers ───────────────────────────────────────────────────────

    def _download(self, url: str, dest: str, label: str):
        last_pct = [0]

        def hook(count, block, total):
            if total > 0:
                pct = min(count * block / total * 100, 100)
                if int(pct) > last_pct[0]:
                    last_pct[0] = int(pct)
                    self._log_write(f"  {label}: {pct:.0f}%")

        urllib.request.urlretrieve(url, dest, reporthook=hook)

    def _inst_python(self):
        ver = self.python_latest or PYTHON_FALLBACK_VER
        url = _python_installer_url(ver)
        tmp = tempfile.mkdtemp()
        dest = os.path.join(tmp, "python_setup.exe")
        self._log_write(f"  Downloading: {url}")
        self._download(url, dest, "Download")
        self._log_write("  Running Python installer (silent)...")
        r = subprocess.run(
            [dest, "/quiet", "InstallAllUsers=0",
             "PrependPath=1", "Include_pip=1"],
            timeout=300
        )
        if r.returncode != 0:
            raise RuntimeError(f"Python installer exited with code {r.returncode}")
        self._log_write("  Python 3.13 installed.")

    def _inst_ffmpeg(self):
        install_dir = self.install_dir.get()
        ffmpeg_dir = os.path.join(install_dir, "ffmpeg")
        os.makedirs(ffmpeg_dir, exist_ok=True)

        tmp = tempfile.mkdtemp()
        zip_path = os.path.join(tmp, "ffmpeg.zip")
        self._log_write(f"  Downloading: {FFMPEG_URL}")
        self._download(FFMPEG_URL, zip_path, "Download")

        self._log_write("  Extracting ffmpeg binaries...")
        with zipfile.ZipFile(zip_path, "r") as zf:
            for name in zf.namelist():
                bn = os.path.basename(name)
                if bn in ("ffmpeg.exe", "ffprobe.exe", "ffplay.exe"):
                    data = zf.read(name)
                    with open(os.path.join(ffmpeg_dir, bn), "wb") as f:
                        f.write(data)

        self._log_write(f"  Adding {ffmpeg_dir} to user PATH...")
        add_to_user_path(ffmpeg_dir)
        self._log_write("  ffmpeg installed.")

    def _inst_ytdlp(self):
        self._log_write("  Running: pip install yt-dlp --upgrade")
        r = subprocess.run(
            ["python", "-m", "pip", "install", "yt-dlp",
             "--upgrade", "--quiet"],
            capture_output=True, text=True, timeout=120
        )
        if r.returncode != 0:
            raise RuntimeError(r.stderr[:300] or "pip failed")
        self._log_write("  yt-dlp installed.")

    def _inst_app(self, install_dir: str):
        # Copy compiled exe (when running as frozen installer)
        src_exe = get_resource("YTDownloader.exe")
        if os.path.exists(src_exe):
            dst = os.path.join(install_dir, "YTDownloader.exe")
            shutil.copy2(src_exe, dst)
            self._log_write(f"  Copied YTDownloader.exe to {dst}")
        else:
            self._log_write("  [WARN] YTDownloader.exe not bundled — skipping.")

        src_ico = get_resource("floproast.ico")
        if os.path.exists(src_ico):
            shutil.copy2(src_ico, os.path.join(install_dir, "floproast.ico"))

    def _inst_shortcuts(self, install_dir: str):
        exe = os.path.join(install_dir, "YTDownloader.exe")
        if not os.path.exists(exe):
            self._log_write("  [WARN] exe not found, skipping shortcuts.")
            return

        if self.want_desktop.get():
            desktop = os.path.join(os.environ["USERPROFILE"], "Desktop")
            lnk = os.path.join(desktop, "Floproast Downloader.lnk")
            create_shortcut(exe, lnk, install_dir)
            self._log_write(f"  Desktop shortcut: {lnk}")

        if self.want_startmenu.get():
            sm = os.path.join(os.environ["APPDATA"],
                              "Microsoft", "Windows", "Start Menu",
                              "Programs", "Floproast Downloader")
            os.makedirs(sm, exist_ok=True)
            lnk = os.path.join(sm, "Floproast Downloader.lnk")
            create_shortcut(exe, lnk, install_dir)
            self._log_write(f"  Start Menu shortcut: {lnk}")

    # ── Page 8: Finish ────────────────────────────────────────────────────────

    def _pg_finish(self):
        self._hdr("Installation Complete",
                  f"{APP_NAME} has been installed on your computer.")
        b = self._body()

        tk.Label(b,
                 text=f"✔  {APP_NAME} v{APP_VER} is installed!",
                 font=FN_T, bg=W_BG, fg=W_GREEN).pack(anchor="w", pady=(0, 12))

        tk.Label(b,
                 text=f"Installed to:\n  {self.install_dir.get()}\n",
                 font=FN, bg=W_BG, justify="left").pack(anchor="w")

        tk.Label(b,
                 text="Click Finish to close the Setup Wizard.",
                 font=FN, bg=W_BG).pack(anchor="w", pady=(0, 12))

        tk.Checkbutton(b,
                       text="Launch Floproast Downloader now",
                       variable=self.want_launch,
                       font=FN, bg=W_BG, activebackground=W_BG).pack(anchor="w")

        self._btn_back.config(state="disabled")
        self._btn_next.config(text="Finish", state="normal", command=self._finish)
        self._btn_cancel.config(state="disabled")

    def _finish(self):
        if self.want_launch.get():
            exe = os.path.join(self.install_dir.get(), "YTDownloader.exe")
            if os.path.exists(exe):
                subprocess.Popen([exe])
        self.destroy()


if __name__ == "__main__":
    try:
        from ctypes import windll
        windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        pass
    Wizard().mainloop()
