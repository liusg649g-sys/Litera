from datetime import datetime
from sqlalchemy import DateTime, LargeBinary, ForeignKey, String, Integer, BigInteger, JSON, Text, Boolean, UniqueConstraint, Index
from sqlalchemy.orm import Mapped, mapped_column
from .database import Base
from sqlalchemy.dialects.mysql import DATETIME, MEDIUMBLOB, MEDIUMTEXT
library_time = DateTime().with_variant(DATETIME(fsp=6), "mysql")

class User(Base):
    __tablename__ = "users"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    email: Mapped[str] = mapped_column(String(254), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    display_name: Mapped[str] = mapped_column(String(80), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)

class LoginSession(Base):
    __tablename__ = "sessions"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

class Document(Base):
    __tablename__ = "documents"
    __table_args__ = (Index("ix_documents_owner_active_created", "owner_id", "deleted_at", "created_at"),
        Index("ix_documents_folder", "owner_id", "folder_id"),
        Index("ix_documents_recent", "owner_id", "deleted_at", "last_read_at"))
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    authors: Mapped[list] = mapped_column(JSON, nullable=False)
    abstract: Mapped[str | None] = mapped_column(Text)
    keywords: Mapped[list] = mapped_column(JSON, nullable=False)
    year: Mapped[int | None] = mapped_column(Integer)
    journal: Mapped[str | None] = mapped_column(String(500))
    doi: Mapped[str | None] = mapped_column(String(255))
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    parse_status: Mapped[str] = mapped_column(String(24), nullable=False)
    extraction_version: Mapped[str | None] = mapped_column(String(36))
    page_count: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime)
    folder_id: Mapped[str | None] = mapped_column(ForeignKey("folders.id", ondelete="SET NULL"))
    last_read_at: Mapped[datetime | None] = mapped_column(library_time)
    purge_job_id: Mapped[str | None] = mapped_column(String(36))

class DocumentFile(Base):
    __tablename__ = "document_files"
    __table_args__ = (UniqueConstraint("owner_id", "sha256", name="uq_document_files_owner_hash"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    document_id: Mapped[str] = mapped_column(ForeignKey("documents.id"), unique=True, nullable=False)
    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    original_name: Mapped[str] = mapped_column(String(255), nullable=False)
    storage_key: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    mime_type: Mapped[str] = mapped_column(String(64), nullable=False)

class Folder(Base):
    __tablename__ = "folders"
    __table_args__ = (UniqueConstraint("owner_id", "normalized_name", name="uq_folders_owner_name"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    normalized_name: Mapped[str] = mapped_column(String(300), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)

class Tag(Base):
    __tablename__ = "tags"
    __table_args__ = (UniqueConstraint("owner_id", "normalized_name", name="uq_tags_owner_name"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    normalized_name: Mapped[str] = mapped_column(String(300), nullable=False)
    color: Mapped[str | None] = mapped_column(String(7))
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)

class DocumentTag(Base):
    __tablename__ = "document_tags"
    __table_args__ = (Index("ix_document_tags_owner_tag", "owner_id", "tag_id"),)
    document_id: Mapped[str] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), primary_key=True)
    tag_id: Mapped[str] = mapped_column(ForeignKey("tags.id", ondelete="CASCADE"), primary_key=True)
    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)

class ReadingProgress(Base):
    __tablename__ = "reading_progress"
    document_id: Mapped[str] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), primary_key=True)
    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    page_number: Mapped[int | None] = mapped_column(Integer)
    zoom: Mapped[str | None] = mapped_column(String(20))
    view_mode: Mapped[str | None] = mapped_column(String(16))
    zoom_mode: Mapped[str | None] = mapped_column(String(16))
    last_read_at: Mapped[datetime] = mapped_column(library_time, nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)

class CleanupJob(Base):
    __tablename__ = "cleanup_jobs"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    # Audit survives deletion of the document, deliberately no document FK.
    document_id: Mapped[str] = mapped_column(String(36), nullable=False, unique=True)
    storage_key: Mapped[str | None] = mapped_column(String(80))
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False)
    error_code: Mapped[str | None] = mapped_column(String(64))
    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)

class Annotation(Base):
    __tablename__ = "annotations"
    __table_args__ = (Index("ix_annotations_owner_document_page", "owner_id", "document_id", "page_number"),
        Index("ix_annotations_document_updated", "document_id", "updated_at"))
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    document_id: Mapped[str] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), nullable=False)
    type: Mapped[str] = mapped_column(String(24), nullable=False)
    schema_version: Mapped[int] = mapped_column(Integer, nullable=False)
    page_number: Mapped[int] = mapped_column(Integer, nullable=False)
    position: Mapped[list | None] = mapped_column(JSON)
    geometry: Mapped[dict] = mapped_column(JSON, nullable=False)
    style: Mapped[dict] = mapped_column(JSON, nullable=False)
    selected_text: Mapped[str | None] = mapped_column(Text().with_variant(MEDIUMTEXT(), "mysql"))
    content: Mapped[str | None] = mapped_column(Text().with_variant(MEDIUMTEXT(), "mysql"))
    color: Mapped[str] = mapped_column(String(7), nullable=False)
    asset_id: Mapped[str | None] = mapped_column(String(36))
    z_index: Mapped[int] = mapped_column(Integer, nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(library_time, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(library_time, nullable=False)
    # Tombstones authenticate restore and retain monotonic object versions.
    deleted_at: Mapped[datetime | None] = mapped_column(library_time)

class DocumentReaderState(Base):
    __tablename__ = "document_reader_state"
    document_id: Mapped[str] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), primary_key=True)
    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    annotation_revision: Mapped[int] = mapped_column(Integer, nullable=False)

class AnnotationCommandReceipt(Base):
    __tablename__ = "annotation_command_receipts"
    __table_args__ = (Index("ix_annotation_receipts_expiry", "expires_at"),)
    document_id: Mapped[str] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), primary_key=True)
    command_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    result: Mapped[dict] = mapped_column(JSON, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(library_time, nullable=False)


class ReaderAsset(Base):
    __tablename__ = "reader_assets"
    __table_args__ = (Index("ix_reader_assets_document_status", "owner_id", "document_id", "status"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    document_id: Mapped[str] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), nullable=False)
    storage_key: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(32), nullable=False)
    width: Mapped[int] = mapped_column(Integer, nullable=False)
    height: Mapped[int] = mapped_column(Integer, nullable=False)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_code: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(library_time, nullable=False)
    # null while referenced; otherwise a recoverable lease for drafts/undo.
    expires_at: Mapped[datetime | None] = mapped_column(library_time)


class Note(Base):
    """Personal note identity is independent of any document association."""
    __tablename__ = "notes"
    __table_args__ = (Index("ix_notes_owner_updated", "owner_id", "updated_at", "id"), {"mysql_engine": "InnoDB"})
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    content: Mapped[str] = mapped_column(Text().with_variant(MEDIUMTEXT(), "mysql"), nullable=False)
    content_format: Mapped[str] = mapped_column(String(16), nullable=False, default="plain-text")
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    source_schema_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    sources: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    created_at: Mapped[datetime] = mapped_column(library_time, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(library_time, nullable=False)


class NoteDocument(Base):
    __tablename__ = "note_documents"
    __table_args__ = (Index("ix_note_documents_owner_document", "owner_id", "document_id", "note_id"), {"mysql_engine": "InnoDB"})
    note_id: Mapped[str] = mapped_column(ForeignKey("notes.id", ondelete="CASCADE"), primary_key=True)
    document_id: Mapped[str] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), primary_key=True)
    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(library_time, nullable=False)


class UserModelProfile(Base):
    __tablename__ = 'user_model_profiles'
    __table_args__ = {'mysql_engine': 'InnoDB'}
    owner_id: Mapped[str] = mapped_column(ForeignKey('users.id', ondelete='CASCADE'), primary_key=True)
    revision: Mapped[str] = mapped_column(String(36), nullable=False)
    provider: Mapped[str] = mapped_column(String(40), nullable=False)
    base_url: Mapped[str] = mapped_column(String(2048), nullable=False)
    model: Mapped[str] = mapped_column(String(200), nullable=False)
    encrypted_key: Mapped[bytes | None] = mapped_column(LargeBinary)
    encryption_scheme: Mapped[str] = mapped_column(String(64), nullable=False)
    tested_revision: Mapped[str | None] = mapped_column(String(36))
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class ExtractionJob(Base):
    __tablename__ = "extraction_jobs"
    __table_args__ = (Index("ix_extraction_jobs_owner_document", "owner_id", "document_id"), {"mysql_engine": "InnoDB"})
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    document_id: Mapped[str] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), nullable=False)
    file_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)  # queued | processing | completed | failed
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_code: Mapped[str | None] = mapped_column(String(64))
    version_id: Mapped[str] = mapped_column(String(36), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class ExtractionResult(Base):
    __tablename__ = "extraction_results"
    __table_args__ = (UniqueConstraint("document_id", "extraction_version", name="uq_extraction_results_doc_version"),
                      Index("ix_extraction_results_owner", "owner_id"), {"mysql_engine": "InnoDB"})
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    document_id: Mapped[str] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), nullable=False)
    extraction_version: Mapped[str] = mapped_column(String(36), nullable=False)
    file_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    candidates: Mapped[dict] = mapped_column("metadata", JSON, nullable=False)
    field_sources: Mapped[dict] = mapped_column(JSON, nullable=False)
    warnings: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class DocumentPage(Base):
    __tablename__ = "document_pages"
    __table_args__ = (UniqueConstraint("document_id", "extraction_version", "page_number", name="uq_document_pages_doc_ver_page"),
                      Index("ix_document_pages_owner", "owner_id"), {"mysql_engine": "InnoDB"})
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    document_id: Mapped[str] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), nullable=False)
    extraction_version: Mapped[str] = mapped_column(String(36), nullable=False)
    page_number: Mapped[int] = mapped_column(Integer, nullable=False)
    text: Mapped[str] = mapped_column(Text().with_variant(MEDIUMTEXT(), "mysql"), nullable=False)


class DocumentChunk(Base):
    __tablename__ = "document_chunks"
    __table_args__ = (Index("ix_document_chunks_owner_doc_ver", "owner_id", "document_id", "extraction_version"),
                      {"mysql_engine": "InnoDB"})
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    document_id: Mapped[str] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), nullable=False)
    extraction_version: Mapped[str] = mapped_column(String(36), nullable=False)
    page_number: Mapped[int] = mapped_column(Integer, nullable=False)
    start_offset: Mapped[int] = mapped_column(Integer, nullable=False)
    end_offset: Mapped[int] = mapped_column(Integer, nullable=False)
    text: Mapped[str] = mapped_column(Text().with_variant(MEDIUMTEXT(), "mysql"), nullable=False)


class QaAnswer(Base):
    """Immutable snapshot of one published answer; never rewritten by later versions."""
    __tablename__ = "qa_answers"
    __table_args__ = (Index("ix_qa_answers_owner_doc_created", "owner_id", "document_id", "created_at"),
                      Index("ix_qa_answers_doc_version", "document_id", "extraction_version"),
                      {"mysql_engine": "InnoDB"})
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    document_id: Mapped[str] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), nullable=False)
    file_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    extraction_version: Mapped[str] = mapped_column(String(36), nullable=False)
    mode: Mapped[str] = mapped_column(String(16), nullable=False)
    intent: Mapped[str] = mapped_column(String(24), nullable=False)
    question: Mapped[str] = mapped_column(Text().with_variant(MEDIUMTEXT(), "mysql"), nullable=False)
    answer: Mapped[str] = mapped_column(Text().with_variant(MEDIUMTEXT(), "mysql"), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False)
    citations: Mapped[list] = mapped_column(JSON, nullable=False)
    sections: Mapped[list] = mapped_column(JSON, nullable=False)
    model: Mapped[str] = mapped_column(String(200), nullable=False)
    context_revision: Mapped[int] = mapped_column(Integer, nullable=False)
    latency_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    revision: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class QaIndex(Base):
    __tablename__ = "qa_indexes"
    __table_args__ = (UniqueConstraint("document_id", "extraction_version", name="uq_qa_indexes_doc_version"),
                      Index("ix_qa_indexes_owner_document", "owner_id", "document_id", "status"),
                      {"mysql_engine": "InnoDB"})
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    document_id: Mapped[str] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), nullable=False)
    extraction_version: Mapped[str] = mapped_column(String(36), nullable=False)
    embedding_model: Mapped[str] = mapped_column(String(200), nullable=False)
    dimension: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)  # building | ready | failed
    chunk_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    error_code: Mapped[str | None] = mapped_column(String(64))
    built_at: Mapped[datetime | None] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class QaChunkVector(Base):
    __tablename__ = "qa_chunk_vectors"
    __table_args__ = (UniqueConstraint("chunk_id", name="uq_qa_chunk_vectors_chunk"),
                      Index("ix_qa_chunk_vectors_doc_version", "document_id", "extraction_version"),
                      {"mysql_engine": "InnoDB"})
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    document_id: Mapped[str] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), nullable=False)
    extraction_version: Mapped[str] = mapped_column(String(36), nullable=False)
    chunk_id: Mapped[str] = mapped_column(String(36), nullable=False)
    page_number: Mapped[int] = mapped_column(Integer, nullable=False)
    vector: Mapped[bytes] = mapped_column(LargeBinary().with_variant(MEDIUMBLOB(), "mysql"), nullable=False)
    dimension: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
