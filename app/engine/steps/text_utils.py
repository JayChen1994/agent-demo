"""纯代码文本工具（无 LLM）：剧本预处理用。"""
from __future__ import annotations


def split_episodes(text: str) -> list[str]:
    """把原文按非空行切成「场景/段落原文」。"""
    return [ln.strip() for ln in text.splitlines() if ln.strip()]
