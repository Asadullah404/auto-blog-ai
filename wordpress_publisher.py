#!/usr/bin/env python3
"""
wordpress_publisher.py  —  PHASE 6: PUBLISH TO WORDPRESS
=========================================================
Consumes the output of your Auto Content Pipeline (automation.py) and pushes
each finished article to a self-hosted WordPress site via the built-in
REST API (/wp-json/wp/v2/), using Application Passwords for auth.

What it does per article:
  • Uploads the feature image  → sets it as the post's FEATURED image (+ alt text)
  • Uploads every section image → inserts inline, each with its own ALT TEXT
  • Rebuilds a CLEAN post body as Gutenberg blocks (intro → [img + h2 + paras]* → conclusion)
    (it does NOT dump your standalone final_output.html — that would fight your theme)
  • Sets excerpt = meta_description   (your theme / OG tags use this as the description)
  • Creates/【reuses】 the Category (from structured['category'])
  • Creates/reuses Tags (from structured['keywords'], comma-split)
  • Publishes immediately (status configurable)
  • Idempotent + checkpointed in the same SQLite DB:
      - a URL already published is skipped (no duplicate posts)
      - uploaded media is remembered (a retry never re-uploads the same file)

TWO WAYS TO USE IT
------------------
1) Hooked into the pipeline (recommended). In automation.py, at the end of
   run_one_url(), right after `html_path = phase_compile(...)`, add:

       from wordpress_publisher import phase_publish, PublishError
       try:
           phase_publish(structured, rendered, out_dir, url, db)
       except PublishError as e:
           warn(f"WordPress publish failed (article still saved locally): {e}")

2) Standalone, over everything already generated:
       python wordpress_publisher.py            # publishes every finished article
       python wordpress_publisher.py --root pipeline_output

CREDENTIALS (never hard-code secrets in git)
--------------------------------------------
Create an Application Password in WordPress:
   WP Admin → Users → Profile → "Application Passwords" → add name "pipeline" → Add.
Copy the generated password (looks like: abcd EFGH ijkl MNOP qrst UVWX).
Then set environment variables (recommended) OR edit WP_CONFIG below:

   export WP_URL="https://yoursite.com"
   export WP_USER="your_login_name"
   export WP_APP_PASSWORD="abcd EFGH ijkl MNOP qrst UVWX"
"""

import os
import sys
import re
import json
import html
import time
import glob
import mimetypes
import argparse
from pathlib import Path

# Ensure UTF-8 stdout/stderr streams on Windows consoles and pipes
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
if hasattr(sys.stderr, "reconfigure"):
    try:
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

import requests
from requests.auth import HTTPBasicAuth

mimetypes.add_type("image/webp", ".webp")  # not registered on all Python builds

_con = None
try:                       # nice output if rich is available (it is, in your pipeline)
    from rich.console import Console
    _con = Console(legacy_windows=False) if os.name == "nt" else Console()
except Exception:
    _con = None

def _safe_print(rich_str, fallback_str):
    if _con is not None:
        try:
            _con.print(rich_str)
            return
        except Exception:
            pass
    clean = re.sub(r"\[/?\w+(?:\s+[^\]]*)?\]", "", fallback_str)
    try:
        print(clean)
    except Exception:
        try:
            print(clean.encode("ascii", "replace").decode("ascii"))
        except Exception:
            pass

def ok(m):   _safe_print(f"  [green]\u2713[/]  {m}", f"  [ok]  {m}")
def inf(m):  _safe_print(f"  [blue]\u2192[/]  {m}", f"  [->]  {m}")
def warn(m): _safe_print(f"  [yellow]\u26a0[/]  {m}", f"  [!]   {m}")
def err(m):  _safe_print(f"  [red]\u2717[/]  {m}", f"  [x]   {m}")
def phline(m): _safe_print(f"[bold magenta]{m}[/]", f"\n==== {m} ====")


# ─────────────────────────────────────────────────────────────
# .env SUPPORT  (dependency-free — no python-dotenv needed)
# Loads KEY=VALUE lines from a .env file into the environment so the
# WP_* variables below pick them up. Real shell env vars still win.
# ─────────────────────────────────────────────────────────────
def _load_dotenv(path=None):
    p = Path(path or os.environ.get("DOTENV_PATH", ".env"))
    if not p.exists():
        return
    for raw in p.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, val = line.split("=", 1)
        key = key.strip()
        val = val.strip().strip('"').strip("'")
        if key:
            os.environ.setdefault(key, val)   # don't override real env vars

_load_dotenv()

def _env_bool(name, default):
    v = os.environ.get(name)
    if v is None:
        return default
    return v.strip().lower() in ("1", "true", "yes", "on", "y")


# ─────────────────────────────────────────────────────────────
# CONFIG  —  edit here OR (better) set the WP_* variables in a .env file
# ─────────────────────────────────────────────────────────────
WP_CONFIG = {
    "base_url":      os.environ.get("WP_URL", "https://YOURSITE.com").rstrip("/"),
    "username":      os.environ.get("WP_USER", "YOUR_WP_USERNAME"),
    "app_password":  os.environ.get("WP_APP_PASSWORD", "xxxx xxxx xxxx xxxx xxxx xxxx"),

    "status":        os.environ.get("WP_STATUS", "publish"),   # "publish" | "draft" | ...
    "alt_from":      os.environ.get("WP_ALT_FROM", "heading"),  # "heading" | "title"
    "max_tags":      12,          # cap number of tags created from keywords

    # ── SEO plugin integration ──────────────────────────────────
    # "rankmath" -> also writes Rank Math SEO title / description / focus keyword.
    #               REQUIRES the mu-plugin `rank-math-rest-meta.php` on your site
    #               (free Rank Math is fine — no Pro needed).
    # "none"     -> core fields only (title, excerpt, featured image, cats, tags).
    "seo_plugin":       os.environ.get("WP_SEO_PLUGIN", "rankmath"),  # "rankmath" | "none"
    "focus_keywords_max": 5,      # Rank Math free supports up to 5 focus keywords
    "timeout":       60,          # seconds per HTTP call
    "verify_ssl":    _env_bool("WP_VERIFY_SSL", True),  # False only for local dev
    "retries":       3,           # network retry attempts per call
    "retry_wait":    5,           # seconds between retries
}


class PublishError(Exception):
    """Raised when the article cannot be published after retries."""
    pass


# ─────────────────────────────────────────────────────────────
# CONFIG FILE  —  written by the GUI (pipeline_gui.py).
# If present, its values override WP_CONFIG so the switches in the
# control panel (Live/Draft, Auto on/off, credentials) take effect.
# ─────────────────────────────────────────────────────────────
CONFIG_FILE  = os.environ.get("PIPELINE_CONFIG", "pipeline_config.json")
AUTO_PUBLISH = _env_bool("WP_AUTO_PUBLISH", True)   # env default; GUI/json can override

def _load_config():
    """Merge settings from pipeline_config.json (if it exists) into WP_CONFIG."""
    global AUTO_PUBLISH
    path = Path(CONFIG_FILE)
    if not path.exists():
        return
    try:
        cfg = json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        warn(f"Could not read {path}: {e}")
        return
    for key in ("base_url", "username", "app_password", "status",
                "seo_plugin", "alt_from", "verify_ssl"):
        if key in cfg and cfg[key] not in (None, ""):
            WP_CONFIG[key] = cfg[key].rstrip("/") if key == "base_url" else cfg[key]
    if "auto_publish" in cfg:
        AUTO_PUBLISH = bool(cfg["auto_publish"])


# ─────────────────────────────────────────────────────────────
# DB CHECKPOINT TABLES  (created inside the pipeline's own SQLite DB)
# ─────────────────────────────────────────────────────────────
def _wp_db_init(db):
    db.execute("""CREATE TABLE IF NOT EXISTS wp_published
                  (url TEXT PRIMARY KEY, post_id INTEGER, post_url TEXT,
                   ts TEXT DEFAULT CURRENT_TIMESTAMP)""")
    db.execute("""CREATE TABLE IF NOT EXISTS wp_media
                  (local_path TEXT PRIMARY KEY, media_id INTEGER, source_url TEXT,
                   ts TEXT DEFAULT CURRENT_TIMESTAMP)""")
    db.commit()

def _already_published(db, url):
    row = db.execute("SELECT post_id, post_url FROM wp_published WHERE url=?",
                     (url,)).fetchone()
    return (row[0], row[1]) if row else None

def _mark_published(db, url, post_id, post_url):
    db.execute("INSERT OR REPLACE INTO wp_published (url, post_id, post_url) VALUES (?,?,?)",
               (url, post_id, post_url)); db.commit()

def _media_cached(db, local_path):
    row = db.execute("SELECT media_id, source_url FROM wp_media WHERE local_path=?",
                     (str(local_path),)).fetchone()
    return (row[0], row[1]) if row else None

def _media_save(db, local_path, media_id, source_url):
    db.execute("INSERT OR REPLACE INTO wp_media (local_path, media_id, source_url) VALUES (?,?,?)",
               (str(local_path), media_id, source_url)); db.commit()


# ─────────────────────────────────────────────────────────────
# HTTP helpers
# ─────────────────────────────────────────────────────────────
def _auth():
    return HTTPBasicAuth(WP_CONFIG["username"], WP_CONFIG["app_password"])

def _api(path):
    return f'{WP_CONFIG["base_url"]}/wp-json/wp/v2/{path.lstrip("/")}'

def _request(method, url, **kw):
    """Thin retry wrapper around requests."""
    kw.setdefault("auth", _auth())
    kw.setdefault("timeout", WP_CONFIG["timeout"])
    kw.setdefault("verify", WP_CONFIG["verify_ssl"])
    last = None
    for attempt in range(1, WP_CONFIG["retries"] + 1):
        try:
            r = requests.request(method, url, **kw)
            if r.status_code in (429, 500, 502, 503, 504):
                raise requests.HTTPError(f"{r.status_code} {r.text[:180]}")
            return r
        except Exception as e:
            last = e
            if attempt < WP_CONFIG["retries"]:
                warn(f"    HTTP {method} retry {attempt}/{WP_CONFIG['retries']}: {e}")
                time.sleep(WP_CONFIG["retry_wait"])
    raise PublishError(f"{method} {url} failed after retries: {last}")

def _check_connection():
    """Verify credentials early, before uploading anything."""
    r = _request("GET", _api("users/me"))
    if r.status_code == 401:
        raise PublishError("401 Unauthorized — check WP_USER / WP_APP_PASSWORD.")
    if r.status_code >= 400:
        raise PublishError(f"Cannot reach REST API ({r.status_code}). "
                           f"Is the URL right and REST enabled? {r.text[:160]}")
    who = r.json().get("name", "?")
    ok(f"Connected to WordPress as [cyan]{who}[/]" if _con_ok() else f"Connected as {who}")

def _con_ok():
    return "Console" in globals().get("_con", type("x", (), {})).__class__.__name__


# ─────────────────────────────────────────────────────────────
# Small text utils
# ─────────────────────────────────────────────────────────────
def _slugify(text, maxlen=80):
    text = (text or "").lower()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_-]+", "-", text).strip("-")
    return text[:maxlen] or "post"

def _esc_body(s):   # escape for text nodes
    return html.escape(str(s or ""), quote=False)

def _esc_attr(s):   # escape for attribute values (alt="...")
    return html.escape(str(s or ""), quote=True)

def _split_keywords(keywords):
    if not keywords:
        return []
    parts = re.split(r"[,\n;|]", str(keywords))
    seen, out = set(), []
    for p in parts:
        t = p.strip()
        k = t.lower()
        if t and k not in seen:
            seen.add(k); out.append(t)
    return out[: WP_CONFIG["max_tags"]]

def _resolve_img(out_dir, p):
    """Return an existing absolute Path for an image referenced by the pipeline."""
    out_dir = Path(out_dir)
    if not p:
        return None
    p = Path(str(p))
    for cand in (p, out_dir / p, out_dir / "rendered" / p.name):
        if cand.exists():
            return cand.resolve()
    return None


# ─────────────────────────────────────────────────────────────
# WordPress operations
# ─────────────────────────────────────────────────────────────
def _upload_media(db, img_path, alt_text, title=None):
    """Upload one image, set its alt text, return (media_id, source_url). Cached."""
    img_path = Path(img_path)
    cached = _media_cached(db, img_path)
    if cached:
        inf(f"    media cached: {img_path.name} (id {cached[0]})")
        return cached

    ctype = mimetypes.guess_type(str(img_path))[0] or "image/jpeg"
    data = img_path.read_bytes()
    headers = {
        "Content-Disposition": f'attachment; filename="{img_path.name}"',
        "Content-Type": ctype,
    }
    r = _request("POST", _api("media"), headers=headers, data=data)
    if r.status_code >= 400:
        raise PublishError(f"media upload failed for {img_path.name}: "
                           f"{r.status_code} {r.text[:180]}")
    obj = r.json()
    media_id = obj["id"]

    # set alt text + title (separate update call — reliable across WP versions)
    upd = _request("POST", _api(f"media/{media_id}"),
                   json={"alt_text": alt_text or "",
                         "title": title or alt_text or img_path.stem})
    source_url = (upd.json() if upd.status_code < 400 else obj).get("source_url", "")

    _media_save(db, img_path, media_id, source_url)
    ok(f"    uploaded {img_path.name} \u2192 id {media_id}")
    return media_id, source_url


def _get_or_create_term(name, kind):
    """kind: 'categories' or 'tags'. Returns term id (creates if missing)."""
    name = (name or "").strip()
    if not name:
        return None
    # search existing
    r = _request("GET", _api(kind), params={"search": name, "per_page": 100})
    if r.status_code < 400:
        for term in r.json():
            tname = html.unescape(term.get("name", "")).strip().lower()
            if tname == name.lower():
                return term["id"]
    # create
    c = _request("POST", _api(kind), json={"name": name})
    if c.status_code < 400:
        return c.json()["id"]

    # race / duplicate / HTML entity mismatch → try search again or fetch all
    r2 = _request("GET", _api(kind), params={"per_page": 100})
    if r2.status_code < 400:
        for term in r2.json():
            tname = html.unescape(term.get("name", "")).strip().lower()
            if tname == name.lower():
                return term["id"]
    warn(f"    could not create {kind[:-1]} '{name}'")
    return None


def _rankmath_meta(structured):
    """Build the Rank Math meta dict from the article data.
    These keys only take effect if the `rank-math-rest-meta.php` mu-plugin is
    installed on the site (it exposes them to the REST API)."""
    meta = {}
    title = structured.get("title")
    desc  = structured.get("meta_description")
    kws   = _split_keywords(structured.get("keywords", ""))
    focus = ", ".join(kws[: WP_CONFIG["focus_keywords_max"]])
    if title:
        meta["rank_math_title"] = title
    if desc:
        meta["rank_math_description"] = desc
    if focus:
        meta["rank_math_focus_keyword"] = focus
    return meta


def _image_block(media_id, url, alt):
    return (f'<!-- wp:image {{"id":{media_id},"sizeSlug":"large","linkDestination":"none"}} -->\n'
            f'<figure class="wp-block-image size-large">'
            f'<img src="{_esc_attr(url)}" alt="{_esc_attr(alt)}" class="wp-image-{media_id}"/>'
            f'</figure>\n<!-- /wp:image -->')

def _para_block(text):
    return f'<!-- wp:paragraph -->\n<p>{_esc_body(text)}</p>\n<!-- /wp:paragraph -->'

def _heading_block(text, level=2):
    return (f'<!-- wp:heading {{"level":{level}}} -->\n'
            f'<h{level}>{_esc_body(text)}</h{level}>\n<!-- /wp:heading -->')


def _build_content(structured, section_media):
    """Assemble the Gutenberg post body. section_media: {index: (id, url, alt)}."""
    blocks = []

    intro = structured.get("intro")
    if intro:
        blocks.append(_para_block(intro))

    for i, sec in enumerate(structured.get("sections", [])):
        heading = sec.get("heading", f"Section {i+1}")
        m = section_media.get(i)
        if m:
            mid, murl, malt = m
            blocks.append(_image_block(mid, murl, malt or heading))
        blocks.append(_heading_block(heading, level=2))
        for para in sec.get("paragraphs", []):
            if para and str(para).strip():
                blocks.append(_para_block(para))

    concl = structured.get("conclusion")
    if isinstance(concl, dict) and concl.get("paragraphs"):
        blocks.append(_heading_block(concl.get("heading", "Conclusion"), level=2))
        for para in concl.get("paragraphs", []):
            if para and str(para).strip():
                blocks.append(_para_block(para))

    return "\n\n".join(blocks)


# ─────────────────────────────────────────────────────────────
# MAIN ENTRY  —  call this from the pipeline
# ─────────────────────────────────────────────────────────────
def phase_publish(structured, rendered, out_dir, url, db, respect_auto=True):
    """
    Publish one finished article to WordPress.
    Args mirror your pipeline:
      structured : dict from phase_transform  (title, meta_description, keywords,
                   category, intro, sections[], conclusion)
      rendered   : dict from phase_render     ({"feature": relpath, "sections": [paths]})
      out_dir    : Path/str of this article's output folder
      url        : the source URL (used as the unique key for checkpointing)
      db         : the open sqlite3 connection from db_init()
    Returns: (post_id, post_url)
    """
    phline("PHASE 6: PUBLISH \u2192 WORDPRESS")
    _load_config()

    # ── Auto mode gate ──────────────────────────────────────────
    # respect_auto=True  → the pipeline hook (obeys the GUI "Auto" switch)
    # respect_auto=False → manual "Publish All Generated" (always runs)
    if respect_auto and not AUTO_PUBLISH:
        inf("Auto-publish is OFF — article generated but not published. "
            "Turn Auto on, or use 'Publish All Generated' later.")
        return None

    _wp_db_init(db)

    # ── idempotency: never post the same article twice ──────────
    existing = _already_published(db, url)
    if existing:
        ok(f"Already published (post {existing[0]}) \u2192 {existing[1]}")
        return existing

    if "YOURSITE" in WP_CONFIG["base_url"] or WP_CONFIG["username"] == "YOUR_WP_USERNAME":
        raise PublishError("WordPress credentials not set. Set WP_URL / WP_USER / "
                           "WP_APP_PASSWORD env vars, or edit WP_CONFIG at the top.")

    _check_connection()

    out_dir = Path(out_dir)
    title   = structured.get("title", "Untitled")
    meta    = structured.get("meta_description", "")
    inf(f"Title: [cyan]{title}[/]" if _con_ok() else f"Title: {title}")

    # ── 1) Feature image → featured media ───────────────────────
    feat_path = _resolve_img(out_dir, rendered.get("feature"))
    featured_id = None
    if feat_path:
        featured_id, _ = _upload_media(db, feat_path, alt_text=title, title=title)
    else:
        warn("No feature image found — post will have no featured image.")

    # ── 2) Section images (each with its own alt text) ──────────
    section_media = {}
    sec_paths = rendered.get("sections", [])
    for i, sec in enumerate(structured.get("sections", [])):
        raw = sec_paths[i] if i < len(sec_paths) else sec.get("img")
        p = _resolve_img(out_dir, raw)
        if not p:
            warn(f"    section {i} image missing — skipping its image.")
            continue
        alt = sec.get("heading", title) if WP_CONFIG["alt_from"] == "heading" else title
        mid, murl = _upload_media(db, p, alt_text=alt, title=alt)
        section_media[i] = (mid, murl, alt)

    # ── 3) Category + tags ──────────────────────────────────────
    cat_id = _get_or_create_term(structured.get("category", "Article"), "categories")
    tag_ids = []
    for kw in _split_keywords(structured.get("keywords", "")):
        tid = _get_or_create_term(kw, "tags")
        if tid:
            tag_ids.append(tid)
    inf(f"Category id: {cat_id} | {len(tag_ids)} tag(s)")

    # ── 4) Build clean Gutenberg body ───────────────────────────
    content = _build_content(structured, section_media)

    # ── 5) Create the post ──────────────────────────────────────
    payload = {
        "title":    title,
        "slug":     _slugify(title),
        "status":   WP_CONFIG["status"],
        "content":  content,
        "excerpt":  meta,          # theme/OG description (no SEO plugin installed)
    }
    # Note: Hostinger AI Theme has a bug where passing featured_media during POST /posts
    # crashes with 500 because post_id is null in their catch_featured_image_change hook.
    # We set featured_media in a separate step after post creation.
    if cat_id:
        payload["categories"] = [cat_id]
    if tag_ids:
        payload["tags"] = tag_ids

    # ── Rank Math SEO meta (needs the mu-plugin on the site) ────
    rm_meta = {}
    if WP_CONFIG["seo_plugin"] == "rankmath":
        rm_meta = _rankmath_meta(structured)
        if rm_meta:
            payload["meta"] = rm_meta

    r = _request("POST", _api("posts"), json=payload)
    if r.status_code >= 400:
        raise PublishError(f"post creation failed: {r.status_code} {r.text[:200]}")
    post = r.json()
    post_id  = post["id"]
    post_url = post.get("link", "")

    # Set featured image in a follow-up step to avoid Hostinger theme 500 error
    if featured_id:
        r_feat = _request("POST", _api(f"posts/{post_id}"), json={"featured_media": featured_id})
        if r_feat.status_code >= 400:
            warn(f"Failed to set featured image id {featured_id} on post {post_id}: {r_feat.text[:150]}")
        else:
            ok(f"Set featured image id {featured_id} on post {post_id}")

    # ── Self-check: did Rank Math meta actually save? ───────────
    # If we sent meta but the response shows it empty, the mu-plugin is missing
    # (WordPress silently drops unregistered meta) — warn so it's easy to fix.
    if rm_meta:
        saved = (post.get("meta") or {})
        if not saved.get("rank_math_description"):
            warn("Rank Math meta was sent but did NOT save. Install the mu-plugin "
                 "`rank-math-rest-meta.php` in wp-content/mu-plugins/ on your site.")
        else:
            ok("Rank Math SEO fields set (title / description / focus keyword).")

    _mark_published(db, url, post_id, post_url)
    ok(f"PUBLISHED \u2192 [green]{post_url}[/]" if _con_ok() else f"PUBLISHED -> {post_url}")
    return post_id, post_url


# ─────────────────────────────────────────────────────────────
# STANDALONE MODE  —  publish everything already generated
# ─────────────────────────────────────────────────────────────
def _load_finished_articles(root):
    """
    Yield (url, structured, out_dir, db) for every article whose transform is done.
    Reads each article folder's own pipeline_state.db.
    """
    import sqlite3
    for db_path in glob.glob(str(Path(root) / "*" / "pipeline_state.db")):
        out_dir = Path(db_path).parent
        db = sqlite3.connect(db_path)
        rows = db.execute(
            "SELECT url, data FROM runs WHERE phase='transform_v3' AND status='done' "
            "ORDER BY id DESC").fetchall()
        seen = set()
        for url, data in rows:
            if url in seen:
                continue
            seen.add(url)
            try:
                structured = json.loads(data)
            except Exception:
                continue
            yield url, structured, out_dir, db


def _reconstruct_rendered(out_dir):
    """Rebuild the 'rendered' dict from files on disk (standalone mode)."""
    rdir = Path(out_dir) / "rendered"
    feature = next((p for p in rdir.glob("feature_rendered.*")), None)
    secs = sorted(str(p) for p in rdir.glob("sec_*_rendered.*"))
    return {"feature": str(feature) if feature else None, "sections": secs}


def main():
    ap = argparse.ArgumentParser(description="Publish finished pipeline articles to WordPress")
    ap.add_argument("--root", default="pipeline_output",
                    help="Pipeline output folder (default: pipeline_output)")
    ap.add_argument("--dry-run", action="store_true",
                    help="List what would be published without posting")
    ap.add_argument("--test", action="store_true",
                    help="Only test the WordPress connection, then exit")
    args = ap.parse_args()

    _load_config()

    if args.test:
        phline("WORDPRESS CONNECTION TEST")
        if "YOURSITE" in WP_CONFIG["base_url"] or WP_CONFIG["username"] == "YOUR_WP_USERNAME":
            err("Credentials not set. Fill them in the control panel and Save.")
            raise SystemExit(1)
        _check_connection()
        ok("Connection OK.")
        return

    phline("WORDPRESS BATCH PUBLISH")
    count = 0
    for url, structured, out_dir, db in _load_finished_articles(args.root):
        _wp_db_init(db)
        if _already_published(db, url):
            inf(f"skip (already published): {structured.get('title','?')}")
            continue
        if args.dry_run:
            inf(f"[dry-run] would publish: {structured.get('title','?')}  <- {url}")
            continue
        rendered = _reconstruct_rendered(out_dir)
        try:
            phase_publish(structured, rendered, out_dir, url, db, respect_auto=False)
            count += 1
        except PublishError as e:
            err(f"Failed: {structured.get('title','?')} :: {e}")
        finally:
            db.close()

    ok(f"Done. {count} article(s) published." if not args.dry_run
       else "Dry run complete.")


if __name__ == "__main__":
    main()
