"""Explicit offline mode for an administrator-enabled isolated acceptance site."""
from .ai_service import ModelFailure
from .config import get_settings

async def translate_mock(text,source,target):
    if not get_settings().translation_mock_enabled:
        raise ModelFailure('MOCK_DISABLED','此环境未启用模拟翻译',403)
    direction='英译中' if (source,target)==('en','zh') else '中译英'
    return f'【隔离 Mock，非真实模型译文；{direction}】\n{text}'
