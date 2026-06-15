"""流水线编排接口层：注册表 / 模板配置 / 运行 / 实时事件流(SSE)。

为方便 demo 演示，本模块接口不挂登录依赖。
"""
from __future__ import annotations

import asyncio
import json

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from app.api.deps import DBSession
from app.core.response import success
from app.schemas.pipeline import RunCreate, TemplateUpdate
from app.services.pipeline import get_broker, pipeline_service

router = APIRouter(prefix="/pipeline", tags=["流水线编排"])


@router.get("/steps", summary="步骤注册表")
async def list_steps():
    steps = pipeline_service.list_steps()
    return success([s.model_dump() for s in steps])


@router.get("/templates", summary="模板列表")
async def list_templates(db: DBSession):
    await pipeline_service.ensure_default_template(db)
    rows = await pipeline_service.list_templates(db)
    return success(
        [
            {
                "id": t.id,
                "name": t.name,
                "version": t.version,
                "dag": t.dag,
                "is_default": t.is_default,
            }
            for t in rows
        ]
    )


@router.get("/templates/{tpl_id}", summary="模板详情")
async def get_template(tpl_id: int, db: DBSession):
    t = await pipeline_service.get_template(db, tpl_id)
    return success(
        {"id": t.id, "name": t.name, "version": t.version, "dag": t.dag}
    )


@router.put("/templates/{tpl_id}", summary="保存流程编排（增减/开关步骤）")
async def update_template(tpl_id: int, payload: TemplateUpdate, db: DBSession):
    t = await pipeline_service.update_template(db, tpl_id, payload)
    return success(
        {"id": t.id, "name": t.name, "version": t.version, "dag": t.dag},
        msg="已保存，版本+1",
    )


@router.post("/runs", summary="发起一次运行")
async def create_run(payload: RunCreate, db: DBSession):
    run = await pipeline_service.create_run(db, payload.template_id, payload.input_text)
    return success({"run_id": run.id, "status": run.status}, msg="已开始执行")


@router.get("/runs", summary="运行历史列表")
async def list_runs(db: DBSession):
    runs = await pipeline_service.list_runs(db)
    return success(
        [
            {
                "id": r.id,
                "status": r.status,
                "template_id": r.template_id,
                "template_version": r.template_version,
                "input_preview": (r.input_text or "")[:40],
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in runs
        ]
    )


@router.get("/runs/{run_id}", summary="运行详情（含各步骤状态 + 事件流回放）")
async def get_run(run_id: int, db: DBSession):
    detail = await pipeline_service.get_run_detail(db, run_id, with_events=True)
    run = detail["run"]
    return success(
        {
            "id": run.id,
            "status": run.status,
            "template_id": run.template_id,
            "template_version": run.template_version,
            "input_text": run.input_text,
            "created_at": run.created_at.isoformat() if run.created_at else None,
            "blackboard": run.blackboard,
            "error": run.error,
            "steps": [
                {
                    "step_key": s.step_key,
                    "name": s.name,
                    "kind": s.kind,
                    "status": s.status,
                    "cost_ms": s.cost_ms,
                    "output": s.output,
                    "error": s.error,
                }
                for s in detail["steps"]
            ],
            # 事件流（落库回放）：直接复用 SSE 事件结构，前端可用同一套渲染
            "events": [e.payload for e in detail.get("events", [])],
        }
    )


@router.get("/runs/{run_id}/events", summary="运行事件流(SSE)")
async def run_events(run_id: int):
    broker = get_broker(run_id)

    async def event_gen():
        q = broker.subscribe()
        try:
            while True:
                try:
                    event = await asyncio.wait_for(q.get(), timeout=30)
                except asyncio.TimeoutError:
                    yield ": keep-alive\n\n"
                    continue
                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
                if event.get("type") == "run_finished":
                    break
        finally:
            broker.unsubscribe(q)

    return StreamingResponse(
        event_gen(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
