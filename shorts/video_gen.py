"""AI 视频片段生成（通义万相 Wan2.1 via ModelScope API-Inference）。

认证：走 Secure Vault 注册连接 custom.modelscope 的代理机制，
不读环境变量、不落盘 key。用法见 helper：
    from shorts.video_gen import WanVideoGenerator
    WanVideoGenerator().generate(prompt, "clip_1.mp4")

实测结论（2026-10-16）：
- POST /v1/videos/generations 端点存在；未绑阿里云账号时返回
  401 "Please bind your Alibaba Cloud account before use."，
  需用户在 modelscope.cn 账号设置里绑定阿里云账号后才能调用。
- /v1/models 列表里暂无视频模型，model 参数以实际返回的错误为准调整。

占位模式：generate_placeholder() 用 ffmpeg 生成电影感渐变片段，
供绑定完成前跑通配音/字幕/合成全链路。
"""
from __future__ import annotations
import json
import os
import subprocess
import sys
import time
import urllib.request
import urllib.error

sys.path.insert(0, "/opt/muse/skills/custom-connector-setup/bin")
from dynamic_credentials import add_surrogate_to_request  # noqa: E402

BASE_URL = "https://api-inference.modelscope.cn/v1"
CONNECTION = "custom.modelscope"
ALLOWED_HOSTS = ["api-inference.modelscope.cn"]

SUBMIT_PATH = "/videos/generations"
TASK_PATHS = ["/videos/generations/{task_id}", "/tasks/{task_id}"]

DEFAULT_MODEL = os.environ.get("WAN_MODEL", "Wan-AI/Wan2.1-T2V-1.3B")

BIND_HINT = ("ModelScope 要求账号先绑定阿里云账号才能调用推理接口 "
             "(401: Please bind your Alibaba Cloud account before use.)。"
             "请在 modelscope.cn 登录后进入账号设置完成绑定，再跑视频生成。")


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args):
        raise RuntimeError("redirect refused, verify the endpoint")


def _request(method: str, path: str, body: dict | None = None,
             timeout: int = 60) -> dict:
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(
        BASE_URL + path, data=data, method=method,
        headers={"Content-Type": "application/json",
                 # 视频生成合规头（2026-10-16 实测：缺失报
                 # "X-ModelScope-DataInspection is empty"，空 JSON 对象可通过）
                 "X-ModelScope-DataInspection": "{}"})
    add_surrogate_to_request(req, CONNECTION, allowed_hosts=ALLOWED_HOSTS)
    try:
        with urllib.request.build_opener(NoRedirect()).open(
                req, timeout=timeout) as r:
            return json.loads(r.read().decode() or "{}")
    except urllib.error.HTTPError as e:
        raw = e.read(2000).decode(errors="replace")
        if "bind your Alibaba Cloud account" in raw:
            raise RuntimeError(BIND_HINT)
        raise RuntimeError(f"API {e.code}: {raw[:500]}")


class WanVideoGenerator:
    def __init__(self, model: str = DEFAULT_MODEL,
                 poll_interval: int = 15, timeout: int = 1800):
        self.model = model
        self.poll_interval = poll_interval
        self.timeout = timeout

    def submit(self, prompt: str, duration: int = 5,
               aspect_ratio: str = "9:16") -> str:
        # 429（任务槽位占满）时退避重试，最长等 2 小时
        deadline = time.time() + 7200
        attempt = 0
        while True:
            try:
                data = _request("POST", SUBMIT_PATH, {
                    "model": self.model,
                    "prompt": prompt,
                    "duration": duration,
                    "aspect_ratio": aspect_ratio,
                })
            except RuntimeError as e:
                if "429" in str(e) and time.time() < deadline:
                    attempt += 1
                    wait = min(180, 30 * attempt)
                    print(f"[video] 任务槽位满，{wait}s 后重试 (#{attempt})…",
                          flush=True)
                    time.sleep(wait)
                    continue
                raise
            task_id = data.get("task_id") or data.get("id")
            if not task_id:
                raise RuntimeError(f"提交未返回 task_id: {str(data)[:300]}")
            return task_id

    def poll(self, task_id: str) -> dict:
        deadline = time.time() + self.timeout
        last = {}
        while time.time() < deadline:
            data, ok = None, False
            for tpl in TASK_PATHS:
                try:
                    data = _request("GET", tpl.format(task_id=task_id))
                    ok = True
                    break
                except RuntimeError as e:
                    last = {"path": tpl, "err": str(e)[:120]}
            if not ok:
                raise RuntimeError(f"查询任务失败: {last}")
            status = str(data.get("status", "")).lower()
            if status in ("succeeded", "completed", "success"):
                return data
            if status in ("failed", "error", "cancelled"):
                raise RuntimeError(f"视频生成失败: {str(data)[:300]}")
            time.sleep(self.poll_interval)
        raise TimeoutError(f"任务 {task_id} 超时")

    def generate(self, prompt: str, out_path: str,
                 duration: int = 5) -> str:
        task_id = self.submit(prompt, duration=duration)
        data = self.poll(task_id)
        url = (data.get("video_url") or data.get("url")
               or (data.get("output") or {}).get("video_url")
               or (data.get("data") or {}).get("video_url"))
        if not url:
            raise RuntimeError(f"未拿到视频地址: {str(data)[:300]}")
        req = urllib.request.Request(url)
        with urllib.request.build_opener(NoRedirect()).open(
                req, timeout=300) as r, open(out_path, "wb") as f:
            while True:
                chunk = r.read(1024 * 64)
                if not chunk:
                    break
                f.write(chunk)
        return out_path


def generate_placeholder(out_path: str, duration: int = 5, seed: int = 0) -> str:
    """电影感占位片段：暗调渐变 + 缓慢推镜 + 胶片颗粒，1080x1920。"""
    import random
    rng = random.Random(seed)
    # 暗调双色渐变（茶山晨雾感：深青→暖灰）
    c1 = f"{rng.randint(18,40):02x}{rng.randint(40,70):02x}{rng.randint(45,75):02x}"
    c2 = f"{rng.randint(90,130):02x}{rng.randint(100,140):02x}{rng.randint(95,125):02x}"
    vf = ("scale=1080:1920,"
          "noise=alls=7:allf=t,"
          "vignette=PI/5")
    subprocess.run(["ffmpeg", "-y", "-v", "error",
                    "-f", "lavfi", "-i",
                    f"gradients=s=540x960:c0=0x{c1}:c1=0x{c2}:speed=0.015",
                    "-vf", vf, "-t", str(duration), "-r", "30",
                    "-c:v", "libx264", "-pix_fmt", "yuv420p",
                    out_path], check=True)
    return out_path
