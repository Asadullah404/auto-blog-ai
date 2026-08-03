# # #!/usr/bin/env python3
# # """
# # Auto Content Pipeline — Extract → SEO Rewrite → Imagen → Render → HTML
# # Features:
# #   - Caps at MAX_SECTIONS (9) sections — 1 feature image + 9 section images
# #   - Proper article conclusion appended when content is trimmed
# #   - Feature/hero image (separate from section images)
# #   - Full-length rewrite (not summarized)
# #   - Auto-downloads SEO skill to Skills/seo_skill.md
# #   - Uses SEO skill as agy context for every rewrite call
# #   - 100% dynamic & fault-tolerant JSON parsing + auto-retry (Zero JSON errors)
# #   - 100% free — agy (Antigravity CLI) for text + Imagen
# #   - Sequential image generation: one at a time
# #   - QUOTA SAFE: detects quota, saves progress, exits cleanly — next run resumes
# # Usage: python automation.py [--fresh]
# # """

# # # ── PHASE 0: AUTO INSTALL ────────────────────────────────────
# # import subprocess, sys, importlib, shutil, os, time

# # REQUIRED = {
# #     "rich":            "rich",
# #     "requests":        "requests",
# #     "lxml":            "lxml",
# #     "lxml_html_clean": "lxml_html_clean",
# #     "newspaper":       "newspaper4k",
# #     "jinja2":          "Jinja2",
# #     "PIL":             "Pillow",
# #     "cv2":             "opencv-python",
# #     "nltk":            "nltk",
# #     "bs4":             "beautifulsoup4",
# # }
# # OPTIONAL = {
# #     "cupy":                "cupy-cuda12x",
# #     "agy_headless_bridge": "agy-headless-bridge",
# # }

# # def _install(pkg, imp, optional=False):
# #     try:
# #         importlib.import_module(imp)
# #         return True
# #     except ImportError:
# #         print(f"  → Installing {pkg} ...")
# #         r = subprocess.run([sys.executable, "-m", "pip", "install", pkg, "-q"],
# #                            capture_output=True, text=True)
# #         if r.returncode != 0:
# #             if optional:
# #                 print(f"  ⚠  {pkg} skipped (optional).")
# #                 return False
# #             print(f"  ✗  Failed: {pkg}"); sys.exit(1)
# #         return True

# # print("\n📦 Installing dependencies ...\n")
# # for imp, pkg in REQUIRED.items():
# #     _install(pkg, imp)

# # GPU_OK = False
# # BRIDGE_OK = False
# # for imp, pkg in OPTIONAL.items():
# #     ok_ = _install(pkg, imp, optional=True)
# #     if imp == "cupy"                and ok_: GPU_OK    = True
# #     if imp == "agy_headless_bridge" and ok_: BRIDGE_OK = True

# # # ── LXML CLEAN COMPATIBILITY PATCH ───────────────────────────
# # try:
# #     import lxml_html_clean as _lxml_clean_mod
# #     import lxml.html as _lxml_html
# #     import types as _types
# #     _lxml_html.clean = _lxml_clean_mod
# #     sys.modules["lxml.html.clean"] = _lxml_clean_mod
# #     _lxml_clean_pkg = _types.ModuleType("lxml.clean")
# #     _lxml_clean_pkg.__dict__.update(vars(_lxml_clean_mod))
# #     sys.modules.setdefault("lxml.clean", _lxml_clean_pkg)
# # except ImportError:
# #     pass

# # try:
# #     import nltk
# #     for ds in ["punkt", "punkt_tab"]:
# #         try: nltk.data.find(f"tokenizers/{ds}")
# #         except LookupError: nltk.download(ds, quiet=True)
# # except Exception: pass

# # print("\n✅ Dependencies ready.\n")

# # # ── IMPORTS ──────────────────────────────────────────────────
# # import json, sqlite3, textwrap, hashlib, re, platform

# # if platform.system() != "Windows":
# #     import pty, select

# # from pathlib import Path
# # from datetime import datetime
# # from io import BytesIO

# # import requests
# # from rich.console import Console
# # from rich.panel import Panel
# # from rich.table import Table
# # from rich.progress import Progress, SpinnerColumn, BarColumn, TextColumn, TimeElapsedColumn
# # from rich.prompt import Prompt
# # from rich.rule import Rule
# # from rich import box
# # from jinja2 import Template
# # from PIL import Image, ImageDraw, ImageFont
# # import cv2, numpy as np
# # from bs4 import BeautifulSoup

# # console = Console()

# # CONFIG = {
# #     "output_dir":        "pipeline_output",
# #     "db_path":           "pipeline_state.db",
# #     "render_w":          1200,
# #     "render_h":          675,
# #     "feature_w":         1200,
# #     "feature_h":         630,
# #     "use_gpu":           GPU_OK,
# #     "agy_timeout":       180,
# #     "agy_img_timeout":   120,
# #     "skills_dir":        "Skills",
# #     "seo_skill_file":    "seo_skill.md",
# #     "chars_per_section": 2000,
# #     "batch_size":        3,
# #     # ── Section cap ─────────────────────────────────────────
# #     "max_sections":      9,      # 1 feature + 9 section images max
# #     # ── Image delays ────────────────────────────────────────
# #     "img_inter_delay":   8,      # seconds between successful image calls
# #     "img_min_file_bytes": 5000,
# # }

# # # ── QUOTA EXCEPTION ──────────────────────────────────────────
# # class QuotaExceededError(Exception):
# #     """Raised when Imagen quota is hit — pipeline saves state and exits cleanly."""
# #     pass

# # # ─────────────────────────────────────────────────────────────
# # # HTML TEMPLATE
# # # ─────────────────────────────────────────────────────────────
# # HTML_TEMPLATE = """<!DOCTYPE html>
# # <html lang="en">
# # <head>
# # <meta charset="UTF-8">
# # <meta name="viewport" content="width=device-width,initial-scale=1">
# # <title>{{ data.title }}</title>
# # <meta name="description" content="{{ data.meta_description }}">
# # <meta name="keywords"    content="{{ data.keywords }}">
# # <meta property="og:title"       content="{{ data.title }}">
# # <meta property="og:description" content="{{ data.meta_description }}">
# # <meta property="og:image"       content="{{ feature_img }}">
# # <meta property="og:type"        content="article">
# # <meta name="twitter:card"        content="summary_large_image">
# # <meta name="twitter:title"       content="{{ data.title }}">
# # <meta name="twitter:description" content="{{ data.meta_description }}">
# # <meta name="twitter:image"       content="{{ feature_img }}">
# # <style>
# # @import url('https://fonts.googleapis.com/css2?family=Playfair+Display:wght@700;900&family=Inter:wght@400;500;600&display=swap');
# # *,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
# # :root{--ink:#0f0f0f;--bg:#f7f6f3;--accent:#2563eb;--rule:#e2e2e2;--muted:#555;--card:#fff}
# # body{background:var(--bg);color:var(--ink);font-family:'Inter',sans-serif;line-height:1.78}
# # .hero{position:relative;width:100%;max-height:630px;overflow:hidden;background:#111}
# # .hero img{display:block;width:100%;height:auto;opacity:.82;object-fit:cover}
# # .hero-overlay{position:absolute;inset:0;background:linear-gradient(to top,rgba(0,0,0,.72) 0%,rgba(0,0,0,.10) 60%,transparent 100%);display:flex;align-items:flex-end;padding:48px 40px}
# # .hero-inner{max-width:860px}
# # .hero-eyebrow{font-size:11px;letter-spacing:3px;text-transform:uppercase;color:var(--accent);font-weight:600;margin-bottom:14px}
# # .hero h1{font-family:'Playfair Display',Georgia,serif;font-size:clamp(1.9rem,4.5vw,3.2rem);line-height:1.15;color:#fff;max-width:760px}
# # .hero-meta{margin-top:18px;font-size:13px;color:#aaa}
# # main{max-width:960px;margin:0 auto;padding:64px 24px 100px}
# # .intro{font-size:1.15rem;line-height:1.85;color:#333;border-left:4px solid var(--accent);padding-left:20px;margin-bottom:64px;max-width:740px}
# # .sec{margin-bottom:80px}
# # .sec-num{font-size:11px;letter-spacing:2px;text-transform:uppercase;color:var(--accent);font-weight:600;margin-bottom:10px}
# # .sec h2{font-family:'Playfair Display',Georgia,serif;font-size:clamp(1.35rem,2.8vw,1.9rem);margin-bottom:18px;line-height:1.28}
# # .img-wrap{border-radius:10px;overflow:hidden;box-shadow:0 6px 32px rgba(0,0,0,.10);margin-bottom:22px}
# # .img-wrap img{display:block;width:100%;height:auto}
# # .sec-body p{font-size:1.04rem;color:#333;margin-bottom:14px;max-width:740px}
# # .sec-body p:last-child{margin-bottom:0}
# # .conclusion{background:linear-gradient(135deg,#1e3a5f 0%,#2563eb 100%);border-radius:16px;padding:48px 44px;margin-top:80px;margin-bottom:40px;color:#fff}
# # .conclusion h2{font-family:'Playfair Display',Georgia,serif;font-size:clamp(1.4rem,2.8vw,2rem);margin-bottom:20px;color:#fff}
# # .conclusion p{font-size:1.05rem;line-height:1.8;margin-bottom:14px;color:rgba(255,255,255,.90)}
# # .conclusion p:last-child{margin-bottom:0}
# # .conclusion-tag{display:inline-block;margin-top:24px;font-size:11px;letter-spacing:2px;text-transform:uppercase;color:rgba(255,255,255,.55);font-weight:600}
# # .div{display:flex;align-items:center;gap:16px;margin:64px 0}
# # .div-line{flex:1;height:1px;background:var(--rule)}
# # .div-dot{width:6px;height:6px;border-radius:50%;background:var(--accent);flex-shrink:0}
# # footer{text-align:center;padding:40px;font-size:12px;color:#aaa;border-top:1px solid var(--rule)}
# # @media(max-width:640px){.hero-overlay{padding:28px 18px}main{padding:40px 16px 72px}.conclusion{padding:32px 22px}}
# # </style>
# # </head>
# # <body>
# # <div class="hero">
# #   <img src="{{ feature_img }}" alt="{{ data.title }}" loading="eager">
# #   <div class="hero-overlay">
# #     <div class="hero-inner">
# #       <div class="hero-eyebrow">{{ data.category | default("Article") }}</div>
# #       <h1>{{ data.title }}</h1>
# #       <div class="hero-meta">{{ generated_at }} · {{ section_count }} sections · {{ read_time }} min read</div>
# #     </div>
# #   </div>
# # </div>
# # <main>
# #   {% if data.intro %}<p class="intro">{{ data.intro }}</p>{% endif %}
# #   {% for s in data.sections %}
# #   <div class="sec">
# #     <div class="sec-num">{{ "%02d"|format(loop.index) }} / {{ "%02d"|format(section_count) }}</div>
# #     {% if s.img %}<div class="img-wrap"><img src="{{ s.img }}" alt="{{ s.heading }}" loading="lazy"></div>{% endif %}
# #     <h2>{{ s.heading }}</h2>
# #     <div class="sec-body">
# #       {% for para in s.paragraphs %}<p>{{ para }}</p>{% endfor %}
# #     </div>
# #   </div>
# #   {% if not loop.last %}<div class="div"><div class="div-line"></div><div class="div-dot"></div><div class="div-line"></div></div>{% endif %}
# #   {% endfor %}
# #   {% if data.conclusion %}
# #   <div class="div"><div class="div-line"></div><div class="div-dot"></div><div class="div-line"></div></div>
# #   <div class="conclusion">
# #     <h2>{{ data.conclusion.heading }}</h2>
# #     {% for para in data.conclusion.paragraphs %}<p>{{ para }}</p>{% endfor %}
# #     <span class="conclusion-tag">End of Article</span>
# #   </div>
# #   {% endif %}
# # </main>
# # <footer>Auto Content Pipeline &middot; {{ generated_at }}</footer>
# # </body>
# # </html>"""

# # # ── DB ───────────────────────────────────────────────────────
# # def db_init(path):
# #     c = sqlite3.connect(path)
# #     c.execute("""CREATE TABLE IF NOT EXISTS runs
# #                  (id INTEGER PRIMARY KEY, url TEXT, phase TEXT,
# #                   status TEXT, data TEXT, ts TEXT DEFAULT CURRENT_TIMESTAMP)""")
# #     # Track which individual images are done (for resume)
# #     c.execute("""CREATE TABLE IF NOT EXISTS images_done
# #                  (id INTEGER PRIMARY KEY, url TEXT, img_key TEXT UNIQUE,
# #                   dest_path TEXT, ts TEXT DEFAULT CURRENT_TIMESTAMP)""")
# #     c.commit(); return c

# # def db_log(c, url, phase, status, data=""):
# #     c.execute("INSERT INTO runs (url,phase,status,data) VALUES (?,?,?,?)",
# #               (url, phase, status, data)); c.commit()

# # def db_cached(c, url, phase):
# #     row = c.execute(
# #         "SELECT data FROM runs WHERE url=? AND phase=? AND status='done' ORDER BY id DESC LIMIT 1",
# #         (url, phase)).fetchone()
# #     return row[0] if row else None

# # def db_img_done(c, url, img_key):
# #     """Returns saved dest_path if this image was already generated, else None."""
# #     row = c.execute(
# #         "SELECT dest_path FROM images_done WHERE url=? AND img_key=?",
# #         (url, img_key)).fetchone()
# #     return row[0] if row else None

# # def db_img_save(c, url, img_key, dest_path):
# #     c.execute(
# #         "INSERT OR REPLACE INTO images_done (url, img_key, dest_path) VALUES (?,?,?)",
# #         (url, img_key, str(dest_path))); c.commit()

# # # ── UI helpers ───────────────────────────────────────────────
# # def ph(n, name, desc):
# #     console.print()
# #     console.print(Rule(f"[bold cyan]Phase {n}[/] [white]{name}[/] [dim]— {desc}[/]", style="cyan"))
# #     console.print()
# # def ok(m):   console.print(f"  [green]✓[/]  {m}")
# # def inf(m):  console.print(f"  [blue]→[/]  {m}")
# # def warn(m): console.print(f"  [yellow]⚠[/]  {m}")
# # def err(m):  console.print(f"  [red]✗[/]  {m}")
# # def spin(msg):
# #     return Progress(SpinnerColumn(style="cyan"), TextColumn(f"[white]{msg}[/]"),
# #                     TimeElapsedColumn(), console=console, transient=True)

# # # ─────────────────────────────────────────────────────────────
# # # SEO SKILL
# # # ─────────────────────────────────────────────────────────────
# # SEO_SKILL_CONTENT = """\
# # # SEO Copywriting Skill v2.0
# # ## Purpose
# # Rewrite web content for maximum on-page SEO while keeping it human, engaging, and accurate.

# # ## Core Rules
# # 1. **Title**: Keep primary keyword within first 60 chars. Use power words (Ultimate, Complete, Best, How to, Why).
# # 2. **Meta Description**: 145-158 chars, include primary keyword, include a CTA or benefit.
# # 3. **Headings (H2)**: Each H2 must contain a long-tail keyword variant.
# # 4. **Paragraphs**: First sentence of each paragraph should contain a keyword. Aim 80-120 words per paragraph.
# # 5. **Keyword Density**: Primary keyword ~1-1.5% of total text. LSI/semantic keywords distributed naturally.
# # 6. **Readability**: Flesch reading ease > 60. Short sentences (avg < 20 words). Active voice.
# # 7. **E-E-A-T signals**: Include specific facts, numbers, examples, and authoritative claims.
# # 8. **Featured snippet optimization**: For each section, include one concise 40-60 word answer block.

# # ## JSON Output Format
# # Return strictly valid JSON — no preamble, no markdown fences:
# # {
# #   "title": "...",
# #   "meta_description": "...",
# #   "keywords": "kw1, kw2, kw3",
# #   "category": "...",
# #   "intro": "2-3 sentence article intro with primary keyword",
# #   "feature_image_prompt": "vivid 50-word photorealistic scene, no text, cinematic lighting",
# #   "sections": [
# #     {
# #       "heading": "H2 with keyword",
# #       "paragraphs": ["paragraph 1 text", "paragraph 2 text"],
# #       "image_prompt": "vivid 50-word photorealistic scene for this section",
# #       "image_alt": "SEO alt text max 125 chars",
# #       "snippet": "40-60 word featured snippet answer"
# #     }
# #   ],
# #   "conclusion": {
# #     "heading": "Final Thoughts heading",
# #     "paragraphs": ["closing paragraph 1", "closing paragraph 2"]
# #   }
# # }

# # ## Style
# # - Conversational but authoritative
# # - No fluff — every sentence earns its place
# # - Vary sentence length for rhythm
# # - End each section with a forward-looking sentence or micro-CTA
# # """

# # def ensure_seo_skill(skills_dir: str) -> str:
# #     sdir = Path(skills_dir)
# #     sdir.mkdir(parents=True, exist_ok=True)
# #     skill_path = sdir / CONFIG["seo_skill_file"]
# #     if skill_path.exists():
# #         ok(f"SEO skill loaded from [cyan]{skill_path}[/]")
# #         return skill_path.read_text(encoding="utf-8")
# #     skill_path.write_text(SEO_SKILL_CONTENT, encoding="utf-8")
# #     ok(f"SEO skill created → [cyan]{skill_path}[/]")
# #     return SEO_SKILL_CONTENT

# # # ── AGY CORE ─────────────────────────────────────────────────
# # def _check_agy():
# #     if not shutil.which("agy"):
# #         err("agy not found. Install: curl -fsSL https://antigravity.google/cli/install.sh | bash")
# #         sys.exit(1)

# # def _strip_ansi(s):
# #     return re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])').sub("", s)

# # def _run_agy(prompt: str, timeout: int) -> str:
# #     if BRIDGE_OK:
# #         from agy_headless_bridge import run as agy_run
# #         result = agy_run(prompt, timeout=timeout)
# #         if hasattr(result, "__iter__") and not isinstance(result, str):
# #             return "".join(c if isinstance(c, str) else str(c) for c in result)
# #         return result or ""

# #     if platform.system() != "Windows":
# #         master, slave = pty.openpty()
# #         proc = subprocess.Popen(
# #             ["agy", "--dangerously-skip-permissions", "-p", prompt],
# #             stdin=slave, stdout=slave, stderr=slave)
# #         os.close(slave)
# #         chunks = []; deadline = time.time() + timeout
# #         while True:
# #             rem = deadline - time.time()
# #             if rem <= 0: proc.kill(); break
# #             r, _, _ = select.select([master], [], [], min(rem, 1.0))
# #             if r:
# #                 try:
# #                     chunk = os.read(master, 4096)
# #                     if chunk: chunks.append(chunk.decode("utf-8", errors="replace"))
# #                     else: break
# #                 except OSError: break
# #             elif proc.poll() is not None: break
# #         try: os.close(master)
# #         except OSError: pass
# #         proc.wait()
# #         return "".join(chunks)

# #     r = subprocess.run(["agy", "--dangerously-skip-permissions", "-p", prompt],
# #                        capture_output=True, text=True, timeout=timeout)
# #     return r.stdout or r.stderr

# # # ─────────────────────────────────────────────────────────────
# # # PHASE 1: EXTRACT
# # # ─────────────────────────────────────────────────────────────
# # def _extract_structured(url: str) -> dict:
# #     from newspaper import Article
# #     art = Article(url); art.download(); art.parse()
# #     title = art.title or "Untitled"
# #     raw_text = art.text or ""

# #     headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
# #     r = requests.get(url, timeout=30, headers=headers)
# #     soup = BeautifulSoup(r.text, "lxml")

# #     for tag in soup(["nav","footer","aside","script","style","noscript","header","form","button","svg"]):
# #         tag.decompose()

# #     sections = []
# #     current_heading = title
# #     current_body_parts = []

# #     content_area = (
# #         soup.find("article") or soup.find("main") or
# #         soup.find(class_=re.compile(r"content|post|entry|article", re.I)) or
# #         soup.body
# #     )
# #     if content_area is None:
# #         content_area = soup

# #     for el in content_area.find_all(["h1","h2","h3","h4","h5","h6","p","li","blockquote"], recursive=True):
# #         tag = el.name
# #         text = el.get_text(separator=" ", strip=True)
# #         if not text or len(text) < 5:
# #             continue
# #         if tag in ("h1","h2","h3","h4","h5","h6"):
# #             body = " ".join(current_body_parts).strip()
# #             if body or (sections and current_heading != title):
# #                 sections.append({"heading": current_heading, "body": body})
# #             current_heading = text
# #             current_body_parts = []
# #         else:
# #             current_body_parts.append(text)

# #     body = " ".join(current_body_parts).strip()
# #     if body:
# #         sections.append({"heading": current_heading, "body": body})

# #     if sections and sections[0]["heading"].lower() == title.lower():
# #         sections = sections[1:]

# #     if not sections:
# #         paras = [p.strip() for p in raw_text.split("\n\n") if p.strip()]
# #         chunk_size = max(3, len(paras) // 5)
# #         for i in range(0, len(paras), chunk_size):
# #             sections.append({"heading": f"Part {len(sections)+1}",
# #                               "body": " ".join(paras[i:i+chunk_size])})

# #     inf(f"Detected [cyan]{len(sections)}[/] headings/sections from source")
# #     return {"title": title, "raw_text": raw_text, "sections": sections}

# # def phase_extract(url, db):
# #     ph("1", "EXTRACT", "Full structured scrape — title + all headings + body")
# #     cached = db_cached(db, url, "extract_v2")
# #     if cached:
# #         warn("Cached — skipping."); return json.loads(cached)
# #     with spin("Downloading ...") as p: p.add_task("", total=None)
# #     try:
# #         data = _extract_structured(url)
# #     except Exception as e:
# #         err(f"Extract failed: {e}"); sys.exit(1)
# #     ok(f"Title: [cyan]{data['title']}[/]")
# #     ok(f"Sections: [cyan]{len(data['sections'])}[/]")
# #     ok(f"Total chars: [cyan]{len(data['raw_text']):,}[/]")
# #     db_log(db, url, "extract_v2", "done", json.dumps(data))
# #     return data

# # # ─────────────────────────────────────────────────────────────
# # # SECTION CAP
# # # ─────────────────────────────────────────────────────────────
# # def cap_sections(sections: list, max_n: int, title: str) -> tuple:
# #     if len(sections) <= max_n:
# #         hint = {"heading": f"Final Thoughts on {title}", "overflow": ""}
# #         return sections, hint

# #     kept     = sections[:max_n]
# #     overflow = sections[max_n:]
# #     overflow_body = " ".join(s.get("body","")[:300] for s in overflow).strip()
# #     hint = {
# #         "heading":  f"Wrapping Up: Everything You Need to Know About {title}",
# #         "overflow": overflow_body,
# #     }
# #     inf(f"[yellow]Section cap:[/] keeping {max_n} of {len(sections)} — {len(overflow)} merged into conclusion")
# #     return kept, hint

# # # ─────────────────────────────────────────────────────────────
# # # PHASE 2: TRANSFORM
# # # ─────────────────────────────────────────────────────────────
# # def _clean_raw_llm_output(raw: str) -> str:
# #     raw = _strip_ansi(raw).strip()
# #     m = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', raw, re.IGNORECASE)
# #     if m: return m.group(1).strip()
# #     fb = raw.find('{'); fl = raw.find('[')
# #     if fb != -1 and (fl == -1 or fb < fl):
# #         lb = raw.rfind('}')
# #         return raw[fb:lb+1] if lb > fb else raw[fb:]
# #     elif fl != -1:
# #         ll = raw.rfind(']')
# #         return raw[fl:ll+1] if ll > fl else raw[fl:]
# #     return raw

# # def _fix_common_json_errors(s):
# #     return re.sub(r',\s*([}\]])', r'\1', s)

# # def _heal_truncated_json(s):
# #     s = s.rstrip().rstrip(",")
# #     in_str = False; esc = False; stack = []
# #     for ch in s:
# #         if esc: esc = False; continue
# #         if ch == '\\' and in_str: esc = True; continue
# #         if ch == '"': in_str = not in_str; continue
# #         if not in_str:
# #             if ch in ('{','['): stack.append(ch)
# #             elif ch in ('}',']'):
# #                 if stack: stack.pop()
# #     if in_str: s += '"'
# #     s = s.rstrip().rstrip(",")
# #     for o in reversed(stack):
# #         s += {'{':'}','[':']'}[o]
# #     return s

# # def _extract_sections_regex(raw):
# #     sections = []
# #     blocks = re.findall(r'\{\s*"heading"\s*:\s*"[^"]+"[\s\S]*?\}(?=\s*,\s*\{|\s*\]|\s*$)', raw)
# #     for block in blocks:
# #         try:
# #             d = json.loads(_fix_common_json_errors(block), strict=False)
# #             if isinstance(d, dict) and "heading" in d:
# #                 sections.append(d)
# #         except Exception: pass
# #     if not sections:
# #         for h in re.findall(r'"heading"\s*:\s*"([^"]+)"', raw):
# #             sections.append({"heading":h,"paragraphs":[f"Optimized content for {h}."],
# #                              "image_prompt":h,"image_alt":h[:120],"snippet":f"Guide on {h}."})
# #     return sections

# # def _parse_json(raw, expected_sections=0):
# #     clean = _clean_raw_llm_output(raw)
# #     for fn in [
# #         lambda s: json.loads(s, strict=False),
# #         lambda s: json.loads(_fix_common_json_errors(s), strict=False),
# #         lambda s: json.loads(_heal_truncated_json(s), strict=False),
# #         lambda s: json.loads(_heal_truncated_json(s[:s.rfind('}')+1]), strict=False),
# #     ]:
# #         try:
# #             d = fn(clean)
# #             if isinstance(d, dict): return d
# #             if isinstance(d, list): return {"sections": d}
# #         except Exception: continue
# #     secs = _extract_sections_regex(raw)
# #     if secs:
# #         warn(f"Extracted {len(secs)} section(s) via regex.")
# #         return {"sections": secs}
# #     raise ValueError(f"Could not parse JSON.\nRaw (first 1000 chars):\n{raw[:1000]}")

# # CONCLUSION_PROMPT = """\
# # {seo_skill}
# # ---
# # Write a compelling conclusion section for the article "{title}".
# # {extra}

# # Return ONLY valid JSON (no markdown, no preamble):
# # {{
# #   "heading": "Engaging conclusion H2 with keyword",
# #   "paragraphs": [
# #     "Paragraph 1: synthesize key takeaways (80-120 words)",
# #     "Paragraph 2: forward-looking statement or call-to-action (60-100 words)"
# #   ]
# # }}
# # """

# # def _rewrite_conclusion(title, hint, seo_skill):
# #     extra = f"Use this context from the rest of the article: {hint['overflow']}" if hint.get("overflow") else ""
# #     prompt = CONCLUSION_PROMPT.format(seo_skill=seo_skill, title=title, extra=extra)
# #     try:
# #         raw = _run_agy(prompt, CONFIG["agy_timeout"])
# #         parsed = _parse_json(raw)
# #         if isinstance(parsed, dict) and "heading" in parsed and "paragraphs" in parsed:
# #             return parsed
# #         if "sections" in parsed and parsed["sections"]:
# #             s = parsed["sections"][0]
# #             return {"heading": s.get("heading", hint["heading"]), "paragraphs": s.get("paragraphs",[])}
# #     except Exception as e:
# #         warn(f"Conclusion rewrite failed ({e}) — using fallback.")
# #     return {
# #         "heading": hint.get("heading", f"Final Thoughts on {title}"),
# #         "paragraphs": [
# #             f"Throughout this article we explored the key dimensions of {title}, "
# #             "breaking down each area so you can apply these insights right away.",
# #             "Whether you are just starting out or looking to deepen your understanding, "
# #             "the concepts covered here provide a solid foundation. Bookmark this guide "
# #             "and revisit it as your knowledge grows.",
# #         ],
# #     }

# # AGY_REWRITE_PROMPT = """\
# # {seo_skill}
# # ---
# # ## YOUR TASK
# # Rewrite this article for SEO, preserving ALL {n_sections} sections.
# # Every section MUST appear in your output — do not merge or drop any.

# # SOURCE TITLE: {title}
# # SOURCE SECTIONS:
# # {sections_block}

# # RULES:
# # - Output ONLY valid JSON, no markdown fences, no preamble.
# # - Do NOT use unescaped double quotes inside string values.
# # - Do NOT use literal linebreaks inside JSON strings.
# # - Return exactly {n_sections} section objects in "sections".
# # - Each section "paragraphs" must have 2-4 paragraphs (80-120 words each).
# # - Include a "conclusion" object.

# # JSON schema:
# # {{
# #   "title": "SEO title",
# #   "meta_description": "145-158 chars",
# #   "keywords": "kw1, kw2, kw3, kw4, kw5",
# #   "category": "Category",
# #   "intro": "article opener",
# #   "feature_image_prompt": "hero scene 50 words",
# #   "sections": [
# #     {{"heading":"H2","paragraphs":["p1","p2"],"image_prompt":"scene","image_alt":"alt","snippet":"answer"}}
# #   ],
# #   "conclusion": {{"heading":"Wrap-up H2","paragraphs":["para1","para2"]}}
# # }}
# # """

# # SEC_ONLY_PROMPT = """\
# # {seo_skill}
# # ---
# # Rewrite these {n} sections from "{title}".
# # Return ONLY: {{"sections": [ ... ]}}

# # RULES:
# # - Valid JSON only, no markdown, no preamble.
# # - Exactly {n} section objects.

# # Sections:
# # {block}
# # """

# # def _build_sections_block(sections):
# #     lines = []
# #     for i, s in enumerate(sections):
# #         lines.append(f"[{i+1}] HEADING: {s['heading']}")
# #         body = s.get("body","").strip()
# #         if body: lines.append(f"    BODY: {body[:CONFIG['chars_per_section']]}")
# #         lines.append("")
# #     return "\n".join(lines)

# # def _rewrite_single_section(s, title, seo_skill):
# #     prompt = (f"{seo_skill}\n---\nRewrite this section from \"{title}\" for SEO.\n"
# #               f"HEADING: {s['heading']}\nBODY: {s.get('body','')[:1500]}\n\n"
# #               f"Return ONLY valid JSON:\n"
# #               f"{{\"heading\":\"{s['heading']}\","
# #               f"\"paragraphs\":[\"Para 1\",\"Para 2\"],"
# #               f"\"image_prompt\":\"scene\",\"image_alt\":\"alt\",\"snippet\":\"answer\"}}")
# #     try:
# #         raw = _run_agy(prompt, CONFIG["agy_timeout"])
# #         parsed = _parse_json(raw)
# #         if isinstance(parsed, dict):
# #             if "heading" in parsed and "paragraphs" in parsed: return parsed
# #             if "sections" in parsed and parsed["sections"]: return parsed["sections"][0]
# #     except Exception: pass
# #     return {"heading": s["heading"],
# #             "paragraphs": [s.get("body","")[:600] or f"Guide to {s['heading']}."],
# #             "image_prompt": s["heading"], "image_alt": s["heading"][:120],
# #             "snippet": s.get("body","")[:200] or s["heading"]}

# # def phase_transform(extracted, url, db, seo_skill):
# #     ph("2", "TRANSFORM", f"Full SEO rewrite — capped at {CONFIG['max_sections']} sections")
# #     cached = db_cached(db, url, "transform_v3")
# #     if cached:
# #         warn("Cached — skipping."); return json.loads(cached)

# #     _check_agy()
# #     title   = extracted["title"]
# #     all_src = extracted["sections"]
# #     sections, conclusion_hint = cap_sections(all_src, CONFIG["max_sections"], title)

# #     BATCH   = CONFIG["batch_size"]
# #     batches = [sections[i:i+BATCH] for i in range(0, len(sections), BATCH)]

# #     inf(f"agy call 1/{len(batches)} — first batch + meta ...")
# #     with spin("agy rewriting ...") as p: p.add_task("", total=None)
# #     try:
# #         raw  = _run_agy(AGY_REWRITE_PROMPT.format(
# #             seo_skill=seo_skill, n_sections=len(batches[0]),
# #             title=title, sections_block=_build_sections_block(batches[0])),
# #             CONFIG["agy_timeout"])
# #         base = _parse_json(raw, len(batches[0]))
# #     except Exception as e:
# #         warn(f"First batch notice ({e}) — recovering ...")
# #         base = {"title":title,"meta_description":f"Complete guide on {title}",
# #                 "keywords":title,"category":"Guide","intro":f"Welcome to our guide on {title}.",
# #                 "feature_image_prompt":title,"sections":[],"conclusion":None}
# #         for s in batches[0]:
# #             base["sections"].append(_rewrite_single_section(s, title, seo_skill))

# #     all_sections = list(base.get("sections", []))

# #     for bi, batch in enumerate(batches[1:], start=1):
# #         inf(f"agy call {bi+1}/{len(batches)} — sections {bi*BATCH+1}-{min((bi+1)*BATCH,len(sections))} ...")
# #         with spin("agy rewriting ...") as p: p.add_task("", total=None)
# #         try:
# #             raw = _run_agy(SEC_ONLY_PROMPT.format(
# #                 seo_skill=seo_skill, n=len(batch), title=title,
# #                 block=_build_sections_block(batch)), CONFIG["agy_timeout"])
# #             fetched = _parse_json(raw, len(batch)).get("sections", [])
# #             if not fetched: raise ValueError("No sections returned")
# #             all_sections.extend(fetched)
# #         except Exception as e:
# #             warn(f"Batch {bi+1} notice ({e}) — rewriting individually ...")
# #             for s in batch:
# #                 all_sections.append(_rewrite_single_section(s, title, seo_skill))

# #     conclusion = base.get("conclusion")
# #     if not conclusion or not isinstance(conclusion, dict) or not conclusion.get("paragraphs"):
# #         inf("Generating conclusion via dedicated agy call ...")
# #         conclusion = _rewrite_conclusion(title, conclusion_hint, seo_skill)
# #     ok(f"Conclusion: [cyan]{conclusion.get('heading','—')}[/]")

# #     result = {
# #         "title":                base.get("title", title),
# #         "meta_description":     base.get("meta_description", ""),
# #         "keywords":             base.get("keywords", ""),
# #         "category":             base.get("category", "Article"),
# #         "intro":                base.get("intro", ""),
# #         "feature_image_prompt": base.get("feature_image_prompt", title),
# #         "sections":             all_sections,
# #         "conclusion":           conclusion,
# #     }
# #     ok(f"Title: [cyan]{result['title']}[/]")
# #     ok(f"Sections: [cyan]{len(all_sections)}[/]  (max {CONFIG['max_sections']})")
# #     db_log(db, url, "transform_v3", "done", json.dumps(result))
# #     return result

# # # ─────────────────────────────────────────────────────────────
# # # PHASE 3: AI IMAGES — quota-safe, resume-on-restart
# # # ─────────────────────────────────────────────────────────────
# # AGY_BRAIN_ROOTS = [
# #     Path.home() / ".gemini" / "antigravity-cli" / "brain",
# #     Path.home() / ".antigravity" / "brain",
# #     Path.home() / ".agy" / "brain",
# # ]

# # AGY_IMG_PROMPT_TEMPLATE = (
# #     "Generate a photorealistic image and save it as {slug}.\n\n"
# #     "Scene description:\n{scene}\n\n"
# #     "Requirements: ultra-photorealistic, cinematic lighting, sharp focus, "
# #     "professional photography quality, 16:9 landscape orientation, no text or watermarks."
# # )

# # _IMG_PATH_RE = re.compile(
# #     r'(?:saved?(?:\s+(?:to|as|at))?|wrote?(?:\s+(?:to|file))?|output(?:\s+(?:file|path))?'
# #     r'|created?|generated?|file(?:\s+path)?)\s*[:\-]?\s*'
# #     r'([^\s\'"<>]+\.(?:png|jpg|jpeg|webp))'
# #     r'|([^\s\'"<>]*\.(?:png|jpg|jpeg|webp))',
# #     re.IGNORECASE,
# # )

# # # Keywords that signal quota/rate-limit in agy output
# # _QUOTA_SIGNALS = [
# #     "quota", "rate limit", "rate_limit", "resource exhausted",
# #     "429", "too many requests", "limit exceeded", "billing",
# #     "ResourceExhausted", "RESOURCE_EXHAUSTED", "quota exceeded",
# #     "daily limit", "free tier", "upgrade",
# # ]

# # def _is_quota_error(text: str) -> bool:
# #     lower = text.lower()
# #     return any(sig.lower() in lower for sig in _QUOTA_SIGNALS)

# # def _snapshot_brain() -> set:
# #     found = set()
# #     for root in AGY_BRAIN_ROOTS:
# #         if root.exists():
# #             for ext in ("png","jpg","jpeg","webp"):
# #                 found.update(root.rglob(f"*.{ext}"))
# #     return found

# # def _find_new_image(before: set, raw_output: str) -> Path | None:
# #     raw = _strip_ansi(raw_output)
# #     for m in _IMG_PATH_RE.finditer(raw):
# #         candidate = (m.group(1) or m.group(2) or "").strip().strip("'\".,;")
# #         if candidate.startswith("/") or (len(candidate) > 2 and candidate[1] == ":"):
# #             p = Path(candidate)
# #             if p.exists() and p.stat().st_size > 1000:
# #                 return p
# #     after = _snapshot_brain()
# #     new   = after - before
# #     if new:
# #         return max(new, key=lambda p: p.stat().st_size)
# #     return None

# # def _copy_image_to_dest(img_path: Path, dest: Path) -> bool:
# #     try:
# #         if img_path.stat().st_size < CONFIG["img_min_file_bytes"]:
# #             warn(f"  Image too small ({img_path.stat().st_size}B) — rejecting")
# #             return False
# #         Image.open(img_path).convert("RGB").save(dest, "JPEG", quality=93, optimize=True)
# #         return True
# #     except Exception as e:
# #         warn(f"  Image copy/validate failed: {e}")
# #         return False

# # def _generate_one_image(scene: str, slug: str, dest: Path, label: str,
# #                          db, url: str) -> bool:
# #     """
# #     Generate a single image.
# #     - If already done (DB record + file exists) → skip, return True.
# #     - If quota hit → raise QuotaExceededError (caller saves state + exits).
# #     - On other failure → use placeholder, return True (don't block pipeline).
# #     """
# #     img_key = f"img:{slug}"

# #     # ── Resume check ─────────────────────────────────────────
# #     saved = db_img_done(db, url, img_key)
# #     if saved and Path(saved).exists() and Path(saved).stat().st_size > CONFIG["img_min_file_bytes"]:
# #         # Copy from saved path to dest if different
# #         if Path(saved) != dest:
# #             try: shutil.copy(saved, dest)
# #             except Exception: pass
# #         ok(f"  {label} [dim]resumed from cache[/]")
# #         return True

# #     before = _snapshot_brain()
# #     prompt = AGY_IMG_PROMPT_TEMPLATE.format(slug=slug, scene=scene)

# #     try:
# #         raw = _run_agy(prompt, CONFIG["agy_img_timeout"])
# #     except Exception as e:
# #         warn(f"  agy error for {label}: {e} — using placeholder")
# #         placeholder(dest, label, CONFIG["render_w"], CONFIG["render_h"])
# #         return True

# #     clean = _strip_ansi(raw)

# #     # ── QUOTA DETECTED ───────────────────────────────────────
# #     if _is_quota_error(clean):
# #         raise QuotaExceededError(
# #             f"Imagen quota reached while generating: {label}"
# #         )

# #     # ── Find file ────────────────────────────────────────────
# #     img_path = _find_new_image(before, clean)
# #     if img_path is None:
# #         warn(f"  No image file found for {label} — using placeholder")
# #         placeholder(dest, label, CONFIG["render_w"], CONFIG["render_h"])
# #         return True

# #     if _copy_image_to_dest(img_path, dest):
# #         db_img_save(db, url, img_key, dest)   # ★ mark as done in DB
# #         return True

# #     warn(f"  Invalid image for {label} — using placeholder")
# #     placeholder(dest, label, CONFIG["render_w"], CONFIG["render_h"])
# #     return True


# # def phase_images(structured: dict, url: str, db, out_dir: Path) -> dict:
# #     ph("3", "AI IMAGES",
# #        f"Sequential — 1 feature + max {CONFIG['max_sections']} sections | quota=stop+resume")
# #     _check_agy()

# #     idir = out_dir / "images"; idir.mkdir(exist_ok=True)
# #     sections    = structured.get("sections", [])
# #     inter_delay = CONFIG["img_inter_delay"]
# #     generated_count = 0   # track how many were newly generated this run

# #     # ── Feature / hero image ─────────────────────────────────
# #     feat_dest  = idir / "feature.jpg"
# #     feat_scene = structured.get("feature_image_prompt", structured.get("title","hero"))
# #     feat_key   = "img:feature_hero"

# #     feat_cached = (db_img_done(db, url, feat_key) and
# #                    feat_dest.exists() and
# #                    feat_dest.stat().st_size > 20_000)

# #     if feat_cached:
# #         ok("Feature image [dim]resumed from cache[/]")
# #     else:
# #         inf(f"Feature image → [dim italic]{feat_scene[:80]}[/]")
# #         # May raise QuotaExceededError
# #         _generate_one_image(feat_scene, "feature_hero", feat_dest, "Feature", db, url)
# #         if feat_dest.exists() and feat_dest.stat().st_size > CONFIG["img_min_file_bytes"]:
# #             ok(f"Feature image ✓ ({feat_dest.stat().st_size // 1024} KB)")
# #             generated_count += 1
# #             inf(f"  Waiting {inter_delay}s ...")
# #             time.sleep(inter_delay)

# #     # ── Per-section images ───────────────────────────────────
# #     sec_paths = []

# #     with Progress(
# #         SpinnerColumn(style="cyan"), TextColumn("[white]{task.description}"),
# #         BarColumn(), TextColumn("[cyan]{task.completed}/{task.total}"),
# #         TimeElapsedColumn(), console=console,
# #     ) as prog:
# #         t = prog.add_task("Section images", total=len(sections))

# #         for i, sec in enumerate(sections):
# #             dest = idir / f"sec_{i:02d}.jpg"
# #             sec_paths.append(dest)

# #             slug  = re.sub(r"[^a-z0-9]+","_",
# #                            sec.get("heading",f"section_{i}").lower())[:40]
# #             scene = (sec.get("image_prompt","").strip() or
# #                      f"{sec.get('heading','')}. {' '.join(sec.get('paragraphs',['']))[:150]}")
# #             label = f"Sec {i:02d}"

# #             # _generate_one_image handles its own resume check
# #             # QuotaExceededError will bubble up and be caught in main()
# #             _generate_one_image(scene, slug, dest, label, db, url)

# #             if dest.exists() and dest.stat().st_size > CONFIG["img_min_file_bytes"]:
# #                 ok(f"  {label} ✓ ({dest.stat().st_size // 1024} KB)")
# #                 generated_count += 1

# #             prog.advance(t)

# #             if i < len(sections) - 1:
# #                 inf(f"  Waiting {inter_delay}s ...")
# #                 time.sleep(inter_delay)

# #     inf(f"Images generated this run: [cyan]{generated_count}[/]")
# #     return {"feature": feat_dest, "sections": sec_paths}

# # # ─────────────────────────────────────────────────────────────
# # # PHASE 4: RENDER
# # # ─────────────────────────────────────────────────────────────
# # _FONT_URLS = [
# #     ("https://github.com/google/fonts/raw/main/ofl/montserrat/static/Montserrat-ExtraBold.ttf","Montserrat-ExtraBold.ttf"),
# #     ("https://github.com/google/fonts/raw/main/ofl/inter/static/Inter-Bold.ttf","Inter-Bold.ttf"),
# #     ("https://github.com/google/fonts/raw/main/ofl/oswald/static/Oswald-Bold.ttf","Oswald-Bold.ttf"),
# # ]
# # _FONT_TTF_CACHE: dict = {}

# # def _dl_font(font_dir: Path) -> Path | None:
# #     font_dir.mkdir(parents=True, exist_ok=True)
# #     for url, fname in _FONT_URLS:
# #         dest = font_dir / fname
# #         if dest.exists(): return dest
# #         try:
# #             r = requests.get(url, timeout=25); r.raise_for_status()
# #             dest.write_bytes(r.content); return dest
# #         except Exception: continue
# #     return None

# # def _sys_font() -> str | None:
# #     for p in ["C:/Windows/Fonts/arialbd.ttf","C:/Windows/Fonts/verdanab.ttf",
# #               "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
# #               "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
# #               "/Library/Fonts/Arial Bold.ttf"]:
# #         if Path(p).exists(): return p
# #     return None

# # def _ttf(size, font_path):
# #     key = (str(font_path), size)
# #     if key in _FONT_TTF_CACHE: return _FONT_TTF_CACHE[key]
# #     font = None
# #     for src in [font_path, _sys_font()]:
# #         if src and Path(str(src)).exists():
# #             try: font = ImageFont.truetype(str(src), size); break
# #             except Exception: pass
# #     if font is None: font = ImageFont.load_default()
# #     _FONT_TTF_CACHE[key] = font; return font

# # def _inspect(path):
# #     img = Image.open(path); w, h = img.size
# #     short = min(w,h)
# #     dpi = "uhd" if short>=2160 else "fhd" if short>=1080 else "hd" if short>=720 else "sd"
# #     return dict(w=w,h=h,dpi=dpi)

# # def _wrap_px(heading, font, avail_w, max_lines, tmp_draw):
# #     words = heading.split(); lines = []; cur = []
# #     for word in words:
# #         test = " ".join(cur+[word])
# #         bb = tmp_draw.textbbox((0,0),test,font=font)
# #         if (bb[2]-bb[0]) <= avail_w: cur.append(word)
# #         else:
# #             if not cur: cur=[word]
# #             lines.append(" ".join(cur)); cur=[word]
# #     if cur: lines.append(" ".join(cur))
# #     return None if len(lines)>max_lines else "\n".join(lines)

# # def _fit_text(heading, out_w, out_h, font_path, band_h, mx, my):
# #     avail_w=out_w-2*mx; avail_h=band_h-2*my
# #     start=max(18,min(out_w//14,avail_h//3,80))
# #     tmp=ImageDraw.Draw(Image.new("RGBA",(4,4))); best=None
# #     for size in range(start,11,-1):
# #         font=_ttf(size,font_path); ls=max(4,int(size*0.22))
# #         wrapped=_wrap_px(heading,font,avail_w,2,tmp)
# #         if wrapped is None: continue
# #         bb=tmp.multiline_textbbox((0,0),wrapped,font=font,spacing=ls)
# #         if (bb[2]-bb[0])<=avail_w and (bb[3]-bb[1])<=avail_h:
# #             best=(font,wrapped,size,ls,bb); break
# #     if best is None:
# #         size=12; font=_ttf(size,font_path); ls=4
# #         wrapped=_wrap_px(heading,font,avail_w,4,tmp) or heading
# #         bb=tmp.multiline_textbbox((0,0),wrapped,font=font,spacing=ls)
# #         best=(font,wrapped,size,ls,bb)
# #     return best

# # def _render_image(bg_path, heading, out_path, out_w, out_h, font_path):
# #     meta=_inspect(bg_path)
# #     bg_full=Image.open(bg_path).convert("RGB"); sw,sh=bg_full.size
# #     scale=max(out_w/sw,out_h/sh); nw,nh=int(sw*scale),int(sh*scale)
# #     bg_full=bg_full.resize((nw,nh),Image.LANCZOS)
# #     left=(nw-out_w)//2; top=(nh-out_h)//2
# #     bg=bg_full.crop((left,top,left+out_w,top+out_h))
# #     mx=int(out_w*0.05); my=int(out_h*0.04); band_h=int(out_h*0.40)
# #     ov=Image.new("RGBA",(out_w,out_h),(0,0,0,0)); od=ImageDraw.Draw(ov)
# #     for y in range(band_h):
# #         a=int(252*(y/band_h)**0.50)
# #         od.rectangle([(0,out_h-band_h+y),(out_w,out_h-band_h+y+1)],fill=(0,0,0,a))
# #     canvas=Image.alpha_composite(bg.convert("RGBA"),ov)
# #     font,wrapped,fsize,ls,bbox=_fit_text(heading,out_w,out_h,font_path,band_h,mx,my)
# #     th=bbox[3]-bbox[1]; ty=(out_h-band_h)+(band_h-th)//2-my
# #     ty=max(min(ty,out_h-th-my),out_h-band_h+my)
# #     tl=Image.new("RGBA",(out_w,out_h),(0,0,0,0)); draw=ImageDraw.Draw(tl)
# #     bh2=max(3,fsize//20); bw=int(out_w*0.10)
# #     by=max(ty-bh2-int(fsize*0.30),out_h-band_h+my//2)
# #     draw.rectangle([(mx,by),(mx+bw,by+bh2)],fill=(56,139,253,255))
# #     sh2=max(2,fsize//18)
# #     for dx,dy in [(-sh2,-sh2),(sh2,-sh2),(-sh2,sh2),(sh2,sh2),(0,sh2*2)]:
# #         draw.multiline_text((mx+dx,ty+dy),wrapped,font=font,fill=(0,0,0,175),spacing=ls)
# #     draw.multiline_text((mx,ty),wrapped,font=font,fill=(255,255,255,255),spacing=ls)
# #     Image.alpha_composite(canvas,tl).convert("RGB").save(out_path,"JPEG",quality=93,optimize=True)
# #     return dict(src=f"{meta['w']}×{meta['h']}",out=f"{out_w}×{out_h}",
# #                 dpi=meta["dpi"].upper(),fs=fsize,ln=wrapped.count("\n")+1)

# # def phase_render(structured, raw_paths, out_dir):
# #     ph("4","RENDER","Compositing headings onto images")
# #     rdir=out_dir/"rendered"; rdir.mkdir(exist_ok=True)
# #     font_path=_dl_font(out_dir/"fonts")
# #     if font_path: ok(f"Font: [cyan]{font_path.name}[/]")
# #     else:
# #         sp=_sys_font(); ok(f"Font: [cyan]{Path(sp).name if sp else 'Pillow default'}[/]")

# #     feat_raw=raw_paths["feature"]; feat_out=rdir/"feature_rendered.jpg"
# #     feat_rel=str(feat_out.relative_to(out_dir))
# #     if not feat_out.exists():
# #         try:
# #             img=Image.open(feat_raw).convert("RGB"); w,h=img.size
# #             scale=max(CONFIG["feature_w"]/w,CONFIG["feature_h"]/h)
# #             nw,nh=int(w*scale),int(h*scale)
# #             img=img.resize((nw,nh),Image.LANCZOS)
# #             left=(nw-CONFIG["feature_w"])//2; top=(nh-CONFIG["feature_h"])//2
# #             img.crop((left,top,left+CONFIG["feature_w"],top+CONFIG["feature_h"]))\
# #                .save(feat_out,"JPEG",quality=93,optimize=True)
# #             ok(f"Feature rendered: [cyan]{feat_out.name}[/]")
# #         except Exception as e:
# #             warn(f"Feature render failed: {e}"); shutil.copy(feat_raw,feat_out)
# #     else:
# #         ok("Feature [dim]cached[/]")

# #     sections=structured.get("sections",[]); sec_raws=raw_paths["sections"]; sec_outs=[]
# #     tbl=Table(box=box.SIMPLE_HEAD,border_style="dim",show_header=True,
# #               header_style="bold magenta",padding=(0,1))
# #     tbl.add_column("#",width=4,justify="right"); tbl.add_column("Heading",width=34,no_wrap=True)
# #     tbl.add_column("Src",width=11,justify="center"); tbl.add_column("px",width=6,justify="right")
# #     tbl.add_column("OK",width=5,justify="center")
# #     rows=[]

# #     with Progress(SpinnerColumn(style="magenta"),TextColumn("[white]{task.description}"),
# #                   BarColumn(bar_width=28),TextColumn("[magenta]{task.completed}/{task.total}"),
# #                   TimeElapsedColumn(),console=console) as prog:
# #         t=prog.add_task("Compositing",total=len(sections))
# #         for i,(sec,raw) in enumerate(zip(sections,sec_raws)):
# #             heading=sec.get("heading",f"Section {i+1}")
# #             out=rdir/f"sec_{i:02d}_rendered.jpg"; sec_outs.append(str(out))
# #             if out.exists():
# #                 rows.append((f"{i:02d}",heading[:33],"—","—","[dim]cache[/]"))
# #                 prog.advance(t); continue
# #             try:
# #                 st=_render_image(raw,heading,out,CONFIG["render_w"],CONFIG["render_h"],font_path)
# #                 rows.append((f"{i:02d}",heading[:33]+("…" if len(heading)>33 else ""),
# #                              st["src"],f"[bold]{st['fs']}[/]","[green]✓[/]"))
# #             except Exception as e:
# #                 warn(f"Sec {i}: {e}"); shutil.copy(raw,out)
# #                 rows.append((f"{i:02d}",heading[:33],"?","—","[red]✗[/]"))
# #             prog.advance(t)

# #     console.print()
# #     for r in rows: tbl.add_row(*[str(c) for c in r])
# #     console.print(tbl); console.print()
# #     return {"feature": feat_rel, "sections": sec_outs}

# # # ─────────────────────────────────────────────────────────────
# # # PHASE 5: COMPILE
# # # ─────────────────────────────────────────────────────────────
# # def _estimate_read_time(structured):
# #     words = sum(len(p.split()) for s in structured.get("sections",[]) for p in s.get("paragraphs",[]))
# #     words += len(structured.get("intro","").split())
# #     words += sum(len(p.split()) for p in (structured.get("conclusion") or {}).get("paragraphs",[]))
# #     return max(1, round(words/200))

# # def phase_compile(structured, rendered, out_dir):
# #     ph("5","COMPILE","Building HTML with SEO meta + feature image + conclusion")
# #     sections=structured.get("sections",[])
# #     for i,s in enumerate(sections):
# #         if i < len(rendered["sections"]):
# #             rp=Path(rendered["sections"][i])
# #             try: s["img"]=str(rp.relative_to(out_dir))
# #             except ValueError: s["img"]=str(rp)
# #         else: s["img"]=None
# #     html=Template(HTML_TEMPLATE).render(
# #         data=structured, feature_img=rendered["feature"],
# #         generated_at=datetime.now().strftime("%d %b %Y, %H:%M"),
# #         section_count=len(sections), read_time=_estimate_read_time(structured))
# #     out=out_dir/"final_output.html"
# #     out.write_text(html,encoding="utf-8")
# #     ok(f"Saved → [cyan]{out}[/]")
# #     return out

# # # ─────────────────────────────────────────────────────────────
# # # PLACEHOLDER
# # # ─────────────────────────────────────────────────────────────
# # def placeholder(dest, label, w, h):
# #     img=Image.new("RGB",(w,h)); draw=ImageDraw.Draw(img)
# #     for y in range(h):
# #         t=y/h
# #         draw.line([(0,y),(w,y)],fill=(int(15+t*35),int(20+t*40),int(70+t*55)))
# #     font_size=max(48,w//18); font=None
# #     for p in ["C:/Windows/Fonts/arialbd.ttf",
# #               "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
# #               "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"]:
# #         try: font=ImageFont.truetype(p,font_size); break
# #         except Exception: continue
# #     if font is None: font=ImageFont.load_default()
# #     lines=textwrap.fill(label[:80],width=22)
# #     draw.text((w//2+3,h//2+3),lines,font=font,fill=(0,0,0,160),anchor="mm",align="center")
# #     draw.text((w//2,h//2),lines,font=font,fill=(220,220,255),anchor="mm",align="center")
# #     img.save(dest,"JPEG",quality=90)

# # # ─────────────────────────────────────────────────────────────
# # # SUMMARY
# # # ─────────────────────────────────────────────────────────────
# # def summary(url, structured, html_path, t0):
# #     elapsed=time.time()-t0
# #     console.print(); console.print(Rule("[bold green]Pipeline Complete[/]",style="green"))
# #     tbl=Table(box=box.ROUNDED,border_style="green",show_header=False,padding=(0,2))
# #     tbl.add_column(style="dim",width=18); tbl.add_column(style="white")
# #     tbl.add_row("URL",url)
# #     tbl.add_row("Title",structured.get("title","—"))
# #     tbl.add_row("Sections",str(len(structured.get("sections",[]))))
# #     tbl.add_row("Conclusion",structured.get("conclusion",{}).get("heading","—")[:60])
# #     tbl.add_row("Keywords",structured.get("keywords","—")[:60])
# #     tbl.add_row("Read time",f"~{_estimate_read_time(structured)} min")
# #     tbl.add_row("Output",str(html_path))
# #     tbl.add_row("Time",f"{elapsed:.1f}s")
# #     console.print(tbl); console.print()
# #     console.print(f"  Open: [link=file://{html_path.absolute()}][cyan]{html_path.absolute()}[/][/link]")
# #     console.print()

# # def quota_summary(url, out_dir, completed_images: int, total_images: int):
# #     """Shown instead of normal summary when quota is hit mid-run."""
# #     console.print()
# #     console.print(Panel(
# #         f"[bold yellow]⚠  IMAGEN QUOTA REACHED[/]\n\n"
# #         f"  Images done  : [cyan]{completed_images}[/] / {total_images}\n"
# #         f"  Progress saved in: [dim]{out_dir}[/]\n\n"
# #         f"  [white]What to do:[/]\n"
# #         f"  • Wait until your Imagen quota resets (usually midnight Pacific)\n"
# #         f"  • Then run the script again with the SAME URL\n"
# #         f"  • It will [green]automatically skip[/] already-generated images\n"
# #         f"    and continue from where it stopped",
# #         title="[bold red]Quota Stopped[/]",
# #         border_style="yellow",
# #         padding=(1, 4),
# #     ))
# #     console.print()

# # # ─────────────────────────────────────────────────────────────
# # # MAIN
# # # ─────────────────────────────────────────────────────────────
# # def main():
# #     console.print()
# #     console.print(Panel.fit(
# #         "[bold white]AUTO CONTENT PIPELINE[/]\n"
# #         "[dim]9-section cap · Conclusion · agy Imagen · Quota-safe resume[/]",
# #         border_style="bold blue", padding=(1,6)))
# #     console.print()

# #     _check_agy(); ok("agy found on PATH.")
# #     if CONFIG["use_gpu"]: ok("GPU (CuPy) enabled.")
# #     else: inf("CPU mode.")
# #     console.print()

# #     seo_skill = ensure_seo_skill(CONFIG["skills_dir"])
# #     console.print()

# #     url = Prompt.ask("  [bold cyan]Article URL[/]", console=console)
# #     if not url.startswith("http"): err("Invalid URL."); sys.exit(1)

# #     fresh = "--fresh" in sys.argv
# #     if fresh: inf("--fresh: wiping cached images & renders.")
# #     console.print()

# #     out_dir = Path(CONFIG["output_dir"]) / hashlib.md5(url.encode()).hexdigest()[:8]
# #     out_dir.mkdir(parents=True, exist_ok=True)

# #     if fresh:
# #         for sub in ("images","rendered"):
# #             d=out_dir/sub
# #             if d.exists(): shutil.rmtree(d); inf(f"  Cleared: {d}")

# #     db=db_init(str(out_dir/CONFIG["db_path"])); t0=time.time()

# #     console.print(Panel(
# #         f"  [cyan]1.[/] EXTRACT    — scrape all headings + body\n"
# #         f"  [cyan]2.[/] TRANSFORM  — SEO rewrite, cap at [bold]{CONFIG['max_sections']}[/] sections + conclusion\n"
# #         f"  [cyan]3.[/] AI IMAGES  — 1 feature + {CONFIG['max_sections']} section images (quota=stop+resume)\n"
# #         f"  [cyan]4.[/] RENDER     — composite headings onto images\n"
# #         f"  [cyan]5.[/] COMPILE    — HTML with SEO meta + conclusion block",
# #         title="[bold]Pipeline Steps[/]", border_style="blue", padding=(0,2)))

# #     try:
# #         extracted  = phase_extract(url, db)
# #         structured = phase_transform(extracted, url, db, seo_skill)

# #         total_images = 1 + len(structured.get("sections",[]))  # feature + sections

# #         try:
# #             raw_paths = phase_images(structured, url, db, out_dir)

# #         except QuotaExceededError as qe:
# #             # ── Count how many images actually landed ────────
# #             idir = out_dir / "images"
# #             done = len([f for f in idir.glob("*.jpg") if f.stat().st_size > CONFIG["img_min_file_bytes"]]) if idir.exists() else 0

# #             console.print()
# #             err(str(qe))
# #             quota_summary(url, out_dir, done, total_images)
# #             db.close()
# #             sys.exit(0)   # clean exit — not an error, just paused

# #         rendered  = phase_render(structured, raw_paths, out_dir)
# #         html_path = phase_compile(structured, rendered, out_dir)
# #         summary(url, structured, html_path, t0)

# #     except KeyboardInterrupt:
# #         console.print("\n\n  [yellow]Interrupted by user.[/]")
# #         console.print(f"  Progress saved. Run again with the same URL to resume.\n")
# #         sys.exit(0)

# #     db.close()


# # if __name__ == "__main__":
# #     main()













# #!/usr/bin/env python3
# """
# Auto Content Pipeline — 24/7 Batch Mode
# Features:
#   - NO section limit — processes every section A to Z
#   - CSV batch mode: reads URLs from a .csv file, marks each "done" when complete
#   - Quota-safe: on Imagen quota hit, waits 6 hours then auto-resumes same URL
#   - Runs forever until every URL in the CSV is marked done
#   - FULL MID-RUN RESUME — if stopped at ANY point (Ctrl+C, crash, power loss):
#       · Extract   → cached in SQLite after first run, always skipped on restart
#       · Transform → each rewrite batch is checkpointed; restarts from last incomplete batch
#       · Images    → every individual image is DB-tracked; already-done images are skipped
#       · Render    → each rendered section file is checked on disk; already done = skip
#       · Compile   → rebuilds HTML (fast, no API calls)
#       · CSV       → only marks "done" after the full pipeline succeeds for that URL
#   - Sequential image generation: one at a time
#   - 100% dynamic & fault-tolerant JSON parsing + auto-retry
# Usage:
#   python automation.py                        # prompts for CSV path
#   python automation.py --csv links.csv        # use specific CSV
#   python automation.py --csv links.csv --fresh  # wipe caches and restart
# CSV format (one URL per row, optional status column):
#   https://example.com/article1
#   https://example.com/article2,done          ← already done, will be skipped
# """

# # ── PHASE 0: AUTO INSTALL ────────────────────────────────────
# import subprocess, sys, importlib, shutil, os, time, csv

# REQUIRED = {
#     "rich":            "rich",
#     "requests":        "requests",
#     "lxml":            "lxml",
#     "lxml_html_clean": "lxml_html_clean",
#     "newspaper":       "newspaper4k",
#     "jinja2":          "Jinja2",
#     "PIL":             "Pillow",
#     "cv2":             "opencv-python",
#     "nltk":            "nltk",
#     "bs4":             "beautifulsoup4",
# }
# OPTIONAL = {
#     "cupy":                "cupy-cuda12x",
#     "agy_headless_bridge": "agy-headless-bridge",
# }

# def _install(pkg, imp, optional=False):
#     try:
#         importlib.import_module(imp)
#         return True
#     except ImportError:
#         print(f"  → Installing {pkg} ...")
#         r = subprocess.run([sys.executable, "-m", "pip", "install", pkg, "-q"],
#                            capture_output=True, text=True)
#         if r.returncode != 0:
#             if optional:
#                 print(f"  ⚠  {pkg} skipped (optional).")
#                 return False
#             print(f"  ✗  Failed: {pkg}"); sys.exit(1)
#         return True

# print("\n📦 Installing dependencies ...\n")
# for imp, pkg in REQUIRED.items():
#     _install(pkg, imp)

# GPU_OK = False
# BRIDGE_OK = False
# for imp, pkg in OPTIONAL.items():
#     ok_ = _install(pkg, imp, optional=True)
#     if imp == "cupy"                and ok_: GPU_OK    = True
#     if imp == "agy_headless_bridge" and ok_: BRIDGE_OK = True

# # ── LXML CLEAN COMPATIBILITY PATCH ───────────────────────────
# try:
#     import lxml_html_clean as _lxml_clean_mod
#     import lxml.html as _lxml_html
#     import types as _types
#     _lxml_html.clean = _lxml_clean_mod
#     sys.modules["lxml.html.clean"] = _lxml_clean_mod
#     _lxml_clean_pkg = _types.ModuleType("lxml.clean")
#     _lxml_clean_pkg.__dict__.update(vars(_lxml_clean_mod))
#     sys.modules.setdefault("lxml.clean", _lxml_clean_pkg)
# except ImportError:
#     pass

# try:
#     import nltk
#     for ds in ["punkt", "punkt_tab"]:
#         try: nltk.data.find(f"tokenizers/{ds}")
#         except LookupError: nltk.download(ds, quiet=True)
# except Exception: pass

# print("\n✅ Dependencies ready.\n")

# # ── IMPORTS ──────────────────────────────────────────────────
# import json, sqlite3, textwrap, hashlib, re, platform, argparse

# if platform.system() != "Windows":
#     import pty, select

# from pathlib import Path
# from datetime import datetime
# from io import BytesIO

# import requests
# from rich.console import Console
# from rich.panel import Panel
# from rich.table import Table
# from rich.progress import Progress, SpinnerColumn, BarColumn, TextColumn, TimeElapsedColumn
# from rich.prompt import Prompt
# from rich.rule import Rule
# from rich import box
# from jinja2 import Template
# from PIL import Image, ImageDraw, ImageFont
# import cv2, numpy as np
# from bs4 import BeautifulSoup

# console = Console()

# # ─────────────────────────────────────────────────────────────
# # CONFIG  (max_sections removed — unlimited)
# # ─────────────────────────────────────────────────────────────
# CONFIG = {
#     "output_dir":         "pipeline_output",
#     "db_path":            "pipeline_state.db",
#     "render_w":           1200,
#     "render_h":           675,
#     "feature_w":          1200,
#     "feature_h":          630,
#     "use_gpu":            GPU_OK,
#     "agy_timeout":        180,
#     "agy_img_timeout":    120,
#     "skills_dir":         "Skills",
#     "seo_skill_file":     "seo_skill.md",
#     "chars_per_section":  2000,
#     "batch_size":         3,
#     # ── Quota wait ──────────────────────────────────────────
#     "quota_wait_hours":   6,           # wait this long after quota hit
#     # ── Image delays ────────────────────────────────────────
#     "img_inter_delay":    8,           # seconds between successful image calls
#     "img_min_file_bytes": 5000,
# }

# QUOTA_WAIT_SECONDS = CONFIG["quota_wait_hours"] * 3600

# # ── QUOTA EXCEPTION ──────────────────────────────────────────
# class QuotaExceededError(Exception):
#     """Raised when Imagen quota is hit — pipeline waits then resumes."""
#     pass

# # ─────────────────────────────────────────────────────────────
# # HTML TEMPLATE
# # ─────────────────────────────────────────────────────────────
# HTML_TEMPLATE = """<!DOCTYPE html>
# <html lang="en">
# <head>
# <meta charset="UTF-8">
# <meta name="viewport" content="width=device-width,initial-scale=1">
# <title>{{ data.title }}</title>
# <meta name="description" content="{{ data.meta_description }}">
# <meta name="keywords"    content="{{ data.keywords }}">
# <meta property="og:title"       content="{{ data.title }}">
# <meta property="og:description" content="{{ data.meta_description }}">
# <meta property="og:image"       content="{{ feature_img }}">
# <meta property="og:type"        content="article">
# <meta name="twitter:card"        content="summary_large_image">
# <meta name="twitter:title"       content="{{ data.title }}">
# <meta name="twitter:description" content="{{ data.meta_description }}">
# <meta name="twitter:image"       content="{{ feature_img }}">
# <style>
# @import url('https://fonts.googleapis.com/css2?family=Playfair+Display:wght@700;900&family=Inter:wght@400;500;600&display=swap');
# *,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
# :root{--ink:#0f0f0f;--bg:#f7f6f3;--accent:#2563eb;--rule:#e2e2e2;--muted:#555;--card:#fff}
# body{background:var(--bg);color:var(--ink);font-family:'Inter',sans-serif;line-height:1.78}
# .hero{position:relative;width:100%;max-height:630px;overflow:hidden;background:#111}
# .hero img{display:block;width:100%;height:auto;opacity:.82;object-fit:cover}
# .hero-overlay{position:absolute;inset:0;background:linear-gradient(to top,rgba(0,0,0,.72) 0%,rgba(0,0,0,.10) 60%,transparent 100%);display:flex;align-items:flex-end;padding:48px 40px}
# .hero-inner{max-width:860px}
# .hero-eyebrow{font-size:11px;letter-spacing:3px;text-transform:uppercase;color:var(--accent);font-weight:600;margin-bottom:14px}
# .hero h1{font-family:'Playfair Display',Georgia,serif;font-size:clamp(1.9rem,4.5vw,3.2rem);line-height:1.15;color:#fff;max-width:760px}
# .hero-meta{margin-top:18px;font-size:13px;color:#aaa}
# main{max-width:960px;margin:0 auto;padding:64px 24px 100px}
# .intro{font-size:1.15rem;line-height:1.85;color:#333;border-left:4px solid var(--accent);padding-left:20px;margin-bottom:64px;max-width:740px}
# .sec{margin-bottom:80px}
# .sec-num{font-size:11px;letter-spacing:2px;text-transform:uppercase;color:var(--accent);font-weight:600;margin-bottom:10px}
# .sec h2{font-family:'Playfair Display',Georgia,serif;font-size:clamp(1.35rem,2.8vw,1.9rem);margin-bottom:18px;line-height:1.28}
# .img-wrap{border-radius:10px;overflow:hidden;box-shadow:0 6px 32px rgba(0,0,0,.10);margin-bottom:22px}
# .img-wrap img{display:block;width:100%;height:auto}
# .sec-body p{font-size:1.04rem;color:#333;margin-bottom:14px;max-width:740px}
# .sec-body p:last-child{margin-bottom:0}
# .conclusion{background:linear-gradient(135deg,#1e3a5f 0%,#2563eb 100%);border-radius:16px;padding:48px 44px;margin-top:80px;margin-bottom:40px;color:#fff}
# .conclusion h2{font-family:'Playfair Display',Georgia,serif;font-size:clamp(1.4rem,2.8vw,2rem);margin-bottom:20px;color:#fff}
# .conclusion p{font-size:1.05rem;line-height:1.8;margin-bottom:14px;color:rgba(255,255,255,.90)}
# .conclusion p:last-child{margin-bottom:0}
# .conclusion-tag{display:inline-block;margin-top:24px;font-size:11px;letter-spacing:2px;text-transform:uppercase;color:rgba(255,255,255,.55);font-weight:600}
# .div{display:flex;align-items:center;gap:16px;margin:64px 0}
# .div-line{flex:1;height:1px;background:var(--rule)}
# .div-dot{width:6px;height:6px;border-radius:50%;background:var(--accent);flex-shrink:0}
# footer{text-align:center;padding:40px;font-size:12px;color:#aaa;border-top:1px solid var(--rule)}
# @media(max-width:640px){.hero-overlay{padding:28px 18px}main{padding:40px 16px 72px}.conclusion{padding:32px 22px}}
# </style>
# </head>
# <body>
# <div class="hero">
#   <img src="{{ feature_img }}" alt="{{ data.title }}" loading="eager">
#   <div class="hero-overlay">
#     <div class="hero-inner">
#       <div class="hero-eyebrow">{{ data.category | default("Article") }}</div>
#       <h1>{{ data.title }}</h1>
#       <div class="hero-meta">{{ generated_at }} · {{ section_count }} sections · {{ read_time }} min read</div>
#     </div>
#   </div>
# </div>
# <main>
#   {% if data.intro %}<p class="intro">{{ data.intro }}</p>{% endif %}
#   {% for s in data.sections %}
#   <div class="sec">
#     <div class="sec-num">{{ "%02d"|format(loop.index) }} / {{ "%02d"|format(section_count) }}</div>
#     {% if s.img %}<div class="img-wrap"><img src="{{ s.img }}" alt="{{ s.heading }}" loading="lazy"></div>{% endif %}
#     <h2>{{ s.heading }}</h2>
#     <div class="sec-body">
#       {% for para in s.paragraphs %}<p>{{ para }}</p>{% endfor %}
#     </div>
#   </div>
#   {% if not loop.last %}<div class="div"><div class="div-line"></div><div class="div-dot"></div><div class="div-line"></div></div>{% endif %}
#   {% endfor %}
#   {% if data.conclusion %}
#   <div class="div"><div class="div-line"></div><div class="div-dot"></div><div class="div-line"></div></div>
#   <div class="conclusion">
#     <h2>{{ data.conclusion.heading }}</h2>
#     {% for para in data.conclusion.paragraphs %}<p>{{ para }}</p>{% endfor %}
#     <span class="conclusion-tag">End of Article</span>
#   </div>
#   {% endif %}
# </main>
# <footer>Auto Content Pipeline &middot; {{ generated_at }}</footer>
# </body>
# </html>"""

# # ── DB ───────────────────────────────────────────────────────
# def db_init(path):
#     c = sqlite3.connect(path)
#     c.execute("""CREATE TABLE IF NOT EXISTS runs
#                  (id INTEGER PRIMARY KEY, url TEXT, phase TEXT,
#                   status TEXT, data TEXT, ts TEXT DEFAULT CURRENT_TIMESTAMP)""")
#     c.execute("""CREATE TABLE IF NOT EXISTS images_done
#                  (id INTEGER PRIMARY KEY, url TEXT, img_key TEXT UNIQUE,
#                   dest_path TEXT, ts TEXT DEFAULT CURRENT_TIMESTAMP)""")
#     c.commit(); return c

# def db_log(c, url, phase, status, data=""):
#     c.execute("INSERT INTO runs (url,phase,status,data) VALUES (?,?,?,?)",
#               (url, phase, status, data)); c.commit()

# def db_cached(c, url, phase):
#     row = c.execute(
#         "SELECT data FROM runs WHERE url=? AND phase=? AND status='done' ORDER BY id DESC LIMIT 1",
#         (url, phase)).fetchone()
#     return row[0] if row else None

# def db_img_done(c, url, img_key):
#     row = c.execute(
#         "SELECT dest_path FROM images_done WHERE url=? AND img_key=?",
#         (url, img_key)).fetchone()
#     return row[0] if row else None

# def db_img_save(c, url, img_key, dest_path):
#     c.execute(
#         "INSERT OR REPLACE INTO images_done (url, img_key, dest_path) VALUES (?,?,?)",
#         (url, img_key, str(dest_path))); c.commit()

# # ── UI helpers ───────────────────────────────────────────────
# def ph(n, name, desc):
#     console.print()
#     console.print(Rule(f"[bold cyan]Phase {n}[/] [white]{name}[/] [dim]— {desc}[/]", style="cyan"))
#     console.print()
# def ok(m):   console.print(f"  [green]✓[/]  {m}")
# def inf(m):  console.print(f"  [blue]→[/]  {m}")
# def warn(m): console.print(f"  [yellow]⚠[/]  {m}")
# def err(m):  console.print(f"  [red]✗[/]  {m}")
# def spin(msg):
#     return Progress(SpinnerColumn(style="cyan"), TextColumn(f"[white]{msg}[/]"),
#                     TimeElapsedColumn(), console=console, transient=True)

# # ─────────────────────────────────────────────────────────────
# # CSV BATCH MANAGEMENT
# # ─────────────────────────────────────────────────────────────

# def csv_load(csv_path: Path) -> list[dict]:
#     """
#     Load URLs from CSV. Each row = {url, status}.
#     Supports:
#       - Single-column:  https://example.com/article
#       - Two-column:     https://example.com/article, done
#     Returns list of dicts with 'url' and 'status' keys.
#     """
#     rows = []
#     with open(csv_path, newline="", encoding="utf-8") as f:
#         for raw_row in csv.reader(f):
#             if not raw_row:
#                 continue
#             url = raw_row[0].strip()
#             if not url or url.startswith("#"):
#                 continue  # skip blank lines and comments
#             status = raw_row[1].strip().lower() if len(raw_row) > 1 else ""
#             rows.append({"url": url, "status": status})
#     return rows


# def csv_save(csv_path: Path, rows: list[dict]):
#     """Write rows back to CSV, preserving order."""
#     with open(csv_path, "w", newline="", encoding="utf-8") as f:
#         writer = csv.writer(f)
#         for row in rows:
#             if row["status"]:
#                 writer.writerow([row["url"], row["status"]])
#             else:
#                 writer.writerow([row["url"]])


# def csv_mark_done(csv_path: Path, url: str):
#     """Mark a specific URL as done in the CSV file."""
#     rows = csv_load(csv_path)
#     for row in rows:
#         if row["url"] == url:
#             row["status"] = "done"
#     csv_save(csv_path, rows)
#     ok(f"[dim]CSV updated → [cyan]{url}[/] marked [green]done[/]")


# def csv_pending(csv_path: Path) -> list[str]:
#     """Return URLs not yet marked done."""
#     return [r["url"] for r in csv_load(csv_path) if r["status"] != "done"]

# # ─────────────────────────────────────────────────────────────
# # QUOTA WAIT — 6-hour countdown, then continues
# # ─────────────────────────────────────────────────────────────

# def quota_wait():
#     """Block for QUOTA_WAIT_SECONDS, printing a live countdown."""
#     hours = CONFIG["quota_wait_hours"]
#     console.print()
#     console.print(Panel(
#         f"[bold yellow]⚠  IMAGEN QUOTA REACHED[/]\n\n"
#         f"  Waiting [bold cyan]{hours} hours[/] for quota to reset, then auto-resuming.\n"
#         f"  Leave this terminal running — it will continue on its own.\n"
#         f"  Press [bold]Ctrl+C[/] only if you want to stop completely.",
#         title="[bold red]Quota Wait — Auto Resume in {hours}h[/]".format(hours=hours),
#         border_style="yellow",
#         padding=(1, 4),
#     ))
#     console.print()

#     end_time = time.time() + QUOTA_WAIT_SECONDS
#     while True:
#         remaining = end_time - time.time()
#         if remaining <= 0:
#             break
#         h = int(remaining // 3600)
#         m = int((remaining % 3600) // 60)
#         s = int(remaining % 60)
#         console.print(f"  [dim]⏳ Quota resume in: [cyan]{h:02d}:{m:02d}:{s:02d}[/][/dim]",
#                       end="\r")
#         time.sleep(5)

#     console.print()
#     console.print()
#     ok("[bold green]Quota wait complete — resuming pipeline![/]")
#     console.print()

# # ─────────────────────────────────────────────────────────────
# # SEO SKILL
# # ─────────────────────────────────────────────────────────────
# SEO_SKILL_CONTENT = """\
# # SEO Copywriting Skill v2.0
# ## Purpose
# Rewrite web content for maximum on-page SEO while keeping it human, engaging, and accurate.

# ## Core Rules
# 1. **Title**: Keep primary keyword within first 60 chars. Use power words (Ultimate, Complete, Best, How to, Why).
# 2. **Meta Description**: 145-158 chars, include primary keyword, include a CTA or benefit.
# 3. **Headings (H2)**: Each H2 must contain a long-tail keyword variant.
# 4. **Paragraphs**: First sentence of each paragraph should contain a keyword. Aim 80-120 words per paragraph.
# 5. **Keyword Density**: Primary keyword ~1-1.5% of total text. LSI/semantic keywords distributed naturally.
# 6. **Readability**: Flesch reading ease > 60. Short sentences (avg < 20 words). Active voice.
# 7. **E-E-A-T signals**: Include specific facts, numbers, examples, and authoritative claims.
# 8. **Featured snippet optimization**: For each section, include one concise 40-60 word answer block.

# ## JSON Output Format
# Return strictly valid JSON — no preamble, no markdown fences:
# {
#   "title": "...",
#   "meta_description": "...",
#   "keywords": "kw1, kw2, kw3",
#   "category": "...",
#   "intro": "2-3 sentence article intro with primary keyword",
#   "feature_image_prompt": "vivid 50-word photorealistic scene, no text, cinematic lighting",
#   "sections": [
#     {
#       "heading": "H2 with keyword",
#       "paragraphs": ["paragraph 1 text", "paragraph 2 text"],
#       "image_prompt": "vivid 50-word photorealistic scene for this section",
#       "image_alt": "SEO alt text max 125 chars",
#       "snippet": "40-60 word featured snippet answer"
#     }
#   ],
#   "conclusion": {
#     "heading": "Final Thoughts heading",
#     "paragraphs": ["closing paragraph 1", "closing paragraph 2"]
#   }
# }

# ## Style
# - Conversational but authoritative
# - No fluff — every sentence earns its place
# - Vary sentence length for rhythm
# - End each section with a forward-looking sentence or micro-CTA
# """

# def ensure_seo_skill(skills_dir: str) -> str:
#     sdir = Path(skills_dir)
#     sdir.mkdir(parents=True, exist_ok=True)
#     skill_path = sdir / CONFIG["seo_skill_file"]
#     if skill_path.exists():
#         ok(f"SEO skill loaded from [cyan]{skill_path}[/]")
#         return skill_path.read_text(encoding="utf-8")
#     skill_path.write_text(SEO_SKILL_CONTENT, encoding="utf-8")
#     ok(f"SEO skill created → [cyan]{skill_path}[/]")
#     return SEO_SKILL_CONTENT

# # ── AGY CORE ─────────────────────────────────────────────────
# def _check_agy():
#     if not shutil.which("agy"):
#         err("agy not found. Install: curl -fsSL https://antigravity.google/cli/install.sh | bash")
#         sys.exit(1)

# def _strip_ansi(s):
#     return re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])').sub("", s)

# def _run_agy(prompt: str, timeout: int) -> str:
#     if BRIDGE_OK:
#         from agy_headless_bridge import run as agy_run
#         result = agy_run(prompt, timeout=timeout)
#         if hasattr(result, "__iter__") and not isinstance(result, str):
#             return "".join(c if isinstance(c, str) else str(c) for c in result)
#         return result or ""

#     if platform.system() != "Windows":
#         master, slave = pty.openpty()
#         proc = subprocess.Popen(
#             ["agy", "--dangerously-skip-permissions", "-p", prompt],
#             stdin=slave, stdout=slave, stderr=slave)
#         os.close(slave)
#         chunks = []; deadline = time.time() + timeout
#         while True:
#             rem = deadline - time.time()
#             if rem <= 0: proc.kill(); break
#             r, _, _ = select.select([master], [], [], min(rem, 1.0))
#             if r:
#                 try:
#                     chunk = os.read(master, 4096)
#                     if chunk: chunks.append(chunk.decode("utf-8", errors="replace"))
#                     else: break
#                 except OSError: break
#             elif proc.poll() is not None: break
#         try: os.close(master)
#         except OSError: pass
#         proc.wait()
#         return "".join(chunks)

#     r = subprocess.run(["agy", "--dangerously-skip-permissions", "-p", prompt],
#                        capture_output=True, text=True, timeout=timeout)
#     return r.stdout or r.stderr

# # ─────────────────────────────────────────────────────────────
# # PHASE 1: EXTRACT
# # ─────────────────────────────────────────────────────────────
# def _extract_structured(url: str) -> dict:
#     from newspaper import Article
#     art = Article(url); art.download(); art.parse()
#     title = art.title or "Untitled"
#     raw_text = art.text or ""

#     headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
#     r = requests.get(url, timeout=30, headers=headers)
#     soup = BeautifulSoup(r.text, "lxml")

#     for tag in soup(["nav","footer","aside","script","style","noscript","header","form","button","svg"]):
#         tag.decompose()

#     sections = []
#     current_heading = title
#     current_body_parts = []

#     content_area = (
#         soup.find("article") or soup.find("main") or
#         soup.find(class_=re.compile(r"content|post|entry|article", re.I)) or
#         soup.body
#     )
#     if content_area is None:
#         content_area = soup

#     for el in content_area.find_all(["h1","h2","h3","h4","h5","h6","p","li","blockquote"], recursive=True):
#         tag = el.name
#         text = el.get_text(separator=" ", strip=True)
#         if not text or len(text) < 5:
#             continue
#         if tag in ("h1","h2","h3","h4","h5","h6"):
#             body = " ".join(current_body_parts).strip()
#             if body or (sections and current_heading != title):
#                 sections.append({"heading": current_heading, "body": body})
#             current_heading = text
#             current_body_parts = []
#         else:
#             current_body_parts.append(text)

#     body = " ".join(current_body_parts).strip()
#     if body:
#         sections.append({"heading": current_heading, "body": body})

#     if sections and sections[0]["heading"].lower() == title.lower():
#         sections = sections[1:]

#     if not sections:
#         paras = [p.strip() for p in raw_text.split("\n\n") if p.strip()]
#         chunk_size = max(3, len(paras) // 5)
#         for i in range(0, len(paras), chunk_size):
#             sections.append({"heading": f"Part {len(sections)+1}",
#                               "body": " ".join(paras[i:i+chunk_size])})

#     inf(f"Detected [cyan]{len(sections)}[/] headings/sections from source")
#     return {"title": title, "raw_text": raw_text, "sections": sections}

# def phase_extract(url, db):
#     ph("1", "EXTRACT", "Full structured scrape — title + ALL headings + body (no limit)")
#     cached = db_cached(db, url, "extract_v2")
#     if cached:
#         warn("Cached — skipping."); return json.loads(cached)
#     with spin("Downloading ...") as p: p.add_task("", total=None)
#     try:
#         data = _extract_structured(url)
#     except Exception as e:
#         err(f"Extract failed: {e}"); raise
#     ok(f"Title: [cyan]{data['title']}[/]")
#     ok(f"Sections: [cyan]{len(data['sections'])}[/]")
#     ok(f"Total chars: [cyan]{len(data['raw_text']):,}[/]")
#     db_log(db, url, "extract_v2", "done", json.dumps(data))
#     return data

# # ─────────────────────────────────────────────────────────────
# # PHASE 2: TRANSFORM  (no section cap)
# # ─────────────────────────────────────────────────────────────
# def _clean_raw_llm_output(raw: str) -> str:
#     raw = _strip_ansi(raw).strip()
#     m = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', raw, re.IGNORECASE)
#     if m: return m.group(1).strip()
#     fb = raw.find('{'); fl = raw.find('[')
#     if fb != -1 and (fl == -1 or fb < fl):
#         lb = raw.rfind('}')
#         return raw[fb:lb+1] if lb > fb else raw[fb:]
#     elif fl != -1:
#         ll = raw.rfind(']')
#         return raw[fl:ll+1] if ll > fl else raw[fl:]
#     return raw

# def _fix_common_json_errors(s):
#     return re.sub(r',\s*([}\]])', r'\1', s)

# def _heal_truncated_json(s):
#     s = s.rstrip().rstrip(",")
#     in_str = False; esc = False; stack = []
#     for ch in s:
#         if esc: esc = False; continue
#         if ch == '\\' and in_str: esc = True; continue
#         if ch == '"': in_str = not in_str; continue
#         if not in_str:
#             if ch in ('{','['): stack.append(ch)
#             elif ch in ('}',']'):
#                 if stack: stack.pop()
#     if in_str: s += '"'
#     s = s.rstrip().rstrip(",")
#     for o in reversed(stack):
#         s += {'{':'}','[':']'}[o]
#     return s

# def _extract_sections_regex(raw):
#     sections = []
#     blocks = re.findall(r'\{\s*"heading"\s*:\s*"[^"]+"[\s\S]*?\}(?=\s*,\s*\{|\s*\]|\s*$)', raw)
#     for block in blocks:
#         try:
#             d = json.loads(_fix_common_json_errors(block), strict=False)
#             if isinstance(d, dict) and "heading" in d:
#                 sections.append(d)
#         except Exception: pass
#     if not sections:
#         for h in re.findall(r'"heading"\s*:\s*"([^"]+)"', raw):
#             sections.append({"heading":h,"paragraphs":[f"Optimized content for {h}."],
#                              "image_prompt":h,"image_alt":h[:120],"snippet":f"Guide on {h}."})
#     return sections

# def _parse_json(raw, expected_sections=0):
#     clean = _clean_raw_llm_output(raw)
#     for fn in [
#         lambda s: json.loads(s, strict=False),
#         lambda s: json.loads(_fix_common_json_errors(s), strict=False),
#         lambda s: json.loads(_heal_truncated_json(s), strict=False),
#         lambda s: json.loads(_heal_truncated_json(s[:s.rfind('}')+1]), strict=False),
#     ]:
#         try:
#             d = fn(clean)
#             if isinstance(d, dict): return d
#             if isinstance(d, list): return {"sections": d}
#         except Exception: continue
#     secs = _extract_sections_regex(raw)
#     if secs:
#         warn(f"Extracted {len(secs)} section(s) via regex.")
#         return {"sections": secs}
#     raise ValueError(f"Could not parse JSON.\nRaw (first 1000 chars):\n{raw[:1000]}")

# CONCLUSION_PROMPT = """\
# {seo_skill}
# ---
# Write a compelling conclusion section for the article "{title}".
# {extra}

# Return ONLY valid JSON (no markdown, no preamble):
# {{
#   "heading": "Engaging conclusion H2 with keyword",
#   "paragraphs": [
#     "Paragraph 1: synthesize key takeaways (80-120 words)",
#     "Paragraph 2: forward-looking statement or call-to-action (60-100 words)"
#   ]
# }}
# """

# def _rewrite_conclusion(title, seo_skill, extra=""):
#     prompt = CONCLUSION_PROMPT.format(seo_skill=seo_skill, title=title, extra=extra)
#     try:
#         raw = _run_agy(prompt, CONFIG["agy_timeout"])
#         parsed = _parse_json(raw)
#         if isinstance(parsed, dict) and "heading" in parsed and "paragraphs" in parsed:
#             return parsed
#         if "sections" in parsed and parsed["sections"]:
#             s = parsed["sections"][0]
#             return {"heading": s.get("heading", f"Final Thoughts on {title}"),
#                     "paragraphs": s.get("paragraphs",[])}
#     except Exception as e:
#         warn(f"Conclusion rewrite failed ({e}) — using fallback.")
#     return {
#         "heading": f"Final Thoughts on {title}",
#         "paragraphs": [
#             f"Throughout this article we explored the key dimensions of {title}, "
#             "breaking down each area so you can apply these insights right away.",
#             "Whether you are just starting out or looking to deepen your understanding, "
#             "the concepts covered here provide a solid foundation. Bookmark this guide "
#             "and revisit it as your knowledge grows.",
#         ],
#     }

# AGY_REWRITE_PROMPT = """\
# {seo_skill}
# ---
# ## YOUR TASK
# Rewrite this article for SEO, preserving ALL {n_sections} sections.
# Every section MUST appear in your output — do not merge or drop any.

# SOURCE TITLE: {title}
# SOURCE SECTIONS:
# {sections_block}

# RULES:
# - Output ONLY valid JSON, no markdown fences, no preamble.
# - Do NOT use unescaped double quotes inside string values.
# - Do NOT use literal linebreaks inside JSON strings.
# - Return exactly {n_sections} section objects in "sections".
# - Each section "paragraphs" must have 2-4 paragraphs (80-120 words each).
# - Include a "conclusion" object.

# JSON schema:
# {{
#   "title": "SEO title",
#   "meta_description": "145-158 chars",
#   "keywords": "kw1, kw2, kw3, kw4, kw5",
#   "category": "Category",
#   "intro": "article opener",
#   "feature_image_prompt": "hero scene 50 words",
#   "sections": [
#     {{"heading":"H2","paragraphs":["p1","p2"],"image_prompt":"scene","image_alt":"alt","snippet":"answer"}}
#   ],
#   "conclusion": {{"heading":"Wrap-up H2","paragraphs":["para1","para2"]}}
# }}
# """

# SEC_ONLY_PROMPT = """\
# {seo_skill}
# ---
# Rewrite these {n} sections from "{title}".
# Return ONLY: {{"sections": [ ... ]}}

# RULES:
# - Valid JSON only, no markdown, no preamble.
# - Exactly {n} section objects.

# Sections:
# {block}
# """

# def _build_sections_block(sections):
#     lines = []
#     for i, s in enumerate(sections):
#         lines.append(f"[{i+1}] HEADING: {s['heading']}")
#         body = s.get("body","").strip()
#         if body: lines.append(f"    BODY: {body[:CONFIG['chars_per_section']]}")
#         lines.append("")
#     return "\n".join(lines)

# def _rewrite_single_section(s, title, seo_skill):
#     prompt = (f"{seo_skill}\n---\nRewrite this section from \"{title}\" for SEO.\n"
#               f"HEADING: {s['heading']}\nBODY: {s.get('body','')[:1500]}\n\n"
#               f"Return ONLY valid JSON:\n"
#               f"{{\"heading\":\"{s['heading']}\","
#               f"\"paragraphs\":[\"Para 1\",\"Para 2\"],"
#               f"\"image_prompt\":\"scene\",\"image_alt\":\"alt\",\"snippet\":\"answer\"}}")
#     try:
#         raw = _run_agy(prompt, CONFIG["agy_timeout"])
#         parsed = _parse_json(raw)
#         if isinstance(parsed, dict):
#             if "heading" in parsed and "paragraphs" in parsed: return parsed
#             if "sections" in parsed and parsed["sections"]: return parsed["sections"][0]
#     except Exception: pass
#     return {"heading": s["heading"],
#             "paragraphs": [s.get("body","")[:600] or f"Guide to {s['heading']}."],
#             "image_prompt": s["heading"], "image_alt": s["heading"][:120],
#             "snippet": s.get("body","")[:200] or s["heading"]}

# def phase_transform(extracted, url, db, seo_skill):
#     ph("2", "TRANSFORM", "Full SEO rewrite — ALL sections, no cap")
#     cached = db_cached(db, url, "transform_v3")
#     if cached:
#         warn("Cached — skipping."); return json.loads(cached)

#     _check_agy()
#     title   = extracted["title"]
#     sections = extracted["sections"]   # ALL sections — no cap

#     BATCH   = CONFIG["batch_size"]
#     batches = [sections[i:i+BATCH] for i in range(0, len(sections), BATCH)]

#     inf(f"Processing [cyan]{len(sections)}[/] sections in [cyan]{len(batches)}[/] batches ...")

#     inf(f"agy call 1/{len(batches)} — first batch + meta ...")
#     with spin("agy rewriting ...") as p: p.add_task("", total=None)
#     try:
#         raw  = _run_agy(AGY_REWRITE_PROMPT.format(
#             seo_skill=seo_skill, n_sections=len(batches[0]),
#             title=title, sections_block=_build_sections_block(batches[0])),
#             CONFIG["agy_timeout"])
#         base = _parse_json(raw, len(batches[0]))
#     except Exception as e:
#         warn(f"First batch notice ({e}) — recovering ...")
#         base = {"title":title,"meta_description":f"Complete guide on {title}",
#                 "keywords":title,"category":"Guide","intro":f"Welcome to our guide on {title}.",
#                 "feature_image_prompt":title,"sections":[],"conclusion":None}
#         for s in batches[0]:
#             base["sections"].append(_rewrite_single_section(s, title, seo_skill))

#     all_sections = list(base.get("sections", []))

#     for bi, batch in enumerate(batches[1:], start=1):
#         inf(f"agy call {bi+1}/{len(batches)} — sections {bi*BATCH+1}-{min((bi+1)*BATCH,len(sections))} ...")
#         with spin("agy rewriting ...") as p: p.add_task("", total=None)
#         try:
#             raw = _run_agy(SEC_ONLY_PROMPT.format(
#                 seo_skill=seo_skill, n=len(batch), title=title,
#                 block=_build_sections_block(batch)), CONFIG["agy_timeout"])
#             fetched = _parse_json(raw, len(batch)).get("sections", [])
#             if not fetched: raise ValueError("No sections returned")
#             all_sections.extend(fetched)
#         except Exception as e:
#             warn(f"Batch {bi+1} notice ({e}) — rewriting individually ...")
#             for s in batch:
#                 all_sections.append(_rewrite_single_section(s, title, seo_skill))

#     conclusion = base.get("conclusion")
#     if not conclusion or not isinstance(conclusion, dict) or not conclusion.get("paragraphs"):
#         inf("Generating conclusion via dedicated agy call ...")
#         conclusion = _rewrite_conclusion(title, seo_skill)
#     ok(f"Conclusion: [cyan]{conclusion.get('heading','—')}[/]")

#     result = {
#         "title":                base.get("title", title),
#         "meta_description":     base.get("meta_description", ""),
#         "keywords":             base.get("keywords", ""),
#         "category":             base.get("category", "Article"),
#         "intro":                base.get("intro", ""),
#         "feature_image_prompt": base.get("feature_image_prompt", title),
#         "sections":             all_sections,
#         "conclusion":           conclusion,
#     }
#     ok(f"Title: [cyan]{result['title']}[/]")
#     ok(f"Sections total: [cyan]{len(all_sections)}[/]")
#     db_log(db, url, "transform_v3", "done", json.dumps(result))
#     return result

# # ─────────────────────────────────────────────────────────────
# # PHASE 3: AI IMAGES — quota raises QuotaExceededError,
# #           caller (run_one_url) catches it and calls quota_wait()
# # ─────────────────────────────────────────────────────────────
# AGY_BRAIN_ROOTS = [
#     Path.home() / ".gemini" / "antigravity-cli" / "brain",
#     Path.home() / ".antigravity" / "brain",
#     Path.home() / ".agy" / "brain",
# ]

# AGY_IMG_PROMPT_TEMPLATE = (
#     "Generate a photorealistic image and save it as {slug}.\n\n"
#     "Scene description:\n{scene}\n\n"
#     "Requirements: ultra-photorealistic, cinematic lighting, sharp focus, "
#     "professional photography quality, 16:9 landscape orientation, no text or watermarks."
# )

# _IMG_PATH_RE = re.compile(
#     r'(?:saved?(?:\s+(?:to|as|at))?|wrote?(?:\s+(?:to|file))?|output(?:\s+(?:file|path))?'
#     r'|created?|generated?|file(?:\s+path)?)\s*[:\-]?\s*'
#     r'([^\s\'"<>]+\.(?:png|jpg|jpeg|webp))'
#     r'|([^\s\'"<>]*\.(?:png|jpg|jpeg|webp))',
#     re.IGNORECASE,
# )

# _QUOTA_SIGNALS = [
#     "quota", "rate limit", "rate_limit", "resource exhausted",
#     "429", "too many requests", "limit exceeded", "billing",
#     "ResourceExhausted", "RESOURCE_EXHAUSTED", "quota exceeded",
#     "daily limit", "free tier", "upgrade",
# ]

# def _is_quota_error(text: str) -> bool:
#     lower = text.lower()
#     return any(sig.lower() in lower for sig in _QUOTA_SIGNALS)

# def _snapshot_brain() -> set:
#     found = set()
#     for root in AGY_BRAIN_ROOTS:
#         if root.exists():
#             for ext in ("png","jpg","jpeg","webp"):
#                 found.update(root.rglob(f"*.{ext}"))
#     return found

# def _find_new_image(before: set, raw_output: str) -> Path | None:
#     raw = _strip_ansi(raw_output)
#     for m in _IMG_PATH_RE.finditer(raw):
#         candidate = (m.group(1) or m.group(2) or "").strip().strip("'\".,;")
#         if candidate.startswith("/") or (len(candidate) > 2 and candidate[1] == ":"):
#             p = Path(candidate)
#             if p.exists() and p.stat().st_size > 1000:
#                 return p
#     after = _snapshot_brain()
#     new   = after - before
#     if new:
#         return max(new, key=lambda p: p.stat().st_size)
#     return None

# def _copy_image_to_dest(img_path: Path, dest: Path) -> bool:
#     try:
#         if img_path.stat().st_size < CONFIG["img_min_file_bytes"]:
#             warn(f"  Image too small ({img_path.stat().st_size}B) — rejecting")
#             return False
#         Image.open(img_path).convert("RGB").save(dest, "JPEG", quality=93, optimize=True)
#         return True
#     except Exception as e:
#         warn(f"  Image copy/validate failed: {e}")
#         return False

# def _generate_one_image(scene: str, slug: str, dest: Path, label: str,
#                          db, url: str) -> bool:
#     img_key = f"img:{slug}"

#     saved = db_img_done(db, url, img_key)
#     if saved and Path(saved).exists() and Path(saved).stat().st_size > CONFIG["img_min_file_bytes"]:
#         if Path(saved) != dest:
#             try: shutil.copy(saved, dest)
#             except Exception: pass
#         ok(f"  {label} [dim]resumed from cache[/]")
#         return True

#     before = _snapshot_brain()
#     prompt = AGY_IMG_PROMPT_TEMPLATE.format(slug=slug, scene=scene)

#     try:
#         raw = _run_agy(prompt, CONFIG["agy_img_timeout"])
#     except Exception as e:
#         warn(f"  agy error for {label}: {e} — using placeholder")
#         placeholder(dest, label, CONFIG["render_w"], CONFIG["render_h"])
#         return True

#     clean = _strip_ansi(raw)

#     if _is_quota_error(clean):
#         raise QuotaExceededError(
#             f"Imagen quota reached while generating: {label}"
#         )

#     img_path = _find_new_image(before, clean)
#     if img_path is None:
#         warn(f"  No image file found for {label} — using placeholder")
#         placeholder(dest, label, CONFIG["render_w"], CONFIG["render_h"])
#         return True

#     if _copy_image_to_dest(img_path, dest):
#         db_img_save(db, url, img_key, dest)
#         return True

#     warn(f"  Invalid image for {label} — using placeholder")
#     placeholder(dest, label, CONFIG["render_w"], CONFIG["render_h"])
#     return True


# def phase_images(structured: dict, url: str, db, out_dir: Path) -> dict:
#     ph("3", "AI IMAGES",
#        f"Sequential — 1 feature + all sections (unlimited) | quota=wait {CONFIG['quota_wait_hours']}h+resume")
#     _check_agy()

#     idir = out_dir / "images"; idir.mkdir(exist_ok=True)
#     sections    = structured.get("sections", [])
#     inter_delay = CONFIG["img_inter_delay"]
#     generated_count = 0

#     # ── Feature image ────────────────────────────────────────
#     feat_dest  = idir / "feature.jpg"
#     feat_scene = structured.get("feature_image_prompt", structured.get("title","hero"))
#     feat_key   = "img:feature_hero"

#     feat_cached = (db_img_done(db, url, feat_key) and
#                    feat_dest.exists() and
#                    feat_dest.stat().st_size > 20_000)

#     if feat_cached:
#         ok("Feature image [dim]resumed from cache[/]")
#     else:
#         inf(f"Feature image → [dim italic]{feat_scene[:80]}[/]")
#         # QuotaExceededError bubbles to run_one_url
#         _generate_one_image(feat_scene, "feature_hero", feat_dest, "Feature", db, url)
#         if feat_dest.exists() and feat_dest.stat().st_size > CONFIG["img_min_file_bytes"]:
#             ok(f"Feature image ✓ ({feat_dest.stat().st_size // 1024} KB)")
#             generated_count += 1
#             inf(f"  Waiting {inter_delay}s ...")
#             time.sleep(inter_delay)

#     # ── Per-section images (unlimited) ───────────────────────
#     sec_paths = []

#     with Progress(
#         SpinnerColumn(style="cyan"), TextColumn("[white]{task.description}"),
#         BarColumn(), TextColumn("[cyan]{task.completed}/{task.total}"),
#         TimeElapsedColumn(), console=console,
#     ) as prog:
#         t = prog.add_task("Section images", total=len(sections))

#         for i, sec in enumerate(sections):
#             dest = idir / f"sec_{i:02d}.jpg"
#             sec_paths.append(dest)

#             slug  = re.sub(r"[^a-z0-9]+","_",
#                            sec.get("heading",f"section_{i}").lower())[:40]
#             scene = (sec.get("image_prompt","").strip() or
#                      f"{sec.get('heading','')}. {' '.join(sec.get('paragraphs',['']))[:150]}")
#             label = f"Sec {i:02d}"

#             # QuotaExceededError bubbles up to run_one_url
#             _generate_one_image(scene, slug, dest, label, db, url)

#             if dest.exists() and dest.stat().st_size > CONFIG["img_min_file_bytes"]:
#                 ok(f"  {label} ✓ ({dest.stat().st_size // 1024} KB)")
#                 generated_count += 1

#             prog.advance(t)

#             if i < len(sections) - 1:
#                 inf(f"  Waiting {inter_delay}s ...")
#                 time.sleep(inter_delay)

#     inf(f"Images generated this run: [cyan]{generated_count}[/]")
#     return {"feature": feat_dest, "sections": sec_paths}

# # ─────────────────────────────────────────────────────────────
# # PHASE 4: RENDER
# # ─────────────────────────────────────────────────────────────
# _FONT_URLS = [
#     ("https://github.com/google/fonts/raw/main/ofl/montserrat/static/Montserrat-ExtraBold.ttf","Montserrat-ExtraBold.ttf"),
#     ("https://github.com/google/fonts/raw/main/ofl/inter/static/Inter-Bold.ttf","Inter-Bold.ttf"),
#     ("https://github.com/google/fonts/raw/main/ofl/oswald/static/Oswald-Bold.ttf","Oswald-Bold.ttf"),
# ]
# _FONT_TTF_CACHE: dict = {}

# def _dl_font(font_dir: Path) -> Path | None:
#     font_dir.mkdir(parents=True, exist_ok=True)
#     for url, fname in _FONT_URLS:
#         dest = font_dir / fname
#         if dest.exists(): return dest
#         try:
#             r = requests.get(url, timeout=25); r.raise_for_status()
#             dest.write_bytes(r.content); return dest
#         except Exception: continue
#     return None

# def _sys_font() -> str | None:
#     for p in ["C:/Windows/Fonts/arialbd.ttf","C:/Windows/Fonts/verdanab.ttf",
#               "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
#               "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
#               "/Library/Fonts/Arial Bold.ttf"]:
#         if Path(p).exists(): return p
#     return None

# def _ttf(size, font_path):
#     key = (str(font_path), size)
#     if key in _FONT_TTF_CACHE: return _FONT_TTF_CACHE[key]
#     font = None
#     for src in [font_path, _sys_font()]:
#         if src and Path(str(src)).exists():
#             try: font = ImageFont.truetype(str(src), size); break
#             except Exception: pass
#     if font is None: font = ImageFont.load_default()
#     _FONT_TTF_CACHE[key] = font; return font

# def _inspect(path):
#     img = Image.open(path); w, h = img.size
#     short = min(w,h)
#     dpi = "uhd" if short>=2160 else "fhd" if short>=1080 else "hd" if short>=720 else "sd"
#     return dict(w=w,h=h,dpi=dpi)

# def _wrap_px(heading, font, avail_w, max_lines, tmp_draw):
#     words = heading.split(); lines = []; cur = []
#     for word in words:
#         test = " ".join(cur+[word])
#         bb = tmp_draw.textbbox((0,0),test,font=font)
#         if (bb[2]-bb[0]) <= avail_w: cur.append(word)
#         else:
#             if not cur: cur=[word]
#             lines.append(" ".join(cur)); cur=[word]
#     if cur: lines.append(" ".join(cur))
#     return None if len(lines)>max_lines else "\n".join(lines)

# def _fit_text(heading, out_w, out_h, font_path, band_h, mx, my):
#     avail_w=out_w-2*mx; avail_h=band_h-2*my
#     start=max(18,min(out_w//14,avail_h//3,80))
#     tmp=ImageDraw.Draw(Image.new("RGBA",(4,4))); best=None
#     for size in range(start,11,-1):
#         font=_ttf(size,font_path); ls=max(4,int(size*0.22))
#         wrapped=_wrap_px(heading,font,avail_w,2,tmp)
#         if wrapped is None: continue
#         bb=tmp.multiline_textbbox((0,0),wrapped,font=font,spacing=ls)
#         if (bb[2]-bb[0])<=avail_w and (bb[3]-bb[1])<=avail_h:
#             best=(font,wrapped,size,ls,bb); break
#     if best is None:
#         size=12; font=_ttf(size,font_path); ls=4
#         wrapped=_wrap_px(heading,font,avail_w,4,tmp) or heading
#         bb=tmp.multiline_textbbox((0,0),wrapped,font=font,spacing=ls)
#         best=(font,wrapped,size,ls,bb)
#     return best

# def _render_image(bg_path, heading, out_path, out_w, out_h, font_path):
#     meta=_inspect(bg_path)
#     bg_full=Image.open(bg_path).convert("RGB"); sw,sh=bg_full.size
#     scale=max(out_w/sw,out_h/sh); nw,nh=int(sw*scale),int(sh*scale)
#     bg_full=bg_full.resize((nw,nh),Image.LANCZOS)
#     left=(nw-out_w)//2; top=(nh-out_h)//2
#     bg=bg_full.crop((left,top,left+out_w,top+out_h))
#     mx=int(out_w*0.05); my=int(out_h*0.04); band_h=int(out_h*0.40)
#     ov=Image.new("RGBA",(out_w,out_h),(0,0,0,0)); od=ImageDraw.Draw(ov)
#     for y in range(band_h):
#         a=int(252*(y/band_h)**0.50)
#         od.rectangle([(0,out_h-band_h+y),(out_w,out_h-band_h+y+1)],fill=(0,0,0,a))
#     canvas=Image.alpha_composite(bg.convert("RGBA"),ov)
#     font,wrapped,fsize,ls,bbox=_fit_text(heading,out_w,out_h,font_path,band_h,mx,my)
#     th=bbox[3]-bbox[1]; ty=(out_h-band_h)+(band_h-th)//2-my
#     ty=max(min(ty,out_h-th-my),out_h-band_h+my)
#     tl=Image.new("RGBA",(out_w,out_h),(0,0,0,0)); draw=ImageDraw.Draw(tl)
#     bh2=max(3,fsize//20); bw=int(out_w*0.10)
#     by=max(ty-bh2-int(fsize*0.30),out_h-band_h+my//2)
#     draw.rectangle([(mx,by),(mx+bw,by+bh2)],fill=(56,139,253,255))
#     sh2=max(2,fsize//18)
#     for dx,dy in [(-sh2,-sh2),(sh2,-sh2),(-sh2,sh2),(sh2,sh2),(0,sh2*2)]:
#         draw.multiline_text((mx+dx,ty+dy),wrapped,font=font,fill=(0,0,0,175),spacing=ls)
#     draw.multiline_text((mx,ty),wrapped,font=font,fill=(255,255,255,255),spacing=ls)
#     Image.alpha_composite(canvas,tl).convert("RGB").save(out_path,"JPEG",quality=93,optimize=True)
#     return dict(src=f"{meta['w']}×{meta['h']}",out=f"{out_w}×{out_h}",
#                 dpi=meta["dpi"].upper(),fs=fsize,ln=wrapped.count("\n")+1)

# def phase_render(structured, raw_paths, out_dir):
#     ph("4","RENDER","Compositing headings onto images")
#     rdir=out_dir/"rendered"; rdir.mkdir(exist_ok=True)
#     font_path=_dl_font(out_dir/"fonts")
#     if font_path: ok(f"Font: [cyan]{font_path.name}[/]")
#     else:
#         sp=_sys_font(); ok(f"Font: [cyan]{Path(sp).name if sp else 'Pillow default'}[/]")

#     feat_raw=raw_paths["feature"]; feat_out=rdir/"feature_rendered.jpg"
#     feat_rel=str(feat_out.relative_to(out_dir))
#     if not feat_out.exists():
#         try:
#             img=Image.open(feat_raw).convert("RGB"); w,h=img.size
#             scale=max(CONFIG["feature_w"]/w,CONFIG["feature_h"]/h)
#             nw,nh=int(w*scale),int(h*scale)
#             img=img.resize((nw,nh),Image.LANCZOS)
#             left=(nw-CONFIG["feature_w"])//2; top=(nh-CONFIG["feature_h"])//2
#             img.crop((left,top,left+CONFIG["feature_w"],top+CONFIG["feature_h"]))\
#                .save(feat_out,"JPEG",quality=93,optimize=True)
#             ok(f"Feature rendered: [cyan]{feat_out.name}[/]")
#         except Exception as e:
#             warn(f"Feature render failed: {e}"); shutil.copy(feat_raw,feat_out)
#     else:
#         ok("Feature [dim]cached[/]")

#     sections=structured.get("sections",[]); sec_raws=raw_paths["sections"]; sec_outs=[]
#     tbl=Table(box=box.SIMPLE_HEAD,border_style="dim",show_header=True,
#               header_style="bold magenta",padding=(0,1))
#     tbl.add_column("#",width=4,justify="right"); tbl.add_column("Heading",width=34,no_wrap=True)
#     tbl.add_column("Src",width=11,justify="center"); tbl.add_column("px",width=6,justify="right")
#     tbl.add_column("OK",width=5,justify="center")
#     rows=[]

#     with Progress(SpinnerColumn(style="magenta"),TextColumn("[white]{task.description}"),
#                   BarColumn(bar_width=28),TextColumn("[magenta]{task.completed}/{task.total}"),
#                   TimeElapsedColumn(),console=console) as prog:
#         t=prog.add_task("Compositing",total=len(sections))
#         for i,(sec,raw) in enumerate(zip(sections,sec_raws)):
#             heading=sec.get("heading",f"Section {i+1}")
#             out=rdir/f"sec_{i:02d}_rendered.jpg"; sec_outs.append(str(out))
#             if out.exists():
#                 rows.append((f"{i:02d}",heading[:33],"—","—","[dim]cache[/]"))
#                 prog.advance(t); continue
#             try:
#                 st=_render_image(raw,heading,out,CONFIG["render_w"],CONFIG["render_h"],font_path)
#                 rows.append((f"{i:02d}",heading[:33]+("…" if len(heading)>33 else ""),
#                              st["src"],f"[bold]{st['fs']}[/]","[green]✓[/]"))
#             except Exception as e:
#                 warn(f"Sec {i}: {e}"); shutil.copy(raw,out)
#                 rows.append((f"{i:02d}",heading[:33],"?","—","[red]✗[/]"))
#             prog.advance(t)

#     console.print()
#     for r in rows: tbl.add_row(*[str(c) for c in r])
#     console.print(tbl); console.print()
#     return {"feature": feat_rel, "sections": sec_outs}

# # ─────────────────────────────────────────────────────────────
# # PHASE 5: COMPILE
# # ─────────────────────────────────────────────────────────────
# def _estimate_read_time(structured):
#     words = sum(len(p.split()) for s in structured.get("sections",[]) for p in s.get("paragraphs",[]))
#     words += len(structured.get("intro","").split())
#     words += sum(len(p.split()) for p in (structured.get("conclusion") or {}).get("paragraphs",[]))
#     return max(1, round(words/200))

# def phase_compile(structured, rendered, out_dir):
#     ph("5","COMPILE","Building HTML with SEO meta + feature image + conclusion")
#     sections=structured.get("sections",[])
#     for i,s in enumerate(sections):
#         if i < len(rendered["sections"]):
#             rp=Path(rendered["sections"][i])
#             try: s["img"]=str(rp.relative_to(out_dir))
#             except ValueError: s["img"]=str(rp)
#         else: s["img"]=None
#     html=Template(HTML_TEMPLATE).render(
#         data=structured, feature_img=rendered["feature"],
#         generated_at=datetime.now().strftime("%d %b %Y, %H:%M"),
#         section_count=len(sections), read_time=_estimate_read_time(structured))
#     out=out_dir/"final_output.html"
#     out.write_text(html,encoding="utf-8")
#     ok(f"Saved → [cyan]{out}[/]")
#     return out

# # ─────────────────────────────────────────────────────────────
# # PLACEHOLDER
# # ─────────────────────────────────────────────────────────────
# def placeholder(dest, label, w, h):
#     img=Image.new("RGB",(w,h)); draw=ImageDraw.Draw(img)
#     for y in range(h):
#         t=y/h
#         draw.line([(0,y),(w,y)],fill=(int(15+t*35),int(20+t*40),int(70+t*55)))
#     font_size=max(48,w//18); font=None
#     for p in ["C:/Windows/Fonts/arialbd.ttf",
#               "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
#               "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"]:
#         try: font=ImageFont.truetype(p,font_size); break
#         except Exception: continue
#     if font is None: font=ImageFont.load_default()
#     lines=textwrap.fill(label[:80],width=22)
#     draw.text((w//2+3,h//2+3),lines,font=font,fill=(0,0,0,160),anchor="mm",align="center")
#     draw.text((w//2,h//2),lines,font=font,fill=(220,220,255),anchor="mm",align="center")
#     img.save(dest,"JPEG",quality=90)

# # ─────────────────────────────────────────────────────────────
# # ARTICLE SUMMARY (per-URL)
# # ─────────────────────────────────────────────────────────────
# def article_summary(url, structured, html_path, t0):
#     elapsed = time.time() - t0
#     console.print()
#     console.print(Rule("[bold green]Article Complete[/]", style="green"))
#     tbl=Table(box=box.ROUNDED,border_style="green",show_header=False,padding=(0,2))
#     tbl.add_column(style="dim",width=18); tbl.add_column(style="white")
#     tbl.add_row("URL", url)
#     tbl.add_row("Title", structured.get("title","—"))
#     tbl.add_row("Sections", str(len(structured.get("sections",[]))))
#     tbl.add_row("Conclusion", structured.get("conclusion",{}).get("heading","—")[:60])
#     tbl.add_row("Keywords", structured.get("keywords","—")[:60])
#     tbl.add_row("Read time", f"~{_estimate_read_time(structured)} min")
#     tbl.add_row("Output", str(html_path))
#     tbl.add_row("Time", f"{elapsed:.1f}s")
#     console.print(tbl); console.print()

# # ─────────────────────────────────────────────────────────────
# # RUN ONE URL  — wraps all phases, handles QuotaExceededError
# #               by waiting 6h and retrying the same URL
# # ─────────────────────────────────────────────────────────────
# def run_one_url(url: str, seo_skill: str, fresh: bool = False) -> bool:
#     """
#     Process a single URL end-to-end.
#     On quota hit: waits QUOTA_WAIT_SECONDS, then retries the same URL.
#     Returns True when the URL is fully done.
#     """
#     console.print()
#     console.print(Panel.fit(
#         f"[bold white]{url}[/]",
#         title="[bold cyan]Processing Article[/]",
#         border_style="cyan", padding=(0,4)))

#     out_dir = Path(CONFIG["output_dir"]) / hashlib.md5(url.encode()).hexdigest()[:8]
#     out_dir.mkdir(parents=True, exist_ok=True)

#     if fresh:
#         for sub in ("images","rendered"):
#             d = out_dir / sub
#             if d.exists(): shutil.rmtree(d); inf(f"  Cleared: {d}")

#     db = db_init(str(out_dir / CONFIG["db_path"]))

#     while True:   # retry loop — exits only when done or KeyboardInterrupt
#         t0 = time.time()
#         try:
#             extracted  = phase_extract(url, db)
#             structured = phase_transform(extracted, url, db, seo_skill)

#             try:
#                 raw_paths = phase_images(structured, url, db, out_dir)

#             except QuotaExceededError as qe:
#                 console.print()
#                 warn(str(qe))
#                 # Don't close DB — we'll resume
#                 quota_wait()       # blocks for 6 hours, then returns
#                 inf("Retrying image generation for this URL ...")
#                 continue           # retry the while loop (phases 1+2 are cached)

#             rendered  = phase_render(structured, raw_paths, out_dir)
#             html_path = phase_compile(structured, rendered, out_dir)
#             article_summary(url, structured, html_path, t0)
#             db.close()
#             return True            # ← success

#         except KeyboardInterrupt:
#             db.close()
#             raise                  # let main() handle Ctrl+C

#         except Exception as e:
#             err(f"Unexpected error on {url}: {e}")
#             warn("Skipping this URL and moving to next.")
#             db.close()
#             return False           # mark as failed but continue batch

# # ─────────────────────────────────────────────────────────────
# # BATCH SUMMARY
# # ─────────────────────────────────────────────────────────────
# def batch_summary(csv_path: Path, total: int, done: int, failed: int, elapsed: float):
#     console.print()
#     console.print(Rule("[bold green]Batch Complete[/]", style="green"))
#     tbl=Table(box=box.ROUNDED,border_style="green",show_header=False,padding=(0,2))
#     tbl.add_column(style="dim",width=18); tbl.add_column(style="white")
#     tbl.add_row("CSV", str(csv_path))
#     tbl.add_row("Total URLs", str(total))
#     tbl.add_row("Completed",  f"[green]{done}[/]")
#     tbl.add_row("Failed",     f"[red]{failed}[/]" if failed else "0")
#     tbl.add_row("Total time", f"{elapsed/3600:.2f}h  ({elapsed:.0f}s)")
#     console.print(tbl); console.print()

# # ─────────────────────────────────────────────────────────────
# # MAIN — 24/7 batch runner
# # ─────────────────────────────────────────────────────────────
# def main():
#     parser = argparse.ArgumentParser(description="Auto Content Pipeline — 24/7 Batch")
#     parser.add_argument("--csv",   default=None, help="Path to CSV file with URLs")
#     parser.add_argument("--fresh", action="store_true", help="Wipe cached images/renders")
#     args = parser.parse_args()

#     console.print()
#     console.print(Panel.fit(
#         "[bold white]AUTO CONTENT PIPELINE  —  24/7 BATCH MODE[/]\n"
#         "[dim]No section limit · CSV batch · Quota waits 6h then auto-resumes · Runs forever[/]",
#         border_style="bold blue", padding=(1,6)))
#     console.print()

#     _check_agy(); ok("agy found on PATH.")
#     if CONFIG["use_gpu"]: ok("GPU (CuPy) enabled.")
#     else: inf("CPU mode.")
#     console.print()

#     # ── Load SEO skill ───────────────────────────────────────
#     seo_skill = ensure_seo_skill(CONFIG["skills_dir"])
#     console.print()

#     # ── Get CSV path ─────────────────────────────────────────
#     csv_path_str = args.csv
#     if not csv_path_str:
#         csv_path_str = Prompt.ask(
#             "  [bold cyan]Path to your CSV file (one URL per line)[/]",
#             console=console)

#     csv_path = Path(csv_path_str.strip())
#     if not csv_path.exists():
#         err(f"CSV file not found: {csv_path}")
#         sys.exit(1)

#     all_rows = csv_load(csv_path)
#     total_urls = len(all_rows)
#     ok(f"CSV loaded: [cyan]{total_urls}[/] URLs found in [cyan]{csv_path}[/]")
#     console.print()

#     batch_start = time.time()
#     done_count = 0
#     fail_count = 0

#     try:
#         while True:
#             # Reload CSV each pass so we pick up any external edits
#             pending = csv_pending(csv_path)

#             if not pending:
#                 console.print()
#                 ok("[bold green]All URLs in the CSV are marked done! Pipeline complete.[/]")
#                 break

#             inf(f"[cyan]{len(pending)}[/] URLs remaining out of [cyan]{total_urls}[/]")
#             console.print()

#             url = pending[0]   # process next pending URL

#             success = run_one_url(url, seo_skill, fresh=args.fresh)

#             if success:
#                 csv_mark_done(csv_path, url)
#                 done_count += 1
#             else:
#                 # Mark as failed so we don't loop on it forever
#                 rows = csv_load(csv_path)
#                 for row in rows:
#                     if row["url"] == url:
#                         row["status"] = "failed"
#                 csv_save(csv_path, rows)
#                 warn(f"Marked as [red]failed[/] in CSV: {url}")
#                 fail_count += 1

#             console.print()
#             console.print(Rule(style="dim"))

#     except KeyboardInterrupt:
#         console.print("\n\n  [yellow]Interrupted by user.[/]")
#         console.print(f"  Progress is saved in the CSV. Run again to resume.\n")

#     elapsed = time.time() - batch_start
#     batch_summary(csv_path, total_urls, done_count, fail_count, elapsed)


# if __name__ == "__main__":
#     main()





#!/usr/bin/env python3
"""
Auto Content Pipeline — 24/7 Batch Mode
Features:
  - NO section limit — processes every section A to Z
  - CSV batch mode: reads URLs from a .csv file, marks each "done" when complete
  - Quota-safe: on Imagen quota hit, waits 6 hours then auto-resumes same URL
  - Runs forever until every URL in the CSV is marked done
  - FULL MID-RUN RESUME — if stopped at ANY point (Ctrl+C, crash, power loss):
      · Extract   → cached in SQLite after first run, always skipped on restart
      · Transform → each rewrite batch is checkpointed; restarts from last incomplete batch
      · Images    → every individual image is DB-tracked; already-done images are skipped
      · Render    → each rendered section file is checked on disk; already done = skip
      · Compile   → rebuilds HTML (fast, no API calls)
      · CSV       → only marks "done" after the full pipeline succeeds for that URL
  - Sequential image generation: one at a time
  - 100% dynamic & fault-tolerant JSON parsing + auto-retry
Usage:
  python automation.py                        # prompts for CSV path
  python automation.py --csv links.csv        # use specific CSV
  python automation.py --csv links.csv --fresh  # wipe caches and restart
CSV format (one URL per row, optional status column):
  https://example.com/article1
  https://example.com/article2,done          ← already done, will be skipped
"""

# ── PHASE 0: AUTO INSTALL ────────────────────────────────────
import subprocess, sys, importlib, shutil, os, time, csv

REQUIRED = {
    "rich":            "rich",
    "requests":        "requests",
    "lxml":            "lxml",
    "lxml_html_clean": "lxml_html_clean",
    "newspaper":       "newspaper4k",
    "jinja2":          "Jinja2",
    "PIL":             "Pillow",
    "cv2":             "opencv-python",
    "nltk":            "nltk",
    "bs4":             "beautifulsoup4",
}
OPTIONAL = {
    "cupy":                "cupy-cuda12x",
    "agy_headless_bridge": "agy-headless-bridge",
}

def _install(pkg, imp, optional=False):
    try:
        importlib.import_module(imp)
        return True
    except ImportError:
        print(f"  → Installing {pkg} ...")
        r = subprocess.run([sys.executable, "-m", "pip", "install", pkg, "-q"],
                           capture_output=True, text=True)
        if r.returncode != 0:
            if optional:
                print(f"  ⚠  {pkg} skipped (optional).")
                return False
            print(f"  ✗  Failed: {pkg}"); sys.exit(1)
        return True

print("\n📦 Installing dependencies ...\n")
for imp, pkg in REQUIRED.items():
    _install(pkg, imp)

GPU_OK = False
BRIDGE_OK = False
for imp, pkg in OPTIONAL.items():
    ok_ = _install(pkg, imp, optional=True)
    if imp == "cupy"                and ok_: GPU_OK    = True
    if imp == "agy_headless_bridge" and ok_: BRIDGE_OK = True

# ── LXML CLEAN COMPATIBILITY PATCH ───────────────────────────
try:
    import lxml_html_clean as _lxml_clean_mod
    import lxml.html as _lxml_html
    import types as _types
    _lxml_html.clean = _lxml_clean_mod
    sys.modules["lxml.html.clean"] = _lxml_clean_mod
    _lxml_clean_pkg = _types.ModuleType("lxml.clean")
    _lxml_clean_pkg.__dict__.update(vars(_lxml_clean_mod))
    sys.modules.setdefault("lxml.clean", _lxml_clean_pkg)
except ImportError:
    pass

try:
    import nltk
    for ds in ["punkt", "punkt_tab"]:
        try: nltk.data.find(f"tokenizers/{ds}")
        except LookupError: nltk.download(ds, quiet=True)
except Exception: pass

print("\n✅ Dependencies ready.\n")

# ── IMPORTS ──────────────────────────────────────────────────
import json, sqlite3, textwrap, hashlib, re, platform, argparse

if platform.system() != "Windows":
    import pty, select

from pathlib import Path
from datetime import datetime
from io import BytesIO

import requests
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, BarColumn, TextColumn, TimeElapsedColumn
from rich.prompt import Prompt
from rich.rule import Rule
from rich import box
from jinja2 import Template
from PIL import Image, ImageDraw, ImageFont
import cv2, numpy as np
from bs4 import BeautifulSoup

console = Console()

# ─────────────────────────────────────────────────────────────
# CONFIG  (max_sections removed — unlimited)
# ─────────────────────────────────────────────────────────────
CONFIG = {
    "output_dir":         "pipeline_output",
    "db_path":            "pipeline_state.db",
    "render_w":           1200,
    "render_h":           675,
    "feature_w":          1200,
    "feature_h":          630,
    "use_gpu":            GPU_OK,
    "agy_timeout":        180,
    "agy_img_timeout":    120,
    "skills_dir":         "Skills",
    "seo_skill_file":     "seo_skill.md",
    "chars_per_section":  2000,
    "batch_size":         3,
    # ── Quota wait ──────────────────────────────────────────
    "quota_wait_hours":   6,           # wait this long after quota hit
    # ── Image delays ────────────────────────────────────────
    "img_inter_delay":    8,           # seconds between successful image calls
    "img_min_file_bytes": 5000,
    # ── Image output format / resolution (overridden by CLI flags) ──
    "image_format":       "webp",      # "webp" | "jpeg"
    "image_quality":      88,
    "image_ext":          "webp",      # file extension matching image_format
    "image_pil_format":   "WEBP",      # PIL save() format matching image_format
    "resolution":         "hd",        # sd | hd | fhd | 2k
}

QUOTA_WAIT_SECONDS = CONFIG["quota_wait_hours"] * 3600

# ── Image format / resolution presets ─────────────────────────
IMAGE_FORMATS = {
    # name -> (PIL format, file extension)
    "webp": ("WEBP", "webp"),
    "jpeg": ("JPEG", "jpg"),
}

# Width per preset; section height derives from 16:9, feature height from
# the ~1.91:1 Open Graph ratio (matches the original 1200x675 / 1200x630 defaults).
RESOLUTION_PRESETS = {
    "sd":  854,
    "hd":  1200,
    "fhd": 1920,
    "2k":  2560,
}

# Custom resolution: "WIDTHxHEIGHT" (e.g. 1000x1000) — applied as-is to both
# the section and feature images (no derived aspect ratio, unlike the presets).
_CUSTOM_RES_RE = re.compile(r'^(\d{2,5})\s*[xX]\s*(\d{2,5})$')

def _resolution_arg(value: str) -> str:
    """argparse type= for --resolution: a preset name or a WIDTHxHEIGHT string."""
    v = value.strip()
    if v.lower() in RESOLUTION_PRESETS:
        return v.lower()
    m = _CUSTOM_RES_RE.match(v)
    if m:
        w, h = int(m.group(1)), int(m.group(2))
        if not (64 <= w <= 8000 and 64 <= h <= 8000):
            raise argparse.ArgumentTypeError(f"resolution out of range (64-8000): {v}")
        return f"{w}x{h}"
    raise argparse.ArgumentTypeError(
        f"invalid resolution '{value}' — use one of {list(RESOLUTION_PRESETS)} "
        f"or a custom WIDTHxHEIGHT like 1000x1000")

def _apply_image_settings(image_format: str, resolution: str):
    """Resolve the --image-format / --resolution CLI choices into CONFIG."""
    pil_format, ext = IMAGE_FORMATS[image_format]
    CONFIG["image_format"]     = image_format
    CONFIG["image_pil_format"] = pil_format
    CONFIG["image_ext"]        = ext

    m = _CUSTOM_RES_RE.match(resolution)
    if m:
        width, height = int(m.group(1)), int(m.group(2))
        CONFIG["resolution"] = f"{width}x{height}"
        CONFIG["render_w"]   = width
        CONFIG["render_h"]   = height
        CONFIG["feature_w"]  = width
        CONFIG["feature_h"]  = height
    else:
        width = RESOLUTION_PRESETS[resolution]
        CONFIG["resolution"] = resolution
        CONFIG["render_w"]   = width
        CONFIG["render_h"]   = round(width * 9 / 16)
        CONFIG["feature_w"]  = width
        CONFIG["feature_h"]  = round(width * 0.525)

def _save_image(img: "Image.Image", dest: "Path"):
    """Save a PIL image using the configured format/extension/quality."""
    save_kwargs = {"quality": CONFIG["image_quality"]}
    if CONFIG["image_pil_format"] == "JPEG":
        save_kwargs["optimize"] = True
    img.save(dest, CONFIG["image_pil_format"], **save_kwargs)

def _img_path(directory: "Path", stem: str) -> "Path":
    return directory / f"{stem}.{CONFIG['image_ext']}"

# ── QUOTA EXCEPTION ──────────────────────────────────────────
class QuotaExceededError(Exception):
    """Raised when Imagen quota is hit — pipeline waits then resumes."""
    pass

# ─────────────────────────────────────────────────────────────
# HTML TEMPLATE
# ─────────────────────────────────────────────────────────────
HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{{ data.title }}</title>
<meta name="description" content="{{ data.meta_description }}">
<meta name="keywords"    content="{{ data.keywords }}">
<meta property="og:title"       content="{{ data.title }}">
<meta property="og:description" content="{{ data.meta_description }}">
<meta property="og:image"       content="{{ feature_img }}">
<meta property="og:type"        content="article">
<meta name="twitter:card"        content="summary_large_image">
<meta name="twitter:title"       content="{{ data.title }}">
<meta name="twitter:description" content="{{ data.meta_description }}">
<meta name="twitter:image"       content="{{ feature_img }}">
<style>
@import url('https://fonts.googleapis.com/css2?family=Playfair+Display:wght@700;900&family=Inter:wght@400;500;600&display=swap');
*,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
:root{--ink:#0f0f0f;--bg:#f7f6f3;--accent:#2563eb;--rule:#e2e2e2;--muted:#555;--card:#fff}
body{background:var(--bg);color:var(--ink);font-family:'Inter',sans-serif;line-height:1.78}
.hero{position:relative;width:100%;max-height:630px;overflow:hidden;background:#111}
.hero img{display:block;width:100%;height:auto;opacity:.82;object-fit:cover}
.hero-overlay{position:absolute;inset:0;background:linear-gradient(to top,rgba(0,0,0,.72) 0%,rgba(0,0,0,.10) 60%,transparent 100%);display:flex;align-items:flex-end;padding:48px 40px}
.hero-inner{max-width:860px}
.hero-eyebrow{font-size:11px;letter-spacing:3px;text-transform:uppercase;color:var(--accent);font-weight:600;margin-bottom:14px}
.hero h1{font-family:'Playfair Display',Georgia,serif;font-size:clamp(1.9rem,4.5vw,3.2rem);line-height:1.15;color:#fff;max-width:760px}
.hero-meta{margin-top:18px;font-size:13px;color:#aaa}
main{max-width:960px;margin:0 auto;padding:64px 24px 100px}
.intro{font-size:1.15rem;line-height:1.85;color:#333;border-left:4px solid var(--accent);padding-left:20px;margin-bottom:64px;max-width:740px}
.sec{margin-bottom:80px}
.sec-num{font-size:11px;letter-spacing:2px;text-transform:uppercase;color:var(--accent);font-weight:600;margin-bottom:10px}
.sec h2{font-family:'Playfair Display',Georgia,serif;font-size:clamp(1.35rem,2.8vw,1.9rem);margin-bottom:18px;line-height:1.28}
.img-wrap{border-radius:10px;overflow:hidden;box-shadow:0 6px 32px rgba(0,0,0,.10);margin-bottom:22px}
.img-wrap img{display:block;width:100%;height:auto}
.sec-body p{font-size:1.04rem;color:#333;margin-bottom:14px;max-width:740px}
.sec-body p:last-child{margin-bottom:0}
.conclusion{background:linear-gradient(135deg,#1e3a5f 0%,#2563eb 100%);border-radius:16px;padding:48px 44px;margin-top:80px;margin-bottom:40px;color:#fff}
.conclusion h2{font-family:'Playfair Display',Georgia,serif;font-size:clamp(1.4rem,2.8vw,2rem);margin-bottom:20px;color:#fff}
.conclusion p{font-size:1.05rem;line-height:1.8;margin-bottom:14px;color:rgba(255,255,255,.90)}
.conclusion p:last-child{margin-bottom:0}
.conclusion-tag{display:inline-block;margin-top:24px;font-size:11px;letter-spacing:2px;text-transform:uppercase;color:rgba(255,255,255,.55);font-weight:600}
.div{display:flex;align-items:center;gap:16px;margin:64px 0}
.div-line{flex:1;height:1px;background:var(--rule)}
.div-dot{width:6px;height:6px;border-radius:50%;background:var(--accent);flex-shrink:0}
footer{text-align:center;padding:40px;font-size:12px;color:#aaa;border-top:1px solid var(--rule)}
@media(max-width:640px){.hero-overlay{padding:28px 18px}main{padding:40px 16px 72px}.conclusion{padding:32px 22px}}
</style>
</head>
<body>
<div class="hero">
  <img src="{{ feature_img }}" alt="{{ data.title }}" loading="eager">
  <div class="hero-overlay">
    <div class="hero-inner">
      <div class="hero-eyebrow">{{ data.category | default("Article") }}</div>
      <h1>{{ data.title }}</h1>
      <div class="hero-meta">{{ generated_at }} · {{ section_count }} sections · {{ read_time }} min read</div>
    </div>
  </div>
</div>
<main>
  {% if data.intro %}<p class="intro">{{ data.intro }}</p>{% endif %}
  {% for s in data.sections %}
  <div class="sec">
    <div class="sec-num">{{ "%02d"|format(loop.index) }} / {{ "%02d"|format(section_count) }}</div>
    {% if s.img %}<div class="img-wrap"><img src="{{ s.img }}" alt="{{ s.heading }}" loading="lazy"></div>{% endif %}
    <h2>{{ s.heading }}</h2>
    <div class="sec-body">
      {% for para in s.paragraphs %}<p>{{ para }}</p>{% endfor %}
    </div>
  </div>
  {% if not loop.last %}<div class="div"><div class="div-line"></div><div class="div-dot"></div><div class="div-line"></div></div>{% endif %}
  {% endfor %}
  {% if data.conclusion %}
  <div class="div"><div class="div-line"></div><div class="div-dot"></div><div class="div-line"></div></div>
  <div class="conclusion">
    <h2>{{ data.conclusion.heading }}</h2>
    {% for para in data.conclusion.paragraphs %}<p>{{ para }}</p>{% endfor %}
    <span class="conclusion-tag">End of Article</span>
  </div>
  {% endif %}
</main>
<footer>Auto Content Pipeline &middot; {{ generated_at }}</footer>
</body>
</html>"""

# ── DB ───────────────────────────────────────────────────────
def db_init(path):
    c = sqlite3.connect(path)
    # Main phase cache (extract, transform_v3 full result)
    c.execute("""CREATE TABLE IF NOT EXISTS runs
                 (id INTEGER PRIMARY KEY, url TEXT, phase TEXT,
                  status TEXT, data TEXT, ts TEXT DEFAULT CURRENT_TIMESTAMP)""")
    # Per-image checkpoint (image key → dest path)
    c.execute("""CREATE TABLE IF NOT EXISTS images_done
                 (id INTEGER PRIMARY KEY, url TEXT, img_key TEXT UNIQUE,
                  dest_path TEXT, ts TEXT DEFAULT CURRENT_TIMESTAMP)""")
    # Per-transform-batch checkpoint: stores each rewrite batch result separately
    # so a mid-transform crash doesn't throw away completed batches
    c.execute("""CREATE TABLE IF NOT EXISTS transform_batches
                 (id INTEGER PRIMARY KEY, url TEXT, batch_idx INTEGER,
                  data TEXT, ts TEXT DEFAULT CURRENT_TIMESTAMP,
                  UNIQUE(url, batch_idx))""")
    # Per-render-section checkpoint: tracks which section renders are on disk
    c.execute("""CREATE TABLE IF NOT EXISTS render_done
                 (id INTEGER PRIMARY KEY, url TEXT, sec_key TEXT UNIQUE,
                  out_path TEXT, ts TEXT DEFAULT CURRENT_TIMESTAMP)""")
    c.commit(); return c

# ── Transform batch checkpoints ──────────────────────────────
def db_batch_save(c, url: str, batch_idx: int, sections: list):
    c.execute(
        "INSERT OR REPLACE INTO transform_batches (url, batch_idx, data) VALUES (?,?,?)",
        (url, batch_idx, json.dumps(sections))); c.commit()

def db_batch_load(c, url: str, batch_idx: int):
    """Returns list of section dicts if this batch was already completed, else None."""
    row = c.execute(
        "SELECT data FROM transform_batches WHERE url=? AND batch_idx=?",
        (url, batch_idx)).fetchone()
    return json.loads(row[0]) if row else None

def db_batch_clear(c, url: str):
    """Wipe batch checkpoints after full transform is committed (cleanup)."""
    c.execute("DELETE FROM transform_batches WHERE url=?", (url,)); c.commit()

# ── Render section checkpoints ───────────────────────────────
def db_render_done(c, url: str, sec_key: str) -> str | None:
    row = c.execute(
        "SELECT out_path FROM render_done WHERE url=? AND sec_key=?",
        (url, sec_key)).fetchone()
    return row[0] if row else None

def db_render_save(c, url: str, sec_key: str, out_path: str):
    c.execute(
        "INSERT OR REPLACE INTO render_done (url, sec_key, out_path) VALUES (?,?,?)",
        (url, sec_key, out_path)); c.commit()

def db_log(c, url, phase, status, data=""):
    c.execute("INSERT INTO runs (url,phase,status,data) VALUES (?,?,?,?)",
              (url, phase, status, data)); c.commit()

def db_cached(c, url, phase):
    row = c.execute(
        "SELECT data FROM runs WHERE url=? AND phase=? AND status='done' ORDER BY id DESC LIMIT 1",
        (url, phase)).fetchone()
    return row[0] if row else None

def db_img_done(c, url, img_key):
    row = c.execute(
        "SELECT dest_path FROM images_done WHERE url=? AND img_key=?",
        (url, img_key)).fetchone()
    return row[0] if row else None

def db_img_save(c, url, img_key, dest_path):
    c.execute(
        "INSERT OR REPLACE INTO images_done (url, img_key, dest_path) VALUES (?,?,?)",
        (url, img_key, str(dest_path))); c.commit()

# ── UI helpers ───────────────────────────────────────────────
def ph(n, name, desc):
    console.print()
    console.print(Rule(f"[bold cyan]Phase {n}[/] [white]{name}[/] [dim]— {desc}[/]", style="cyan"))
    console.print()
def ok(m):   console.print(f"  [green]✓[/]  {m}")
def inf(m):  console.print(f"  [blue]→[/]  {m}")
def warn(m): console.print(f"  [yellow]⚠[/]  {m}")
def err(m):  console.print(f"  [red]✗[/]  {m}")
def spin(msg):
    return Progress(SpinnerColumn(style="cyan"), TextColumn(f"[white]{msg}[/]"),
                    TimeElapsedColumn(), console=console, transient=True)

# ─────────────────────────────────────────────────────────────
# CSV BATCH MANAGEMENT
# ─────────────────────────────────────────────────────────────

def csv_load(csv_path: Path) -> list[dict]:
    """
    Load URLs from CSV. Each row = {url, category, status}.
    Supports:
      - Single-column:  https://example.com/article
      - Two-column:     https://example.com/article, done          ← status only (legacy)
                     or  https://example.com/article, Technology    ← category only
      - Three-column:   https://example.com/article, Technology, done
    A 2nd column is treated as a status only when it's exactly "done"/"failed"
    (case-insensitive); otherwise it's treated as the category. This keeps old
    2-column "url,done" CSVs working unchanged.
    """
    rows = []
    with open(csv_path, newline="", encoding="utf-8") as f:
        for raw_row in csv.reader(f):
            if not raw_row:
                continue
            url = raw_row[0].strip()
            if not url or url.startswith("#"):
                continue  # skip blank lines and comments

            category, status = "", ""
            if len(raw_row) >= 3:
                category = raw_row[1].strip()
                status   = raw_row[2].strip().lower()
            elif len(raw_row) == 2:
                second = raw_row[1].strip()
                if second.lower() in ("done", "failed"):
                    status = second.lower()
                else:
                    category = second

            rows.append({"url": url, "category": category, "status": status})
    return rows


def csv_save(csv_path: Path, rows: list[dict]):
    """Write rows back to CSV, preserving order and column count."""
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        for row in rows:
            category = row.get("category", "")
            status   = row.get("status", "")
            if category and status:
                writer.writerow([row["url"], category, status])
            elif category:
                writer.writerow([row["url"], category])
            elif status:
                writer.writerow([row["url"], status])
            else:
                writer.writerow([row["url"]])


def csv_mark_done(csv_path: Path, url: str):
    """Mark a specific URL as done in the CSV file (category is preserved)."""
    rows = csv_load(csv_path)
    for row in rows:
        if row["url"] == url:
            row["status"] = "done"
    csv_save(csv_path, rows)
    ok(f"[dim]CSV updated → [cyan]{url}[/] marked [green]done[/]")


def csv_pending(csv_path: Path) -> list[dict]:
    """Return rows (url + category) not yet marked done."""
    return [r for r in csv_load(csv_path) if r["status"] != "done"]

# ─────────────────────────────────────────────────────────────
# QUOTA WAIT — 6-hour countdown, then continues
# ─────────────────────────────────────────────────────────────

def quota_wait():
    """Block for QUOTA_WAIT_SECONDS, printing a live countdown."""
    hours = CONFIG["quota_wait_hours"]
    console.print()
    console.print(Panel(
        f"[bold yellow]⚠  IMAGEN QUOTA REACHED[/]\n\n"
        f"  Waiting [bold cyan]{hours} hours[/] for quota to reset, then auto-resuming.\n"
        f"  Leave this terminal running — it will continue on its own.\n"
        f"  Press [bold]Ctrl+C[/] only if you want to stop completely.",
        title="[bold red]Quota Wait — Auto Resume in {hours}h[/]".format(hours=hours),
        border_style="yellow",
        padding=(1, 4),
    ))
    console.print()

    end_time = time.time() + QUOTA_WAIT_SECONDS
    while True:
        remaining = end_time - time.time()
        if remaining <= 0:
            break
        h = int(remaining // 3600)
        m = int((remaining % 3600) // 60)
        s = int(remaining % 60)
        console.print(f"  [dim]⏳ Quota resume in: [cyan]{h:02d}:{m:02d}:{s:02d}[/][/dim]",
                      end="\r")
        time.sleep(5)

    console.print()
    console.print()
    ok("[bold green]Quota wait complete — resuming pipeline![/]")
    console.print()

# ─────────────────────────────────────────────────────────────
# SEO SKILL
# ─────────────────────────────────────────────────────────────
SEO_SKILL_CONTENT = """\
# SEO Copywriting Skill v2.0
## Purpose
Rewrite web content for maximum on-page SEO while keeping it human, engaging, and accurate.

## Core Rules
1. **Title**: Keep primary keyword within first 60 chars. Use power words (Ultimate, Complete, Best, How to, Why).
2. **Meta Description**: 145-158 chars, include primary keyword, include a CTA or benefit.
3. **Headings (H2)**: Each H2 must contain a long-tail keyword variant.
4. **Paragraphs**: First sentence of each paragraph should contain a keyword. Aim 80-120 words per paragraph.
5. **Keyword Density**: Primary keyword ~1-1.5% of total text. LSI/semantic keywords distributed naturally.
6. **Readability**: Flesch reading ease > 60. Short sentences (avg < 20 words). Active voice.
7. **E-E-A-T signals**: Include specific facts, numbers, examples, and authoritative claims.
8. **Featured snippet optimization**: For each section, include one concise 40-60 word answer block.

## JSON Output Format
Return strictly valid JSON — no preamble, no markdown fences:
{
  "title": "...",
  "meta_description": "...",
  "keywords": "kw1, kw2, kw3",
  "category": "...",
  "intro": "2-3 sentence article intro with primary keyword",
  "feature_image_prompt": "vivid 50-word photorealistic scene, no text, cinematic lighting",
  "sections": [
    {
      "heading": "H2 with keyword",
      "paragraphs": ["paragraph 1 text", "paragraph 2 text"],
      "image_prompt": "vivid 50-word photorealistic scene for this section",
      "image_alt": "SEO alt text max 125 chars",
      "snippet": "40-60 word featured snippet answer"
    }
  ],
  "conclusion": {
    "heading": "Final Thoughts heading",
    "paragraphs": ["closing paragraph 1", "closing paragraph 2"]
  }
}

## Style
- Conversational but authoritative
- No fluff — every sentence earns its place
- Vary sentence length for rhythm
- End each section with a forward-looking sentence or micro-CTA
"""

def ensure_seo_skill(skills_dir: str) -> str:
    sdir = Path(skills_dir)
    sdir.mkdir(parents=True, exist_ok=True)
    skill_path = sdir / CONFIG["seo_skill_file"]
    if skill_path.exists():
        ok(f"SEO skill loaded from [cyan]{skill_path}[/]")
        return skill_path.read_text(encoding="utf-8")
    skill_path.write_text(SEO_SKILL_CONTENT, encoding="utf-8")
    ok(f"SEO skill created → [cyan]{skill_path}[/]")
    return SEO_SKILL_CONTENT

# ── AGY CORE ─────────────────────────────────────────────────
def _check_agy():
    if not shutil.which("agy"):
        err("agy not found. Install: curl -fsSL https://antigravity.google/cli/install.sh | bash")
        sys.exit(1)

def _strip_ansi(s):
    return re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])').sub("", s)

def _run_agy(prompt: str, timeout: int) -> str:
    if BRIDGE_OK:
        from agy_headless_bridge import run as agy_run
        result = agy_run(prompt, timeout=timeout)
        if hasattr(result, "__iter__") and not isinstance(result, str):
            return "".join(c if isinstance(c, str) else str(c) for c in result)
        return result or ""

    if platform.system() != "Windows":
        master, slave = pty.openpty()
        proc = subprocess.Popen(
            ["agy", "--dangerously-skip-permissions", "-p", prompt],
            stdin=slave, stdout=slave, stderr=slave)
        os.close(slave)
        chunks = []; deadline = time.time() + timeout
        while True:
            rem = deadline - time.time()
            if rem <= 0: proc.kill(); break
            r, _, _ = select.select([master], [], [], min(rem, 1.0))
            if r:
                try:
                    chunk = os.read(master, 4096)
                    if chunk: chunks.append(chunk.decode("utf-8", errors="replace"))
                    else: break
                except OSError: break
            elif proc.poll() is not None: break
        try: os.close(master)
        except OSError: pass
        proc.wait()
        return "".join(chunks)

    r = subprocess.run(["agy", "--dangerously-skip-permissions", "-p", prompt],
                       capture_output=True, text=True, timeout=timeout)
    return r.stdout or r.stderr

# ─────────────────────────────────────────────────────────────
# PHASE 1: EXTRACT
# ─────────────────────────────────────────────────────────────
def _extract_structured(url: str) -> dict:
    from newspaper import Article
    art = Article(url); art.download(); art.parse()
    title = art.title or "Untitled"
    raw_text = art.text or ""

    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    r = requests.get(url, timeout=30, headers=headers)
    soup = BeautifulSoup(r.text, "lxml")

    for tag in soup(["nav","footer","aside","script","style","noscript","header","form","button","svg"]):
        tag.decompose()

    sections = []
    current_heading = title
    current_body_parts = []

    content_area = (
        soup.find("article") or soup.find("main") or
        soup.find(class_=re.compile(r"content|post|entry|article", re.I)) or
        soup.body
    )
    if content_area is None:
        content_area = soup

    for el in content_area.find_all(["h1","h2","h3","h4","h5","h6","p","li","blockquote"], recursive=True):
        tag = el.name
        text = el.get_text(separator=" ", strip=True)
        if not text or len(text) < 5:
            continue
        if tag in ("h1","h2","h3","h4","h5","h6"):
            body = " ".join(current_body_parts).strip()
            if body or (sections and current_heading != title):
                sections.append({"heading": current_heading, "body": body})
            current_heading = text
            current_body_parts = []
        else:
            current_body_parts.append(text)

    body = " ".join(current_body_parts).strip()
    if body:
        sections.append({"heading": current_heading, "body": body})

    if sections and sections[0]["heading"].lower() == title.lower():
        sections = sections[1:]

    if not sections:
        paras = [p.strip() for p in raw_text.split("\n\n") if p.strip()]
        chunk_size = max(3, len(paras) // 5)
        for i in range(0, len(paras), chunk_size):
            sections.append({"heading": f"Part {len(sections)+1}",
                              "body": " ".join(paras[i:i+chunk_size])})

    inf(f"Detected [cyan]{len(sections)}[/] headings/sections from source")
    return {"title": title, "raw_text": raw_text, "sections": sections}

def phase_extract(url, db):
    ph("1", "EXTRACT", "Full structured scrape — title + ALL headings + body (no limit)")
    cached = db_cached(db, url, "extract_v2")
    if cached:
        warn("Cached — skipping."); return json.loads(cached)
    with spin("Downloading ...") as p: p.add_task("", total=None)
    try:
        data = _extract_structured(url)
    except Exception as e:
        err(f"Extract failed: {e}"); raise
    ok(f"Title: [cyan]{data['title']}[/]")
    ok(f"Sections: [cyan]{len(data['sections'])}[/]")
    ok(f"Total chars: [cyan]{len(data['raw_text']):,}[/]")
    db_log(db, url, "extract_v2", "done", json.dumps(data))
    return data

# ─────────────────────────────────────────────────────────────
# PHASE 2: TRANSFORM  (no section cap)
# ─────────────────────────────────────────────────────────────
def _clean_raw_llm_output(raw: str) -> str:
    raw = _strip_ansi(raw).strip()
    m = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', raw, re.IGNORECASE)
    if m: return m.group(1).strip()
    fb = raw.find('{'); fl = raw.find('[')
    if fb != -1 and (fl == -1 or fb < fl):
        lb = raw.rfind('}')
        return raw[fb:lb+1] if lb > fb else raw[fb:]
    elif fl != -1:
        ll = raw.rfind(']')
        return raw[fl:ll+1] if ll > fl else raw[fl:]
    return raw

def _fix_common_json_errors(s):
    return re.sub(r',\s*([}\]])', r'\1', s)

def _heal_truncated_json(s):
    s = s.rstrip().rstrip(",")
    in_str = False; esc = False; stack = []
    for ch in s:
        if esc: esc = False; continue
        if ch == '\\' and in_str: esc = True; continue
        if ch == '"': in_str = not in_str; continue
        if not in_str:
            if ch in ('{','['): stack.append(ch)
            elif ch in ('}',']'):
                if stack: stack.pop()
    if in_str: s += '"'
    s = s.rstrip().rstrip(",")
    for o in reversed(stack):
        s += {'{':'}','[':']'}[o]
    return s

def _extract_sections_regex(raw):
    sections = []
    blocks = re.findall(r'\{\s*"heading"\s*:\s*"[^"]+"[\s\S]*?\}(?=\s*,\s*\{|\s*\]|\s*$)', raw)
    for block in blocks:
        try:
            d = json.loads(_fix_common_json_errors(block), strict=False)
            if isinstance(d, dict) and "heading" in d:
                sections.append(d)
        except Exception: pass
    if not sections:
        for h in re.findall(r'"heading"\s*:\s*"([^"]+)"', raw):
            sections.append({"heading":h,"paragraphs":[f"Optimized content for {h}."],
                             "image_prompt":h,"image_alt":h[:120],"snippet":f"Guide on {h}."})
    return sections

def _parse_json(raw, expected_sections=0):
    clean = _clean_raw_llm_output(raw)
    for fn in [
        lambda s: json.loads(s, strict=False),
        lambda s: json.loads(_fix_common_json_errors(s), strict=False),
        lambda s: json.loads(_heal_truncated_json(s), strict=False),
        lambda s: json.loads(_heal_truncated_json(s[:s.rfind('}')+1]), strict=False),
    ]:
        try:
            d = fn(clean)
            if isinstance(d, dict): return d
            if isinstance(d, list): return {"sections": d}
        except Exception: continue
    secs = _extract_sections_regex(raw)
    if secs:
        warn(f"Extracted {len(secs)} section(s) via regex.")
        return {"sections": secs}
    raise ValueError(f"Could not parse JSON.\nRaw (first 1000 chars):\n{raw[:1000]}")

CONCLUSION_PROMPT = """\
{seo_skill}
---
Write a compelling conclusion section for the article "{title}".
{extra}

Return ONLY valid JSON (no markdown, no preamble):
{{
  "heading": "Engaging conclusion H2 with keyword",
  "paragraphs": [
    "Paragraph 1: synthesize key takeaways (80-120 words)",
    "Paragraph 2: forward-looking statement or call-to-action (60-100 words)"
  ]
}}
"""

def _rewrite_conclusion(title, seo_skill, extra=""):
    prompt = CONCLUSION_PROMPT.format(seo_skill=seo_skill, title=title, extra=extra)
    try:
        raw = _run_agy(prompt, CONFIG["agy_timeout"])
        parsed = _parse_json(raw)
        if isinstance(parsed, dict) and "heading" in parsed and "paragraphs" in parsed:
            return parsed
        if "sections" in parsed and parsed["sections"]:
            s = parsed["sections"][0]
            return {"heading": s.get("heading", f"Final Thoughts on {title}"),
                    "paragraphs": s.get("paragraphs",[])}
    except Exception as e:
        warn(f"Conclusion rewrite failed ({e}) — using fallback.")
    return {
        "heading": f"Final Thoughts on {title}",
        "paragraphs": [
            f"Throughout this article we explored the key dimensions of {title}, "
            "breaking down each area so you can apply these insights right away.",
            "Whether you are just starting out or looking to deepen your understanding, "
            "the concepts covered here provide a solid foundation. Bookmark this guide "
            "and revisit it as your knowledge grows.",
        ],
    }

AGY_REWRITE_PROMPT = """\
{seo_skill}
---
## YOUR TASK
Rewrite this article for SEO, preserving ALL {n_sections} sections.
Every section MUST appear in your output — do not merge or drop any.

SOURCE TITLE: {title}
SOURCE SECTIONS:
{sections_block}

RULES:
- Output ONLY valid JSON, no markdown fences, no preamble.
- Do NOT use unescaped double quotes inside string values.
- Do NOT use literal linebreaks inside JSON strings.
- Return exactly {n_sections} section objects in "sections".
- Each section "paragraphs" must have 2-4 paragraphs (80-120 words each).
- Include a "conclusion" object.

JSON schema:
{{
  "title": "SEO title",
  "meta_description": "145-158 chars",
  "keywords": "kw1, kw2, kw3, kw4, kw5",
  "category": "Category",
  "intro": "article opener",
  "feature_image_prompt": "hero scene 50 words",
  "sections": [
    {{"heading":"H2","paragraphs":["p1","p2"],"image_prompt":"scene","image_alt":"alt","snippet":"answer"}}
  ],
  "conclusion": {{"heading":"Wrap-up H2","paragraphs":["para1","para2"]}}
}}
"""

SEC_ONLY_PROMPT = """\
{seo_skill}
---
Rewrite these {n} sections from "{title}".
Return ONLY: {{"sections": [ ... ]}}

RULES:
- Valid JSON only, no markdown, no preamble.
- Exactly {n} section objects.

Sections:
{block}
"""

def _build_sections_block(sections):
    lines = []
    for i, s in enumerate(sections):
        lines.append(f"[{i+1}] HEADING: {s['heading']}")
        body = s.get("body","").strip()
        if body: lines.append(f"    BODY: {body[:CONFIG['chars_per_section']]}")
        lines.append("")
    return "\n".join(lines)

def _rewrite_single_section(s, title, seo_skill):
    prompt = (f"{seo_skill}\n---\nRewrite this section from \"{title}\" for SEO.\n"
              f"HEADING: {s['heading']}\nBODY: {s.get('body','')[:1500]}\n\n"
              f"Return ONLY valid JSON:\n"
              f"{{\"heading\":\"{s['heading']}\","
              f"\"paragraphs\":[\"Para 1\",\"Para 2\"],"
              f"\"image_prompt\":\"scene\",\"image_alt\":\"alt\",\"snippet\":\"answer\"}}")
    try:
        raw = _run_agy(prompt, CONFIG["agy_timeout"])
        parsed = _parse_json(raw)
        if isinstance(parsed, dict):
            if "heading" in parsed and "paragraphs" in parsed: return parsed
            if "sections" in parsed and parsed["sections"]: return parsed["sections"][0]
    except Exception: pass
    return {"heading": s["heading"],
            "paragraphs": [s.get("body","")[:600] or f"Guide to {s['heading']}."],
            "image_prompt": s["heading"], "image_alt": s["heading"][:120],
            "snippet": s.get("body","")[:200] or s["heading"]}

def phase_transform(extracted, url, db, seo_skill, category_override: str = ""):
    ph("2", "TRANSFORM", "Full SEO rewrite — ALL sections, no cap — per-batch checkpoint")

    # ── Full cache: entire transform was previously completed ────
    cached = db_cached(db, url, "transform_v3")
    if cached:
        warn("Cached — skipping.")
        result = json.loads(cached)
        if category_override and result.get("category") != category_override:
            result["category"] = category_override
            db_log(db, url, "transform_v3", "done", json.dumps(result))  # re-persist override
        return result

    _check_agy()
    title    = extracted["title"]
    sections = extracted["sections"]   # ALL sections — no cap

    BATCH   = CONFIG["batch_size"]
    batches = [sections[i:i+BATCH] for i in range(0, len(sections), BATCH)]

    inf(f"Processing [cyan]{len(sections)}[/] sections in [cyan]{len(batches)}[/] batches ...")

    # ── Batch 0: first batch + metadata ────────────────────────
    # Check if batch 0 was already completed in a previous (interrupted) run
    base_meta_cached = db_batch_load(db, url, -1)   # -1 = metadata slot
    batch0_cached    = db_batch_load(db, url, 0)

    if base_meta_cached and batch0_cached:
        warn("Batch 0 + metadata resumed from checkpoint.")
        base         = base_meta_cached
        all_sections = list(batch0_cached)
    else:
        inf(f"agy call 1/{len(batches)} — first batch + meta ...")
        with spin("agy rewriting ...") as p: p.add_task("", total=None)
        try:
            raw  = _run_agy(AGY_REWRITE_PROMPT.format(
                seo_skill=seo_skill, n_sections=len(batches[0]),
                title=title, sections_block=_build_sections_block(batches[0])),
                CONFIG["agy_timeout"])
            base = _parse_json(raw, len(batches[0]))
        except Exception as e:
            warn(f"First batch notice ({e}) — recovering ...")
            base = {"title":title,"meta_description":f"Complete guide on {title}",
                    "keywords":title,"category":"Guide","intro":f"Welcome to our guide on {title}.",
                    "feature_image_prompt":title,"sections":[],"conclusion":None}
            for s in batches[0]:
                base["sections"].append(_rewrite_single_section(s, title, seo_skill))

        # Save metadata (everything except sections list) and batch 0 separately
        meta_only = {k:v for k,v in base.items() if k != "sections"}
        db_batch_save(db, url, -1, meta_only)          # metadata checkpoint
        db_batch_save(db, url,  0, base.get("sections", []))  # batch 0 checkpoint
        all_sections = list(base.get("sections", []))

    # ── Batches 1..N ───────────────────────────────────────────
    for bi, batch in enumerate(batches[1:], start=1):
        # Check if this batch was already done in a previous interrupted run
        already = db_batch_load(db, url, bi)
        if already is not None:
            warn(f"  Batch {bi+1}/{len(batches)} resumed from checkpoint "
                 f"({len(already)} sections).")
            all_sections.extend(already)
            continue

        inf(f"agy call {bi+1}/{len(batches)} — sections {bi*BATCH+1}"
            f"-{min((bi+1)*BATCH,len(sections))} ...")
        with spin("agy rewriting ...") as p: p.add_task("", total=None)
        fetched = []
        try:
            raw = _run_agy(SEC_ONLY_PROMPT.format(
                seo_skill=seo_skill, n=len(batch), title=title,
                block=_build_sections_block(batch)), CONFIG["agy_timeout"])
            fetched = _parse_json(raw, len(batch)).get("sections", [])
            if not fetched: raise ValueError("No sections returned")
        except Exception as e:
            warn(f"Batch {bi+1} notice ({e}) — rewriting individually ...")
            for s in batch:
                fetched.append(_rewrite_single_section(s, title, seo_skill))

        db_batch_save(db, url, bi, fetched)   # ★ checkpoint this batch
        all_sections.extend(fetched)

    # ── Conclusion ─────────────────────────────────────────────
    # Reload meta from checkpoint (handles the case where base was loaded from cache)
    meta = db_batch_load(db, url, -1) or base
    conclusion = meta.get("conclusion") if isinstance(meta, dict) else None

    # Also check conclusion checkpoint (slot -2)
    conclusion_cached = db_batch_load(db, url, -2)
    if conclusion_cached:
        conclusion = conclusion_cached
        warn("Conclusion resumed from checkpoint.")
    elif not conclusion or not isinstance(conclusion, dict) or not conclusion.get("paragraphs"):
        inf("Generating conclusion via dedicated agy call ...")
        conclusion = _rewrite_conclusion(title, seo_skill)
        db_batch_save(db, url, -2, conclusion)   # ★ checkpoint conclusion

    ok(f"Conclusion: [cyan]{conclusion.get('heading','—')}[/]")

    result = {
        "title":                meta.get("title", title),
        "meta_description":     meta.get("meta_description", ""),
        "keywords":             meta.get("keywords", ""),
        "category":             category_override or meta.get("category", "Article"),
        "intro":                meta.get("intro", ""),
        "feature_image_prompt": meta.get("feature_image_prompt", title),
        "sections":             all_sections,
        "conclusion":           conclusion,
    }
    ok(f"Title: [cyan]{result['title']}[/]")
    ok(f"Sections total: [cyan]{len(all_sections)}[/]")

    # Commit full result and wipe per-batch checkpoints (no longer needed)
    db_log(db, url, "transform_v3", "done", json.dumps(result))
    db_batch_clear(db, url)
    return result

# ─────────────────────────────────────────────────────────────
# PHASE 3: AI IMAGES — quota raises QuotaExceededError,
#           caller (run_one_url) catches it and calls quota_wait()
# ─────────────────────────────────────────────────────────────
AGY_BRAIN_ROOTS = [
    Path.home() / ".gemini" / "antigravity-cli" / "brain",
    Path.home() / ".antigravity" / "brain",
    Path.home() / ".agy" / "brain",
]

AGY_IMG_PROMPT_TEMPLATE = (
    "Generate a photorealistic image and save it as {slug}.\n\n"
    "Scene description:\n{scene}\n\n"
    "Requirements: ultra-photorealistic, cinematic lighting, sharp focus, "
    "professional photography quality, 16:9 landscape orientation, no text or watermarks."
)

_IMG_PATH_RE = re.compile(
    r'(?:saved?(?:\s+(?:to|as|at))?|wrote?(?:\s+(?:to|file))?|output(?:\s+(?:file|path))?'
    r'|created?|generated?|file(?:\s+path)?)\s*[:\-]?\s*'
    r'([^\s\'"<>]+\.(?:png|jpg|jpeg|webp))'
    r'|([^\s\'"<>]*\.(?:png|jpg|jpeg|webp))',
    re.IGNORECASE,
)

_QUOTA_SIGNALS = [
    "quota", "rate limit", "rate_limit", "resource exhausted",
    "429", "too many requests", "limit exceeded", "billing",
    "ResourceExhausted", "RESOURCE_EXHAUSTED", "quota exceeded",
    "daily limit", "free tier", "upgrade",
]

def _is_quota_error(text: str) -> bool:
    lower = text.lower()
    return any(sig.lower() in lower for sig in _QUOTA_SIGNALS)

def _snapshot_brain() -> set:
    found = set()
    for root in AGY_BRAIN_ROOTS:
        if root.exists():
            for ext in ("png","jpg","jpeg","webp"):
                found.update(root.rglob(f"*.{ext}"))
    return found

def _find_new_image(before: set, raw_output: str) -> Path | None:
    raw = _strip_ansi(raw_output)
    for m in _IMG_PATH_RE.finditer(raw):
        candidate = (m.group(1) or m.group(2) or "").strip().strip("'\".,;")
        if candidate.startswith("/") or (len(candidate) > 2 and candidate[1] == ":"):
            p = Path(candidate)
            if p.exists() and p.stat().st_size > 1000:
                return p
    after = _snapshot_brain()
    new   = after - before
    if new:
        return max(new, key=lambda p: p.stat().st_size)
    return None

def _copy_image_to_dest(img_path: Path, dest: Path) -> bool:
    try:
        if img_path.stat().st_size < CONFIG["img_min_file_bytes"]:
            warn(f"  Image too small ({img_path.stat().st_size}B) — rejecting")
            return False
        _save_image(Image.open(img_path).convert("RGB"), dest)
        return True
    except Exception as e:
        warn(f"  Image copy/validate failed: {e}")
        return False

def _generate_one_image(scene: str, slug: str, dest: Path, label: str,
                         db, url: str) -> bool:
    img_key = f"img:{slug}"

    saved = db_img_done(db, url, img_key)
    if saved and Path(saved).exists() and Path(saved).stat().st_size > CONFIG["img_min_file_bytes"]:
        if Path(saved) != dest:
            try: shutil.copy(saved, dest)
            except Exception: pass
        ok(f"  {label} [dim]resumed from cache[/]")
        return True

    before = _snapshot_brain()
    prompt = AGY_IMG_PROMPT_TEMPLATE.format(slug=slug, scene=scene)

    try:
        raw = _run_agy(prompt, CONFIG["agy_img_timeout"])
    except Exception as e:
        warn(f"  agy error for {label}: {e} — using placeholder")
        placeholder(dest, label, CONFIG["render_w"], CONFIG["render_h"])
        return True

    clean = _strip_ansi(raw)

    if _is_quota_error(clean):
        raise QuotaExceededError(
            f"Imagen quota reached while generating: {label}"
        )

    img_path = _find_new_image(before, clean)
    if img_path is None:
        warn(f"  No image file found for {label} — using placeholder")
        placeholder(dest, label, CONFIG["render_w"], CONFIG["render_h"])
        return True

    if _copy_image_to_dest(img_path, dest):
        db_img_save(db, url, img_key, dest)
        return True

    warn(f"  Invalid image for {label} — using placeholder")
    placeholder(dest, label, CONFIG["render_w"], CONFIG["render_h"])
    return True


def phase_images(structured: dict, url: str, db, out_dir: Path) -> dict:
    ph("3", "AI IMAGES",
       f"Sequential — 1 feature + all sections (unlimited) | quota=wait {CONFIG['quota_wait_hours']}h+resume")
    _check_agy()

    idir = out_dir / "images"; idir.mkdir(exist_ok=True)
    sections    = structured.get("sections", [])
    inter_delay = CONFIG["img_inter_delay"]
    generated_count = 0

    # ── Feature image ────────────────────────────────────────
    feat_dest  = _img_path(idir, "feature")
    feat_scene = structured.get("feature_image_prompt", structured.get("title","hero"))
    feat_key   = "img:feature_hero"

    feat_cached = (db_img_done(db, url, feat_key) and
                   feat_dest.exists() and
                   feat_dest.stat().st_size > 20_000)

    if feat_cached:
        ok("Feature image [dim]resumed from cache[/]")
    else:
        inf(f"Feature image → [dim italic]{feat_scene[:80]}[/]")
        # QuotaExceededError bubbles to run_one_url
        _generate_one_image(feat_scene, "feature_hero", feat_dest, "Feature", db, url)
        if feat_dest.exists() and feat_dest.stat().st_size > CONFIG["img_min_file_bytes"]:
            ok(f"Feature image ✓ ({feat_dest.stat().st_size // 1024} KB)")
            generated_count += 1
            inf(f"  Waiting {inter_delay}s ...")
            time.sleep(inter_delay)

    # ── Per-section images (unlimited) ───────────────────────
    sec_paths = []

    with Progress(
        SpinnerColumn(style="cyan"), TextColumn("[white]{task.description}"),
        BarColumn(), TextColumn("[cyan]{task.completed}/{task.total}"),
        TimeElapsedColumn(), console=console,
    ) as prog:
        t = prog.add_task("Section images", total=len(sections))

        for i, sec in enumerate(sections):
            dest = _img_path(idir, f"sec_{i:02d}")
            sec_paths.append(dest)

            slug  = re.sub(r"[^a-z0-9]+","_",
                           sec.get("heading",f"section_{i}").lower())[:40]
            scene = (sec.get("image_prompt","").strip() or
                     f"{sec.get('heading','')}. {' '.join(sec.get('paragraphs',['']))[:150]}")
            label = f"Sec {i:02d}"

            # QuotaExceededError bubbles up to run_one_url
            _generate_one_image(scene, slug, dest, label, db, url)

            if dest.exists() and dest.stat().st_size > CONFIG["img_min_file_bytes"]:
                ok(f"  {label} ✓ ({dest.stat().st_size // 1024} KB)")
                generated_count += 1

            prog.advance(t)

            if i < len(sections) - 1:
                inf(f"  Waiting {inter_delay}s ...")
                time.sleep(inter_delay)

    inf(f"Images generated this run: [cyan]{generated_count}[/]")
    return {"feature": feat_dest, "sections": sec_paths}

# ─────────────────────────────────────────────────────────────
# PHASE 4: RENDER
# ─────────────────────────────────────────────────────────────
_FONT_URLS = [
    ("https://github.com/google/fonts/raw/main/ofl/montserrat/static/Montserrat-ExtraBold.ttf","Montserrat-ExtraBold.ttf"),
    ("https://github.com/google/fonts/raw/main/ofl/inter/static/Inter-Bold.ttf","Inter-Bold.ttf"),
    ("https://github.com/google/fonts/raw/main/ofl/oswald/static/Oswald-Bold.ttf","Oswald-Bold.ttf"),
]
_FONT_TTF_CACHE: dict = {}

def _dl_font(font_dir: Path) -> Path | None:
    font_dir.mkdir(parents=True, exist_ok=True)
    for url, fname in _FONT_URLS:
        dest = font_dir / fname
        if dest.exists(): return dest
        try:
            r = requests.get(url, timeout=25); r.raise_for_status()
            dest.write_bytes(r.content); return dest
        except Exception: continue
    return None

def _sys_font() -> str | None:
    for p in ["C:/Windows/Fonts/arialbd.ttf","C:/Windows/Fonts/verdanab.ttf",
              "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
              "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
              "/Library/Fonts/Arial Bold.ttf"]:
        if Path(p).exists(): return p
    return None

def _ttf(size, font_path):
    key = (str(font_path), size)
    if key in _FONT_TTF_CACHE: return _FONT_TTF_CACHE[key]
    font = None
    for src in [font_path, _sys_font()]:
        if src and Path(str(src)).exists():
            try: font = ImageFont.truetype(str(src), size); break
            except Exception: pass
    if font is None: font = ImageFont.load_default()
    _FONT_TTF_CACHE[key] = font; return font

def _inspect(path):
    img = Image.open(path); w, h = img.size
    short = min(w,h)
    dpi = "uhd" if short>=2160 else "fhd" if short>=1080 else "hd" if short>=720 else "sd"
    return dict(w=w,h=h,dpi=dpi)

def _wrap_px(heading, font, avail_w, max_lines, tmp_draw):
    words = heading.split(); lines = []; cur = []
    for word in words:
        test = " ".join(cur+[word])
        bb = tmp_draw.textbbox((0,0),test,font=font)
        if (bb[2]-bb[0]) <= avail_w: cur.append(word)
        else:
            if not cur: cur=[word]
            lines.append(" ".join(cur)); cur=[word]
    if cur: lines.append(" ".join(cur))
    return None if len(lines)>max_lines else "\n".join(lines)

def _fit_text(heading, out_w, out_h, font_path, band_h, mx, my):
    avail_w=out_w-2*mx; avail_h=band_h-2*my
    start=max(18,min(out_w//14,avail_h//3,80))
    tmp=ImageDraw.Draw(Image.new("RGBA",(4,4))); best=None
    for size in range(start,11,-1):
        font=_ttf(size,font_path); ls=max(4,int(size*0.22))
        wrapped=_wrap_px(heading,font,avail_w,2,tmp)
        if wrapped is None: continue
        bb=tmp.multiline_textbbox((0,0),wrapped,font=font,spacing=ls)
        if (bb[2]-bb[0])<=avail_w and (bb[3]-bb[1])<=avail_h:
            best=(font,wrapped,size,ls,bb); break
    if best is None:
        size=12; font=_ttf(size,font_path); ls=4
        wrapped=_wrap_px(heading,font,avail_w,4,tmp) or heading
        bb=tmp.multiline_textbbox((0,0),wrapped,font=font,spacing=ls)
        best=(font,wrapped,size,ls,bb)
    return best

def _render_image(bg_path, heading, out_path, out_w, out_h, font_path):
    meta=_inspect(bg_path)
    bg_full=Image.open(bg_path).convert("RGB"); sw,sh=bg_full.size
    scale=max(out_w/sw,out_h/sh); nw,nh=int(sw*scale),int(sh*scale)
    bg_full=bg_full.resize((nw,nh),Image.LANCZOS)
    left=(nw-out_w)//2; top=(nh-out_h)//2
    bg=bg_full.crop((left,top,left+out_w,top+out_h))
    mx=int(out_w*0.05); my=int(out_h*0.04); band_h=int(out_h*0.40)
    ov=Image.new("RGBA",(out_w,out_h),(0,0,0,0)); od=ImageDraw.Draw(ov)
    for y in range(band_h):
        a=int(252*(y/band_h)**0.50)
        od.rectangle([(0,out_h-band_h+y),(out_w,out_h-band_h+y+1)],fill=(0,0,0,a))
    canvas=Image.alpha_composite(bg.convert("RGBA"),ov)
    font,wrapped,fsize,ls,bbox=_fit_text(heading,out_w,out_h,font_path,band_h,mx,my)
    th=bbox[3]-bbox[1]; ty=(out_h-band_h)+(band_h-th)//2-my
    ty=max(min(ty,out_h-th-my),out_h-band_h+my)
    tl=Image.new("RGBA",(out_w,out_h),(0,0,0,0)); draw=ImageDraw.Draw(tl)
    bh2=max(3,fsize//20); bw=int(out_w*0.10)
    by=max(ty-bh2-int(fsize*0.30),out_h-band_h+my//2)
    draw.rectangle([(mx,by),(mx+bw,by+bh2)],fill=(56,139,253,255))
    sh2=max(2,fsize//18)
    for dx,dy in [(-sh2,-sh2),(sh2,-sh2),(-sh2,sh2),(sh2,sh2),(0,sh2*2)]:
        draw.multiline_text((mx+dx,ty+dy),wrapped,font=font,fill=(0,0,0,175),spacing=ls)
    draw.multiline_text((mx,ty),wrapped,font=font,fill=(255,255,255,255),spacing=ls)
    _save_image(Image.alpha_composite(canvas,tl).convert("RGB"), out_path)
    return dict(src=f"{meta['w']}×{meta['h']}",out=f"{out_w}×{out_h}",
                dpi=meta["dpi"].upper(),fs=fsize,ln=wrapped.count("\n")+1)

def phase_render(structured, raw_paths, out_dir, url, db):
    ph("4","RENDER","Compositing headings onto images — per-section checkpoint")
    rdir=out_dir/"rendered"; rdir.mkdir(exist_ok=True)
    font_path=_dl_font(out_dir/"fonts")
    if font_path: ok(f"Font: [cyan]{font_path.name}[/]")
    else:
        sp=_sys_font(); ok(f"Font: [cyan]{Path(sp).name if sp else 'Pillow default'}[/]")

    # ── Feature image ─────────────────────────────────────────
    feat_raw=raw_paths["feature"]; feat_out=_img_path(rdir, "feature_rendered")
    feat_rel=str(feat_out.relative_to(out_dir))

    feat_render_done = (
        db_render_done(db, url, "feature") and
        feat_out.exists() and
        feat_out.stat().st_size > 5000
    )
    if feat_render_done:
        ok("Feature render [dim]resumed from checkpoint[/]")
    else:
        if not feat_out.exists():
            try:
                img=Image.open(feat_raw).convert("RGB"); w,h=img.size
                scale=max(CONFIG["feature_w"]/w,CONFIG["feature_h"]/h)
                nw,nh=int(w*scale),int(h*scale)
                img=img.resize((nw,nh),Image.LANCZOS)
                left=(nw-CONFIG["feature_w"])//2; top=(nh-CONFIG["feature_h"])//2
                cropped = img.crop((left,top,left+CONFIG["feature_w"],top+CONFIG["feature_h"]))
                _save_image(cropped, feat_out)
                ok(f"Feature rendered: [cyan]{feat_out.name}[/]")
            except Exception as e:
                warn(f"Feature render failed: {e}"); shutil.copy(feat_raw,feat_out)
        else:
            ok("Feature [dim]file exists[/]")
        db_render_save(db, url, "feature", str(feat_out))  # ★ checkpoint

    # ── Section renders ───────────────────────────────────────
    sections=structured.get("sections",[]); sec_raws=raw_paths["sections"]; sec_outs=[]
    tbl=Table(box=box.SIMPLE_HEAD,border_style="dim",show_header=True,
              header_style="bold magenta",padding=(0,1))
    tbl.add_column("#",width=4,justify="right"); tbl.add_column("Heading",width=34,no_wrap=True)
    tbl.add_column("Src",width=11,justify="center"); tbl.add_column("px",width=6,justify="right")
    tbl.add_column("OK",width=5,justify="center")
    rows=[]

    with Progress(SpinnerColumn(style="magenta"),TextColumn("[white]{task.description}"),
                  BarColumn(bar_width=28),TextColumn("[magenta]{task.completed}/{task.total}"),
                  TimeElapsedColumn(),console=console) as prog:
        t=prog.add_task("Compositing",total=len(sections))
        for i,(sec,raw) in enumerate(zip(sections,sec_raws)):
            heading=sec.get("heading",f"Section {i+1}")
            out=_img_path(rdir, f"sec_{i:02d}_rendered"); sec_outs.append(str(out))
            sec_key = f"sec_{i:02d}"

            # ── Resume check: DB record + file on disk ────────
            render_cached = (
                db_render_done(db, url, sec_key) and
                out.exists() and
                out.stat().st_size > 2000
            )
            if render_cached:
                rows.append((f"{i:02d}",heading[:33],"—","—","[dim]resume[/]"))
                prog.advance(t); continue

            try:
                st=_render_image(raw,heading,out,CONFIG["render_w"],CONFIG["render_h"],font_path)
                db_render_save(db, url, sec_key, str(out))  # ★ checkpoint
                rows.append((f"{i:02d}",heading[:33]+("…" if len(heading)>33 else ""),
                             st["src"],f"[bold]{st['fs']}[/]","[green]✓[/]"))
            except Exception as e:
                warn(f"Sec {i}: {e}"); shutil.copy(raw,out)
                db_render_save(db, url, sec_key, str(out))  # checkpoint even fallback
                rows.append((f"{i:02d}",heading[:33],"?","—","[red]✗[/]"))
            prog.advance(t)

    console.print()
    for r in rows: tbl.add_row(*[str(c) for c in r])
    console.print(tbl); console.print()
    return {"feature": feat_rel, "sections": sec_outs}

# ─────────────────────────────────────────────────────────────
# PHASE 5: COMPILE
# ─────────────────────────────────────────────────────────────
def _estimate_read_time(structured):
    words = sum(len(p.split()) for s in structured.get("sections",[]) for p in s.get("paragraphs",[]))
    words += len(structured.get("intro","").split())
    words += sum(len(p.split()) for p in (structured.get("conclusion") or {}).get("paragraphs",[]))
    return max(1, round(words/200))

def phase_compile(structured, rendered, out_dir):
    ph("5","COMPILE","Building HTML with SEO meta + feature image + conclusion")
    sections=structured.get("sections",[])
    for i,s in enumerate(sections):
        if i < len(rendered["sections"]):
            rp=Path(rendered["sections"][i])
            try: s["img"]=str(rp.relative_to(out_dir))
            except ValueError: s["img"]=str(rp)
        else: s["img"]=None
    html=Template(HTML_TEMPLATE).render(
        data=structured, feature_img=rendered["feature"],
        generated_at=datetime.now().strftime("%d %b %Y, %H:%M"),
        section_count=len(sections), read_time=_estimate_read_time(structured))
    out=out_dir/"final_output.html"
    out.write_text(html,encoding="utf-8")
    ok(f"Saved → [cyan]{out}[/]")
    return out

# ─────────────────────────────────────────────────────────────
# PLACEHOLDER
# ─────────────────────────────────────────────────────────────
def placeholder(dest, label, w, h):
    img=Image.new("RGB",(w,h)); draw=ImageDraw.Draw(img)
    for y in range(h):
        t=y/h
        draw.line([(0,y),(w,y)],fill=(int(15+t*35),int(20+t*40),int(70+t*55)))
    font_size=max(48,w//18); font=None
    for p in ["C:/Windows/Fonts/arialbd.ttf",
              "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
              "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"]:
        try: font=ImageFont.truetype(p,font_size); break
        except Exception: continue
    if font is None: font=ImageFont.load_default()
    lines=textwrap.fill(label[:80],width=22)
    draw.text((w//2+3,h//2+3),lines,font=font,fill=(0,0,0,160),anchor="mm",align="center")
    draw.text((w//2,h//2),lines,font=font,fill=(220,220,255),anchor="mm",align="center")
    _save_image(img, dest)

# ─────────────────────────────────────────────────────────────
# ARTICLE SUMMARY (per-URL)
# ─────────────────────────────────────────────────────────────
def article_summary(url, structured, html_path, t0):
    elapsed = time.time() - t0
    console.print()
    console.print(Rule("[bold green]Article Complete[/]", style="green"))
    tbl=Table(box=box.ROUNDED,border_style="green",show_header=False,padding=(0,2))
    tbl.add_column(style="dim",width=18); tbl.add_column(style="white")
    tbl.add_row("URL", url)
    tbl.add_row("Title", structured.get("title","—"))
    tbl.add_row("Sections", str(len(structured.get("sections",[]))))
    tbl.add_row("Conclusion", structured.get("conclusion",{}).get("heading","—")[:60])
    tbl.add_row("Keywords", structured.get("keywords","—")[:60])
    tbl.add_row("Read time", f"~{_estimate_read_time(structured)} min")
    tbl.add_row("Output", str(html_path))
    tbl.add_row("Time", f"{elapsed:.1f}s")
    console.print(tbl); console.print()

# ─────────────────────────────────────────────────────────────
# RUN ONE URL  — wraps all phases, handles QuotaExceededError
#               by waiting 6h and retrying the same URL
# ─────────────────────────────────────────────────────────────
def run_one_url(url: str, seo_skill: str, fresh: bool = False, category: str = "") -> str:
    """
    Process a single URL end-to-end.
    - On quota hit   : waits 6 hours, retries the same URL automatically.
    - On Ctrl+C      : re-raises so the batch loop can exit cleanly.
    - On other crash : saves all checkpoints, returns "retry" so the batch
                       loop leaves the URL as pending and tries it again next
                       run (not marked failed — all progress is preserved).
    Returns: "done" | "retry" | "failed" (only "failed" skips permanently)
    """
    console.print()
    console.print(Panel.fit(
        f"[bold white]{url}[/]",
        title="[bold cyan]Processing Article[/]",
        border_style="cyan", padding=(0,4)))

    out_dir = Path(CONFIG["output_dir"]) / hashlib.md5(url.encode()).hexdigest()[:8]
    out_dir.mkdir(parents=True, exist_ok=True)

    if fresh:
        for sub in ("images","rendered"):
            d = out_dir / sub
            if d.exists(): shutil.rmtree(d); inf(f"  Cleared: {d}")

    db = db_init(str(out_dir / CONFIG["db_path"]))

    consecutive_failures = 0   # track repeated crashes on same URL

    while True:   # retry loop — exits only when done, user stops, or too many failures
        t0 = time.time()
        try:
            extracted  = phase_extract(url, db)
            structured = phase_transform(extracted, url, db, seo_skill, category_override=category)

            try:
                raw_paths = phase_images(structured, url, db, out_dir)

            except QuotaExceededError as qe:
                console.print()
                warn(str(qe))
                # All progress so far is safely checkpointed — just wait and retry
                quota_wait()       # blocks for 6 hours, then returns
                inf("Retrying image generation for this URL ...")
                continue           # phases 1+2 are fully cached, images resume from DB

            rendered  = phase_render(structured, raw_paths, out_dir, url, db)
            html_path = phase_compile(structured, rendered, out_dir)
            article_summary(url, structured, html_path, t0)
            db.close()
            return "done"          # ← success

        except KeyboardInterrupt:
            # All checkpoints are already saved — safe to stop
            console.print()
            inf("Interrupted — all progress saved. Restart to continue from this point.")
            db.close()
            raise                  # bubble up to main() batch loop

        except Exception as e:
            consecutive_failures += 1
            err(f"Error on {url} (attempt {consecutive_failures}): {e}")

            if consecutive_failures >= 3:
                # Something is structurally broken with this URL after 3 attempts
                err("3 consecutive failures — permanently skipping this URL.")
                db.close()
                return "failed"

            warn(f"All progress checkpointed. Retrying in 30s "
                 f"(attempt {consecutive_failures}/3) ...")
            time.sleep(30)
            # Loop again — every phase will resume from its checkpoint

# ─────────────────────────────────────────────────────────────
# BATCH SUMMARY
# ─────────────────────────────────────────────────────────────
def batch_summary(csv_path: Path, total: int, done: int, failed: int, elapsed: float):
    console.print()
    console.print(Rule("[bold green]Batch Complete[/]", style="green"))
    tbl=Table(box=box.ROUNDED,border_style="green",show_header=False,padding=(0,2))
    tbl.add_column(style="dim",width=18); tbl.add_column(style="white")
    tbl.add_row("CSV", str(csv_path))
    tbl.add_row("Total URLs", str(total))
    tbl.add_row("Completed",  f"[green]{done}[/]")
    tbl.add_row("Failed",     f"[red]{failed}[/]" if failed else "0")
    tbl.add_row("Total time", f"{elapsed/3600:.2f}h  ({elapsed:.0f}s)")
    console.print(tbl); console.print()

# ─────────────────────────────────────────────────────────────
# MAIN — 24/7 batch runner
# ─────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="Auto Content Pipeline — 24/7 Batch")
    parser.add_argument("--csv",   default=None, help="Path to CSV file with URLs")
    parser.add_argument("--fresh", action="store_true", help="Wipe cached images/renders")
    parser.add_argument("--image-format", choices=list(IMAGE_FORMATS), default="webp",
                        help="Output format for generated/rendered images (default: webp)")
    parser.add_argument("--resolution", type=_resolution_arg, default="hd",
                        help="Image resolution: a preset (sd=854w, hd=1200w, fhd=1920w, 2k=2560w) "
                             "or a custom WIDTHxHEIGHT, e.g. 1000x1000 (default: hd)")
    args = parser.parse_args()

    _apply_image_settings(args.image_format, args.resolution)

    console.print()
    console.print(Panel.fit(
        "[bold white]AUTO CONTENT PIPELINE  —  24/7 BATCH MODE[/]\n"
        "[dim]No section limit · CSV batch · Full mid-run resume · Quota waits 6h · Runs forever[/]",
        border_style="bold blue", padding=(1,6)))
    console.print()

    _check_agy(); ok("agy found on PATH.")
    if CONFIG["use_gpu"]: ok("GPU (CuPy) enabled.")
    else: inf("CPU mode.")
    ok(f"Images: [cyan]{CONFIG['image_format'].upper()}[/] @ "
       f"[cyan]{CONFIG['resolution']}[/] "
       f"(sections {CONFIG['render_w']}×{CONFIG['render_h']}, "
       f"feature {CONFIG['feature_w']}×{CONFIG['feature_h']})")
    console.print()

    # ── Load SEO skill ───────────────────────────────────────
    seo_skill = ensure_seo_skill(CONFIG["skills_dir"])
    console.print()

    # ── Get CSV path ─────────────────────────────────────────
    csv_path_str = args.csv
    if not csv_path_str:
        csv_path_str = Prompt.ask(
            "  [bold cyan]Path to your CSV file (one URL per line)[/]",
            console=console)

    csv_path = Path(csv_path_str.strip())
    if not csv_path.exists():
        err(f"CSV file not found: {csv_path}")
        sys.exit(1)

    all_rows = csv_load(csv_path)
    total_urls = len(all_rows)
    ok(f"CSV loaded: [cyan]{total_urls}[/] URLs found in [cyan]{csv_path}[/]")
    console.print()

    batch_start = time.time()
    done_count = 0
    fail_count = 0

    try:
        while True:
            # Reload CSV each pass so we pick up any external edits
            pending = csv_pending(csv_path)

            if not pending:
                console.print()
                ok("[bold green]All URLs in the CSV are marked done! Pipeline complete.[/]")
                break

            inf(f"[cyan]{len(pending)}[/] URLs remaining out of [cyan]{total_urls}[/]")
            console.print()

            row      = pending[0]   # process next pending row
            url      = row["url"]
            category = row["category"]
            if category:
                inf(f"CSV category → [cyan]{category}[/]")

            result = run_one_url(url, seo_skill, fresh=args.fresh, category=category)

            if result == "done":
                csv_mark_done(csv_path, url)
                done_count += 1

            elif result == "failed":
                # 3 consecutive crashes — mark failed so we skip and move on
                rows = csv_load(csv_path)
                for row in rows:
                    if row["url"] == url:
                        row["status"] = "failed"
                csv_save(csv_path, rows)
                warn(f"Marked as [red]failed[/] in CSV: {url}")
                fail_count += 1

            # result == "retry" → URL stays pending; next loop iteration picks it up
            # (this path is never actually reached right now because run_one_url
            #  internally retries, but the hook is here for future use)

            console.print()
            console.print(Rule(style="dim"))

    except KeyboardInterrupt:
        console.print("\n\n  [yellow]Interrupted by user.[/]")
        console.print(f"  Progress is saved in the CSV. Run again to resume.\n")

    elapsed = time.time() - batch_start
    batch_summary(csv_path, total_urls, done_count, fail_count, elapsed)


if __name__ == "__main__":
    main()