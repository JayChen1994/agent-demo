"""真实生图客户端（portrait_gen 网关）——agent-demo 自包含实现。

与  解耦，仅复刻网关 HTTP 协议（不 import 其代码）：
  - 提交：``POST {base}/api/v2/generate_image``（header ``gpus_id: 1``），
    body 含 ``model_id/provider/model/positive_prompt/...``，返回 ``data.task_id``；
  - 轮询：``GET {base}/api/v2/task/{task_id}/download?model_id=...``，
    ``data.status`` ∈ ``pending/running/done/failed/timeout/not_found``，
    ``done`` 时取 ``data.images[0]``。
  - 并发：进程内 ``asyncio.Semaphore`` 限流（替代 platform 的跨 Pod Redis 信号量）。
"""
from __future__ import annotations

import asyncio

import httpx
from loguru import logger

from app.core.config import settings

_HEADERS = {"gpus_id": "1"}
_POLL_INTERVAL = 5.0
_POLL_INITIAL_DELAY = 8.0
_sem: asyncio.Semaphore | None = None


def _semaphore() -> asyncio.Semaphore:
    global _sem
    if _sem is None:
        _sem = asyncio.Semaphore(settings.IMAGE_GEN_CONCURRENCY)
    return _sem


async def _submit(
    positive_prompt: str,
    negative_prompt: str = "(low quality, worst quality:1.4)",
    width: int | None = None,
    height: int | None = None,
    steps: int = 20,
    cfg: float = 2.0,
) -> str:
    base = settings.PORTRAIT_GEN_BASE_URL.rstrip("/")
    payload = {
        "model_id": settings.PORTRAIT_GEN_MODEL_ID,
        "provider": settings.PORTRAIT_GEN_PROVIDER,
        "model": settings.PORTRAIT_GEN_MODEL,
        "positive_prompt": positive_prompt,
        "negative_prompt": negative_prompt,
        "width": width or settings.IMAGE_WIDTH,
        "height": height or settings.IMAGE_HEIGHT,
        "lora_uuid": "",
        "steps": steps,
        "cfg": cfg,
    }
    url = f"{base}/api/v2/generate_image"
    async with httpx.AsyncClient(timeout=30.0, trust_env=False, headers=_HEADERS) as c:
        resp = await c.post(url, json=payload)
    resp.raise_for_status()
    body = resp.json()
    data = body.get("data") or {}
    task_id = data.get("task_id") or body.get("task_id")
    if not task_id:
        raise RuntimeError(f"generate_image 未返回 task_id：{str(body)[:200]}")
    logger.info("portrait_gen 已提交 task_id={}", task_id)
    return str(task_id)


async def _poll(task_id: str, timeout_sec: float | None = None) -> str:
    base = settings.PORTRAIT_GEN_BASE_URL.rstrip("/")
    url = f"{base}/api/v2/task/{task_id}/download"
    params = {"model_id": settings.PORTRAIT_GEN_MODEL_ID}
    deadline = asyncio.get_event_loop().time() + (
        timeout_sec or settings.IMAGE_GEN_TIMEOUT_SEC
    )
    await asyncio.sleep(_POLL_INITIAL_DELAY)
    async with httpx.AsyncClient(timeout=15.0, trust_env=False, headers=_HEADERS) as c:
        while True:
            try:
                resp = await c.get(url, params=params)
                resp.raise_for_status()
                data = resp.json().get("data") or {}
                status = data.get("status", "")
                if status == "done":
                    images = data.get("images") or []
                    if images:
                        logger.info("image_gen ✓ 完成 task_id={} url={}", task_id, images[0])
                        return str(images[0])
                    files = data.get("files") or []
                    if files and files[0].get("url"):
                        return str(files[0]["url"])
                    raise RuntimeError(f"task {task_id} done 但无图片 URL")
                if status in ("failed", "timeout", "not_found"):
                    raise RuntimeError(
                        f"task {task_id} 状态={status} err={data.get('err_msg', '')}"
                    )
            except httpx.RequestError as e:
                logger.warning("portrait_gen 轮询网络错误（继续重试）：{}", e)
            if asyncio.get_event_loop().time() > deadline:
                raise TimeoutError(f"image task {task_id} 超时")
            await asyncio.sleep(_POLL_INTERVAL)


async def generate_image(positive_prompt: str, **kwargs) -> str:
    """文生图：提交 + 轮询，返回首图 URL。进程内信号量限流。"""
    if not settings.PORTRAIT_GEN_BASE_URL:
        raise RuntimeError("未配置 PORTRAIT_GEN_BASE_URL，无法调用真实生图")
    async with _semaphore():
        task_id = await _submit(positive_prompt, **kwargs)
        return await _poll(task_id)
