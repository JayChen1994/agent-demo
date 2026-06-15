"""导入所有步骤模块，触发 @register_step 注册到 STEP_REGISTRY。"""
from app.engine.steps import (  # noqa: F401
    beat_split,
    char_extract,
    image_prompt,
    keyframe_render,
    scene_plan,
    script_ingest,
    summary,
)
