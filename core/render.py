"""
core/render.py — Phase 4: Image Post-Processing & Typography Overlay
======================================================================
Resizes, crops, and composites headings/titles onto images using Pillow and OpenCV.
Generates responsive hero images, section images, and dedicated tall Pinterest pins
with clean semi-transparent gradient bands and drop-shadowed typography.
"""

from pathlib import Path
import re
import shutil
import sqlite3
from typing import Any, Dict, List, Optional, Tuple, Union

from PIL import Image, ImageDraw, ImageFont
import requests

from core.checkpoints import is_render_done, save_render_done
from core.images import save_image_file

_FONT_URLS = [
    ("https://github.com/google/fonts/raw/main/ofl/montserrat/static/Montserrat-ExtraBold.ttf", "Montserrat-ExtraBold.ttf"),
    ("https://github.com/google/fonts/raw/main/ofl/inter/static/Inter-Bold.ttf", "Inter-Bold.ttf"),
    ("https://github.com/google/fonts/raw/main/ofl/oswald/static/Oswald-Bold.ttf", "Oswald-Bold.ttf"),
]


def download_or_get_font(font_dir: Path) -> Optional[Path]:
    """Downloads a modern Google Font for typography overlay or returns existing cached font."""
    font_dir.mkdir(parents=True, exist_ok=True)
    for url, fname in _FONT_URLS:
        dest = font_dir / fname
        if dest.exists() and dest.stat().st_size > 10000:
            return dest
        try:
            r = requests.get(url, timeout=15)
            if r.status_code == 200 and len(r.content) > 10000:
                dest.write_bytes(r.content)
                return dest
        except Exception:
            pass

    # Windows system font fallback
    sys_font = Path("C:/Windows/Fonts/segoeuib.ttf")
    if sys_font.exists():
        return sys_font
    sys_arial = Path("C:/Windows/Fonts/arialbd.ttf")
    if sys_arial.exists():
        return sys_arial

    return None


def crop_and_resize(src_path: Path, out_path: Path, target_w: int, target_h: int, cfg: Dict[str, Any]) -> None:
    """Scales and center-crops an image to exact target dimensions."""
    img = Image.open(src_path).convert("RGB")
    sw, sh = img.size
    scale = max(target_w / sw, target_h / sh)
    nw, nh = int(sw * scale), int(sh * scale)
    img = img.resize((nw, nh), Image.LANCZOS)
    left = (nw - target_w) // 2
    top = (nh - target_h) // 2
    cropped = img.crop((left, top, left + target_w, top + target_h))
    save_image_file(cropped, out_path, cfg)


def fit_text_to_box(
    heading: str,
    out_w: int,
    out_h: int,
    font_path: Optional[Path],
    band_h: int,
    margin_x: int,
    margin_y: int,
) -> Tuple[Any, str, int, int, Tuple[int, int, int, int]]:
    """Calculates optimal font size and line wrapping to fit within overlay band."""
    avail_w = out_w - (margin_x * 2)
    max_h = band_h - (margin_y * 2)

    min_size = max(18, int(out_h * 0.035))
    max_size = min(96, int(out_h * 0.085))

    tmp_img = Image.new("RGBA", (out_w, out_h))
    tmp_draw = ImageDraw.Draw(tmp_img)

    best_font = None
    best_wrapped = heading
    best_size = min_size
    best_bbox = (0, 0, avail_w, min_size)

    words = heading.split()

    for size in range(max_size, min_size - 1, -2):
        try:
            font = ImageFont.truetype(str(font_path), size) if font_path else ImageFont.load_default()
        except Exception:
            font = ImageFont.load_default()

        # Wrap words
        lines = []
        cur_line = []
        for w in words:
            test_line = " ".join(cur_line + [w])
            bbox = tmp_draw.textbbox((0, 0), test_line, font=font)
            if bbox[2] - bbox[0] <= avail_w:
                cur_line.append(w)
            else:
                if cur_line:
                    lines.append(" ".join(cur_line))
                cur_line = [w]
        if cur_line:
            lines.append(" ".join(cur_line))

        if len(lines) > 3:
            continue

        wrapped = "\n".join(lines)
        total_bbox = tmp_draw.multiline_textbbox((0, 0), wrapped, font=font, spacing=int(size * 0.25))
        h = total_bbox[3] - total_bbox[1]

        if h <= max_h:
            best_font = font
            best_wrapped = wrapped
            best_size = size
            best_bbox = total_bbox
            break

    if not best_font:
        try:
            best_font = ImageFont.truetype(str(font_path), min_size) if font_path else ImageFont.load_default()
        except Exception:
            best_font = ImageFont.load_default()

    return best_font, best_wrapped, best_size, int(best_size * 0.25), best_bbox


def render_image_with_overlay(
    bg_path: Path,
    heading: str,
    out_path: Path,
    out_w: int,
    out_h: int,
    font_path: Optional[Path],
    cfg: Dict[str, Any],
) -> None:
    """Composites heading text onto the image with gradient background and contrast shadows."""
    # 1. Base Crop & Scale
    bg_full = Image.open(bg_path).convert("RGB")
    sw, sh = bg_full.size
    scale = max(out_w / sw, out_h / sh)
    nw, nh = int(sw * scale), int(sh * scale)
    bg_full = bg_full.resize((nw, nh), Image.LANCZOS)
    left = (nw - out_w) // 2
    top = (nh - out_h) // 2
    bg = bg_full.crop((left, top, left + out_w, top + out_h))

    # 2. Semi-Transparent Gradient Band
    margin_x = int(out_w * 0.05)
    margin_y = int(out_h * 0.04)
    band_h = int(out_h * 0.38)

    overlay = Image.new("RGBA", (out_w, out_h), (0, 0, 0, 0))
    ov_draw = ImageDraw.Draw(overlay)
    for y in range(band_h):
        alpha = int(245 * ((y / band_h) ** 0.55))
        ov_draw.rectangle([(0, out_h - band_h + y), (out_w, out_h - band_h + y + 1)], fill=(0, 0, 0, alpha))

    canvas = Image.alpha_composite(bg.convert("RGBA"), overlay)

    # 3. Typography Calculation
    font, wrapped, fsize, line_spacing, bbox = fit_text_to_box(
        heading, out_w, out_h, font_path, band_h, margin_x, margin_y
    )

    text_h = bbox[3] - bbox[1]
    ty = (out_h - band_h) + (band_h - text_h) // 2 - margin_y
    ty = max(min(ty, out_h - text_h - margin_y), out_h - band_h + margin_y)

    text_layer = Image.new("RGBA", (out_w, out_h), (0, 0, 0, 0))
    t_draw = ImageDraw.Draw(text_layer)

    # Accent Bar
    bar_h = max(3, fsize // 18)
    bar_w = int(out_w * 0.08)
    bar_y = max(ty - bar_h - int(fsize * 0.28), out_h - band_h + margin_y // 2)
    t_draw.rectangle([(margin_x, bar_y), (margin_x + bar_w, bar_y + bar_h)], fill=(56, 139, 253, 255))

    # Drop Shadow for contrast
    shadow_offset = max(1, min(3, fsize // 30))
    for dx, dy in [(-shadow_offset, -shadow_offset), (shadow_offset, -shadow_offset),
                  (-shadow_offset, shadow_offset), (shadow_offset, shadow_offset),
                  (0, shadow_offset), (0, -shadow_offset)]:
        t_draw.multiline_text((margin_x + dx, ty + dy), wrapped, font=font, fill=(0, 0, 0, 220), spacing=line_spacing)

    # Clean White Foretext
    t_draw.multiline_text((margin_x, ty), wrapped, font=font, fill=(255, 255, 255, 255), spacing=line_spacing)

    final_img = Image.alpha_composite(canvas, text_layer).convert("RGB")
    save_image_file(final_img, out_path, cfg)


def phase_render(
    structured: Dict[str, Any],
    raw_paths: Dict[str, Any],
    out_dir: Path,
    url: str,
    db: sqlite3.Connection,
    cfg: Dict[str, Any],
    progress_callback=None,
) -> Dict[str, Any]:
    """
    Executes Phase 4: Composites headings/titles or crops images to exact target dimensions.
    """
    rdir = out_dir / "rendered"
    rdir.mkdir(parents=True, exist_ok=True)
    ext = cfg.get("image_ext", "webp")

    font_path = download_or_get_font(out_dir / "fonts")

    # 1. Feature Hero Render
    feat_raw = raw_paths["feature"]
    feat_out = rdir / f"feature_rendered.{ext}"
    feat_rel = str(feat_out.relative_to(out_dir))

    feat_done = is_render_done(db, "feature") and feat_out.exists() and feat_out.stat().st_size > 5000
    if not feat_done:
        if cfg.get("feature_text_overlay"):
            title = structured.get("title", "")
            render_image_with_overlay(
                feat_raw, title, feat_out,
                cfg.get("feature_w", 1200), cfg.get("feature_h", 630), font_path, cfg
            )
        else:
            crop_and_resize(
                feat_raw, feat_out,
                cfg.get("feature_w", 1200), cfg.get("feature_h", 630), cfg
            )
        save_render_done(db, "feature", feat_out)

    if progress_callback:
        progress_callback("feature", 1, len(structured.get("sections", [])) + 1)

    # 2. Pinterest Pin Render
    pin_rel = None
    if cfg.get("pinterest_pin"):
        pin_out = rdir / f"pin_rendered.{ext}"
        pin_done = is_render_done(db, "pin") and pin_out.exists() and pin_out.stat().st_size > 5000
        if not pin_done:
            pin_src = raw_paths.get("pin") or feat_raw
            title = structured.get("title", "")
            render_image_with_overlay(
                pin_src, title, pin_out,
                cfg.get("pin_w", 1000), cfg.get("pin_h", 1500), font_path, cfg
            )
            save_render_done(db, "pin", pin_out)
        pin_rel = str(pin_out.relative_to(out_dir))

    # 3. Section Renders
    sections = structured.get("sections", [])
    sec_raws = raw_paths["sections"]
    sec_outs: List[str] = []

    for i, (sec, raw) in enumerate(zip(sections, sec_raws)):
        sec_out = rdir / f"sec_{i:02d}_rendered.{ext}"
        sec_outs.append(str(sec_out))
        sec_key = f"sec_{i:02d}"

        sec_done = is_render_done(db, sec_key) and sec_out.exists() and sec_out.stat().st_size > 2000
        if not sec_done:
            heading = sec.get("heading", f"Section {i + 1}")
            if cfg.get("heading_text_overlay"):
                render_image_with_overlay(
                    raw, heading, sec_out,
                    cfg.get("render_w", 1200), cfg.get("render_h", 675), font_path, cfg
                )
            else:
                crop_and_resize(
                    raw, sec_out,
                    cfg.get("render_w", 1200), cfg.get("render_h", 675), cfg
                )
            save_render_done(db, sec_key, sec_out)

        if progress_callback:
            progress_callback(f"sec_{i}", i + 2, len(sections) + (2 if cfg.get("pinterest_pin") else 1))

    return {
        "feature": feat_rel,
        "sections": sec_outs,
        "pin": pin_rel,
    }
