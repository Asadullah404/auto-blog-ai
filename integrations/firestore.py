"""
integrations/firestore.py — Thin REST Client for Cloud Firestore
===================================================================
Manages multi-machine job queues and settings synchronization via direct HTTP REST calls
to firestore.googleapis.com using authenticated user Bearer ID tokens.
Implements deterministic document hashing, claim leases with stale recovery, and
efficient aggregation counting.
"""

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import time
from urllib.parse import urlsplit, urlunsplit

import requests

from integrations.firebase_auth import FIREBASE_CONFIG_FILE, get_valid_id_token

FIRESTORE_HOST = "https://firestore.googleapis.com"
_project_id_cache = None


class FirestoreError(Exception):
    pass


def get_project_id() -> str:
    """Reads projectId from firebase_config.json."""
    global _project_id_cache
    if _project_id_cache:
        return _project_id_cache
    cfg = json.loads(Path(FIREBASE_CONFIG_FILE).read_text(encoding="utf-8"))
    project_id = cfg.get("projectId")
    if not project_id:
        raise FirestoreError(f"{FIREBASE_CONFIG_FILE} is missing 'projectId'.")
    _project_id_cache = project_id
    return project_id


def documents_base() -> str:
    return f"{FIRESTORE_HOST}/v1/projects/{get_project_id()}/databases/(default)/documents"


def doc_path(uid: str, doc_id: str, collection: str = "links") -> str:
    return f"users/{uid}/{collection}/{doc_id}"


def doc_url(uid: str, doc_id: str, collection: str = "links") -> str:
    return f"{documents_base()}/{doc_path(uid, doc_id, collection)}"


def link_doc_id(url: str) -> str:
    """Deterministic 20-char doc id from a normalized URL."""
    parts = urlsplit(url.strip())
    normalized = urlunsplit((
        parts.scheme.lower(),
        parts.netloc.lower(),
        parts.path.rstrip("/"),
        parts.query,
        "",
    ))
    return hashlib.sha1(normalized.encode("utf-8")).hexdigest()[:20]


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


# ── Firestore Value Encoding / Decoding ────────────────────────
def encode_value(v):
    if v is None:
        return {"nullValue": None}
    if isinstance(v, bool):
        return {"booleanValue": v}
    if isinstance(v, int):
        return {"integerValue": str(v)}
    if isinstance(v, float):
        return {"doubleValue": v}
    if isinstance(v, datetime):
        return {"timestampValue": v.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")}
    if isinstance(v, list):
        return {"arrayValue": {"values": [encode_value(item) for item in v]}}
    if isinstance(v, dict):
        return {"mapValue": {"fields": encode_fields(v)}}
    return {"stringValue": str(v)}


def decode_value(fv: dict):
    if not isinstance(fv, dict):
        return fv
    if "stringValue" in fv:
        return fv["stringValue"]
    if "integerValue" in fv:
        return int(fv["integerValue"])
    if "doubleValue" in fv:
        return fv["doubleValue"]
    if "booleanValue" in fv:
        return fv["booleanValue"]
    if "timestampValue" in fv:
        return fv["timestampValue"]
    if "nullValue" in fv:
        return None
    if "arrayValue" in fv:
        return [decode_value(x) for x in fv["arrayValue"].get("values", [])]
    if "mapValue" in fv:
        return decode_fields(fv["mapValue"].get("fields", {}))
    return None


def encode_fields(d: dict) -> dict:
    return {k: encode_value(v) for k, v in d.items()}


def decode_fields(fields: dict) -> dict:
    return {k: decode_value(v) for k, v in (fields or {}).items()}


def firestore_request(method: str, url: str, id_token: str, **kwargs) -> requests.Response:
    """Executes a Firestore HTTP request with token refresh on 401 and exponential backoff."""
    max_attempts = 3
    current_token = id_token

    for attempt in range(1, max_attempts + 1):
        headers = dict(kwargs.pop("headers", None) or {})
        if current_token:
            headers["Authorization"] = f"Bearer {current_token}"
        kwargs["headers"] = headers
        kwargs.setdefault("timeout", 30)

        try:
            resp = requests.request(method, url, **kwargs)
            if resp.status_code == 401 and attempt < max_attempts:
                fresh_token, _ = get_valid_id_token()
                if fresh_token:
                    current_token = fresh_token
                    continue
            return resp
        except (requests.RequestException, OSError):
            if attempt < max_attempts:
                time.sleep(1.0 * attempt)
                fresh_token, _ = get_valid_id_token()
                if fresh_token:
                    current_token = fresh_token
                continue
            raise FirestoreError("Firestore request failed after retries.")

    return resp


def get_doc(uid: str, id_token: str, doc_id: str, collection: str = "links") -> dict | None:
    resp = firestore_request("GET", doc_url(uid, doc_id, collection), id_token)
    if resp.status_code == 404:
        return None
    if not resp.ok:
        raise FirestoreError(f"GET {doc_id} failed: {resp.status_code}")
    data = resp.json()
    return {"id": doc_id, **decode_fields(data.get("fields", {}))}


def patch_doc(
    uid: str, id_token: str, doc_id: str, fields: dict,
    exists: bool | None = None, collection: str = "links"
) -> bool:
    params = [("updateMask.fieldPaths", k) for k in fields]
    if exists is not None:
        params.append(("currentDocument.exists", "true" if exists else "false"))
    body = {"fields": encode_fields(fields)}
    resp = firestore_request("PATCH", doc_url(uid, doc_id, collection), id_token, params=params, json=body)
    if exists is not None and not resp.ok:
        return False
    if not resp.ok:
        raise FirestoreError(f"PATCH {doc_id} failed: {resp.status_code} {resp.text[:120]}")
    return True


def upsert_link(
    uid: str, id_token: str, url: str, category: str = "", status_override: str | None = None
) -> str:
    """Upserts a single URL document deterministically. Returns 'created' | 'updated' | 'unchanged'."""
    doc_id = link_doc_id(url)
    now = now_iso()

    if status_override:
        patch_doc(uid, id_token, doc_id, {
            "url": url, "category": category, "status": status_override, "updatedAt": now
        })
        return "updated"

    updated = patch_doc(uid, id_token, doc_id, {
        "url": url, "category": category, "updatedAt": now
    }, exists=True)
    if updated:
        return "updated"

    created = patch_doc(uid, id_token, doc_id, {
        "url": url, "category": category, "status": "pending",
        "createdAt": now, "updatedAt": now
    }, exists=False)
    if created:
        return "created"

    return "unchanged"


def set_status(
    uid: str, id_token: str, url: str, status: str,
    claimed_by: str | None = None, claimed_at: str | None = None
) -> None:
    doc_id = link_doc_id(url)
    fields = {
        "status": status,
        "updatedAt": now_iso(),
        "claimedBy": claimed_by or "",
        "claimedAt": claimed_at or ""
    }
    patch_doc(uid, id_token, doc_id, fields)


def run_query(
    uid: str, id_token: str, filters: list | None = None,
    order_by: str | None = None, descending: bool = False, limit: int | None = None
) -> list:
    structured = {"from": [{"collectionId": "links"}]}
    if filters:
        field_filters = [
            {"fieldFilter": {"field": {"fieldPath": f}, "op": op, "value": encode_value(v)}}
            for f, op, v in filters
        ]
        structured["where"] = (
            field_filters[0] if len(field_filters) == 1
            else {"compositeFilter": {"op": "AND", "filters": field_filters}}
        )
    if order_by:
        structured["orderBy"] = [{
            "field": {"fieldPath": order_by},
            "direction": "DESCENDING" if descending else "ASCENDING"
        }]
    if limit:
        structured["limit"] = limit

    parent = f"projects/{get_project_id()}/databases/(default)/documents/users/{uid}"
    resp = firestore_request(
        "POST", f"{FIRESTORE_HOST}/v1/{parent}:runQuery", id_token,
        json={"structuredQuery": structured}
    )
    if not resp.ok:
        raise FirestoreError(f"runQuery failed: {resp.status_code}")

    results = []
    for item in resp.json():
        doc = item.get("document")
        if not doc:
            continue
        d_id = doc["name"].rsplit("/", 1)[-1]
        results.append({"id": d_id, **decode_fields(doc.get("fields", {}))})
    return results


def query_pending(uid: str, id_token: str, stale_hours: float = 3.0) -> list:
    """Queries pending links and stale claimed links older than stale_hours."""
    pending = run_query(uid, id_token, [("status", "EQUAL", "pending")], order_by="createdAt")
    cutoff = datetime.now(timezone.utc).timestamp() - (stale_hours * 3600)
    cutoff_iso = datetime.fromtimestamp(cutoff, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
    stale_claimed = run_query(uid, id_token, [
        ("status", "EQUAL", "claimed"),
        ("claimedAt", "LESS_THAN", cutoff_iso)
    ], order_by="claimedAt")
    return pending + stale_claimed


def run_count(uid: str, id_token: str, filters: list | None = None) -> int:
    """Uses count aggregation query for cheap Firestore statistics."""
    structured = {"from": [{"collectionId": "links"}]}
    if filters:
        field_filters = [
            {"fieldFilter": {"field": {"fieldPath": f}, "op": op, "value": encode_value(v)}}
            for f, op, v in filters
        ]
        structured["where"] = (
            field_filters[0] if len(field_filters) == 1
            else {"compositeFilter": {"op": "AND", "filters": field_filters}}
        )

    parent = f"projects/{get_project_id()}/databases/(default)/documents/users/{uid}"
    resp = firestore_request(
        "POST", f"{FIRESTORE_HOST}/v1/{parent}:runAggregationQuery", id_token,
        json={"structuredAggregationQuery": {
            "structuredQuery": structured,
            "aggregations": [{"alias": "count", "count": {}}]
        }}
    )
    if not resp.ok:
        raise FirestoreError(f"runAggregationQuery failed: {resp.status_code}")

    for item in resp.json():
        res = item.get("result")
        if res:
            return int(res["aggregateFields"]["count"]["integerValue"])
    return 0


def get_stats(uid: str, id_token: str) -> dict:
    """Returns total, done, failed, and pending link counts."""
    total = run_count(uid, id_token)
    done = run_count(uid, id_token, [("status", "EQUAL", "done")])
    failed = run_count(uid, id_token, [("status", "EQUAL", "failed")])
    return {
        "total": total,
        "done": done,
        "failed": failed,
        "pending": max(0, total - done - failed)
    }
