"""Native Edge PDF regression on generated public samples (not manual acceptance).

Run create_pdf_export_samples.py first, then this script with backend's Python.
Requires installed Edge and frontend's Playwright. Uses an isolated browser profile.
"""
import json
from pathlib import Path
import subprocess

from PIL import Image, ImageChops
from pypdf import PdfReader, PdfWriter
from pypdf.generic import ArrayObject, NameObject

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / '.cache/c1-acceptance'
source = OUT / 'all-13-annotated.pdf'

# Control has identical page content and comment, without watermark semantics.
# Legacy probe intentionally restores the subtype responsible for Edge's icon.
for variant in ('control', 'legacy'):
    writer = PdfWriter(clone_from=source)
    for page in writer.pages:
        notes = [ref for ref in page.annotations or []
                 if ref.get_object().get('/Subj') == '水印'
                 and ref.get_object().get('/NM', '').startswith('litera-')]
        assert len(notes) == 1
        if variant == 'control':
            excluded = {ref.idnum for ref in notes}
            excluded.update(ref.get_object().raw_get('/Popup').idnum for ref in notes)
            page[NameObject('/Annots')] = ArrayObject(
                ref for ref in page.annotations if ref.idnum not in excluded)
        else:
            for ref in notes:
                ref.get_object()[NameObject('/Subtype')] = NameObject('/Stamp')
    writer.write(OUT / f'edge-{variant}.pdf')

script = r"""
const {chromium}=require('./frontend/node_modules/playwright');
(async()=>{
  const browser=await chromium.launch({channel:'msedge',headless:true});
  try {
    console.log(JSON.stringify({edgeVersion:browser.version()}));
    for (const name of ['all-13-annotated','edge-control','edge-legacy']) {
      const page=await browser.newPage({viewport:{width:1100,height:1100}});
      await page.goto(new URL('.cache/c1-acceptance/'+name+'.pdf', 'file:///'+process.cwd().replaceAll('\\','/')+'/').href);
      await page.waitForTimeout(2400);
      await page.screenshot({path:'.cache/c1-acceptance/'+name+'-edge.png'});
      await page.close();
    }
  } finally { await browser.close(); }
})().catch(e=>{console.error(e);process.exit(1)});
"""
result = subprocess.run(['node', '-e', script], cwd=ROOT, check=True,
                        capture_output=True, text=True)
version = json.loads(result.stdout.strip())
# Exclude native toolbar/filename; include the complete first-page content.
images = [Image.open(OUT / f'{name}-edge.png').convert('RGB').crop((150, 60, 948, 1058))
          for name in ('all-13-annotated', 'edge-control', 'edge-legacy')]
actual = ImageChops.difference(images[0], images[1])
legacy = ImageChops.difference(images[2], images[1])
actual.save(OUT / 'edge-fixed-diff.png')
legacy.save(OUT / 'edge-legacy-diff.png')
assert actual.getbbox() is None, 'Unexpected native Edge paint from watermark semantics'
assert legacy.getbbox() is not None, 'Probe did not reproduce the legacy stray icon'
notes = [a.get_object() for p in PdfReader(source).pages for a in p.annotations or []
         if a.get_object().get('/NM', '').startswith('litera-')]
assert sum(a['/Subtype'] == '/Text' for a in notes) == 4
assert sum(a['/Subtype'] == '/FreeText' for a in notes) == 8
evidence = dict(**version, fixedMatchesControl=True, legacyDiff=legacy.getbbox(),
                nativeComments=4, nativeTextObjects=8, manualAcceptance='pending')
(OUT / 'edge-regression.json').write_text(json.dumps(evidence, indent=2), encoding='utf-8')
print(json.dumps(evidence, indent=2))
