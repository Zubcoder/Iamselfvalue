#!/usr/bin/env python3
"""Avatar for @Open_your_inner_sun_bot: glowing inner sun on emerald-purple depth."""
import os
import numpy as np
from PIL import Image, ImageDraw, ImageFilter

SIZE = 1024
OUT = os.path.join(os.path.dirname(__file__), 'jam-bot-avatar.png')
rng = np.random.default_rng(7)

yy, xx = np.mgrid[0:SIZE, 0:SIZE].astype(np.float64)
cx, cy = SIZE / 2, SIZE * 0.51
dx, dy = xx - cx, yy - cy
r = np.sqrt(dx ** 2 + dy ** 2) / (SIZE / 2)
ang = np.arctan2(dy, dx)

EMERALD = np.array([0x10, 0x50, 0x40]) / 255
PURPLE = np.array([0x42, 0x31, 0x89]) / 255
DEEP = np.array([0x14, 0x0E, 0x30]) / 255
GOLD = np.array([0xD4, 0xAF, 0x37]) / 255
ORANGE = np.array([0xF2, 0x8C, 0x28]) / 255
WHITE = np.array([1.0, 0.97, 0.88])

# background: purple top-left -> emerald bottom-right, darkening to the edge
t = np.clip((dx + dy) / SIZE + 0.5, 0, 1)[..., None]
bg = PURPLE * (1 - t) + EMERALD * t
bg = bg * (1 - 0.55 * np.clip(r, 0, 1)[..., None] ** 1.5) + DEEP * 0.55 * np.clip(r, 0, 1)[..., None] ** 1.5

# soft rays
rays = np.zeros_like(r)
for k, (n, w, a0) in enumerate([(12, 0.12, 0.0), (24, 0.05, 0.13)]):
    rays += w * (0.5 + 0.5 * np.cos(n * ang + a0)) ** 6
rays *= np.exp(-((r - 0.15) / 0.55) ** 2) * (r > 0.14)

# sun core + halo
core = np.exp(-(r / 0.11) ** 2)
halo = np.exp(-(r / 0.30) ** 2) * 0.75
outer = np.exp(-(r / 0.7) ** 2) * 0.25

img = bg.copy()
img += outer[..., None] * ORANGE * 0.6
img += rays[..., None] * GOLD * 0.9
img += halo[..., None] * (ORANGE * 0.6 + GOLD * 0.5)
img += core[..., None] * WHITE * 1.4

# sparkles
for _ in range(90):
    a = rng.uniform(0, 2 * np.pi)
    rr = rng.uniform(0.32, 0.92)
    px, py = cx + rr * np.cos(a) * SIZE / 2, cy + rr * np.sin(a) * SIZE / 2
    s = rng.uniform(1.5, 4.5)
    b = rng.uniform(0.3, 1.0)
    img += (b * np.exp(-(((xx - px) ** 2 + (yy - py) ** 2) / (2 * s ** 2))))[..., None] * GOLD

img = np.clip(img, 0, 1)
out = Image.fromarray((img * 255).astype(np.uint8))

# meditating silhouette (lotus pose), sun glows in the chest
sil = Image.new('L', (SIZE, SIZE), 0)
d = ImageDraw.Draw(sil)
S = SIZE
def P(x, y):
    return (S * x, S * y)
# head + neck
d.ellipse((S * 0.437, S * 0.19, S * 0.563, S * 0.33), fill=255)
d.rounded_rectangle((S * 0.475, S * 0.31, S * 0.525, S * 0.37), 14, fill=255)
# shoulders + torso (tapering to waist)
d.polygon([P(0.36, 0.40), P(0.64, 0.40), P(0.62, 0.66), P(0.38, 0.66)], fill=255)
d.ellipse((S * 0.34, S * 0.355, S * 0.66, S * 0.46), fill=255)
# arms resting on knees
d.polygon([P(0.36, 0.41), P(0.415, 0.40), P(0.31, 0.68), P(0.25, 0.68)], fill=255)
d.polygon([P(0.64, 0.41), P(0.585, 0.40), P(0.69, 0.68), P(0.75, 0.68)], fill=255)
d.ellipse((S * 0.225, S * 0.655, S * 0.31, S * 0.71), fill=255)
d.ellipse((S * 0.69, S * 0.655, S * 0.775, S * 0.71), fill=255)
# crossed legs
d.ellipse((S * 0.14, S * 0.62, S * 0.62, S * 0.78), fill=255)
d.ellipse((S * 0.38, S * 0.62, S * 0.86, S * 0.78), fill=255)
d.ellipse((S * 0.30, S * 0.58, S * 0.70, S * 0.74), fill=255)
d.rectangle((0, S * 0.78, S, S), fill=0)
sil = sil.filter(ImageFilter.GaussianBlur(3))
mask = np.asarray(sil).astype(np.float64) / 255

chest = np.exp(-(((xx - SIZE * 0.5) ** 2 + (yy - SIZE * 0.51) ** 2) / (2 * (SIZE * 0.085) ** 2)))
body_col = DEEP * 0.9
fig = body_col[None, None, :] + chest[..., None] * (ORANGE * 0.9 + GOLD * 0.6) \
    + (np.exp(-(((xx - SIZE * 0.5) ** 2 + (yy - SIZE * 0.51) ** 2) / (2 * (SIZE * 0.045) ** 2))))[..., None] * WHITE * 1.2
fig = np.clip(fig, 0, 1)
rim = np.clip(mask - np.asarray(sil.filter(ImageFilter.GaussianBlur(10))).astype(np.float64) / 255, 0, 1)
img = img * (1 - mask[..., None]) + fig * mask[..., None] + rim[..., None] * GOLD * 0.9
img = np.clip(img, 0, 1)
out = Image.fromarray((img * 255).astype(np.uint8))
out = out.filter(ImageFilter.GaussianBlur(0.6))
out.save(OUT, optimize=True)
out.resize((512, 512), Image.LANCZOS).save(OUT.replace('.png', '-512.png'), optimize=True)
print(OUT)
