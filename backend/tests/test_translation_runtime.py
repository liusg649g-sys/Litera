"""Lifecycle tests with queued ASGI messages and Mock model coroutines only.

Run with --noconftest for this pure unit module to avoid the API suite's
unrelated automatic temporary-database fixtures.
"""
import asyncio
import pytest
from fastapi import HTTPException
from app.ai_service import ModelFailure
from app.translation_runtime import run_connected


class QueuedRequest:
    def __init__(self):
        self.messages = asyncio.Queue()
        self.started = asyncio.Event()
        self.second_receive = asyncio.Event()
        self.cancelled = asyncio.Event()
        self.calls = 0

    async def receive(self):
        self.calls += 1
        self.started.set()
        if self.calls >= 2:
            self.second_receive.set()
        try:
            return await self.messages.get()
        except asyncio.CancelledError:
            self.cancelled.set()
            raise


def run(scenario):
    # A failed cancellation contract must fail promptly, not hang the suite.
    return asyncio.run(asyncio.wait_for(scenario, timeout=2))


def test_disconnect_cancels_and_awaits_model_cleanup():
    async def scenario():
        request = QueuedRequest()
        started, cleaned = asyncio.Event(), asyncio.Event()
        model_tasks = []
        async def model():
            model_tasks.append(asyncio.current_task())
            started.set()
            try:
                await asyncio.Event().wait()
            finally:
                # Prove run_connected waits for asynchronous cleanup to finish.
                await asyncio.sleep(0)
                cleaned.set()
        task = asyncio.create_task(run_connected(request, model()))
        await started.wait()
        await request.started.wait()
        request.messages.put_nowait({'type': 'http.disconnect'})
        with pytest.raises(HTTPException) as error:
            await task
        assert error.value.status_code == 499
        assert error.value.detail['code'] == 'TRANSLATION_CANCELLED'
        assert cleaned.is_set()
        assert model_tasks[0].done() and model_tasks[0].cancelled()
    run(scenario())


def test_model_success_cancels_the_pending_disconnect_watcher():
    async def scenario():
        request = QueuedRequest()
        async def model():
            await request.started.wait()
            return 'Mock translated text'
        assert await run_connected(request, model()) == 'Mock translated text'
        assert request.cancelled.is_set()
    run(scenario())


def test_model_failure_is_preserved_and_watcher_is_cancelled():
    async def scenario():
        request = QueuedRequest()
        failure = ModelFailure('MODEL_QUOTA', 'safe Mock quota error', 429)
        async def model():
            await request.started.wait()
            raise failure
        with pytest.raises(ModelFailure) as error:
            await run_connected(request, model())
        assert error.value is failure
        assert request.cancelled.is_set()
    run(scenario())


def test_outer_task_cancellation_leaves_no_model_or_watcher_running():
    async def scenario():
        request = QueuedRequest()
        started, cleaned = asyncio.Event(), asyncio.Event()
        model_tasks = []
        async def model():
            model_tasks.append(asyncio.current_task())
            started.set()
            try:
                await asyncio.Event().wait()
            finally:
                await asyncio.sleep(0)
                cleaned.set()
        task = asyncio.create_task(run_connected(request, model()))
        await started.wait()
        await request.started.wait()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert cleaned.is_set() and request.cancelled.is_set()
        assert model_tasks[0].done() and model_tasks[0].cancelled()
    run(scenario())


def test_non_disconnect_asgi_message_keeps_waiting_for_actual_disconnect():
    async def scenario():
        request = QueuedRequest()
        cleaned = asyncio.Event()
        async def model():
            try:
                await asyncio.Event().wait()
            finally:
                cleaned.set()
        request.messages.put_nowait({'type': 'http.request', 'body': b'', 'more_body': False})
        task = asyncio.create_task(run_connected(request, model()))
        await request.second_receive.wait()
        assert not task.done() and not cleaned.is_set()
        request.messages.put_nowait({'type': 'http.disconnect'})
        with pytest.raises(HTTPException) as error:
            await task
        assert error.value.status_code == 499 and cleaned.is_set()
    run(scenario())
