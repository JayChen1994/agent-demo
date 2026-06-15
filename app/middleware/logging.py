"""日志中间件：为每个请求生成 trace_id，记录方法/路径/状态/耗时，并回写响应头。

实现为「纯 ASGI 中间件」而非 BaseHTTPMiddleware：
后者会缓冲流式响应（StreamingResponse / SSE），导致事件无法实时下发；
纯 ASGI 透传 send/receive，天然支持 SSE 实时推流。
"""
import time
import uuid

from loguru import logger

from app.core.context import set_trace_id

TRACE_HEADER = "X-Trace-Id"


class RequestLoggingMiddleware:
    def __init__(self, app) -> None:
        self.app = app

    async def __call__(self, scope, receive, send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        headers = dict(scope.get("headers") or [])
        trace_id = (
            headers.get(TRACE_HEADER.lower().encode(), b"").decode() or uuid.uuid4().hex
        )
        set_trace_id(trace_id)

        method = scope.get("method", "-")
        path = scope.get("path", "-")
        client = scope.get("client")
        chost = client[0] if client else "-"
        logger.info(f"--> {method} {path} from {chost}")

        start = time.perf_counter()
        status_code = {"value": 0}

        async def send_wrapper(message) -> None:
            if message["type"] == "http.response.start":
                status_code["value"] = message["status"]
                cost = (time.perf_counter() - start) * 1000
                raw = message.setdefault("headers", [])
                raw.append((TRACE_HEADER.encode(), trace_id.encode()))
                raw.append((b"x-process-time-ms", f"{cost:.2f}".encode()))
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        except Exception:
            cost = (time.perf_counter() - start) * 1000
            logger.exception(f"<-- {method} {path} 异常 cost={cost:.2f}ms")
            raise
        cost = (time.perf_counter() - start) * 1000
        logger.info(
            f"<-- {method} {path} status={status_code['value']} cost={cost:.2f}ms"
        )
