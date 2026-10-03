"""
services/task_manager.py — Non-Blocking Background Task & Queue Manager
==========================================================================
Runs the continuous 24/7 autonomous pipeline or single jobs in a dedicated
background thread without blocking Flask. Manages execution states, pause/stop
signals, Firestore/Offline queues, and live event broadcasting.
"""

from datetime import datetime
import json
from pathlib import Path
import platform
import threading
import time
from typing import Any, Callable, Dict, List, Optional

from config.settings import get_current_config, load_config
from core.pipeline import run_single_url_pipeline
from integrations.firebase_auth import get_valid_id_token
import integrations.firestore as fs
from services.bundle_service import BundleService
from services.log_service import log_service
from services.skills_service import SkillsService


class TaskManager:
    def __init__(self):
        self.state: str = "idle"  # "idle" | "running" | "paused" | "quota_wait" | "stopping"
        self.mode: str = "offline"  # "online" | "offline"
        self.current_url: str = ""
        self.current_phase: str = "idle"
        self.progress_pct: int = 0
        self.phase_message: str = "System ready."
        self.active_meta: Dict[str, Any] = {}

        self.stats: Dict[str, int] = {
            "total": 0,
            "done": 0,
            "failed": 0,
            "pending": 0,
        }

        self._thread: Optional[threading.Thread] = None
        self._stop_requested = threading.Event()
        self._pause_requested = threading.Event()
        self._lock = threading.Lock()
        self.skills_service = SkillsService()

    def get_status(self) -> Dict[str, Any]:
        """Returns the full live operational state."""
        with self._lock:
            return {
                "state": self.state,
                "mode": self.mode,
                "current_url": self.current_url,
                "current_phase": self.current_phase,
                "progress": self.progress_pct,
                "progress_pct": self.progress_pct,
                "message": self.phase_message,
                "meta": self.active_meta,
                "stats": dict(self.stats),
                "is_running": self.state in ("running", "quota_wait"),
            }

    def start_pipeline(self, mode: Optional[str] = None, single_url: Optional[str] = None) -> bool:
        """Launches the background processing thread if not already running."""
        with self._lock:
            if self.state in ("running", "quota_wait"):
                return False

            self.state = "running"
            self._stop_requested.clear()
            self._pause_requested.clear()
            self.progress_pct = 0
            self.phase_message = "Starting pipeline engine..."

            cfg = load_config()
            self.mode = mode or cfg.get("mode", "offline")

            target_func = (
                (lambda: self._run_single_url_job(single_url))
                if single_url
                else (self._run_online_loop if self.mode == "online" else self._run_offline_loop)
            )

            self._thread = threading.Thread(target=target_func, daemon=True, name="PipelineWorker")
            self._thread.start()

        log_service.add_log(f"Pipeline started in {self.mode.upper()} mode.", level="info", phase="system")
        return True

    def stop_pipeline(self) -> bool:
        """Signals the background worker to stop gracefully at the next checkpoint."""
        with self._lock:
            if self.state not in ("running", "paused", "quota_wait"):
                return False
            self.state = "stopping"
            self.phase_message = "Stopping... saving progress at checkpoint."
            self._stop_requested.set()
            self._pause_requested.clear()

        log_service.add_log("Stop requested. Halting at phase boundary.", level="warn", phase="system")
        return True

    def pause_pipeline(self) -> bool:
        """Pauses execution."""
        with self._lock:
            if self.state != "running":
                return False
            self.state = "paused"
            self._pause_requested.set()

        log_service.add_log("Pipeline execution paused.", level="warn", phase="system")
        return True

    def resume_pipeline(self) -> bool:
        """Resumes paused execution."""
        with self._lock:
            if self.state != "paused":
                return False
            self.state = "running"
            self._pause_requested.clear()

        log_service.add_log("Pipeline execution resumed.", level="info", phase="system")
        return True

    def _should_stop(self) -> bool:
        while self._pause_requested.is_set():
            if self._stop_requested.is_set():
                return True
            time.sleep(0.5)
        return self._stop_requested.is_set()

    def _progress_callback(self, phase: str, payload: Dict[str, Any]) -> None:
        """Receives real-time phase updates from core.pipeline."""
        with self._lock:
            self.current_phase = phase
            self.progress_pct = payload.get("percent", self.progress_pct)
            self.phase_message = payload.get("message", "")
            self.active_meta = payload.get("meta", {})

        level = "error" if phase == "error" else "warn" if phase == "quota_wait" else "info"
        log_service.add_log(self.phase_message, level=level, phase=phase)

    # ── Online Execution Loop (Firestore) ───────────────────────
    def _run_online_loop(self) -> None:
        cfg = get_current_config()
        id_token, uid = get_valid_id_token()

        if not id_token:
            log_service.add_log("Online mode error: Not signed into Firebase. Sign in on the Sync page.", level="error", phase="system")
            with self._lock:
                self.state = "idle"
            return

        skills_text = self.skills_service.build_combined_skills_prompt(cfg.get("skills_enabled"))
        machine_id = platform.node() or "Worker-1"

        try:
            while not self._should_stop():
                # Refresh dashboard stats
                try:
                    stats = fs.get_stats(uid, id_token)
                    with self._lock:
                        self.stats = stats
                except Exception:
                    pass

                # Query pending or stale claimed rows
                try:
                    pending_items = fs.query_pending(uid, id_token, stale_hours=cfg.get("csv_pending_stale_hours", 3.0))
                except Exception as qe:
                    log_service.add_log(f"Firestore query error: {qe}. Retrying in 15s...", level="warn", phase="system")
                    time.sleep(15)
                    continue

                if not pending_items:
                    log_service.add_log("All URLs processed! Queue is empty.", level="success", phase="system")
                    break

                target_doc = pending_items[0]
                url = target_doc.get("url", "").strip()
                category = target_doc.get("category", "")

                if not url:
                    continue

                with self._lock:
                    self.current_url = url
                    self.progress_pct = 0

                # Claim the URL
                fs.set_status(uid, id_token, url, "claimed", claimed_by=machine_id, claimed_at=fs.now_iso())
                log_service.add_log(f"Claimed URL: {url}", level="info", phase="system")

                # Run Pipeline
                res = run_single_url_pipeline(
                    url=url,
                    skills_text=skills_text,
                    cfg=cfg,
                    category_override=category,
                    progress_callback=self._progress_callback,
                    should_stop_callback=self._should_stop
                )

                if res.get("status") == "done":
                    fs.set_status(uid, id_token, url, "done", claimed_by=machine_id)
                    log_service.add_log(f"Completed: {url}", level="success", phase="system")
                elif res.get("status") == "failed":
                    fs.set_status(uid, id_token, url, "failed", claimed_by=machine_id)
                    log_service.add_log(f"Failed permanently: {url}", level="error", phase="system")
                elif res.get("status") == "quota_wait":
                    wait_s = res.get("quota_seconds_remaining", 3600 * 6)
                    with self._lock:
                        self.state = "quota_wait"
                    log_service.add_log(f"Quota wait active. Sleeping {wait_s // 3600} hours before retry.", level="warn", phase="system")
                    time.sleep(wait_s)
                    with self._lock:
                        self.state = "running"
                elif res.get("status") == "stopped":
                    fs.set_status(uid, id_token, url, "pending")
                    break

        except Exception as e:
            log_service.add_log(f"Unexpected error in online loop: {e}", level="error", phase="system")
        finally:
            with self._lock:
                self.state = "idle"
                self.current_url = ""
                self.current_phase = "idle"
                self.progress_pct = 0
                self.phase_message = "Pipeline idle."

    # ── Offline Execution Loop (Bundle / CSV) ────────────────────
    def _run_offline_loop(self) -> None:
        cfg = get_current_config()
        bundle_path = Path(cfg.get("offline_bundle_path", "offline_bundle.json"))
        skills_text = self.skills_service.build_combined_skills_prompt(cfg.get("skills_enabled"))

        is_json_bundle = bundle_path.suffix.lower() == ".json" and bundle_path.exists()
        csv_fallback = Path("Links.csv")

        links: List[Dict[str, str]] = []
        if is_json_bundle:
            try:
                b_data = BundleService.load_bundle(bundle_path)
                links = b_data.get("links", [])
                log_service.add_log(f"Loaded {len(links)} links from {bundle_path.name}", level="info", phase="system")
            except Exception as e:
                log_service.add_log(f"Bundle read notice: {e}. Falling back to CSV.", level="warn", phase="system")

        if not links and csv_fallback.exists():
            links = BundleService.load_csv_links(csv_fallback)
            log_service.add_log(f"Loaded {len(links)} links from Links.csv", level="info", phase="system")

        if not links:
            log_service.add_log("No links found in offline bundle or Links.csv. Add links to run.", level="warn", phase="system")
            with self._lock:
                self.state = "idle"
            return

        try:
            total = len(links)
            for idx, item in enumerate(links):
                if self._should_stop():
                    break

                url = item.get("url", "").strip()
                status = item.get("status", "pending")
                category = item.get("category", "")

                # Update stats
                done_c = sum(1 for x in links if x.get("status") == "done")
                fail_c = sum(1 for x in links if x.get("status") == "failed")
                with self._lock:
                    self.stats = {
                        "total": total,
                        "done": done_c,
                        "failed": fail_c,
                        "pending": max(0, total - done_c - fail_c),
                    }

                if status in ("done", "failed"):
                    continue

                with self._lock:
                    self.current_url = url
                    self.progress_pct = 0

                log_service.add_log(f"Processing URL [{idx + 1}/{total}]: {url}", level="info", phase="system")

                res = run_single_url_pipeline(
                    url=url,
                    skills_text=skills_text,
                    cfg=cfg,
                    category_override=category,
                    progress_callback=self._progress_callback,
                    should_stop_callback=self._should_stop
                )

                if res.get("status") == "done":
                    item["status"] = "done"
                    if is_json_bundle:
                        BundleService.update_link_status(bundle_path, url, "done")
                    else:
                        BundleService.save_csv_links(csv_fallback, links)
                    log_service.add_log(f"Completed: {url}", level="success", phase="system")
                elif res.get("status") == "failed":
                    item["status"] = "failed"
                    if is_json_bundle:
                        BundleService.update_link_status(bundle_path, url, "failed")
                    else:
                        BundleService.save_csv_links(csv_fallback, links)
                    log_service.add_log(f"Failed: {url}", level="error", phase="system")
                elif res.get("status") == "quota_wait":
                    wait_s = res.get("quota_seconds_remaining", 3600 * 6)
                    with self._lock:
                        self.state = "quota_wait"
                    log_service.add_log(f"Quota wait active. Sleeping {wait_s // 3600} hours before retry.", level="warn", phase="system")
                    time.sleep(wait_s)
                    with self._lock:
                        self.state = "running"
                elif res.get("status") == "stopped":
                    break

        except Exception as e:
            log_service.add_log(f"Error in offline loop: {e}", level="error", phase="system")
        finally:
            with self._lock:
                self.state = "idle"
                self.current_url = ""
                self.current_phase = "idle"
                self.progress_pct = 0
                self.phase_message = "Pipeline idle."

    # ── Single One-Off Job ──────────────────────────────────────
    def _run_single_url_job(self, url: str) -> None:
        cfg = get_current_config()
        skills_text = self.skills_service.build_combined_skills_prompt(cfg.get("skills_enabled"))

        with self._lock:
            self.current_url = url
            self.progress_pct = 0

        try:
            log_service.add_log(f"Processing single URL: {url}", level="info", phase="system")
            res = run_single_url_pipeline(
                url=url,
                skills_text=skills_text,
                cfg=cfg,
                progress_callback=self._progress_callback,
                should_stop_callback=self._should_stop
            )
            if res.get("status") == "done":
                log_service.add_log(f"Article successfully completed for {url}!", level="success", phase="system")
            else:
                log_service.add_log(f"Job ended with status: {res.get('status')}", level="warn", phase="system")
        except Exception as e:
            log_service.add_log(f"Single job error: {e}", level="error", phase="system")
        finally:
            with self._lock:
                self.state = "idle"
                self.current_url = ""
                self.current_phase = "idle"
                self.progress_pct = 0
                self.phase_message = "Pipeline idle."


# Global singleton instance
task_manager = TaskManager()
