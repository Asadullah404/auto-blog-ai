"""
services/log_service.py — Real-Time Log Broadcaster & SSE Event Stream
========================================================================
Maintains an in-memory buffer of colorized, categorized log messages and streams
them to connected web clients via Server-Sent Events (SSE).
"""

from collections import deque
from datetime import datetime
import json
import queue
import threading
from typing import Any, Dict, Generator, List, Optional


class LogService:
    def __init__(self, max_history: int = 1500):
        self.max_history = max_history
        self._buffer: deque = deque(maxlen=max_history)
        self._subscribers: List[queue.Queue] = []
        self._lock = threading.Lock()

    def add_log(self, message: str, level: str = "info", phase: str = "system") -> Dict[str, Any]:
        """Records a log entry and notifies all active SSE listeners."""
        entry = {
            "timestamp": datetime.now().strftime("%H:%M:%S"),
            "datetime": datetime.now().isoformat(),
            "level": level.lower(),   # "info" | "warn" | "error" | "success" | "debug"
            "phase": phase.lower(),   # "extract" | "transform" | "images" | "render" | "compile" | "publish" | "system"
            "message": message,
        }

        with self._lock:
            self._buffer.append(entry)
            dead_subs = []
            for q in self._subscribers:
                try:
                    q.put_nowait(entry)
                except Exception:
                    dead_subs.append(q)
            for d in dead_subs:
                self._subscribers.remove(d)

        return entry

    def get_logs(self, limit: int = 500, level_filter: Optional[str] = None) -> List[Dict[str, Any]]:
        """Returns the most recent log entries, optionally filtered by level."""
        with self._lock:
            logs = list(self._buffer)
        if level_filter:
            filt = level_filter.lower()
            logs = [e for e in logs if e["level"] == filt]
        return logs[-limit:]

    def clear(self) -> None:
        """Clears the in-memory log history."""
        with self._lock:
            self._buffer.clear()
        self.add_log("Logs cleared by user.", level="info", phase="system")

    def subscribe(self) -> Generator[str, None, None]:
        """Generator yielding SSE formatted strings for streaming responses."""
        q = queue.Queue(maxsize=100)
        with self._lock:
            self._subscribers.append(q)

        try:
            # Yield initial connection heartbeat
            yield f"data: {json.dumps({'type': 'connected', 'timestamp': datetime.now().isoformat()})}\n\n"
            while True:
                entry = q.get()
                yield f"data: {json.dumps(entry)}\n\n"
        except GeneratorExit:
            with self._lock:
                if q in self._subscribers:
                    self._subscribers.remove(q)


# Global singleton instance
log_service = LogService()
