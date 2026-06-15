"""运行上下文（黑板 + 事件发射）。

- ``blackboard``：跨步骤共享的数据字典，key = StepMeta.outputs/inputs 声明的名字。
- ``emit``：把执行过程事件推给 SSE / 落库回调（执行引擎注入）。
"""
from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any


class RunContext:
    """单次流水线运行的只读上下文 + 黑板读写 + 事件发射。"""

    def __init__(
        self,
        run_id: int,
        blackboard: dict[str, Any],
        emit: Callable[..., Awaitable[None]],
        params: dict[str, Any] | None = None,
    ) -> None:
        self.run_id = run_id
        self.blackboard = blackboard
        self._emit = emit
        self.params = params or {}
        # 当前正在执行的 step_key（emit 时自动带上）
        self.current_step: str = ""

    def get(self, key: str, default: Any = None) -> Any:
        return self.blackboard.get(key, default)

    async def emit(self, event_type: str, **data: Any) -> None:
        """发射一条执行事件（agent 多轮、进度、日志都走这里）。"""
        payload = {"type": event_type, "step": self.current_step, **data}
        await self._emit(payload)
