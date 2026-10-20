"""Short-lived subprocess: bounded lifetime even if its API parent dies."""
import json
import os
from pathlib import Path
import sys
import threading
import time

import psutil
from .pdf_export_renderer import render, ExportError


def main():
    root=Path(sys.argv[1]);parent=psutil.Process(os.getppid());started=time.monotonic()
    def watchdog():
        while True:
            if not parent.is_running() or time.monotonic()-started>65:os._exit(70)
            time.sleep(.25)
    threading.Thread(target=watchdog,daemon=True).start()
    if sys.platform!='win32':
        import resource
        resource.setrlimit(resource.RLIMIT_FSIZE,(200*1024**2,200*1024**2))
        resource.setrlimit(resource.RLIMIT_CPU,(60,60))
    try:
        data=json.loads((root/'snapshot.json').read_text(encoding='utf-8'))
        render(root/'source.pdf',data['items'],{k:root/v for k,v in data['assets'].items()},root/'result.pdf',data['revision'])
    except ExportError as error:
        (root/'error.json').write_text(json.dumps(dict(code=error.code,message=error.message),ensure_ascii=False),encoding='utf-8');sys.exit(2)
    except Exception:
        (root/'error.json').write_text(json.dumps(dict(code='EXPORT_FAILED',message='PDF导出失败，请检查文献与图片资源后重试')),encoding='utf-8');sys.exit(1)


if __name__=='__main__':main()
