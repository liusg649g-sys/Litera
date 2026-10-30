"""Single-document retrieval: tokenisation, BM25, cosine, RRF/MMR, neighbours,
section detection and versioned index lifecycle.

Pure Python on purpose: a document has hundreds of chunks, the container has no
numpy, and an external vector database would add an operational component.
"""
from __future__ import annotations

import asyncio
import html
import logging
import math
import re
import uuid
from array import array
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Iterable, Sequence

from sqlalchemy import delete, select, update

from .ai_service import DeveloperProfileResolver, MODEL_SLOTS, ModelFailure, ModelService
from .config import get_model_settings
from .models import Document, DocumentChunk, QaChunkVector, QaIndex

logger = logging.getLogger(__name__)

CJK_RUN = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]+")
TOKEN_RUN = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]+|[A-Za-z0-9]+")


@dataclass(frozen=True)
class Chunk:
    id: str
    page_number: int
    start_offset: int
    text: str


@dataclass
class Retrieval:
    chunks: list[Chunk]
    scores: dict[str, float]
    max_similarity: float
    keyword_top: float

    @property
    def empty(self) -> bool:
        return not self.chunks


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def tokenize(text: str) -> list[str]:
    """Chinese runs become character bigrams; Latin/number runs become lower-case words."""
    tokens: list[str] = []
    for run in TOKEN_RUN.findall((text or "").lower()):
        if CJK_RUN.fullmatch(run):
            if len(run) == 1:
                tokens.append(run)
            else:
                tokens.extend(run[i:i + 2] for i in range(len(run) - 1))
        else:
            tokens.append(run)
    return tokens


def bm25_scores(query_tokens: Sequence[str], documents: Sequence[Sequence[str]],
                k1: float = 1.2, b: float = 0.75) -> list[float]:
    if not documents:
        return []
    if not query_tokens:
        return [0.0] * len(documents)
    count = len(documents)
    lengths = [len(tokens) for tokens in documents]
    average = (sum(lengths) / count) or 1.0
    frequencies = [{token: tokens.count(token) for token in set(tokens)} for tokens in documents]
    document_frequency: dict[str, int] = {}
    for tokens in documents:
        for token in set(tokens):
            document_frequency[token] = document_frequency.get(token, 0) + 1
    scores: list[float] = []
    for index in range(count):
        score = 0.0
        for token in set(query_tokens):
            frequency = frequencies[index].get(token)
            if not frequency:
                continue
            df = document_frequency.get(token, 0)
            idf = math.log(1 + (count - df + 0.5) / (df + 0.5))
            score += idf * frequency * (k1 + 1) / (frequency + k1 * (1 - b + b * lengths[index] / average))
        scores.append(score)
    return scores


def cosine(left: Sequence[float], right: Sequence[float]) -> float:
    if not left or not right or len(left) != len(right):
        return 0.0
    dot = norm_left = norm_right = 0.0
    for a, b in zip(left, right):
        dot += a * b
        norm_left += a * a
        norm_right += b * b
    if norm_left <= 0 or norm_right <= 0:
        return 0.0
    return dot / math.sqrt(norm_left * norm_right)


def reciprocal_rank_fusion(rankings: Iterable[Sequence[str]], k: int = 60) -> dict[str, float]:
    scores: dict[str, float] = {}
    for ranking in rankings:
        for rank, chunk_id in enumerate(ranking):
            scores[chunk_id] = scores.get(chunk_id, 0.0) + 1.0 / (k + rank + 1)
    return scores


def maximal_marginal_relevance(candidates: Sequence[tuple[str, float]], vectors: dict[str, list[float]],
                               top_k: int, diversity: float = 0.65) -> list[str]:
    """Select diverse chunks; relevance is scaled to 0..1 so cosine dominates the penalty."""
    remaining = list(candidates)
    if not remaining or top_k <= 0:
        return []
    best = max(score for _, score in remaining) or 1.0
    selected: list[str] = []
    while remaining and len(selected) < top_k:
        chosen = None
        chosen_value = -math.inf
        for chunk_id, score in remaining:
            relevance = score / best
            redundancy = max((cosine(vectors.get(chunk_id, []), vectors.get(other, []))
                              for other in selected), default=0.0)
            value = diversity * relevance - (1 - diversity) * redundancy
            if value > chosen_value:
                chosen, chosen_value = (chunk_id, score), value
        remaining = [item for item in remaining if item[0] != chosen[0]]
        selected.append(chosen[0])
    return selected


def rank_chunks(query_vector: Sequence[float], query_text: str, chunks: Sequence[Chunk],
                vectors: dict[str, list[float]], recall_k: int = 30, top_k: int = 8) -> Retrieval:
    if not chunks:
        return Retrieval([], {}, 0.0, 0.0)
    similarities = {chunk.id: cosine(query_vector, vectors[chunk.id]) if chunk.id in vectors else 0.0
                    for chunk in chunks}
    vector_ranking = sorted(similarities, key=lambda chunk_id: similarities[chunk_id], reverse=True)[:recall_k]
    tokens = tokenize(query_text)
    tokenised = {chunk.id: tokenize(chunk.text) for chunk in chunks}
    keyword_scores = dict(zip((chunk.id for chunk in chunks),
                              bm25_scores(tokens, [tokenised[chunk.id] for chunk in chunks])))\
        if tokens else {chunk.id: 0.0 for chunk in chunks}
    keyword_ranking = sorted(keyword_scores, key=lambda chunk_id: keyword_scores[chunk_id], reverse=True)[:recall_k]
    fused = reciprocal_rank_fusion([vector_ranking, keyword_ranking])
    ordered = sorted(fused.items(), key=lambda item: item[1], reverse=True)
    selected = maximal_marginal_relevance(ordered, vectors, top_k)
    by_id = {chunk.id: chunk for chunk in chunks}
    return Retrieval(
        chunks=[by_id[chunk_id] for chunk_id in selected if chunk_id in by_id],
        scores=fused,
        max_similarity=max(similarities.values(), default=0.0),
        keyword_top=max(keyword_scores.values(), default=0.0),
    )


def expand_neighbours(selected: Sequence[Chunk], pool: Sequence[Chunk], max_chars: int) -> list[Chunk]:
    """Add the previous/next chunk on the same page, preserving reading order."""
    if not selected:
        return []
    ordered_pool = sorted(pool, key=lambda chunk: (chunk.page_number, chunk.start_offset))
    positions = {chunk.id: index for index, chunk in enumerate(ordered_pool)}
    wanted: dict[str, Chunk] = {chunk.id: chunk for chunk in selected}
    for chunk in selected:
        index = positions.get(chunk.id)
        if index is None:
            continue
        for neighbour_index in (index - 1, index + 1):
            if 0 <= neighbour_index < len(ordered_pool):
                neighbour = ordered_pool[neighbour_index]
                if neighbour.page_number == chunk.page_number:
                    wanted.setdefault(neighbour.id, neighbour)
    result: list[Chunk] = []
    used = 0
    for chunk in sorted(wanted.values(), key=lambda item: (item.page_number, item.start_offset)):
        if result and used + len(chunk.text) > max_chars:
            break
        result.append(chunk)
        used += len(chunk.text)
    return result


def render_sources(chunks: Sequence[Chunk]) -> str:
    """Model input is data: escape markup so a chunk cannot close its wrapper."""
    return "\n".join(
        f'<source id="{index}" page="{chunk.page_number}">{html.escape(chunk.text, quote=False)}</source>'
        for index, chunk in enumerate(chunks, start=1)
    )


HEADING_PATTERNS: tuple[tuple[str, re.Pattern], ...] = (
    ("abstract", re.compile(r"^(abstract|summary|a\s*b\s*s\s*t\s*r\s*a\s*c\s*t|摘\s*要)\b", re.I)),
    ("introduction", re.compile(r"^(introduction|background|前\s*言|引\s*言|绪\s*论)\b", re.I)),
    ("related", re.compile(r"^(related\s+work|literature\s+review|相关工作|文献综述)\b", re.I)),
    ("method", re.compile(r"^(method|methods|methodology|approach|proposed\s+method|materials\s+and\s+methods|"
                          r"方\s*法|研究方法|材料与方法|模型与方法|方法介绍)\b", re.I)),
    ("experiment", re.compile(r"^(experiment|experiments|experimental\s+setup|evaluation|实\s*验|实验设置|实验与分析)\b", re.I)),
    ("results", re.compile(r"^(result|results|discussion|findings|results\s+and\s+discussion|"
                           r"结\s*果|结果与分析|实验结果|结果与讨论)\b", re.I)),
    ("conclusion", re.compile(r"^(conclusion|conclusions|concluding\s+remarks|summary\s+and\s+conclusion|"
                              r"结\s*论|结\s*语|总\s*结|结论与展望)\b", re.I)),
    ("references", re.compile(r"^(references|bibliography|参\s*考\s*文\s*献)\b", re.I)),
)
_HEADING_PREFIX = re.compile(r"^(?:\d+(?:\.\d+)*\.?\s*|[ivxIVX]+\.\s*|[一二三四五六七八九十]+[、．.]\s*)")


def heading_key(text: str) -> str | None:
    first_line = next((line.strip() for line in (text or "").splitlines() if line.strip()), "")
    if not first_line or len(first_line) > 80:
        return None
    normalized = _HEADING_PREFIX.sub("", first_line).strip()
    for key, pattern in HEADING_PATTERNS:
        if pattern.match(normalized):
            return key
    return None


def section_map(chunks: Sequence[Chunk]) -> dict[str, str]:
    """Each chunk inherits the most recent heading; text before any heading is introduction."""
    ordered = sorted(chunks, key=lambda chunk: (chunk.page_number, chunk.start_offset))
    current = "introduction"
    mapping: dict[str, str] = {}
    for chunk in ordered:
        detected = heading_key(chunk.text)
        if detected:
            current = detected
        mapping[chunk.id] = current
    return mapping


ANALYSIS_SECTIONS = ("background", "method", "results", "conclusion")


def section_context(chunks: Sequence[Chunk], mapping: dict[str, str], *,
                    per_section: int = 4, max_chars: int = 12000) -> dict[str, list[Chunk]]:
    """Pick heading-first chunks per analysis section; missing sections stay absent."""
    ordered = sorted(chunks, key=lambda chunk: (chunk.page_number, chunk.start_offset))
    groups: dict[str, list[Chunk]] = {key: [] for key in ANALYSIS_SECTIONS}
    for chunk in ordered:
        key = mapping.get(chunk.id)
        if key in ("related", "introduction"):
            key = "background"
        if key in groups and len(groups[key]) < per_section:
            groups[key].append(chunk)
    result: dict[str, list[Chunk]] = {}
    used = 0
    for key in ANALYSIS_SECTIONS:
        selected = groups[key]
        if not selected:
            continue
        kept: list[Chunk] = []
        for chunk in selected:
            if used + len(chunk.text) > max_chars:
                break
            kept.append(chunk)
            used += len(chunk.text)
        if kept:
            result[key] = kept
    return result


def encode_vector(values: Sequence[float]) -> bytes:
    return array("f", (float(value) for value in values)).tobytes()


def decode_vector(blob: bytes) -> list[float]:
    vector = array("f")
    vector.frombytes(blob)
    return vector.tolist()


def load_chunks(db, owner_id: str, document_id: str, extraction_version: str) -> list[Chunk]:
    rows = db.scalars(select(DocumentChunk).where(
        DocumentChunk.owner_id == owner_id,
        DocumentChunk.document_id == document_id,
        DocumentChunk.extraction_version == extraction_version,
    ).order_by(DocumentChunk.page_number, DocumentChunk.start_offset)).all()
    return [Chunk(row.id, row.page_number, row.start_offset, row.text or "") for row in rows]


def load_vectors(db, document_id: str, extraction_version: str) -> dict[str, list[float]]:
    rows = db.scalars(select(QaChunkVector).where(
        QaChunkVector.document_id == document_id,
        QaChunkVector.extraction_version == extraction_version,
    )).all()
    return {row.chunk_id: decode_vector(row.vector) for row in rows}


def index_for(db, document_id: str, extraction_version: str) -> QaIndex | None:
    return db.scalar(select(QaIndex).where(
        QaIndex.document_id == document_id,
        QaIndex.extraction_version == extraction_version,
    ))


def ready_index(db, document_id: str, extraction_version: str) -> QaIndex | None:
    row = index_for(db, document_id, extraction_version)
    return row if row is not None and row.status == "ready" else None


def index_state(db, document_id: str, extraction_version: str) -> str:
    """ready | building | failed | missing"""
    row = index_for(db, document_id, extraction_version)
    return row.status if row is not None else "missing"


_BUILDING: set[str] = set()


def _build_key(document_id: str, extraction_version: str) -> str:
    return f"{document_id}:{extraction_version}"


async def _acquire_slot(timeout: float = 120.0) -> bool:
    return await asyncio.to_thread(MODEL_SLOTS.acquire, True, timeout)


def trigger_index_build(document_id: str, owner_id: str, extraction_version: str) -> bool:
    """Schedule one background build per document version. Returns False without a loop."""
    key = _build_key(document_id, extraction_version)
    if key in _BUILDING:
        return False
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return False
    _BUILDING.add(key)

    async def runner():
        try:
            await build_index(document_id, owner_id, extraction_version)
        finally:
            _BUILDING.discard(key)

    loop.create_task(runner())
    return True


def _mark(db, row: QaIndex, status: str, error_code: str | None = None):
    row.status = status
    row.error_code = error_code
    row.updated_at = _now()
    db.commit()


async def build_index(document_id: str, owner_id: str, extraction_version: str) -> None:
    """Embed every chunk of one version, then atomically switch the active index."""
    from .database import SessionLocal

    db = SessionLocal()
    try:
        doc = db.scalar(select(Document).where(
            Document.id == document_id, Document.owner_id == owner_id,
            Document.deleted_at.is_(None)).execution_options(populate_existing=True))
        if doc is None or doc.extraction_version != extraction_version:
            return
        chunks = load_chunks(db, owner_id, document_id, extraction_version)
        if not chunks:
            row = index_for(db, document_id, extraction_version)
            if row is not None:
                _mark(db, row, "failed", "QA_INDEX_EMPTY")
            return
        row = index_for(db, document_id, extraction_version)
        if row is None:
            row = QaIndex(id=str(uuid.uuid4()), owner_id=owner_id, document_id=document_id,
                          extraction_version=extraction_version, embedding_model="", dimension=0,
                          status="building", chunk_count=0, is_active=False, created_at=_now(),
                          updated_at=_now())
            db.add(row)
            db.commit()
        settings = get_model_settings()
        profile = DeveloperProfileResolver(settings).resolve(owner_id, "embedding")
        if profile.model != row.embedding_model or settings.embedding_dim != row.dimension:
            row.embedding_model = profile.model
            row.dimension = settings.embedding_dim
        row.status = "building"
        row.error_code = None
        row.updated_at = _now()
        db.execute(delete(QaChunkVector).where(
            QaChunkVector.document_id == document_id,
            QaChunkVector.extraction_version == extraction_version))
        db.commit()

        model_service = ModelService()
        batch_size = get_model_settings().qa_index_batch
        vectors: list[tuple[Chunk, list[float]]] = []
        for start in range(0, len(chunks), batch_size):
            batch = chunks[start:start + batch_size]
            if not await _acquire_slot():
                raise ModelFailure("MODEL_BUSY", "向量服务并发已满，请稍后重试。", 429)
            try:
                embedded = await model_service.embed([chunk.text for chunk in batch], owner_id, profile)
            finally:
                MODEL_SLOTS.release()
            if any(len(vector) != settings.embedding_dim for vector in embedded):
                raise ModelFailure("MODEL_INVALID_RESPONSE", "向量维度与配置不一致，请检查模型设置。")
            vectors.extend(zip(batch, embedded))
            if len(batch) < batch_size:
                break

        now = _now()
        for chunk, vector in vectors:
            db.add(QaChunkVector(id=str(uuid.uuid4()), owner_id=owner_id, document_id=document_id,
                                 extraction_version=extraction_version, chunk_id=chunk.id,
                                 page_number=chunk.page_number, vector=encode_vector(vector),
                                 dimension=len(vector), created_at=now))
        db.flush()
        db.execute(update(QaIndex).where(
            QaIndex.document_id == document_id, QaIndex.id != row.id).values(is_active=False))
        row.status = "ready"
        row.chunk_count = len(vectors)
        row.is_active = True
        row.error_code = None
        row.built_at = now
        row.updated_at = now
        db.commit()
        logger.info("QA index ready document=%s version=%s chunks=%d", document_id, extraction_version, len(vectors))
    except ModelFailure as error:
        logger.warning("QA index build failed document=%s code=%s", document_id, error.code)
        db.rollback()
        _mark_failed(document_id, extraction_version, error.code)
    except Exception:
        logger.exception("QA index build failed document=%s", document_id)
        db.rollback()
        _mark_failed(document_id, extraction_version, "QA_INDEX_FAILED")
    finally:
        db.close()


def _mark_failed(document_id: str, extraction_version: str, error_code: str):
    from .database import SessionLocal
    with SessionLocal() as db:
        row = index_for(db, document_id, extraction_version)
        if row is not None and row.status != "ready":
            row.status = "failed"
            row.error_code = error_code
            row.updated_at = _now()
            db.commit()


STALE_BUILDING = timedelta(minutes=10)
FAILED_RETRY = timedelta(minutes=5)


def sweep_indexes(db, limit: int = 1) -> list[tuple[str, str, str]]:
    """Return at most `limit` documents needing a build; reset orphaned building rows."""
    now = _now()
    stale = db.scalars(select(QaIndex).where(
        QaIndex.status == "building", QaIndex.updated_at <= now - STALE_BUILDING)).all()
    for row in stale:
        row.status = "failed"
        row.error_code = "QA_INDEX_INTERRUPTED"
        row.updated_at = now
    if stale:
        db.commit()

    documents = db.scalars(select(Document).where(
        Document.deleted_at.is_(None),
        Document.parse_status == "completed",
        Document.extraction_version.is_not(None),
    ).order_by(Document.updated_at.desc())).all()
    pending: list[tuple[str, str, str]] = []
    for doc in documents:
        if len(pending) >= limit:
            break
        row = index_for(db, doc.id, doc.extraction_version)
        if row is not None:
            if row.status == "ready":
                continue
            if row.status == "building":
                continue
            if row.status == "failed" and row.updated_at > now - FAILED_RETRY:
                continue
        if db.scalar(select(DocumentChunk.id).where(
                DocumentChunk.document_id == doc.id,
                DocumentChunk.extraction_version == doc.extraction_version).limit(1)) is None:
            continue
        pending.append((doc.id, doc.owner_id, doc.extraction_version))
    return pending


def sweep_candidates(limit: int = 1) -> list[tuple[str, str, str]]:
    """Open a short session for the startup/periodic sweeper."""
    from .database import SessionLocal
    with SessionLocal() as db:
        return sweep_indexes(db, limit)
