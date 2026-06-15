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


# ─────────────────────── 档位 C：运行时自定义步骤 ───────────────────────
# 自定义步骤 key 统一以 custom_ 开头，与代码内置步骤区分（可覆盖、可注销）。
CUSTOM_KEY_PREFIX = "custom_"


def is_custom_key(key: str) -> bool:
    return key.startswith(CUSTOM_KEY_PREFIX)


def register_custom_step(step: PipelineStep) -> None:
    """注册/覆盖一个「运行时自定义步骤」（来自模板数据，非 import 时登记）。

    与 ``register_step`` 不同：允许覆盖（业务可反复编辑同一步骤），
    但 key 必须以 ``custom_`` 开头，避免污染内置步骤。
    """
    if not is_custom_key(step.meta.key):
        raise ValueError(f"自定义步骤 key 必须以 {CUSTOM_KEY_PREFIX} 开头：{step.meta.key}")
    STEP_REGISTRY[step.meta.key] = step


def unregister_custom_step(key: str) -> None:
    if is_custom_key(key):
        STEP_REGISTRY.pop(key, None)
