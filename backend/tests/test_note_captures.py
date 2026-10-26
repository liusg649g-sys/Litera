"""P3-B real HTTP / isolated SQLite / synthetic PDFs; model calls are explicit Mock."""
from copy import deepcopy
from concurrent.futures import ThreadPoolExecutor
from io import BytesIO
from uuid import uuid4
import pytest
from fastapi.testclient import TestClient
from pypdf import PdfWriter
from pypdf.generic import ArrayObject, DictionaryObject, NameObject, NumberObject
from reportlab.pdfgen.canvas import Canvas
from sqlalchemy import func, select
from app import note_captures, translations, translation_proof
from app.database import SessionLocal
from app.main import app
from app.models import DocumentFile, Note, NoteDocument
from app.pdf_source_validation import source_text_matches
from test_auth import login, register
from test_documents import logged, upload
from test_notes import create

TEXT = 'Optical microscopy is widely used in scientific research.'
OTHER = 'Another independently sourced paragraph.'


def synthetic_pdf(*pages):
    stream = BytesIO()
    canvas = Canvas(stream, pagesize=(612, 792))
    for lines in pages:
        canvas.setFont('Helvetica', 12)
        for index, text in enumerate(lines): canvas.drawString(40, 700 - 16 * index, text)
        canvas.showPage()
    canvas.save()
    return stream.getvalue()


@pytest.fixture(autouse=True)
def no_model_rate_leak():
    translations.attempts.clear()
    yield
    translations.attempts.clear()


@pytest.fixture
def document(logged):
    result = upload(logged, synthetic_pdf([TEXT], [OTHER]), 'Synthetic provenance.pdf')
    assert result.status_code == 201, result.text
    return result.json()


def payload(document, note=None, **source_changes):
    source = dict(kind='pdf_excerpt', documentId=document['id'], pageNumber=1,
                  originalText=TEXT, positions=[], contextRevision=4)
    source.update(source_changes)
    return dict(operationId=str(uuid4()), noteId=note['id'] if note else str(uuid4()),
                version=note['version'] if note else None,
                newNoteTitle=None if note else 'Captured research', associationMode='keep', source=source)


def send(client, body):
    return client.post('/api/v1/notes/captures', json=body)


def assert_error(response, code, status=422):
    assert response.status_code == status, response.text
    assert response.json()['error']['code'] == code, response.text


def translated_payload(logged, document, monkeypatch, note=None):
    async def fake(text, source, target, settings, **kwargs):
        return '[ISOLATED MOCK] ' + ('合成测试译文' if target == 'zh' else 'Synthetic translation')
    monkeypatch.setattr(translations, 'translate_text', fake)
    response = logged.post('/api/v1/documents/' + document['id'] + '/translations', json={
        'text': TEXT, 'sourceLanguage': 'en', 'targetLanguage': 'zh', 'pageNumber': 1, 'contextRevision': 4})
    assert response.status_code == 200, response.text
    result = response.json()
    assert result['translationProof']['provenance'] == 'isolated_mock'
    source = dict(kind='translation_excerpt', originalText=result['originalText'], translatedText=result['translatedText'],
                  sourceLanguage='en', targetLanguage='zh', translationProof=result['translationProof'])
    for key in ('modelInputText', 'normalizationCount'):
        if key in result: source[key] = result[key]
    return payload(document, note, **source)


def test_capture_config_uses_static_route_and_never_changes_old_config(logged, monkeypatch):
    assert logged.get('/api/v1/notes/config').json() == {
        'available': True, 'contentMaxLength': 100000, 'titleMaxLength': 200, 'contentFormat': 'plain-text'}
    config = logged.get('/api/v1/notes/capture-config')
    assert config.status_code == 200
    assert config.json() == dict(available=True, formatVersion=1, maxOriginalLength=6000,
        maxTranslatedLength=20000, maxBlocks=100, maxSourceBytes=1048576, isolatedTranslationMock=False,
        supportedSourceKinds=['pdf_excerpt','translation_excerpt'], aiAnswerCapture=dict(available=False, isolatedMock=False))
    monkeypatch.setenv('LITERA_ISOLATED_TRANSLATION_MOCK', '1')
    assert logged.get('/api/v1/notes/capture-config').json()['isolatedTranslationMock'] is True
    monkeypatch.setattr(note_captures, 'schema_available', lambda db: False)
    assert logged.get('/api/v1/notes/capture-config').json()['available'] is False


def test_pdf_capture_atomic_new_note_and_exact_raw_provenance(logged, document):
    raw = 'Optical microscopy is widely used\n in scientific research.'
    body = payload(document, originalText=raw)
    response = send(logged, body)
    assert response.status_code == 201, response.text
    result = response.json()
    assert result['created'] and not result['linked'] and not result['replayed']
    note = result['note']
    assert note['version'] == 1 and note['content'] == '' and note['documents'] == []
    assert note['contentFormat'] == 'plain-text' and note['sourceSchemaVersion'] == 1
    block = note['sources'][0]
    assert block['id'] == body['operationId'] and block['originalText'] == raw
    assert block['kind'] == 'pdf_excerpt' and not block['historical']
    assert block['source'] == dict(documentId=document['id'], title=document['title'],
        fileSha256=DocumentFileHash(document['id']), pageNumber=1, pageNumbers=[1], positions=[], contextRevision=4, precision='page')
    assert len(block['requestFingerprint']) == 64
    assert 'translationProof' not in block and 'translationProvenance' not in block
    assert logged.get('/api/v1/notes/' + note['id']).json() == note
    with SessionLocal() as db:
        assert db.scalar(select(func.count()).select_from(Note)) == 1
        assert db.scalar(select(func.count()).select_from(NoteDocument)) == 0


def test_cross_extractor_source_matching_is_ordered_and_never_rewrites_original():
    assert source_text_matches('efficient microscopy', ['ef\ufb01cient microscopy'])
    assert source_text_matches('micro-\nscopy reveals cells', ['microscopy reveals cells'])
    assert source_text_matches('label-free insights', ['label free insights'])
    assert source_text_matches('structure, dynamics', ['structure dynamics'])
    assert source_text_matches('eld light microscopy', ['Bright-field light microscopy'])
    assert source_text_matches('microscop', ['microscopy'])
    assert source_text_matches('—', ['the result — remains'])
    assert not source_text_matches('microscopy reveals cells', ['cells reveal microscopy'])
    assert not source_text_matches('microscopy reveals cells', ['microscopy hides cells'])
    assert not source_text_matches('eld light cells', ['Bright-field light microscopy'])
    assert not source_text_matches('—', ['the result remains'])


def test_line_hyphen_verification_does_not_join_an_ordinary_compound():
    assert source_text_matches('label-free', ['label-free methods'])
    assert not source_text_matches('label-free', ['labelfree methods'])


def DocumentFileHash(document_id):
    with SessionLocal() as db:
        return db.scalar(select(DocumentFile.sha256).where(DocumentFile.document_id == document_id))


def test_existing_body_and_many_document_source_survive_unlink_refresh_login(logged, document):
    other = upload(logged, synthetic_pdf([OTHER]), 'Second source.pdf').json()
    note = create(logged, other['id'], title='Shared note', content='My independent thoughts')
    body = payload(document, note)
    body['associationMode'] = 'link'
    response = send(logged, body)
    assert response.status_code == 201, response.text
    note = response.json()['note']
    assert note['version'] == 2 and note['content'] == 'My independent thoughts'
    assert {doc['id'] for doc in note['documents']} == {document['id'], other['id']}
    source = deepcopy(note['sources'])
    changed = logged.patch('/api/v1/notes/' + note['id'], json={'version': 2, 'content': 'Edited thoughts'})
    assert changed.status_code == 200
    unlinked = logged.delete('/api/v1/notes/' + note['id'] + '/documents/' + document['id'])
    assert unlinked.status_code == 200 and unlinked.json()['sources'] == source
    assert [doc['id'] for doc in unlinked.json()['documents']] == [other['id']]
    assert logged.get('/api/v1/notes', params={'documentId': other['id']}).json()['items'][0]['id'] == note['id']
    assert logged.get('/api/v1/notes', params={'documentId': document['id']}).json()['items'] == []
    assert logged.post('/api/v1/auth/logout').status_code == 204
    logged.headers['X-CSRF-Token'] = login(logged).json()['csrfToken']
    retained = logged.get('/api/v1/notes/' + note['id']).json()
    assert retained['sources'] == source and retained['content'] == 'Edited thoughts'
    assert retained['sources'][0]['source']['documentId'] == document['id']


def test_replay_after_ack_loss_and_unlink_never_duplicates_or_relinks(logged, document):
    body = payload(document)
    body['associationMode'] = 'link'
    first = send(logged, body).json()
    assert first['linked']
    replay = send(logged, body)
    assert replay.status_code == 200 and replay.json()['replayed']
    assert replay.json()['note'] == first['note']
    logged.delete('/api/v1/notes/' + body['noteId'] + '/documents/' + document['id'])
    replay = send(logged, body)
    assert replay.status_code == 200 and not replay.json()['linked']
    assert replay.json()['note']['version'] == 1 and len(replay.json()['note']['sources']) == 1
    changed = deepcopy(body)
    changed['source']['originalText'] = 'Different selection'
    assert_error(send(logged, changed), 'NOTE_CAPTURE_CONFLICT', 409)


def test_append_replay_ignores_version_but_conflicting_operations_do_not_overwrite(logged, document):
    note = create(logged)
    first = payload(document, note)
    saved = send(logged, first)
    assert saved.status_code == 201
    refreshed = deepcopy(first)
    refreshed['version'] = 2
    assert send(logged, refreshed).status_code == 200
    conflict = payload(document, note)
    assert_error(send(logged, conflict), 'NOTE_VERSION_CONFLICT', 409)
    persisted = logged.get('/api/v1/notes/' + note['id']).json()
    assert persisted['version'] == 2 and persisted['content'] == note['content'] and len(persisted['sources']) == 1


def test_two_concurrent_captures_use_cas_and_keep_winning_block(logged, document):
    note = create(logged)
    requests = [payload(document, note), payload(document, note)]
    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(pool.map(lambda body: send(logged, body), requests))
    assert sorted(response.status_code for response in responses) == [201, 409], [r.text for r in responses]
    retained = logged.get('/api/v1/notes/' + note['id']).json()
    assert retained['version'] == 2 and len(retained['sources']) == 1


def test_title_filter_is_literal_title_only_not_fulltext(logged):
    wanted = create(logged, title='Optical_100% summary', content='hidden body')
    create(logged, title='Other summary', content='Optical_100% summary')
    found = logged.get('/api/v1/notes', params={'title': 'OPTICAL_100%'}).json()
    assert [item['id'] for item in found['items']] == [wanted['id']]
    assert 'content' not in found['items'][0]
    assert logged.get('/api/v1/notes?title=  ').status_code == 422
    assert logged.get('/api/v1/notes?title=x&title=y').status_code == 422
    assert logged.get('/api/v1/notes?q=hidden').status_code == 422


def test_mult_page_selection_verifies_each_page_and_preserves_positions(logged, document):
    def position(page, text):
        return dict(pageNumber=page, textQuote=text, rects=[dict(x=0.1, y=0.2, width=0.6, height=0.05)],
                    textRanges=[dict(item=0, start=0, end=len(text))])
    positions = [position(1, TEXT), position(2, OTHER)]
    body = payload(document, originalText=TEXT + '\n' + OTHER, positions=positions)
    response = send(logged, body)
    assert response.status_code == 201, response.text
    source = response.json()['note']['sources'][0]['source']
    assert source['pageNumbers'] == [1, 2] and source['positions'] == positions and source['precision'] == 'page'
    wrong = payload(document, originalText=OTHER, pageNumber=1, positions=[position(1, OTHER)])
    assert_error(send(logged, wrong), 'PDF_TEXT_NOT_FOUND')


@pytest.mark.parametrize('changes,code', [
    ({'originalText': 'Not present in this PDF'}, 'PDF_TEXT_NOT_FOUND'),
    ({'originalText': 'Opticalmicroscopy'}, 'PDF_TEXT_NOT_FOUND'),
    ({'pageNumber': 3}, 'INVALID_PAGE'),
    ({'originalText': 'Optical \ufffd text'}, 'PDF_TEXT_UNRELIABLE'),
    ({'originalText': 'Optical \ue001 text'}, 'PDF_TEXT_UNRELIABLE'),
    ({'originalText': 'Optical \u0003 text'}, 'PDF_TEXT_UNRELIABLE'),
])
def test_invalid_source_never_creates_partial_note(logged, document, changes, code):
    assert_error(send(logged, payload(document, **changes)), code)
    with SessionLocal() as db:
        assert db.scalar(select(func.count()).select_from(Note)) == 0
        assert db.scalar(select(func.count()).select_from(NoteDocument)) == 0


def test_opaque_font_source_rejected_even_when_printable(logged):
    writer = PdfWriter()
    page = writer.add_blank_page(width=200, height=300)
    font = DictionaryObject({NameObject('/Type'): NameObject('/Font'), NameObject('/Subtype'): NameObject('/Type1'),
        NameObject('/BaseFont'): NameObject('/Helvetica'), NameObject('/Encoding'): DictionaryObject({
            NameObject('/Type'): NameObject('/Encoding'), NameObject('/Differences'): ArrayObject([
                NumberObject(1), NameObject('/G01'), NameObject('/G02')])})})
    page[NameObject('/Resources')] = DictionaryObject({NameObject('/Font'): DictionaryObject({NameObject('/F1'): font})})
    stream = BytesIO(); writer.write(stream)
    doc = upload(logged, stream.getvalue()).json()
    assert_error(send(logged, payload(doc, originalText='123')), 'PDF_TEXT_UNRELIABLE')


@pytest.mark.parametrize('changes', [
    {'translatedText': 'forged'}, {'originalText': ''}, {'originalText': ' '}, {'originalText': 'x' * 6001},
    {'pageNumber': True}, {'contextRevision': True}, {'contextRevision': -1},
    {'positions': [{'pageNumber': 1, 'textQuote': TEXT, 'rects': [{'x': 0.9, 'y': 0, 'width': 0.2, 'height': 0.1}]}]},
    {'positions': [{'pageNumber': 1, 'textQuote': 'different', 'rects': [{'x': 0, 'y': 0, 'width': 0.2, 'height': 0.1}]}]},
    {'historical': True}, {'ownerId': 'forged'},
])
def test_capture_input_validation(logged, document, changes):
    response = send(logged, payload(document, **changes))
    assert response.status_code == 422
    assert logged.get('/api/v1/notes').json()['total'] == 0


def test_source_limit_and_unknown_schema_leave_original_untouched(logged, document, monkeypatch):
    note = create(logged)
    body = payload(document, note)
    monkeypatch.setattr(note_captures, 'BLOCK_LIMIT', 0)
    assert_error(send(logged, body), 'NOTE_CAPTURE_LIMIT')
    monkeypatch.setattr(note_captures, 'BLOCK_LIMIT', 100)
    monkeypatch.setattr(note_captures, 'SOURCE_BYTES_LIMIT', 1)
    assert_error(send(logged, body), 'NOTE_CAPTURE_LIMIT')
    with SessionLocal() as db:
        item = db.get(Note, note['id']); item.source_schema_version = 9; db.commit()
    assert_error(send(logged, body), 'NOTE_SOURCE_FORMAT_UNSUPPORTED', 409)
    with SessionLocal() as db:
        item = db.get(Note, note['id'])
        assert item.content == note['content'] and item.sources == [] and item.version == 1


def test_translation_receipt_current_historical_and_save_without_model(logged, document, monkeypatch):
    body = translated_payload(logged, document, monkeypatch)
    async def unexpected(*args, **kwargs): raise AssertionError('Capture must not call the model')
    monkeypatch.setattr(translations, 'translate_text', unexpected)
    response = send(logged, body)
    assert response.status_code == 201, response.text
    block = response.json()['note']['sources'][0]
    assert block['translationProvenance'] == 'isolated_mock' and block['translatedText'].startswith('[ISOLATED MOCK]')
    assert block['source']['documentId'] == document['id'] and not block['historical']
    assert 'translationProof' not in block and 'signature' not in str(block)
    history = deepcopy(body)
    history.update(operationId=str(uuid4()), noteId=str(uuid4()))
    history['source']['historical'] = True
    assert send(logged, history).status_code == 422
    history['source']['confirmHistorical'] = True
    saved = send(logged, history)
    assert saved.status_code == 201 and saved.json()['note']['sources'][0]['historical']


@pytest.mark.parametrize('field,value', [
    ('translatedText', 'forged translation'), ('contextRevision', 9),
    ('sourceLanguage', 'zh'), ('targetLanguage', 'en'),
    ('modelInputText', 'forged normalized model input'),
])
def test_tampered_translation_is_not_a_model_response(logged, document, monkeypatch, field, value):
    body = translated_payload(logged, document, monkeypatch)
    body['source'][field] = value
    if field == 'sourceLanguage': body['source']['targetLanguage'] = 'en'
    if field == 'targetLanguage': body['source']['sourceLanguage'] = 'zh'
    if field == 'modelInputText': body['source']['normalizationCount'] = 1
    assert_error(send(logged, body), 'TRANSLATION_PROOF_INVALID')
    assert logged.get('/api/v1/notes').json()['total'] == 0


def test_raw_page_document_hash_and_signature_are_bound(logged, document, monkeypatch):
    original = translated_payload(logged, document, monkeypatch)
    other = upload(logged, synthetic_pdf([TEXT]), 'Other equal text.pdf').json()
    for changes in ({'documentId': other['id']}, {'originalText': 'Optical microscopy'}, {'pageNumber': 2, 'originalText': OTHER}):
        body = deepcopy(original); body['source'].update(changes)
        assert_error(send(logged, body), 'TRANSLATION_PROOF_INVALID')
    altered = deepcopy(original)
    altered['source']['translationProof']['signature'] = '0' * 64
    assert_error(send(logged, altered), 'TRANSLATION_PROOF_INVALID')
    altered = deepcopy(original)
    altered['source']['translationProof']['provenance'] = 'model_api'
    assert_error(send(logged, altered), 'TRANSLATION_PROOF_INVALID')


@pytest.mark.parametrize('offset', [-(24 * 60 * 60 + 1), 61])
def test_expired_or_future_receipt_does_not_save(logged, document, monkeypatch, offset):
    body = translated_payload(logged, document, monkeypatch)
    issued = body['source']['translationProof']['issuedAt']
    monkeypatch.setattr(translation_proof, 'clock_seconds', lambda: issued - offset)
    assert_error(send(logged, body), 'TRANSLATION_PROOF_EXPIRED')


def test_pdf_dehyphenation_receipt_preserves_raw_and_binds_normalized_metadata(logged, monkeypatch):
    raw = 'Some disor-\nders and thera-\npies.'
    doc = upload(logged, synthetic_pdf(['Some disor-', 'ders and thera-', 'pies.'])).json()
    async def fake(*args, **kwargs): return '[ISOLATED MOCK] example'
    monkeypatch.setattr(translations, 'translate_text', fake)
    translated = logged.post('/api/v1/documents/' + doc['id'] + '/translations', json={
        'text': raw, 'sourceLanguage': 'en', 'targetLanguage': 'zh', 'pageNumber': 1, 'contextRevision': 4}).json()
    assert translated['modelInputText'] == 'Some disorders and therapies.' and translated['normalizationCount'] == 2
    body = payload(doc, kind='translation_excerpt', originalText=raw, translatedText=translated['translatedText'],
        sourceLanguage='en', targetLanguage='zh', translationProof=translated['translationProof'],
        modelInputText=translated['modelInputText'], normalizationCount=translated['normalizationCount'])
    altered = deepcopy(body); altered['source']['normalizationCount'] = 1
    assert_error(send(logged, altered), 'TRANSLATION_PROOF_INVALID')
    saved = send(logged, body)
    assert saved.status_code == 201, saved.text
    block = saved.json()['note']['sources'][0]
    assert block['originalText'] == raw and block['modelInputText'] == translated['modelInputText']


def test_dual_ownership_csrf_and_owner_bound_receipt(logged, document, monkeypatch):
    note = create(logged)
    body = translated_payload(logged, document, monkeypatch, note)
    assert send(logged, body).status_code == 201
    assert logged.post('/api/v1/notes/captures', json=payload(document), headers={'X-CSRF-Token': 'bad'}).status_code == 403
    with TestClient(app, headers={'Origin': 'http://localhost:8080'}) as other:
        assert other.post('/api/v1/notes/captures', json=body).status_code == 401
        register(other, 'capture-other@example.com')
        other.headers['X-CSRF-Token'] = login(other, 'capture-other@example.com').json()['csrfToken']
        own = upload(other, synthetic_pdf([TEXT]), 'Other owned.pdf').json()
        assert send(other, body).status_code == 404
        target = create(other)
        source_attack = payload(document, target)
        assert send(other, source_attack).status_code == 404
        receipt_attack = deepcopy(body)
        receipt_attack.update(noteId=target['id'], version=target['version'], operationId=str(uuid4()))
        receipt_attack['source']['documentId'] = own['id']
        assert_error(send(other, receipt_attack), 'TRANSLATION_PROOF_INVALID')
    assert logged.get('/api/v1/notes/' + note['id']).json()['version'] == 2


def test_unreliable_missing_file_errors_are_sanitized(logged, document, monkeypatch):
    def failure(*args, **kwargs): raise OSError('private filesystem detail')
    monkeypatch.setattr(note_captures, 'storage_path', failure)
    response = send(logged, payload(document))
    assert_error(response, 'PDF_UNAVAILABLE')
    assert 'private filesystem' not in response.text and 'Traceback' not in response.text


def test_concurrent_identical_capture_is_one_block_and_safe_replay(logged, document):
    note = create(logged)
    body = payload(document, note)
    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(pool.map(lambda unused: send(logged, body), range(2)))
    assert sorted(response.status_code for response in responses) == [200, 201], [r.text for r in responses]
    current = logged.get('/api/v1/notes/' + note['id']).json()
    assert current['version'] == 2 and len(current['sources']) == 1


def test_capture_closes_read_snapshot_then_locks_document_before_note(logged, document, monkeypatch):
    # SQLite cannot reproduce InnoDB REPEATABLE READ. Verify the transaction
    # boundary/order which prevents an old read snapshot surviving lock waits.
    note = create(logged)
    events = []
    seen = set()
    real_replay = note_captures.existing_capture
    real_document = note_captures.owned_document
    real_note = note_captures.owned_note

    def replay(db, *args):
        events.append('probe')
        result = real_replay(db, *args)
        if id(db) not in seen:
            seen.add(id(db))
            assert db.in_transaction()
            real_rollback = db.rollback
            real_get = db.get

            def rollback():
                events.append('rollback')
                return real_rollback()

            def get(entity, *values, **kwargs):
                # No unlocked Note read may establish a new snapshot between
                # the document and note locks on the existing-note path.
                if entity is Note and events[-1:] == ['document-lock']:
                    raise AssertionError('Unlocked note read before note lock')
                return real_get(entity, *values, **kwargs)

            monkeypatch.setattr(db, 'rollback', rollback)
            monkeypatch.setattr(db, 'get', get)
        return result

    def document_lock(db, *args, **kwargs):
        assert kwargs.get('lock') is True
        assert events[-1] == 'rollback' and not db.in_transaction()
        item = real_document(db, *args, **kwargs)
        events.append('document-lock')
        return item

    def note_lock(db, *args, **kwargs):
        assert kwargs.get('lock') is True and events[-1] == 'document-lock'
        item = real_note(db, *args, **kwargs)
        events.append('note-lock')
        return item

    monkeypatch.setattr(note_captures, 'existing_capture', replay)
    monkeypatch.setattr(note_captures, 'owned_document', document_lock)
    monkeypatch.setattr(note_captures, 'owned_note', note_lock)
    body = payload(document, note)
    body['associationMode'] = 'link'
    response = send(logged, body)
    assert response.status_code == 201, response.text
    assert events == ['probe', 'rollback', 'document-lock', 'note-lock', 'probe']
    assert response.json()['note']['documents'] == [{'id': document['id'], 'title': document['title']}]
    assert response.json()['note']['content'] == note['content']


def test_concurrent_identical_new_note_capture_returns_one_created_and_replay(logged, document):
    body = payload(document)
    body['associationMode'] = 'link'
    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(pool.map(lambda unused: send(logged, body), range(2)))
    assert sorted(response.status_code for response in responses) == [200, 201], [r.text for r in responses]
    current = logged.get('/api/v1/notes/' + body['noteId']).json()
    assert current['version'] == 1 and len(current['sources']) == 1
    assert current['documents'] == [{'id': document['id'], 'title': document['title']}]
    with SessionLocal() as db:
        assert db.scalar(select(func.count()).select_from(Note)) == 1
        assert db.scalar(select(func.count()).select_from(NoteDocument)) == 1
