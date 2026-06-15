"""步骤⑥：关键帧生图（真实生图，io）。依赖 image_prompts。

为控制 demo 时长与成本，仅渲染前 N 个镜头（默认 3，可经 params.max_keyframes 调整）。
每出一张图即通过事件推送缩略图 URL，前端实时展示。
"""
from __future__ import annotations

import asyncio

from app.engine.context import RunContext
from app.engine.registry import PipelineStep, StepMeta, register_step
from app.services.image_client import generate_image

_DEFAULT_MAX = 3


@register_step
class KeyframeRenderStep(PipelineStep):
    meta = StepMeta(
        key="keyframe_render",
        name="关键帧生图",
        kind="io",
        inputs=("image_prompts",),
        outputs=("keyframes",),
        description="调用 portrait_gen 网关为前 N 个镜头真实生图，产出关键帧 URL。",
        group="产出",
    )

    async def run(self, ctx: RunContext) -> dict:
        prompts = ctx.get("image_prompts", [])
        limit = int(ctx.params.get("max_keyframes", _DEFAULT_MAX))
        targets = prompts[:limit]
        await ctx.emit("log", message=f"开始为前 {len(targets)} 个镜头真实生图…")

        async def _one(item: dict) -> dict:
            shot_no = item.get("shot_no")
            prompt = item.get("prompt", "")
            neg = item.get("negative_prompt", "(low quality, worst quality:1.4)")
            try:
                url = await generate_image(prompt, negative_prompt=neg)
                await ctx.emit(
                    "keyframe", shot_no=shot_no, url=url, prompt=prompt, ok=True
                )
                return {"shot_no": shot_no, "prompt": prompt, "image_url": url}
            except Exception as exc:  # noqa: BLE001 - 单图失败不影响其它
                await ctx.emit(
                    "keyframe", shot_no=shot_no, error=str(exc), prompt=prompt, ok=False
                )
                return {"shot_no": shot_no, "prompt": prompt, "error": str(exc)}

        keyframes = await asyncio.gather(*(_one(it) for it in targets))
        ok = sum(1 for k in keyframes if k.get("image_url"))
        await ctx.emit("log", message=f"生图完成：成功 {ok}/{len(targets)} 张")
        return {"keyframes": list(keyframes)}
