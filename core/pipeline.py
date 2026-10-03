"""
core/pipeline.py — Master Pipeline Orchestrator & Execution Loop
==================================================================
Coordinates the sequential execution of Phases 1 through 6 for a single URL
or across continuous batches. Manages state checkpoints, auto-resumption,
quota cooldowns, and real-time progress callbacks.
"""

import hashlib
import json
from pathlib import Path
import shutil
import sqlite3
import time
from typing import Any, Callable, Dict, Optional

from core.checkpoints import (
    clear_quota_end_time,
    get_quota_end_time,
    init_db,
    set_quota_end_time,
)
from core.compile import phase_compile
from core.extract import phase_extract
from core.images import QuotaExceededError, phase_images
from core.render import phase_render
from core.transform import phase_transform


def get_url_output_dir(url: str, base_output_dir: Union_Path = "pipeline_output") -> Path:
    """Generates the deterministic output directory for a given URL."""
    url_hash = hashlib.md5(url.strip().encode("utf-8")).hexdigest()[:8]
    out_dir = Path(base_output_dir) / url_hash
    out_dir.mkdir(parents=True, exist_ok=True)
    return out_dir


# Type alias
Union_Path = Any


def run_single_url_pipeline(
    url: str,
    skills_text: str,
    cfg: Dict[str, Any],
    category_override: str = "",
    fresh: bool = False,
    progress_callback: Optional[Callable[[str, Dict[str, Any]], None]] = None,
    should_stop_callback: Optional[Callable[[], bool]] = None,
) -> Dict[str, Any]:
    """
    Executes the complete 6-phase pipeline for one URL.
    Returns:
        {
            "status": "done" | "failed" | "stopped" | "quota_wait",
            "url": str,
            "out_dir": str,
            "structured": dict,
            "html_path": str,
            "wp_result": dict,
            "error": str,
        }
    """
    out_dir = get_url_output_dir(url, cfg.get("output_dir", "pipeline_output"))

    if fresh:
        for sub in ("images", "rendered"):
            d = out_dir / sub
            if d.exists():
                shutil.rmtree(d, ignore_errors=True)

    db_path = out_dir / cfg.get("db_path", "pipeline_state.db")
    db = init_db(db_path)

    # Check active quota wait
    quota_end = get_quota_end_time(db)
    if quota_end and time.time() < quota_end:
        rem = int(quota_end - time.time())
        return {
            "status": "quota_wait",
            "url": url,
            "out_dir": str(out_dir),
            "quota_seconds_remaining": rem,
        }

    def emit(phase: str, percent: int, message: str, meta: Optional[Dict] = None):
        if progress_callback:
            progress_callback(phase, {
                "percent": percent,
                "message": message,
                "meta": meta or {},
                "url": url
            })

    consecutive_errors = 0

    while consecutive_errors < 3:
        if should_stop_callback and should_stop_callback():
            db.close()
            return {"status": "stopped", "url": url, "out_dir": str(out_dir)}

        try:
            t0 = time.time()

            # ── Phase 1: Extract ──
            emit("extract", 10, "Extracting article content from source URL...")
            extracted = phase_extract(url, db, fresh=fresh)
            emit("extract", 25, f"Extraction complete: '{extracted.get('title', '')[:50]}...'", {
                "title": extracted.get("title"),
                "sections_count": len(extracted.get("sections", [])),
                "chars": len(extracted.get("raw_text", ""))
            })

            if should_stop_callback and should_stop_callback():
                db.close()
                return {"status": "stopped", "url": url, "out_dir": str(out_dir)}

            # ── Phase 2: Transform ──
            emit("transform", 30, "Rewriting content for SEO, GEO & AEO with AI models...")
            structured = phase_transform(
                extracted, url, db, skills_text, cfg,
                category_override=category_override, fresh=fresh
            )
            emit("transform", 50, "Content transformation & JSON schema complete", {
                "keywords": structured.get("keywords"),
                "category": structured.get("category"),
                "sections": len(structured.get("sections", []))
            })

            if should_stop_callback and should_stop_callback():
                db.close()
                return {"status": "stopped", "url": url, "out_dir": str(out_dir)}

            # ── Phase 3: AI Images ──
            emit("images", 55, "Synthesizing hero, section, and Pinterest pin images...")
            try:
                def img_cb(slug, cur, total):
                    sub_pct = 55 + int((cur / max(1, total)) * 20)
                    emit("images", sub_pct, f"Generating image {cur}/{total} ({slug})...")

                raw_paths = phase_images(
                    structured, url, db, out_dir, cfg, progress_callback=img_cb
                )
            except QuotaExceededError as qe:
                cooldown_hrs = cfg.get("quota_wait_hours", 6)
                end_time = time.time() + (cooldown_hrs * 3600)
                set_quota_end_time(db, end_time)
                emit("quota_wait", 55, f"AI quota reached. Cooldown initiated ({cooldown_hrs}h).")
                db.close()
                return {
                    "status": "quota_wait",
                    "url": url,
                    "out_dir": str(out_dir),
                    "quota_seconds_remaining": cooldown_hrs * 3600,
                    "error": str(qe)
                }

            clear_quota_end_time(db)
            emit("images", 75, "All images successfully generated")

            if should_stop_callback and should_stop_callback():
                db.close()
                return {"status": "stopped", "url": url, "out_dir": str(out_dir)}

            # ── Phase 4: Render & Typography ──
            emit("render", 80, "Compositing typography overlays and scaling resolutions...")
            rendered = phase_render(
                structured, raw_paths, out_dir, url, db, cfg
            )
            emit("render", 90, "Image compositing & post-processing complete")

            # ── Phase 5: Compile ──
            emit("compile", 92, "Compiling responsive HTML and Schema.org JSON-LD...")
            html_path = phase_compile(structured, rendered, out_dir)
            emit("compile", 95, f"HTML preview compiled -> {html_path.name}")

            # ── Phase 6: WordPress Publish ──
            wp_res = None
            if cfg.get("auto_publish", True) and cfg.get("base_url"):
                emit("publish", 96, "Publishing natively to WordPress as Gutenberg blocks...")
                try:
                    from integrations.wordpress import phase_publish
                    wp_res = phase_publish(structured, rendered, out_dir, url, db, config=cfg)
                    emit("publish", 100, f"Published to WordPress! Post ID: {wp_res.get('post_id')}")
                except Exception as wpe:
                    emit("publish", 98, f"WordPress publication notice: {wpe}")

            db.close()
            return {
                "status": "done",
                "url": url,
                "out_dir": str(out_dir),
                "structured": structured,
                "html_path": str(html_path),
                "wp_result": wp_res,
                "elapsed": time.time() - t0,
            }

        except Exception as e:
            consecutive_errors += 1
            emit("error", 0, f"Error processing URL (attempt {consecutive_errors}/3): {e}")
            if consecutive_errors >= 3:
                db.close()
                return {
                    "status": "failed",
                    "url": url,
                    "out_dir": str(out_dir),
                    "error": str(e)
                }
            time.sleep(5)

    db.close()
    return {"status": "failed", "url": url, "out_dir": str(out_dir), "error": "Exceeded 3 retry attempts"}
