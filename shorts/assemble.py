"""成片合成（ffmpeg）。

输入：shots.json + 每镜视频片段 + 每句配音 + 字幕条 PNG
流程：单镜(视频+配音对位+字幕条)→ concat → 输出 1080x1920 竖屏成片。
"""
from __future__ import annotations
import json
import subprocess
from pathlib import Path

W, H, FPS = 1080, 1920, 30
PAD_BEFORE, PAD_AFTER = 0.6, 0.5


def _run(cmd: list[str]):
    subprocess.run(cmd, check=True)


def _dur(path: str) -> float:
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries",
                        "format=duration", "-of", "csv=p=0", path],
                       capture_output=True, text=True)
    return float(r.stdout.strip())


def assemble(shots_json: str, workdir: str, out_mp4: str) -> str:
    work = Path(workdir)
    shots = json.loads(Path(shots_json).read_text(encoding="utf-8"))

    # 时间轴：每镜时长 = 配音时长 + 前后留白
    timeline = []
    t = 0.0
    for s in shots:
        audio = work / f"audio_{s['n']}.mp3"
        d = _dur(str(audio))
        seg = d + PAD_BEFORE + PAD_AFTER
        timeline.append((s, str(audio), t, d, seg))
        t += seg
    total = t + 0.8

    # 1) 单镜：视频(不足则用字幕条时长定长) + 字幕 overlay
    seg_files = []
    for s, audio, start, d, seg in timeline:
        n = s["n"]
        clip = work / f"clip_{n}.mp4"
        sub = work / f"sub_{n}.png"
        seg_out = work / f"seg_{n}.mp4"
        _run(["ffmpeg", "-y", "-v", "error",
              "-i", str(clip), "-i", str(sub),
              "-filter_complex",
              f"[0:v]scale={W}:{H}:force_original_aspect_ratio=increase,"
              f"crop={W}:{H},setsar=1,fps={FPS},"
              f"trim=0:{seg:.3f},setpts=PTS-STARTPTS[base];"
              f"[base][1:v]overlay=(W-w)/2:H-h-120[vo]",
              "-map", "[vo]", "-t", f"{seg:.3f}",
              "-c:v", "libx264", "-pix_fmt", "yuv420p", str(seg_out)])
        seg_files.append(str(seg_out))

    # 2) 拼接（列表用绝对路径：concat 按列表文件所在目录解析相对路径）
    lst = work / "list.txt"
    lst.write_text("".join(f"file '{Path(p).resolve()}'\n" for p in seg_files))
    video_all = work / "video.mp4"
    _run(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0",
          "-i", str(lst), "-c", "copy", str(video_all)])

    # 3) 混音：每句配音延迟到 (镜开始 + PAD_BEFORE)
    inputs, fc = [], []
    for i, (s, audio, start, d, seg) in enumerate(timeline):
        inputs += ["-i", audio]
        ms = int((start + PAD_BEFORE) * 1000)
        fc.append(f"[{i}:a]adelay={ms}|{ms}[a{i}]")
    fc.append("".join(f"[a{i}]" for i in range(len(timeline)))
              + f"amix=inputs={len(timeline)}:normalize=0[aout]")
    audio_all = work / "audio.m4a"
    _run(["ffmpeg", "-y", "-v", "error", *inputs,
          "-filter_complex", ";".join(fc),
          "-map", "[aout]", "-t", f"{total:.3f}", str(audio_all)])

    # 4) 合成
    _run(["ffmpeg", "-y", "-v", "error",
          "-i", str(video_all), "-i", str(audio_all),
          "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac",
          "-shortest", out_mp4])
    return out_mp4
