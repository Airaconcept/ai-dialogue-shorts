"""分镜生成：文案 → 分镜表。

整合点：
- 取自 Turbo 的"自定义文案 → 分段 → 逐段配料"流水线思想，
  但分段单位是「一句对白 = 一镜」，贴合对话短视频；
- 取自 Toonflow 的角色资产思想：每镜提示词注入角色外貌锁定块，
  同一角色在所有镜头里描述一字不差，跨镜不串脸。

输出 shots.json，每镜包含：
  n, shot_type, characters, action_cn/en,
  dialogue{ speaker, cn, en }, video_prompt, voice
"""
from __future__ import annotations
import json
from dataclasses import dataclass, field, asdict

from .script import Script, Block, AUTO_SHOT_ROTATION
from .characters import Character, find_character

STYLE_TAIL = ("cinematic video, vertical 9:16 portrait composition, "
              "35mm film look, shallow depth of field")
SHOT_TYPE_EN = {
    "wide": "wide establishing shot, slow push-in",
    "full": "full shot, slow push-in",
    "medium": "medium shot, subtle parallax drift",
    "closeup": "medium close-up, gentle push-in",
    "extreme_closeup": "extreme close-up, slow push-in",
}


@dataclass
class Shot:
    n: int
    shot_type: str
    characters: list[str] = field(default_factory=list)
    action_cn: str = ""
    action_en: str = ""
    speaker: str = ""
    line_cn: str = ""
    line_en: str = ""
    voice: str = ""
    video_prompt: str = ""


def build_storyboard(script: Script,
                     characters: dict[str, Character]) -> list[Shot]:
    shots: list[Shot] = []
    pending_hint: Block | None = None
    auto_idx = 0
    n = 0

    for block in script.blocks:
        if block.kind == "shot_hint":
            pending_hint = block
            continue
        # 一句对白 = 一镜
        n += 1
        dlg = block.dialogue
        if pending_hint and pending_hint.shot_type:
            shot_type = pending_hint.shot_type
            action_cn = pending_hint.action_cn
            action_en = pending_hint.action_en
        else:
            shot_type = AUTO_SHOT_ROTATION[auto_idx % len(AUTO_SHOT_ROTATION)]
            auto_idx += 1
            action_cn = pending_hint.action_cn if pending_hint else ""
            action_en = pending_hint.action_en if pending_hint else ""
        pending_hint = None

        char = find_character(characters, dlg.speaker)
        chars_in_shot = [char.name] if char else [dlg.speaker]
        # 动作描述里提到的人物也算入镜（跨镜一致性需要知道谁在画面里）
        for c in characters.values():
            if c.name != (char.name if char else None) and c.name in action_cn:
                chars_in_shot.append(c.name)

        # 角色锁定块：同一角色所有镜头一字不差
        lock_blocks = []
        for cname in chars_in_shot:
            c = find_character(characters, cname)
            if c and c.prompt_block():
                who = c.name_en or c.name
                lock_blocks.append(f"{who}: {c.prompt_block()}")
        lock_text = "; ".join(lock_blocks)

        parts = [STYLE_TAIL + ".",
                 f"{SHOT_TYPE_EN.get(shot_type, shot_type)}."]
        if action_en:
            parts.append(action_en.rstrip(".") + ".")
        elif action_cn:
            parts.append(f"scene: {action_cn}.")
        if lock_text:
            parts.append(f"Characters (keep identical in every shot): {lock_text}.")
        if script.scene:
            parts.append(f"Setting: {script.scene}.")
        video_prompt = " ".join(parts)

        shots.append(Shot(
            n=n, shot_type=shot_type,
            characters=chars_in_shot,
            action_cn=action_cn, action_en=action_en,
            speaker=dlg.speaker, line_cn=dlg.cn, line_en=dlg.en,
            voice=char.voice if char else "",
            video_prompt=video_prompt,
        ))
    return shots


def shots_to_json(shots: list[Shot]) -> str:
    return json.dumps([asdict(s) for s in shots],
                      ensure_ascii=False, indent=2)


def shots_to_markdown(title: str, shots: list[Shot]) -> str:
    out = [f"# {title} · 分镜表", ""]
    for s in shots:
        out.append(f"## 镜 {s.n} · {s.shot_type} · {s.speaker}")
        if s.action_cn:
            out.append(f"动作：{s.action_cn}")
        out.append(f"对白：{s.line_cn}")
        if s.line_en:
            out.append(f"字幕：{s.line_en}")
        out.append(f"提示词：{s.video_prompt}")
        out.append("")
    return "\n".join(out)
