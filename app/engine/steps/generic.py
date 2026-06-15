"""档位 C：声明式「通用步骤」—— 步骤定义（IO 契约 + 提示词）来自模板数据而非写死。

业务在前端配置一个步骤（名称 / 输入 / 输出 / 提示词），存进 ``pipeline_template`` 的节点；
运行前由服务层据此实例化 ``GenericLLMStep`` 注册进 ``STEP_REGISTRY``。

关键收益：**执行器、依赖推导、分波并发、落库、SSE 全程一行不改**——
因为它们只认 ``StepMeta`` 的 IO 契约，不关心步骤是「代码写的」还是「配置出来的」。
这就是把「IO 契约 + 提示词」从代码搬到数据后，运营态零代码、不发版即可加流程。
"""
from __future__ import annotations

import json

from app.engine.context import RunContext
from app.engine.registry import PipelineStep, StepMeta
from app.services.llm_client import generate_json


class GenericLLMStep(PipelineStep):
    """由数据定义驱动的通用 LLM 步骤。

    - ``inputs``：要消费的黑板字段；运行时打包成 JSON 喂给模型；
    - ``outputs``：要产出的黑板字段；约束模型只返回这些字段；
    - ``prompt``：system 指令（这一步要做什么），业务在 UI 里填。
    """

    def __init__(
        self,
        *,
        key: str,
        name: str,
        inputs: list[str],
        outputs: list[str],
        prompt: str,
        description: str = "",
        group: str = "自定义",
        kind: str = "llm",
    ) -> None:
        self.meta = StepMeta(
            key=key,
            name=name,
            kind=kind,
            inputs=tuple(inputs),
            outputs=tuple(outputs),
            description=description or "运行时配置的通用 LLM 步骤（档位 C）",
            group=group,
            default_enabled=True,
        )
        self.prompt = prompt

    async def run(self, ctx: RunContext) -> dict:
        ctx_data = {k: ctx.get(k) for k in self.meta.inputs}
        out_keys = list(self.meta.outputs)
        await ctx.emit("log", message=f"自定义步骤调用 Gemini，产出 {out_keys}…")
        user = (
            f"上下文数据（JSON）：\n"
            f"{json.dumps(ctx_data, ensure_ascii=False, default=str)}\n\n"
            f"请严格输出一个 JSON 对象，且仅包含字段：{out_keys}。"
            f"每个字段对应你产出的内容（可为字符串、数组或对象）。"
        )
        data = await generate_json(
            self.prompt or "你是流水线处理器，根据上下文产出结果。",
            user,
            response_schema=None,
        )
        result = {k: data.get(k) for k in out_keys if k in data}
        await ctx.emit("log", message=f"自定义步骤完成，写回 {list(result.keys())}")
        return result
