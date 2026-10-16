"""双人配音（edge-tts，免费无 key）。

按角色 YAML 里的 voice 字段选声，逐句合成，返回每句时长。
依赖: pip install edge-tts
"""
from __future__ import annotations
import asyncio
import subprocess
import edge_tts


def _duration(path: str) -> float:
    r = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "csv=p=0", path], capture_output=True, text=True)
    return float(r.stdout.strip())


async def _speak(text: str, voice: str, out: str, rate: str = "+0%"):
    tts = edge_tts.Communicate(text, voice, rate=rate)
    await tts.save(out)


def synthesize_line(text: str, voice: str, out_path: str,
                    rate: str = "+0%") -> float:
    """合成一句对白，返回音频时长（秒）。"""
    asyncio.run(_speak(text, voice, out_path, rate))
    # 去除首尾静音，收紧节奏
    tmp = out_path + ".trim.mp3"
    subprocess.run(
        ["ffmpeg", "-y", "-v", "error", "-i", out_path, "-af",
         "silenceremove=start_periods=1:start_duration=0.2:start_threshold=-40dB:"
         "stop_periods=-1:stop_duration=0.35:stop_threshold=-40dB,"
         "areverse,silenceremove=start_periods=1:start_duration=0.2:"
         "start_threshold=-40dB,areverse",
         tmp], check=True)
    subprocess.run(["mv", tmp, out_path], check=True)
    return _duration(out_path)
