"""
web/api/settings_api.py — REST API for Application Configuration
===================================================================
Provides endpoints to read and update categorized application settings.
"""

from flask import Blueprint, jsonify, request

from config.constants import ARTICLE_FORMAT_LABELS, IMAGE_TYPES, PIN_STYLE_PRESETS, RESOLUTION_PRESETS
from config.settings import get_current_config, save_config
from integrations.firebase_auth import get_valid_id_token
import integrations.firestore as fs

settings_bp = Blueprint("settings_api", __name__, url_prefix="/api/settings")


@settings_bp.route("", methods=["GET"])
def get_settings():
    """Returns the current application configuration and preset metadata."""
    cfg = get_current_config()
    return jsonify({
        "settings": cfg,
        "presets": {
            "image_types": IMAGE_TYPES,
            "pin_styles": PIN_STYLE_PRESETS,
            "resolutions": list(RESOLUTION_PRESETS.keys()),
            "article_formats": ARTICLE_FORMAT_LABELS,
        }
    })


@settings_bp.route("", methods=["POST"])
def update_settings():
    """Saves updated settings to disk and syncs to Firestore if signed in."""
    data = request.get_json(silent=True) or {}
    updated_cfg = save_config(data)

    # If signed in, sync settings to user's Firestore doc
    id_token, uid = get_valid_id_token()
    if id_token and uid:
        try:
            fs.patch_doc(uid, id_token, "pipeline", updated_cfg, collection="settings")
        except Exception:
            pass

    return jsonify({
        "ok": True,
        "message": "Settings saved successfully.",
        "settings": updated_cfg
    })
