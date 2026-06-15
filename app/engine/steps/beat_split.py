"""步骤④：分镜拆分（Agent）—— 本 demo 的 Agent 化样板（真实 LLM + LangGraph 回环）。

依赖 episodes + characters + scenes（三路汇聚），内部用 LangGraph 状态图自检：
  draft：调 Gemini 把场景拆成连续镜头
  critique：调 Gemini 质检 image_hook 是否齐备、序号是否连续
  revise：调 Gemini 按问题清单修订
这就是把「beat_planner 单次 LLM」升级为「多轮 Agent + 校验」的真实形态。
"""
from __future__ import annotations

from typing import Any

from app.engine import prompts
from app.engine.agent import AgentStep, CritiqueResult
from app.engine.context import RunContext
from app.engine.registry import StepMeta, register_step
from app.services.llm_client import generate_json


@register_step
class BeatSplitStep(AgentStep):
    meta = StepMeta(
        key="beat_split",
        name="分镜拆分(Agent)",
        kind="agent",
        inputs=("episodes", "characters", "scenes"),
        outputs=("shots",),
        description="多轮 Agent：拆镜头 → Gemini 自检 → 修订，直至通过（LangGraph 回环）。",
        group="创作",
    )
    max_rounds = 3

    async def draft(self, ctx: RunContext) -> list[dict[str, Any]]:
        scenes = ctx.get("scenes", [])
        characters = ctx.get("characters", [])
        data = await generate_json(
            prompts.BEAT_DRAFT_SYSTEM,
            prompts.beat_draft_user(scenes, characters),
            response_schema=prompts.ShotList,
        )
        return data.get("shots", [])

    async def critique(self, ctx: RunContext, draft: list[dict]) -> CritiqueResult:
        # 先做确定性本地校验（便宜、稳定），有问题直接回环，省一次 LLM
        local_issues: list[str] = []
        for s in draft:
            if not (s.get("image_hook") or "").strip():
                local_issues.append(f"镜头 {s.get('shot_no')} 缺少 image_hook")
        if local_issues:
            return CritiqueResult(passed=False, issues=local_issues)
        # 本地通过后，交给 Gemini 做语义级质检
        data = await generate_json(
            prompts.BEAT_CRITIQUE_SYSTEM,
            prompts.beat_critique_user(draft),
            response_schema=prompts.Critique,
        )
        return CritiqueResult(
            passed=bool(data.get("passed")), issues=data.get("issues", [])
        )

    async def revise(
        self, ctx: RunContext, draft: list[dict], issues: list[str]
    ) -> list[dict]:
        data = await generate_json(
            prompts.BEAT_REVISE_SYSTEM,
            prompts.beat_revise_user(draft, issues),
            response_schema=prompts.ShotList,
        )
        return data.get("shots", draft)

    def finalize(self, ctx: RunContext, draft: list[dict]) -> dict:
        return {"shots": draft}
