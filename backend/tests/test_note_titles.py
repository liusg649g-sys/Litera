from concurrent.futures import ThreadPoolExecutor
from test_notes import note_payload, documents
from test_documents import logged, pdf

def test_title_scope_and_atomic_rename(logged,pdf):
 a,b=documents(logged,pdf)
 def create(doc,title):return logged.post('/api/v1/notes',json=note_payload(doc,title=title))
 n=create(a['id'],'Title').json()
 assert create(a['id'],' title ').json()['error']['code']=='NOTE_TITLE_DUPLICATE'
 other=create(b['id'],'TITLE').json()
 assert 'id' in other
 assert logged.put(f"/api/v1/notes/{other['id']}/documents/{a['id']}",json={}).status_code==409
 assert logged.patch('/api/v1/notes/'+n['id'],json={'version':n['version'],'title':'Title'}).status_code==200
 x=create(a['id'],'Other').json()
 before=logged.get('/api/v1/notes/'+x['id']).json()
 assert logged.patch('/api/v1/notes/'+x['id'],json={'version':x['version'],'title':'TITLE','content':'lost'}).status_code==409
 after=logged.get('/api/v1/notes/'+x['id']).json()
 assert after['version']==before['version'] and after['content']==before['content']

def test_multidocument_rename(logged,pdf):
 a,b=documents(logged,pdf)
 n=logged.post('/api/v1/notes',json=note_payload(a['id'],title='Shared')).json()
 assert logged.put(f"/api/v1/notes/{n['id']}/documents/{b['id']}",json={}).status_code==200
 assert logged.post('/api/v1/notes',json=note_payload(b['id'],title='Taken')).status_code==201
 assert logged.patch('/api/v1/notes/'+n['id'],json={'version':n['version'],'title':' taken '}).status_code==409

def test_concurrent_titles(logged,pdf):
 a,b=documents(logged,pdf)
 def create(_):return logged.post('/api/v1/notes',json=note_payload(a['id'],title='Concurrent')).status_code
 with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(create,range(2)))
 assert sorted(results)==[201,409]


def test_concurrent_rename_and_create(logged,pdf):
 a,b=documents(logged,pdf)
 n=logged.post('/api/v1/notes',json=note_payload(a['id'],title='Initial')).json()
 def write(kind):
  if kind==0:return logged.patch('/api/v1/notes/'+n['id'],json={'version':n['version'],'title':'Racing'}).status_code
  return logged.post('/api/v1/notes',json=note_payload(a['id'],title=' racing ')).status_code
 with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(write,range(2)))
 assert results.count(409)==1 and sum(x in (200,201) for x in results)==1
