"""无头 CLI：不依赖 HTTP/DB，直接跑一遍可配置 Agent 流水线（真实 LLM + 真实生图）。

用法：
    .venv/bin/python scripts/run_agent_pipeline_demo.py
    .venv/bin/python scripts/run_agent_pipeline_demo.py --no-image   # 跳过生图，仅跑 LLM 链路
    .venv/bin/python scripts/run_agent_pipeline_demo.py --steps script_ingest,char_extract

直接复用与 Web 端同一套引擎（registry/executor/steps），证明编排内核与传输层解耦。
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import app.engine.steps  # noqa: F401,E402  触发步骤注册
from app.engine.context import RunContext  # noqa: E402
from app.engine.executor import PipelineExecutor  # noqa: E402
from app.engine.registry import STEP_REGISTRY  # noqa: E402

DEFAULT_TEXT = (
    "【林深】深夜回到公寓，发现门虚掩着。他握紧拳头，缓缓推开门。\n"
    "客厅一片漆黑，只有窗外霓虹闪烁。【苏曼】坐在沙发上，神色凝重。\n"
    "“你终于回来了。”她轻声说。林深沉默地走近，空气仿佛凝固。"
)


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--text", default=DEFAULT_TEXT)
    parser.add_argument("--steps", default="", help="逗号分隔的步骤 key，留空=注册表默认启用项")
    parser.add_argument("--no-image", action="store_true", help="跳过 keyframe_render 生图")
    parser.add_argument("--max-keyframes", type=int, default=2)
    args = parser.parse_args()

    if args.steps:
        enabled = [k.strip() for k in args.steps.split(",") if k.strip()]
    else:
        enabled = [k for k, s in STEP_REGISTRY.items() if s.meta.default_enabled]
    if args.no_image and "keyframe_render" in enabled:
        enabled.remove("keyframe_render")

    async def emit(event: dict) -> None:
        t = event.get("type")
        if t == "step_started":
            print(f"  ▶ [{event['step']}] {event.get('name')} 开始")
        elif t == "step_completed":
            print(f"  ✓ [{event['step']}] 完成 ({event.get('cost_ms')}ms)")
        elif t == "step_failed":
            print(f"  ✗ [{event['step']}] 失败：{event.get('error')}")
        elif t == "step_skipped":
            print(f"  ⊘ [{event['step']}] 跳过：{event.get('reason')}")
        elif t == "agent_round":
            print(f"      · R{event.get('round')} {event.get('action')}: {event.get('message')}")
        elif t == "log":
            print(f"      · [{event['step']}] {event.get('message')}")
        elif t == "keyframe":
            if event.get("ok"):
                print(f"      🖼  镜头 {event.get('shot_no')} 出图：{event.get('url')}")
            else:
                print(f"      🖼  镜头 {event.get('shot_no')} 生图失败：{event.get('error')}")

    blackboard: dict = {}
    ctx = RunContext(
        run_id=0,
        blackboard=blackboard,
        emit=emit,
        params={"input_text": args.text, "max_keyframes": args.max_keyframes},
    )

    async def record(step_key: str, *, status: str, **fields) -> None:
        return None

    print(f"启用步骤：{enabled}\n{'=' * 60}")
    await PipelineExecutor(ctx, record).run(enabled)
    print(f"{'=' * 60}\n最终 blackboard：")
    print(json.dumps(blackboard, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
