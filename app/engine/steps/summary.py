"""步骤⑥：剧情摘要（code，默认关闭）—— 演示「可选/可增减环节」。

default_enabled=False：默认不在流程里，业务可在前端一键开启，
开启后引擎自动按 IO 契约把它编排进 DAG。
"""
from __future__ import annotations

from app.engine.context import RunContext
from app.engine.registry import PipelineStep, StepMeta, register_step


@register_step
class SummaryStep(PipelineStep):
    meta = StepMeta(
        key="summary",
        name="剧情摘要",
        kind="code",
        inputs=("episodes",),
        outputs=("summary",),
        description="统计场景数/字数并生成一句话摘要（可选环节，默认关闭）。",
        group="产出",
        default_enabled=False,
    )

    async def run(self, ctx: RunContext) -> dict:
        episodes = ctx.get("episodes", [])
        chars = sum(len(e) for e in episodes)
        summary = {
            "scene_count": len(episodes),
            "char_count": chars,
            "headline": episodes[0][:16] + "…" if episodes else "",
        }
        await ctx.emit("log", message=f"摘要：{summary}")
        return {"summary": summary}
