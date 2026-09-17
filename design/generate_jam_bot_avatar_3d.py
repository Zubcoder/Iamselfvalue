#!/usr/bin/env python3
"""Volumetric (3D-shaded) avatars for @Open_your_inner_sun_bot.

Objects are built as heightmaps, shaded with Blinn-Phong lighting and composited
over a deep purple -> emerald background, in the same style as the site hero.
"""
import os
import numpy as np
from PIL import Image, ImageDraw, ImageFilter
from scipy.ndimage import gaussian_filter, distance_transform_edt

SIZE = 1024
HERE = os.path.dirname(os.path.abspath(__file__))
rng = np.random.default_rng(21)
yy, xx = np.mgrid[0:SIZE, 0:SIZE].astype(np.float64)

EMERALD = np.array([0x10, 0x50, 0x40]) / 255
EMERALD_L = np.array([0x2A, 0x8C, 0x6E]) / 255
PURPLE = np.array([0x42, 0x31, 0x89]) / 255
PURPLE_L = np.array([0x7B, 0x63, 0xD6]) / 255
DEEP = np.array([0x14, 0x0E, 0x30]) / 255
GOLD = np.array([0xD4, 0xAF, 0x37]) / 255
GOLD_D = np.array([0x8A, 0x63, 0x14]) / 255
ORANGE = np.array([0xF2, 0x8C, 0x28]) / 255
WHITE = np.array([1.0, 0.97, 0.88])

LIGHT = np.array([-0.45, -0.6, 0.66])
LIGHT /= np.linalg.norm(LIGHT)
VIEW = np.array([0.0, 0.0, 1.0])
HALF = LIGHT + VIEW
HALF /= np.linalg.norm(HALF)


def glow(cx, cy, sigma, col, amp=1.0):
    return (amp * np.exp(-(((xx - cx) ** 2 + (yy - cy) ** 2) / (2 * sigma ** 2))))[..., None] * col


def background():
    t = np.clip((xx * 0.6 + yy) / (1.6 * SIZE), 0, 1)[..., None]
    bg = PURPLE * (1 - t) + EMERALD * t
    r = np.sqrt((xx - SIZE / 2) ** 2 + (yy - SIZE / 2) ** 2) / (SIZE / 2)
    v = np.clip(r, 0, 1)[..., None] ** 1.4
    bg = bg * (1 - 0.6 * v) + DEEP * 0.6 * v
    # soft volumetric blobs like the hero background
    bg += glow(SIZE * 0.2, SIZE * 0.25, SIZE * 0.22, PURPLE_L, 0.35)
    bg += glow(SIZE * 0.85, SIZE * 0.8, SIZE * 0.25, EMERALD_L, 0.3)
    return bg


def sparkles(img, n=70, rmin=0.35, rmax=0.95):
    for _ in range(n):
        a = rng.uniform(0, 2 * np.pi)
        rr = rng.uniform(rmin, rmax)
        px, py = SIZE / 2 + rr * np.cos(a) * SIZE / 2, SIZE / 2 + rr * np.sin(a) * SIZE / 2
        img += glow(px, py, rng.uniform(1.5, 4.0), GOLD, rng.uniform(0.3, 1.0))
    return img


def shade(height, mask, base_col, spec=0.9, shin=60, rim_col=GOLD, rim_amt=0.5, metal=0.5):
    """Blinn-Phong shading of a heightmap. base_col may be (3,) or (H,W,3)."""
    gy, gx = np.gradient(height)
    n = np.dstack([-gx, -gy, np.ones_like(height)])
    n /= np.linalg.norm(n, axis=2, keepdims=True)
    diff = np.clip(n @ LIGHT, 0, 1)
    specular = np.clip(n @ HALF, 0, 1) ** shin
    fres = (1 - np.clip(n[..., 2], 0, 1)) ** 2.5
    base = np.broadcast_to(base_col, (SIZE, SIZE, 3)) if np.ndim(base_col) == 1 else base_col
    col = base * (0.28 + 0.85 * diff)[..., None]
    col += (spec * specular)[..., None] * (WHITE * (1 - metal) + base * metal * 1.6)
    col += (rim_amt * fres)[..., None] * rim_col
    return np.clip(col, 0, 1) * mask[..., None]


def heightmap_from_mask(mask, depth, softness):
    """Rounded 'pillow' height from a binary mask via distance transform."""
    d = distance_transform_edt(mask > 0.5)
    h = np.tanh(d / softness) * depth
    return gaussian_filter(h, 1.5)


def sphere(cx, cy, R):
    d2 = (xx - cx) ** 2 + (yy - cy) ** 2
    mask = (d2 <= R * R).astype(np.float64)
    h = np.sqrt(np.clip(R * R - d2, 0, None))
    return h, gaussian_filter(mask, 1.0)


def drop_shadow(mask, dx, dy, blur, strength=0.55):
    m = Image.fromarray((mask * 255).astype(np.uint8)).transform(
        (SIZE, SIZE), Image.AFFINE, (1, 0, -dx, 0, 1, -dy))
    m = np.asarray(m.filter(ImageFilter.GaussianBlur(blur))).astype(np.float64) / 255
    return m * strength


def composite(img, layer, mask):
    return img * (1 - mask[..., None]) + layer


def save(img, name):
    out = Image.fromarray((np.clip(img, 0, 1) * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(0.5))
    path = os.path.join(HERE, name)
    out.save(path, optimize=True)
    out.resize((512, 512), Image.LANCZOS).save(path.replace('.png', '-512.png'), optimize=True)
    print(path)


def mask_draw(fn, blur=1.0):
    m = Image.new('L', (SIZE, SIZE), 0)
    fn(ImageDraw.Draw(m), SIZE)
    return np.asarray(m.filter(ImageFilter.GaussianBlur(blur))).astype(np.float64) / 255


def sun_glow(img, cx, cy, R):
    img += glow(cx, cy, R * 2.2, ORANGE * 0.6 + GOLD * 0.5, 0.75)
    img += glow(cx, cy, R * 1.25, GOLD, 0.5)
    return img


def sun_sphere(img, cx, cy, R, ray_len=0.0, with_glow=True):
    """Glossy golden-orange sun sphere with glow; optional embossed rays."""
    if with_glow:
        img = sun_glow(img, cx, cy, R)
    if ray_len:
        def rays(d, S):
            for k in range(16):
                a = 2 * np.pi * k / 16 + np.pi / 16
                L = R * (1.35 + ray_len * (1.0 if k % 2 == 0 else 0.6))
                w = R * 0.11
                p1 = (cx + R * 1.05 * np.cos(a), cy + R * 1.05 * np.sin(a))
                p2 = (cx + L * np.cos(a), cy + L * np.sin(a))
                nx, ny = -np.sin(a) * w, np.cos(a) * w
                d.polygon([(p1[0] + nx, p1[1] + ny), (p1[0] - nx, p1[1] - ny), p2], fill=255)
        rm = mask_draw(rays, 0.8)
        img += drop_shadow(rm, 10, 14, 10, 0.45)[..., None] * (DEEP - img) * 0.9
        rh = heightmap_from_mask(rm, 18, 9)
        img = composite(img, shade(rh, rm, GOLD, 0.8, 50, WHITE, 0.3, 0.6), rm)
    h, m = sphere(cx, cy, R)
    img += drop_shadow(m, 14, 20, 16, 0.5)[..., None] * (DEEP - img) * 0.9
    # gradient base: hot white-gold center -> orange edge
    d = np.sqrt((xx - cx) ** 2 + (yy - cy) ** 2) / R
    base = (WHITE * 0.9 + GOLD * 0.3) * (1 - np.clip(d, 0, 1) ** 1.6)[..., None] + ORANGE * np.clip(d, 0, 1)[..., None] ** 1.6
    layer = shade(h / R * 60, m, base, 1.1, 90, ORANGE, 0.5, 0.3)
    # emissive: lift the shadow side so it reads as a glowing sun, not a metal ball
    layer = layer * 0.55 + (base * m[..., None]) * 0.55
    layer += (m * np.exp(-(d / 0.5) ** 2) * 0.55)[..., None] * WHITE
    return composite(img, np.clip(layer, 0, 1), m)


# ---------- Variant 1: 3D golden lotus with sun sphere ----------
def variant_lotus3d():
    img = background()
    cx, cy = SIZE / 2, SIZE * 0.47
    base_pt = (SIZE * 0.5, SIZE * 0.86)
    rows = [([-70, -35, 0, 35, 70], 0.40, 0.19, np.array([0.36, 0.22, 0.72])),
            ([-52, -17, 17, 52], 0.35, 0.18, np.array([0.55, 0.38, 0.92])),
            ([-30, 0, 30], 0.27, 0.17, np.array([0.78, 0.62, 1.0]))]

    def petal_mask(deg, h, w):
        def fn(d, S):
            a = np.deg2rad(deg)
            L, hw = S * h, S * w / 2
            pts = []
            for side in (1, -1):
                us = np.linspace(0, 1, 50) if side == 1 else np.linspace(1, 0, 50)
                for u in us:
                    off = side * hw * np.sin(np.pi * u) ** 0.8 * (1 - 0.3 * u)
                    pts.append((base_pt[0] + L * u * np.sin(a) + off * np.cos(a),
                                base_pt[1] - L * u * np.cos(a) + off * np.sin(a)))
            d.polygon(pts, fill=255)
        return mask_draw(fn, 0.8)

    img = sun_sphere(img, cx, cy, SIZE * 0.14)
    for tips, h, w, col in rows:
        for deg in tips:
            m = petal_mask(deg, h, w)
            img += drop_shadow(m, 8, 12, 12, 0.5)[..., None] * (DEEP - img) * 0.9
            hm = heightmap_from_mask(m, 30, 28)
            # gold light from the sun above tints petal tops
            dist = np.sqrt((xx - cx) ** 2 + (yy - cy) ** 2) / SIZE
            tint = col[None, None, :] * (1 - np.clip(dist * 1.6, 0, 0.45))[..., None] + GOLD * np.clip(0.45 - dist * 1.6, 0, 0.45)[..., None]
            layer = shade(hm, m, tint, 0.7, 70, GOLD, 0.8, 0.15)
            img = composite(img, layer, m)
    img = sparkles(img, 60)
    save(img, 'jam-bot-avatar-3d-lotus.png')


# ---------- Variant 2: 3D meditating figure with sun in the chest ----------
def variant_figure3d():
    img = background()

    def figure(d, S):
        def P(x, y):
            return (S * x, S * y)
        d.ellipse((S * 0.437, S * 0.16, S * 0.563, S * 0.30), fill=255)
        d.rounded_rectangle((S * 0.475, S * 0.28, S * 0.525, S * 0.35), 14, fill=255)
        d.polygon([P(0.36, 0.38), P(0.64, 0.38), P(0.62, 0.64), P(0.38, 0.64)], fill=255)
        d.ellipse((S * 0.34, S * 0.335, S * 0.66, S * 0.44), fill=255)
        d.polygon([P(0.36, 0.39), P(0.415, 0.38), P(0.31, 0.66), P(0.25, 0.66)], fill=255)
        d.polygon([P(0.64, 0.39), P(0.585, 0.38), P(0.69, 0.66), P(0.75, 0.66)], fill=255)
        d.ellipse((S * 0.225, S * 0.635, S * 0.31, S * 0.69), fill=255)
        d.ellipse((S * 0.69, S * 0.635, S * 0.775, S * 0.69), fill=255)
        d.ellipse((S * 0.14, S * 0.60, S * 0.62, S * 0.76), fill=255)
        d.ellipse((S * 0.38, S * 0.60, S * 0.86, S * 0.76), fill=255)
        d.ellipse((S * 0.30, S * 0.56, S * 0.70, S * 0.72), fill=255)
        d.rectangle((0, S * 0.76, S, S), fill=0)

    m = mask_draw(figure, 1.2)
    # glowing aura behind figure
    img += (gaussian_filter(m, 40) * 0.9)[..., None] * (GOLD * 0.7 + ORANGE * 0.3)
    img += drop_shadow(m, 16, 22, 18, 0.55)[..., None] * (DEEP - img) * 0.9
    hm = heightmap_from_mask(m, 34, 34)
    # gold metallic body, brighter towards the chest sun
    chest = np.exp(-(((xx - SIZE * 0.5) ** 2 + (yy - SIZE * 0.49) ** 2) / (2 * (SIZE * 0.10) ** 2)))
    body = PURPLE * 0.75 + EMERALD * 0.25
    base = body + (GOLD * 1.1 - body) * np.clip(chest * 1.3, 0, 1)[..., None]
    layer = shade(hm, m, np.clip(base, 0, 1), 0.9, 55, GOLD, 0.9, 0.3)
    img = composite(img, layer, m)
    # sun in the chest
    img = sun_sphere(img, SIZE * 0.5, SIZE * 0.49, SIZE * 0.075)
    img = sparkles(img, 70, 0.4)
    save(img, 'jam-bot-avatar-3d-figure.png')


# ---------- Variant 3: 3D sun with embossed rays ----------
def variant_sun3d():
    img = background()
    cx, cy = SIZE / 2, SIZE * 0.5
    # orbit ring behind sun
    def ring(d, S):
        d.ellipse((S * 0.12, S * 0.12, S * 0.88, S * 0.88), outline=255, width=int(S * 0.035))
    rm = mask_draw(ring, 0.8)
    img = sun_glow(img, cx, cy, SIZE * 0.2)
    img += drop_shadow(rm, 10, 14, 12, 0.45)[..., None] * (DEEP - img) * 0.9
    img = composite(img, shade(heightmap_from_mask(rm, 16, 8), rm, EMERALD * 0.9 + EMERALD_L * 0.3, 0.7, 60, GOLD, 0.35, 0.3), rm)
    img = sun_sphere(img, cx, cy, SIZE * 0.2, ray_len=0.45, with_glow=False)
    img = sparkles(img, 60, 0.5)
    save(img, 'jam-bot-avatar-3d-sun.png')


if __name__ == '__main__':
    variant_lotus3d()
    variant_figure3d()
    variant_sun3d()
