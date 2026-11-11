"""SEC-07 audit logger.

Single entry point ``log_audit`` -- builds the seven-column event, JSON-dumps
it (which handles escaping), truncates the payload to 4096 bytes so we don't
log megabyte-sized answers, and inserts one row into ``audit_logs``.

Never raises from audit failures.  The whole point is that audit must not
block or break the primary operation path.  If the insert fails we log to
stderr and move on.
"""
from __future__ import annotations

import json
import logging
import re
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select

from .database import SessionLocal
from .models import AuditLog, LoginSession
from .security import token_hash

logger = logging.getLogger("audit")

# MySQL JSON column max is 1GB but we want lines that a human can grep.
# 4096 bytes holds a full answer text with citations; beyond that the
# answer itself goes into qa_answers/qa_chunks so we only need the gist
# for audit.
_PAYLOAD_MAX_BYTES = 4096


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _truncate(obj: Any, max_bytes: int = _PAYLOAD_MAX_BYTES) -> Any:
    """Recursively truncate long string values inside a JSON-serialisable
    object.  Returns a shallow-ish copy where every long string has been
    snipped to ``max_bytes`` UTF-8 bytes max.
    """
    if isinstance(obj, str):
        encoded = obj.encode("utf-8")
        if len(encoded) > max_bytes:
            # decode back to UTF-8, cutting at a valid character boundary
            cut = encoded[:max_bytes]
            # strip trailing partial multi-byte chars
            while cut and cut[-1] & 0xC0 == 0x80:
                cut = cut[:-1]
            return cut.decode("utf-8") + "...[truncated]"
        return obj
    if isinstance(obj, list):
        return [_truncate(item, max_bytes) for item in obj]
    if isinstance(obj, dict):
        return {k: _truncate(v, max_bytes) for k, v in obj.items()}
    return obj


def _build_payload(
    *,
    action: str,
    target: str,
    status: str,
    user_id: str | None = None,
    skill: str | None = None,
    duration_ms: int | None = None,
    tokens_in: int | None = None,
    tokens_out: int | None = None,
    model: str | None = None,
    error_code: str | None = None,
    extra: dict | None = None,
) -> dict:
    """Assemble the canonical seven-column event dict.  Fields beyond the
    seven columns go into ``usage.extra`` so the row stays compact but
    detail is preserved.
    """
    usage: dict[str, Any] = {}
    if duration_ms is not None:
        usage["duration_ms"] = duration_ms
    if tokens_in is not None:
        usage["tokens_in"] = tokens_in
    if tokens_out is not None:
        usage["tokens_out"] = tokens_out
    if model:
        usage["model"] = model
    if error_code:
        usage["error_code"] = error_code
    if extra:
        usage["extra"] = extra

    # Canonical event shape (always UTC ISO string for created_at so payload
    # is JSON round-trippable without TZ ambiguity).
    return {
        "user_id": user_id,
        "created_at": _now().isoformat(timespec="microseconds") + "Z",
        "action": action,
        "target": target,
        "status": status,
        "skill": skill,
        "usage": usage,
    }


def log_audit(
    *,
    action: str,
    target: str,
    status: str,
    user_id: str | None = None,
    skill: str | None = None,
    duration_ms: int | None = None,
    tokens_in: int | None = None,
    tokens_out: int | None = None,
    model: str | None = None,
    error_code: str | None = None,
    extra: dict | None = None,
) -> None:
    """Write one audit row.  Safe to call from any process (api / worker / CLI).

    Never raises.  If the DB is down, the insert simply doesn't happen.

    Args map to the seven SEC-07 columns:
      user_id    -> 操作人
      created_at -> 自动取 UTC now()
      action     -> 操作类型 (extract / qa_ask / translate / upload / ...)
      target     -> 操作对象 (document_id / note_id / annotation_id)
      status     -> 结果状态 (success / failed / partial / skipped)
      skill      -> 技能标识 (extract-llm / qa-rag / translate / ...)
      usage      -> 用量与耗时 (duration_ms, tokens_in, tokens_out, model, error_code, extra)
    """
    payload = _truncate(_build_payload(
        action=action, target=target, status=status,
        user_id=user_id, skill=skill, duration_ms=duration_ms,
        tokens_in=tokens_in, tokens_out=tokens_out, model=model,
        error_code=error_code, extra=extra,
    ))
    try:
        db = SessionLocal()
        try:
            row = AuditLog(
                id=str(uuid.uuid4()),
                user_id=user_id,
                created_at=_now(),
                action=action,
                target=target,
                status=status,
                skill=skill,
                duration_ms=duration_ms,
                usage=payload["usage"] if payload["usage"] else None,
                payload=payload,
            )
            db.add(row)
            db.commit()
        finally:
            db.close()
    except Exception as exc:
        # Audit must never block the primary path.  Log and drop.
        logger.warning("audit insert failed: %s", exc)
        try:
            logger.warning("payload that failed: %s", json.dumps(payload, ensure_ascii=False)[:400])
        except Exception:
            pass


_UUID_RE = re.compile(
    r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}")


def resolve_session_user_id(session_token: str | None) -> str | None:
    """Resolve a session cookie value to a user_id, server-side only.

    Never raises.  Returns None for missing / invalid / expired sessions.
    """
    if not session_token or len(session_token) > 128:
        return None
    try:
        db = SessionLocal()
        try:
            s = db.scalar(select(LoginSession).where(
                LoginSession.token_hash == token_hash(session_token)))
            if not s or s.revoked_at or s.expires_at <= _now():
                return None
            return s.user_id
        finally:
            db.close()
    except Exception as exc:
        logger.warning("denied-audit session lookup failed: %s", exc)
        return None


def log_denied_request(*, method: str, path: str, http_status: int,
                       session_token: str | None) -> None:
    """Write one ``denied`` audit row for a rejected API request.

    Called from the request middleware for 401/403/404 responses under
    /api/v1.  user_id is resolved from the session cookie server-side;
    unauthenticated denials get user_id=None.  Never raises.
    """
    match = _UUID_RE.search(path)
    target = match.group(0) if match else "-"
    parts = [p for p in path.split("/") if p]  # ['api', 'v1', 'documents', ...]
    resource = parts[2] if len(parts) > 2 else (parts[-1] if parts else "unknown")
    log_audit(
        action=f"{resource}.{method.lower()}"[:32],
        target=target,
        status="denied",
        user_id=resolve_session_user_id(session_token),
        extra={"method": method, "path": path[:200], "http_status": http_status},
    )
