import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import threading
import queue
import os
import sys
import re
import math
import time
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse
from datetime import date

try:
    import yt_dlp
except ImportError:
    messagebox.showerror("SYSTEM ERROR", "yt-dlp not found.\nRun: pip install yt-dlp")
    sys.exit(1)

try:
    import numpy as np
    _HAS_NUMPY = True
except ImportError:
    _HAS_NUMPY = False
    np = None

try:
    from PIL import Image, ImageTk, ImageDraw
    _HAS_PIL = True
except ImportError:
    _HAS_PIL = False

_HAS_FRACTAL = _HAS_NUMPY and _HAS_PIL

# ── Cython fractal kernel (optional — falls back to numpy) ────────────────────
_HAS_CYTHON = False
if _HAS_FRACTAL:
    try:
        _base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
        os.add_dll_directory(_base)
    except (AttributeError, OSError):
        pass
    try:
        from fractal import mandelbrot as _cy_mandelbrot, colorize as _cy_colorize
        _HAS_CYTHON = True
    except ImportError:
        pass

# ── Audio library (optional) ──────────────────────────────────────────────────
_HAS_AUDIO = False
try:
    import miniaudio
    _HAS_AUDIO = True
except ImportError:
    pass

# ── Deus Ex / Skinny Puppy palette ───────────────────────────────────────────
BG      = "#020c02"   # void black
BG2     = "#041004"
BG3     = "#010801"
G_DIM   = "#0d3d0d"
G_MID   = "#1a6b1a"
GREEN   = "#2db82d"
G_HI    = "#4ade4a"
TEXT    = "#7ac97a"
T_DIM   = "#2d5c2d"
BORDER  = "#1a5c1a"
LOG_FG  = "#33cc33"
DARK_R  = "#5a0000"   # blood red — section markers & header frame
SCAR_R  = "#8b1a1a"   # scar red — used for disturbing accent text

PULSE_LO = (0x1a, 0x6b, 0x1a)
PULSE_HI = (0x4a, 0xde, 0x4a)

# ── Fonts ─────────────────────────────────────────────────────────────────────
FM     = ("Consolas", 9)
FM_B   = ("Consolas", 9, "bold")
FM_T   = ("Consolas", 20, "bold")
FM_BTN = ("Consolas", 10, "bold")
FM_LOG = ("Consolas", 9)

FORMATS = {
    "Best quality (video)": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
    "1080p (video)":        "bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]/best[height<=1080][ext=mp4]",
    "720p (video)":         "bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]/best[height<=720][ext=mp4]",
    "480p (video)":         "bestvideo[height<=480][ext=mp4]+bestaudio[ext=m4a]/best[height<=480][ext=mp4]",
    "360p (video)":         "bestvideo[height<=360][ext=mp4]+bestaudio[ext=m4a]/best[height<=360][ext=mp4]",
    "Audio only (MP3)":     "bestaudio/best",
}

ANSI_ESCAPE = re.compile(r"\x1b\[[0-9;]*m")

WIN_W = 960
WIN_H = 800

# Directory the exe (frozen) or script (dev) lives in — used as downloads root
_INSTALL_DIR = (os.path.dirname(sys.executable)
                if getattr(sys, "frozen", False)
                else os.path.dirname(os.path.abspath(__file__)))

FRAC_CX        = -0.7435669
FRAC_CY        =  0.1314023
FRAC_ZOOM_RATE = 1.035
FRAC_ZOOM_MAX  = 8e4
FRAC_PHASE_INC = 0.004


# ── Fractal computation ───────────────────────────────────────────────────────
def _mandelbrot(cx, cy, zoom, w, h, max_iter):
    if _HAS_CYTHON:
        return _cy_mandelbrot(cx, cy, zoom, w, h, max_iter)
    scale  = 3.5 / zoom
    aspect = w / h
    x = np.linspace(cx - scale * aspect * 0.5, cx + scale * aspect * 0.5, w, dtype=np.float64)
    y = np.linspace(cy - scale * 0.5,          cy + scale * 0.5,          h, dtype=np.float64)
    C     = x[np.newaxis, :] + 1j * y[:, np.newaxis]
    Z     = np.zeros_like(C)
    esc   = np.full((h, w), float(max_iter), dtype=np.float32)
    alive = np.ones((h, w), dtype=bool)
    for i in range(1, max_iter + 1):
        Z[alive] = Z[alive] ** 2 + C[alive]
        burst = alive & (np.abs(Z) > 2.0)
        az = np.abs(Z[burst])
        esc[burst] = i + 1.0 - np.log2(np.log2(np.maximum(az, 1.001)))
        alive[burst] = False
    return esc


def _colorize(esc, max_iter, phase, pulse=0.0):
    if _HAS_CYTHON:
        return _cy_colorize(esc, max_iter, phase, pulse)
    # numpy fallback — mirrors the Cython dual-band logic
    PHI    = 1.6180339887498948
    in_set = esc >= max_iter - 0.5
    t      = np.clip(esc / max_iter, 0.0, 1.0).astype(np.float32)
    a1     = (t * 7.0  + phase)      * (2.0 * math.pi)
    a2     = (t * 11.0 + phase * PHI) * (2.0 * math.pi)
    wv1    = (np.sin(a1) * 0.5 + 0.5).astype(np.float32)
    wv2    = (np.sin(a2) * 0.5 + 0.5).astype(np.float32)
    bright = (wv1 * wv2) ** 2
    r = (bright * 22.0 + wv1 * 14.0).astype(np.float32)
    g = (bright * 190.0).astype(np.float32)
    b = (bright * 10.0).astype(np.float32)
    flash = pulse * wv1
    r += flash * 220.0
    g += flash * 48.0
    b += flash * 35.0
    if pulse > 0.7:
        f2 = (pulse - 0.7) * 3.333
        r += f2 * (255.0 - r)
        g += f2 * (255.0 - g) * 0.5
        b += f2 * (255.0 - b) * 0.3
    rgb         = np.stack([
        np.clip(r, 0, 255).astype(np.uint8),
        np.clip(g, 0, 255).astype(np.uint8),
        np.clip(b, 0, 255).astype(np.uint8),
    ], axis=-1)
    rgb[in_set] = [0, 0, 0]  # void interior
    return rgb


# ── URL sanitiser ─────────────────────────────────────────────────────────────

def _strip_to_video(url: str) -> str:
    parsed = urlparse(url.strip())
    if parsed.netloc in ("www.youtube.com", "youtube.com", "m.youtube.com"):
        params = parse_qs(parsed.query)
        if "v" in params:
            return urlunparse(parsed._replace(query=urlencode({"v": params["v"][0]})))
    return url


# ── Custom segmented progress bar ─────────────────────────────────────────────

class SegmentedBar(tk.Canvas):
    SEGMENTS = 30

    def __init__(self, parent, **kw):
        kw.setdefault("bg", BG)
        kw.setdefault("highlightthickness", 0)
        kw.setdefault("height", 14)
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
        if w < 2:
            return
        n      = self.SEGMENTS
        gap    = 2
        seg_w  = (w - gap * (n - 1)) / n
        filled = self._pct / 100 * n
        for i in range(n):
            x0  = i * (seg_w + gap)
            x1  = x0 + seg_w
            col = GREEN if i < int(filled) else (G_MID if i == int(filled) and filled % 1 > 0 else G_DIM)
            self.create_rectangle(x0, 1, x1, h - 1, fill=col, outline="")


# ── Section header ────────────────────────────────────────────────────────────

def _section_hdr(parent, row, label, padx=14):
    """Blood-red marker + green label + dim rule — one combined header row."""
    fr = tk.Frame(parent, bg=BG)
    fr.grid(row=row, column=0, sticky="ew", padx=padx, pady=(10, 2))
    tk.Label(fr, text="▌", bg=BG, fg=DARK_R, font=FM_B).pack(side="left")
    tk.Label(fr, text=f" {label} ", bg=BG, fg=G_MID, font=FM_B).pack(side="left")
    tk.Label(fr, text="─" * 48, bg=BG, fg=G_DIM, font=FM).pack(side="left")


# ── Main app ──────────────────────────────────────────────────────────────────

class DXDownloader(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("FLOPROAST // SIGNAL TERMINAL")
        self.configure(bg=BG)
        self.resizable(True, True)
        self.minsize(760, 700)

        self._downloading  = False
        self._stop_event   = threading.Event()
        self._output_dir   = os.path.join(_INSTALL_DIR, "Downloads")
        os.makedirs(self._output_dir, exist_ok=True)

        # Fractal state
        self._frac_zoom    = 2.5
        self._frac_zoom_t  = 0.0         # sine-wave breathing zoom time
        self._frac_phase   = 0.0
        self._frac_twist   = 0.0         # melt rotation (grows unbounded)
        self._frac_queue   = queue.Queue(maxsize=3)
        self._frac_stop    = threading.Event()   # app-shutdown signal (shared w/ audio)
        self._photo_ref    = None
        self._frac_rw      = WIN_W
        self._frac_rh      = WIN_H
        self._vx_key       = None        # vortex precompute cache key

        # Audio state
        self._audio_volume = 0.5
        self._audio_muted  = False
        self._audio_device = None
        self._audio_pulse  = 0.0   # smoothed RMS (0..1) — drives fractal pulse

        # Library state
        self._last_save_dir = None

        self._set_icon()
        self._setup_styles()
        self._build_scene()
        self._center_window()
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        self.after(50, self._pulse_tick)
        self._boot_messages()

        if _HAS_FRACTAL:
            threading.Thread(target=self._fractal_worker, daemon=True).start()
        self._poll_fractal()

        self._init_audio()

    def _on_close(self):
        self._frac_stop.set()
        self.destroy()

    # ── Setup ─────────────────────────────────────────────────────────────────

    def _set_icon(self):
        ico = os.path.join(os.path.dirname(os.path.abspath(__file__)), "floproast.ico")
        if os.path.exists(ico):
            try:
                self.iconbitmap(ico)
            except Exception:
                pass

    def _setup_styles(self):
        s = ttk.Style(self)
        s.theme_use("clam")
        s.configure(".",
                    background=BG, foreground=TEXT,
                    fieldbackground=BG2, bordercolor=BORDER,
                    darkcolor=BG2, lightcolor=BG2,
                    troughcolor=BG2,
                    selectbackground=GREEN, selectforeground=BG,
                    font=FM)
        s.configure("TFrame", background=BG)
        s.configure("DX.TEntry",
                    fieldbackground=BG2, foreground=LOG_FG,
                    insertcolor=GREEN, bordercolor=BORDER,
                    lightcolor=BG2, darkcolor=BG2, font=FM_LOG)
        s.configure("DX.TCombobox",
                    fieldbackground=BG2, foreground=TEXT,
                    background=BG2, arrowcolor=GREEN,
                    bordercolor=BORDER, font=FM)
        s.map("DX.TCombobox",
              fieldbackground=[("readonly", BG2)],
              foreground=[("readonly", TEXT)],
              selectbackground=[("readonly", GREEN)],
              selectforeground=[("readonly", BG)])
        s.configure("Vertical.TScrollbar",
                    background=G_DIM, troughcolor=BG3,
                    bordercolor=BG, arrowcolor=G_MID,
                    darkcolor=BG2, lightcolor=BG2)

    # ── Scene ─────────────────────────────────────────────────────────────────

    def _build_scene(self):
        self._bg_canvas = tk.Canvas(self, bg=BG, highlightthickness=0)
        self._bg_canvas.pack(fill="both", expand=True)

        self._fractal_img_id = self._bg_canvas.create_image(0, 0, anchor="nw")

        outer = tk.Frame(self._bg_canvas, bg=G_DIM, padx=2, pady=2)
        inner = tk.Frame(outer, bg=G_MID, padx=1, pady=1)
        inner.pack(fill="both", expand=True)
        self._ui_panel = tk.Frame(inner, bg=BG)
        self._ui_panel.pack(fill="both", expand=True)

        self._build_ui(self._ui_panel)

        self.update_idletasks()
        self._ui_window_id = self._bg_canvas.create_window(
            WIN_W // 2, WIN_H // 2, window=outer, anchor="center"
        )
        self._bg_canvas.bind("<Configure>", self._on_canvas_resize)

    def _on_canvas_resize(self, event):
        self._bg_canvas.coords(self._ui_window_id, event.width // 2, event.height // 2)
        self._frac_rw = max(64, event.width)
        self._frac_rh = max(64, event.height)

    def _build_ui(self, p):
        P = 14
        p.columnconfigure(0, weight=1)

        # ── Header ────────────────────────────────────────────────────────────
        hdr = tk.Frame(p, bg=BG, pady=8)
        hdr.grid(row=0, column=0, sticky="ew")
        hdr.columnconfigure(0, weight=1)

        tk.Label(hdr,
                 text="█▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀█",
                 bg=BG, fg=DARK_R, font=FM).grid(row=0, column=0)

        self._title_lbl = tk.Label(hdr, text="F L O P R O A S T",
                                   bg=BG, fg=GREEN, font=FM_T)
        self._title_lbl.grid(row=1, column=0, pady=(4, 0))

        tk.Label(hdr, text="SIGNAL  ACQUISITION  TERMINAL",
                 bg=BG, fg=TEXT, font=FM_B).grid(row=2, column=0)

        tk.Label(hdr, text="floppy  ·  bacon  ·  sushi",
                 bg=BG, fg=T_DIM, font=FM).grid(row=3, column=0, pady=(2, 3))

        tk.Label(hdr,
                 text="[ NEURAL LINK ESTABLISHED  —  SUBJECT: CONNECTED ]",
                 bg=BG, fg=SCAR_R, font=FM).grid(row=4, column=0, pady=(0, 3))

        tk.Label(hdr,
                 text="█▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄█",
                 bg=BG, fg=DARK_R, font=FM).grid(row=5, column=0)

        # ── YouTube URL ───────────────────────────────────────────────────────
        _section_hdr(p, 1, "YOUTUBE URL")

        ir = tk.Frame(p, bg=BG)
        ir.grid(row=2, column=0, padx=P, pady=(0, 4), sticky="ew")
        ir.columnconfigure(1, weight=1)

        tk.Label(ir, text="YouTube URL:", bg=BG, fg=TEXT, font=FM).grid(
            row=0, column=0, columnspan=3, sticky="w", pady=(0, 3))

        tk.Label(ir, text=">", bg=BG, fg=GREEN, font=FM_B).grid(
            row=1, column=0, padx=(0, 6))

        self._url_var = tk.StringVar()
        ue = ttk.Entry(ir, textvariable=self._url_var, width=54, style="DX.TEntry")
        ue.grid(row=1, column=1, sticky="ew", padx=(0, 6))
        ue.bind("<Control-a>", lambda _: (ue.select_range(0, "end"), "break")[1])

        self._mk_btn(ir, "[PASTE]", self._paste_url).grid(row=1, column=2)

        # ── Download options ──────────────────────────────────────────────────
        _section_hdr(p, 3, "DOWNLOAD OPTIONS")

        opt = tk.Frame(p, bg=BG)
        opt.grid(row=4, column=0, padx=P, pady=(0, 4), sticky="ew")
        opt.columnconfigure(1, weight=1)

        tk.Label(opt, text="Quality:", bg=BG, fg=TEXT, font=FM).grid(
            row=0, column=0, sticky="w", padx=(0, 8))
        self._format_var = tk.StringVar(value=list(FORMATS.keys())[0])
        ttk.Combobox(opt, textvariable=self._format_var,
                     values=list(FORMATS.keys()),
                     state="readonly", width=31,
                     style="DX.TCombobox").grid(row=0, column=1, sticky="w")

        tk.Label(opt, text="Save to:", bg=BG, fg=TEXT, font=FM).grid(
            row=1, column=0, sticky="w", padx=(0, 8), pady=(6, 0))
        self._dir_var = tk.StringVar(value=self._output_dir)
        ttk.Entry(opt, textvariable=self._dir_var, width=34,
                  state="readonly", style="DX.TEntry").grid(
            row=1, column=1, sticky="ew", pady=(6, 0))
        self._mk_btn(opt, "[BROWSE]", self._browse_dir).grid(
            row=1, column=2, padx=(6, 0), pady=(6, 0))

        # ── Transfer status ───────────────────────────────────────────────────
        _section_hdr(p, 5, "TRANSFER STATUS")

        pr = tk.Frame(p, bg=BG)
        pr.grid(row=6, column=0, padx=P, sticky="ew")
        pr.columnconfigure(0, weight=1)

        self._bar = SegmentedBar(pr, height=14)
        self._bar.grid(row=0, column=0, sticky="ew")

        self._pct_var = tk.StringVar(value="  --.--%")
        tk.Label(pr, textvariable=self._pct_var,
                 bg=BG, fg=GREEN, font=FM_B, width=9, anchor="e").grid(
            row=0, column=1, padx=(6, 0))

        sr = tk.Frame(p, bg=BG)
        sr.grid(row=7, column=0, padx=P, pady=(3, 4), sticky="ew")
        tk.Label(sr, text=">", bg=BG, fg=G_MID, font=FM).grid(
            row=0, column=0, padx=(0, 4))
        self._status_var = tk.StringVar(value="SYSTEM READY")
        tk.Label(sr, textvariable=self._status_var,
                 bg=BG, fg=TEXT, font=FM, anchor="w").grid(row=0, column=1, sticky="w")

        # ── System log ────────────────────────────────────────────────────────
        _section_hdr(p, 8, "SYSTEM LOG")

        lf = tk.Frame(p, bg=BG3,
                      highlightbackground=BORDER, highlightthickness=1)
        lf.grid(row=9, column=0, padx=P, pady=(0, 4), sticky="nsew")
        lf.columnconfigure(0, weight=1)

        self._log = tk.Text(lf, height=8, width=70, state="disabled",
                            wrap="word", font=FM_LOG, bg=BG3, fg=LOG_FG,
                            insertbackground=GREEN, relief="flat", bd=6,
                            selectbackground=GREEN, selectforeground=BG)
        self._log.grid(row=0, column=0, sticky="nsew")

        sb = ttk.Scrollbar(lf, orient="vertical", command=self._log.yview)
        sb.grid(row=0, column=1, sticky="ns")
        self._log["yscrollcommand"] = sb.set

        # ── Action buttons ────────────────────────────────────────────────────
        bf = tk.Frame(p, bg=BG)
        bf.grid(row=10, column=0, pady=(4, 0))

        self._dl_btn = tk.Button(
            bf,
            text="[ EXECUTE DOWNLOAD ]",
            command=self._start_download,
            bg=BG2, fg=GREEN,
            activebackground=G_DIM, activeforeground=G_HI,
            disabledforeground=T_DIM,
            font=FM_BTN, relief="flat",
            highlightbackground=BORDER, highlightthickness=1,
            cursor="hand2", padx=20, pady=8,
        )
        self._dl_btn.grid(row=0, column=0, padx=(0, 8))

        self._mk_btn(bf, "[ VIEW LIBRARY ]", self._open_library).grid(
            row=0, column=1, padx=(0, 8))

        self._folder_btn = tk.Button(
            bf,
            text="[ OPEN FOLDER ]",
            command=self._open_last_folder,
            state="disabled",
            bg=BG2, fg=T_DIM,
            activebackground=G_DIM, activeforeground=G_HI,
            disabledforeground=T_DIM,
            font=FM_BTN, relief="flat",
            highlightbackground=G_DIM, highlightthickness=1,
            cursor="hand2", padx=20, pady=8,
        )
        self._folder_btn.grid(row=0, column=2)

        # ── Audio controls ────────────────────────────────────────────────────
        _section_hdr(p, 11, "AUDIO MATRIX")

        af = tk.Frame(p, bg=BG)
        af.grid(row=12, column=0, padx=P, pady=(0, P), sticky="ew")
        af.columnconfigure(1, weight=1)

        tk.Label(af, text="Volume:", bg=BG, fg=TEXT, font=FM).grid(
            row=0, column=0, sticky="w", padx=(0, 8))

        self._vol_var = tk.IntVar(value=50)
        tk.Scale(
            af, from_=0, to=100, orient="horizontal",
            variable=self._vol_var, command=self._set_volume,
            bg=BG, fg=GREEN, troughcolor=G_DIM, activebackground=G_HI,
            highlightthickness=0, sliderrelief="flat",
            showvalue=False, width=10,
        ).grid(row=0, column=1, sticky="ew", padx=(0, 8))

        self._mute_btn = self._mk_btn(af, "[MUTE]", self._toggle_mute)
        self._mute_btn.grid(row=0, column=2)

    # ── Fractal background ────────────────────────────────────────────────────

    def _fractal_worker(self):
        while not self._frac_stop.is_set():
            rw       = self._frac_rw
            rh       = self._frac_rh
            pulse    = self._audio_pulse
            max_iter = min(250, int(80 + 35 * math.log10(max(1.0, self._frac_zoom))))
            try:
                esc = _mandelbrot(FRAC_CX, FRAC_CY, self._frac_zoom, rw, rh, max_iter)
                rgb = _colorize(esc, max_iter, self._frac_phase, pulse)
                if _HAS_NUMPY:
                    rgb = self._apply_vortex(rgb, self._frac_twist)
                img = Image.fromarray(rgb, "RGB")
                self._frac_queue.put(img, block=True, timeout=0.1)
            except (queue.Full, Exception):
                pass

            # Sine-wave breathing zoom — organic inhale/exhale on a log scale
            self._frac_zoom_t += 0.00045 + pulse * 0.00018
            t_z = (math.sin(self._frac_zoom_t) + 1.0) * 0.5
            self._frac_zoom = 2.5 * (FRAC_ZOOM_MAX / 2.5) ** t_z

            # Slow colour drift and gentle melt
            self._frac_phase = (self._frac_phase + 0.0018 + pulse * 0.005) % 1.0
            self._frac_twist += 0.0018 + pulse * 0.008

    # ── Vortex / DMT tunnel warp ──────────────────────────────────────────────

    def _apply_vortex(self, rgb, twist):
        h, w = rgb.shape[:2]
        key  = (w, h)

        if self._vx_key != key:
            cx  = np.float32(w * 0.5)
            cy  = np.float32(h * 0.5)
            yi, xi = np.mgrid[0:h, 0:w].astype(np.float32)
            dx  = xi - cx
            dy  = yi - cy
            r   = np.hypot(dx, dy).astype(np.float32)
            max_r = float(math.hypot(cx, cy))
            rn  = np.clip(r / max_r, 0.0, 1.0).astype(np.float32)

            self._vx_r     = r
            self._vx_rn    = rn
            self._vx_theta = np.arctan2(dy, dx).astype(np.float32)
            self._vx_cx    = cx
            self._vx_cy    = cy
            self._vx_W     = w
            self._vx_H     = h
            # Softer vignette — breathe, not suffocate
            self._vx_vig   = (np.float32(1.0) - rn ** np.float32(2.5) * np.float32(0.45)).astype(np.float32)
            self._vx_key   = key

        t      = np.float32(twist)
        TWO_PI = np.float32(6.283185307179586)

        # Dual-frequency concentric ripple — breathing rings, no hard barrel pull
        ring1  = np.sin(self._vx_rn * TWO_PI * np.float32(3.0) + t * np.float32(0.8))
        ring2  = np.sin(self._vx_rn * TWO_PI * np.float32(5.0) - t * np.float32(0.5))
        ripple = (ring1 * np.float32(0.6) + ring2 * np.float32(0.4)) \
                 * np.float32(0.055) * (np.float32(1.2) - self._vx_rn)
        r_src  = self._vx_r * (np.float32(1.0) + ripple)

        # Very gentle melt rotation — slow centre-weighted stir
        theta_src = self._vx_theta + t * np.float32(0.035) \
                    * (np.float32(1.0) - self._vx_rn ** np.float32(1.5))

        src_x = np.clip(r_src * np.cos(theta_src) + self._vx_cx, 0, self._vx_W - 1).astype(np.int32)
        src_y = np.clip(r_src * np.sin(theta_src) + self._vx_cy, 0, self._vx_H - 1).astype(np.int32)

        warped = rgb[src_y, src_x]
        warped = (warped.astype(np.float32) * self._vx_vig[:, :, np.newaxis]).clip(0, 255).astype(np.uint8)
        return warped

    def _poll_fractal(self):
        try:
            img = self._frac_queue.get_nowait()
            cw  = self._bg_canvas.winfo_width()  or WIN_W
            ch  = self._bg_canvas.winfo_height() or WIN_H
            if img.width != cw or img.height != ch:
                img = img.resize((cw, ch), Image.BILINEAR)
            photo = ImageTk.PhotoImage(img)
            self._photo_ref = photo
            self._bg_canvas.itemconfig(self._fractal_img_id, image=photo)
        except queue.Empty:
            pass
        if not self._frac_stop.is_set():
            self.after(8, self._poll_fractal)

    # ── Audio playback ────────────────────────────────────────────────────────

    def _init_audio(self):
        if not _HAS_AUDIO:
            return
        base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
        mp3  = os.path.join(base, "music.mp3")
        if not os.path.exists(mp3):
            self._log_write(">> audio: music.mp3 not found")
            return
        self._audio_path = mp3
        threading.Thread(target=self._audio_worker, daemon=True).start()

    def _audio_worker(self):
        try:
            self._audio_device = miniaudio.PlaybackDevice(
                output_format=miniaudio.SampleFormat.SIGNED16,
                nchannels=2, sample_rate=48000, buffersize_msec=200,
            )
            gen = self._audio_stream()
            next(gen)  # prime: advance to first yield before miniaudio calls send()
            self._audio_device.start(gen)
            self._frac_stop.wait()
            self._audio_device.stop()
        except Exception as e:
            self.after(0, lambda m=str(e): self._log_write(f">> audio error: {m}"))

    def _audio_stream(self):
        # Buffer audio data and yield exactly required_frames each callback.
        # Without this, we'd yield fixed 1024-frame chunks while the device
        # requests ~9600 frames — filling only 10% of the buffer and playing
        # at 10% speed.
        BYTES_PER_FRAME = 4  # SIGNED16 × 2 channels = 4 bytes per frame
        buf = bytearray()

        required_frames = yield b""   # primed by next() before start() is called

        while not self._frac_stop.is_set():
            try:
                for raw in miniaudio.stream_file(
                    self._audio_path,
                    output_format=miniaudio.SampleFormat.SIGNED16,
                    nchannels=2, sample_rate=48000,
                    frames_to_read=2048,
                ):
                    if self._frac_stop.is_set():
                        return
                    if _HAS_NUMPY:
                        arr_f = np.frombuffer(raw, dtype=np.int16).astype(np.float32)
                        # RMS for fractal pulse — fast attack, slow decay
                        rms = float(np.sqrt(np.mean(arr_f ** 2))) / 32768.0
                        if rms > self._audio_pulse:
                            self._audio_pulse = 0.35 * rms + 0.65 * self._audio_pulse
                        else:
                            self._audio_pulse = 0.04 * rms + 0.96 * self._audio_pulse
                        # Volume in the same float pass
                        vol = 0.0 if self._audio_muted else self._audio_volume
                        if vol != 1.0:
                            arr_f *= vol
                            np.clip(arr_f, -32768, 32767, out=arr_f)
                            raw = arr_f.astype(np.int16).tobytes()
                    buf.extend(raw)
                    # Drain buffer in device-sized chunks
                    need = required_frames * BYTES_PER_FRAME
                    while len(buf) >= need:
                        out = bytes(buf[:need])
                        del buf[:need]
                        required_frames = yield out
                        need = required_frames * BYTES_PER_FRAME
            except Exception:
                break

    def _set_volume(self, val):
        self._audio_volume = float(val) / 100.0

    def _toggle_mute(self):
        self._audio_muted = not self._audio_muted
        self._mute_btn.config(
            text="[UNMUTE]" if self._audio_muted else "[MUTE]",
            fg="#ff4444" if self._audio_muted else GREEN,
        )

    # ── Button factory ────────────────────────────────────────────────────────

    def _mk_btn(self, parent, label, cmd):
        return tk.Button(
            parent, text=label, command=cmd,
            bg=BG2, fg=GREEN,
            activebackground=G_DIM, activeforeground=G_HI,
            font=FM_B, relief="flat",
            highlightbackground=BORDER, highlightthickness=1,
            cursor="hand2", padx=6, pady=2,
        )

    # ── Pulse animation ───────────────────────────────────────────────────────

    def _pulse_tick(self):
        brightness = (math.sin(time.time() * 2 * math.pi / 3.5) + 1) / 2
        r   = int(PULSE_LO[0] + (PULSE_HI[0] - PULSE_LO[0]) * brightness)
        g   = int(PULSE_LO[1] + (PULSE_HI[1] - PULSE_LO[1]) * brightness)
        b   = int(PULSE_LO[2] + (PULSE_HI[2] - PULSE_LO[2]) * brightness)
        col = f"#{r:02x}{g:02x}{b:02x}"
        self._title_lbl.config(fg=col)
        self._dl_btn.config(highlightbackground=col)
        self.after(50, self._pulse_tick)

    # ── Boot sequence ─────────────────────────────────────────────────────────

    def _boot_messages(self):
        msgs = [
            (100,  "▌ FLOPROAST SIGNAL TERMINAL v2.0"),
            (300,  "  ... establishing neural link ..."),
            (500,  "> uplink: acquired"),
            (700,  "> yt-dlp engine: online"),
            (900,  "> ffmpeg codec: loaded"),
            (1100, "> fractal matrix: rendering"),
            (1200, "> audio interface: " + ("active" if _HAS_AUDIO else "offline")),
            (1500, "> WARNING: signal integrity nominal"),
            (1800, "> standby.  awaiting target."),
            (1800, ""),
        ]
        for delay, msg in msgs:
            self.after(delay, lambda m=msg: self._log_write(m))

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _center_window(self):
        self.geometry(f"{WIN_W}x{WIN_H}")
        self.update_idletasks()
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        self.geometry(f"{WIN_W}x{WIN_H}+{(sw - WIN_W) // 2}+{(sh - WIN_H) // 2}")

    def _paste_url(self):
        try:
            self._url_var.set(self.clipboard_get().strip())
        except tk.TclError:
            pass

    def _browse_dir(self):
        d = filedialog.askdirectory(initialdir=self._dir_var.get())
        if d:
            self._dir_var.set(d)
            self._output_dir = d

    def _log_write(self, msg: str):
        msg = ANSI_ESCAPE.sub("", msg).rstrip()
        self._log.config(state="normal")
        self._log.insert("end", msg + "\n")
        self._log.see("end")
        self._log.config(state="disabled")

    def _set_status(self, msg: str):
        self._status_var.set(msg.upper())

    def _reset_ui(self):
        self._stop_event.clear()
        self._dl_btn.config(
            state="normal",
            text="[ EXECUTE DOWNLOAD ]",
            command=self._start_download,
            fg=GREEN,
        )
        self._downloading = False

    def _enable_folder_btn(self):
        self._folder_btn.config(
            state="normal", fg=GREEN,
            highlightbackground=BORDER,
        )

    def _open_last_folder(self):
        d = self._last_save_dir
        if d and os.path.isdir(d):
            import subprocess
            subprocess.Popen(["explorer", d])

    def _open_library(self):
        LibraryWindow(self, self._output_dir)

    # ── Download ──────────────────────────────────────────────────────────────

    def _start_download(self):
        url = self._url_var.get().strip()
        if not url:
            messagebox.showwarning("INPUT ERROR", "No YouTube URL entered.")
            return
        if self._downloading:
            return

        url = _strip_to_video(url)
        self._url_var.set(url)

        self._downloading = True
        self._stop_event.clear()
        self._dl_btn.config(
            text="[ ABORT ]",
            command=self._stop_download,
            fg="#ff4444",
            state="normal",
        )
        self._folder_btn.config(state="disabled", fg=T_DIM, highlightbackground=G_DIM)
        self._bar.set(0)
        self._pct_var.set("   0.0%")
        self._log.config(state="normal")
        self._log.delete("1.0", "end")
        self._log.config(state="disabled")
        self._log_write("// INITIATING DOWNLOAD SEQUENCE //")

        threading.Thread(target=self._download, args=(url,), daemon=True).start()

    def _stop_download(self):
        self._stop_event.set()
        self._dl_btn.config(state="disabled", text="[ ABORTING... ]")
        self._log_write("// ABORT SIGNAL SENT //")
        self._set_status("ABORTING...")

    def _progress_hook(self, d):
        if self._stop_event.is_set():
            raise Exception("DOWNLOAD ABORTED BY USER")
        status = d.get("status")
        if status == "downloading":
            total      = d.get("total_bytes") or d.get("total_bytes_estimate")
            downloaded = d.get("downloaded_bytes", 0)
            speed      = d.get("_speed_str", "").strip()
            eta        = d.get("_eta_str", "").strip()
            if total:
                pct = downloaded / total * 100
                self.after(0, lambda p=pct: self._bar.set(p))
                self.after(0, lambda p=pct: self._pct_var.set(f"{p:6.1f}%"))
            parts = [d.get("_percent_str", "").strip()]
            if speed: parts.append(speed)
            if eta:   parts.append(f"ETA {eta}")
            msg = " | ".join(p for p in parts if p)
            self.after(0, lambda m=msg: self._set_status(m))
        elif status == "finished":
            self.after(0, lambda: self._bar.set(100))
            self.after(0, lambda: self._pct_var.set(" 100.0%"))
            self.after(0, lambda: self._set_status("PROCESSING"))

    def _download(self, url: str):
        fmt_key  = self._format_var.get()
        fmt      = FORMATS[fmt_key]
        base_dir = self._dir_var.get()
        out_dir  = os.path.join(base_dir, date.today().strftime("%Y-%m-%d"))
        os.makedirs(out_dir, exist_ok=True)
        is_audio = "MP3" in fmt_key or "Audio" in fmt_key

        postprocessors = []
        if is_audio:
            postprocessors.append({
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "192",
            })
        # Always write a thumbnail so the library browser can display it
        postprocessors.append({"key": "FFmpegThumbnailsConvertor", "format": "jpg"})

        ydl_opts = {
            "format": fmt,
            "outtmpl": os.path.join(out_dir, "%(title)s.%(ext)s"),
            "progress_hooks": [self._progress_hook],
            "postprocessors": postprocessors,
            "writethumbnail": True,
            "quiet": True,
            "no_warnings": False,
            "logger": _YDLLogger(self._log_write),
            "merge_output_format": "mp4",
        }

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                self.after(0, lambda: self._set_status("ACQUIRING TARGET"))
                info  = ydl.extract_info(url, download=False)
                title = info.get("title", "UNKNOWN")
                self.after(0, lambda t=title: self._log_write(f"> target acquired: {t}"))
                self.after(0, lambda t=title: self._set_status(f"DOWNLOADING: {t}"))
                ydl.download([url])
            self._last_save_dir = out_dir
            self.after(0, lambda: self._set_status("DOWNLOAD COMPLETE"))
            self.after(0, lambda: self._log_write(f"> data stream saved: {out_dir}"))
            self.after(0, lambda: self._log_write("// TRANSMISSION COMPLETE //"))
            self.after(0, self._enable_folder_btn)
            self.after(0, lambda: messagebox.showinfo(
                "FLOPROAST // COMPLETE",
                f"Download complete.\n\nSaved to:\n{out_dir}"))
        except yt_dlp.utils.DownloadError as e:
            if self._stop_event.is_set():
                self.after(0, lambda: self._set_status("ABORTED"))
                self.after(0, lambda: self._log_write("// DOWNLOAD ABORTED //"))
            else:
                msg = str(e)
                self.after(0, lambda: self._set_status("ERROR - SEE LOG"))
                self.after(0, lambda m=msg: self._log_write(f">> ERROR: {m}"))
                self.after(0, lambda m=msg: messagebox.showerror("Download Error", m))
        except Exception as e:
            if self._stop_event.is_set():
                self.after(0, lambda: self._set_status("ABORTED"))
                self.after(0, lambda: self._log_write("// DOWNLOAD ABORTED //"))
            else:
                msg = str(e)
                self.after(0, lambda: self._set_status("UNEXPECTED ERROR"))
                self.after(0, lambda m=msg: self._log_write(f">> CRITICAL: {m}"))
                self.after(0, lambda m=msg: messagebox.showerror("Error", m))
        finally:
            self.after(0, self._reset_ui)


class LibraryWindow(tk.Toplevel):
    THUMB_W    = 160
    THUMB_H    = 90
    COLS       = 4
    MEDIA_EXTS = {".mp4", ".mkv", ".webm", ".avi", ".mov", ".mp3", ".m4a", ".ogg", ".flac", ".wav"}

    def __init__(self, master, downloads_root):
        super().__init__(master)
        self.title("FLOPROAST // SIGNAL LIBRARY")
        self.configure(bg=BG)
        self.geometry("820x620")
        self.minsize(600, 400)
        self._root  = downloads_root
        self._thumbs = []  # keep PhotoImage refs alive

        self._build()
        self._scan()

    # ── Layout ────────────────────────────────────────────────────────────────

    def _build(self):
        hdr = tk.Frame(self, bg=BG2, pady=6)
        hdr.pack(fill="x")

        tk.Label(hdr, text="▌ SIGNAL LIBRARY — ACQUIRED TRANSMISSIONS ▐",
                 bg=BG2, fg=DARK_R, font=FM_B).pack(side="left", padx=14)

        self._btn(hdr, "[ REFRESH ]", self._scan).pack(side="right", padx=14)

        sep = tk.Frame(self, bg=G_DIM, height=1)
        sep.pack(fill="x")

        outer = tk.Frame(self, bg=BG)
        outer.pack(fill="both", expand=True)

        self._canvas = tk.Canvas(outer, bg=BG, highlightthickness=0)
        vsb = ttk.Scrollbar(outer, orient="vertical", command=self._canvas.yview)
        self._canvas.configure(yscrollcommand=vsb.set)
        vsb.pack(side="right", fill="y")
        self._canvas.pack(side="left", fill="both", expand=True)

        self._grid_frame = tk.Frame(self._canvas, bg=BG)
        self._cw_id = self._canvas.create_window((0, 0), window=self._grid_frame, anchor="nw")

        self._grid_frame.bind("<Configure>", lambda _: self._canvas.configure(
            scrollregion=self._canvas.bbox("all")))
        self._canvas.bind("<Configure>", lambda e: self._canvas.itemconfig(
            self._cw_id, width=e.width))
        self._canvas.bind("<Enter>", lambda _: self._canvas.bind_all(
            "<MouseWheel>", lambda e: self._canvas.yview_scroll(int(-e.delta / 120), "units")))
        self._canvas.bind("<Leave>", lambda _: self._canvas.unbind_all("<MouseWheel>"))

    def _btn(self, parent, label, cmd, fg=GREEN):
        return tk.Button(
            parent, text=label, command=cmd,
            bg=BG2, fg=fg,
            activebackground=G_DIM, activeforeground=G_HI,
            font=FM_B, relief="flat",
            highlightbackground=BORDER, highlightthickness=1,
            cursor="hand2", padx=6, pady=2,
        )

    # ── Scan & grid ───────────────────────────────────────────────────────────

    def _scan(self):
        for w in self._grid_frame.winfo_children():
            w.destroy()
        self._thumbs.clear()

        entries = []
        if os.path.isdir(self._root):
            for date_dir in sorted(os.listdir(self._root), reverse=True):
                sub = os.path.join(self._root, date_dir)
                if not os.path.isdir(sub):
                    continue
                for fname in sorted(os.listdir(sub)):
                    if os.path.splitext(fname)[1].lower() in self.MEDIA_EXTS:
                        entries.append((date_dir, os.path.join(sub, fname)))

        if not entries:
            tk.Label(self._grid_frame,
                     text="NO SIGNAL — LIBRARY EMPTY",
                     bg=BG, fg=SCAR_R,
                     font=("Consolas", 14, "bold"),
                     pady=60).grid(row=0, column=0, padx=60)
            return

        for idx, (date_str, fpath) in enumerate(entries):
            self._build_card(self._grid_frame,
                             idx // self.COLS, idx % self.COLS,
                             date_str, fpath)

    def _build_card(self, parent, row, col, date_str, fpath):
        fname  = os.path.basename(fpath)
        base   = os.path.splitext(fname)[0]
        folder = os.path.dirname(fpath)

        # Find matching thumbnail (yt-dlp writes <title>.jpg next to the file)
        thumb_path = None
        for ext in (".jpg", ".jpeg", ".png", ".webp"):
            c = os.path.join(folder, base + ext)
            if os.path.exists(c):
                thumb_path = c
                break

        card = tk.Frame(parent, bg=BG2,
                        highlightbackground=BORDER, highlightthickness=1,
                        padx=4, pady=4)
        card.grid(row=row, column=col, padx=6, pady=6, sticky="n")

        # ── Thumbnail ──────────────────────────────────────────────────────
        if _HAS_PIL:
            try:
                if thumb_path:
                    src = Image.open(thumb_path).convert("RGB")
                else:
                    src = self._placeholder()
                src.thumbnail((self.THUMB_W, self.THUMB_H), Image.LANCZOS)
                bg_img = Image.new("RGB", (self.THUMB_W, self.THUMB_H), (2, 12, 2))
                bg_img.paste(src, ((self.THUMB_W - src.width) // 2,
                                   (self.THUMB_H - src.height) // 2))
                photo = ImageTk.PhotoImage(bg_img)
                self._thumbs.append(photo)
                tk.Label(card, image=photo, bg=BG2).pack()
            except Exception:
                tk.Label(card, text="[ NO SIGNAL ]",
                         bg=BG2, fg=G_DIM, font=FM,
                         width=22, height=5).pack()
        else:
            tk.Label(card, text="[ NO SIGNAL ]",
                     bg=BG2, fg=G_DIM, font=FM,
                     width=22, height=5).pack()

        # ── Title ──────────────────────────────────────────────────────────
        display = base if len(base) <= 22 else base[:19] + "..."
        tk.Label(card, text=display, bg=BG2, fg=TEXT, font=FM,
                 wraplength=self.THUMB_W, justify="center").pack(pady=(4, 1))

        # ── Date + size ────────────────────────────────────────────────────
        try:
            sz = os.path.getsize(fpath)
            sz_str = f"{sz/1048576:.1f} MB" if sz >= 1048576 else f"{sz/1024:.0f} KB"
        except OSError:
            sz_str = "?"
        tk.Label(card, text=f"{date_str}  ·  {sz_str}",
                 bg=BG2, fg=T_DIM, font=FM).pack()

        # ── Action buttons ─────────────────────────────────────────────────
        bf = tk.Frame(card, bg=BG2)
        bf.pack(pady=(4, 0))
        self._btn(bf, "[PLAY]",   lambda p=fpath:  self._play(p)).pack(side="left", padx=2)
        self._btn(bf, "[FOLDER]", lambda d=folder: self._reveal(d)).pack(side="left", padx=2)

    # ── Utilities ─────────────────────────────────────────────────────────────

    def _placeholder(self):
        img  = Image.new("RGB", (self.THUMB_W, self.THUMB_H), (4, 16, 4))
        draw = ImageDraw.Draw(img)
        draw.rectangle([0, 0, self.THUMB_W - 1, self.THUMB_H - 1],
                       outline=(26, 107, 26), width=1)
        cx, cy = self.THUMB_W // 2, self.THUMB_H // 2
        draw.text((cx, cy - 8),  "NO",     fill=(90, 0, 0), anchor="mm")
        draw.text((cx, cy + 8),  "SIGNAL", fill=(90, 0, 0), anchor="mm")
        return img

    def _play(self, path):
        try:
            os.startfile(path)
        except Exception as e:
            messagebox.showerror("PLAYBACK ERROR", str(e), parent=self)

    def _reveal(self, folder):
        try:
            import subprocess
            subprocess.Popen(["explorer", folder])
        except Exception as e:
            messagebox.showerror("FOLDER ERROR", str(e), parent=self)


class _YDLLogger:
    def __init__(self, write_fn):
        self._write = write_fn

    def debug(self, msg):
        if msg.startswith("[debug]"):
            return
        self._write(f"  {msg}")

    def info(self, msg):
        self._write(f"> {msg}")

    def warning(self, msg):
        self._write(f">> WARNING: {msg}")

    def error(self, msg):
        self._write(f">> ERROR: {msg}")


if __name__ == "__main__":
    try:
        from ctypes import windll
        windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        pass

    app = DXDownloader()
    app.mainloop()
