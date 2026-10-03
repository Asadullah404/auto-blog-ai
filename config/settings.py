"""
config/settings.py — Centralized Configuration Management
============================================================
Handles thread-safe loading, validating, and saving of application configuration,
merging persisted JSON settings with environment variables and defaults.
"""

import json
import os
import threading
from pathlib import Path
from typing import Any, Dict, Tuple

from config.constants import (
    CUSTOM_RES_REGEX,
    DEFAULT_CONFIG,
    DEFAULT_CONFIG_PATH,
    IMAGE_FORMATS,
    IMAGE_TYPES,
    RESOLUTION_PRESETS,
)

_config_lock = threading.RLock()
_cached_config: Dict[str, Any] = {}


def resolve_dimensions(resolution_str: str, aspect: float = 9 / 16) -> Tuple[int, int]:
    """
    Resolves a preset or custom resolution string into concrete (width, height) integers.
    Presets:
      'sd'  -> 854w  x (854 * aspect)h
      'hd'  -> 1200w x (1200 * aspect)h
      'fhd' -> 1920w x (1920 * aspect)h
      '2k'  -> 2560w x (2560 * aspect)h
    Custom format: 'WIDTHxHEIGHT' (e.g. '1000x1500') uses exact dimensions without aspect ratio.
    """
    res = (resolution_str or "hd").strip().lower()
    custom_match = CUSTOM_RES_REGEX.match(res)
    if custom_match:
        w = max(64, min(8000, int(custom_match.group(1))))
        h = max(64, min(8000, int(custom_match.group(2))))
        return w, h

    width = RESOLUTION_PRESETS.get(res, RESOLUTION_PRESETS["hd"])
    height = round(width * aspect)
    return width, height


def get_image_dimensions(cfg: Dict[str, Any]) -> Dict[str, int]:
    """Calculates all concrete image widths and heights from config resolutions."""
    heading_res = cfg.get("image_resolution", "hd")
    feat_res = cfg.get("feature_resolution", heading_res)
    pin_res = cfg.get("pin_resolution", "1000x1500")

    render_w, render_h = resolve_dimensions(heading_res, aspect=9 / 16)
    feature_w, feature_h = resolve_dimensions(feat_res, aspect=0.525)
    pin_w, pin_h = resolve_dimensions(pin_res, aspect=1.5)

    return {
        "render_w": render_w,
        "render_h": render_h,
        "feature_w": feature_w,
        "feature_h": feature_h,
        "pin_w": pin_w,
        "pin_h": pin_h,
    }


def load_config(file_path: Path = None) -> Dict[str, Any]:
    """
    Loads configuration from file_path (or default pipeline_config.json),
    merging with defaults and environment variables. Thread-safe.
    """
    global _cached_config
    target_path = Path(file_path or os.environ.get("PIPELINE_CONFIG", DEFAULT_CONFIG_PATH))

    with _config_lock:
        cfg = dict(DEFAULT_CONFIG)

        if target_path.exists():
            try:
                raw_data = json.loads(target_path.read_text(encoding="utf-8"))
                if isinstance(raw_data, dict):
                    # Handle both flat config and bundle-nested config {"settings": {...}}
                    payload = raw_data.get("settings", raw_data)
                    for k, v in payload.items():
                        if k in cfg and v is not None:
                            cfg[k] = v
            except Exception as e:
                print(f"[!] Warning reading {target_path}: {e}. Using defaults.")

        # Environment variable overrides
        if "WP_URL" in os.environ:
            cfg["base_url"] = os.environ["WP_URL"].rstrip("/")
        if "WP_USER" in os.environ:
            cfg["username"] = os.environ["WP_USER"]
        if "WP_APP_PASSWORD" in os.environ:
            cfg["app_password"] = os.environ["WP_APP_PASSWORD"]
        if "WP_STATUS" in os.environ:
            cfg["status"] = os.environ["WP_STATUS"]
        if "WP_AUTO_PUBLISH" in os.environ:
            cfg["auto_publish"] = os.environ["WP_AUTO_PUBLISH"].strip().lower() in ("1", "true", "yes", "on")
        if "WP_SEO_PLUGIN" in os.environ:
            cfg["seo_plugin"] = os.environ["WP_SEO_PLUGIN"]

        # Validate image format
        fmt = cfg.get("image_format", "webp").lower()
        if fmt not in IMAGE_FORMATS:
            fmt = "webp"
        cfg["image_format"] = fmt
        pil_fmt, ext = IMAGE_FORMATS[fmt]
        cfg["image_pil_format"] = pil_fmt
        cfg["image_ext"] = ext

        # Calculate dimensions
        dims = get_image_dimensions(cfg)
        cfg.update(dims)

        _cached_config = cfg
        return dict(_cached_config)


def save_config(new_settings: Dict[str, Any], file_path: Path = None) -> Dict[str, Any]:
    """
    Atomically saves updated settings to the configuration file and refreshes cache.
    Thread-safe.
    """
    global _cached_config
    target_path = Path(file_path or os.environ.get("PIPELINE_CONFIG", DEFAULT_CONFIG_PATH))

    with _config_lock:
        current = dict(DEFAULT_CONFIG)
        if target_path.exists():
            try:
                existing = json.loads(target_path.read_text(encoding="utf-8"))
                if isinstance(existing, dict):
                    current.update(existing)
            except Exception:
                pass

        # Update with new settings
        for k, v in new_settings.items():
            current[k] = v

        # Write safely
        target_path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = target_path.with_suffix(".tmp")
        temp_path.write_text(json.dumps(current, indent=2, ensure_ascii=False), encoding="utf-8")
        temp_path.replace(target_path)

        # Refresh cached config
        _cached_config = load_config(target_path)
        return dict(_cached_config)


def get_current_config() -> Dict[str, Any]:
    """Returns the cached configuration or loads it if empty."""
    global _cached_config
    if not _cached_config:
        return load_config()
    with _config_lock:
        return dict(_cached_config)
