"""步骤③：场景规划（真实 LLM）。与 char_extract 同层、可并行。"""
from __future__ import annotations

from app.engine import prompts
from app.engine.context import RunContext
from app.engine.registry import PipelineStep, StepMeta, register_step
from app.services.llm_client import generate_json


@register_step
class ScenePlanStep(PipelineStep):
    meta = StepMeta(
        key="scene_plan",
        name="场景规划",
        kind="llm",
        inputs=("episodes",),
        outputs=("scenes",),
        description="把剧本拆为有序场景并标注地点/时间/氛围（真实 Gemini）。",
        group="理解",
    )

    async def run(self, ctx: RunContext) -> dict:
        text = "\n".join(ctx.get("episodes", []))
        await ctx.emit("log", message="调用 Gemini 做分场规划…")
        data = await generate_json(
            prompts.SCENE_PLAN_SYSTEM,
            prompts.scene_plan_user(text),
            response_schema=prompts.SceneList,
        )
        scenes = data.get("scenes", [])
        await ctx.emit("log", message=f"规划出 {len(scenes)} 个场景")
        return {"scenes": scenes}
