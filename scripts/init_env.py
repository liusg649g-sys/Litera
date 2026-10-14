"""Generate local secrets without overwriting an existing environment file."""
from pathlib import Path
import secrets
root = Path(__file__).resolve().parent.parent
target = root / ".env"
if target.exists():
    print(".env already exists; left unchanged.")
else:
    text = (root / ".env.example").read_text(encoding="utf-8")
    for name in ("MYSQL_PASSWORD", "MYSQL_ROOT_PASSWORD", "SESSION_SECRET"):
        text = text.replace(name + "=\n", name + "=" + secrets.token_hex(32) + "\n")
    target.write_text(text, encoding="utf-8")
    print("Created local .env with generated secrets. Do not commit this file.")
