"""P3-C1 5.1 experiment, run with backend/.venv/Scripts/python. No business data."""
import hashlib
import io
import json
import time
from pathlib import Path
import sys

import fitz
import psutil
from PIL import Image
from pypdf import PdfReader, PdfWriter, Transformation
from pypdf.generic import RectangleObject
from reportlab.pdfgen.canvas import Canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / '.cache/c1-probe'
OUT.mkdir(parents=True, exist_ok=True)
pdfmetrics.registerFont(TTFont('Litera', str(ROOT/'backend/app/fonts/NotoSansSC.ttf')))
started = time.monotonic()
source = PdfWriter()
for rotation in (0, 90, 180, 270):
    p = source.add_blank_page(660, 840)
    p.cropbox = RectangleObject([30, 40, 630, 800])
    p.rotate(rotation)
source.write(OUT/'original.pdf')
digest = hashlib.sha256((OUT/'original.pdf').read_bytes()).hexdigest()
writer = PdfWriter(clone_from=OUT/'original.pdf')
types = ['highlight','underline','squiggly','strikeout','comment','freeText','ink','rectangle','circle','ellipse','signature','watermark','image']
im = Image.new('RGBA', (60,30), (0,150,100,110)); im.save(OUT/'alpha.png')
for p in writer.pages:
    buf = io.BytesIO(); c = Canvas(buf, pagesize=(600,760))
    c.setFont('Litera',12)
    for i, kind in enumerate(types):
        x, y = 35+(i//7)*290, 710-(i%7)*95
        c.setFillColorRGB(.6,0,0); c.setStrokeColorRGB(.6,0,0)
        c.drawString(x,y+20,kind+' 中文 αβ ±∞ →')
        c.saveState(); c.setFillAlpha(.35); c.setStrokeAlpha(.65)
        if kind=='highlight': c.rect(x,y-4,210,16,fill=1,stroke=0)
        elif kind in ('underline','strikeout'): c.line(x,y, x+210,y)
        elif kind=='squiggly':
            path=c.beginPath();path.moveTo(x,y)
            for n in range(35):path.curveTo(x+n*6+2,y+3,x+n*6+4,y-3,x+n*6+6,y)
            c.drawPath(path)
        elif kind=='ink':
            path=c.beginPath();path.moveTo(x,y);path.lineTo(x+80,y+10);path.lineTo(x+130,y-10);c.drawPath(path)
        elif kind in ('circle','ellipse'): c.ellipse(x,y-30,x+(50 if kind=='circle' else 150),y+20,fill=1)
        elif kind=='rectangle': c.rect(x,y-20,160,35,fill=1)
        elif kind in ('signature','image'): c.drawImage(str(OUT/'alpha.png'),x,y-30,180,60,mask='auto')
        elif kind=='watermark': c.translate(x+60,y);c.rotate(30);c.drawString(-60,0,'中文水印')
        else: c.drawString(x,y,'正文第一行'); c.drawString(x,y-16,'第二行 English ∞')
        c.restoreState()
    c.save(); p.merge_transformed_page(PdfReader(buf).pages[0], Transformation().translate(30,40))
writer.write(OUT/'overlay.pdf')
native=fitz.open(OUT/'original.pdf')
page=native[0]
note=page.add_text_annot((60,70),'完整中文注释正文\nEnglish');note.update()
free=page.add_freetext_annot(fitz.Rect(60,120,300,200),'中文自由文本 αβ',fontsize=16);free.update()
page.add_highlight_annot(fitz.Rect(60,230,300,250)).update(opacity=.35)
native.save(OUT/'native.pdf')
native.bake();native.save(OUT/'baked.pdf')
for name in ('overlay','native','baked'):
    doc=fitz.open(OUT/(name+'.pdf'))
    for i,p in enumerate(doc):
        if name!='overlay' and i:break
        p.get_pixmap(matrix=fitz.Matrix(1,1)).save(OUT/f'{name}-{i}.png')
    assert all(p.rect.width>0 for p in doc)
assert hashlib.sha256((OUT/'original.pdf').read_bytes()).hexdigest()==digest
overlay=PdfReader(OUT/'overlay.pdf')
assert '中文' in overlay.pages[0].extract_text()
result=dict(types=types, rotations=[p.rotation for p in overlay.pages],
            sourceSha256=digest, sourceUnchanged=True, elapsedSeconds=round(time.monotonic()-started,3),
            peakWorkingSetMiB=round(psutil.Process().memory_info().peak_wset/1048576,1),
            overlayBytes=(OUT/'overlay.pdf').stat().st_size,
            nativeText=fitz.open(OUT/'native.pdf')[0].get_text(),
            bakedText=fitz.open(OUT/'baked.pdf')[0].get_text())
(OUT/'evidence.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(result,ensure_ascii=False,indent=2))
