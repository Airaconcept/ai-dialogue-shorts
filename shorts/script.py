"""对话脚本解析。

脚本格式 (Markdown, 人可手写)：

    # 争

    场景：晨雾茶山

    [远景] 晨雾漫过层层茶山 / Mist rolling over layered tea mountains

    老茶农：小伙子，记住——这世上所有赢了争吵的人，其实都输了。 / Young man, remember...
    年轻人：赢了怎么会输？道理明明在我这边！

规则：
- `# 标题`            → 标题
- `场景：xxx`         → 场景描述
- `[景别] 中文动作 / EN action` → 镜头提示 (作用于其后的对白，直到下一个提示)
  景别关键词：远景/全景→wide，全身→full，中景→medium，近景→closeup，特写→extreme_closeup
- `人名：中文对白 / English subtitle` → 对白 (英文可省；`/` 分隔)
- 空行忽略；`<!-- 注释 -->` 忽略
"""
from __future__ import annotations
import re
from dataclasses import dataclass, field

SHOT_HINTS = {
    "远景": "wide", "全景": "wide",
    "全身": "full",
    "中景": "medium",
    "近景": "closeup",
    "特写": "extreme_closeup",
}
AUTO_SHOT_ROTATION = ["wide", "medium", "closeup", "medium", "closeup", "extreme_closeup"]


@dataclass
class Dialogue:
    speaker: str
    cn: str
    en: str = ""


@dataclass
class Block:
    kind: str            # "dialogue" | "shot_hint"
    dialogue: Dialogue | None = None
    shot_type: str = ""
    action_cn: str = ""
    action_en: str = ""


@dataclass
class Script:
    title: str = ""
    scene: str = ""
    blocks: list[Block] = field(default_factory=list)

    @property
    def dialogues(self) -> list[Dialogue]:
        return [b.dialogue for b in self.blocks if b.kind == "dialogue"]


_HINT_RE = re.compile(r"^\[(?P<hint>[^\]]+)\]\s*(?P<rest>.*)$")
_DIALOGUE_RE = re.compile(r"^(?P<speaker>[^：:\[\]#]+?)\s*[：:]\s*(?P<text>.+)$")


def _split_bilingual(text: str) -> tuple[str, str]:
    # 用 " / " 分隔中英；中文里单独的 "/" 不常见，取最后一个 " / " 为分隔
    if " / " in text:
        cn, en = text.rsplit(" / ", 1)
        return cn.strip(), en.strip()
    return text.strip(), ""


def parse_script(path: str) -> Script:
    script = Script()
    with open(path, encoding="utf-8") as f:
        lines = f.read().splitlines()

    for raw in lines:
        line = raw.strip()
        if not line or line.startswith("<!--"):
            continue
        if line.startswith("# "):
            script.title = line[2:].strip()
            continue
        if line.startswith("场景：") or line.startswith("场景:"):
            script.scene = re.split(r"[：:]", line, 1)[1].strip()
            continue
        m = _HINT_RE.match(line)
        if m:
            hint, rest = m.group("hint").strip(), m.group("rest").strip()
            shot_type = SHOT_HINTS.get(hint, "")
            action_cn, action_en = _split_bilingual(rest)
            script.blocks.append(Block(kind="shot_hint", shot_type=shot_type,
                                       action_cn=action_cn, action_en=action_en))
            continue
        m = _DIALOGUE_RE.match(line)
        if m:
            cn, en = _split_bilingual(m.group("text"))
            script.blocks.append(Block(
                kind="dialogue",
                dialogue=Dialogue(speaker=m.group("speaker").strip(), cn=cn, en=en)))
            continue
        # 其它行视为场景补充描述
        script.scene = (script.scene + " " + line).strip() if script.scene else line
    return script
