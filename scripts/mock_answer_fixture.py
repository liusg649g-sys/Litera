"""Fixed synthetic QA records ONLY for explicitly isolated notes previews/tests.
No QA generator, persistence, external service or real model configuration.
"""
from datetime import datetime, timezone
from hashlib import sha256
from io import BytesIO
import os
from pathlib import Path
from uuid import UUID, uuid5
from reportlab.pdfgen.canvas import Canvas

QUOTE = 'This synthetic PDF exists only to test saving simulated AI answers to notes.'
QUESTION = '[MOCK] What is this synthetic document for?'
ANSWER = '[MOCK] It is an artificial fixture for notes-side integration tests, not a real AI answer.'


def synthetic_pdf():
    stream = BytesIO()
    canvas = Canvas(stream, pagesize=(612, 792), invariant=1)
    canvas.setFont('Helvetica', 12)
    canvas.drawString(40, 740, 'LITERA ISOLATED MOCK QA FIXTURE - NOT A REAL PAPER')
    canvas.drawString(40, 700, 'This synthetic PDF exists only to test saving')
    canvas.drawString(40, 680, 'simulated AI answers to notes.')
    canvas.showPage()
    canvas.save()
    return stream.getvalue()


PDF_BYTES = synthetic_pdf()
PDF_HASH = sha256(PDF_BYTES).hexdigest()
NAMESPACE = UUID('942c442c-d30c-4c17-b162-cd449790abc1')


def answer_id(owner, document, variant):
    return str(uuid5(NAMESPACE, owner + ':' + document + ':' + variant))


class FixedMockAnswers:
    available = True
    isolated_mock = True

    def __init__(self):
        # Fixed records are derived from existing authorized synthetic uploads;
        # no per-answer DB/table or browser-supplied question/citations exist.
        pass

    def records(self, db, owner, document_id):
        from app.documents import owned_document
        from app.answer_sources import ResolvedAnswer, AnswerCitation
        doc, file = owned_document(db, owner, document_id)
        if file.sha256 != PDF_HASH:
            return []
        base = dict(ownerId=owner, answerRevision=1, documentId=doc.id, fileSha256=PDF_HASH,
            question=QUESTION, answer=ANSWER, mode='question', status='answered', contextRevision=1,
            createdAt=datetime(2026,10,26,tzinfo=timezone.utc), provenance='isolated_mock')
        citation = AnswerCitation(citationId='MOCK-CITATION-1', documentId=doc.id,
            fileSha256=PDF_HASH, extractionVersion='isolated-mock-v1', chunkId='MOCK-CHUNK-1',
            pageNumber=1, quote=QUOTE)
        return [ResolvedAnswer(**base, answerId=answer_id(owner, doc.id, 'cited'),
            evidenceState='verified', extractionVersion='isolated-mock-v1', citations=[citation]),
            ResolvedAnswer(**dict(base, status='insufficient_evidence', question='[MOCK] Uncited test question',
                answer='[MOCK] Unverified synthetic answer. No reliable PDF citation is claimed.'),
                answerId=answer_id(owner, doc.id, 'uncited'), evidenceState='none', citations=[])]

    def resolve(self, db, owner, identifier, revision):
        from sqlalchemy import select
        from app.models import Document, DocumentFile
        from app.answer_sources import AnswerResolutionError
        # Only known fixture hashes; no private PDF text is inspected here.
        ids = db.scalars(select(Document.id).join(DocumentFile, DocumentFile.document_id==Document.id)
                         .where(Document.owner_id==owner, Document.deleted_at.is_(None), DocumentFile.sha256==PDF_HASH)).all()
        for document in ids:
            for record in self.records(db, owner, document):
                if record.answerId == identifier:
                    if revision != record.answerRevision: raise AnswerResolutionError('stale')
                    return record
        raise AnswerResolutionError('not_found')

    def verify_citation(self, db, owner, answer, citation):
        return citation.model_dump() == self.records(db, owner, answer.documentId)[0].citations[0].model_dump()


def enable_mock_answers():
    from fastapi import Depends, Response
    from sqlalchemy.orm import Session
    from sqlalchemy.engine import make_url
    from app.config import get_settings
    from app.answer_sources import get_answer_resolver
    from app.database import get_db
    from app.main import app, current_session
    from app.note_captures import answer_snapshot
    settings = get_settings()
    url = make_url(settings.database_url)
    unified = settings.unified_acceptance and settings.app_env == 'development'
    if (settings.app_env != 'test' and not unified) or url.get_backend_name() != 'sqlite':
        raise RuntimeError('Mock answers require explicit isolated SQLite test environment')
    data = Path(url.database).resolve().parent
    root = Path(__file__).resolve().parents[1]
    permitted_unified = unified and data == root/'.cache'/'user-model-preview'/'unified'
    if not (permitted_unified or data == root/'.cache'/'notes-preview' or data.name.startswith(('litera-note-captures-', 'litera-unified-'))):
        raise RuntimeError('Mock answer path is not an approved isolated environment')
    if settings.pdf_storage_root.resolve() != data/'pdfs' or any(os.environ.get(k) for k in ('AI_API_KEY','AI_BASE_URL','AI_MODEL')):
        raise RuntimeError('Mock answers must not use model settings or other PDF storage')
    resolver = FixedMockAnswers()
    app.dependency_overrides[get_answer_resolver] = lambda: resolver

    # Registered only by the isolated scripts, absent from normal app routes.
    @app.get('/api/v1/notes/mock-answers/fixture.pdf')
    def fixture(session=Depends(current_session)):
        return Response(PDF_BYTES, media_type='application/pdf', headers={
            'Content-Disposition':'attachment; filename="Litera-MOCK-QA-synthetic.pdf"'})

    @app.get('/api/v1/notes/mock-answers/list')
    def listing(documentId: str, session=Depends(current_session), db: Session=Depends(get_db)):
        from app.documents import owned_document
        doc, _ = owned_document(db, session.user_id, documentId)
        return [answer_snapshot(record, doc) for record in resolver.records(db, session.user_id, doc.id)]
