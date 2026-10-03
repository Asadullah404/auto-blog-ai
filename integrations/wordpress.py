"""
integrations/wordpress.py — Phase 6: WordPress REST API & Gutenberg Publisher
================================================================================
Handles automated publishing to self-hosted WordPress sites via the REST API (/wp-json/wp/v2/)
using Application Passwords. Reconstructs clean Gutenberg blocks, uploads media with alt text,
creates categories & tags, and injects Rank Math SEO metadata.
"""

import html
import json
import mimetypes
import os
from pathlib import Path
import re
import sqlite3
import time
from typing import Any, Dict, List, Optional, Tuple, Union

import requests
from requests.auth import HTTPBasicAuth

mimetypes.add_type("image/webp", ".webp")


class PublishError(Exception):
    """Raised when publication to WordPress fails after retries."""
    pass


def wp_db_init(db: sqlite3.Connection) -> None:
    """Ensures checkpoint tables exist in SQLite for WordPress idempotency."""
    with db:
        db.execute("""
            CREATE TABLE IF NOT EXISTS wp_published (
                url TEXT PRIMARY KEY,
                post_id INTEGER,
                post_url TEXT,
                ts TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        db.execute("""
            CREATE TABLE IF NOT EXISTS wp_media (
                local_path TEXT PRIMARY KEY,
                media_id INTEGER,
                source_url TEXT,
                ts TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)


def already_published(db: sqlite3.Connection, url: str) -> Optional[Tuple[int, str]]:
    """Checks if a URL has already been published to avoid duplicate posts."""
    cur = db.execute("SELECT post_id, post_url FROM wp_published WHERE url = ?", (url,))
    row = cur.fetchone()
    return (row[0], row[1]) if row else None


def mark_published(db: sqlite3.Connection, url: str, post_id: int, post_url: str) -> None:
    """Records a completed WordPress post."""
    with db:
        db.execute(
            "INSERT OR REPLACE INTO wp_published (url, post_id, post_url) VALUES (?, ?, ?)",
            (url, post_id, post_url)
        )


def media_cached(db: sqlite3.Connection, local_path: Union[str, Path]) -> Optional[Tuple[int, str]]:
    """Checks if a local image has already been uploaded to the WordPress media library."""
    cur = db.execute("SELECT media_id, source_url FROM wp_media WHERE local_path = ?", (str(local_path),))
    row = cur.fetchone()
    return (row[0], row[1]) if row else None


def media_save(db: sqlite3.Connection, local_path: Union[str, Path], media_id: int, source_url: str) -> None:
    """Caches an uploaded media ID to prevent duplicate uploads on retry."""
    with db:
        db.execute(
            "INSERT OR REPLACE INTO wp_media (local_path, media_id, source_url) VALUES (?, ?, ?)",
            (str(local_path), media_id, source_url)
        )


def wp_auth(cfg: Dict[str, Any]) -> HTTPBasicAuth:
    """Builds HTTP Basic Auth for WordPress REST API."""
    return HTTPBasicAuth(cfg.get("username", ""), cfg.get("app_password", ""))


def wp_api_url(cfg: Dict[str, Any], path: str) -> str:
    """Constructs the full WordPress REST API endpoint URL."""
    base = cfg.get("base_url", "").rstrip("/")
    endpoint = path.lstrip("/")
    return f"{base}/wp-json/wp/v2/{endpoint}"


def wp_request(method: str, path: str, cfg: Dict[str, Any], **kwargs) -> requests.Response:
    """Wrapper around requests with retries and exponential backoff."""
    url = wp_api_url(cfg, path)
    kwargs.setdefault("auth", wp_auth(cfg))
    kwargs.setdefault("timeout", cfg.get("timeout", 60))
    kwargs.setdefault("verify", cfg.get("verify_ssl", True))

    retries = cfg.get("retries", 3)
    last_err = None

    for attempt in range(1, retries + 1):
        try:
            r = requests.request(method, url, **kwargs)
            if r.status_code in (429, 500, 502, 503, 504):
                raise requests.HTTPError(f"HTTP {r.status_code}: {r.text[:160]}")
            return r
        except Exception as e:
            last_err = e
            if attempt < retries:
                time.sleep(2 * attempt)

    raise PublishError(f"WordPress request {method} {url} failed: {last_err}")


def test_connection(cfg: Dict[str, Any]) -> Dict[str, Any]:
    """
    Tests WordPress credentials and REST API access.
    Returns: {"ok": bool, "user": str, "site_name": str, "error": str}
    """
    try:
        r = wp_request("GET", "users/me", cfg)
        if r.status_code == 401:
            return {"ok": False, "error": "401 Unauthorized — check username and Application Password."}
        if r.status_code >= 400:
            return {"ok": False, "error": f"REST API error (HTTP {r.status_code}): {r.text[:160]}"}

        user_data = r.json()
        who = user_data.get("name", user_data.get("slug", "Authorized User"))

        # Check site settings / name
        site_name = ""
        try:
            settings_resp = wp_request("GET", "settings", cfg)
            if settings_resp.status_code == 200:
                site_name = settings_resp.json().get("title", "")
        except Exception:
            pass

        return {
            "ok": True,
            "user": who,
            "site_name": site_name or cfg.get("base_url", ""),
            "id": user_data.get("id"),
        }
    except Exception as e:
        return {"ok": False, "error": str(e)}


def upload_media_file(
    db: sqlite3.Connection,
    img_path: Union[str, Path],
    alt_text: str,
    title: str = None,
    post_id: int = None,
    cfg: Dict[str, Any] = None,
) -> Tuple[int, str]:
    """Uploads an image file to WordPress Media Library, returns (media_id, source_url)."""
    img_path = Path(img_path)
    cached = media_cached(db, img_path)
    if cached:
        return cached

    ctype = mimetypes.guess_type(str(img_path))[0] or "image/jpeg"
    data = img_path.read_bytes()
    headers = {
        "Content-Disposition": f'attachment; filename="{img_path.name}"',
        "Content-Type": ctype,
    }

    r = wp_request("POST", "media", cfg, headers=headers, data=data)
    if r.status_code >= 400:
        raise PublishError(f"Media upload failed for {img_path.name}: {r.status_code} {r.text[:180]}")

    obj = r.json()
    media_id = obj["id"]

    # Set alt text & title
    upd_payload = {
        "alt_text": alt_text or "",
        "title": title or alt_text or img_path.stem
    }
    if post_id:
        upd_payload["post"] = post_id

    upd = wp_request("POST", f"media/{media_id}", cfg, json=upd_payload)
    source_url = (upd.json() if upd.status_code < 400 else obj).get("source_url", "")

    media_save(db, img_path, media_id, source_url)
    return media_id, source_url


def get_or_create_term(name: str, kind: str, cfg: Dict[str, Any]) -> Optional[int]:
    """Retrieves or creates a category or tag term ID."""
    name = (name or "").strip()
    if not name:
        return None

    # Search existing
    r = wp_request("GET", kind, cfg, params={"search": name, "per_page": 100})
    if r.status_code < 400:
        for term in r.json():
            tname = html.unescape(term.get("name", "")).strip().lower()
            if tname == name.lower():
                return term["id"]

    # Create new
    c = wp_request("POST", kind, cfg, json={"name": name})
    if c.status_code < 400:
        return c.json()["id"]

    return None


def format_inline_markdown(text: str) -> str:
    """Escapes text and replaces bold/italic markdown with HTML."""
    escaped = html.escape(str(text or ""), quote=False)
    escaped = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", escaped)
    escaped = re.sub(r"__(.+?)__", r"<strong>\1</strong>", escaped)
    escaped = re.sub(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)", r"<em>\1</em>", escaped)
    return escaped


def image_block(media_id: int, url: str, alt: str) -> str:
    """Generates a Gutenberg wp:image block."""
    alt_esc = html.escape(str(alt or ""), quote=True)
    url_esc = html.escape(str(url or ""), quote=True)
    return (
        f'<!-- wp:image {{"id":{media_id},"sizeSlug":"large","linkDestination":"none"}} -->\n'
        f'<figure class="wp-block-image size-large">'
        f'<img src="{url_esc}" alt="{alt_esc}" class="wp-image-{media_id}"/>'
        f'</figure>\n<!-- /wp:image -->'
    )


def paragraph_block(text: str) -> str:
    """Generates a Gutenberg wp:paragraph block."""
    return f'<!-- wp:paragraph -->\n<p>{format_inline_markdown(text)}</p>\n<!-- /wp:paragraph -->'


def heading_block(text: str, level: int = 2) -> str:
    """Generates a Gutenberg wp:heading block."""
    return f'<!-- wp:heading {{"level":{level}}} -->\n<h{level}>{format_inline_markdown(text)}</h{level}>\n<!-- /wp:heading -->'


def list_block(items: List[str], ordered: bool = False) -> str:
    """Generates a Gutenberg wp:list block."""
    tag = "ol" if ordered else "ul"
    attrs = '{"ordered":true}' if ordered else ''
    li_html = "\n".join(f"<li>{format_inline_markdown(it.strip())}</li>" for it in items if str(it).strip())
    wp_comment = f'<!-- wp:list {attrs} -->' if attrs else '<!-- wp:list -->'
    return f'{wp_comment}\n<{tag}>\n{li_html}\n</{tag}>\n<!-- /wp:list -->'


def paragraphs_to_gutenberg_blocks(paragraphs: List[Any]) -> List[str]:
    """Converts a section paragraphs array into clean Gutenberg block strings."""
    if not paragraphs:
        return []
    blocks = []
    list_items = []

    def flush_list():
        nonlocal list_items
        if list_items:
            blocks.append(list_block(list_items))
            list_items = []

    for item in paragraphs:
        if not item:
            continue
        text = str(item).strip()
        if not text:
            continue

        if text.startswith("### ") or text.startswith("H3: ") or text.startswith("h3: "):
            flush_list()
            h_text = re.sub(r"^(###\s*|H3:\s*|h3:\s*)", "", text).strip()
            blocks.append(heading_block(h_text, level=3))
        elif text.startswith("## ") and not text.startswith("### "):
            flush_list()
            h_text = text[3:].strip()
            blocks.append(heading_block(h_text, level=2))
        elif text.startswith("- ") or text.startswith("* ") or text.startswith("• ") or re.match(r"^\d+\.\s+", text):
            lines = [l.strip() for l in text.splitlines() if l.strip()]
            for line in lines:
                if line.startswith("- ") or line.startswith("* ") or line.startswith("• "):
                    list_items.append(line[2:].strip())
                elif re.match(r"^\d+\.\s+", line):
                    list_items.append(re.sub(r"^\d+\.\s+", "", line).strip())
                else:
                    flush_list()
                    blocks.append(paragraph_block(line))
        else:
            flush_list()
            blocks.append(paragraph_block(text))

    flush_list()
    return blocks


def build_gutenberg_post_content(
    structured: Dict[str, Any],
    section_media: List[Tuple[int, str, str]],
    pin_media: Optional[Tuple[int, str]] = None,
) -> str:
    """Builds the complete article post body as Gutenberg block comments."""
    blocks = []

    # Intro
    intro = structured.get("intro", "").strip()
    if intro:
        blocks.append(paragraph_block(intro))

    # Sections (Heading -> Image -> Paragraphs / Lists)
    sections = structured.get("sections", [])
    for i, sec in enumerate(sections):
        heading = sec.get("heading", "")
        if heading:
            blocks.append(heading_block(heading, level=2))

        # Inline section image
        if i < len(section_media) and section_media[i][0]:
            media_id, src_url, alt = section_media[i]
            blocks.append(image_block(media_id, src_url, alt))

        # Body blocks
        paras = sec.get("paragraphs", [])
        sec_blocks = paragraphs_to_gutenberg_blocks(paras)
        blocks.extend(sec_blocks)

    # Conclusion
    conclusion = structured.get("conclusion")
    if conclusion and isinstance(conclusion, dict):
        c_head = conclusion.get("heading", "Conclusion")
        if c_head:
            blocks.append(heading_block(c_head, level=2))
        c_blocks = paragraphs_to_gutenberg_blocks(conclusion.get("paragraphs", []))
        blocks.extend(c_blocks)

    # Hidden Pinterest Pin for browser extensions
    if pin_media and pin_media[0]:
        pin_id, pin_url = pin_media
        pin_block = (
            f'<!-- wp:image {{"id":{pin_id},"sizeSlug":"full","linkDestination":"none"}} -->\n'
            f'<figure class="wp-block-image size-full" style="display:none;" data-pin-media="{pin_url}" nopin="nopin">\n'
            f'<img src="{pin_url}" alt="{structured.get("title", "")}" class="wp-image-{pin_id}" style="display:none;"/>\n'
            f'</figure>\n<!-- /wp:image -->'
        )
        blocks.append(pin_block)

    return "\n\n".join(blocks)


def phase_publish(
    structured: Dict[str, Any],
    rendered: Dict[str, Any],
    out_dir: Path,
    url: str,
    db: sqlite3.Connection,
    config: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Executes Phase 6: Publishes finished article to WordPress via REST API.
    """
    wp_db_init(db)
    cfg = config or {}

    # Check if already published
    already = already_published(db, url)
    if already:
        return {"post_id": already[0], "post_url": already[1], "cached": True}

    # Verify site connection
    test_res = test_connection(cfg)
    if not test_res.get("ok"):
        raise PublishError(f"Cannot publish: {test_res.get('error')}")

    out_dir = Path(out_dir)

    # 1. Upload Feature Image
    feat_path = rendered.get("feature")
    if feat_path:
        feat_full = out_dir / feat_path if not Path(feat_path).is_absolute() else Path(feat_path)
    else:
        feat_full = None

    feat_media_id = None
    if feat_full and feat_full.exists():
        alt = structured.get("title", "") if cfg.get("alt_from") == "title" else structured.get("title", "")
        feat_media_id, _ = upload_media_file(db, feat_full, alt, title=structured.get("title"), cfg=cfg)

    # 2. Upload Section Images
    section_media: List[Tuple[int, str, str]] = []
    sec_renders = rendered.get("sections", [])
    sections = structured.get("sections", [])

    for i, s_path in enumerate(sec_renders):
        sp = Path(s_path)
        full_p = out_dir / sp if not sp.is_absolute() else sp
        if full_p.exists():
            heading = sections[i].get("heading", f"Section {i + 1}") if i < len(sections) else ""
            alt = sections[i].get("image_alt", heading) if i < len(sections) else heading
            try:
                mid, murl = upload_media_file(db, full_p, alt, title=heading, cfg=cfg)
                section_media.append((mid, murl, alt))
            except Exception:
                section_media.append((0, "", ""))
        else:
            section_media.append((0, "", ""))

    # 3. Upload Pinterest Pin Image
    pin_media = None
    pin_path = rendered.get("pin")
    if pin_path:
        full_pin = out_dir / pin_path if not Path(pin_path).is_absolute() else Path(pin_path)
        if full_pin.exists():
            try:
                pm_id, pm_url = upload_media_file(
                    db, full_pin, f"Pinterest Pin: {structured.get('title')}", cfg=cfg
                )
                pin_media = (pm_id, pm_url)
            except Exception:
                pass

    # 4. Construct Gutenberg Content
    post_content = build_gutenberg_post_content(structured, section_media, pin_media)

    # 5. Resolve Taxonomy (Category & Tags)
    cat_ids = []
    cat_name = structured.get("category", "").strip()
    if cat_name:
        cid = get_or_create_term(cat_name, "categories", cfg)
        if cid:
            cat_ids.append(cid)

    tag_ids = []
    raw_keywords = structured.get("keywords", "")
    if raw_keywords:
        tags = [t.strip() for t in re.split(r"[,;\n|]", str(raw_keywords)) if t.strip()]
        for tag in tags[:cfg.get("max_tags", 12)]:
            tid = get_or_create_term(tag, "tags", cfg)
            if tid:
                tag_ids.append(tid)

    # 6. SEO Plugin Meta (Rank Math)
    meta = {}
    if cfg.get("seo_plugin", "rankmath") == "rankmath":
        meta["rank_math_title"] = structured.get("title", "")
        meta["rank_math_description"] = structured.get("meta_description", "")
        focus_kws = [t.strip() for t in re.split(r"[,;\n|]", str(raw_keywords)) if t.strip()]
        if focus_kws:
            meta["rank_math_focus_keyword"] = ", ".join(focus_kws[:cfg.get("focus_keywords_max", 5)])

    # 7. Create WordPress Post
    post_payload = {
        "title": structured.get("title", "Untitled Article"),
        "content": post_content,
        "excerpt": structured.get("meta_description", ""),
        "status": cfg.get("status", "publish"),
        "categories": cat_ids,
        "tags": tag_ids,
    }
    if feat_media_id:
        post_payload["featured_media"] = feat_media_id
    if meta:
        post_payload["meta"] = meta

    resp = wp_request("POST", "posts", cfg, json=post_payload)
    if resp.status_code >= 400:
        raise PublishError(f"Post creation failed (HTTP {resp.status_code}): {resp.text[:180]}")

    post_data = resp.json()
    post_id = post_data.get("id")
    post_url = post_data.get("link", "")

    # Save checkpoint
    mark_published(db, url, post_id, post_url)

    return {
        "post_id": post_id,
        "post_url": post_url,
        "status": post_data.get("status"),
        "title": post_data.get("title", {}).get("rendered", ""),
    }
