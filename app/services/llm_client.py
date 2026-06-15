"""真实 LLM 客户端（Gemini via google-genai）——agent-demo 自包含实现。

设计要点（与  解耦，仅复刻其调用方式，不 import 其代码）：
  - 多 key 轮询（RR）：N 个 key 负载均衡，单 key 失败自动切下一个；
  - 结构化输出：``response_schema`` 传 Pydantic 模型，Gemini 直出可解析 JSON；
  - SDK 是同步的，全部放入 ``asyncio.to_thread``，不阻塞事件循环；
  - Vertex AI 企业版：``genai.Client(api_key=..., vertexai=True)``。
"""
from __future__ import annotations

import asyncio
import json
import re
from typing import Any

from loguru import logger

from app.core.config import settings

_clients: dict[int, Any] = {}  # key_idx -> genai.Client（懒加载缓存）
_rr_lock = asyncio.Lock()
_rr_idx: int = -1


def _get_client(key_idx: int):
    client = _clients.get(key_idx)
    if client is not None:
        return client
    from google import genai

    keys = settings.google_api_keys_list
    api_key = keys[key_idx]
    if settings.GEMINI_BACKEND == "vertex_ai":
        client = genai.Client(api_key=api_key, vertexai=True)
        logger.info("Gemini 客户端初始化（Vertex AI）key#{}/{} model={}",
                    key_idx, len(keys), settings.LLM_MODEL)
    else:
        client = genai.Client(api_key=api_key)
        logger.info("Gemini 客户端初始化（AI Studio）key#{}/{}", key_idx, len(keys))
    _clients[key_idx] = client
    return client


async def _next_key_index() -> int:
    global _rr_idx
    keys = settings.google_api_keys_list
    async with _rr_lock:
        _rr_idx = (_rr_idx + 1) % len(keys)
        return _rr_idx


def _safe_extract_json(raw: str) -> dict[str, Any]:
    """模型偶尔包裹 ```json ``` 或夹带说明文字时的兜底解析。"""
    m = re.search(r"\{.*\}", raw, re.S)
    if m:
        return json.loads(m.group(0))
    raise ValueError(f"无法从响应中解析 JSON：{raw[:200]}")


async def generate_json(
    system: str,
    user: str,
    *,
    response_schema: type | None = None,
    model: str | None = None,
) -> dict[str, Any]:
    """调用 Gemini 生成结构化 JSON，返回 dict。多 key 轮询兜底。"""
    keys = settings.google_api_keys_list
    if not keys:
        raise RuntimeError("未配置 GOOGLE_API_KEYS，无法调用真实 LLM")
    use_model = model or settings.LLM_MODEL

    def _sync_call(key_idx: int) -> dict[str, Any]:
        from google.genai import types

        config = types.GenerateContentConfig(
            system_instruction=system,
            response_mime_type="application/json",
            response_schema=response_schema,
            thinking_config=types.ThinkingConfig(
                thinking_level=settings.LLM_THINKING_LEVEL
            ),
            max_output_tokens=65536,
        )
        client = _get_client(key_idx)
        resp = client.models.generate_content(
            model=use_model, contents=user, config=config
        )
        raw = resp.text or ""
        logger.debug("Gemini 响应 {} chars (key#{})", len(raw), key_idx)
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return _safe_extract_json(raw)

    last_err: Exception | None = None
    tried: set[int] = set()
    while len(tried) < len(keys):
        idx = await _next_key_index()
        if idx in tried:
            continue
        tried.add(idx)
        try:
            return await asyncio.to_thread(_sync_call, idx)
        except Exception as exc:  # noqa: BLE001 - 逐 key 兜底
            last_err = exc
            logger.warning("Gemini key#{} 调用失败，尝试下一个 key：{}", idx, exc)
    raise RuntimeError(f"所有 Gemini key 均失败：{last_err}")
