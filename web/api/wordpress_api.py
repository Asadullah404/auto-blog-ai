"""
web/api/wordpress_api.py — REST API for WordPress Integration
================================================================
Endpoints for connection testing, single-post publication, and bulk publishing.
"""

import json
from pathlib import Path

from flask import Blueprint, jsonify, request

from config.settings import get_current_config
from core.checkpoints import init_db
from integrations.wordpress import already_published, phase_publish, test_connection

wordpress_bp = Blueprint("wordpress_api", __name__, url_prefix="/api/wordpress")


@wordpress_bp.route("/test", methods=["POST"])
def check_wp_connection():
    """Validates WordPress site connection and credentials."""
    data = request.get_json(silent=True) or {}
    cfg = dict(get_current_config())
    cfg.update(data)

    res = test_connection(cfg)
    status_code = 200 if res.get("ok") else 400
    return jsonify(res), status_code


@wordpress_bp.route("/publish-all", methods=["POST"])
def publish_all_generated():
    """Scans pipeline_output/ and publishes any completed articles that aren't yet published."""
    cfg = get_current_config()
    out_root = Path(cfg.get("output_dir", "pipeline_output"))

    if not out_root.exists():
        return jsonify({"ok": True, "published": 0, "message": "No pipeline_output folder found."})

    test_res = test_connection(cfg)
    if not test_res.get("ok"):
        return jsonify({"ok": False, "error": f"WordPress connection failed: {test_res.get('error')}"}), 400

    published_count = 0
    skipped_count = 0
    errors = []

    for art_dir in sorted(out_root.iterdir()):
        if not art_dir.is_dir():
            continue

        db_file = art_dir / cfg.get("db_path", "pipeline_state.db")
        if not db_file.exists():
            continue

        db = init_db(db_file)
        # Check transform checkpoint
        cur = db.execute("SELECT key, val FROM checkpoints WHERE key = 'transform_v3'")
        row = cur.fetchone()
        if not row or not row["val"]:
            db.close()
            continue

        try:
            structured = json.loads(row["val"])
            url_row = db.execute("SELECT key FROM checkpoints WHERE key LIKE 'extract%'").fetchone()
            # If URL not explicitly saved in key, fallback to article title as identifier
            article_url = structured.get("title", art_dir.name)

            # Check if already published
            if already_published(db, article_url):
                skipped_count += 1
                db.close()
                continue

            rendered = {
                "feature": str(art_dir / "rendered" / f"feature_rendered.{cfg.get('image_ext', 'webp')}"),
                "sections": [str(p) for p in sorted((art_dir / "rendered").glob("sec_*_rendered.*"))],
                "pin": str(art_dir / "rendered" / f"pin_rendered.{cfg.get('image_ext', 'webp')}")
                if (art_dir / "rendered" / f"pin_rendered.{cfg.get('image_ext', 'webp')}").exists()
                else None,
            }

            phase_publish(structured, rendered, art_dir, article_url, db, config=cfg)
            published_count += 1
        except Exception as e:
            errors.append(f"{art_dir.name}: {e}")
        finally:
            db.close()

    return jsonify({
        "ok": True,
        "published": published_count,
        "skipped": skipped_count,
        "errors": errors,
        "message": f"Bulk publish complete: {published_count} published, {skipped_count} already up to date.",
    })
