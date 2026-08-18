#!/usr/bin/env python3
"""Generate business-card front/back/preview for 'Я Есть Ценность'."""
import os
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import qrcode

CARD_W, CARD_H = 1050, 600
BG = os.path.join(os.path.dirname(__file__), '..', 'video', 'slide1.png')
FONT_SERIF_BOLD = '/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf'
FONT_SANS = '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'
FONT_SANS_BOLD = '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'

EMERALD = '#105040'
PURPLE = '#423189'
GOLD = '#D4AF37'
WHITE = '#FFFFFF'


def load_font(path, size):
    return ImageFont.truetype(path, size)


def gradient(size, c1, c2, direction='diagonal'):
    """Return RGBA linear gradient."""
    base = Image.new('RGBA', size, c1)
    draw = ImageDraw.Draw(base)
    w, h = size
    for i in range(max(w, h)):
        if direction == 'diagonal':
            # top-left to bottom-right
            pass
    # Simpler: draw rectangle per band
    for x in range(w):
        for y in range(h):
            # normalized distance along diagonal
            r = (x + y) / (w + h)
            r = max(0.0, min(1.0, r))
            col = tuple(int(c1[k] + (c2[k] - c1[k]) * r) for k in range(3))
            draw.point((x, y), fill=col + (255,))
    return base


def hex_to_rgb(value):
    value = value.lstrip('#')
    return tuple(int(value[i:i+2], 16) for i in (0, 2, 4))


def draw_text_shadow(draw, text, pos, font, fill, shadow=(0, 0, 0, 120), offset=2):
    x, y = pos
    draw.text((x + offset, y + offset), text, font=font, fill=shadow)
    draw.text((x, y), text, font=font, fill=fill)


def make_front():
    img = Image.open(BG).convert('RGBA').resize((CARD_W, CARD_H), Image.LANCZOS)
    # bottom gradient for text readability
    overlay = Image.new('RGBA', (CARD_W, CARD_H), (0, 0, 0, 0))
    odraw = ImageDraw.Draw(overlay)
    for y in range(CARD_H):
        alpha = int(180 * (y / CARD_H) ** 2)  # stronger at bottom
        odraw.line([(0, y), (CARD_W, y)], fill=(0, 0, 0, alpha))
    img = Image.alpha_composite(img, overlay)

    draw = ImageDraw.Draw(img)
    brand_font = load_font(FONT_SERIF_BOLD, 70)
    roles_font = load_font(FONT_SANS, 24)

    brand = 'Я Есть Ценность'
    bbox = draw.textbbox((0, 0), brand, font=brand_font)
    bw = bbox[2] - bbox[0]
    bh = bbox[3] - bbox[1]
    bx = (CARD_W - bw) // 2
    by = CARD_H - bh - 145
    draw_text_shadow(draw, brand, (bx, by), brand_font, GOLD)

    roles = [
        'коуч-психолог  ·  расстановщик',
        'мастер добаюкивания  ·  телесный терапевт',
    ]
    ry = by + bh + 18
    for line in roles:
        rbox = draw.textbbox((0, 0), line, font=roles_font)
        rw = rbox[2] - rbox[0]
        draw.text(((CARD_W - rw) // 2, ry), line, font=roles_font, fill=WHITE)
        ry += 34
    return img


def make_back(phone, qr_url):
    c1 = hex_to_rgb(EMERALD) + (255,)
    c2 = hex_to_rgb(PURPLE) + (255,)
    img = gradient((CARD_W, CARD_H), c1, c2)

    # subtle lotus watermark
    lotus = Image.open(BG).convert('RGBA').resize((CARD_W, CARD_H), Image.LANCZOS)
    lotus = lotus.point(lambda p: int(p * 0.12))
    lotus = lotus.filter(ImageFilter.GaussianBlur(radius=4))
    img = Image.alpha_composite(img, lotus)

    draw = ImageDraw.Draw(img)

    # brand title
    brand_font = load_font(FONT_SERIF_BOLD, 42)
    draw_text_shadow(draw, 'Я Есть Ценность', (60, 50), brand_font, GOLD)

    # name
    name_font = load_font(FONT_SERIF_BOLD, 54)
    draw_text_shadow(draw, 'Екатерина Скулоченко', (60, 115), name_font, WHITE)

    # roles
    roles_font = load_font(FONT_SANS, 24)
    roles = 'коуч-психолог · расстановщик · мастер добаюкивания · телесный терапевт'
    draw.text((60, 185), roles, font=roles_font, fill='#E0E0E0')

    # gold line
    draw.line([(60, 235), (500, 235)], fill=GOLD, width=3)

    # contacts
    contact_font = load_font(FONT_SANS, 28)
    line_h = 48
    y = 270
    draw.text((60, y), 'iamselfvalue.ru', font=contact_font, fill=WHITE)
    y += line_h
    draw.text((60, y), 't.me/iamselfvalue', font=contact_font, fill=WHITE)
    y += line_h
    draw.text((60, y), f'Телефон: {phone}', font=contact_font, fill=WHITE)

    # QR code
    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_H,
        box_size=8,
        border=2,
    )
    qr.add_data(qr_url)
    qr.make(fit=True)
    qr_img = qr.make_image(fill_color='black', back_color='white').convert('RGBA')
    qr_size = 180
    qr_img = qr_img.resize((qr_size, qr_size), Image.LANCZOS)
    # paste with white padding (quiet zone already handled by border)
    x = CARD_W - qr_size - 60
    y = (CARD_H - qr_size) // 2 + 20
    img.paste(qr_img, (x, y), qr_img)

    return img


def make_preview(front, back):
    preview = Image.new('RGBA', (CARD_W * 2, CARD_H), (255, 255, 255, 255))
    preview.paste(front, (0, 0))
    preview.paste(back, (CARD_W, 0))
    return preview


def main():
    phone = '+7 (999) 839-72-27'
    qr_url = 'https://iamselfvalue.ru'
    front = make_front()
    back = make_back(phone, qr_url)
    preview = make_preview(front, back)

    base = os.path.dirname(__file__)
    front.save(os.path.join(base, 'business-card-front.png'))
    back.save(os.path.join(base, 'business-card-back.png'))
    preview.save(os.path.join(base, 'business-card-preview.png'))
    print('Saved business cards. QR target:', qr_url, 'Phone:', phone)


if __name__ == '__main__':
    main()
