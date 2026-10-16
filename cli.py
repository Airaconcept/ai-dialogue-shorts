#!/usr/bin/env python3
"""ai-dialogue-shorts CLI：对话短视频流水线。

    python cli.py board examples/zheng.md --chars characters/ -o shots.json
    python cli.py prompts shots.json
    python cli.py md shots.json -o board.md
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from shorts.script import parse_script
from shorts.characters import load_characters
from shorts.storyboard import build_storyboard, shots_to_json, shots_to_markdown
import json


def cmd_board(args):
    script = parse_script(args.script)
    chars = load_characters(args.chars)
    shots = build_storyboard(script, chars)
    out = shots_to_json(shots)
    if args.o:
        Path(args.o).write_text(out, encoding="utf-8")
        print(f"wrote {args.o} ({len(shots)} shots)")
    else:
        print(out)


def cmd_prompts(args):
    shots = json.loads(Path(args.shots).read_text(encoding="utf-8"))
    for s in shots:
        print(f"--- shot {s['n']} [{s['shot_type']}] {s['speaker']} ---")
        print(s["video_prompt"])
        print()


def cmd_md(args):
    data = json.loads(Path(args.shots).read_text(encoding="utf-8"))
    title = Path(args.shots).stem
    lines = [f"# {title} · 分镜表", ""]
    for s in data:
        lines.append(f"## 镜 {s['n']} · {s['shot_type']} · {s['speaker']}")
        if s["action_cn"]:
            lines.append(f"动作：{s['action_cn']}")
        lines.append(f"对白：{s['line_cn']}")
        if s["line_en"]:
            lines.append(f"字幕：{s['line_en']}")
        lines.append(f"提示词：{s['video_prompt']}")
        lines.append("")
    md = "\n".join(lines)
    if args.o:
        Path(args.o).write_text(md, encoding="utf-8")
        print(f"wrote {args.o}")
    else:
        print(md)


def cmd_build(args):
    from shorts.video_gen import WanVideoGenerator
    from shorts.voice import synthesize_line
    from shorts.subtitle import render_subtitle, split_cn, split_en
    from shorts.assemble import assemble

    work = Path(args.work)
    work.mkdir(parents=True, exist_ok=True)

    script = parse_script(args.script)
    chars = load_characters(args.chars)
    shots = build_storyboard(script, chars)
    shots_json = work / "shots.json"
    shots_json.write_text(shots_to_json(shots), encoding="utf-8")
    print(f"分镜：{len(shots)} 镜 -> {shots_json}")

    vgen = WanVideoGenerator()
    for s in shots:
        n = s.n
        clip = work / f"clip_{n}.mp4"
        if not clip.exists() or args.force_video:
            print(f"[video] 镜{n} 生成中…")
            vgen.generate(s.video_prompt, str(clip), duration=5)
        wav = work / f"audio_{n}.mp3"
        print(f"[voice] 镜{n} {s.speaker} 配音…")
        synthesize_line(s.line_cn, s.voice or "zh-CN-XiaoxiaoNeural", str(wav))
        cn_lines = split_cn(s.line_cn)
        en_lines = split_en(s.line_en) if s.line_en else []
        render_subtitle(cn_lines, en_lines, str(work / f"sub_{n}.png"))

    out = args.o or str(work / "final.mp4")
    assemble(str(shots_json), str(work), out)
    print(f"成片：{out}")


def main():
    ap = argparse.ArgumentParser(prog="shorts",
                                 description="对话短视频：文案→分镜→角色锁定提示词")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("board", help="脚本 → 分镜表 JSON")
    p.add_argument("script")
    p.add_argument("--chars", default="characters")
    p.add_argument("-o", default="")
    p.set_defaults(fn=cmd_board)

    p = sub.add_parser("prompts", help="打印每镜视频提示词")
    p.add_argument("shots")
    p.set_defaults(fn=cmd_prompts)

    p = sub.add_parser("md", help="分镜表 → Markdown")
    p.add_argument("shots")
    p.add_argument("-o", default="")
    p.set_defaults(fn=cmd_md)

    p = sub.add_parser("build", help="全链路：分镜→视频→配音→字幕→成片")
    p.add_argument("script")
    p.add_argument("--chars", default="characters")
    p.add_argument("--work", default="work")
    p.add_argument("-o", default="")
    p.add_argument("--force-video", action="store_true",
                   help="重新生成视频片段（默认跳过已存在的）")
    p.set_defaults(fn=cmd_build)

    args = ap.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()
