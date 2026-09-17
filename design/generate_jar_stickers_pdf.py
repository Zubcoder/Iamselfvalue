#!/usr/bin/env python3
"""Build the print-house PDF package for the orange-jam jar stickers.

Output:
  design/jar-stickers-print-spec.pdf   — техническое задание для типографии (спецификация + макеты)
  design/jar-lid-sticker-print.pdf     — печатный файл крышки, 1:1 с вылетами (Ø51 мм)
  design/jar-body-label-print.pdf      — печатный файл боковой этикетки, 1:1 с вылетами (64×39 мм)
"""
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas
from reportlab.platypus import (Image, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table,
                                TableStyle, KeepTogether)

HERE = Path(__file__).parent
FONT_DIR = Path('/usr/share/fonts/truetype/dejavu')
pdfmetrics.registerFont(TTFont('DV', str(FONT_DIR / 'DejaVuSans.ttf')))
pdfmetrics.registerFont(TTFont('DV-B', str(FONT_DIR / 'DejaVuSans-Bold.ttf')))
pdfmetrics.registerFont(TTFont('DV-I', str(FONT_DIR / 'DejaVuSans.ttf')))

PURPLE, EMERALD, GOLD = '#423189', '#105040', '#D4AF37'
BOT_URL = 'https://t.me/Open_your_inner_sun_bot?start=orange_jam'

LID_PNG = HERE / 'jar-sticker-orange-print.png'      # 601×601 px = Ø51 мм @300dpi
BODY_PNG = HERE / 'jar-body-label-print.png'          # 754×459 px = 64×39 мм @300dpi
LID_CUT, LID_BLEED = 45, 3
BODY_W, BODY_H, BODY_BLEED = 60, 35, 2

styles = {
    'h1': ParagraphStyle('h1', fontName='DV-B', fontSize=18, leading=22, textColor=colors.HexColor(PURPLE),
                         spaceAfter=4 * mm),
    'h2': ParagraphStyle('h2', fontName='DV-B', fontSize=13, leading=16, textColor=colors.HexColor(EMERALD),
                         spaceBefore=5 * mm, spaceAfter=2.5 * mm),
    'body': ParagraphStyle('body', fontName='DV', fontSize=9.5, leading=13.5),
    'small': ParagraphStyle('small', fontName='DV', fontSize=8, leading=11, textColor=colors.HexColor('#555555')),
    'cap': ParagraphStyle('cap', fontName='DV-I', fontSize=8, leading=11, alignment=TA_CENTER,
                          textColor=colors.HexColor('#555555')),
    'cell': ParagraphStyle('cell', fontName='DV', fontSize=8.8, leading=12),
    'cellb': ParagraphStyle('cellb', fontName='DV-B', fontSize=8.8, leading=12),
}


def P(text, style='body'):
    return Paragraph(text, styles[style])


def spec_table(rows, col_widths):
    data = [[P(c, 'cellb') if i == 0 else P(c, 'cell') for i, c in enumerate(r)] for r in rows]
    t = Table(data, colWidths=col_widths, hAlign='LEFT')
    t.setStyle(TableStyle([
        ('GRID', (0, 0), (-1, -1), 0.4, colors.HexColor('#BBBBBB')),
        ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#F3F0FA')),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING', (0, 0), (-1, -1), 4), ('RIGHTPADDING', (0, 0), (-1, -1), 4),
        ('TOPPADDING', (0, 0), (-1, -1), 3), ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
    ]))
    return t


def color_table():
    rows = [['Элемент', 'HEX', 'RGB', 'CMYK (ориентир)', 'Образец'],
            ['Фон — центр (фиолетовый)', PURPLE, '66 · 49 · 137', '85 · 90 · 0 · 15', ''],
            ['Фон — край (изумрудный)', EMERALD, '16 · 80 · 64', '85 · 35 · 70 · 45', ''],
            ['Золото: заголовки, рамки, лучи', GOLD, '212 · 175 · 55', '15 · 25 · 90 · 5', ''],
            ['Белый: текст, подложка QR', '#FFFFFF', '255 · 255 · 255', '0 · 0 · 0 · 0', ''],
            ['QR-код', '#000000', '0 · 0 · 0', '0 · 0 · 0 · 100', '']]
    data = [[P(c, 'cellb' if r == 0 else 'cell') for c in row] for r, row in enumerate(rows)]
    t = Table(data, colWidths=[48 * mm, 20 * mm, 28 * mm, 32 * mm, 24 * mm], hAlign='LEFT')
    st = [('GRID', (0, 0), (-1, -1), 0.4, colors.HexColor('#BBBBBB')),
          ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#F3F0FA')),
          ('VALIGN', (0, 0), (-1, -1), 'MIDDLE')]
    for i, row in enumerate(rows[1:], start=1):
        st.append(('BACKGROUND', (4, i), (4, i), colors.HexColor(row[1])))
    t.setStyle(TableStyle(st))
    return t


def header_footer(c: canvas.Canvas, doc):
    c.saveState()
    c.setFont('DV', 7.5)
    c.setFillColor(colors.HexColor('#777777'))
    c.drawString(20 * mm, 287 * mm, 'Я Есть Ценность · Апельсиновый джем «Твоё наслаждение» · ТЗ на печать наклеек')
    c.drawRightString(190 * mm, 12 * mm, f'стр. {doc.page}')
    c.restoreState()


def build_spec(out: Path):
    doc = SimpleDocTemplate(str(out), pagesize=A4, leftMargin=20 * mm, rightMargin=20 * mm,
                            topMargin=18 * mm, bottomMargin=18 * mm,
                            title='ТЗ на печать наклеек — апельсиновый джем «Твоё наслаждение»',
                            author='Я Есть Ценность')
    s = []
    s.append(P('Техническое задание на печать наклеек<br/>для банки апельсинового джема «Твоё наслаждение»', 'h1'))
    s.append(P('Комплект: 2 наклейки на одну банку — круглая на крышку и прямоугольная на корпус. '
               'Обе содержат QR-код, ведущий в Telegram-бот с медитацией. Ниже — параметры для печати, '
               'цветовая карта, требования к материалам и к QR-коду, а также сами макеты в масштабе 1:1.'))

    s.append(P('1. Изделие и тираж', 'h2'))
    s.append(spec_table([
        ['Упаковка', 'Стеклянная шестигранная банка 100 мл, высота ≈ 65 мм, ширина по углам ≈ 70 мм, '
                     'крышка twist-off Ø ≈ 48 мм'],
        ['Комплект', '1 крышечная + 1 корпусная наклейка на банку'],
        ['Тираж', 'по количеству банок (указать при заказе) + 10 % запас на брак/переклейку'],
        ['Файлы', 'jar-lid-sticker-print.pdf (крышка, 1:1), jar-body-label-print.pdf (корпус, 1:1); '
                  'дублирующие PNG 300 dpi: jar-sticker-orange-print.png, jar-body-label-print.png'],
    ], [38 * mm, 132 * mm]))

    s.append(P('2. Наклейка на крышку', 'h2'))
    s.append(spec_table([
        ['Форма', 'круг'],
        ['Размер по обрезу (cut)', f'Ø {LID_CUT} мм'],
        ['Вылеты (bleed)', f'{LID_BLEED} мм по контуру → размер файла Ø {LID_CUT + 2 * LID_BLEED} мм'],
        ['Безопасная зона', 'значимые элементы не ближе 3 мм к линии реза (в макете соблюдено)'],
        ['Разрешение', '300 dpi (601 × 601 px), фон за пределами круга прозрачный'],
        ['Материал', 'самоклеящаяся плёнка (полипропилен/винил) белая, влагостойкая; '
                     'ламинация матовая или soft-touch'],
        ['Вырубка', 'плоттерная / штамп, круг Ø 45 мм по контуру, без белой рамки'],
    ], [38 * mm, 132 * mm]))

    s.append(P('3. Наклейка на корпус банки', 'h2'))
    s.append(spec_table([
        ['Форма', 'прямоугольник, углы скруглены радиусом 2 мм'],
        ['Размер по обрезу (cut)', f'{BODY_W} × {BODY_H} мм (ширина × высота)'],
        ['Вылеты (bleed)', f'{BODY_BLEED} мм со всех сторон → размер файла {BODY_W + 2 * BODY_BLEED} × '
                            f'{BODY_H + 2 * BODY_BLEED} мм'],
        ['Безопасная зона', 'не ближе 3 мм к линии реза (в макете соблюдено)'],
        ['Разрешение', '300 dpi (754 × 459 px)'],
        ['Нанесение', 'клеится на две соседние грани шестигранника, сгиб по ребру приходится на середину '
                      '(между QR-кодом и текстом) — критичных элементов на линии сгиба нет'],
        ['Материал', 'самоклеящаяся плёнка белая, влагостойкая, клей permanent (холодильник, конденсат); '
                     'ламинация матовая'],
        ['Альтернатива', 'если печать только на одну грань — пропорционально уменьшить до 30 × 35 мм; '
                         'QR при этом ≥ 15 мм и остаётся читаемым'],
    ], [38 * mm, 132 * mm]))

    s.append(PageBreak())
    s.append(P('4. Цветовая карта', 'h2'))
    s.append(color_table())
    s.append(Spacer(1, 2 * mm))
    s.append(P('Фон обеих наклеек — радиальный градиент от фиолетового (центр) к изумрудному (край). '
               'Печать CMYK. Обязательна цветопроба по золоту: оно не должно уходить в лимонно-жёлтый или '
               'зелёный оттенок; допустима замена на пантон Metallic 871 C при офсетной/шёлкографической печати. '
               'Чёрный QR — только Key (100 K), без составного чёрного, чтобы не было смещения растров.'))

    s.append(P('5. Требования к QR-коду', 'h2'))
    s.append(P(f'Адрес: <font name="DV-B">{BOT_URL}</font>'))
    s.append(spec_table([
        ['Размер', 'крышка ≈ 18 мм, корпус ≈ 21 мм; не масштабировать QR отдельно от макета, минимум 15 мм'],
        ['Контраст', 'чёрные модули на белой подложке — не менять цвета и не накладывать эффекты'],
        ['Поверхность', 'без глянца и металлика без ламината — блики мешают считыванию; матовый ламинат допустим'],
        ['Контроль', 'обязательно считать QR телефоном с тестового отпечатка (пробы) до запуска тиража'],
    ], [38 * mm, 132 * mm]))

    s.append(P('6. Что нужно от типографии', 'h2'))
    s.append(P('1. Подтвердить материал, ламинацию и способ вырубки.<br/>'
               '2. Прислать цветопробу (или фото пробного отпечатка при дневном свете) — сравниваем золото и фиолетовый.<br/>'
               '3. Проверить считывание обоих QR-кодов с пробного отпечатка.<br/>'
               '4. После согласования — печать тиража, поштучная резка (не на листе), упаковка стопками по 50 шт.'))
    s.append(P('Контакт по вопросам макета: Telegram-бот @Open_your_inner_sun_bot → команда /support.', 'small'))

    s.append(PageBreak())
    s.append(P('7. Макеты в масштабе 1:1 (для визуальной проверки)', 'h2'))
    s.append(P('Пунктирная линия — линия реза, сплошная внешняя — граница вылетов. '
               'На печать идут отдельные файлы jar-lid-sticker-print.pdf и jar-body-label-print.pdf.', 'small'))
    s.append(Spacer(1, 4 * mm))

    lid_full = (LID_CUT + 2 * LID_BLEED) * mm
    body_full_w, body_full_h = (BODY_W + 2 * BODY_BLEED) * mm, (BODY_H + 2 * BODY_BLEED) * mm
    lid_img = Image(str(LID_PNG), lid_full, lid_full)
    body_img = Image(str(BODY_PNG), body_full_w, body_full_h)
    grid = Table([[lid_img, body_img],
                  [P(f'Крышка: cut Ø{LID_CUT} мм, файл Ø{LID_CUT + 2 * LID_BLEED} мм', 'cap'),
                   P(f'Корпус: cut {BODY_W}×{BODY_H} мм, файл {BODY_W + 2 * BODY_BLEED}×{BODY_H + 2 * BODY_BLEED} мм',
                     'cap')]],
                 colWidths=[80 * mm, 90 * mm])
    grid.setStyle(TableStyle([('ALIGN', (0, 0), (-1, -1), 'CENTER'), ('VALIGN', (0, 0), (-1, -1), 'MIDDLE')]))
    s.append(KeepTogether(grid))
    s.append(Spacer(1, 6 * mm))

    s.append(P('8. Макеты, увеличение ×2.5 (проверка деталей)', 'h2'))
    k = 2.5
    big = Table([[Image(str(LID_PNG), lid_full * k, lid_full * k)],
                 [Image(str(BODY_PNG), body_full_w * k, body_full_h * k)]], colWidths=[170 * mm])
    big.setStyle(TableStyle([('ALIGN', (0, 0), (-1, -1), 'CENTER')]))
    s.append(big)

    doc.build(s, onFirstPage=header_footer, onLaterPages=header_footer)


def build_print_file(out: Path, png: Path, w_mm: float, h_mm: float, cut_w: float, cut_h: float, round_: bool):
    c = canvas.Canvas(str(out), pagesize=(w_mm * mm, h_mm * mm))
    c.setTitle(out.stem)
    c.drawImage(str(png), 0, 0, w_mm * mm, h_mm * mm, mask='auto')
    # cut line as a separate non-printing-style guide (thin, magenta) — типография удалит/использует как контур
    c.setStrokeColor(colors.HexColor('#FF00FF'))
    c.setLineWidth(0.15)
    c.setDash(1.5, 1.5)
    bx, by = (w_mm - cut_w) / 2 * mm, (h_mm - cut_h) / 2 * mm
    if round_:
        c.circle(w_mm * mm / 2, h_mm * mm / 2, cut_w * mm / 2)
    else:
        c.roundRect(bx, by, cut_w * mm, cut_h * mm, 2 * mm)
    c.showPage()
    c.save()


if __name__ == '__main__':
    build_spec(HERE / 'jar-stickers-print-spec.pdf')
    build_print_file(HERE / 'jar-lid-sticker-print.pdf', LID_PNG, LID_CUT + 2 * LID_BLEED, LID_CUT + 2 * LID_BLEED,
                     LID_CUT, LID_CUT, True)
    build_print_file(HERE / 'jar-body-label-print.pdf', BODY_PNG, BODY_W + 2 * BODY_BLEED, BODY_H + 2 * BODY_BLEED,
                     BODY_W, BODY_H, False)
    print('ok')
