"""Create an external AES-256 key file exclusively; never print key material."""
import argparse,base64,os,secrets
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

def create_key(output):
    path=Path(output).expanduser().absolute()
    if path.resolve().is_relative_to(ROOT.resolve()):raise ValueError('Keep the master key outside the Git repository and Docker build contexts')
    if not path.parent.is_dir():raise ValueError('Create the private parent directory first')
    with os.fdopen(os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|getattr(os,'O_BINARY',0),0o600),'wb') as stream:
        stream.write(base64.urlsafe_b64encode(secrets.token_bytes(32))+b'\n')
    return path

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--output',required=True)
    try:create_key(parser.parse_args().output)
    except (OSError,ValueError):raise SystemExit('Key file creation refused; check destination and existing file. Nothing overwritten.') from None
    print('External master key created. Content was not printed. Back it up separately and never overwrite it.')
