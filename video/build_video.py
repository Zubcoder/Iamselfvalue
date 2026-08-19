import subprocess, shlex, os, math

D = 5.8
FPS = 30
ZOOM_STEP = 0.000862
ZOOM_MAX = 1.15
W, H = 1280, 720
OUT_W, OUT_H = 2560, 1440
COMMON = (
    f"zoompan=z='min(1+{ZOOM_STEP}*on,{ZOOM_MAX})':d=1:"
    f"x='(iw-(iw/zoom))/2':y='(ih-(ih/zoom))/2':"
    f"s={OUT_W}x{OUT_H}:fps={FPS},"
    f"scale={W}:{H}:flags=lanczos"
)

def seg_filter(text, subtitle, font_size=52):
    return (
        f"{COMMON},"
        f"drawtext=fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf:"
        f"text='{text}':fontcolor=white:fontsize={font_size}:"
        f"box=1:boxcolor=black@0.35:boxborderw=14:"
        f"x=(w-text_w)/2:y=(h-text_h)/2-35,"
        f"drawtext=fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf:"
        f"text='{subtitle}':fontcolor=#D4AF37:fontsize=24:"
        f"box=1:boxcolor=black@0.35:boxborderw=10:"
        f"x=(w-text_w)/2:y=(h-text_h)/2+35"
    )

slides = [
    ('slide1.png', 'Я Есть Ценность', 'Пространство бережной психологии', 52),
    ('slide2.png', 'Коучинг и психология', 'Индивидуальные сессии для женщин', 52),
    ('slide3.png', 'Системные расстановки', 'Работа с родовыми сценариями', 52),
    ('slide4.png', 'Добаюкивание', 'Возвращение утраченного детского ресурса', 52),
    ('slide5.png', 'Телесно-ориентированная терапия', 'Дыхательные практики и телесные техники', 48),
    ('slide6.png', None, None, 52),  # slide already has baked brand text
]

for i, (img, text, sub, fs) in enumerate(slides, 1):
    vf = seg_filter(text, sub, fs) if text else COMMON
    cmd = [
        'ffmpeg', '-y', '-framerate', '30', '-loop', '1', '-t', str(D),
        '-i', img,
        '-vf', vf,
        '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-r', '30',
        f'seg{i}.mp4'
    ]
    print('Building', f'seg{i}.mp4')
    subprocess.run(cmd, check=True)

# crossfade chain
fade_d = 1.0
offsets = [4.8, 9.6, 14.4, 19.2, 24.0]
inputs = ' '.join(f'-i seg{i}.mp4' for i in range(1, 7))
chain = []
prev = '0'
for i, off in enumerate(offsets, 1):
    out = f'xa{i}' if i < len(offsets) else 'out'
    chain.append(f'[{prev}][{i}]xfade=transition=fade:duration={fade_d}:offset={off}[{out}]')
    prev = out
filter_complex = '; '.join(chain)
cmd = f"ffmpeg -y {inputs} -filter_complex '{filter_complex}' -map '[out]' -c:v libx264 -pix_fmt yuv420p -r 30 promo.mp4"
print('Concatenating...')
print(cmd)
subprocess.run(shlex.split(cmd), check=True)

for f in os.listdir('.'):
    if f.startswith('seg') and f.endswith('.mp4'):
        os.remove(f)

print('Done:', 'promo.mp4')
