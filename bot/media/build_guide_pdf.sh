#!/usr/bin/env bash
# Renders lead_goodgirl.html -> lead_goodgirl.pdf with headless Chrome and
# writes a contact-sheet preview to /tmp/guide-preview.png.
set -euo pipefail
cd "$(dirname "$0")"
google-chrome --headless=new --disable-gpu --no-sandbox --no-pdf-header-footer \
  --print-to-pdf=lead_goodgirl.pdf --virtual-time-budget=8000 \
  "file://$PWD/lead_goodgirl.html" 2>/dev/null
python3 - <<'PY'
import pymupdf
from PIL import Image
doc = pymupdf.open('lead_goodgirl.pdf')
print('pages:', len(doc))
ims = []
for p in doc:
    pix = p.get_pixmap(dpi=45)
    ims.append(Image.frombytes('RGB', (pix.width, pix.height), pix.samples))
w, h = ims[0].size
cols = 3
rows = (len(ims) + cols - 1) // cols
out = Image.new('RGB', (w * cols, h * rows), 'white')
for i, im in enumerate(ims):
    out.paste(im, ((i % cols) * w, (i // cols) * h))
out.save('/tmp/guide-preview.png')
PY
