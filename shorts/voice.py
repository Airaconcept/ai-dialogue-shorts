"""双人配音。

引擎优先级：
1. MOSS-TTS-Nano（复旦 OpenMOSS，100M 参数，ONNX CPU 实时推理，
   中文神经语音，免费无 key）——本机主力。模型在
   ~/workspace/MOSS-TTS-Nano/models（随 workspace 持久化）。
2. edge-tts（微软神经语音）——本机出境代理破坏 websocket 握手，
   此环境不可用；正常网络下可用 VOICE_ENGINE=edge 强制。
3. gTTS（Google TTS 纯 HTTPS）——最后降级。

按角色 YAML 里的 voice 字段选声，逐句合成，返回每句时长。
"""
from __future__ import annotations
import asyncio
import os
import subprocess
import edge_tts

# 角色 voice 名 → MOSS 内置音色
MOSS_VOICES = {
    "zh-CN-YunxiNeural": "Weiguo",    # 老茶农：说书风
    "zh-CN-YunjianNeural": "Junhao",  # 年轻人
}
_MOSS_RUNTIME = None


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


def _speak_moss(text: str, voice: str, out: str):
    """MOSS-TTS-Nano ONNX 本地推理。"""
    global _MOSS_RUNTIME
    if _MOSS_RUNTIME is None:
        import sys
        moss_dir = os.path.expanduser("~/workspace/MOSS-TTS-Nano")
        if moss_dir not in sys.path:
            sys.path.insert(0, moss_dir)
        from onnx_tts_runtime import OnnxTtsRuntime
        _MOSS_RUNTIME = OnnxTtsRuntime(
            model_dir=os.path.join(moss_dir, "models"),
            execution_provider="cpu",
        )
    moss_voice = MOSS_VOICES.get(voice, "Junhao")
    _MOSS_RUNTIME.synthesize(
        text=text,
        voice=moss_voice,
        output_audio_path=out,
        sample_mode="fixed",
        streaming=True,
    )


def _speak_gtts(text: str, voice: str, out: str):
    """降级方案：Google TTS（纯 HTTPS，无需 websocket）。
    本机出境代理破坏 websocket 握手时用。单音色，用变调区分角色：
    老茶农(Yunxi)降调慢速，年轻人(Yunjian)保持原样。"""
    from gtts import gTTS
    gTTS(text, lang="zh-cn").save(out)
    if "Yunxi" in voice:
        # 老茶农：只放慢语速（沉稳感），不动音调——变调器是"怪"的来源
        tmp = out + ".slow.mp3"
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", out,
                        "-af", "atempo=0.92", tmp], check=True)
        subprocess.run(["mv", tmp, out], check=True)


def synthesize_line(text: str, voice: str, out_path: str,
                    rate: str = "+0%") -> float:
    """合成一句对白，返回音频时长（秒）。
    引擎：moss → edge-tts → gTTS 自动降级。可用 VOICE_ENGINE
    环境变量强制指定（moss / edge / gtts）。"""
    engine = os.environ.get("VOICE_ENGINE", "").strip()
    tried = []

    def _try(name, fn):
        tried.append(name)
        if engine and engine != name:
            return False
        try:
            fn()
            print(f"[voice] 引擎: {name}")
            return True
        except Exception as e:
            print(f"[voice] {name} 失败({type(e).__name__})")
            return False

    ok = _try("moss", lambda: _speak_moss(text, voice, out_path))
    if not ok:
        ok = _try("edge", lambda: asyncio.run(_speak(text, voice, out_path, rate)))
    if not ok:
        ok = _try("gtts", lambda: _speak_gtts(text, voice, out_path))
    if not ok:
        raise RuntimeError(f"所有配音引擎失败: {tried}")
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
