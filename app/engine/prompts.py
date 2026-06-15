"""提示词与结构化输出 Schema 配置中心。

把每个 LLM 环节的 system / user 提示词与响应 Schema 集中在此，
业务可在不动编排代码的前提下调整提示词（对应「提示词配置化」诉求）。
"""
from __future__ import annotations

from pydantic import BaseModel, Field


# ─────────────────────────── 角色抽取 ───────────────────────────
class Character(BaseModel):
    name: str = Field(description="角色名")
    role: str = Field(description="角色定位，如 主角/反派/配角")
    appearance: str = Field(description="一句话外貌特征，用于后续生图保持一致")


class CharacterList(BaseModel):
    characters: list[Character]


CHAR_EXTRACT_SYSTEM = (
    "你是资深影视责编。请从剧本文本中抽取出场角色，"
    "给出角色名、定位与一句话外貌特征。只输出 JSON。"
)


def char_extract_user(text: str) -> str:
    return f"剧本文本如下，请抽取全部出场角色：\n\n{text}"


# ─────────────────────────── 场景规划 ───────────────────────────
class Scene(BaseModel):
    no: int = Field(description="场景序号，从 1 开始")
    location: str = Field(description="地点")
    time: str = Field(description="时间，如 日/夜/黄昏")
    mood: str = Field(description="氛围基调")
    brief: str = Field(description="一句话场景概要")


class SceneList(BaseModel):
    scenes: list[Scene]


SCENE_PLAN_SYSTEM = (
    "你是分场导演。请把剧本拆分为有序场景，"
    "每个场景标注地点、时间、氛围与一句话概要。只输出 JSON。"
)


def scene_plan_user(text: str) -> str:
    return f"请对以下剧本做分场规划：\n\n{text}"


# ─────────────────────────── 分镜拆分（Agent） ───────────────────────────
class Shot(BaseModel):
    shot_no: int = Field(description="镜头全局序号，从 1 开始连续")
    scene_no: int = Field(description="所属场景序号")
    description: str = Field(description="镜头画面内容描述")
    characters: list[str] = Field(default_factory=list, description="出场角色名")
    camera: str = Field(description="景别/运镜，如 近景/推镜")
    image_hook: str = Field(description="可直接喂给文生图的画面关键描述，必须非空")


class ShotList(BaseModel):
    shots: list[Shot]


class Critique(BaseModel):
    passed: bool = Field(description="是否通过质检")
    issues: list[str] = Field(default_factory=list, description="未通过时的问题清单")


BEAT_DRAFT_SYSTEM = (
    "你是分镜师。基于场景与角色，把剧情拆成连续镜头。"
    "每个镜头要有景别/运镜，并给出可直接生图的 image_hook（务必非空）。只输出 JSON。"
)
BEAT_CRITIQUE_SYSTEM = (
    "你是分镜质检员。检查镜头表是否满足：①image_hook 均非空；"
    "②镜头序号连续；③每镜头有明确景别。返回是否通过及问题清单。只输出 JSON。"
)
BEAT_REVISE_SYSTEM = (
    "你是分镜师。请根据质检问题清单修订镜头表，修复全部问题后输出完整镜头表。只输出 JSON。"
)


def beat_draft_user(scenes: list[dict], characters: list[dict]) -> str:
    return (
        f"角色表：{characters}\n\n场景表：{scenes}\n\n"
        "请基于以上信息拆出连续镜头表。"
    )


def beat_critique_user(shots: list[dict]) -> str:
    return f"请质检以下镜头表：\n{shots}"


def beat_revise_user(shots: list[dict], issues: list[str]) -> str:
    return f"问题清单：{issues}\n\n待修订镜头表：\n{shots}\n\n请输出修订后的完整镜头表。"


# ─────────────────────────── 图像提示词 ───────────────────────────
class ImagePrompt(BaseModel):
    shot_no: int
    prompt: str = Field(description="英文文生图正向提示词，含画面/光影/镜头风格")
    negative_prompt: str = Field(default="(low quality, worst quality:1.4)")


class ImagePromptList(BaseModel):
    prompts: list[ImagePrompt]


IMAGE_PROMPT_SYSTEM = (
    "你是 AI 绘画提示词工程师。把每个镜头转写为高质量英文文生图正向提示词，"
    "包含主体、画面、光影、镜头与电影质感，并给出通用负向提示词。只输出 JSON。"
)


def image_prompt_user(shots: list[dict], characters: list[dict]) -> str:
    return f"角色表：{characters}\n\n镜头表：{shots}\n\n请为每个镜头生成英文文生图提示词。"
