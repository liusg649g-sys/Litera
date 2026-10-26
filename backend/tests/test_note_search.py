"""P3-C1 note search against the isolated pytest database only."""
from fastapi.testclient import TestClient

from app.database import SessionLocal
from app.main import app
from app.models import Note
from test_auth import login, register
from test_documents import logged, pdf
from test_notes import create, documents


def set_sources(note_id, sources):
    with SessionLocal() as db:
        item = db.get(Note, note_id)
        item.sources = sources
        db.commit()


def search(client, query, **params):
    return client.get('/api/v1/notes/search', params={'q': query, **params})


def assert_highlight(match, expected):
    value = match['snippet'][match['matchStart']:match['matchEnd']]
    assert value.casefold() == expected.casefold()


def test_searches_title_body_original_and_translation_without_relation_duplicates(logged, pdf):
    first, second = documents(logged, pdf)
    item = create(logged, first['id'], title='量子显微笔记',
                  content='Optical Microscopy supports live-cell research.')
    assert logged.put(f'/api/v1/notes/{item["id"]}/documents/{second["id"]}').status_code == 200
    set_sources(item['id'], [
        {'id': 'source-original', 'kind': 'pdf_excerpt', 'originalText': '细胞动力学原文摘录',
         'source': {'documentId': first['id'], 'pageNumber': 3}},
        {'id': 'source-translation', 'kind': 'translation_excerpt', 'originalText': 'Stable source text',
         'translatedText': '活细胞成像译文', 'source': {'documentId': second['id'], 'pageNumber': 7}},
    ])

    cases = [('量子', 'title'), ('mIcRoScOpY', 'content'), ('动力学', 'source_original'), ('成像译文', 'source_translation')]
    for query, field in cases:
        response = search(logged, query)
        assert response.status_code == 200, response.text
        page = response.json()
        assert page['query'] == query and page['total'] == 1 and len(page['items']) == 1
        result = page['items'][0]
        assert result['id'] == item['id'] and len(result['documents']) == 2
        assert 'content' not in result and 'sources' not in result
        match = next(match for match in result['matches'] if match['field'] == field)
        assert_highlight(match, query)
        if field.startswith('source_'):
            assert match['sourceBlockId'].startswith('source-')
            assert match['documentId'] in {first['id'], second['id']}
            assert match['pageNumber'] in {3, 7}


def test_search_is_private_literal_paginated_and_read_only(logged):
    literal = create(logged, title='Literal symbols', content='Keep 100%_safe [draft] "quoted" unchanged.')
    private = create(logged, title='PrivateAlpha', content='Owner-only phrase')
    before = logged.get('/api/v1/notes/' + literal['id']).json()

    percent = search(logged, '%_').json()
    assert percent['total'] == 1 and percent['items'][0]['id'] == literal['id']
    assert_highlight(percent['items'][0]['matches'][0], '%_')
    assert search(logged, "%_safe' OR 1=1 --").json()['total'] == 0
    assert search(logged, '   ').json() == {'items': [], 'query': '', 'page': 1, 'pageSize': 20, 'total': 0}
    assert logged.get('/api/v1/notes/' + literal['id']).json() == before

    page = search(logged, 'i', page=1, pageSize=1).json()
    assert page['pageSize'] == 1 and len(page['items']) == 1 and page['total'] == 2
    assert search(logged, 'i', page=2, pageSize=1).json()['items'][0]['id'] != page['items'][0]['id']

    with TestClient(app, headers={'Origin': 'http://localhost:8080'}) as other:
        assert other.get('/api/v1/notes/search', params={'q': 'PrivateAlpha'}).status_code == 401
        assert register(other, 'note-search-other@example.com').status_code == 201
        other.headers['X-CSRF-Token'] = login(other, 'note-search-other@example.com').json()['csrfToken']
        assert search(other, 'PrivateAlpha').json()['total'] == 0
        own = create(other, title='PrivateAlpha other owner')
        own_result = search(other, 'privatealpha').json()
        assert own_result['total'] == 1 and own_result['items'][0]['id'] == own['id']
    assert search(logged, 'PrivateAlpha').json()['items'][0]['id'] == private['id']


def test_search_rejects_ambiguous_or_oversized_queries(logged):
    create(logged, title='Validation note', content='Nothing should be changed')
    cases = [
        '/api/v1/notes/search?q=a&q=b',
        '/api/v1/notes/search?q=a&documentId=unexpected',
        '/api/v1/notes/search?q=' + ('x' * 101),
        '/api/v1/notes/search?q=a&pageSize=51',
        '/api/v1/notes/search?q=a&page=0',
    ]
    for url in cases:
        assert logged.get(url).status_code == 422
    assert logged.get('/api/v1/notes').json()['total'] == 1
