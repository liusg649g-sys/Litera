"""Database gate: linear migration chain, repeat-head no-op, index presence,
and rollback refusal on a disposable SQLite copy. No business database is used.
"""
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, inspect, text

from app import models  # noqa: F401  (populate Base.metadata)
from app.config import get_settings
from app.database import Base

HEAD = "0013_index_alignment"

# Tables whose declared ORM indexes must also exist after `alembic upgrade head`.
INDEXED_TABLES = (
    "documents",
    "folders",
    "tags",
    "document_tags",
    "reading_progress",
    "cleanup_jobs",
    "annotations",
    "annotation_command_receipts",
    "reader_assets",
    "notes",
    "note_documents",
    "extraction_jobs",
    "extraction_results",
    "document_pages",
    "document_chunks",
    "qa_answers",
    "qa_indexes",
    "qa_chunk_vectors",
    "audit_logs",
)


def _disposable(tmp_path, monkeypatch):
    url = "sqlite:///" + str(tmp_path / "migration-gate.db")
    monkeypatch.setattr(get_settings(), "database_url", url)
    return Config("alembic.ini"), create_engine(url)


def _schema(engine):
    with engine.connect() as connection:
        return connection.exec_driver_sql(
            "SELECT type, name, tbl_name, sql FROM sqlite_master "
            "WHERE name NOT LIKE 'sqlite_%' ORDER BY type, name").fetchall()


def _rows(engine, table):
    with engine.connect() as connection:
        return connection.execute(text(f'SELECT * FROM "{table}" ORDER BY 1')).fetchall()


def test_chain_has_one_head_and_every_revision_links_to_the_previous():
    script = ScriptDirectory.from_config(Config("alembic.ini"))
    assert script.get_current_head() == HEAD
    assert script.get_heads() == [HEAD]
    revisions = list(script.walk_revisions())
    by_revision = {item.revision: item for item in revisions}
    assert len(by_revision) == len(revisions)
    for item in revisions:
        down = item.down_revision
        if down is None:
            continue
        assert down in by_revision, f"{item.revision} points at missing {down}"
        assert by_revision[down].down_revision != item.revision


def test_upgrade_head_is_repeatable_and_declared_indexes_exist(tmp_path, monkeypatch):
    config, engine = _disposable(tmp_path, monkeypatch)
    try:
        command.upgrade(config, "head")
        inspector = inspect(engine)
        assert set(inspector.get_table_names()) == set(Base.metadata.tables) | {"alembic_version"}

        missing = []
        for table in INDEXED_TABLES:
            actual = {tuple(index["column_names"]) for index in inspector.get_indexes(table)}
            expected = {tuple(index.columns.keys()) for index in Base.metadata.tables[table].indexes}
            missing.extend(f"{table}{sorted(columns)}" for columns in expected - actual)
        assert missing == [], f"missing declared indexes: {missing}"

        before = _schema(engine)
        command.upgrade(config, "head")
        assert _schema(engine) == before
    finally:
        engine.dispose()


def test_rollback_refuses_qa_layer_and_preserves_core_rows(tmp_path, monkeypatch):
    config, engine = _disposable(tmp_path, monkeypatch)
    try:
        command.upgrade(config, "head")
        with engine.begin() as connection:
            connection.execute(text(
                "INSERT INTO users(id,email,password_hash,display_name,created_at,updated_at) "
                "VALUES('gate-user','gate@example.com','synthetic-hash','Gate',CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)"))
            connection.execute(text(
                "INSERT INTO documents(id,owner_id,title,authors,keywords,version,parse_status,created_at,updated_at) "
                "VALUES('gate-doc','gate-user','Rollback fixture','[]','[]',1,'completed',CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)"))
            connection.execute(text(
                "INSERT INTO document_files(id,document_id,owner_id,original_name,storage_key,sha256,size_bytes,mime_type) "
                "VALUES('gate-file','gate-doc','gate-user','gate.pdf','gate.pdf','synthetic-hash',16,'application/pdf')"))
            connection.execute(text(
                "INSERT INTO notes(id,owner_id,title,content,content_format,version,source_schema_version,sources,created_at,updated_at) "
                "VALUES('gate-note','gate-user','Rollback note','Unchanged body','plain-text',1,1,'[]',CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)"))

        core = {table: _rows(engine, table) for table in ("users", "documents", "document_files", "notes")}
        with pytest.raises(RuntimeError):
            command.downgrade(config, "0008_user_model_profiles")
        assert {table: _rows(engine, table) for table in core} == core

        command.upgrade(config, "head")
        assert {table: _rows(engine, table) for table in core} == core
        with engine.connect() as connection:
            assert connection.execute(text("SELECT version_num FROM alembic_version")).scalar() == HEAD
    finally:
        engine.dispose()
