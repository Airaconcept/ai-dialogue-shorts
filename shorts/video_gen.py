"""AI 视频片段生成（通义万相 Wan2.1 via ModelScope）。

使用前设置环境变量::

    export MODELSCOPE_API_KEY=ms-xxxx

说明：
- 采用异步任务模式：submit → 轮询 → 下载，和主流视频生成 API 一致；
- 具体 endpoint 路径以魔搭官方文档为准，如有出入改 BASE_URL / 路径常量即可，
  调用逻辑不用动。
"""
from __future__ import annotations
import os
import time
import requests

BASE_URL = os.environ.get("MODELSCOPE_API_BASE",
                           "https://api-inference.modelscope.cn/v1")
SUBMIT_PATH = "/videos/generations"      # 按魔搭文档核对
TASK_PATH = "/videos/generations/{task_id}"


class WanVideoGenerator:
    def __init__(self, api_key: str | None = None,
                 base_url: str = BASE_URL,
                 poll_interval: int = 10,
                 timeout: int = 900):
        self.api_key = api_key or os.environ.get("MODELSCOPE_API_KEY", "")
        if not self.api_key:
            raise RuntimeError("MODELSCOPE_API_KEY 未设置")
        self.base_url = base_url.rstrip("/")
        self.poll_interval = poll_interval
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        })

    def submit(self, prompt: str, duration: int = 5,
               aspect_ratio: str = "9:16") -> str:
        r = self.session.post(self.base_url + SUBMIT_PATH, json={
            "model": "wan2.1",
            "prompt": prompt,
            "duration": duration,
            "aspect_ratio": aspect_ratio,
        }, timeout=60)
        r.raise_for_status()
        data = r.json()
        return data.get("task_id") or data.get("id")

    def poll(self, task_id: str) -> dict:
        deadline = time.time() + self.timeout
        while time.time() < deadline:
            r = self.session.get(
                self.base_url + TASK_PATH.format(task_id=task_id), timeout=60)
            r.raise_for_status()
            data = r.json()
            status = data.get("status")
            if status in ("succeeded", "completed", "success"):
                return data
            if status in ("failed", "error", "cancelled"):
                raise RuntimeError(f"视频生成失败: {data}")
            time.sleep(self.poll_interval)
        raise TimeoutError(f"任务 {task_id} 超时")

    def generate(self, prompt: str, out_path: str,
                 duration: int = 5) -> str:
        task_id = self.submit(prompt, duration=duration)
        data = self.poll(task_id)
        url = (data.get("video_url") or data.get("url")
               or (data.get("output") or {}).get("video_url"))
        if not url:
            raise RuntimeError(f"未拿到视频地址: {data}")
        with self.session.get(url, stream=True, timeout=300) as r:
            r.raise_for_status()
            with open(out_path, "wb") as f:
                for chunk in r.iter_content(1024 * 64):
                    f.write(chunk)
        return out_path
