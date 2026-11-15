"""Document-scoped titles, serialized by an existing per-owner row lock."""
from sqlalchemy import select, update
from .models import User, Note, NoteDocument
from .documents import reject


def lock_note_writes(db, owner):
    # End authentication/schema read snapshots before acquiring the owner mutex.
    # A no-op UPDATE also takes SQLite's write lock, unlike SELECT FOR UPDATE.
    db.rollback()
    db.execute(update(User).where(User.id == owner).values(updated_at=User.updated_at))


def require_unique_title(db, owner, title, document_ids, exclude_id=None):
    documents = set(document_ids)
    if not documents:
        return
    query = (select(Note.id, Note.title).join(NoteDocument, NoteDocument.note_id == Note.id)
             .where(Note.owner_id == owner, NoteDocument.document_id.in_(documents))
             .with_for_update())
    normalized = title.strip().casefold()
    for note_id, existing in db.execute(query):
        if note_id != exclude_id and existing.strip().casefold() == normalized:
            reject(409, 'NOTE_TITLE_DUPLICATE', '该文献已有关联的同名笔记，请修改标题。当前输入和内容已保留。')
