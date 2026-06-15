"""通用 DAG 执行引擎。

输入：DAG（启用了哪些 step）+ 黑板初始值 + 事件/落库回调。
做的事：
  1. 仅在「启用的步骤」之间，按 outputs->inputs 推导依赖
  2. 拓扑分波，每一波内并发执行（asyncio.gather）
  3. 缺少上游产物的步骤自动「跳过」，不阻塞其它分支
  4. 任一步骤异常 -> 标记失败，其下游因缺输入而跳过
所有「执行顺序/分组」都由数据（DAG + IO 契约）决定，不写死。
"""
from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Callable
from typing import Any

from loguru import logger

from app.engine.context import RunContext
from app.engine.registry import STEP_REGISTRY, PipelineStep

# 步骤运行结束态回调：record(step_key, status, **fields)
RecordFn = Callable[..., Awaitable[None]]
EmitFn = Callable[[dict], Awaitable[None]]


def build_dependencies(enabled_keys: list[str]) -> dict[str, set[str]]:
    """根据启用步骤的 IO 契约推导依赖：谁生产了我需要的输入，我就依赖谁。"""
    producer: dict[str, str] = {}
    for key in enabled_keys:
        step = STEP_REGISTRY[key]
        for out in step.meta.outputs:
            producer[out] = key

    deps: dict[str, set[str]] = {}
    for key in enabled_keys:
        step = STEP_REGISTRY[key]
        deps[key] = {
            producer[inp]
            for inp in step.meta.inputs
            if inp in producer and producer[inp] != key
        }
    return deps


class PipelineExecutor:
    def __init__(self, ctx: RunContext, record: RecordFn) -> None:
        self.ctx = ctx
        self.record = record

    async def run(self, enabled_keys: list[str]) -> dict[str, Any]:
        # 只保留注册表里真实存在的步骤
        enabled_keys = [k for k in enabled_keys if k in STEP_REGISTRY]
        deps = build_dependencies(enabled_keys)
        resolved: set[str] = set()  # 终态（完成/跳过/失败）的步骤

        await self.ctx.emit(
            "run_started", message=f"启用 {len(enabled_keys)} 个步骤", steps=enabled_keys
        )

        while len(resolved) < len(enabled_keys):
            ready = [
                k for k in enabled_keys if k not in resolved and deps[k] <= resolved
            ]
            if not ready:
                # 剩余步骤成环 / 依赖无法满足，全部跳过兜底
                for k in enabled_keys:
                    if k not in resolved:
                        await self._skip(k, "依赖无法满足（可能成环）")
                        resolved.add(k)
                break

            await asyncio.gather(*(self._run_one(k, resolved) for k in ready))

        await self.ctx.emit("run_finished", blackboard=self.ctx.blackboard)
        return self.ctx.blackboard

    async def _run_one(self, key: str, resolved: set[str]) -> None:
        step = STEP_REGISTRY[key]
        # 校验输入是否齐备（上游被关掉/跳过时会缺）
        missing = [i for i in step.meta.inputs if i not in self.ctx.blackboard]
        if missing:
            await self._skip(key, f"缺少输入 {missing}（上游步骤未启用或失败）")
            resolved.add(key)
            return

        # 每个步骤一份独立 ctx（绑定自身 step_key），共享同一黑板，
        # 避免并发步骤相互覆盖 current_step 导致事件错配
        step_ctx = RunContext(
            run_id=self.ctx.run_id,
            blackboard=self.ctx.blackboard,
            emit=self.ctx._emit,
            params=self.ctx.params,
        )
        step_ctx.current_step = key

        await self.record(key, status="running")
        await step_ctx.emit("step_started", kind=step.meta.kind, name=step.meta.name)
        t0 = time.perf_counter()
        try:
            output = await step.run(step_ctx)
            # 写回黑板（只接受声明过的 outputs）
            clean = {k: v for k, v in (output or {}).items() if k in step.meta.outputs}
            self.ctx.blackboard.update(clean)
            cost = round((time.perf_counter() - t0) * 1000)
            await self.record(key, status="completed", output=clean, cost_ms=cost)
            await step_ctx.emit(
                "step_completed", name=step.meta.name, output=clean, cost_ms=cost
            )
        except Exception as exc:  # noqa: BLE001 - demo：任一步骤失败不影响其它分支
            logger.exception(f"step {key} 执行失败")
            await self.record(key, status="failed", error=str(exc))
            await step_ctx.emit("step_failed", name=step.meta.name, error=str(exc))
        finally:
            resolved.add(key)

    async def _skip(self, key: str, reason: str) -> None:
        step = STEP_REGISTRY[key]
        await self.record(key, status="skipped", error=reason)
        # 显式带上 step_key，避免共享 ctx 的 current_step 串台
        await self.ctx._emit(
            {"type": "step_skipped", "step": key, "name": step.meta.name, "reason": reason}
        )
