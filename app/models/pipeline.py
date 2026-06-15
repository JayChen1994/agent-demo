"""流水线编排相关 ORM 模型：模板（DAG 配置）、运行、步骤运行。"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, BigInteger, DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import BaseModel


class PipelineTemplate(BaseModel):
    """流程模板：以 DAG（启用了哪些步骤）的形式声明式存储，可版本化。"""

    __tablename__ = "pipeline_template"

    name: Mapped[str] = mapped_column(String(128), comment="模板名")
    version: Mapped[int] = mapped_column(Integer, default=1, comment="版本号")
    # {"nodes": [{"key": "script_ingest", "enabled": true}, ...]}
    dag: Mapped[dict] = mapped_column(JSON, comment="DAG 配置（启用的步骤）")
    is_default: Mapped[bool] = mapped_column(default=False, comment="是否默认模板")


class PipelineRun(BaseModel):
    """一次流水线运行实例。"""

    __tablename__ = "pipeline_run"

    template_id: Mapped[int] = mapped_column(BigInteger, index=True, comment="模板ID")
    template_version: Mapped[int] = mapped_column(Integer, default=1, comment="模板版本")
    input_text: Mapped[str] = mapped_column(Text, comment="输入剧本文本")
    status: Mapped[str] = mapped_column(
        String(16), default="pending", comment="pending/running/completed/failed"
    )
    blackboard: Mapped[dict | None] = mapped_column(JSON, comment="最终黑板产物")
    error: Mapped[str | None] = mapped_column(Text, comment="错误信息")


class PipelineStepRun(BaseModel):
    """单个步骤在一次运行中的执行记录。"""

    __tablename__ = "pipeline_step_run"

    run_id: Mapped[int] = mapped_column(BigInteger, index=True, comment="运行ID")
    step_key: Mapped[str] = mapped_column(String(64), comment="步骤key")
    name: Mapped[str] = mapped_column(String(128), comment="步骤名")
    kind: Mapped[str] = mapped_column(String(16), comment="code/llm/agent")
    status: Mapped[str] = mapped_column(
        String(16), default="pending", comment="pending/running/completed/failed/skipped"
    )
    cost_ms: Mapped[int] = mapped_column(Integer, default=0, comment="耗时ms")
    output: Mapped[dict | None] = mapped_column(JSON, comment="步骤产物")
    error: Mapped[str | None] = mapped_column(Text, comment="错误/跳过原因")
    started_at: Mapped[datetime | None] = mapped_column(DateTime, comment="开始时间")
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, comment="结束时间")
