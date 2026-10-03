"""
web/api/pipeline_api.py — REST API for Pipeline Control & Status
===================================================================
Provides endpoints to start, stop, pause, resume, and monitor the autonomous pipeline.
"""

from flask import Blueprint, jsonify, request

from services.task_manager import task_manager

pipeline_bp = Blueprint("pipeline_api", __name__, url_prefix="/api/pipeline")


@pipeline_bp.route("/status", methods=["GET"])
def get_pipeline_status():
    """Returns the current operational status, active URL, phase, and progress."""
    return jsonify(task_manager.get_status())


@pipeline_bp.route("/start", methods=["POST"])
def start_pipeline():
    """Starts the continuous pipeline in the requested mode (online/offline)."""
    data = request.get_json(silent=True) or {}
    mode = data.get("mode")
    single_url = data.get("url")

    started = task_manager.start_pipeline(mode=mode, single_url=single_url)
    if not started:
        return jsonify({"ok": False, "error": "Pipeline is already running."}), 400

    return jsonify({"ok": True, "message": "Pipeline started successfully."})


@pipeline_bp.route("/stop", methods=["POST"])
def stop_pipeline():
    """Gracefully halts the pipeline at the next phase checkpoint."""
    stopped = task_manager.stop_pipeline()
    if not stopped:
        return jsonify({"ok": False, "error": "Pipeline is not currently running."}), 400

    return jsonify({"ok": True, "message": "Stop requested. Saving progress at checkpoint."})


@pipeline_bp.route("/pause", methods=["POST"])
def pause_pipeline():
    """Pauses pipeline execution."""
    paused = task_manager.pause_pipeline()
    if not paused:
        return jsonify({"ok": False, "error": "Pipeline is not running or already paused."}), 400

    return jsonify({"ok": True, "message": "Pipeline paused."})


@pipeline_bp.route("/resume", methods=["POST"])
def resume_pipeline():
    """Resumes paused pipeline execution."""
    resumed = task_manager.resume_pipeline()
    if not resumed:
        return jsonify({"ok": False, "error": "Pipeline is not paused."}), 400

    return jsonify({"ok": True, "message": "Pipeline resumed."})


@pipeline_bp.route("/run-single", methods=["POST"])
def run_single():
    """Runs the pipeline for a single target URL in the background."""
    from config.settings import save_config
    data = request.get_json(silent=True) or {}
    url = (data.get("url") or "").strip()
    if not url:
        return jsonify({"ok": False, "status": "error", "message": "Missing target URL."}), 400

    overrides = {}
    if data.get("article_format"):
        overrides["article_format"] = data["article_format"]
    if "publish_wp" in data:
        overrides["auto_publish"] = bool(data["publish_wp"])
    if overrides:
        save_config(overrides)

    started = task_manager.start_pipeline(mode="offline", single_url=url)
    if not started:
        return jsonify({"ok": False, "status": "error", "message": "Pipeline is already running."}), 400

    return jsonify({"ok": True, "status": "success", "message": f"Processing launched for {url}", "url": url})

