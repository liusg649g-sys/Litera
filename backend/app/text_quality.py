"""Conservative extraction checks; never repair text by substitution or deletion."""
import re
import unicodedata

def unreliable_characters(text):
    return any((ord(c)<32 and c not in '\t\r\n') or 0x7f<=ord(c)<=0x9f or c=='\ufffd' or unicodedata.category(c) in ('Co','Cs') for c in text)

def opaque_font_mapping(page):
    fonts=page.get('/Resources',{}).get('/Font',{})
    if hasattr(fonts,'get_object'): fonts=fonts.get_object()
    for ref in fonts.values():
        font=ref.get_object()
        if font.get('/ToUnicode'): continue
        encoding=font.get('/Encoding',{})
        if hasattr(encoding,'get_object'):encoding=encoding.get_object()
        if not hasattr(encoding,'get'):continue
        names=[str(n) for n in encoding.get('/Differences',[]) if isinstance(n,str)]
        if names and all(re.fullmatch(r'/(?:G[0-9A-Fa-f]+|glyph[0-9]+|g[0-9]+)',name) for name in names):return True
    return False
