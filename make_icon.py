"""
Generates floproast.ico — a floppy bacon sushi roll icon.
"""
from PIL import Image, ImageDraw
import math


def draw_icon(size: int) -> Image.Image:
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    s = size

    # ── Background circle (dark navy) ─────────────────────────────────────────
    draw.ellipse([2, 2, s - 2, s - 2], fill="#1a1a2e")

    # ── Nori (dark outer band) ────────────────────────────────────────────────
    pad = s * 0.05
    draw.ellipse([pad, pad, s - pad, s - pad], fill="#111118")

    # ── Rice (white band) ─────────────────────────────────────────────────────
    rice_pad = s * 0.13
    draw.ellipse([rice_pad, rice_pad, s - rice_pad, s - rice_pad], fill="#f0ede6")

    # ── Bacon filling (red center) ────────────────────────────────────────────
    fill_pad = s * 0.28
    draw.ellipse([fill_pad, fill_pad, s - fill_pad, s - fill_pad], fill="#e63946")

    # ── Bacon fat stripes (lighter pink diagonals) ───────────────────────────
    stripe_color = "#f4a2aa"
    cx, cy = s / 2, s / 2
    r_inner = s * 0.22
    for angle_deg in [-35, 10, 55]:
        angle = math.radians(angle_deg)
        x1 = cx + r_inner * math.cos(angle) - s * 0.02
        y1 = cy + r_inner * math.sin(angle) - s * 0.09
        x2 = cx - r_inner * math.cos(angle) + s * 0.02
        y2 = cy - r_inner * math.sin(angle) + s * 0.09
        w = max(1, int(s * 0.04))
        draw.line([(x1, y1), (x2, y2)], fill=stripe_color, width=w)

    # ── "Floppy" droop — a small dark arc at the bottom ─────────────────────
    droop_bbox = [s * 0.25, s * 0.62, s * 0.75, s * 0.88]
    draw.arc(droop_bbox, start=20, end=160, fill="#1a1a2e", width=max(1, int(s * 0.04)))

    # ── Outer glow ring (accent) ──────────────────────────────────────────────
    draw.ellipse([1, 1, s - 1, s - 1], outline="#e63946", width=max(1, int(s * 0.025)))

    return img


def main():
    sizes = [16, 32, 48, 64, 128, 256]
    frames = [draw_icon(sz) for sz in sizes]
    frames[0].save(
        "floproast.ico",
        format="ICO",
        sizes=[(sz, sz) for sz in sizes],
        append_images=frames[1:],
    )
    print("floproast.ico created.")


if __name__ == "__main__":
    main()
