"""流水线编排相关 Pydantic 模型。"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class StepInfo(BaseModel):
    """注册表里一个步骤的对外信息（前端展示用）。"""

    key: str
    name: str
    kind: str
    inputs: list[str]
    outputs: list[str]
    description: str
    group: str
    default_enabled: bool


class DagNode(BaseModel):
    key: str
    enabled: bool = True
    # 档位 C：自定义步骤携带完整定义（IO 契约 + 提示词），随模板落库
    custom: bool = False
    name: str | None = None
    kind: str | None = None
    inputs: list[str] | None = None
    outputs: list[str] | None = None
    prompt: str | None = None
    description: str | None = None


class DagConfig(BaseModel):
    nodes: list[DagNode] = Field(default_factory=list)


class TemplateOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    version: int
    dag: dict
    is_default: bool
    updated_at: datetime


class TemplateUpdate(BaseModel):
    name: str | None = None
    dag: DagConfig


class RunCreate(BaseModel):
    template_id: int
    input_text: str = Field(min_length=1, description="剧本原文")


class StepRunOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    step_key: str
    name: str
    kind: str
    status: str
    cost_ms: int
    output: dict | None = None
    error: str | None = None


class RunOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    template_id: int
    status: str
    input_text: str
    blackboard: dict | None = None
    error: str | None = None
    created_at: datetime


class RunDetail(RunOut):
    steps: list[StepRunOut] = Field(default_factory=list)
