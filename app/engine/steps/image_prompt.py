"""步骤⑤：图像提示词（真实 LLM）。依赖 shots + characters。"""
from __future__ import annotations

from app.engine import prompts
from app.engine.context import RunContext
from app.engine.registry import PipelineStep, StepMeta, register_step
from app.services.llm_client import generate_json


@register_step
class ImagePromptStep(PipelineStep):
    meta = StepMeta(
        key="image_prompt",
        name="图像提示词",
        kind="llm",
        inputs=("shots", "characters"),
        outputs=("image_prompts",),
        description="把分镜转写为高质量英文文生图提示词（真实 Gemini）。",
        group="产出",
    )

    async def run(self, ctx: RunContext) -> dict:
        shots = ctx.get("shots", [])
        characters = ctx.get("characters", [])
        await ctx.emit("log", message="调用 Gemini 生成文生图提示词…")
        data = await generate_json(
            prompts.IMAGE_PROMPT_SYSTEM,
            prompts.image_prompt_user(shots, characters),
            response_schema=prompts.ImagePromptList,
        )
        image_prompts = data.get("prompts", [])
        await ctx.emit("log", message=f"生成 {len(image_prompts)} 条图像提示词")
        return {"image_prompts": image_prompts}
