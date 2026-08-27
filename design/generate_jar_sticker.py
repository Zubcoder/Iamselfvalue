#!/usr/bin/env python3
"""Generate round jar-lid sticker for 'I am self value' orange jam + QR bot link."""
import os
from PIL import Image, ImageDraw, ImageFont
import qrcode

# 45 mm diameter sticker at 300 dpi, plus 3 mm bleed
# The lid diameter of the photographed 100 ml hexagonal jar is ~48 mm,
# so the sticker is 45 mm (a little smaller than the lid) with 3 mm bleed.
MM_TO_PX = 300 / 25.4
DIAMETER_MM = 45
BLEED_MM = 3
SAFE_MM = 5
D = int(DIAMETER_MM * MM_TO_PX)          # 531 px cut size
B = int(BLEED_MM * MM_TO_PX)             # 35 px bleed
S = int(SAFE_MM * MM_TO_PX)              # 59 px safe margin
TOTAL = D + 2 * B                        # 601 px print file
CENTER = TOTAL // 2
R = D // 2                               # 265 px cut radius
R_SAFE = R - S                           # 206 px safe radius

EMERALD = '#105040'
PURPLE = '#423189'
GOLD = '#D4AF37'
WHITE = '#FFFFFF'
ORANGE = '#E07A2E'

FONT_DIR = '/usr/share/fonts/truetype/dejavu'
FONT_SERIF = os.path.join(FONT_DIR, 'DejaVuSerif-Bold.ttf')
FONT_SANS = os.path.join(FONT_DIR, 'DejaVuSans.ttf')
FONT_SANS_BOLD = os.path.join(FONT_DIR, 'DejaVuSans-Bold.ttf')

LOGO_PATH = os.path.join(os.path.dirname(__file__), '..', 'logo-icon.png')


def hex_to_rgb(value):
    value = value.lstrip('#')
    return tuple(int(value[i:i + 2], 16) for i in (0, 2, 4))


def load_font(path, size):
    return ImageFont.truetype(path, size)


def radial_gradient(size, center_color, edge_color):
    w, h = size
    cx, cy = w / 2, h / 2
    max_dist = (cx ** 2 + cy ** 2) ** 0.5
    base = Image.new('RGBA', size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(base)
    c1 = hex_to_rgb(center_color)
    c2 = hex_to_rgb(edge_color)
    for y in range(h):
        for x in range(w):
            dist = ((x - cx) ** 2 + (y - cy) ** 2) ** 0.5
            t = min(1.0, dist / max_dist)
            col = tuple(int(c1[k] + (c2[k] - c1[k]) * t) for k in range(3))
            draw.point((x, y), fill=col + (255,))
    return base


def make_qr(url, size):
    # Determine QR version first, then choose an integer box size that
    # lands close to the target size to keep the modules sharp.
    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_H,
        box_size=1,
        border=2,
    )
    qr.add_data(url)
    qr.make(fit=True)
    total_cells = qr.modules_count + 2 * qr.border
    box_size = max(2, size // total_cells)
    qr.box_size = box_size
    qr_img = qr.make_image(fill_color='black', back_color='white').convert('RGBA')
    qr_img = qr_img.resize((size, size), Image.LANCZOS)
    return qr_img


def draw_text_center(draw, text, y, font, fill, shadow=True):
    bbox = draw.textbbox((0, 0), text, font=font)
    w = bbox[2] - bbox[0]
    x = (TOTAL - w) // 2
    if shadow:
        draw.text((x + 2, y + 2), text, font=font, fill=(0, 0, 0, 120))
    draw.text((x, y), text, font=font, fill=fill)


def make_sticker(bot_username='iamselfvalue_bot', campaign='orange_jam'):
    url = f'https://t.me/{bot_username}?start={campaign}'

    # Print file with bleed, transparent outside cut circle
    img = Image.new('RGBA', (TOTAL, TOTAL), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Background circle with radial gradient
    bg = radial_gradient((TOTAL, TOTAL), PURPLE, EMERALD)
    mask = Image.new('L', (TOTAL, TOTAL), 0)
    mdraw = ImageDraw.Draw(mask)
    mdraw.ellipse((B, B, B + D - 1, B + D - 1), fill=255)
    img.paste(bg, (0, 0), mask)

    # Decorative gold ring near cut edge
    draw.ellipse((B, B, B + D - 1, B + D - 1), outline=GOLD, width=3)
    draw.ellipse((B + 18, B + 18, B + D - 19, B + D - 19), outline=GOLD, width=1)

    # Add subtle lotus logo at top
    if os.path.exists(LOGO_PATH):
        logo = Image.open(LOGO_PATH).convert('RGBA')
        logo_size = 45
        logo = logo.resize((logo_size, logo_size), Image.LANCZOS)
        # Slightly fade to blend with background
        alpha = logo.split()[-1].point(lambda a: int(a * 0.85))
        logo.putalpha(alpha)
        lx = (TOTAL - logo_size) // 2
        ly = 85
        img.paste(logo, (lx, ly), logo)

    # Fonts (scaled for the 45 mm sticker)
    brand_font = load_font(FONT_SERIF, 26)
    flavor_font = load_font(FONT_SANS_BOLD, 22)
    tagline_font = load_font(FONT_SANS, 18)
    sub_font = load_font(FONT_SANS, 16)
    hint_font = load_font(FONT_SANS, 14)

    # Texts
    brand_y = 145
    draw_text_center(draw, 'Я Есть Ценность', brand_y, brand_font, GOLD)

    flavor_y = 172
    draw_text_center(draw, 'Апельсиновый джем', flavor_y, flavor_font, WHITE)

    tagline_y = 195
    draw_text_center(draw, 'Твое наслаждение', tagline_y, tagline_font, GOLD)

    # QR code in center
    qr_size = 180
    qr = make_qr(url, qr_size)
    qx = (TOTAL - qr_size) // 2
    qy = CENTER - (qr_size // 2) + 10
    # white rounded backing
    backing = Image.new('RGBA', (qr_size + 20, qr_size + 20), WHITE)
    draw_back = ImageDraw.Draw(backing)
    draw_back.rounded_rectangle((0, 0, qr_size + 19, qr_size + 19), radius=16, fill=WHITE, outline=GOLD, width=2)
    img.paste(backing, (qx - 10, qy - 10), backing)
    img.paste(qr, (qx, qy), qr)

    # Call-to-action below QR
    hint_y = qy + qr_size + 15
    draw_text_center(draw, 'Сканируй → медитация', hint_y, hint_font, WHITE, shadow=False)

    sub_y = hint_y + 25
    draw_text_center(draw, 'Раскрой своё внутреннее солнце', sub_y, sub_font, GOLD, shadow=False)

    # Save print file (with bleed, transparent outside cut circle)
    base = os.path.dirname(__file__)
    img.save(os.path.join(base, 'jar-sticker-orange-print.png'))

    # Save preview/cut file with cut circle visible for review
    preview = img.crop((B, B, B + D, B + D))
    draw_prev = ImageDraw.Draw(preview)
    draw_prev.ellipse((0, 0, D - 1, D - 1), outline=GOLD, width=2)
    preview.save(os.path.join(base, 'jar-sticker-orange.png'))

    print('Saved jar sticker for', url)
    return url


if __name__ == '__main__':
    url = make_sticker()
    print('QR target:', url)
