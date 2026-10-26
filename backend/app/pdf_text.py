"""Conservative PDF line-end dehyphenation for model input, never source repair.

Only a small reviewed vocabulary and independently extracted, simple same-column
PDF line geometry are accepted. Everything uncertain is deliberately preserved.
"""
from dataclasses import dataclass
import math
import re

from .text_quality import unreliable_characters

# Explicitly reviewed scientific words, not a heuristic that joins arbitrary words.
# In particular high-intensity / label-free are not members. Expand with evidence
# and regression tests, not by treating every alphabetic hyphen as discretionary.
_JOINABLE_WORDS = frozenset({'disorders', 'therapies', 'ultrasound'})
_END = re.compile(r'(?<![A-Za-z-])([A-Za-z]{2,})-$')
_START = re.compile(r'^([a-z]{2,})(?=$|[^A-Za-z-])')
_BREAK = re.compile(r'(?<![A-Za-z-])([A-Za-z]{2,})-[ \t]*\r?\n[ \t]*([a-z]{2,})(?=$|[^A-Za-z-])')

@dataclass(frozen=True)
class ModelInput:
    text: str
    joins: int = 0


def model_input_text(original: str, page) -> ModelInput:
    """Return separate model text only when the whole quote belongs to this page.

    Caller must first enforce the page's font-mapping guard. The character guard
    is repeated here as defense in depth. No PDF bytes, selection ranges or
    annotation geometry are changed. Unsupported layouts/extraction errors are a
    no-op, not a new reason to reject otherwise readable text.
    """
    unchanged = ModelInput(original)
    if unreliable_characters(original) or not _BREAK.search(original):
        return unchanged
    lines, chunks = [], []
    offset = 0
    try:
        if int(page.get('/Rotate', 0)) % 360:
            return unchanged

        def visit(text, cm, tm, font, size):
            nonlocal offset
            text = text.replace('\r\n', '\n')
            start_offset = offset
            chunks.append(text)
            offset += len(text)
            if not text.strip():
                return
            # pypdf's visitor coordinates are reliable here only for simple,
            # upright, positive axis-aligned matrices. Do not infer rotations,
            # shears, complex transforms, multi-line chunks or text without EOL.
            values = [*cm, *tm, float(size)]
            if not all(math.isfinite(float(v)) for v in values):
                lines.append(None); return
            if any(abs(float(v)) > 1e-6 for v in (cm[1], cm[2], tm[1], tm[2])) or min(cm[0], cm[3], tm[0], tm[3], size) <= 0:
                lines.append(None); return
            content = text.rstrip('\r\n')
            if not text.endswith(('\n', '\r')) or '\n' in content or '\r' in content or unreliable_characters(content):
                lines.append(None); return
            x = tm[4] * cm[0] + cm[4]
            y = tm[5] * cm[3] + cm[5]
            height = float(size) * tm[3] * cm[3]
            lines.append((content, x, y, height, start_offset))

        extracted = page.extract_text(visitor_text=visit)
        # A multi-page quote, reordered columns, or different text extraction is
        # insufficient evidence. Require an exact single-page quote (CRLF only
        # canonicalized for this comparison, never for the returned raw source).
        extracted = (extracted or '').replace('\r\n', '\n')
        quote = original.replace('\r\n', '\n')
        # Visitor reconstruction must exactly match extract_text, otherwise its
        # character offsets cannot be used as positional evidence. A repeated
        # quote has no unique source offset and is likewise left untouched.
        if ''.join(chunks) != extracted:
            return unchanged
        quote_start = extracted.find(quote)
        if quote_start < 0 or extracted.find(quote, quote_start + 1) >= 0:
            return unchanged
        evidence = set()
        for before, after in zip(lines, lines[1:]):
            if before is None or after is None:
                continue
            left, x1, y1, h1, offset1 = before
            right, x2, y2, h2, offset2 = after
            if max(h1, h2) > min(h1, h2) * 1.1 or abs(x1-x2) > min(h1, h2) * .25:
                continue
            if not .8 * max(h1, h2) <= y1-y2 <= 1.8 * min(h1, h2):
                continue
            end, start = _END.search(left), _START.search(right)
            if end and start and (end[1] + start[1]).lower() in _JOINABLE_WORDS:
                evidence.add((offset1 + end.start(1), offset2 + start.end(1)))
        if not evidence:
            return unchanged
        joins = 0
        def combine(match):
            nonlocal joins
            # Map the raw regex boundaries to the canonical comparison string.
            # The returned raw source itself retains its CRLF and all bytes.
            start = quote_start + len(original[:match.start()].replace('\r\n', '\n'))
            end = quote_start + len(original[:match.end()].replace('\r\n', '\n'))
            if (start, end) not in evidence:
                return match[0]
            joins += 1
            return match[1] + match[2]
        return ModelInput(_BREAK.sub(combine, original), joins)
    except Exception:
        # Optional normalization must not replace the established mapping guard
        # or break normal translation when layout extraction is unsupported.
        return unchanged
