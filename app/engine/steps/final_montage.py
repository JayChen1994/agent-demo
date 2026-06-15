"""步骤⑦：成片合成（code，默认关闭）—— 演示「新增一层 L5 / 插入新流程」。

本步骤刻意依赖 L4 关键帧产物（``keyframes``）+ 镜头表（``shots``），
因此引擎会按 IO 契约把它自动编排到 keyframe_render **之后**，形成新的一层 L5——
全程**不改执行器、不改前端分层逻辑、不改任何已有步骤**，仅新增本文件即可。

这正是回答「我想新增一个流程插进去 / 新增一个 L5」的最小样板：
声明好 inputs/outputs，剩下的依赖推导、分波、并发、落库、推流全由引擎接管。
"""
from __future__ import annotations

from app.engine.context import RunContext
from app.engine.registry import PipelineStep, StepMeta, register_step


@register_step
class FinalMontageStep(PipelineStep):
    meta = StepMeta(
        key="final_montage",
        name="成片合成",
        kind="code",
        inputs=("shots", "keyframes"),
        outputs=("montage",),
        description="把镜头表与关键帧汇编成一份成片清单（演示新增 L5，依赖关键帧产物）。",
        group="产出",
        default_enabled=False,
    )

    async def run(self, ctx: RunContext) -> dict:
        shots = ctx.get("shots", [])
        keyframes = ctx.get("keyframes", [])
        by_shot = {k.get("shot_no"): k for k in keyframes}
        timeline = [
            {
                "shot_no": s.get("shot_no"),
                "camera": s.get("camera"),
                "description": s.get("description"),
                "image_url": by_shot.get(s.get("shot_no"), {}).get("image_url"),
            }
            for s in shots
        ]
        rendered = sum(1 for t in timeline if t["image_url"])
        montage = {
            "shot_count": len(shots),
            "rendered_count": rendered,
            "timeline": timeline,
        }
        await ctx.emit(
            "log", message=f"成片清单：{len(shots)} 镜头，{rendered} 张关键帧已就位"
        )
        return {"montage": montage}
