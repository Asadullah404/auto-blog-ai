"""
integrations/pollinations.py — Pollinations AI Client
========================================================
Lightweight HTTP client for Pollinations AI image generation with rate-limit tracking.
"""

from io import BytesIO
from pathlib import Path
import re
import time
from typing import Any, Dict
import urllib.parse

from PIL import Image
import requests


class PollinationsClient:
    def __init__(self, delay_seconds: int = 180):
        self.delay_seconds = delay_seconds
        self.last_call_time = 0.0

    def wait_rate_limit(self):
        if self.delay_seconds <= 0:
            return
        now = time.time()
        elapsed = now - self.last_call_time
        if self.last_call_time > 0 and elapsed < self.delay_seconds:
            wait_needed = int(self.delay_seconds - elapsed)
            time.sleep(wait_needed)

    def generate_image(self, prompt: str, width: int = 1200, height: int = 675, timeout: int = 120) -> Image.Image:
        self.wait_rate_limit()
        clean_prompt = re.sub(r'[\r\n\t]+', ' ', prompt).strip()
        encoded = urllib.parse.quote(clean_prompt)
        url = f"https://image.pollinations.ai/prompt/{encoded}?width={width}&height={height}&nologo=true"

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36"
        }
        r = requests.get(url, headers=headers, timeout=timeout)
        self.last_call_time = time.time()

        if r.status_code != 200:
            raise RuntimeError(f"Pollinations HTTP {r.status_code}: {r.text[:120]}")
        if len(r.content) < 5000:
            raise RuntimeError(f"Pollinations image too small ({len(r.content)} bytes)")

        return Image.open(BytesIO(r.content)).convert("RGB")
