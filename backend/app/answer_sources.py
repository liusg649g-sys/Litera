"""Notes-owned adapter boundary; does not generate or persist QA answers.

D1 fields are provisional until the QA owner confirms them. Production defaults
unavailable; only explicitly isolated fixtures inject a fixed-record resolver.
"""
from datetime import datetime, timezone
from typing import Literal, Protocol
from uuid import UUID
from pydantic import Field, field_validator, model_validator
from sqlalchemy.orm import Session
from .schemas import InputModel
from .documents import reject


class AiAnswerSource(InputModel):
    kind: Literal['ai_answer']
    answerId: str
    answerRevision: int = Field(ge=1, strict=True)
    historical: bool = Field(default=False, strict=True)
    confirmHistorical: bool = Field(default=False, strict=True)
    confirmUncited: bool = Field(default=False, strict=True)

    @field_validator('answerId')
    @classmethod
    def identifier(cls, value):
        return str(UUID(value))

    @model_validator(mode='after')
    def history(self):
        if self.historical != self.confirmHistorical:
            raise ValueError('Historical answer requires explicit confirmation')
        return self


class AnswerCitation(InputModel):
    citationId: str = Field(min_length=1, max_length=100)
    documentId: str = Field(min_length=1, max_length=36)
    fileSha256: str = Field(pattern=r'^[a-f0-9]{64}$')
    extractionVersion: str = Field(min_length=1, max_length=100)
    chunkId: str = Field(min_length=1, max_length=100)
    pageNumber: int = Field(ge=1, strict=True)
    quote: str = Field(min_length=1, max_length=6000)


class ResolvedAnswer(InputModel):
    schemaVersion: Literal[1] = 1
    ownerId: str
    answerId: str
    answerRevision: int = Field(ge=1, strict=True)
    documentId: str
    fileSha256: str = Field(pattern=r'^[a-f0-9]{64}$')
    mode: Literal['question', 'summary', 'analysis'] = 'question'
    question: str = Field(max_length=6000)
    answer: str = Field(min_length=1, max_length=20000)
    status: Literal['answered', 'insufficient_evidence']
    contextRevision: int = Field(ge=0, strict=True)
    createdAt: datetime
    expiresAt: datetime | None = None
    extractionVersion: str | None = Field(default=None, max_length=100)
    provenance: Literal['model_api', 'isolated_mock']
    evidenceState: Literal['verified', 'none']
    citations: list[AnswerCitation] = Field(max_length=20)


class AnswerResolutionError(Exception):
    """Finite public error code; adapter exception messages are never returned."""
    def __init__(self, code):
        self.code = code


class AnswerResolver(Protocol):
    """Must authorize owner, reject obsolete revisions, and bind immutable evidence.

    verify_citation MUST resolve the versioned evidence/chunk in a trusted QA
    source. Merely matching text somewhere in a PDF is not a QA evidence binding.
    Notes independently verifies PDF identity, page and quotation afterwards.
    """
    available: bool
    isolated_mock: bool

    def resolve(self, db: Session, owner: str, answer_id: str, revision: int) -> ResolvedAnswer: ...
    def verify_citation(self, db: Session, owner: str, answer: ResolvedAnswer, citation: AnswerCitation) -> bool: ...


class UnavailableAnswerResolver:
    available = False
    isolated_mock = False

    def resolve(self, db, owner, answer_id, revision):
        reject(503, 'AI_ANSWER_UNAVAILABLE', 'AI回答来源服务尚未接入，未保存。')

    def verify_citation(self, *args):
        return False


_DEFAULT = UnavailableAnswerResolver()


def get_answer_resolver() -> AnswerResolver:
    return _DEFAULT


def read_answer(resolver, db, owner, source):
    if not resolver.available:
        reject(503, 'AI_ANSWER_UNAVAILABLE', 'AI回答来源服务尚未接入，未保存。')
    try:
        record = resolver.resolve(db, owner, source.answerId, source.answerRevision)
        record = ResolvedAnswer.model_validate(record.model_dump() if isinstance(record, ResolvedAnswer) else record)
    except AnswerResolutionError as error:
        errors = {
            'not_found': (404, 'AI_ANSWER_NOT_FOUND', '回答不存在或不可访问。'),
            'stale': (409, 'AI_ANSWER_STALE', '回答版本已变化，请重新选择后保存。'),
            'expired': (409, 'AI_ANSWER_EXPIRED', '回答已过期，请重新取得有效回答。'),
        }
        status, code, message = errors.get(error.code, (503, 'AI_ANSWER_UNAVAILABLE', 'AI回答来源服务暂不可用，未保存。'))
        reject(status, code, message)
    except Exception:
        reject(503, 'AI_ANSWER_UNAVAILABLE', 'AI回答来源服务暂不可用，未保存。请稍后重试。')
    if record.ownerId != owner:
        reject(404, 'AI_ANSWER_NOT_FOUND', '回答不存在或不可访问。')
    if record.answerId != source.answerId or record.answerRevision != source.answerRevision:
        reject(409, 'AI_ANSWER_STALE', '回答版本已变化，请重新选择后保存。')
    expiry = record.expiresAt
    if expiry and expiry.replace(tzinfo=expiry.tzinfo or timezone.utc) <= datetime.now(timezone.utc):
        reject(409, 'AI_ANSWER_EXPIRED', '回答已过期，请重新取得有效回答。')
    if not record.answer.strip() or (record.provenance == 'isolated_mock' and not resolver.isolated_mock):
        reject(422, 'AI_ANSWER_INVALID', '回答来源无效，未保存。')
    citations = record.citations
    if record.evidenceState == 'verified':
        if record.status != 'answered' or not citations or not record.extractionVersion:
            reject(422, 'AI_EVIDENCE_INVALID', '回答引用不完整，未保存。')
        if len({c.citationId for c in citations}) != len(citations):
            reject(422, 'AI_EVIDENCE_INVALID', '回答引用标识重复，未保存。')
    elif citations:
        reject(422, 'AI_EVIDENCE_INVALID', '未核实回答不能携带可信引用，未保存。')
    return record
