#!/usr/bin/env python3
"""Alternative avatars for @Open_your_inner_sun_bot (inner-sun meditation theme)."""
import os
import numpy as np
from PIL import Image, ImageDraw, ImageFilter

SIZE = 1024
HERE = os.path.dirname(__file__)
rng = np.random.default_rng(11)

yy, xx = np.mgrid[0:SIZE, 0:SIZE].astype(np.float64)

EMERALD = np.array([0x10, 0x50, 0x40]) / 255
PURPLE = np.array([0x42, 0x31, 0x89]) / 255
DEEP = np.array([0x14, 0x0E, 0x30]) / 255
GOLD = np.array([0xD4, 0xAF, 0x37]) / 255
ORANGE = np.array([0xF2, 0x8C, 0x28]) / 255
WHITE = np.array([1.0, 0.97, 0.88])


def polar(cx, cy):
    dx, dy = xx - cx, yy - cy
    return np.sqrt(dx ** 2 + dy ** 2) / (SIZE / 2), np.arctan2(dy, dx)


def background(vertical=False):
    if vertical:
        t = np.clip(yy / SIZE, 0, 1)[..., None]
    else:
        t = np.clip((xx + yy) / (2 * SIZE), 0, 1)[..., None]
    bg = PURPLE * (1 - t) + EMERALD * t
    r, _ = polar(SIZE / 2, SIZE / 2)
    v = np.clip(r, 0, 1)[..., None] ** 1.5
    return bg * (1 - 0.55 * v) + DEEP * 0.55 * v


def glow(cx, cy, sigma, col, amp=1.0):
    return (amp * np.exp(-(((xx - cx) ** 2 + (yy - cy) ** 2) / (2 * sigma ** 2))))[..., None] * col


def sparkles(img, n=80, rmin=0.3, rmax=0.92, cx=SIZE / 2, cy=SIZE / 2):
    for _ in range(n):
        a = rng.uniform(0, 2 * np.pi)
        rr = rng.uniform(rmin, rmax)
        px, py = cx + rr * np.cos(a) * SIZE / 2, cy + rr * np.sin(a) * SIZE / 2
        img += glow(px, py, rng.uniform(1.5, 4.5), GOLD, rng.uniform(0.3, 1.0))
    return img


def rays(cx, cy, n=16, width=0.1, inner=0.15, spread=0.55):
    r, ang = polar(cx, cy)
    out = width * (0.5 + 0.5 * np.cos(n * ang)) ** 6
    return out * np.exp(-((r - inner) / spread) ** 2) * (r > inner)


def to_img(img):
    return Image.fromarray((np.clip(img, 0, 1) * 255).astype(np.uint8))


def mask_of(draw_fn, blur=3):
    m = Image.new('L', (SIZE, SIZE), 0)
    draw_fn(ImageDraw.Draw(m), SIZE)
    return np.asarray(m.filter(ImageFilter.GaussianBlur(blur))).astype(np.float64) / 255


def save(img, name):
    out = to_img(img).filter(ImageFilter.GaussianBlur(0.6))
    path = os.path.join(HERE, name)
    out.save(path, optimize=True)
    out.resize((512, 512), Image.LANCZOS).save(path.replace('.png', '-512.png'), optimize=True)
    print(path)


# ---------- Variant B: sun rising from a lotus ----------
def variant_lotus():
    img = background(vertical=True)
    cx, cy = SIZE / 2, SIZE * 0.50
    img += rays(cx, cy, 20, 0.12, 0.13, 0.5)[..., None] * GOLD
    img += glow(cx, cy, SIZE * 0.22, ORANGE * 0.6 + GOLD * 0.4, 0.8)
    img += glow(cx, cy, SIZE * 0.09, WHITE, 1.3)
    img = sparkles(img, 70, 0.35)

    def petals(d, S):
        base = (S * 0.5, S * 0.86)
        for tips, h, w in [([-70, -35, 0, 35, 70], 0.40, 0.19), ([-52, -17, 17, 52], 0.35, 0.18), ([-30, 0, 30], 0.27, 0.17)]:
            for deg in tips:
                a = np.deg2rad(deg)
                L = S * h
                hw = S * w / 2
                # leaf shape: pointed at both ends, widest at 55% of the length
                pts = []
                for side in (1, -1):
                    rng_u = np.linspace(0, 1, 40) if side == 1 else np.linspace(1, 0, 40)
                    for u in rng_u:
                        off = side * hw * np.sin(np.pi * u) ** 0.8 * (1 - 0.3 * u)
                        px = base[0] + L * u * np.sin(a) + off * np.cos(a)
                        py = base[1] - L * u * np.cos(a) + off * np.sin(a)
                        pts.append((px, py))
                d.polygon(pts, fill=255)
                d.polygon(pts, outline=0, width=int(S * 0.008))

    m = mask_of(petals, 2)
    r, _ = polar(cx, SIZE * 0.95)
    petal_col = (PURPLE * 0.7 + np.array([0.75, 0.55, 0.95]) * 0.5)[None, None, :] * (1 - 0.35 * r[..., None])
    petal_col += glow(cx, cy, SIZE * 0.25, GOLD, 0.6)
    edge = np.clip(m - mask_of(petals, 12), 0, 1)
    img = img * (1 - m[..., None]) + np.clip(petal_col, 0, 1) * m[..., None] + edge[..., None] * GOLD * 0.8
    save(img, 'jam-bot-avatar-lotus.png')


# ---------- Variant C: sun held in open palms ----------
def variant_hands():
    img = background()
    cx, cy = SIZE / 2, SIZE * 0.42
    img += rays(cx, cy, 14, 0.1, 0.12, 0.5)[..., None] * GOLD
    img += glow(cx, cy, SIZE * 0.2, ORANGE * 0.6 + GOLD * 0.4, 0.8)
    img += glow(cx, cy, SIZE * 0.085, WHITE, 1.3)
    img = sparkles(img, 60, 0.3)

    def hands(d, S):
        def hand(sign):
            # cupped palm as a tilted rounded blob + fingers curling up toward the sun
            palm = Image.new('L', (int(S * 0.30), int(S * 0.26)), 0)
            ImageDraw.Draw(palm).rounded_rectangle((0, 0, palm.width - 1, palm.height - 1), int(S * 0.09), fill=255)
            palm = palm.rotate(sign * 22, expand=True, resample=Image.BICUBIC)
            d._image.paste(255, (int(S * (0.5 + sign * 0.19) - palm.width / 2), int(S * 0.64 - palm.height / 2)), palm)
            for fx, fy, L, tilt in [(0.06, 0.60, 0.17, 12), (0.13, 0.57, 0.20, 18), (0.20, 0.56, 0.19, 26), (0.27, 0.58, 0.16, 36)]:
                f = Image.new('L', (int(S * 0.058), int(S * L)), 0)
                ImageDraw.Draw(f).rounded_rectangle((0, 0, f.width - 1, f.height - 1), f.width // 2, fill=255)
                f = f.rotate(sign * tilt, expand=True, resample=Image.BICUBIC)
                d._image.paste(255, (int(S * (0.5 + sign * fx) - f.width / 2), int(S * fy - f.height * 0.85)), f)
            # forearm
            d.polygon([(S * (0.5 + sign * 0.08), S * 0.74), (S * (0.5 + sign * 0.30), S * 0.70),
                       (S * (0.5 + sign * 0.36), S * 1.0), (S * (0.5 + sign * 0.14), S * 1.0)], fill=255)
        hand(-1)
        hand(1)

    m = mask_of(hands, 2)
    skin = DEEP * 0.85
    fig = skin[None, None, :] + glow(cx, cy, SIZE * 0.3, ORANGE * 0.8 + GOLD * 0.5, 0.9)
    rim = np.clip(m - mask_of(hands, 10), 0, 1)
    img = img * (1 - m[..., None]) + np.clip(fig, 0, 1) * m[..., None] + rim[..., None] * GOLD * 0.9
    save(img, 'jam-bot-avatar-hands.png')


# ---------- Variant D: sunrise over calm water (horizon) ----------
def variant_sunrise():
    img = background(vertical=True)
    hy = SIZE * 0.6
    cx, cy = SIZE / 2, hy - SIZE * 0.02
    img += rays(cx, cy, 18, 0.1, 0.1, 0.6)[..., None] * GOLD * (yy < hy)[..., None]
    img += glow(cx, cy, SIZE * 0.3, ORANGE * 0.6 + GOLD * 0.4, 0.7)
    sun = (np.sqrt((xx - cx) ** 2 + (yy - cy) ** 2) < SIZE * 0.13) & (yy < hy)
    img += sun[..., None] * (WHITE * 0.9 + GOLD * 0.3)
    img += glow(cx, cy, SIZE * 0.1, WHITE, 0.6) * (yy < hy)[..., None]
    # water: darker emerald with horizontal shimmer reflecting the sun
    water = yy >= hy
    shimmer = (0.5 + 0.5 * np.sin(yy / 6.0 + np.sin(xx / 40.0) * 2)) ** 3
    refl = np.exp(-((xx - cx) / (SIZE * 0.10 + (yy - hy) * 0.35)) ** 2) * np.exp(-(yy - hy) / (SIZE * 0.35))
    img = np.where(water[..., None], EMERALD * 0.6 + DEEP * 0.4 + (refl * (0.35 + 0.65 * shimmer))[..., None] * (ORANGE * 0.7 + GOLD * 0.6), img)
    img = sparkles(img, 50, 0.4, 0.95, cx, SIZE * 0.3)
    save(img, 'jam-bot-avatar-sunrise.png')


# ---------- Variant E: minimal sun with orange slice segments ----------
def variant_minimal():
    img = background()
    cx, cy = SIZE / 2, SIZE / 2
    r, ang = polar(cx, cy)
    img += glow(cx, cy, SIZE * 0.3, ORANGE * 0.5 + GOLD * 0.4, 0.6)
    disk = r < 0.34
    seg = (0.5 + 0.5 * np.cos(10 * ang)) ** 0.5
    lines = np.abs(((ang * 10 / (2 * np.pi)) % 1) - 0.5) < 0.03
    inner = r < 0.06
    col = ORANGE * 0.85 + GOLD * 0.35 * seg[..., None]
    col = np.where((lines | inner | (r > 0.31))[..., None], (WHITE * 0.9 + GOLD * 0.2)[None, None, :], col)
    img = np.where(disk[..., None], col, img)
    ring = (r > 0.34) & (r < 0.375)
    img = np.where(ring[..., None], GOLD[None, None, :], img)
    petals_ang = np.abs(((ang * 12 / (2 * np.pi)) % 1) - 0.5) < 0.16
    burst = petals_ang & (r > 0.40) & (r < 0.48 + 0.04 * np.cos(12 * ang))
    img = np.where(burst[..., None], img + GOLD * 0.9, img)
    img = sparkles(img, 60, 0.55)
    save(img, 'jam-bot-avatar-minimal.png')


if __name__ == '__main__':
    variant_lotus()
    variant_hands()
    variant_sunrise()
    variant_minimal()
