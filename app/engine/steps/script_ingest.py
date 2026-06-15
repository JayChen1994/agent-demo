"""步骤①：剧本解析（code）。原始文本 -> 分场。"""
from __future__ import annotations

from app.engine.context import RunContext
from app.engine.registry import PipelineStep, StepMeta, register_step
from app.engine.steps.text_utils import split_episodes


@register_step
class ScriptIngestStep(PipelineStep):
    meta = StepMeta(
        key="script_ingest",
        name="剧本解析",
        kind="code",
        inputs=(),
        outputs=("episodes",),
        description="将原始剧本文本按段落切分为场景列表（纯代码 ETL，无 LLM）。",
        group="预处理",
    )

    async def run(self, ctx: RunContext) -> dict:
        text = ctx.params.get("input_text", "")
        episodes = split_episodes(text)
        await ctx.emit("log", message=f"解析出 {len(episodes)} 个场景")
        return {"episodes": episodes}
