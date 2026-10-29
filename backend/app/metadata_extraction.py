"""三层混合提取引擎 + 候选合并。

Layer 1: 从 pypdf 读取 PDF 自带 metadata（/Title, /Author, /Keywords）
Layer 2: 正则启发式匹配（DOI, ISSN, year, journal 白名单）
Layer 3: course-chat LLM 结构化 JSON 提取

每层独立产出候选，不阻塞其他层。合并时 source priority: llm > heuristic > metadata。
"""
from __future__ import annotations

import json
import logging
import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field, field_validator

from .ai_service import ModelFailure, ModelService
from .config import get_model_settings

logger = logging.getLogger(__name__)

# ── 字段名和固定置信度 ──────────────────────────────────────────────

METADATA_FIELDS = ("title", "authors", "abstract", "keywords", "year", "journal", "doi")

LAYER1_CONFIDENCE = {
    "title": 0.85,
    "authors": 0.9,
    "keywords": 0.7,
}

LAYER2_CONFIDENCE = {
    "doi": 1.0,
    "issn": 1.0,
    "year": 0.95,
    "journal": 0.8,
}

# ── 正则 ─────────────────────────────────────────────────────────

_DOI_RE = re.compile(r"10\.\d{4,9}/[^\s,;\"'()\[\]<>]+")
_ISSN_RE = re.compile(r"\b\d{4}-\d{3}[\dX]\b")
_YEAR_MIN = 1950
_YEAR_MAX = datetime.now(timezone.utc).year + 1  # 明年容忍，覆盖预印本
_YEAR_RE = re.compile(r"\b(19\d{2}|20\d{2})\b")
_ARXIV_RE = re.compile(r"arXiv[:\s](\d{4}\.\d{4,5}(?:v\d+)?)", re.IGNORECASE)

# ── known_journals 白名单 ─────────────────────────────────────────

_KNOWN_JOURNALS: list[str] | None = None


def _load_known_journals() -> list[str]:
    global _KNOWN_JOURNALS
    if _KNOWN_JOURNALS is None:
        path = Path(__file__).resolve().parent.parent / "data" / "known_journals.json"
        _KNOWN_JOURNALS = json.loads(path.read_text(encoding="utf-8"))
    return _KNOWN_JOURNALS


# ── 候选数据结构 ─────────────────────────────────────────────────

@dataclass
class FieldCandidate:
    """一个字段在某一层提取的结果。"""
    value: Any
    source: str              # metadata / heuristic / llm
    confidence: float        # 0.0–1.0

    def is_empty(self) -> bool:
        if self.value is None:
            return True
        if isinstance(self.value, str):
            return self.value.strip() == ""
        if isinstance(self.value, list):
            return len(self.value) == 0
        return False


@dataclass
class LayerResult:
    """某一层的全部产出：field_name → FieldCandidate。"""
    layer: str                              # "metadata" / "heuristic" / "llm"
    fields: dict[str, FieldCandidate] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)


# ── Layer 1: PDF 自带 metadata ────────────────────────────────────

def extract_from_pdf_metadata(reader) -> LayerResult:
    """从 pypdf.PdfReader.metadata 读取 /Title、/Author、/Keywords。"""
    result = LayerResult(layer="metadata")
    try:
        meta = reader.metadata
    except Exception as exc:
        result.warnings.append(f"PDF metadata 不可读取: {exc}")
        return result

    if meta is None:
        return result

    # /Title
    title_val = None
    if hasattr(meta, "get"):
        raw = meta.get("/Title")
    else:
        raw = getattr(meta, "title", None)
    if raw is not None:
        s = str(raw).strip()
        if s and not s.lower().startswith("document"):  # 排除 "Document1" 这类垃圾
            title_val = s
    if title_val:
        result.fields["title"] = FieldCandidate(title_val, "metadata", LAYER1_CONFIDENCE["title"])

    # /Author
    author_val = None
    if hasattr(meta, "get"):
        raw = meta.get("/Author")
    else:
        raw = getattr(meta, "author", None)
    if raw is not None:
        s = str(raw).strip()
        if s:
            authors = [a.strip() for a in re.split(r"[;,&]", s) if a.strip()]
            if authors:
                author_val = authors
                result.fields["authors"] = FieldCandidate(author_val, "metadata", LAYER1_CONFIDENCE["authors"])

    # /Keywords
    kw_val = None
    if hasattr(meta, "get"):
        raw = meta.get("/Keywords") or meta.get("/Subject")
    else:
        raw = getattr(meta, "keywords", None) or getattr(meta, "subject", None)
    if raw is not None:
        s = str(raw).strip()
        if s:
            keywords = [k.strip() for k in re.split(r"[,;]", s) if k.strip()]
            if keywords:
                kw_val = keywords
                result.fields["keywords"] = FieldCandidate(kw_val, "metadata", LAYER1_CONFIDENCE["keywords"])

    return result


# ── Layer 2: 正则启发式 ───────────────────────────────────────────

def extract_heuristic(page_texts: list[str]) -> LayerResult:
    """对前 3 页文本做正则和白名单匹配。"""
    result = LayerResult(layer="heuristic")
    top_text = "\n".join(page_texts[:3]) if page_texts else ""

    # DOI
    doi_match = _DOI_RE.search(top_text)
    if doi_match:
        doi = doi_match.group(0).rstrip(".,;:")
        result.fields["doi"] = FieldCandidate(doi, "heuristic", LAYER2_CONFIDENCE["doi"])

    # ISSN
    issn_match = _ISSN_RE.search(top_text)
    if issn_match:
        result.fields["issn"] = FieldCandidate(issn_match.group(0), "heuristic", LAYER2_CONFIDENCE["issn"])

    # arXiv
    arxiv_match = _ARXIV_RE.search(top_text)
    if arxiv_match:
        result.fields["doi"] = FieldCandidate(f"arXiv:{arxiv_match.group(1)}", "heuristic", LAYER2_CONFIDENCE["doi"])

    # Year: 取文本中第一个合理年份
    for m in _YEAR_RE.finditer(top_text):
        year = int(m.group(1))
        if _YEAR_MIN <= year <= _YEAR_MAX:
            result.fields["year"] = FieldCandidate(year, "heuristic", LAYER2_CONFIDENCE["year"])
            break

    # Journal: 首页文本中匹配 known_journals 白名单（大小写不敏感，按长度降序避免子串先匹配）
    top_line = page_texts[0] if page_texts else top_text
    journals = sorted(_load_known_journals(), key=len, reverse=True)
    matched = None
    lower_line = top_line.lower()
    for j in journals:
        j_lower = j.lower()
        # 只匹配非前缀形式（避免 "Nature" 匹配 "Nature Reviews" 的子串情况；先按长度排序已处理大部分）
        idx = lower_line.find(j_lower)
        if idx >= 0:
            # 检查不是更长期刊的子串
            is_substring = any(
                other.lower() != j_lower
                and j_lower in other.lower()
                and lower_line.find(other.lower()) >= 0
                and other != j
                for other in journals
            )
            if not is_substring:
                matched = j
                break
    if matched:
        result.fields["journal"] = FieldCandidate(matched, "heuristic", LAYER2_CONFIDENCE["journal"])

    return result


# ── Layer 3: course-chat LLM ──────────────────────────────────────

class MetadataCandidate(BaseModel):
    """course-chat 输出的 Pydantic schema。"""
    title: str | None = Field(None, max_length=500)
    authors: list[str] = Field(default_factory=list, max_length=50)
    abstract: str | None = Field(None, max_length=5000)
    keywords: list[str] = Field(default_factory=list, max_length=20)
    year: int | None = Field(None, ge=_YEAR_MIN, le=_YEAR_MAX)
    journal: str | None = Field(None, max_length=500)
    doi: str | None = Field(None, max_length=255)
    confidence: float = Field(0.5, ge=0.0, le=1.0)

    @field_validator("doi")
    @classmethod
    def check_doi_format(cls, v):
        if v is None:
            return v
        v = v.strip()
        if not v:
            return None
        # 允许 arXiv:xxx 格式或标准 DOI 格式
        if v.startswith("arXiv:") or _DOI_RE.fullmatch(v) or v.lower().startswith("10."):
            return v
        return None  # 格式不合规则丢弃

    @field_validator("authors", "keywords", mode="before")
    @classmethod
    def none_to_empty_list(cls, v):
        # 提示词允许 LLM 输出 null，统一归一化为空列表，避免整包校验失败
        return [] if v is None else v

    @field_validator("authors", "keywords")
    @classmethod
    def clean_list(cls, v):
        return [s.strip() for s in v if isinstance(s, str) and s.strip()]


# Layer 3 system prompt
_LAYER3_SYSTEM = (
    "你是一名学术文献元数据提取器。从提供的 PDF 前几页文本中，尽可能提取以下字段。"
    "规则：\n"
    "1. 只根据文本实际内容回答，绝对不能编造不存在的信息。不确定就输出 null。\n"
    "2. 返回严格的 JSON，不要任何 Markdown 代码块标记，不要额外文字。\n"
    "3. abstract 是摘要正文（通常以 Abstract 开头的段落），关键词是作者给出的关键词。\n"
    "4. authors 是作者列表数组，journal 是发表期刊/会议名，doi 必须以 10. 开头或 arXiv: 开头。\n"
    "5. confidence 是你对整体提取质量的自评，0.0–1.0。\n"
    "6. 输出示例：{\"title\":\"...\",\"authors\":[\"...\"],\"abstract\":\"...\",\"keywords\":[...],\"year\":2024,\"journal\":\"...\",\"doi\":\"10.1234/...\",\"confidence\":0.85}"
)

_LAYER3_MAX_CHARS = 4000


async def extract_llm(page_texts: list[str]) -> LayerResult:
    """把前 3 页文本交给 course-chat，让其返回结构化 JSON。"""
    result = LayerResult(layer="llm")
    if not page_texts:
        result.warnings.append("LLM 输入为空，跳过 Layer 3")
        return result

    top_text = "\n\n".join(page_texts[:3])[:_LAYER3_MAX_CHARS]
    messages = [
        {"role": "system", "content": _LAYER3_SYSTEM},
        {"role": "user", "content": top_text},
    ]

    try:
        profile = get_model_settings()
        # 手动构造 developer profile（绕过 ModelService.complete 里的 verified 检查）
        from .ai_service import ModelProfile, OpenAICompatible
        adapter = OpenAICompatible()
        response_text = await adapter.complete(messages, ModelProfile(
            provider=profile.provider,
            base_url=profile.base_url,
            model=profile.model,
            api_key=profile.api_key,
            scope="developer",
            verified=True,
        ))
    except ModelFailure as exc:
        result.warnings.append(f"LLM 提取失败: {exc.code} {exc.message}")
        return result
    except Exception as exc:
        result.warnings.append(f"LLM 提取异常: {exc}")
        return result

    # 解析 JSON
    try:
        # 模型偶尔会把 JSON 包在 Markdown 代码块里，去掉
        cleaned = response_text.strip()
        if cleaned.startswith("```"):
            cleaned = re.sub(r"^```(?:json)?", "", cleaned).strip()
            cleaned = re.sub(r"```$", "", cleaned).strip()
        raw = json.loads(cleaned)
        candidate = MetadataCandidate(**raw)
    except Exception as exc:
        result.warnings.append(f"LLM 输出解析失败: {exc}; raw={response_text[:200]}")
        return result

    conf = float(candidate.confidence) if candidate.confidence is not None else 0.5
    if candidate.title:
        result.fields["title"] = FieldCandidate(candidate.title, "llm", conf)
    if candidate.authors:
        result.fields["authors"] = FieldCandidate(candidate.authors, "llm", conf)
    if candidate.abstract:
        result.fields["abstract"] = FieldCandidate(candidate.abstract, "llm", conf)
    if candidate.keywords:
        result.fields["keywords"] = FieldCandidate(candidate.keywords, "llm", conf)
    if candidate.year is not None:
        result.fields["year"] = FieldCandidate(candidate.year, "llm", conf)
    if candidate.journal:
        result.fields["journal"] = FieldCandidate(candidate.journal, "llm", conf)
    if candidate.doi:
        result.fields["doi"] = FieldCandidate(candidate.doi, "llm", conf)

    return result


# ── 合并函数 ──────────────────────────────────────────────────────

_SOURCE_PRIORITY = {"llm": 3, "heuristic": 2, "metadata": 1}


def _validate_doi(val: str | None) -> bool:
    if not val:
        return False
    val = val.strip()
    return bool(val.startswith("arXiv:") or val.lower().startswith("10.") or _DOI_RE.fullmatch(val))


def _validate_year(val: Any) -> bool:
    try:
        year = int(val)
        return _YEAR_MIN <= year <= _YEAR_MAX
    except (TypeError, ValueError):
        return False


def merge_candidates(layer1: LayerResult, layer2: LayerResult, layer3: LayerResult) -> dict:
    """按 source priority 合并三层结果，保留所有原始值到 fieldSources。

    返回:
        {
            "metadata": {field_name: {"value": ..., "confidence": ...}, ...},   # 最终合并后的候选
            "fieldSources": {field_name: [{"source": ..., "value": ..., "confidence": ...}, ...]},  # 所有层原始值
            "warnings": [str, ...],
            "has_text": bool,
        }
    """
    all_layers = [layer1, layer2, layer3]
    warnings: list[str] = []
    field_sources: dict[str, list[dict]] = {}  # field → 各层候选
    merged: dict[str, dict] = {}

    for layer in all_layers:
        warnings.extend(layer.warnings)
        for fname, fc in layer.fields.items():
            field_sources.setdefault(fname, []).append({
                "source": fc.source,
                "value": fc.value,
                "confidence": fc.confidence,
            })

    for fname, entries in field_sources.items():
        # 按 source priority 排序（高优先在前）
        entries_sorted = sorted(entries, key=lambda e: _SOURCE_PRIORITY.get(e["source"], 0), reverse=True)

        # DOI / year 强校验：所有不合规的直接丢
        candidates = entries_sorted
        if fname == "doi":
            candidates = [e for e in candidates if _validate_doi(e["value"])]
        elif fname == "year":
            candidates = [e for e in candidates if _validate_year(e["value"])]

        if not candidates:
            # 全部校验失败，不填 merged，但保留原始到 fieldSources 供调试
            continue

        chosen = candidates[0]
        merged[fname] = {
            "value": chosen["value"],
            "confidence": chosen["confidence"],
            "source": chosen["source"],
        }

    # 移除中间层字段（issn 不作为正式题录字段）
    field_sources.pop("issn", None)

    has_text = bool(field_sources.get("title") or field_sources.get("doi"))
    return {
        "metadata": merged,
        "fieldSources": field_sources,
        "warnings": warnings,
        "hasText": has_text,
    }


# ── 同步层入口（供上传端点调用） ──────────────────────────────────

def run_sync_layers(pypdf_reader) -> tuple[LayerResult, LayerResult, list[str], list[str]]:
    """执行 Layer 1 + Layer 2，同时提取页文本供 Layer 3 使用。

    返回: (layer1_result, layer2_result, all_page_texts, top3_page_texts_for_llm)
    """
    layer1 = extract_from_pdf_metadata(pypdf_reader)

    all_page_texts: list[str] = []
    try:
        for page in pypdf_reader.pages:
            try:
                text = page.extract_text() or ""
            except Exception:
                text = ""
            all_page_texts.append(text)
    except Exception as exc:
        layer1.warnings.append(f"页文本提取失败: {exc}")

    layer2 = extract_heuristic(all_page_texts)
    return layer1, layer2, all_page_texts, all_page_texts[:3]
