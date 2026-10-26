"""New launcher shutdown guard only, no real service/database/process termination."""
import asyncio
import importlib.util
from pathlib import Path
import pytest

@pytest.mark.parametrize('reason',['marker','disk'])
def test_api_worker_exits_gracefully_for_its_own_guard(tmp_path,monkeypatch,reason):
    spec=importlib.util.spec_from_file_location('user_model_preview',Path(__file__).resolve().parents[2]/'scripts/user_model_preview.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    monkeypatch.setattr(module,'DATA',tmp_path)
    if reason=='marker':
        (tmp_path/'stop.request').touch();monkeypatch.setattr(module,'ensure_space',lambda:{'test':20000000000})
    else:
        def low():raise RuntimeError('Preview stopped: available disk space below 10 GB')
        monkeypatch.setattr(module,'ensure_space',low)
    class Server:
        should_exit=False
        async def serve(self):
            for _ in range(100):
                if self.should_exit:return
                await asyncio.sleep(.001)
            raise AssertionError('Guard did not stop actual API worker')
    server=Server();asyncio.run(module.serve_api(server));assert server.should_exit


def test_unified_backup_restore_migrates_only_copy_and_retains_every_source_file(tmp_path,monkeypatch):
    import shutil,sqlite3,json
    from alembic import command
    from sqlalchemy import text
    from app.config import get_settings
    from test_notes_migration import legacy_database
    spec=importlib.util.spec_from_file_location('unified_preview',Path(__file__).resolve().parents[2]/'scripts/user_model_preview.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    config,engine,pdf,image=legacy_database(tmp_path,monkeypatch)
    command.upgrade(config,'0007_literature_notes')
    with engine.begin() as db:
        db.execute(text("INSERT INTO notes(id,owner_id,title,content,content_format,version,source_schema_version,sources,created_at,updated_at) VALUES('note','owner','Existing','Retain body','plain-text',1,1,'[]',CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)"))
        db.execute(text("INSERT INTO note_documents(note_id,document_id,owner_id,created_at) VALUES('note','doc','owner',CURRENT_TIMESTAMP)"))
    source=tmp_path/'original-preview';source.mkdir();(source/'pdfs').mkdir()
    engine.dispose();shutil.copy2(Path(engine.url.database),source/'preview.db')
    for file in (pdf,image):shutil.copy2(file,source/'pdfs'/file.name)
    (source/'session-secret').write_text('synthetic-session-only-not-a-real-credential')
    (source/'existing.log').write_text('Historical log retained')
    root=tmp_path/'repo';data=root/'.cache/user-model-preview/unified'
    monkeypatch.setattr(module,'ROOT',root);monkeypatch.setattr(module,'SOURCE',source);monkeypatch.setattr(module,'DATA',data)
    monkeypatch.setattr(module,'ensure_space',lambda:{'test':20000000000})
    monkeypatch.setattr(module,'check',lambda:None)
    monkeypatch.setattr(module,'migration_config',lambda:config)
    monkeypatch.setattr(module,'configure',lambda:monkeypatch.setattr(get_settings(),'database_url','sqlite:///'+data.joinpath('preview.db').as_posix()))
    before=module.file_manifest(source)
    module.prepare()
    assert module.file_manifest(source)==before
    record=json.loads((data/'import-verification.json').read_text())
    assert record['backupAndRestoreVerified'] is True and record['files']==before
    assert module.file_manifest(Path(record['backup']))==before
    assert module.file_manifest(data/'pdfs')==module.file_manifest(source/'pdfs')
    with sqlite3.connect((source/'preview.db').as_uri()+'?mode=ro',uri=True) as db:assert db.execute('select version_num from alembic_version').fetchone()[0]=='0007_literature_notes'
    with sqlite3.connect((data/'preview.db').as_uri()+'?mode=ro',uri=True) as db:
        assert db.execute('select version_num from alembic_version').fetchone()[0]=='0008_user_model_profiles'
        assert db.execute('select content from notes').fetchall()==[('Retain body',)]
        assert db.execute('pragma integrity_check').fetchone()[0]=='ok'
        assert db.execute('pragma foreign_key_check').fetchall()==[]
    module.prepare() # no re-import, overwrite or second backup
    assert module.file_manifest(source)==before
    assert len(list((root.parent/'Litera-backups').iterdir()))==1
