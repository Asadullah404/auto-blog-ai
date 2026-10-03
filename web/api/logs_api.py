"""
web/api/logs_api.py — REST & SSE Endpoints for Streaming Logs
================================================================
Provides real-time Server-Sent Events (SSE) log streaming and historical log retrieval.
"""

from datetime import datetime
from io import BytesIO

from flask import Blueprint, Response, jsonify, request, send_file

from services.log_service import log_service

logs_bp = Blueprint("logs_api", __name__, url_prefix="/api/logs")


@logs_bp.route("", methods=["GET"])
def get_log_history():
    """Returns the most recent log entries."""
    limit = int(request.args.get("limit", 500))
    lvl = request.args.get("level")
    return jsonify({"logs": log_service.get_logs(limit=limit, level_filter=lvl)})


@logs_bp.route("/stream", methods=["GET"])
def stream_logs():
    """Streams real-time log entries to the web client via SSE."""
    return Response(
        log_service.subscribe(),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        }
    )


@logs_bp.route("/clear", methods=["POST"])
def clear_all_logs():
    """Clears in-memory log buffer."""
    log_service.clear()
    return jsonify({"ok": True, "message": "Logs cleared."})


@logs_bp.route("/download", methods=["GET"])
def download_logs_file():
    """Downloads all recorded logs as a clean plaintext file."""
    logs = log_service.get_logs(limit=2000)
    lines = []
    for l in logs:
        lines.append(f"[{l['timestamp']}] [{l['level'].upper()}] [{l['phase']}] {l['message']}")
    content = "\n".join(lines)
    buf = BytesIO(content.encode("utf-8"))
    filename = f"content_pipeline_logs_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
    return send_file(buf, as_attachment=True, download_name=filename, mimetype="text/plain")
