"""Request-local numeric diagnostics and bounded disconnect cancellation.
No texts, document/user IDs, URLs, credentials or upstream bodies are logged.
"""
import asyncio
from contextvars import ContextVar
from dataclasses import dataclass, field
from functools import wraps
import logging
import time
from fastapi import HTTPException

@dataclass
class TranslationTiming:
    started: float = field(default_factory=time.perf_counter)
    pdf_ms: float = 0
    gateway_ms: float = 0
    gateway_status: int | None = None
    gateway_calls: int = 0

    def headers(self):
        total = (time.perf_counter() - self.started) * 1000
        return {'Server-Timing': f'translation;dur={total:.2f}, pdf;dur={self.pdf_ms:.2f}, gateway;dur={self.gateway_ms:.2f}',
                'X-Translation-Gateway-Status': str(self.gateway_status or 0)}

current_timing: ContextVar[TranslationTiming | None] = ContextVar('translation_timing', default=None)

async def run_connected(request, operation):
    # FastAPI has consumed the JSON body. This is the only receive consumer while
    # the model runs; no polling, retries, queue or timeout extension is added.
    async def disconnected():
        while True:
            message = await request.receive()
            if message['type'] == 'http.disconnect': return
    work = asyncio.ensure_future(operation)
    watcher = asyncio.create_task(disconnected())
    try:
        done, _ = await asyncio.wait((work, watcher), return_when=asyncio.FIRST_COMPLETED)
        if work in done: return await work
        # Propagate an actual watcher error instead of silently hiding it.
        await watcher
        raise HTTPException(499, detail={'code':'TRANSLATION_CANCELLED','message':'翻译请求已取消'})
    finally:
        for task in (work, watcher):
            if not task.done(): task.cancel()
        await asyncio.gather(work, watcher, return_exceptions=True)

def observed_translation(function):
    @wraps(function)
    async def wrapped(*args, **kwargs):
        metrics = TranslationTiming(); token = current_timing.set(metrics)
        status, code = 200, 'OK'
        request, response = kwargs.get('request'), kwargs.get('response')
        try:
            result = await function(*args, **kwargs)
            response.headers.update(metrics.headers())
            return result
        except HTTPException as error:
            status = error.status_code
            code = error.detail.get('code','HTTP_ERROR') if isinstance(error.detail,dict) else 'HTTP_ERROR'
            error.headers = {**(error.headers or {}), **metrics.headers()}
            raise
        except asyncio.CancelledError:
            status, code = 499, 'TRANSLATION_CANCELLED'
            raise
        except Exception:
            status, code = 500, 'INTERNAL_ERROR'
            raise
        finally:
            logging.getLogger('uvicorn.error').info(
                'translation_metrics request=%s status=%d code=%s handler_ms=%.2f pdf_ms=%.2f gateway_ms=%.2f upstream_status=%s gateway_calls=%d',
                getattr(getattr(request,'state',None),'request_id','-'),status,code,
                (time.perf_counter()-metrics.started)*1000,metrics.pdf_ms,metrics.gateway_ms,
                metrics.gateway_status if metrics.gateway_status is not None else '-',metrics.gateway_calls)
            current_timing.reset(token)
    return wrapped
