"""Private plain-text notes with independent identities and reusable document links.
No schema creation, HTML execution or model calls occur here.
"""
import re
from datetime import datetime, timezone
from uuid import UUID
from fastapi import APIRouter, Body, Depends, Query, Request, Response
from pydantic import Field, field_validator, model_validator
from sqlalchemy import delete, func, inspect, select, update
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session
from .database import get_db
from .documents import iso, owned_document, reject
from .models import Document, LoginSession, Note, NoteDocument
from .schemas import InputModel

TITLE_LIMIT = 200
CONTENT_LIMIT = 100000
SEARCH_QUERY_LIMIT = 100
SEARCH_PAGE_SIZE_LIMIT = 50
SEARCH_MATCH_LIMIT = 6
SEARCH_SNIPPET_LIMIT = 160
_REQUIRED = {
    "notes": {"id","owner_id","title","content","content_format","version","source_schema_version","sources","created_at","updated_at"},
    "note_documents": {"note_id","document_id","owner_id","created_at"},
}


def now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def schema_available(db):
    # Only inspect: a partial/absent migration is never repaired by an API call.
    try:
        inspector = inspect(db.connection())
        return all(inspector.has_table(name) and columns <= {c['name'] for c in inspector.get_columns(name)}
                   for name, columns in _REQUIRED.items())
    except SQLAlchemyError:
        return False


def ready(db):
    if not schema_available(db):
        reject(503, "NOTES_NOT_READY", "笔记尚未部署：需要经确认后完成增量迁移，当前数据未被重置。")


class NoteCreate(InputModel):
    id: str = Field(min_length=36, max_length=36)
    title: str = Field(min_length=1, max_length=TITLE_LIMIT)
    content: str = Field(max_length=CONTENT_LIMIT)
    documentId: str | None = Field(default=None, min_length=1, max_length=36)

    @field_validator('id')
    @classmethod
    def valid_id(cls, value):
        return str(UUID(value))

    @field_validator('title')
    @classmethod
    def valid_title(cls, value):
        value = value.strip()
        if not value: raise ValueError('Title cannot be empty')
        return value


class NotePatch(InputModel):
    version: int = Field(ge=1, strict=True)
    title: str | None = Field(default=None, min_length=1, max_length=TITLE_LIMIT)
    content: str | None = Field(default=None, max_length=CONTENT_LIMIT)

    @field_validator('title')
    @classmethod
    def valid_title(cls, value):
        if value is None or not value.strip(): raise ValueError('Title cannot be empty')
        return value.strip()

    @field_validator('content')
    @classmethod
    def valid_content(cls, value):
        if value is None: raise ValueError('Content cannot be null')
        return value

    @model_validator(mode='after')
    def changed_fields(self):
        if not ({'title','content'} & self.model_fields_set): raise ValueError('No editable fields')
        return self


class EmptyInput(InputModel):
    pass


def owned_note(db, owner, id, lock=False):
    query = select(Note).where(Note.id == id, Note.owner_id == owner)
    if lock: query = query.with_for_update().execution_options(populate_existing=True)
    item = db.scalar(query)
    if item is None: reject(404, "NOTE_NOT_FOUND", "笔记不存在或不可访问")
    return item


def dto(db, item, detail=False):
    documents = db.execute(select(Document.id, Document.title).join(NoteDocument, NoteDocument.document_id == Document.id)
        .where(NoteDocument.note_id == item.id, NoteDocument.owner_id == item.owner_id,
               Document.owner_id == item.owner_id, Document.deleted_at.is_(None), Document.purge_job_id.is_(None))
        .order_by(Document.title, Document.id)).all()
    result = {"id":item.id,"title":item.title,"contentFormat":item.content_format,"version":item.version,
              "sourceSchemaVersion":item.source_schema_version,"createdAt":iso(item.created_at),"updatedAt":iso(item.updated_at),
              "documents":[{"id":row.id,"title":row.title} for row in documents]}
    if detail: result.update(content=item.content,sources=item.sources)
    return result


def _search_match(text, pattern, field, label, **source):
    if not isinstance(text, str):
        return None
    match = pattern.search(text)
    if match is None:
        return None
    context = max(0, (SEARCH_SNIPPET_LIMIT - (match.end() - match.start())) // 2)
    start = max(0, match.start() - context)
    end = min(len(text), max(match.end() + context, start + SEARCH_SNIPPET_LIMIT))
    if end - start > SEARCH_SNIPPET_LIMIT:
        end = start + SEARCH_SNIPPET_LIMIT
    snippet = text[start:end]
    result = {
        "field": field,
        "label": label,
        "snippet": snippet,
        "matchStart": match.start() - start,
        "matchEnd": match.end() - start,
        "leadingEllipsis": start > 0,
        "trailingEllipsis": end < len(text),
    }
    result.update({key: value for key, value in source.items() if value is not None})
    return result


def _search_note(item, pattern):
    matches = []

    def add(text, field, label, **source):
        if len(matches) >= SEARCH_MATCH_LIMIT:
            return
        match = _search_match(text, pattern, field, label, **source)
        if match is not None:
            matches.append(match)

    add(item.title, "title", "标题")
    add(item.content, "content", "正文")
    if isinstance(item.sources, list):
        for block in item.sources:
            if len(matches) >= SEARCH_MATCH_LIMIT:
                break
            if not isinstance(block, dict):
                continue
            if block.get('kind') == 'ai_answer':
                context = block.get('contextDocument', {})
                metadata = dict(sourceBlockId=block.get('id'), documentId=context.get('documentId'))
                add(block.get('question'), 'ai_question', 'AI问题', **metadata)
                add(block.get('answer'), 'ai_answer', 'AI回答', **metadata)
                for citation in block.get('citations', []):
                    if isinstance(citation, dict):
                        add(citation.get('quote'), 'source_original', 'AI引用原文', sourceBlockId=block.get('id'),
                            documentId=citation.get('documentId'), pageNumber=citation.get('pageNumber'))
                continue
            source = block.get("source") if isinstance(block.get("source"), dict) else {}
            metadata = {
                "sourceBlockId": block.get("id") if isinstance(block.get("id"), str) else None,
                "documentId": source.get("documentId") if isinstance(source.get("documentId"), str) else None,
                "pageNumber": source.get("pageNumber") if type(source.get("pageNumber")) is int else None,
            }
            add(block.get("originalText"), "source_original", "PDF 原文摘录", **metadata)
            add(block.get("translatedText"), "source_translation", "译文", **metadata)
    if not matches:
        return None
    return matches


def create_note_router(current_session, require_csrf):
    router = APIRouter(prefix='/api/v1/notes', tags=['notes'])

    @router.get('/config')
    def config(session: LoginSession = Depends(current_session), db: Session = Depends(get_db)):
        return {"available":schema_available(db),"contentMaxLength":CONTENT_LIMIT,"titleMaxLength":TITLE_LIMIT,"contentFormat":"plain-text"}

    # Register static paths before /{id}; captures reuse the existing JSON column.
    from .note_captures import add_capture_routes
    add_capture_routes(router, current_session, require_csrf)

    @router.get('/search')
    def searching(request: Request, q: str = Query(default="", max_length=SEARCH_QUERY_LIMIT),
                  page: int = Query(1, ge=1), pageSize: int = Query(20, ge=1, le=SEARCH_PAGE_SIZE_LIMIT),
                  session: LoginSession = Depends(current_session), db: Session = Depends(get_db)):
        ready(db)
        allowed = {'q', 'page', 'pageSize'}
        if set(request.query_params) - allowed or any(len(request.query_params.getlist(key)) != 1 for key in request.query_params):
            reject(422, "INVALID_QUERY", "不支持或重复的笔记搜索参数")
        query = q.strip()
        if not query:
            return {"items": [], "query": "", "page": page, "pageSize": pageSize, "total": 0}
        pattern = re.compile(re.escape(query), re.IGNORECASE)
        notes = db.scalars(select(Note).where(Note.owner_id == session.user_id)
                           .order_by(Note.updated_at.desc(), Note.id)).all()
        results = [(item, matches) for item in notes if (matches := _search_note(item, pattern)) is not None]
        start = (page - 1) * pageSize
        items = [{**dto(db, item), "matches": matches} for item, matches in results[start:start + pageSize]]
        return {"items": items, "query": query, "page": page,
                "pageSize": pageSize, "total": len(results)}

    @router.get('')
    def listing(request: Request, documentId: str | None = None, title: str | None = Query(default=None, min_length=1, max_length=TITLE_LIMIT), page: int = Query(1,ge=1), pageSize: int = Query(20,ge=1,le=100),
                session: LoginSession = Depends(current_session), db: Session = Depends(get_db)):
        ready(db)
        allowed={'documentId','page','pageSize','title'}
        if set(request.query_params)-allowed or any(len(request.query_params.getlist(k))!=1 for k in request.query_params):
            reject(422,"INVALID_QUERY","不支持或重复的笔记查询参数")
        query=select(Note).where(Note.owner_id==session.user_id)
        if documentId:
            owned_document(db,session.user_id,documentId)
            linked=select(NoteDocument.note_id).where(NoteDocument.owner_id==session.user_id,NoteDocument.document_id==documentId)
            query=query.where(Note.id.in_(linked))
        if title is not None:
            if not title.strip(): reject(422,'INVALID_QUERY','标题筛选不能为空')
            query=query.where(func.lower(Note.title).contains(title.strip().lower(),autoescape=True))
        total=db.scalar(select(func.count()).select_from(query.subquery()))
        rows=db.scalars(query.order_by(Note.updated_at.desc(),Note.id).offset((page-1)*pageSize).limit(pageSize)).all()
        return {"items":[dto(db,item) for item in rows],"page":page,"pageSize":pageSize,"total":total}

    @router.get('/{id}')
    def details(id: str, session: LoginSession = Depends(current_session), db: Session = Depends(get_db)):
        ready(db);return dto(db,owned_note(db,session.user_id,id),True)

    @router.post('',status_code=201)
    def creating(payload: NoteCreate, response: Response, session: LoginSession = Depends(require_csrf), db: Session = Depends(get_db)):
        ready(db)
        if payload.documentId: owned_document(db,session.user_id,payload.documentId,lock=True)
        def replay(item):
            if item.owner_id != session.user_id: reject(404,"NOTE_NOT_FOUND","笔记不存在或不可访问")
            linked=not payload.documentId or db.get(NoteDocument,(item.id,payload.documentId)) is not None
            if item.version!=1 or item.title!=payload.title or item.content!=payload.content or not linked:
                reject(409,"NOTE_CREATE_CONFLICT","该笔记已存在且内容或关联发生变化，请重新读取。")
            response.status_code=200;return dto(db,item,True)
        item=db.get(Note,payload.id)
        if item is not None:return replay(item)
        timestamp=now()
        item=Note(id=payload.id,owner_id=session.user_id,title=payload.title,content=payload.content,content_format='plain-text',
                  version=1,source_schema_version=1,sources=[],created_at=timestamp,updated_at=timestamp)
        db.add(item)
        try:
            db.flush()
            if payload.documentId:
                db.add(NoteDocument(note_id=item.id,document_id=payload.documentId,owner_id=session.user_id,created_at=timestamp))
            db.commit();db.refresh(item)
        except IntegrityError:
            db.rollback();existing=db.get(Note,payload.id)
            if existing is not None:return replay(existing)
            reject(409,"NOTE_CREATE_CONFLICT","笔记创建状态发生变化，请重试或重新读取。")
        return dto(db,item,True)

    @router.patch('/{id}')
    def editing(id: str, payload: NotePatch, session: LoginSession = Depends(require_csrf), db: Session = Depends(get_db)):
        ready(db);item=owned_note(db,session.user_id,id)
        values=payload.model_dump(exclude_unset=True,exclude={'version'})
        def exact(current):return all(getattr(current,k)==v for k,v in values.items())
        if payload.version<=item.version and exact(item):return dto(db,item,True)
        result=db.execute(update(Note).where(Note.id==id,Note.owner_id==session.user_id,Note.version==payload.version)
                          .values(**values,version=Note.version+1,updated_at=now()))
        if result.rowcount!=1:
            db.rollback();current=owned_note(db,session.user_id,id,lock=True)
            if payload.version<current.version and exact(current):return dto(db,current,True)
            reject(409,"NOTE_VERSION_CONFLICT","笔记已被其他窗口更新，当前输入已保留，请重新读取后处理。")
        db.commit();db.refresh(item)
        return dto(db,item,True)

    @router.delete('/{id}',status_code=204)
    def removing(id: str, version: int = Query(ge=1), session: LoginSession = Depends(require_csrf), db: Session = Depends(get_db)):
        ready(db);owned_note(db,session.user_id,id)
        result=db.execute(delete(Note).where(Note.id==id,Note.owner_id==session.user_id,Note.version==version))
        if result.rowcount!=1:
            db.rollback();owned_note(db,session.user_id,id)
            reject(409,"NOTE_VERSION_CONFLICT","笔记已更新，未删除；请重新读取后确认。")
        db.commit();return Response(status_code=204)

    def relationship(id, documentId, session, db, add):
        ready(db)
        # Existing document writes take this lock first; match that order on MySQL.
        owned_document(db,session.user_id,documentId,lock=True)
        item=owned_note(db,session.user_id,id,lock=True)
        # SQLite's SELECT FOR UPDATE is a no-op. Acquire its write lock before
        # checking the relationship; no content/version/timestamp is changed.
        locked=db.execute(update(Note).where(Note.id==id,Note.owner_id==session.user_id).values(version=Note.version))
        if locked.rowcount!=1:
            db.rollback();reject(404,"NOTE_NOT_FOUND","笔记不存在或不可访问")
        link=db.get(NoteDocument,(id,documentId))
        if add and link is None:
            db.add(NoteDocument(note_id=id,document_id=documentId,owner_id=session.user_id,created_at=now()))
        elif not add and link is not None:db.delete(link)
        try:db.commit()
        except IntegrityError:
            db.rollback();item=owned_note(db,session.user_id,id)
            # A concurrent identical PUT may have won the unique pair. Confirm
            # actual post-state, never claim an arbitrary FK failure succeeded.
            owned_document(db,session.user_id,documentId)
            link=db.get(NoteDocument,(id,documentId))
            if (add and link is None) or (not add and link is not None):
                reject(409,"NOTE_LINK_CONFLICT","关联状态发生变化，请重新读取。")
        db.refresh(item);return dto(db,item,True)

    @router.put('/{id}/documents/{documentId}')
    def linking(id: str, documentId: str, payload: EmptyInput | None = Body(default=None), session: LoginSession = Depends(require_csrf), db: Session = Depends(get_db)):
        return relationship(id,documentId,session,db,True)

    @router.delete('/{id}/documents/{documentId}')
    def unlinking(id: str, documentId: str, payload: EmptyInput | None = Body(default=None), session: LoginSession = Depends(require_csrf), db: Session = Depends(get_db)):
        return relationship(id,documentId,session,db,False)

    return router
