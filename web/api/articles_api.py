"""
web/api/articles_api.py — REST API for Generated Articles Catalog
===================================================================
Scans pipeline_output/ to discover, inspect, and serve generated articles.
Provides endpoints to view HTML, open in system file explorer, or republish.
"""

from datetime import datetime
import json
import os
from pathlib import Path
import subprocess
import sys

from flask import Blueprint, jsonify, request, send_file

from config.settings import get_current_config
from core.checkpoints import init_db

articles_bp = Blueprint("articles_api", __name__, url_prefix="/api/articles")


@articles_bp.route("", methods=["GET"])
def list_articles():
    """Returns a catalog of all generated articles stored under pipeline_output/."""
    cfg = get_current_config()
    out_root = Path(cfg.get("output_dir", "pipeline_output"))

    articles = []
    if not out_root.exists():
        return jsonify({"articles": []})

    for folder in sorted(out_root.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True):
        if not folder.is_dir():
            continue

        db_file = folder / cfg.get("db_path", "pipeline_state.db")
        html_file = folder / "final_output.html"

        title = folder.name
        meta_desc = ""
        category = "General"
        keywords = ""
        sections_count = 0
        word_count = 0
        has_html = html_file.exists()
        wp_status = None
        feature_img = None

        if db_file.exists():
            try:
                db = init_db(db_file)
                # Check transform
                row = db.execute("SELECT val FROM checkpoints WHERE key = 'transform_v3'").fetchone()
                if row and row["val"]:
                    st = json.loads(row["val"])
                    title = st.get("title", title)
                    meta_desc = st.get("meta_description", "")
                    category = st.get("category", "General")
                    keywords = st.get("keywords", "")
                    sections = st.get("sections", [])
                    sections_count = len(sections)
                    word_count = sum(len(str(p).split()) for s in sections for p in s.get("paragraphs", []))

                # Check WordPress publication status
                wp_row = db.execute("SELECT post_id, post_url FROM wp_published LIMIT 1").fetchone()
                if wp_row:
                    wp_status = {"post_id": wp_row[0], "post_url": wp_row[1]}

                # Check feature image render
                feat_render = folder / "rendered" / f"feature_rendered.{cfg.get('image_ext', 'webp')}"
                if feat_render.exists():
                    feature_img = f"/api/articles/{folder.name}/image/feature_rendered.{cfg.get('image_ext', 'webp')}"

                db.close()
            except Exception:
                pass

        mtime = folder.stat().st_mtime
        formatted_date = datetime.fromtimestamp(mtime).strftime("%b %d, %Y %H:%M")

        articles.append({
            "folder_name": folder.name,
            "title": title,
            "meta_description": meta_desc,
            "category": category,
            "keywords": keywords,
            "sections_count": sections_count,
            "word_count": word_count,
            "read_time": max(1, round(word_count / 200)),
            "date": formatted_date,
            "has_html": has_html,
            "wp_status": wp_status,
            "feature_img": feature_img,
        })

    return jsonify({"articles": articles})


@articles_bp.route("/<folder_name>/html", methods=["GET"])
def view_article_html(folder_name: str):
    """Serves the generated final_output.html file directly."""
    cfg = get_current_config()
    target_html = Path(cfg.get("output_dir", "pipeline_output")) / folder_name / "final_output.html"
    if not target_html.exists():
        return jsonify({"error": "HTML preview not found."}), 404
    return send_file(target_html, mimetype="text/html")


@articles_bp.route("/<folder_name>/image/<image_name>", methods=["GET"])
def view_article_image(folder_name: str, image_name: str):
    """Serves rendered or raw images belonging to an article."""
    cfg = get_current_config()
    art_dir = Path(cfg.get("output_dir", "pipeline_output")) / folder_name
    for sub in ("rendered", "images"):
        cand = art_dir / sub / image_name
        if cand.exists():
            ext = cand.suffix.lower()
            mime = "image/webp" if ext == ".webp" else "image/png" if ext == ".png" else "image/jpeg"
            return send_file(cand, mimetype=mime)
    return jsonify({"error": "Image not found."}), 404


@articles_bp.route("/<folder_name>/open-folder", methods=["POST"])
def open_article_folder(folder_name: str):
    """Opens the local article output directory in Windows File Explorer or native OS manager."""
    cfg = get_current_config()
    target_dir = (Path(cfg.get("output_dir", "pipeline_output")) / folder_name).resolve()
    if not target_dir.exists():
        return jsonify({"ok": False, "error": "Folder not found."}), 404

    try:
        if sys.platform == "win32":
            os.startfile(str(target_dir))
        elif sys.platform == "darwin":
            subprocess.run(["open", str(target_dir)], check=False)
        else:
            subprocess.run(["xdg-open", str(target_dir)], check=False)
        return jsonify({"ok": True, "path": str(target_dir)})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500
