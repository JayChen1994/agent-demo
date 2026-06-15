"""步骤②：角色抽取（真实 LLM）。与 scene_plan 同层、可并行。"""
from __future__ import annotations

from app.engine import prompts
from app.engine.context import RunContext
from app.engine.registry import PipelineStep, StepMeta, register_step
from app.services.llm_client import generate_json


@register_step
class CharExtractStep(PipelineStep):
    meta = StepMeta(
        key="char_extract",
        name="角色抽取",
        kind="llm",
        inputs=("episodes",),
        outputs=("characters",),
        description="从剧本文本中抽取出场角色（真实 Gemini 结构化输出）。",
        group="理解",
    )

    async def run(self, ctx: RunContext) -> dict:
        text = "\n".join(ctx.get("episodes", []))
        await ctx.emit("log", message="调用 Gemini 抽取角色…")
        data = await generate_json(
            prompts.CHAR_EXTRACT_SYSTEM,
            prompts.char_extract_user(text),
            response_schema=prompts.CharacterList,
        )
        characters = data.get("characters", [])
        names = "、".join(c.get("name", "") for c in characters)
        await ctx.emit("log", message=f"识别 {len(characters)} 个角色：{names}")
        return {"characters": characters}
