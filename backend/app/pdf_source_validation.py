"""Independent, conservative page-text verification for stored note sources.

PDF.js, pypdf and PDFium can segment the same valid PDF differently. We keep
the exact browser quote for display and geometry, while accepting it only when
at least one server extractor finds the same normalized text or contiguous
Unicode word sequence on the claimed physical page.
"""
import re
import unicodedata


_WORD = re.compile(r'[^\W_]+', re.UNICODE)
_LINE_HYPHEN = re.compile(r'([^\W\d_]{2,})-[ \t]*\r?\n[ \t]*([^\W\d_]{2,})', re.UNICODE)


def canonical_text(value: str) -> str:
    return re.sub(r'\s+', ' ', value).strip()


def normalized_text(value: str) -> str:
    return canonical_text(unicodedata.normalize('NFKC', value).replace('\u00ad', ''))


def word_sequence(value: str) -> tuple[str, ...]:
    return tuple(_WORD.findall(unicodedata.normalize('NFKC', value).replace('\u00ad', '')))


def line_hyphen_word_sequence(value: str) -> tuple[str, ...]:
    normalized = unicodedata.normalize('NFKC', value).replace('\u00ad', '')
    return word_sequence(_LINE_HYPHEN.sub(r'\1\2', normalized))


def contains_selection_sequence(page: tuple[str, ...], quote: tuple[str, ...]) -> bool:
    """Allow only the first/last selected word to end/start inside a PDF word."""
    if not quote or len(quote) > len(page):
        return False
    if len(quote) == 1:
        return any(quote[0] in word for word in page)
    for index in range(len(page) - len(quote) + 1):
        window = page[index:index + len(quote)]
        if (window[0].endswith(quote[0]) and window[-1].startswith(quote[-1])
                and window[1:-1] == quote[1:-1]):
            return True
    return False


def source_text_matches(quote: str, extracted_pages: list[str]) -> bool:
    """Verify page-level provenance without rewriting the saved original.

    Punctuation-only selections must match literally after whitespace/NFKC
    normalization. Word selections may ignore extractor-only punctuation and
    spacing differences, but the complete word sequence must stay contiguous,
    ordered and case-preserving on one independently extracted page string.
    A hyphen is removed only in a separate comparison when it is followed by an
    actual line break and both fragments contain letters; stored text is never
    changed and ordinary compounds such as ``label-free`` are not joined.
    """
    raw = canonical_text(quote)
    normalized = normalized_text(quote)
    words = word_sequence(quote)
    joined_words = line_hyphen_word_sequence(quote)
    if not raw:
        return False
    for page in extracted_pages:
        if raw in canonical_text(page) or normalized in normalized_text(page):
            return True
        page_words = word_sequence(page)
        if contains_selection_sequence(page_words, words):
            return True
        if joined_words != words and contains_selection_sequence(line_hyphen_word_sequence(page), joined_words):
            return True
    return False
