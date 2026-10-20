"""Isolated PDF renderer. Uses saved normalized CropBox coordinates, never screenshots."""
import io
import math
from pathlib import Path

from pypdf import PdfReader, PdfWriter, Transformation
from pypdf.annotations import Text, FreeText, Popup
from pypdf.generic import (ArrayObject, DecodedStreamObject, DictionaryObject,
                          FloatObject, NameObject, NumberObject, RectangleObject, TextStringObject)
from reportlab.lib.colors import HexColor
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen.canvas import Canvas

FONT = 'LiteraNotoSansSC'
LABELS = dict(highlight='高亮', underline='下划线', squiggly='波浪线', strikeout='删除线',
              comment='注释', freeText='自由文本', ink='手绘', rectangle='矩形', circle='圆形',
              ellipse='椭圆形', signature='签名', watermark='水印', image='图片')


class ExportError(Exception):
    def __init__(self, code, message):
        self.code, self.message = code, message
        super().__init__(message)


def font():
    if FONT not in pdfmetrics.getRegisteredFontNames():
        pdfmetrics.registerFont(TTFont(FONT, str(Path(__file__).parent/'fonts/NotoSansSC.ttf')))
    return pdfmetrics.getFont(FONT)


def checked_text(text):
    text = (text or '').replace('\r\n', '\n').replace('\r', '\n').replace('\t', '    ')
    glyphs = font().face.charToGlyph
    missing = sorted({ord(ch) for ch in text if ch != '\n' and not glyphs.get(ord(ch))})
    if missing:
        raise ExportError('EXPORT_UNSUPPORTED_GLYPH', '导出字体不支持字符 ' + ', '.join(f'U+{n:04X}' for n in missing[:8]) + '，请修改正文后重试')
    return text


def wrap(text, width, size):
    """CSS pre-wrap/overflow-wrap:anywhere equivalent, bounded linear glyph work."""
    lines = []
    widths = font().face.charWidths
    for paragraph in text.split('\n'):
        line, used = '', 0
        for ch in paragraph:
            advance = widths.get(ord(ch), 1000) * size / 1000
            if line and used + advance > max(width, 1):
                lines.append(line); line, used = '', 0
            line += ch; used += advance
        lines.append(line)
    return lines


def union(a, b):
    x, y = min(a['x'], b['x']), min(a['y'], b['y'])
    return dict(x=x, y=y, width=max(a['x']+a['width'], b['x']+b['width'])-x,
                height=max(a['y']+a['height'], b['y']+b['height'])-y)


def mark_lines(rects, w, h):
    """Port of B1 mergeTextRects/textMarkLines; body baseline survives superscripts."""
    merged = []
    for r in sorted(rects, key=lambda r: (r['y'], r['x'])):
        r = dict(r)
        found = None
        for p in merged:
            overlap = (min(p['y']+p['height'], r['y']+r['height'])-max(p['y'], r['y']))*h
            gap = (max(p['x'],r['x'])-min(p['x']+p['width'],r['x']+r['width']))*w
            if overlap >= min(p['height'],r['height'])*h*.75 and max(p['height'],r['height']) <= min(p['height'],r['height'])*1.4 and gap <= min(p['height'],r['height'])*h*.55:
                found = p; break
        if found is None:
            merged.append(r); continue
        baseline = max(found['y']+found['height']*found.get('baseline',.8),r['y']+r['height']*r.get('baseline',.8))
        has_baseline = 'baseline' in found or 'baseline' in r
        found.update(union(found,r))
        if has_baseline: found['baseline']=(baseline-found['y'])/found['height']
    rows = [dict(rect=dict(r), body=dict(r), attached=False) for r in merged]
    for small in sorted(rows, key=lambda r:r['body']['height']):
        s=small['body']; candidates=[]
        sb=(s['y']+s['height']*s.get('baseline',.8))*h
        for row in rows:
            if row is small or row['attached']: continue
            b=row['body']; bh=b['height']*h
            gap=max(0,(max(s['x'],b['x'])-min(s['x']+s['width'],b['x']+b['width']))*w)
            rise=(sb-(b['y']+b['height']*b.get('baseline',.8))*h)/bh
            if .3 <= s['height']/b['height'] <= .85 and s['width']*w <= 6*bh and gap <= .65*bh and -.95 <= rise <= -.12:
                candidates.append((gap/bh,abs(rise),row))
        if candidates:
            target=min(candidates,key=lambda c:c[:2])[2]
            target['rect']=union(target['rect'],small['rect']); small['attached']=True
    lines=[]
    for row in sorted((r for r in rows if not r['attached']),key=lambda r:(r['body']['y'],r['rect']['x'])):
        b=row['body']; found=None
        for p in lines:
            a=p['body']; height=min(a['height'],b['height'])*h
            baseline=lambda r:(r['y']+r['height']*r.get('baseline',.8))*h
            gap=(max(p['rect']['x'],row['rect']['x'])-min(p['rect']['x']+p['rect']['width'],row['rect']['x']+row['rect']['width']))*w
            if abs(baseline(a)-baseline(b)) <= height*.12 and max(a['height'],b['height']) <= min(a['height'],b['height'])*1.4 and gap <= height*.55:
                found=p;break
        if found is None: lines.append(row)
        else:
            found['rect']=union(found['rect'],row['rect'])
            if b['height']>found['body']['height']:found['body']=b
    return lines


def comment_layout(a, w, h, unit, page_number, rotation):
    g=a['geometry']
    if g['kind']=='anchor':px,py=g['x']*w,(1-g['y'])*h
    else:
        pos=next(p for p in g['positions'] if p['pageNumber']==page_number)
        px,py=pos['rects'][0]['x']*w,(1-pos['rects'][0]['y'])*h
    rotation=rotation%360
    sx,sy,sw={0:(px,h-py,w),90:(py,px,h),180:(w-px,py,w),270:(h-py,w-px,h)}[rotation]
    return px,py,(-1 if sx>sw-25/unit else 1)/unit,(-1 if sy<23/unit else 1)/unit


def draw_object(c, a, w, h, unit, assets, number, page_number, rotation=0):
    g, kind, style = a['geometry'], a['type'], a['style']
    opacity=style.get('opacity',1); size=style.get('fontSize',14)/unit
    c.saveState()
    c.setFillColor(HexColor(a['color']));c.setStrokeColor(HexColor(style.get('stroke') or a['color']))
    c.setFillAlpha(opacity);c.setStrokeAlpha(opacity)
    c.setLineWidth(style.get('lineWidth',1)/unit);c.setLineCap(1);c.setLineJoin(1)
    c.setFont(FONT,size)
    if g['kind']=='text':
        positions=[p for p in g['positions'] if p['pageNumber']==page_number]
        for pos in positions:
            for row in mark_lines(pos['rects'],w,h):
                r,b=row['rect'],row['body']; x,y,rw,rh=r['x']*w,(1-r['y']-r['height'])*h,r['width']*w,r['height']*h
                if kind=='highlight':c.rect(x,y,rw,rh,fill=1,stroke=0)
                elif kind in ('underline','squiggly','strikeout'):
                    offset=max(.35,min(.6,b.get('baseline',.8)-.32)) if kind=='strikeout' else max(.82,min(.9,b.get('baseline',.8)+.075))
                    y=(1-b['y']-b['height']*offset)*h
                    c.setLineWidth(min(style.get('lineWidth',1)/unit,b['height']*h*.065))
                    if kind=='squiggly':
                        amp=b['height']*h*.035; halves=max(2,math.ceil(rw/(max(3,b['height']*h*.32)/2)));step=rw/halves
                        path=c.beginPath();path.moveTo(x,y)
                        for i in range(halves):
                            # quadratic to cubic conversion, matching B1 smoothWave.
                            ax=x+i*step; end=ax+step; control=y+(1 if i%2 else -1)*amp*2
                            path.curveTo(ax+step/3,y+(control-y)*2/3,end-step/3,y+(control-y)*2/3,end,y)
                        c.drawPath(path)
                    else:c.line(x,y,x+rw,y)
    elif g['kind']=='points':
        path=c.beginPath()
        for i,p in enumerate(g['points']):
            (path.moveTo if i==0 else path.lineTo)(p['x']*w,(1-p['y'])*h)
        c.drawPath(path)
    elif g['kind']=='box':
        r=g['rect'];x,y,rw,rh=r['x']*w,(1-r['y']-r['height'])*h,r['width']*w,r['height']*h
        fill=bool(style.get('fill'))
        if fill:c.setFillColor(HexColor(style['fill']))
        if kind=='rectangle':c.rect(x,y,rw,rh,stroke=1,fill=int(fill))
        elif kind in ('circle','ellipse'):c.ellipse(x,y,x+rw,y+rh,stroke=1,fill=int(fill))
        elif kind in ('signature','image'):
            c.translate(x+rw/2,y+rh/2);c.rotate(-g.get('rotation',0))
            c.drawImage(ImageReader(str(assets[a['assetId']])),-rw/2,-rh/2,rw,rh,preserveAspectRatio=True,anchor='c',mask='auto')
        elif kind in ('freeText','watermark'):
            text=checked_text(a['content']);c.setFillColor(HexColor(a['color']))
            path=c.beginPath();path.rect(x,y,rw,rh);c.clipPath(path,stroke=0,fill=0)
            if kind=='freeText':
                for i,line in enumerate(wrap(text,max(1,rw-3/unit),size)):
                    c.drawString(x+3/unit,y+rh-size-i*size*1.25,line)
                    if size+i*size*1.25 > rh+size:break
            else:
                c.translate(x+rw/2,y+rh/2);c.rotate(-g.get('rotation',0))
                lines=text.split('\n')
                for i,line in enumerate(lines):c.drawCentredString(0,(len(lines)-1)*size*.625-i*size*1.25-size*.35,line)
    if kind=='comment':
        px,py,flip_x,flip_y=comment_layout(a,w,h,unit,page_number,rotation)
        # Match B1's upright speech bubble, including edge flips on rotated pages.
        c.translate(px,py);c.rotate(rotation)
        c.scale(flip_x,flip_y)
        path=c.beginPath();path.moveTo(0,0);path.lineTo(0,18);path.curveTo(0,20,1,21,3,21)
        path.lineTo(20,21);path.curveTo(22,21,23,20,23,18);path.lineTo(23,7);path.curveTo(23,5,22,4,20,4);path.lineTo(6,4);path.close()
        c.setStrokeColorRGB(1,1,1);c.setLineWidth(1.2);c.drawPath(path,fill=1,stroke=1)
        c.setLineWidth(1.4);c.line(5,15,18,15);c.line(5,10,15,10)
    c.restoreState()


def add_text_annotation(writer, page, a, w, h, unit, assets, page_number, left, bottom):
    """One native markup annotation owns both its appearance and full Unicode body."""
    if a['type']=='comment':
        px,py,fx,fy=comment_layout(a,w,h,unit,page_number,page.rotation)
        theta=math.radians(page.rotation);cs,sn=math.cos(theta),math.sin(theta)
        points=[(px+cs*x*fx-sn*y*fy,py+sn*x*fx+cs*y*fy) for x in (-1,24) for y in (-1,22)]
        bounds=(min(p[0] for p in points),min(p[1] for p in points),max(p[0] for p in points),max(p[1] for p in points))
    else:
        r=a['geometry']['rect'];bounds=(r['x']*w,(1-r['y']-r['height'])*h,(r['x']+r['width'])*w,(1-r['y'])*h)
    rect=(bounds[0]+left,bounds[1]+bottom,bounds[2]+left,bounds[3]+bottom)
    appearance=DecodedStreamObject()
    if a['type']=='comment':
        buf=io.BytesIO();c=Canvas(buf,pagesize=(w,h),pageCompression=1)
        draw_object(c,a,w,h,unit,assets,None,page_number,page.rotation);c.save()
        appearance_page=PdfReader(buf).pages[0]
        appearance.set_data(appearance_page.get_contents().get_data())
        resources=appearance_page['/Resources'].clone(writer)
    else:
        # Free text / watermark keep their existing page-content z-order.
        # This annotation adds only a full-body popup, with no duplicate paint.
        appearance.set_data(b'');resources=DictionaryObject()
    appearance.update({NameObject('/Type'):NameObject('/XObject'),NameObject('/Subtype'):NameObject('/Form'),
        NameObject('/BBox'):RectangleObject(bounds),NameObject('/Resources'):resources})
    if a['type']=='comment':
        note=Text(rect=rect,text=a['content'],open=False)
        note.pop('/Flags',None)  # pypdf Text uses /Flags; PDF annotation flags belong in /F.
        note[NameObject('/Name')]=NameObject('/Comment')
    else:
        # Both are text objects. Edge adds its own comment icon to /Stamp even
        # with an empty AP, causing a stray bubble at the watermark position.
        note=FreeText(rect=rect,text=a['content'])
    rgb=HexColor(a['color'])
    note.update({NameObject('/F'):NumberObject(4),NameObject('/T'):TextStringObject('Litera'),
        NameObject('/Subj'):TextStringObject(LABELS[a['type']]),
        NameObject('/NM'):TextStringObject(f"litera-{a['id']}-{page_number}"),
        NameObject('/C'):ArrayObject([FloatObject(rgb.red),FloatObject(rgb.green),FloatObject(rgb.blue)]),
        NameObject('/AP'):DictionaryObject({NameObject('/N'):writer._add_object(appearance)})})
    parent=writer.add_annotation(page,note)
    pw,ph=min(280/unit,w),min(180/unit,h)
    x=min(max(bounds[2]+8/unit,0),w-pw);y=min(max(bounds[3]-ph,0),h-ph)
    writer.add_annotation(page,Popup(rect=(left+x,bottom+y,left+x+pw,bottom+y+ph),parent=parent,open=False))
    if writer.pdf_header<'%PDF-1.4':writer.pdf_header='%PDF-1.4'


def render(source, items, assets, target, revision):
    font()
    for a in items:
        if a.get('content'):checked_text(a['content'])
    reader=PdfReader(str(source))
    if len(reader.pages)>1000:raise ExportError('EXPORT_LIMIT','导出最多支持1000页')
    writer=PdfWriter();writer.clone_document_from_reader(reader)
    ordered=sorted(items,key=lambda a:(a['zIndex'],a['createdAt'],a['id']))
    by_page={}
    for a in ordered:
        pages={p['pageNumber'] for p in a['geometry']['positions']} if a['geometry']['kind']=='text' else {a['pageNumber']}
        for n in pages:
            if n<1 or n>len(writer.pages):raise ExportError('EXPORT_INVALID_SNAPSHOT','批注页码与PDF不一致')
            by_page.setdefault(n,[]).append(a)
    for n,page in enumerate(writer.pages,1):
        if n not in by_page:continue
        left,bottom,right,top=map(float,page.cropbox)
        # PDF.js uses the intersection with MediaBox, falling back to MediaBox.
        ml,mb,mr,mt=map(float,page.mediabox)
        l,b,r,t=max(left,ml),max(bottom,mb),min(right,mr),min(top,mt)
        if l>=r or b>=t:l,b,r,t=ml,mb,mr,mt
        w,h=r-l,t-b;unit=float(page.get('/UserUnit',1))
        if not all(math.isfinite(v) for v in (w,h,unit)) or w<=0 or h<=0 or unit<=0:
            raise ExportError('EXPORT_INVALID_PDF','PDF页面尺寸无效')
        flat=[a for a in by_page[n] if a['type']!='comment']
        if flat:
            buf=io.BytesIO();c=Canvas(buf,pagesize=(w,h),pageCompression=1)
            for a in flat:draw_object(c,a,w,h,unit,assets,None,n,page.rotation)
            c.save();page.merge_transformed_page(PdfReader(buf).pages[0],Transformation().translate(l,b))
        for a in by_page[n]:
            if a['type'] in ('comment','freeText','watermark'):
                add_text_annotation(writer,page,a,w,h,unit,assets,n,l,b)
    writer.add_metadata({'/LiteraAnnotationRevision':str(revision),'/LiteraExport':'Page-preserving export with native Unicode annotation popups'})
    writer.write(str(target))
    reopened=PdfReader(str(target))
    if len(reopened.pages)!=len(reader.pages):raise ExportError('EXPORT_INVALID_PDF','导出文件校验失败')
