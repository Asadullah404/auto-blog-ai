"""
web/api/skills_api.py — REST API for AI Skills & Prompt Directives
====================================================================
Lists, toggles, creates, and previews modular Markdown skill files (*.md).
"""

from flask import Blueprint, jsonify, request

from config.settings import get_current_config, save_config
from services.skills_service import SkillsService

skills_bp = Blueprint("skills_api", __name__, url_prefix="/api/skills")
_service = SkillsService()


@skills_bp.route("", methods=["GET"])
def get_skills_list():
    """Returns all available skills with active toggle status."""
    cfg = get_current_config()
    enabled = set(cfg.get("skills_enabled", []))

    all_skills = _service.list_skills()
    # If enabled is empty, by default all skills in Skills/ are active
    is_default_all = len(enabled) == 0

    for s in all_skills:
        s["enabled"] = True if is_default_all else (s["filename"] in enabled)

    return jsonify({"skills": all_skills})


@skills_bp.route("/toggle", methods=["POST"])
def toggle_skill():
    """Toggles a specific skill on or off in configuration."""
    data = request.get_json(silent=True) or {}
    filename = data.get("filename")
    is_enabled = data.get("enabled", True)

    if not filename:
        return jsonify({"ok": False, "error": "Filename is required."}), 400

    cfg = get_current_config()
    all_skills = [s["filename"] for s in _service.list_skills()]
    current_enabled = set(cfg.get("skills_enabled") or all_skills)

    if is_enabled:
        current_enabled.add(filename)
    else:
        current_enabled.discard(filename)

    save_config({"skills_enabled": sorted(list(current_enabled))})
    return jsonify({"ok": True, "enabled_skills": sorted(list(current_enabled))})


@skills_bp.route("/create", methods=["POST"])
def create_custom_skill():
    """Creates a new custom skill file in the Skills/ directory."""
    data = request.get_json(silent=True) or {}
    filename = data.get("filename", "").strip()
    content = data.get("content", "").strip()

    if not filename:
        return jsonify({"ok": False, "error": "Filename is required."}), 400
    if not content:
        return jsonify({"ok": False, "error": "Skill content cannot be empty."}), 400

    if not filename.endswith(".md"):
        filename = f"{filename}.md"

    saved = _service.save_skill(filename, content)
    return jsonify({"ok": saved, "filename": filename})


@skills_bp.route("/<filename>", methods=["DELETE"])
def delete_skill_file(filename: str):
    """Deletes a custom skill file."""
    deleted = _service.delete_skill(filename)
    if not deleted:
        return jsonify({"ok": False, "error": "Cannot delete core default skills."}), 400
    return jsonify({"ok": True, "message": f"Deleted {filename}"})


@skills_bp.route("/preview", methods=["GET"])
def preview_combined_prompt():
    """Returns the rendered, combined prompt from all currently active skills."""
    cfg = get_current_config()
    combined = _service.build_combined_skills_prompt(cfg.get("skills_enabled"))
    return jsonify({
        "prompt": combined,
        "chars": len(combined),
        "est_tokens": round(len(combined) / 4)
    })
