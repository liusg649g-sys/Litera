"""Review only Git delivery candidates. Never read ignored credentials or user data.
Writes path-only manifests and redacted findings; does not stage or commit.
"""
import argparse,fnmatch,hashlib,json,re,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
LOCAL_ONLY={'AGENTS.md':'本机协作规范包含固定交接路径，保留本地，不直接共享','LOCAL_DEVELOPMENT.md':'本机历史启动/数据说明，团队使用docs/delivery/deployment.md','compose.dev.yaml':'本机litera-dev隔离配置，不用于团队默认部署'}
PATTERNS={
 'provider-key':r'\bsk-[A-Za-z0-9_-]{20,}',
 'github-token':r'\b(?:gh[pousr]_[A-Za-z0-9]{25,}|github_pat_[A-Za-z0-9_]{25,})',
 'private-key':r'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----',
 'jwt':r'\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}'
}

def forbidden(name):
    path=Path(name);parts={x.lower() for x in path.parts};base=path.name.lower()
    if parts & {'.cache','.venv','node_modules','dist','storage','.secrets','test-results','playwright-report','litera-backups'}:return True
    if base.startswith('.env') and base!='.env.example':return True
    if base in {'session-secret','processes.json','import-verification.json'}:return True
    return any(fnmatch.fnmatch(base,pattern) for pattern in ['*.db*','*.sqlite*','*.pdf','*.key','*.pem','*.p12','*.pfx','*.bak','*.log','*.zip','*.vhdx','*.mp4','*.webm'])

def main(write=False):
    docs=ROOT/'docs/delivery';docs.mkdir(exist_ok=True)
    for name in ['commit-files.txt','excluded-files.md']:
        path=docs/name
        if not path.exists():path.touch()
    raw=subprocess.check_output(['git','ls-files','-m','-o','--exclude-standard','-z'],cwd=ROOT)
    names=sorted({x.decode('utf-8') for x in raw.split(b'\0') if x})
    candidates=[];blocked=[];findings=[];synthetic=[];sizes={};hashes={}
    for name in names:
        if name in LOCAL_ONLY:continue
        if forbidden(name):blocked.append(name);continue
        path=ROOT/name
        if not path.is_file():blocked.append(name);continue
        sizes[name]=path.stat().st_size
        if sizes[name]>2_000_000:blocked.append(name);continue
        try:content=path.read_text(encoding='utf-8')
        except UnicodeError:blocked.append(name);continue
        for number,line in enumerate(content.splitlines(),1):
            for kind,pattern in PATTERNS.items():
                if re.search(pattern,line):findings.append(dict(path=name,line=number,kind=kind))
            # Inspect literal assignments too; synthetic fixtures are listed separately.
            assignment=re.search(r"(?i)(?<![\w:-])(?:AI_API_KEY|API_KEY|SESSION_SECRET|MYSQL_PASSWORD|MYSQL_ROOT_PASSWORD|PASSWORD|TOKEN|ACCESS_TOKEN|SECRET)\s*[:=]\s*['\"]([^'\"]+)['\"]",line) or re.search(r"(?<![\w:-])KEY\s*=\s*['\"]([^'\"]+)['\"]",line)
            if assignment and name.endswith('.vue') and line[:assignment.start()].rstrip().endswith(':'):assignment=None
            if assignment:
                value=assignment.group(1)
                fixture=('/tests/' in name or '/e2e/' in name or name.endswith('_e2e_server.py') or name in {'scripts/e2e_server.py','scripts/mock_answer_fixture.py','scripts/mock_translation_fixture.py'})
                placeholder=any(word in value.lower() for word in ('synthetic','fixture','isolated','test-only','your_','your-','<','${'))
                entry=dict(path=name,line=number,kind='literal-credential-assignment')
                if fixture or placeholder:synthetic.append(entry)
                else:findings.append(entry)

        hashes[name]=hashlib.sha256(path.read_bytes()).hexdigest();candidates.append(name)
    # Verify exclusion for representative runtime/secret paths without opening them.
    ignored={}
    for name in ['backend/.env','.env.private','backend/private.key','.cache/user-model-preview/unified/preview.db','frontend/dist/index.html','backend/test.db-journal']:
        ignored[name]=subprocess.run(['git','check-ignore','-q',name],cwd=ROOT).returncode==0
    result=dict(candidateCount=len(candidates),candidateBytes=sum(sizes.values()),candidates=candidates,localOnly=LOCAL_ONLY,blocked=blocked,secretFindings=findings,syntheticAssignments=synthetic,ignored=ignored,hashes=hashes,scope='Pending Git files only; patterns/manifest review are not a full-history secret or penetration audit')
    dest=ROOT/'.cache/github-delivery';dest.mkdir(parents=True,exist_ok=True)
    (dest/'security-audit.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    if blocked or findings or not all(ignored.values()):
        print(json.dumps({k:result[k] for k in ['blocked','secretFindings','ignored']},ensure_ascii=False));raise SystemExit('Review required; no staging/commit performed')
    if write:
        (docs/'commit-files.txt').write_text(''.join(name+'\n' for name in candidates),encoding='utf-8')
        text='# 不应提交的文件\n\n以下保留在本机，不删除：\n\n'+''.join('- `'+name+'`：'+reason+'。\n' for name,reason in LOCAL_ONLY.items())
        text+='\n已由忽略规则排除：真实.env及变体、数据库与伴随文件、PDF/图片storage、.cache、会话文件、用户密文备份/主密钥文件、node_modules、venv、dist、日志/录屏/测试输出、现有冷备和其他项目。只审查Git候选，不读取上述私有文件。\n\n不要git add .或git add -A；获最终批准后按commit-files.txt明确暂存，并重新检查暂存区。扫描是模式检查与文件审阅，不宣称全历史/渗透测试。\n'
        (docs/'excluded-files.md').write_text(text,encoding='utf-8')
    result['hashes']={name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in candidates}
    result['candidateBytes']=sum((ROOT/name).stat().st_size for name in candidates)
    (dest/'security-audit.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    runtime=[name for name in candidates if not name.startswith(('docs/','openspec/')) and name not in {'README.md','HANDOFF.md'}]
    documents=[name for name in candidates if name not in runtime]
    (dest/'commit-runtime.txt').write_text(''.join(name+'\n' for name in runtime),encoding='utf-8')
    (dest/'commit-docs.txt').write_text(''.join(name+'\n' for name in documents),encoding='utf-8')
    print(json.dumps(dict(candidates=len(candidates),bytes=result['candidateBytes'],localOnly=len(LOCAL_ONLY),blocked=0,secretFindings=0,ignored=ignored,writeManifest=write),ensure_ascii=False))

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--write-manifest',action='store_true');main(parser.parse_args().write_manifest)
