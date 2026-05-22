# cython: language_level=3, boundscheck=False, wraparound=False,
#         cdivision=True, nonecheck=False, initializedcheck=False

"""
Cython-optimised fractal kernel — disturbing dual-band coloriser.

Key design:
  * Dual-frequency sin interference (7× and 11× with golden-ratio phase offset)
    creates quasi-periodic banding with deep black valleys — more organic/unsettling
    than a single sine
  * Product of two waves steepens contrast non-linearly
  * pulse (0..1) from audio RMS: bleeds in red corruption, then white overload
  * Interior → pure void black (not the old dark-green)
  * prange + nogil + OpenMP parallelism across rows
"""

import numpy as np
cimport numpy as cnp
from libc.math  cimport log2, sqrt, sin
from cython.parallel cimport prange

ctypedef cnp.float32_t f32
ctypedef cnp.uint8_t   u8

DEF _TWO_PI = 6.283185307179586
DEF _PHI    = 1.6180339887498948   # golden ratio — keeps the two bands incommensurable


# ── Mandelbrot smooth-escape kernel ──────────────────────────────────────────
def mandelbrot(double cx, double cy, double zoom,
               int w, int h, int max_iter):
    """Return float32 (h, w) smooth escape count. max_iter = interior."""
    cdef:
        double scale  = 3.5 / zoom
        double aspect = <double>w / <double>h
        double x0 = cx - scale * aspect * 0.5
        double y0 = cy - scale * 0.5
        double dx = scale * aspect / (w - 1)
        double dy = scale         / (h - 1)

        int    row, col, i
        double cr, ci, zr, zi, zr2, zi2, az

        cnp.ndarray[f32, ndim=2] esc = np.full((h, w), <float>max_iter,
                                                dtype=np.float32)
        f32[:, :] ev = esc

    for row in prange(h, nogil=True, schedule='guided'):
        ci = y0 + row * dy
        for col in range(w):
            cr = x0 + col * dx
            zr = zi = zr2 = zi2 = 0.0
            for i in range(1, max_iter + 1):
                zi  = 2.0 * zr * zi + ci
                zr  = zr2 - zi2 + cr
                zr2 = zr * zr
                zi2 = zi * zi
                if zr2 + zi2 > 4.0:
                    az = sqrt(zr2 + zi2)
                    if az < 1.001:
                        az = 1.001
                    ev[row, col] = i + 1.0 - log2(log2(az))
                    break
    return esc


# ── Disturbing dual-band coloriser ───────────────────────────────────────────
def colorize(cnp.ndarray[f32, ndim=2] esc, int max_iter, float phase,
             float pulse=0.0):
    """
    Map smooth escape → RGB uint8 (h, w, 3).

    Interior → pure black void.
    Exterior → Deus Ex green with dual-frequency interference rings.
    pulse (0..1): audio-driven red corruption bleeding into white overload.
    """
    cdef:
        int   h  = esc.shape[0]
        int   w  = esc.shape[1]
        float mi = <float>max_iter
        int   row, col
        float e, t, a1, a2, wv1, wv2, bright, r, g, b, flash

        cnp.ndarray[u8, ndim=3] rgb = np.zeros((h, w, 3), dtype=np.uint8)
        f32[:, :] ev   = esc
        u8[:, :, :] rv = rgb

    for row in prange(h, nogil=True, schedule='static'):
        for col in range(w):
            e = ev[row, col]
            if e >= mi - 0.5:
                # Interior: void — true black
                rv[row, col, 0] = 0
                rv[row, col, 1] = 0
                rv[row, col, 2] = 0
            else:
                t = e / mi
                if t > 1.0: t = 1.0
                if t < 0.0: t = 0.0

                # Dual-frequency interference — 7× and 11× with golden-ratio offset
                a1  = (t * 7.0  + phase)                   * <float>_TWO_PI
                a2  = (t * 11.0 + phase * <float>_PHI)     * <float>_TWO_PI
                wv1 = <float>sin(a1) * 0.5 + 0.5
                wv2 = <float>sin(a2) * 0.5 + 0.5

                # Product → deep black valleys; squared product steepens contrast
                bright = wv1 * wv2
                bright = bright * bright

                # Base: Deus Ex green dominant, faint red/blue undertone
                g = bright * 190.0
                r = bright * 22.0 + wv1 * 14.0
                b = bright * 10.0

                # Pulse: red corruption modulated by wv1 so it flickers, not flat
                flash = pulse * wv1
                r = r + flash * 220.0
                g = g + flash * 48.0
                b = b + flash * 35.0

                # Hard white overload on extreme pulse (top 30%)
                if pulse > 0.7:
                    flash = (pulse - 0.7) * 3.333
                    r = r + flash * (255.0 - r)
                    g = g + flash * (255.0 - g) * 0.5
                    b = b + flash * (255.0 - b) * 0.3

                if r > 255.0: r = 255.0
                if g > 255.0: g = 255.0
                if b > 255.0: b = 255.0
                if r < 0.0:   r = 0.0
                if g < 0.0:   g = 0.0
                if b < 0.0:   b = 0.0

                rv[row, col, 0] = <u8>r
                rv[row, col, 1] = <u8>g
                rv[row, col, 2] = <u8>b
    return rgb
