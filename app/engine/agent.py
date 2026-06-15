"""AgentStep：用 LangGraph ``StateGraph`` 编排「自检回环」的 Agent 步骤基类。

把「单次 LLM 调用」升级为「会自检的多轮 Agent」。回环用真实的状态图驱动：

    draft ──▶ critique ──(passed/超轮次)──▶ END
                  │
              (有问题) ──▶ revise ──▶ critique ...

子类只需实现 draft / critique / revise / finalize 四个钩子，
StateGraph 的节点/条件边、轮次事件、产物落黑板由基类统一处理——
任何「生成-校验-修订」型环节都能低成本 Agent 化。
"""
from __future__ import annotations

import abc
from dataclasses import dataclass, field
from typing import Any, TypedDict

from langgraph.graph import END, StateGraph

from app.engine.context import RunContext
from app.engine.registry import PipelineStep


@dataclass
class CritiqueResult:
    """critic 校验结果。"""

    passed: bool
    issues: list[str] = field(default_factory=list)


class _AgentState(TypedDict):
    draft: Any
    issues: list[str]
    round: int
    passed: bool


class AgentStep(PipelineStep):
    """带 critic 回环的 Agent 步骤基类（LangGraph 实现）。"""

    max_rounds: int = 3

    @abc.abstractmethod
    async def draft(self, ctx: RunContext) -> Any:
        """第一轮：生成初稿。"""

    @abc.abstractmethod
    async def critique(self, ctx: RunContext, draft: Any) -> CritiqueResult:
        """校验：返回是否通过 + 问题清单。"""

    @abc.abstractmethod
    async def revise(self, ctx: RunContext, draft: Any, issues: list[str]) -> Any:
        """按问题清单修订。"""

    @abc.abstractmethod
    def finalize(self, ctx: RunContext, draft: Any) -> dict:
        """把通过校验的产物整理成写回黑板的 dict。"""

    def _build_graph(self, ctx: RunContext):
        async def draft_node(state: _AgentState) -> dict:
            d = await self.draft(ctx)
            await ctx.emit("agent_round", round=1, action="draft", message="生成初稿完成")
            return {"draft": d, "round": 1}

        async def critique_node(state: _AgentState) -> dict:
            res = await self.critique(ctx, state["draft"])
            await ctx.emit(
                "agent_round",
                round=state["round"],
                action="critique",
                message="自检通过 ✓" if res.passed else "自检发现问题：" + "；".join(res.issues),
                passed=res.passed,
                issues=res.issues,
            )
            return {"passed": res.passed, "issues": res.issues}

        async def revise_node(state: _AgentState) -> dict:
            d = await self.revise(ctx, state["draft"], state["issues"])
            nxt = state["round"] + 1
            await ctx.emit(
                "agent_round", round=nxt, action="revise", message="按问题清单修订完成"
            )
            return {"draft": d, "round": nxt}

        def route(state: _AgentState) -> str:
            if state["passed"]:
                return END
            if state["round"] >= self.max_rounds:
                return "give_up"
            return "revise"

        async def give_up_node(state: _AgentState) -> dict:
            await ctx.emit(
                "agent_round",
                round=state["round"],
                action="critique",
                message="达到最大轮次，带问题交付",
                passed=False,
            )
            return {}

        sg = StateGraph(_AgentState)
        sg.add_node("draft", draft_node)
        sg.add_node("critique", critique_node)
        sg.add_node("revise", revise_node)
        sg.add_node("give_up", give_up_node)
        sg.set_entry_point("draft")
        sg.add_edge("draft", "critique")
        sg.add_conditional_edges(
            "critique", route, {"revise": "revise", "give_up": "give_up", END: END}
        )
        sg.add_edge("revise", "critique")
        sg.add_edge("give_up", END)
        return sg.compile()

    async def run(self, ctx: RunContext) -> dict:
        graph = self._build_graph(ctx)
        final = await graph.ainvoke(
            {"draft": None, "issues": [], "round": 0, "passed": False},
            config={"recursion_limit": self.max_rounds * 4 + 10},
        )
        return self.finalize(ctx, final["draft"])
