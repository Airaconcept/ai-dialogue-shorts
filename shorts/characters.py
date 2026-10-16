"""角色资产 (Character Bible)。

设计取自 Toonflow 的"角色与场景资产管理"：
每个角色一份 YAML，固定外貌描述 + 参照图 + 配音，
分镜生成时把外貌锁定块注入每一镜的提示词，跨镜不串脸。

characters/<id>.yaml 例::

    name: 老茶农
    name_en: old tea farmer
    appearance: 60多岁中国老茶农，饱经风霜的皱纹脸，灰白短发，深蓝色粗布衣
    appearance_en: an elderly Chinese tea farmer in his 60s, sun-weathered wrinkled
      face, short grey hair, dark blue coarse cloth shirt
    reference_image: ref/laochanong.png   # 可选：定妆照，供图生视频用
    voice: zh-CN-YunxiNeural              # edge-tts voice id
"""
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
import yaml


@dataclass
class Character:
    id: str
    name: str
    name_en: str = ""
    appearance: str = ""
    appearance_en: str = ""
    reference_image: str = ""
    voice: str = ""

    def prompt_block(self) -> str:
        """注入分镜提示词的角色锁定块（英文）。"""
        return self.appearance_en or self.appearance


def load_characters(chars_dir: str | Path) -> dict[str, Character]:
    chars: dict[str, Character] = {}
    d = Path(chars_dir)
    if not d.is_dir():
        return chars
    for yf in sorted(d.glob("*.yaml")) + sorted(d.glob("*.yml")):
        data = yaml.safe_load(yf.read_text(encoding="utf-8")) or {}
        cid = yf.stem
        chars[cid] = Character(
            id=cid,
            name=data.get("name", cid),
            name_en=data.get("name_en", ""),
            appearance=data.get("appearance", ""),
            appearance_en=data.get("appearance_en", ""),
            reference_image=data.get("reference_image", ""),
            voice=data.get("voice", ""),
        )
    return chars


def find_character(chars: dict[str, Character], speaker: str) -> Character | None:
    for c in chars.values():
        if c.name == speaker or c.id == speaker:
            return c
    return None
