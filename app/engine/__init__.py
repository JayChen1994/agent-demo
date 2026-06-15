"""可配置 DAG 流水线编排引擎（精品剧流程化配置 + Agent 化 demo 内核）。

三层抽象：
  1. registry  —— Step 注册表：每个处理环节注册成带 IO 契约的 Step
  2. executor  —— 通用执行引擎：读 DAG → 算就绪步骤 → 并发执行 → 记录状态
  3. agent     —— AgentStep：把"单次 LLM"升级为"会自检的多轮 Agent"
"""
from app.engine.registry import (
    STEP_REGISTRY,
    PipelineStep,
    StepMeta,
    register_step,
)

__all__ = ["STEP_REGISTRY", "PipelineStep", "StepMeta", "register_step"]
