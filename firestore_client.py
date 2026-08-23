"""
firestore_client.py — thin REST wrapper around Firestore, used by both
pipeline_gui.py (live dashboard/links table) and automation.py (the run
loop's claim/done/failed state changes).

Deliberately talks to firestore.googleapis.com directly via `requests`
(already a dependency) instead of the `google-cloud-firestore` client
library, for two reasons:
  1. No new dependency.
  2. That library is built around service-account (Admin SDK) auth, which
     bypasses Firestore Security Rules entirely — this app authenticates as
     the signed-in end user instead (Authorization: Bearer <Firebase ID
     token>), so every request is checked against Security Rules the same
     way a web/mobile client's would be. See firebase_auth.py.

Data model: users/{uid}/links/{linkId} — one doc per URL, linkId derived
deterministically from the URL (see link_doc_id) so re-importing the same
CSV maps to the same docs without a query per row.
"""
import hashlib
import json
import re
import time
from datetime import datetime, timezone
from urllib.parse import urlsplit, urlunsplit

import requests

from firebase_auth import FIREBASE_CONFIG_FILE

FIRESTORE_HOST = "https://firestore.googleapis.com"
_project_id_cache = None


class FirestoreError(Exception):
    pass


def _project_id() -> str:
    global _project_id_cache
    if _project_id_cache:
        return _project_id_cache
    from pathlib import Path
    cfg = json.loads(Path(FIREBASE_CONFIG_FILE).read_text(encoding="utf-8"))
    project_id = cfg.get("projectId")
    if not project_id:
        raise FirestoreError(f"{FIREBASE_CONFIG_FILE} is missing 'projectId'.")
    _project_id_cache = project_id
    return project_id


def _documents_base() -> str:
    return f"{FIRESTORE_HOST}/v1/projects/{_project_id()}/databases/(default)/documents"


def _doc_path(uid: str, doc_id: str, collection: str = "links") -> str:
    return f"users/{uid}/{collection}/{doc_id}"


def _doc_url(uid: str, doc_id: str, collection: str = "links") -> str:
    return f"{_documents_base()}/{_doc_path(uid, doc_id, collection)}"


def _headers(id_token: str) -> dict:
    return {"Authorization": f"Bearer {id_token}"}


def link_doc_id(url: str) -> str:
    """Deterministic doc id from a normalized URL — same URL always maps to
    the same document, so re-uploading a CSV upserts instead of duplicating."""
    parts = urlsplit(url.strip())
    normalized = urlunsplit((
        parts.scheme.lower(),
        parts.netloc.lower(),
        parts.path.rstrip("/"),
        parts.query,
        "",
    ))
    return hashlib.sha1(normalized.encode("utf-8")).hexdigest()[:20]


# ── Firestore <-> Python value encoding ─────────────────────────
def _encode_value(v):
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
    return {"stringValue": str(v)}


def _decode_value(fv: dict):
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
    return None


def _encode_fields(d: dict) -> dict:
    return {k: _encode_value(v) for k, v in d.items()}


def _decode_fields(fields: dict) -> dict:
    return {k: _decode_value(v) for k, v in (fields or {}).items()}


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


_now_iso = now_iso  # internal alias, kept short for use elsewhere in this module


def _raise_for_status(resp):
    if not resp.ok:
        raise FirestoreError(f"Firestore {resp.request.method} {resp.url} -> "
                              f"{resp.status_code}: {resp.text}")


# ── Document reads/writes ───────────────────────────────────────
def get_doc(uid: str, id_token: str, doc_id: str, collection: str = "links") -> dict | None:
    resp = requests.get(_doc_url(uid, doc_id, collection), headers=_headers(id_token), timeout=30)
    if resp.status_code == 404:
        return None
    _raise_for_status(resp)
    data = resp.json()
    return {"id": doc_id, **_decode_fields(data.get("fields", {}))}


def patch_doc(uid: str, id_token: str, doc_id: str, fields: dict, *,
              exists: bool | None = None, collection: str = "links"):
    """PATCH just the given fields (Firestore creates the doc if it doesn't
    exist and no exists-precondition is given, or exactly matches it).
    currentDocument.exists is a query param on this endpoint, not a body
    field — the request body is the bare Document resource (fields only)."""
    params = [("updateMask.fieldPaths", k) for k in fields]
    if exists is not None:
        params.append(("currentDocument.exists", "true" if exists else "false"))
    body = {"fields": _encode_fields(fields)}
    resp = requests.patch(_doc_url(uid, doc_id, collection), headers=_headers(id_token),
                          params=params, json=body, timeout=30)
    if exists is not None and not resp.ok:
        # Precondition not met — Firestore returns 404 NOT_FOUND for
        # exists=true against a missing doc, and 400 FAILED_PRECONDITION for
        # exists=false against an existing one. Either way, since the caller
        # explicitly asked for a precondition check, any failure here just
        # means "try the other branch" rather than a real error.
        return False
    _raise_for_status(resp)
    return True


# ── Pipeline config (GUI Settings page) ─────────────────────────
# Stored as a single fixed doc at users/{uid}/settings/pipeline, separate
# from the per-URL docs in users/{uid}/links/* above, so it round-trips as
# one PATCH instead of a query.
CONFIG_COLLECTION = "settings"
CONFIG_DOC_ID = "pipeline"


def get_config(uid: str, id_token: str) -> dict | None:
    """Returns the last-saved pipeline_config.json contents for this user,
    or None if nothing has been synced yet (new account / first device)."""
    doc = get_doc(uid, id_token, CONFIG_DOC_ID, collection=CONFIG_COLLECTION)
    if not doc:
        return None
    doc.pop("id", None)
    doc.pop("updatedAt", None)
    return doc


def save_config(uid: str, id_token: str, cfg: dict):
    """Upserts the pipeline config doc — called whenever the GUI's Settings
    page is saved, so other devices signed into the same account pick it up."""
    fields = dict(cfg)
    fields["updatedAt"] = now_iso()
    patch_doc(uid, id_token, CONFIG_DOC_ID, fields, collection=CONFIG_COLLECTION)


def upsert_link(uid: str, id_token: str, url: str, category: str,
                status_override: str | None = None) -> str:
    """
    Upsert one link by URL. If status_override is given (CSV row explicitly
    said "done"/"failed"), it always wins. Otherwise: brand-new URLs are
    created with status "pending"; URLs that already have a doc keep their
    existing status untouched (only url/category/updatedAt are refreshed) —
    so re-uploading the same CSV never clobbers in-progress/finished work.
    Returns "created" | "updated" | "unchanged".
    """
    doc_id = link_doc_id(url)
    now = _now_iso()

    if status_override:
        patch_doc(uid, id_token, doc_id, {
            "url": url, "category": category, "status": status_override,
            "updatedAt": now,
        })
        return "updated"

    # Try updating only url/category on an existing doc, without touching status.
    updated = patch_doc(uid, id_token, doc_id,
                        {"url": url, "category": category, "updatedAt": now},
                        exists=True)
    if updated:
        return "updated"

    # No existing doc — create it fresh with status "pending".
    created = patch_doc(uid, id_token, doc_id, {
        "url": url, "category": category, "status": "pending",
        "createdAt": now, "updatedAt": now,
    }, exists=False)
    if created:
        return "created"

    # Lost a race with a concurrent write between the two attempts above —
    # harmless, just means someone else's write already covered this URL.
    return "unchanged"


def set_status(uid: str, id_token: str, url: str, status: str,
              claimed_by: str | None = None, claimed_at: str | None = None):
    doc_id = link_doc_id(url)
    fields = {"status": status, "updatedAt": _now_iso()}
    fields["claimedBy"] = claimed_by or ""
    fields["claimedAt"] = claimed_at or ""
    patch_doc(uid, id_token, doc_id, fields)


# ── Queries ──────────────────────────────────────────────────────
def _field_filter(field: str, op: str, value) -> dict:
    return {"fieldFilter": {"field": {"fieldPath": field}, "op": op,
                            "value": _encode_value(value)}}


def run_query(uid: str, id_token: str, filters: list | None = None,
              order_by: str | None = None, descending: bool = False,
              limit: int | None = None) -> list:
    """filters: list of (field, op, value) tuples, ANDed together.
    op is a Firestore StructuredQuery.FieldFilter.Operator string,
    e.g. "EQUAL", "LESS_THAN", "IN"."""
    structured = {"from": [{"collectionId": "links"}]}
    if filters:
        field_filters = [_field_filter(f, op, v) for f, op, v in filters]
        structured["where"] = (field_filters[0] if len(field_filters) == 1
                               else {"compositeFilter": {"op": "AND", "filters": field_filters}})
    if order_by:
        structured["orderBy"] = [{"field": {"fieldPath": order_by},
                                  "direction": "DESCENDING" if descending else "ASCENDING"}]
    if limit:
        structured["limit"] = limit

    parent = f"projects/{_project_id()}/databases/(default)/documents/users/{uid}"
    resp = requests.post(f"{FIRESTORE_HOST}/v1/{parent}:runQuery",
                         headers=_headers(id_token),
                         json={"structuredQuery": structured}, timeout=30)
    _raise_for_status(resp)

    results = []
    for item in resp.json():
        doc = item.get("document")
        if not doc:
            continue
        doc_id = doc["name"].rsplit("/", 1)[-1]
        results.append({"id": doc_id, **_decode_fields(doc.get("fields", {}))})
    return results


def query_pending(uid: str, id_token: str, stale_hours: float = 3) -> list:
    """Rows available to (re)claim: never started, or a "claimed" claim old
    enough that whatever machine placed it has presumably crashed. "done"
    and "failed" are terminal and always excluded."""
    pending = run_query(uid, id_token, [("status", "EQUAL", "pending")],
                        order_by="createdAt")
    cutoff = datetime.now(timezone.utc).timestamp() - stale_hours * 3600
    cutoff_iso = datetime.fromtimestamp(cutoff, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
    stale_claimed = run_query(uid, id_token, [
        ("status", "EQUAL", "claimed"),
        ("claimedAt", "LESS_THAN", cutoff_iso),
    ], order_by="claimedAt")
    return pending + stale_claimed


def run_count(uid: str, id_token: str, filters: list | None = None) -> int:
    """COUNT() aggregation — billed as ~1 read per 1000 matched docs instead
    of one read per document like run_query, so polling this for dashboard
    stats doesn't burn through the Firestore free-tier read quota."""
    structured = {"from": [{"collectionId": "links"}]}
    if filters:
        field_filters = [_field_filter(f, op, v) for f, op, v in filters]
        structured["where"] = (field_filters[0] if len(field_filters) == 1
                               else {"compositeFilter": {"op": "AND", "filters": field_filters}})
    parent = f"projects/{_project_id()}/databases/(default)/documents/users/{uid}"
    resp = requests.post(f"{FIRESTORE_HOST}/v1/{parent}:runAggregationQuery",
                         headers=_headers(id_token),
                         json={"structuredAggregationQuery": {
                             "structuredQuery": structured,
                             "aggregations": [{"alias": "count", "count": {}}],
                         }}, timeout=30)
    _raise_for_status(resp)
    for item in resp.json():
        result = item.get("result")
        if result:
            return int(result["aggregateFields"]["count"]["integerValue"])
    return 0


def get_stats(uid: str, id_token: str) -> dict:
    """total/done/failed/pending counts for the dashboard — mirrors the
    semantics of the old CSV-based _csv_stats(): pending = total - done - failed
    (i.e. "claimed" rows count as pending for display purposes). Uses COUNT
    aggregations (3 cheap reads total) instead of fetching every document."""
    total = run_count(uid, id_token)
    done = run_count(uid, id_token, [("status", "EQUAL", "done")])
    failed = run_count(uid, id_token, [("status", "EQUAL", "failed")])
    return {"total": total, "done": done, "failed": failed, "pending": total - done - failed}
