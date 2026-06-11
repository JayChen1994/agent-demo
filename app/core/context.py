"""请求级上下文：用 ContextVar 在整条调用链中透传 trace_id。"""
from contextvars import ContextVar

trace_id_ctx: ContextVar[str] = ContextVar("trace_id", default="-")


def get_trace_id() -> str:
    return trace_id_ctx.get()


def set_trace_id(value: str) -> None:
    trace_id_ctx.set(value)
