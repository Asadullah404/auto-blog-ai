"""
web/api/queue_api.py — REST API for Link Queues & Authentication
===================================================================
Manages cloud Firestore links or offline CSV/bundle records and user authentication.
"""

from pathlib import Path
from flask import Blueprint, jsonify, request
from werkzeug.utils import secure_filename

from config.settings import get_current_config
from integrations.firebase_auth import (
    current_profile,
    get_valid_id_token,
    sign_in_with_password,
    sign_out,
    sign_up_with_password,
)
import integrations.firestore as fs
from services.bundle_service import BundleService

queue_bp = Blueprint("queue_api", __name__, url_prefix="/api/queue")


@queue_bp.route("", methods=["GET"])
def get_queue_items():
    """Returns links and statistics based on the active mode (online or offline)."""
    cfg = get_current_config()
    mode = cfg.get("mode", "offline")
    id_token, uid = get_valid_id_token()

    if mode == "online" and id_token and uid:
        try:
            links = fs.run_query(uid, id_token, order_by="createdAt", descending=True, limit=200)
            stats = fs.get_stats(uid, id_token)
            return jsonify({
                "mode": "online",
                "authenticated": True,
                "profile": current_profile(),
                "links": links,
                "stats": stats,
            })
        except Exception as e:
            return jsonify({
                "mode": "online",
                "authenticated": True,
                "profile": current_profile(),
                "error": str(e),
                "links": [],
                "stats": {"total": 0, "done": 0, "failed": 0, "pending": 0},
            })

    # Offline mode
    bundle_path = Path(cfg.get("offline_bundle_path", "offline_bundle.json"))
    links = []
    if bundle_path.exists() and bundle_path.suffix.lower() == ".json":
        try:
            b_data = BundleService.load_bundle(bundle_path)
            links = b_data.get("links", [])
        except Exception:
            pass

    if not links and Path("Links.csv").exists():
        links = BundleService.load_csv_links("Links.csv")

    done_c = sum(1 for x in links if x.get("status") == "done")
    fail_c = sum(1 for x in links if x.get("status") == "failed")
    total = len(links)
    stats = {
        "total": total,
        "done": done_c,
        "failed": fail_c,
        "pending": max(0, total - done_c - fail_c),
    }

    return jsonify({
        "mode": "offline",
        "authenticated": bool(id_token),
        "profile": current_profile(),
        "links": links,
        "stats": stats,
    })


@queue_bp.route("/add", methods=["POST"])
def add_link_item():
    """Adds a single URL to the queue."""
    data = request.get_json(silent=True) or {}
    url = data.get("url", "").strip()
    category = data.get("category", "").strip()

    if not url:
        return jsonify({"ok": False, "error": "URL is required."}), 400

    cfg = get_current_config()
    mode = cfg.get("mode", "offline")
    id_token, uid = get_valid_id_token()

    if mode == "online" and id_token and uid:
        try:
            status = fs.upsert_link(uid, id_token, url, category=category)
            return jsonify({"ok": True, "action": status, "url": url})
        except Exception as e:
            return jsonify({"ok": False, "error": str(e)}), 400

    # Offline mode
    csv_path = Path("Links.csv")
    links = BundleService.load_csv_links(csv_path) if csv_path.exists() else []
    links.insert(0, {"url": url, "category": category, "status": "pending"})
    BundleService.save_csv_links(csv_path, links)
    return jsonify({"ok": True, "action": "created", "url": url})


@queue_bp.route("/upload-csv", methods=["POST"])
def upload_csv():
    """Receives a CSV file and appends rows to the queue."""
    if "file" not in request.files:
        return jsonify({"ok": False, "error": "No file uploaded."}), 400

    file = request.files["file"]
    if not file.filename:
        return jsonify({"ok": False, "error": "Empty filename."}), 400

    temp_path = Path("temp_uploaded.csv")
    file.save(str(temp_path))

    new_links = BundleService.load_csv_links(temp_path)
    temp_path.unlink(missing_ok=True)

    if not new_links:
        return jsonify({"ok": False, "error": "No valid links found in CSV."}), 400

    cfg = get_current_config()
    mode = cfg.get("mode", "offline")
    id_token, uid = get_valid_id_token()

    if mode == "online" and id_token and uid:
        created = 0
        updated = 0
        for item in new_links:
            st = fs.upsert_link(uid, id_token, item["url"], item.get("category", ""), item.get("status"))
            if st == "created":
                created += 1
            elif st == "updated":
                updated += 1
        return jsonify({"ok": True, "created": created, "updated": updated, "total": len(new_links)})

    # Offline
    csv_path = Path("Links.csv")
    existing = BundleService.load_csv_links(csv_path) if csv_path.exists() else []
    seen = {x["url"] for x in existing}
    added = 0
    for it in new_links:
        if it["url"] not in seen:
            existing.append(it)
            seen.add(it["url"])
            added += 1
    BundleService.save_csv_links(csv_path, existing)
    return jsonify({"ok": True, "added": added, "total": len(existing)})


@queue_bp.route("/status", methods=["POST"])
def update_item_status():
    """Updates the status of a specific URL."""
    data = request.get_json(silent=True) or {}
    url = data.get("url", "").strip()
    new_status = data.get("status", "pending").lower()

    if not url:
        return jsonify({"ok": False, "error": "URL is required."}), 400

    cfg = get_current_config()
    mode = cfg.get("mode", "offline")
    id_token, uid = get_valid_id_token()

    if mode == "online" and id_token and uid:
        fs.set_status(uid, id_token, url, new_status)
        return jsonify({"ok": True, "url": url, "status": new_status})

    # Offline
    bundle_path = Path(cfg.get("offline_bundle_path", "offline_bundle.json"))
    if bundle_path.exists() and bundle_path.suffix.lower() == ".json":
        BundleService.update_link_status(bundle_path, url, new_status)

    csv_path = Path("Links.csv")
    if csv_path.exists():
        links = BundleService.load_csv_links(csv_path)
        for it in links:
            if it.get("url") == url:
                it["status"] = new_status
        BundleService.save_csv_links(csv_path, links)

    return jsonify({"ok": True, "url": url, "status": new_status})


# ── Firebase Authentication Endpoints ───────────────────────────
@queue_bp.route("/auth/signin", methods=["POST"])
def api_sign_in():
    data = request.get_json(silent=True) or {}
    email = data.get("email", "").strip()
    password = data.get("password", "").strip()

    try:
        res = sign_in_with_password(email, password)
        return jsonify({"ok": True, "profile": {"uid": res["uid"], "email": res["email"]}})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 400


@queue_bp.route("/auth/signup", methods=["POST"])
def api_sign_up():
    data = request.get_json(silent=True) or {}
    email = data.get("email", "").strip()
    password = data.get("password", "").strip()

    try:
        res = sign_up_with_password(email, password)
        return jsonify({"ok": True, "profile": {"uid": res["uid"], "email": res["email"]}})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 400


@queue_bp.route("/auth/signout", methods=["POST"])
def api_sign_out():
    sign_out()
    return jsonify({"ok": True, "message": "Signed out."})


@queue_bp.route("/auth/profile", methods=["GET"])
def api_profile():
    return jsonify({"profile": current_profile()})
