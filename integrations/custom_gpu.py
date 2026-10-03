"""
integrations/custom_gpu.py — Colab / ngrok GPU Image Server Client
====================================================================
Communicates with self-hosted Diffusers / SDXL / RealVisXL endpoints.
Enforces ngrok warning bypass headers and dimension divisibility by 8.
"""

from io import BytesIO
import re
from typing import Optional

from PIL import Image
import requests


class CustomGPUClient:
    def __init__(self, server_url: str):
        url = server_url.strip().rstrip("/")
        if url and not url.endswith("/generate"):
            url = f"{url}/generate"
        self.server_url = url

    def generate_image(
        self,
        prompt: str,
        negative_prompt: str = "",
        width: int = 1024,
        height: int = 768,
        steps: int = 25,
        guidance_scale: float = 6.0,
        timeout: int = 180,
    ) -> Image.Image:
        if not self.server_url:
            raise ValueError("Custom GPU server URL is empty.")

        sd_w = max(64, int(round(width / 8.0)) * 8)
        sd_h = max(64, int(round(height / 8.0)) * 8)

        payload = {
            "prompt": prompt,
            "negative_prompt": negative_prompt,
            "width": sd_w,
            "height": sd_h,
            "steps": steps,
            "guidance_scale": guidance_scale,
        }
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
            "ngrok-skip-browser-warning": "69420",
        }

        resp = requests.post(self.server_url, json=payload, headers=headers, timeout=timeout)
        if resp.status_code != 200:
            raise RuntimeError(f"Server error HTTP {resp.status_code}: {resp.text[:140]}")
        if len(resp.content) < 5000:
            raise RuntimeError("Server returned an invalid or empty image payload.")

        return Image.open(BytesIO(resp.content)).convert("RGB")
