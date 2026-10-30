"""Fresh disposable SQLite and OFFLINE MySQL DDL only. No real MySQL/Docker."""
from pathlib import Path
import sqlite3
from alembic import command
from alembic.config import Config
from app.config import get_settings

def test_fresh_sqlite_full_migration_chain_and_repeat_head(tmp_path,monkeypatch):
    target=tmp_path/'fresh-delivery.db'
    monkeypatch.setattr(get_settings(),'database_url','sqlite:///'+str(target))
    config=Config('alembic.ini');command.upgrade(config,'head')
    with sqlite3.connect(target) as db:
        assert db.execute('select version_num from alembic_version').fetchall()==[('0010_qa_answers_indexes_vectors',)]
        assert db.execute('pragma integrity_check').fetchone()[0]=='ok'
        assert db.execute('pragma foreign_key_check').fetchall()==[]
        before=db.execute('select name,sql from sqlite_master order by name').fetchall()
    command.upgrade(config,'head')
    with sqlite3.connect(target) as db:assert db.execute('select name,sql from sqlite_master order by name').fetchall()==before

def test_mysql_profile_ddl_is_additive_binary_owner_bound_offline_only(monkeypatch,capsys):
    monkeypatch.setattr(get_settings(),'database_url','mysql+pymysql://test:unused@127.0.0.1/litera_test')
    command.upgrade(Config('alembic.ini'),'0007_literature_notes:0008_user_model_profiles',sql=True)
    ddl=capsys.readouterr().out
    assert 'CREATE TABLE user_model_profiles' in ddl and 'encrypted_key BLOB' in ddl
    assert 'REFERENCES users' in ddl and 'ON DELETE CASCADE' in ddl and 'ENGINE=InnoDB' in ddl
    assert 'ALTER TABLE' not in ddl and 'DROP TABLE' not in ddl

def test_direct_runtime_pins_exist_in_install_manifest():
    root=Path(__file__).resolve().parents[1]
    pins=lambda name:{line.strip().lower() for line in (root/name).read_text().splitlines() if line.strip() and not line.startswith('#')}
    assert pins('requirements.in')<=pins('requirements.txt')
