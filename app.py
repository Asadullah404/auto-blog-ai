#!/usr/bin/env python3
"""
app.py — Content Pipeline Pro (Flask + Windows 11 Fluent Studio)
================================================================
Main entry point for Content Pipeline Pro.
Performs pre-flight startup checks, initializes the Flask server with all
modular API blueprints, and automatically launches the user's default browser.

Usage:
    python app.py
"""

import os
import signal
import sys
import threading
import time
import webbrowser
from pathlib import Path
from typing import Dict, Any

# Ensure UTF-8 output encoding across Windows terminals
if sys.platform.startswith("win"):
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from flask import Flask, render_template, jsonify, send_from_directory

from config.settings import load_config, get_current_config
from core.checkpoints import CheckpointManager
from services.skills_service import SkillsService
from services.log_service import log_service
from web.api import register_api_blueprints


def preflight_checks() -> Dict[str, Any]:
    """
    Performs initial application environment checks and directory provisioning.
    Ensures output, temp, checkpoint, and skills folders exist.
    """
    print("[*] Running pre-flight startup checks...")

    required_dirs = [
        Path("output"),
        Path("temp_input"),
        Path("Skills"),
        Path("checkpoints"),
        Path("web/static/assets"),
    ]

    for d in required_dirs:
        d.mkdir(parents=True, exist_ok=True)

    # Seed baseline SEO, GEO, and AEO skills
    skills_service = SkillsService(skills_dir=Path("Skills"))
    skills_service.ensure_default_skills()
    skill_count = len(skills_service.list_skills())

    # Initialize SQLite WAL checkpoints
    chk_mgr = CheckpointManager(db_path=Path("checkpoints/pipeline.db"))
    chk_mgr.init_db()

    # Load and validate application settings
    cfg = load_config()

    print(f"[*] Pre-flight completed. Found {skill_count} active AI skills.")
    return cfg


def create_app() -> Flask:
    """Creates and configures the Flask application instance."""
    app = Flask(
        __name__,
        template_folder=str(Path(__file__).parent / "web" / "templates"),
        static_folder=str(Path(__file__).parent / "web" / "static"),
    )

    app.config["SECRET_KEY"] = os.urandom(24).hex()
    app.config["JSON_SORT_KEYS"] = False

    # Register all modular REST API blueprints
    register_api_blueprints(app)

    @app.route("/")
    def index():
        """Serves the Windows 11 Fluent Studio single-page application shell."""
        return render_template("index.html")

    @app.route("/favicon.ico")
    def favicon():
        """Returns application icon or 204 if absent."""
        icon_path = Path("web/static/assets/favicon.ico")
        if icon_path.exists():
            return send_from_directory("web/static/assets", "favicon.ico")
        return ("", 204)

    @app.errorhandler(404)
    def page_not_found(e):
        return jsonify({"error": "Resource not found", "status_code": 404}), 404

    @app.errorhandler(500)
    def internal_server_error(e):
        return jsonify({"error": "Internal server error", "details": str(e), "status_code": 500}), 500

    return app


def launch_browser(url: str, delay: float = 1.2) -> None:
    """Launches the default web browser after a brief delay for server initialization."""
    def _open():
        time.sleep(delay)
        print(f"[*] Opening browser to {url} ...")
        try:
            webbrowser.open(url)
        except Exception as e:
            print(f"[!] Could not automatically open browser: {e}")

    thread = threading.Thread(target=_open, daemon=True)
    thread.start()


def print_banner(host: str, port: int, cfg: Dict[str, Any]) -> None:
    """Displays a clean Windows 11 Fluent Studio startup banner in the console."""
    url = f"http://{host}:{port}"
    banner = f"""
===============================================================================
   CONTENT PIPELINE PRO — Windows 11 Fluent Studio v2.0
===============================================================================
   Local URL:        {url}
   Execution Mode:   {cfg.get('mode', 'offline').upper()}
   Output Directory: {cfg.get('output_dir', 'output')}
   AI Model:         {cfg.get('gemini_model', 'gemini-2.5-flash')}
   Image Engine:     {cfg.get('image_engine', 'pollinations')}
   Database:         checkpoints/pipeline.db (SQLite WAL)
===============================================================================
   Press CTRL+C to cleanly stop the server.
"""
    print(banner)


def main():
    """Application entry point."""
    cfg = preflight_checks()

    app = create_app()

    host = os.environ.get("FLASK_HOST", "127.0.0.1")
    port = int(os.environ.get("FLASK_PORT", 5000))
    app_url = f"http://{host}:{port}"

    print_banner(host, port, cfg)

    # Launch browser automatically if configured
    if cfg.get("auto_launch_browser", True):
        launch_browser(app_url, delay=1.2)

    # Start Flask WSGI server
    try:
        app.run(host=host, port=port, debug=False, use_reloader=False)
    except (KeyboardInterrupt, SystemExit):
        print("\n[*] Shutting down Content Pipeline Pro server. Goodbye!")
        sys.exit(0)


if __name__ == "__main__":
    main()
