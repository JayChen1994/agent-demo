"""流水线编排业务层：注册表查询、模板 CRUD、运行调度、SSE 事件广播。"""
from __future__ import annotations

import asyncio
import json
from datetime import datetime
from typing import Any

from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BizError, ErrorCode
from app.db.session import AsyncSessionLocal
from app.engine.context import RunContext
from app.engine.executor import PipelineExecutor
from app.engine.registry import STEP_REGISTRY
import app.engine.steps  # noqa: F401  确保所有步骤被 import 注册
from app.models.pipeline import PipelineRun, PipelineStepRun, PipelineTemplate
from app.schemas.pipeline import StepInfo, TemplateUpdate


# ---------------------------------------------------------------- SSE 事件广播
class RunBroker:
    """单次运行的事件广播：支持多订阅者 + 历史回放（应对晚连接的 SSE）。"""

    def __init__(self) -> None:
        self.queues: set[asyncio.Queue] = set()
        self.history: list[dict] = []
        self.finished = False

    async def publish(self, event: dict) -> None:
        self.history.append(event)
        if event.get("type") == "run_finished":
            self.finished = True
        for q in list(self.queues):
            q.put_nowait(event)

    def subscribe(self) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue()
        for ev in self.history:  # 回放已发生的事件
            q.put_nowait(ev)
        self.queues.add(q)
        return q

    def unsubscribe(self, q: asyncio.Queue) -> None:
        self.queues.discard(q)


_BROKERS: dict[int, RunBroker] = {}
# 持有后台任务的强引用：事件循环只保留弱引用，不持有会被 GC 提前回收
_BACKGROUND_TASKS: set[asyncio.Task] = set()


def get_broker(run_id: int) -> RunBroker:
    return _BROKERS.setdefault(run_id, RunBroker())


class PipelineService:
    # ------------------------------------------------------------- 注册表
    def list_steps(self) -> list[StepInfo]:
        return [
            StepInfo(
                key=s.meta.key,
                name=s.meta.name,
                kind=s.meta.kind,
                inputs=list(s.meta.inputs),
                outputs=list(s.meta.outputs),
                description=s.meta.description,
                group=s.meta.group,
                default_enabled=s.meta.default_enabled,
            )
            for s in STEP_REGISTRY.values()
        ]

    # ------------------------------------------------------------- 模板
    async def ensure_default_template(self, db: AsyncSession) -> PipelineTemplate:
        """无默认模板时，按注册表生成一份（演示「注册表 -> 默认 DAG」）。"""
        existing = await db.scalar(
            select(PipelineTemplate).where(PipelineTemplate.is_default.is_(True))
        )
        if existing:
            # 同步注册表新增/移除的步骤（保留已有 enabled 选择）
            known = {n["key"]: n.get("enabled") for n in existing.dag.get("nodes", [])}
            registry_keys = list(STEP_REGISTRY.keys())
            merged = [
                {
                    "key": k,
                    "enabled": known[k]
                    if k in known
                    else STEP_REGISTRY[k].meta.default_enabled,
                }
                for k in registry_keys
            ]
            if [n["key"] for n in existing.dag.get("nodes", [])] != registry_keys or any(
                n.get("enabled") != m["enabled"]
                for n, m in zip(existing.dag.get("nodes", []), merged)
            ):
                existing.dag = {"nodes": merged}
                logger.info("默认模板已按注册表同步步骤")
            return existing
        nodes = [
            {"key": s.meta.key, "enabled": s.meta.default_enabled}
            for s in STEP_REGISTRY.values()
        ]
        tpl = PipelineTemplate(
            name="精品剧默认流程", version=1, dag={"nodes": nodes}, is_default=True
        )
        db.add(tpl)
        await db.flush()
        logger.info(f"已生成默认流程模板 id={tpl.id}")
        return tpl

    async def list_templates(self, db: AsyncSession) -> list[PipelineTemplate]:
        rows = await db.scalars(select(PipelineTemplate).order_by(PipelineTemplate.id))
        return list(rows)

    async def get_template(self, db: AsyncSession, tpl_id: int) -> PipelineTemplate:
        tpl = await db.get(PipelineTemplate, tpl_id)
        if not tpl:
            raise BizError("模板不存在", code=ErrorCode.NOT_FOUND)
        return tpl

    async def update_template(
        self, db: AsyncSession, tpl_id: int, data: TemplateUpdate
    ) -> PipelineTemplate:
        tpl = await self.get_template(db, tpl_id)
        unknown = [n.key for n in data.dag.nodes if n.key not in STEP_REGISTRY]
        if unknown:
            raise BizError(f"未知步骤：{unknown}", code=ErrorCode.PARAM_ERROR)
        if data.name:
            tpl.name = data.name
        tpl.dag = {"nodes": [n.model_dump() for n in data.dag.nodes]}
        tpl.version += 1
        await db.flush()
        return tpl

    # ------------------------------------------------------------- 运行
    async def create_run(
        self, db: AsyncSession, template_id: int, input_text: str
    ) -> PipelineRun:
        tpl = await self.get_template(db, template_id)
        run = PipelineRun(
            template_id=tpl.id,
            template_version=tpl.version,
            input_text=input_text,
            status="pending",
        )
        db.add(run)
        await db.flush()
        run_id = run.id
        enabled = [n["key"] for n in tpl.dag.get("nodes", []) if n.get("enabled")]
        # 后台异步执行（项目选型：进程内 asyncio 编排）
        task = asyncio.create_task(self._execute(run_id, input_text, enabled))
        _BACKGROUND_TASKS.add(task)
        task.add_done_callback(_BACKGROUND_TASKS.discard)
        return run

    async def _execute(self, run_id: int, input_text: str, enabled: list[str]) -> None:
        """后台任务：独立 DB 会话，执行 DAG 并广播事件 + 落库。"""
        broker = get_broker(run_id)
        async with AsyncSessionLocal() as db:
            run = await db.get(PipelineRun, run_id)
            if run is None:
                return
            run.status = "running"
            await db.commit()

            step_rows: dict[str, PipelineStepRun] = {}
            # 同一 AsyncSession 不可被并发步骤同时提交，故用锁串行化 DB 写入
            db_lock = asyncio.Lock()

            async def record(step_key: str, *, status: str, **fields: Any) -> None:
                async with db_lock:
                    row = step_rows.get(step_key)
                    if row is None:
                        meta = STEP_REGISTRY[step_key].meta
                        row = PipelineStepRun(
                            run_id=run_id,
                            step_key=step_key,
                            name=meta.name,
                            kind=meta.kind,
                        )
                        db.add(row)
                        step_rows[step_key] = row
                    row.status = status
                    if status == "running":
                        row.started_at = datetime.now()
                    if status in ("completed", "failed", "skipped"):
                        row.finished_at = datetime.now()
                    if "output" in fields:
                        row.output = fields["output"]
                    if "cost_ms" in fields:
                        row.cost_ms = fields["cost_ms"]
                    if "error" in fields:
                        row.error = fields["error"]
                    await db.commit()

            async def emit(event: dict) -> None:
                await broker.publish(event)

            blackboard: dict[str, Any] = {}
            ctx = RunContext(
                run_id=run_id,
                blackboard=blackboard,
                emit=emit,
                params={"input_text": input_text},
            )
            executor = PipelineExecutor(ctx, record)
            try:
                await executor.run(enabled)
                run.status = "completed"
                run.blackboard = blackboard
            except Exception as exc:  # noqa: BLE001
                logger.exception("流水线执行异常")
                run.status = "failed"
                run.error = str(exc)
                await broker.publish({"type": "run_finished", "error": str(exc)})
            await db.commit()

    async def get_run_detail(self, db: AsyncSession, run_id: int) -> dict:
        run = await db.get(PipelineRun, run_id)
        if not run:
            raise BizError("运行不存在", code=ErrorCode.NOT_FOUND)
        rows = await db.scalars(
            select(PipelineStepRun)
            .where(PipelineStepRun.run_id == run_id)
            .order_by(PipelineStepRun.id)
        )
        return {"run": run, "steps": list(rows)}


pipeline_service = PipelineService()
