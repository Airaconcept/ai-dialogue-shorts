"""双人配音（edge-tts，免费无 key）。

按角色 YAML 里的 voice 字段选声，逐句合成，返回每句时长。
依赖: pip install edge-tts
"""
from __future__ import annotations
import asyncio
import os
import subprocess
import edge_tts


def _proxy() -> str | None:
    # aiohttp 默认不读系统代理，显式传入（本机经 hatch-egress-proxy 出境）
    return os.environ.get("HTTPS_PROXY") or os.environ.get("https_proxy")


def _duration(path: str) -> float:
    r = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "csv=p=0", path], capture_output=True, text=True)
    return float(r.stdout.strip())


async def _speak(text: str, voice: str, out: str, rate: str = "+0%"):
    tts = edge_tts.Communicate(text, voice, rate=rate, proxy=_proxy())
    await tts.save(out)


def _speak_gtts(text: str, voice: str, out: str):
    """降级方案：Google TTS（纯 HTTPS，无需 websocket）。
    本机出境代理破坏 websocket 握手时用。单音色，用变调区分角色：
    老茶农(Yunxi)降调慢速，年轻人(Yunjian)保持原样。"""
    from gtts import gTTS
    gTTS(text, lang="zh-cn").save(out)
    if "Yunxi" in voice:
        # 降调 + 稍慢：苍老感
        tmp = out + ".deep.mp3"
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", out,
                        "-af", "asetrate=44100*0.88,aresample=44100,atempo=0.94",
                        tmp], check=True)
        subprocess.run(["mv", tmp, out], check=True)


def synthesize_line(text: str, voice: str, out_path: str,
                    rate: str = "+0%") -> float:
    """合成一句对白，返回音频时长（秒）。
    优先 edge-tts（神经语音）；本机网络不通时自动降级到 gTTS。"""
    try:
        asyncio.run(_speak(text, voice, out_path, rate))
    except Exception as e:
        print(f"[voice] edge-tts 失败({type(e).__name__})，降级 gTTS")
        _speak_gtts(text, voice, out_path)
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
