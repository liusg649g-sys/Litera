"""Real PDF layout extraction, no external model and no developer data."""
from io import BytesIO
import pytest
from pypdf import PdfReader
from reportlab.pdfgen.canvas import Canvas
from app.pdf_text import model_input_text


def line_pdf(lines):
    stream = BytesIO(); canvas = Canvas(stream, pagesize=(612, 792))
    canvas.setFont('Helvetica', 12)
    for x, y, text in lines:
        canvas.drawString(x, y, text)
    canvas.save()
    return stream.getvalue()


def page(lines):
    return PdfReader(BytesIO(line_pdf(lines))).pages[0]


def test_reviewed_words_require_real_adjacent_same_column_lines():
    raw = 'Some disor-\nders and thera-\npies with ul-\ntrasound.'
    pdf_page = page([(40,700,'Some disor-'),(40,684,'ders and thera-'),(40,668,'pies with ul-'),(40,652,'trasound.')])
    result = model_input_text(raw, pdf_page)
    assert result.text == 'Some disorders and therapies with ultrasound.'
    assert result.joins == 3
    assert raw == 'Some disor-\nders and thera-\npies with ul-\ntrasound.'
    assert 'disor-' in pdf_page.extract_text()  # Source PDF is untouched.


@pytest.mark.parametrize('raw,lines', [
    ('high-intensity and label-free',[(40,700,'high-intensity and label-free')]),
    ('high-\nintensity and label-\nfree',[(40,700,'high-'),(40,684,'intensity and label-'),(40,668,'free')]),
    ('un-\nknown',[(40,700,'un-'),(40,684,'known')]),
    ('disor- ders',[(40,700,'disor- ders')]),
    ('disor-\nders',[(40,700,'disor-'),(300,684,'ders')]),  # Other column.
    ('disor-\nders',[(40,700,'disor-'),(40,620,'ders')]),  # Paragraph gap.
    ('disor-\nders',[(40,700,'disor-'),(40,700,'ders')]),  # Same physical line.
    ('disor-\nders',[(40,700,'disor-ders')]),  # No physical EOL evidence.
    ('other page disor-\nders',[(40,700,'disor-'),(40,684,'ders')]),  # Whole quote not on page.
    ('pre-disor-\nders',[(40,700,'pre-disor-'),(40,684,'ders')]),
])
def test_uncertain_text_and_genuine_hyphens_are_preserved(raw, lines):
    result = model_input_text(raw, page(lines))
    assert result.text == raw and result.joins == 0


def test_crlf_and_capitalized_word_keep_other_source_characters():
    raw='Disor-\r\nders and high-intensity.'
    result=model_input_text(raw,page([(40,700,'Disor-'),(40,684,'ders and high-intensity.')]))
    assert result.text=='Disorders and high-intensity.' and result.joins==1


def test_rotation_mapping_errors_and_extractor_failure_are_noops():
    raw='disor-\nders';pdf_page=page([(40,700,'disor-'),(40,684,'ders')])
    pdf_page.rotate(90)
    assert model_input_text(raw,pdf_page).text==raw
    assert model_input_text('disor-\n\u0003ders',object()).text=='disor-\n\u0003ders'
    class Unsupported:
        def get(self,*args):return 0
        def extract_text(self,**kwargs):raise ValueError('unsupported layout')
    assert model_input_text(raw,Unsupported()).text==raw


@pytest.mark.parametrize('bad_x,bad_y',[(300,636),(40,570)])
def test_repeated_spelling_uses_evidence_at_each_exact_offset(bad_x,bad_y):
    # Same spelling twice, but only the first physical break is trustworthy.
    raw='First disor-\nders. Then disor-\nders.'
    pdf_page=page([(40,700,'First disor-'),(40,684,'ders. Then disor-'),(bad_x,bad_y,'ders.')])
    result=model_input_text(raw,pdf_page)
    assert result.text=='First disorders. Then disor-\nders.' and result.joins==1


def test_repeated_quote_has_no_unique_location_and_is_preserved():
    raw='disor-\nders'
    pdf_page=page([(40,700,'disor-'),(40,684,'ders'),(40,650,'disor-'),(40,570,'ders')])
    result=model_input_text(raw,pdf_page)
    assert result.text==raw and result.joins==0


def test_visitor_text_offsets_must_match_extraction_exactly():
    class MismatchedVisitor:
        def get(self,*args):return 0
        def extract_text(self,visitor_text):
            visitor_text('disor-\n',[1,0,0,1,0,0],[1,0,0,1,40,700],None,12)
            visitor_text('ders\n',[1,0,0,1,0,0],[1,0,0,1,40,684],None,12)
            return 'unvisited prefix disor-\nders\n'
    result=model_input_text('disor-\nders',MismatchedVisitor())
    assert result.text=='disor-\nders' and result.joins==0
