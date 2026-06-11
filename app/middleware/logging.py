"""日志中间件：为每个请求生成 trace_id，记录方法/路径/状态/耗时，并回写响应头。"""
import time
import uuid

from loguru import logger
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.core.context import set_trace_id

TRACE_HEADER = "X-Trace-Id"


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        trace_id = request.headers.get(TRACE_HEADER) or uuid.uuid4().hex
        set_trace_id(trace_id)

        client = request.client.host if request.client else "-"
        logger.info(f"--> {request.method} {request.url.path} from {client}")

        start = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            cost = (time.perf_counter() - start) * 1000
            logger.exception(
                f"<-- {request.method} {request.url.path} 异常 cost={cost:.2f}ms"
            )
            raise

        cost = (time.perf_counter() - start) * 1000
        response.headers[TRACE_HEADER] = trace_id
        response.headers["X-Process-Time-Ms"] = f"{cost:.2f}"
        logger.info(
            f"<-- {request.method} {request.url.path} "
            f"status={response.status_code} cost={cost:.2f}ms"
        )
        return response
