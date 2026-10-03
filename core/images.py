"""
core/images.py — Phase 3: Multi-Engine AI Image Synthesis
============================================================
Generates high-resolution hero images, heading images, and dedicated vertical Pinterest pins.
Supports Google Antigravity (Imagen), Pollinations AI, and Custom Colab/ngrok GPU (RealVisXL / SDXL)
with visual style presets, master image directives, and negative prompt filtering.
"""

import os
import re
import shutil
import sqlite3
import time
import urllib.parse
from io import BytesIO
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

import requests
from PIL import Image, ImageStat

from config.constants import IMAGE_TYPES
from core.checkpoints import is_image_done, save_image_done
from core.transform import run_agy, strip_ansi

# Brain roots for agy imagen discovery
AGY_BRAIN_ROOTS = [
    Path.home() / ".gemini" / "antigravity" / "brain",
    Path.home() / ".antigravity" / "brain",
]

_IMG_PATH_RE = re.compile(
    r'(?:saved|written|output|to|at|file|path)\s*[:=\s]\s*["\']?([^\s"\'<>]+\.(?:png|jpg|jpeg|webp))["\']?'
    r'|([^\s\'"<>]*\.(?:png|jpg|jpeg|webp))',
    re.IGNORECASE,
)

_QUOTA_SIGNALS = [
    "quota", "rate limit", "rate_limit", "resource exhausted",
    "429", "too many requests", "limit exceeded", "billing",
    "ResourceExhausted", "RESOURCE_EXHAUSTED", "quota exceeded",
    "daily limit", "free tier", "upgrade",
]

_LAST_POLLINATIONS_TIME = 0.0
_FALLBACK_ACTIVE = False


class QuotaExceededError(Exception):
    """Raised when an explicit AI generation quota or rate limit is hit."""
    pass


class ImageGenerationError(Exception):
    """Raised when generation fails for reasons other than quota (e.g. malformed response, flat image)."""
    pass


def is_quota_error(text: str) -> bool:
    """Checks whether an error text matches known quota/rate-limit signals."""
    lower = text.lower()
    return any(sig.lower() in lower for sig in _QUOTA_SIGNALS)


def snapshot_brain() -> Set[Path]:
    """Snapshots existing images in the Antigravity artifact brain directory."""
    found = set()
    for root in AGY_BRAIN_ROOTS:
        if root.exists():
            for ext in ("png", "jpg", "jpeg", "webp"):
                found.update(root.rglob(f"*.{ext}"))
    return found


def find_new_image(before: Set[Path], raw_output: str) -> Optional[Path]:
    """Finds newly created image files referenced in raw output or created on disk."""
    raw = strip_ansi(raw_output)
    for m in _IMG_PATH_RE.finditer(raw):
        candidate = (m.group(1) or m.group(2) or "").strip().strip("'\".,;")
        if candidate.startswith("/") or (len(candidate) > 2 and candidate[1] == ":"):
            p = Path(candidate)
            if p.exists() and p.stat().st_size > 1000:
                return p
    after = snapshot_brain()
    new = after - before
    if new:
        return max(new, key=lambda p: p.stat().st_size)
    return None


def is_blank_image(img: Image.Image, min_stddev: float = 4.0) -> bool:
    """Detects solid, blank, or grey frames returned by content filters."""
    small = img.convert("RGB").resize((64, 64))
    stat = ImageStat.Stat(small)
    return max(stat.stddev) < min_stddev


def resolve_image_prompt(scene: str, image_role: str, cfg: Dict[str, Any]) -> str:
    """
    Combines the raw scene description with:
      1. Global Master Image Prompt (if apply_master_to_all_images is enabled)
      2. Role-specific overrides (feature_image_master_prompt, heading_image_master_prompt, pin_image_master_prompt)
      3. Visual Style Presets (from IMAGE_TYPES or custom text)
    """
    clean_scene = re.sub(r'[\r\n\t]+', ' ', scene).strip().rstrip(".,; ")
    parts = []

    # 1. Global Master Image Prompt
    master_img = cfg.get("master_image_prompt", "").strip()
    apply_all = cfg.get("apply_master_to_all_images", True)
    if master_img and (apply_all or image_role == "general"):
        if "{prompt}" in master_img:
            clean_scene = master_img.replace("{prompt}", clean_scene)
        else:
            parts.append(master_img)

    # 2. Role-Specific Master Prompt Overrides
    if image_role == "feature":
        feat_master = cfg.get("feature_image_master_prompt", "").strip()
        if feat_master:
            if "{prompt}" in feat_master:
                clean_scene = feat_master.replace("{prompt}", clean_scene)
            else:
                parts.append(feat_master)
    elif image_role == "section":
        head_master = cfg.get("heading_image_master_prompt", "").strip()
        if head_master:
            if "{prompt}" in head_master:
                clean_scene = head_master.replace("{prompt}", clean_scene)
            else:
                parts.append(head_master)
    elif image_role == "pin":
        pin_master = cfg.get("pin_image_master_prompt", "").strip()
        if pin_master:
            if "{prompt}" in pin_master:
                clean_scene = pin_master.replace("{prompt}", clean_scene)
            else:
                parts.append(pin_master)

    parts.insert(0, clean_scene)

    # 3. Visual Style Preset Injection
    img_type_key = cfg.get("image_type", "photo")
    if image_role == "pin":
        pin_type = cfg.get("pin_image_type", "inherit")
        if pin_type and pin_type != "inherit":
            img_type_key = pin_type

    if img_type_key == "custom":
        custom_style = (
            cfg.get("pin_image_type_custom", "").strip()
            if image_role == "pin" and cfg.get("pin_image_type") == "custom"
            else cfg.get("image_type_custom", "").strip()
        )
        if custom_style:
            parts.append(custom_style)
    elif img_type_key in IMAGE_TYPES:
        type_style = IMAGE_TYPES[img_type_key]["prompt"]
        if type_style:
            parts.append(type_style)

    combined = ", ".join(p.strip().rstrip(".,; ") for p in parts if p.strip())
    if "no text" not in combined.lower():
        combined += ", no text, no watermark"
    return combined


def save_image_file(img: Image.Image, dest: Path, cfg: Dict[str, Any]) -> None:
    """Saves a PIL image with configured format and quality."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    fmt = cfg.get("image_pil_format", "WEBP")
    quality = cfg.get("image_quality", 88)
    kwargs = {"quality": quality}
    if fmt == "JPEG":
        kwargs["optimize"] = True
    img.save(dest, fmt, **kwargs)


def wait_pollinations_rate_limit(delay: int) -> None:
    """Throttles requests to Pollinations AI to avoid rate-limiting."""
    global _LAST_POLLINATIONS_TIME
    if delay <= 0:
        return
    now = time.time()
    elapsed = now - _LAST_POLLINATIONS_TIME
    if _LAST_POLLINATIONS_TIME > 0 and elapsed < delay:
        wait_needed = int(delay - elapsed)
        time.sleep(wait_needed)


def generate_pollinations(
    scene: str, dest: Path, width: int, height: int, label: str, cfg: Dict[str, Any]
) -> bool:
    """Generates an image via Pollinations AI with exact dimensions."""
    global _LAST_POLLINATIONS_TIME
    delay = cfg.get("pollinations_delay", 180)
    wait_pollinations_rate_limit(delay)

    clean_prompt = re.sub(r'[\r\n\t]+', ' ', scene).strip()
    encoded_prompt = urllib.parse.quote(clean_prompt)
    url = f"https://image.pollinations.ai/prompt/{encoded_prompt}?width={width}&height={height}&nologo=true"

    max_retries = cfg.get("img_max_retries", 3)
    retry_delay = cfg.get("img_retry_delay", 15)

    for attempt in range(1, max_retries + 1):
        try:
            headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/124.0.0.0 Safari/537.36"}
            r = requests.get(url, headers=headers, timeout=120)
            _LAST_POLLINATIONS_TIME = time.time()

            if r.status_code != 200:
                if attempt < max_retries:
                    time.sleep(retry_delay)
                    continue
                raise ImageGenerationError(f"Pollinations AI returned HTTP {r.status_code} for {label}")

            if len(r.content) < cfg.get("img_min_file_bytes", 5000):
                if attempt < max_retries:
                    time.sleep(retry_delay)
                    continue
                raise ImageGenerationError(f"Pollinations AI returned undersized image for {label}")

            img = Image.open(BytesIO(r.content)).convert("RGB")
            if is_blank_image(img, cfg.get("img_min_stddev", 4.0)):
                if attempt < max_retries:
                    time.sleep(retry_delay)
                    continue
                raise ImageGenerationError(f"Pollinations AI returned blank/flat image for {label}")

            save_image_file(img, dest, cfg)
            return True
        except requests.RequestException as e:
            _LAST_POLLINATIONS_TIME = time.time()
            if attempt < max_retries:
                time.sleep(retry_delay)
                continue
            raise ImageGenerationError(f"Pollinations AI connection failed for {label}: {e}")

    return False


def generate_myserver(
    scene: str, dest: Path, width: int, height: int, label: str, cfg: Dict[str, Any]
) -> bool:
    """Generates an image via a custom GPU server (e.g. Colab / ngrok RealVisXL)."""
    server_url = cfg.get("server_url", "").strip()
    if not server_url:
        raise ImageGenerationError("Custom GPU server URL is empty.")

    server_url = server_url.rstrip("/")
    if not server_url.endswith("/generate"):
        server_url = server_url + "/generate"

    sd_width = max(64, int(round(width / 8.0)) * 8)
    sd_height = max(64, int(round(height / 8.0)) * 8)

    img_type_key = cfg.get("image_type", "photo")
    if "pin" in label.lower() and cfg.get("pin_image_type") and cfg.get("pin_image_type") != "inherit":
        img_type_key = cfg["pin_image_type"]
    custom_neg = IMAGE_TYPES.get(img_type_key, {}).get("negative", "")
    neg_prompt = f"{custom_neg}, text, watermark, writing, words, letters, font, typography" if custom_neg else "cartoon, drawing, painting, blurry, deformed hands, bad quality, oversaturated, CGI, text, watermark"

    payload = {
        "prompt": scene,
        "negative_prompt": neg_prompt,
        "width": sd_width,
        "height": sd_height,
        "steps": 25,
        "guidance_scale": 6.0,
    }
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
        "ngrok-skip-browser-warning": "69420",
    }

    max_retries = cfg.get("img_max_retries", 3)
    retry_delay = cfg.get("img_retry_delay", 15)

    for attempt in range(1, max_retries + 1):
        try:
            r = requests.post(server_url, json=payload, headers=headers, timeout=180)
            if r.status_code != 200:
                if attempt < max_retries:
                    time.sleep(retry_delay)
                    continue
                raise ImageGenerationError(f"Custom server returned HTTP {r.status_code} for {label}")

            if len(r.content) < cfg.get("img_min_file_bytes", 5000):
                if attempt < max_retries:
                    time.sleep(retry_delay)
                    continue
                raise ImageGenerationError(f"Custom server returned undersized image for {label}")

            img = Image.open(BytesIO(r.content)).convert("RGB")
            if is_blank_image(img, cfg.get("img_min_stddev", 4.0)):
                if attempt < max_retries:
                    time.sleep(retry_delay)
                    continue
                raise ImageGenerationError(f"Custom server returned blank/flat image for {label}")

            save_image_file(img, dest, cfg)
            return True
        except requests.RequestException as e:
            if attempt < max_retries:
                time.sleep(retry_delay)
                continue
            raise ImageGenerationError(f"Custom server connection failed for {label}: {e}")

    return False


def generate_agy(
    scene: str, slug: str, dest: Path, label: str, cfg: Dict[str, Any]
) -> bool:
    """Generates an image via Google Antigravity Imagen CLI."""
    expected_path = dest.parent / f"{slug}_src.png"
    max_retries = cfg.get("img_max_retries", 3)
    retry_delay = cfg.get("img_retry_delay", 15)

    prompt_template = (
        "Generate a high resolution image based on this scene description: '{scene}'. "
        "Save the image to this exact absolute path: '{path}'. "
        "Do not ask for permission. Do not add any text or labels on the image."
    )

    for attempt in range(1, max_retries + 1):
        if expected_path.exists():
            try:
                expected_path.unlink()
            except Exception:
                pass
        before = snapshot_brain()
        prompt = prompt_template.format(scene=scene, path=expected_path)

        try:
            raw = run_agy(prompt, timeout=cfg.get("agy_img_timeout", 120))
        except Exception as e:
            if is_quota_error(str(e)):
                raise QuotaExceededError(f"Imagen quota reached while generating {label}")
            if attempt < max_retries:
                time.sleep(retry_delay)
                continue
            raise ImageGenerationError(f"agy execution error for {label}: {e}")

        clean = strip_ansi(raw)
        if is_quota_error(clean):
            raise QuotaExceededError(f"Imagen quota reached while generating {label}")

        if expected_path.exists() and expected_path.stat().st_size > 1000:
            img_path = expected_path
        else:
            img_path = find_new_image(before, clean)

        if img_path is None:
            if attempt < max_retries:
                time.sleep(retry_delay)
                continue
            raise ImageGenerationError(f"No image file produced for {label}")

        try:
            if img_path.stat().st_size < cfg.get("img_min_file_bytes", 5000):
                if attempt < max_retries:
                    time.sleep(retry_delay)
                    continue
                raise ImageGenerationError(f"Image too small for {label}")

            img = Image.open(img_path).convert("RGB")
            if is_blank_image(img, cfg.get("img_min_stddev", 4.0)):
                if attempt < max_retries:
                    time.sleep(retry_delay)
                    continue
                raise ImageGenerationError(f"Image is flat/blank for {label}")

            save_image_file(img, dest, cfg)
            if img_path == expected_path:
                try:
                    expected_path.unlink()
                except Exception:
                    pass
            return True
        except Exception as e:
            if attempt < max_retries:
                time.sleep(retry_delay)
                continue
            raise ImageGenerationError(f"Image processing failed for {label}: {e}")

    return True


def generate_single_image(
    scene: str,
    slug: str,
    dest: Path,
    label: str,
    db: sqlite3.Connection,
    url: str,
    cfg: Dict[str, Any],
    width: int = 1200,
    height: int = 675,
) -> bool:
    """Dispatches a single image generation request to the configured engine."""
    global _FALLBACK_ACTIVE
    img_key = f"img:{slug}"

    saved = is_image_done(db, img_key)
    if saved and Path(saved).exists() and Path(saved).stat().st_size > cfg.get("img_min_file_bytes", 5000):
        if Path(saved) != dest:
            try:
                shutil.copy(saved, dest)
            except Exception:
                pass
        return True

    engine = cfg.get("image_engine", "agy_fallback")

    # 1. Custom GPU Server mode
    if engine == "my_server":
        if generate_myserver(scene, dest, width, height, label, cfg):
            save_image_done(db, img_key, dest)
            return True
        return False

    # 2. Direct Pollinations or Active Fallback mode
    if engine == "pollinations" or (engine == "agy_fallback" and _FALLBACK_ACTIVE):
        if generate_pollinations(scene, dest, width, height, label, cfg):
            save_image_done(db, img_key, dest)
            return True
        return False

    # 3. Antigravity with fallback
    try:
        if generate_agy(scene, slug, dest, label, cfg):
            save_image_done(db, img_key, dest)
            return True
    except QuotaExceededError as qe:
        if engine == "agy_fallback":
            _FALLBACK_ACTIVE = True
            if generate_pollinations(scene, dest, width, height, label, cfg):
                save_image_done(db, img_key, dest)
                return True
        else:
            raise
    except ImageGenerationError as ige:
        if engine == "agy_fallback":
            _FALLBACK_ACTIVE = True
            if generate_pollinations(scene, dest, width, height, label, cfg):
                save_image_done(db, img_key, dest)
                return True
        else:
            raise

    return True


def phase_images(
    structured: Dict[str, Any],
    url: str,
    db: sqlite3.Connection,
    out_dir: Path,
    cfg: Dict[str, Any],
    progress_callback=None,
) -> Dict[str, Any]:
    """
    Executes Phase 3: Generates feature hero image, all section images, and optional Pinterest pin.
    """
    idir = out_dir / "images"
    idir.mkdir(parents=True, exist_ok=True)
    ext = cfg.get("image_ext", "webp")

    sections = structured.get("sections", [])
    inter_delay = cfg.get("img_inter_delay", 8)
    engine = cfg.get("image_engine", "agy_fallback")

    # 1. Feature Hero Image
    feat_dest = idir / f"feature.{ext}"
    raw_feat = structured.get("feature_image_prompt", structured.get("title", "hero"))
    feat_scene = resolve_image_prompt(raw_feat, image_role="feature", cfg=cfg)

    generate_single_image(
        feat_scene, "feature_hero", feat_dest, "Feature Image",
        db, url, cfg, width=cfg.get("feature_w", 1200), height=cfg.get("feature_h", 630)
    )

    if progress_callback:
        progress_callback("feature", 1, len(sections) + 1)

    if engine not in ("pollinations", "my_server"):
        time.sleep(inter_delay)

    # 2. Section Images
    sec_paths = []
    for i, sec in enumerate(sections):
        dest = idir / f"sec_{i:02d}.{ext}"
        sec_paths.append(dest)

        slug = f"{i:02d}_" + re.sub(r"[^a-z0-9]+", "_", sec.get("heading", f"sec_{i}").lower())[:40]
        raw_scene = sec.get("image_prompt", "").strip() or f"{sec.get('heading', '')}. {' '.join(sec.get('paragraphs', ['']))[:150]}"
        scene = resolve_image_prompt(raw_scene, image_role="section", cfg=cfg)

        generate_single_image(
            scene, slug, dest, f"Section {i + 1}",
            db, url, cfg, width=cfg.get("render_w", 1200), height=cfg.get("render_h", 675)
        )

        if progress_callback:
            progress_callback(f"sec_{i}", i + 2, len(sections) + (2 if cfg.get("pinterest_pin") else 1))

        if i < len(sections) - 1 and engine not in ("pollinations", "my_server"):
            time.sleep(inter_delay)

    # 3. Optional Vertical Pinterest Pin Image
    pin_dest = None
    if cfg.get("pinterest_pin"):
        pin_dest = idir / f"pin.{ext}"
        raw_pin = structured.get("pin_image_prompt") or structured.get("feature_image_prompt") or structured.get("title", "pin")
        pin_scene = resolve_image_prompt(raw_pin, image_role="pin", cfg=cfg)

        generate_single_image(
            pin_scene, "pin", pin_dest, "Pinterest Pin",
            db, url, cfg, width=cfg.get("pin_w", 1000), height=cfg.get("pin_h", 1500)
        )

        if progress_callback:
            progress_callback("pin", len(sections) + 2, len(sections) + 2)

    return {
        "feature": feat_dest,
        "sections": sec_paths,
        "pin": pin_dest,
    }
