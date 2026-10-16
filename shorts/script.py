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
# 运镜 / 画面修饰关键词 → 英文提示词片段
MODIFIER_HINTS = {
    "缓推": "slow push-in",
    "缓拉": "slow pull-back",
    "左移": "gentle pan left",
    "右移": "gentle pan right",
    "环绕": "slow orbiting camera",
    "静": "static tripod framing",
    "航拍": "aerial view",
    "手部": "focus on hands",
    "侧逆光": "soft backlight",
    "逆光": "backlit",
    "过肩": "over-the-shoulder framing",
    "低角度": "low angle",
    "高角度": "high angle",
}
MOVE_KEYS = {"缓推", "缓拉", "左移", "右移", "环绕", "静"}
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
    camera_move: str = ""      # 显式运镜（英文）
    modifiers_en: str = ""     # 其它画面修饰（英文，逗号分隔）


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
            # [远景·缓推·航拍] → 景别 + 运镜 + 修饰，兼容旧写法 [远景]；
            # 修饰词可连写（如"航拍缓推"），按已知关键词做子串拆分
            tokens = re.split(r"[·•・.\s]", hint)
            shot_type = SHOT_HINTS.get(tokens[0].strip(), "")
            camera_move, mods = "", []
            rest_text = "".join(tokens[1:])
            for key in sorted(MODIFIER_HINTS, key=len, reverse=True):
                if key in rest_text:
                    en = MODIFIER_HINTS[key]
                    if key in MOVE_KEYS and not camera_move:
                        camera_move = en
                    elif key not in MOVE_KEYS and en not in mods:
                        mods.append(en)
                    rest_text = rest_text.replace(key, "", 1)
            action_cn, action_en = _split_bilingual(rest)
            script.blocks.append(Block(kind="shot_hint", shot_type=shot_type,
                                       action_cn=action_cn, action_en=action_en,
                                       camera_move=camera_move,
                                       modifiers_en=", ".join(mods)))
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
