from datetime import datetime
from sqlalchemy import DateTime, ForeignKey, String, Integer, BigInteger, JSON, Text, UniqueConstraint, Index
from sqlalchemy.orm import Mapped, mapped_column
from .database import Base
from sqlalchemy.dialects.mysql import DATETIME
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
