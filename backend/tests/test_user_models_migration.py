"""Only disposable SQLite: actual backup/restore verification before additive upgrade."""
import hashlib
import sqlite3
from pathlib import Path
from alembic import command
from sqlalchemy import inspect,text
from test_notes_migration import legacy_database,snapshot

def test_0007_backup_restore_then_0008_preserves_data(tmp_path,monkeypatch):
    config,engine,pdf,image=legacy_database(tmp_path,monkeypatch)
    try:
        command.upgrade(config,'0007_literature_notes')
        with engine.begin() as db:
            db.execute(text("INSERT INTO notes(id,owner_id,title,content,content_format,version,source_schema_version,sources,created_at,updated_at) VALUES('n','owner','Existing note','Unchanged body','plain-text',1,1,'[]',CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)"))
            db.execute(text("INSERT INTO note_documents(note_id,document_id,owner_id,created_at) VALUES('n','doc','owner',CURRENT_TIMESTAMP)"))
        tables=set(inspect(engine).get_table_names())-{'alembic_version'}
        before=snapshot(engine,tables)
        files=[hashlib.sha256(p.read_bytes()).hexdigest() for p in (pdf,image)]
        source=Path(engine.url.database);backup=tmp_path/'before-0008.db';restored=tmp_path/'restored-verification.db'
        with sqlite3.connect(source.as_uri()+'?mode=ro',uri=True) as src,sqlite3.connect(backup) as dst:src.backup(dst)
        restored.write_bytes(backup.read_bytes())
        assert hashlib.sha256(backup.read_bytes()).digest()==hashlib.sha256(restored.read_bytes()).digest()
        with sqlite3.connect(restored.as_uri()+'?mode=ro',uri=True) as db:
            assert db.execute('pragma integrity_check').fetchone()[0]=='ok'
            assert db.execute('pragma foreign_key_check').fetchall()==[]
            assert db.execute('select count(*) from notes').fetchone()[0]==1
            assert db.execute('select count(*) from note_documents').fetchone()[0]==1
        command.upgrade(config,'0008_user_model_profiles')
        assert snapshot(engine,tables)==before
        assert set(inspect(engine).get_table_names())==tables|{'alembic_version','user_model_profiles'}
        assert [hashlib.sha256(p.read_bytes()).hexdigest() for p in (pdf,image)]==files
        once=snapshot(engine,tables|{'alembic_version','user_model_profiles'})
        command.upgrade(config,'0008_user_model_profiles')
        assert snapshot(engine,tables|{'alembic_version','user_model_profiles'})==once
        with engine.connect() as db:
            assert db.exec_driver_sql('pragma integrity_check').scalar()=='ok'
            assert db.exec_driver_sql('pragma foreign_key_check').fetchall()==[]
    finally:engine.dispose()
