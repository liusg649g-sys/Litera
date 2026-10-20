"""Create non-private P3-C1 manual acceptance samples, not screenshots as PDFs."""
import hashlib
import json
from pathlib import Path
import sys
import time
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'backend'),str(ROOT/'backend/tests')]
import fitz
import psutil
from app.pdf_export_renderer import render
from export_samples import samples,KINDS

out=ROOT/'.cache/c1-acceptance';source,items,assets=samples(out)
digest=hashlib.sha256(source.read_bytes()).hexdigest();started=time.monotonic()
render(source,items,assets,out/'all-13-annotated.pdf',52)
doc=fitz.open(out/'all-13-annotated.pdf')
for i,p in enumerate(doc):p.get_pixmap(matrix=fitz.Matrix(1,1)).save(out/f'page-{i+1}.png')
assert hashlib.sha256(source.read_bytes()).hexdigest()==digest
evidence=dict(objects=len(items),types=KINDS,sourcePages=4,exportPages=len(doc),sourceSha256=digest,unchanged=True,
    elapsedSeconds=round(time.monotonic()-started,3),peakWorkingSetMiB=round(psutil.Process().memory_info().peak_wset/1048576,1),bytes=(out/'all-13-annotated.pdf').stat().st_size,
    muPdfVersion=fitz.VersionBind,edgeManual='pending',acrobatManual='pending')
(out/'evidence.json').write_text(json.dumps(evidence,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(evidence,ensure_ascii=False,indent=2))
