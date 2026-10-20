"""Deterministic public fixture covering all 13 persisted object types."""
from io import BytesIO
from pathlib import Path
from PIL import Image, ImageDraw
from pypdf import PdfWriter, PdfReader
from pypdf.generic import RectangleObject, NameObject, NumberObject
from reportlab.pdfgen.canvas import Canvas

KINDS=['highlight','underline','squiggly','strikeout','comment','freeText','ink','rectangle','circle','ellipse','signature','watermark','image']


def samples(root):
    root=Path(root);root.mkdir(parents=True,exist_ok=True)
    image=Image.new('RGBA',(160,80),(0,0,0,0));d=ImageDraw.Draw(image)
    d.ellipse((20,10,140,70),fill=(20,145,85,140));d.line([(15,65),(50,20),(90,60),(140,10)],fill=(80,20,120,255),width=4)
    image.save(root/'alpha.png')
    jpg=Image.new('RGB',(160,80),'#517CA8');jpg.save(root/'photo.jpg')
    writer=PdfWriter();items=[]
    for i,rotation in enumerate((0,90,180,270)):
        w,h=(600,760) if i%2==0 else (700,800)
        buf=BytesIO();c=Canvas(buf,pagesize=(w+60,h+80))
        c.setFont('Helvetica',14);c.drawString(45,h+50,f'Litera C1 original page {i+1} Rotate {rotation}')
        for j,kind in enumerate(KINDS):
            x=.06+(j//7)*.48;y=.09+(j%7)*.125
            c.setFillColorRGB(.1,.1,.1);c.setFont('Helvetica',11)
            c.drawString(30+x*w,40+(1-y)*h+17,kind)
            if j<4:c.drawString(30+x*w,40+(1-y)*h-10,'Original text anchor')
        c.save();page=writer.add_page(PdfReader(buf).pages[0]);page.cropbox=RectangleObject([30,40,w+30,h+40]);page.rotate(rotation)
        if i==3:page[NameObject('/UserUnit')]=NumberObject(2)
        for j,kind in enumerate(KINDS):
            x=.06+(j//7)*.48;y=.09+(j%7)*.125
            rect=dict(x=x,y=y,width=.35,height=.075)
            geometry=dict(kind='box',pageNumber=i+1,rect=rect,rotation=-28 if kind=='watermark' else 0)
            if kind=='circle':rect['width']=.075*h/w
            if kind=='ink':geometry=dict(kind='points',pageNumber=i+1,points=[dict(x=x,y=y+.04),dict(x=x+.1,y=y),dict(x=x+.2,y=y+.06),dict(x=x+.3,y=y+.02)])
            pos=None
            if j<4:
                pos=[dict(pageNumber=i+1,rects=[dict(x=x,y=y,width=.30,height=.025,baseline=.8)],textQuote='Original text anchor')]
                geometry=dict(kind='text',positions=pos)
            if kind=='comment':geometry=dict(kind='anchor',pageNumber=i+1,x=x,y=y)
            items.append(dict(id=f'sample-{i}-{j}',documentId='sample',type=kind,schemaVersion=1,pageNumber=i+1,
                geometry=geometry,position=pos,selectedText='Original text anchor' if pos else None,
                content=f'第{i+1}页{kind} 中文正文\nEnglish αβ ±∞ → 第二行\n完整内容不应丢失。'* (6 if kind=='freeText' else 1) if kind in ('comment','freeText','watermark') else None,
                color='#9B0000' if kind!='highlight' else '#F5D547',style=dict(opacity=.55 if kind not in ('freeText','comment') else 1,lineWidth=2,fontSize=14,fill='#6395CF' if kind in ('rectangle','circle') else None),
                assetId='png' if kind=='signature' else 'jpg' if kind=='image' else None,zIndex=j,version=1,createdAt='2026-10-17T00:00:00Z',updatedAt='2026-10-17T00:00:00Z'))
    writer.write(root/'original.pdf')
    return root/'original.pdf',items,dict(png=root/'alpha.png',jpg=root/'photo.jpg')
