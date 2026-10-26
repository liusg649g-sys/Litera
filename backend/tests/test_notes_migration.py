"""Additive 0006 -> 0007 checks in independent temporary SQLite; no business DB.

MySQL case emits offline DDL only. It is not a real MySQL execution test.
"""
import hashlib
import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text
from app.config import get_settings

HEAD = '0007_literature_notes'


def snapshot(engine, tables):
    result = {}
    with engine.connect() as connection:
        for name in sorted(tables):
            columns = tuple(tuple(row) for row in connection.exec_driver_sql(f'PRAGMA table_info("{name}")'))
            rows = sorted((tuple(row) for row in connection.exec_driver_sql(f'SELECT * FROM "{name}"')), key=repr)
            result[name] = (columns, rows)
    return result


def legacy_database(tmp_path, monkeypatch):
    # Only this explicitly generated filename is ever migrated by these tests.
    path = tmp_path / 'notes-additive-upgrade.db'
    monkeypatch.setattr(get_settings(), 'database_url', 'sqlite:///' + str(path))
    config = Config('alembic.ini')
    command.upgrade(config, '0006_reader_assets')
    engine = create_engine('sqlite:///' + str(path))
    original = tmp_path / 'existing-original.pdf'
    original.write_bytes(b'%PDF-public-migration-fixture-unchanged')
    image = tmp_path / 'existing-image.png'
    image.write_bytes(b'public-existing-image-unchanged')
    digest = hashlib.sha256(original.read_bytes()).hexdigest()
    image_digest = hashlib.sha256(image.read_bytes()).hexdigest()
    with engine.begin() as connection:
        connection.exec_driver_sql('PRAGMA foreign_keys=ON')
        connection.execute(text("INSERT INTO users(id,email,password_hash,display_name,created_at,updated_at) VALUES('owner','migration-only@example.com','not-a-real-password','Migration fixture',CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)"))
        connection.execute(text("INSERT INTO sessions(id,user_id,token_hash,created_at,expires_at) VALUES('session','owner','synthetic-session-hash',CURRENT_TIMESTAMP,'2100-01-01 00:00:00')"))
        connection.execute(text("INSERT INTO documents(id,owner_id,title,authors,keywords,version,parse_status,created_at,updated_at) VALUES('doc','owner','Public existing paper','[]','[]',7,'not_requested',CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)"))
        connection.execute(text("INSERT INTO document_files(id,document_id,owner_id,original_name,storage_key,sha256,size_bytes,mime_type) VALUES('file','doc','owner','existing.pdf','existing-original.pdf',:hash,:size,'application/pdf')"),{'hash':digest,'size':original.stat().st_size})
        connection.execute(text("INSERT INTO reading_progress(document_id,owner_id,page_number,zoom,view_mode,zoom_mode,last_read_at,version) VALUES('doc','owner',2,'1.5','continuous','custom',CURRENT_TIMESTAMP,4)"))
        connection.execute(text("INSERT INTO document_reader_state(document_id,owner_id,annotation_revision) VALUES('doc','owner',3)"))
        connection.execute(text("INSERT INTO annotations(id,owner_id,document_id,type,schema_version,page_number,geometry,style,content,color,z_index,version,created_at,updated_at) VALUES('annotation','owner','doc','comment',1,1,'{}','{}','Existing annotation remains','#FFFF00',2,3,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)"))
        connection.execute(text("INSERT INTO reader_assets(id,owner_id,document_id,storage_key,sha256,mime_type,width,height,size_bytes,status,attempts,created_at) VALUES('asset','owner','doc','existing-image.png',:hash,'image/png',1,1,:size,'ready',0,CURRENT_TIMESTAMP)"),{'hash':image_digest,'size':image.stat().st_size})
    return config, engine, original, image


def test_upgrade_only_adds_note_tables_and_preserves_old_rows_schema_files(tmp_path, monkeypatch):
    config, engine, original, image = legacy_database(tmp_path, monkeypatch)
    try:
        old_tables = set(inspect(engine).get_table_names()) - {'alembic_version'}
        old_state = snapshot(engine, old_tables)
        hashes = [hashlib.sha256(path.read_bytes()).hexdigest() for path in (original, image)]
        command.upgrade(config, HEAD)
        assert set(inspect(engine).get_table_names()) == old_tables | {'alembic_version','notes','note_documents'}
        assert snapshot(engine, old_tables) == old_state
        assert [hashlib.sha256(path.read_bytes()).hexdigest() for path in (original, image)] == hashes
        with engine.connect() as connection:
            assert connection.execute(text('SELECT version_num FROM alembic_version')).scalar() == HEAD
            assert connection.exec_driver_sql('PRAGMA integrity_check').scalar() == 'ok'
            assert connection.exec_driver_sql('PRAGMA foreign_key_check').fetchall() == []
        assert 'document_id' not in {column['name'] for column in inspect(engine).get_columns('notes')}
        assert set(inspect(engine).get_pk_constraint('note_documents')['constrained_columns']) == {'note_id','document_id'}
    finally:
        engine.dispose()


def test_repeated_head_upgrade_is_noop_and_downgrade_refuses_data_loss(tmp_path, monkeypatch):
    config, engine, original, image = legacy_database(tmp_path, monkeypatch)
    try:
        command.upgrade(config, HEAD)
        with engine.begin() as connection:
            connection.execute(text("INSERT INTO notes(id,owner_id,title,content,content_format,version,source_schema_version,sources,created_at,updated_at) VALUES('note','owner','Preserve this note','Public note body','plain-text',1,1,'[]',CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)"))
            connection.execute(text("INSERT INTO note_documents(note_id,document_id,owner_id,created_at) VALUES('note','doc','owner',CURRENT_TIMESTAMP)"))
        tables = set(inspect(engine).get_table_names())
        first = snapshot(engine, tables)
        command.upgrade(config, HEAD)
        assert snapshot(engine, tables) == first
        with pytest.raises(RuntimeError):
            command.downgrade(config, '0006_reader_assets')
        assert snapshot(engine, tables) == first
        assert original.exists() and image.exists()
    finally:
        engine.dispose()


def test_mysql_notes_ddl_is_additive_offline_only(monkeypatch, capsys):
    monkeypatch.setattr(get_settings(), 'database_url', 'mysql+pymysql://test:unused@127.0.0.1/litera_test')
    command.upgrade(Config('alembic.ini'), '0006_reader_assets:' + HEAD, sql=True)
    ddl = capsys.readouterr().out
    assert 'CREATE TABLE notes' in ddl and 'CREATE TABLE note_documents' in ddl
    assert 'MEDIUMTEXT' in ddl and 'DATETIME(6)' in ddl and 'JSON' in ddl
    assert ddl.count('ENGINE=InnoDB') == 2
    assert 'DROP TABLE' not in ddl and 'ALTER TABLE documents' not in ddl and 'ALTER TABLE users' not in ddl
    assert 'REFERENCES notes' in ddl and 'REFERENCES documents' in ddl and 'ON DELETE CASCADE' in ddl
