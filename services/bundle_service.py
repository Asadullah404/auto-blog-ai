"""
services/bundle_service.py — Offline Bundle & CSV Management Service
======================================================================
Provides utilities to create, inspect, and update all-in-one offline bundle files
and import/export CSV link records. Enables 100% cloud-quota-free 24/7 execution.
"""

import csv
import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Union


class BundleService:
    @staticmethod
    def load_csv_links(csv_path: Union[str, Path]) -> List[Dict[str, str]]:
        """Reads a CSV file and returns normalized list of link records."""
        path = Path(csv_path)
        links = []
        if not path.exists():
            return links

        with open(path, "r", encoding="utf-8", errors="replace") as f:
            reader = csv.reader(f)
            for row in reader:
                if not row:
                    continue
                first = row[0].strip()
                if not first or first.startswith("#") or first.lower() == "url":
                    continue
                url = first
                category = row[1].strip() if len(row) > 1 else ""
                status = row[2].strip().lower() if len(row) > 2 else "pending"
                if status not in ("done", "failed"):
                    status = "pending"
                links.append({"url": url, "category": category, "status": status})
        return links

    @staticmethod
    def save_csv_links(csv_path: Union[str, Path], links: List[Dict[str, str]]) -> None:
        """Exports link records to a standard CSV file."""
        path = Path(csv_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["url", "category", "status"])
            for item in links:
                writer.writerow([item.get("url", ""), item.get("category", ""), item.get("status", "pending")])

    @staticmethod
    def create_bundle(
        settings: Dict[str, Any],
        links: List[Dict[str, str]],
        out_path: Union[str, Path],
        name: str = "Offline Content Pipeline Bundle"
    ) -> Dict[str, Any]:
        """Creates and saves a self-contained offline bundle JSON file."""
        bundle_data = {
            "bundle_version": "1.0",
            "name": name,
            "created_at": Path(out_path).name,
            "settings": settings,
            "links": links
        }
        path = Path(out_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(bundle_data, indent=2, ensure_ascii=False), encoding="utf-8")
        return bundle_data

    @staticmethod
    def load_bundle(bundle_path: Union[str, Path]) -> Dict[str, Any]:
        """Loads and validates an offline bundle JSON file."""
        path = Path(bundle_path)
        if not path.exists():
            raise FileNotFoundError(f"Bundle file not found: {path}")
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict) or "settings" not in data or "links" not in data:
            raise ValueError(f"Invalid bundle format in {path}. Expected keys 'settings' and 'links'.")
        return data

    @staticmethod
    def update_link_status(bundle_path: Union[str, Path], url: str, status: str) -> bool:
        """Updates the status of a specific URL inside the bundle."""
        path = Path(bundle_path)
        data = BundleService.load_bundle(path)
        updated = False
        for item in data.get("links", []):
            if item.get("url") == url:
                item["status"] = status
                updated = True
                break
        if updated:
            path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        return updated
