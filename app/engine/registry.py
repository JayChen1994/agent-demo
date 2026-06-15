"""Step 注册表：把每个处理环节声明成「带 IO 契约」的可编排步骤。

设计要点（对应方案「需求1：流程化配置」）：
- 每个 Step 显式声明 ``inputs`` / ``outputs``（黑板 blackboard 的 key），
  执行引擎据此**自动推导 DAG 依赖**——业务在前端增减/开关步骤即可改流程，
  无需改编排代码。
- ``kind`` 区分 code / llm / agent 三类（对应「需求2：Agent 化」），
  执行引擎对三类一视同仁地编排、记录状态。
"""
from __future__ import annotations

import abc
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.engine.context import RunContext


@dataclass(frozen=True)
class StepMeta:
    """步骤的静态契约（声明式，供 DAG 推导与前端展示）。"""

    key: str
    name: str
    kind: str  # code | llm | agent
    inputs: tuple[str, ...] = ()
    outputs: tuple[str, ...] = ()
    description: str = ""
    group: str = "通用"
    # default_enabled=False 表示「默认关闭、可选环节」（demo 用 summary 演示可增减）
    default_enabled: bool = True


class PipelineStep(abc.ABC):
    """所有步骤的基类。子类用 ``@register_step`` 注册。"""

    meta: StepMeta

    @abc.abstractmethod
    async def run(self, ctx: "RunContext") -> dict:
        """执行步骤，返回写回黑板的产物 dict（key 须 ⊆ ``meta.outputs``）。"""
        raise NotImplementedError


# 进程级注册表：模块 import 时通过 register_step 写入
STEP_REGISTRY: dict[str, PipelineStep] = {}


def register_step(step_cls: type[PipelineStep]) -> type[PipelineStep]:
    """类装饰器：实例化并登记到 ``STEP_REGISTRY``。"""
    inst = step_cls()
    if inst.meta.key in STEP_REGISTRY:
        raise ValueError(f"重复注册 step_key={inst.meta.key}")
    STEP_REGISTRY[inst.meta.key] = inst
    return step_cls


def all_steps() -> list[PipelineStep]:
    return list(STEP_REGISTRY.values())


def get_step(key: str) -> PipelineStep | None:
    return STEP_REGISTRY.get(key)
