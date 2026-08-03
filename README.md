# Auto Content Pipeline — Complete Setup & Reference Guide

Extract an article from a URL → rewrite it for SEO → generate AI images → render
a finished page → publish it to WordPress with Rank Math SEO fields filled in.
Runs one URL at a time from a CSV, checkpoints every phase in SQLite so it can
be killed and resumed at any point, and can be packaged into a double-click
Windows installer.

This guide covers everything: one-time setup, the CSV format, every image/
resolution option, both ways to run it (GUI and command line), how resume
and idempotency work, and how to build a standalone `.exe` installer.

---

## Table of Contents

1. [How it works — the six phases](#1-how-it-works--the-six-phases)
2. [File manifest](#2-file-manifest)
3. [One-time setup (do this once)](#3-one-time-setup-do-this-once)
4. [The Control Panel (GUI)](#4-the-control-panel-gui)
5. [Running from the command line](#5-running-from-the-command-line)
6. [The CSV file — full format reference](#6-the-csv-file--full-format-reference)
7. [Image output — format & resolution](#7-image-output--format--resolution)
8. [Making AUTO-publish actually automatic (Step 5 hook)](#8-making-auto-publish-actually-automatic-step-5-hook)
9. [How resume / idempotency works](#9-how-resume--idempotency-works)
10. [Publishing articles you already generated](#10-publishing-articles-you-already-generated)
11. [Building a standalone Windows installer](#11-building-a-standalone-windows-installer)
12. [Troubleshooting](#12-troubleshooting)
13. [FAQ](#13-faq)

---

## 1. How it works — the six phases

| # | Phase | File | What happens |
|---|-------|------|---------------|
| 1 | **Extract** | `automation.py` | Downloads the URL, pulls the article text/title with `newspaper4k` + BeautifulSoup. Cached in SQLite so a re-run never re-downloads. |
| 2 | **Transform** | `automation.py` | Sends the article to the `agy` CLI (Antigravity) in batches of `batch_size` sections, using the SEO skill in `Skills/seo_skill.md` as instructions. Returns title, meta description, keywords, category, intro, per-section headings/paragraphs/image prompts, and a conclusion. Checkpointed **per batch**, so a crash mid-rewrite only re-does the unfinished batches. |
| 3 | **Images** | `automation.py` | Generates one feature/hero image + one image per section via `agy` (Imagen). Sequential, with an `img_inter_delay` pause between calls. Each image is DB-tracked individually — a retry skips images already done. On quota exhaustion it waits `quota_wait_hours` (default 6h) and resumes automatically. |
| 4 | **Render** | `automation.py` | Composites each section heading onto its image (gradient overlay + fitted text) using Pillow, at the configured resolution and format. Checkpointed per section. |
| 5 | **Compile** | `automation.py` | Builds the final standalone `final_output.html` (Jinja2 template, no server needed to preview it). |
| 6 | **Publish** | `wordpress_publisher.py` | Uploads images (with alt text) to WordPress, sets the featured image, rebuilds the post body as clean Gutenberg blocks, sets the category/tags, fills in Rank Math SEO fields, and publishes. Idempotent — a URL that's already published is skipped. |

Phases 1–5 always run as part of `automation.py`. Phase 6 is a **separate script**
(`wordpress_publisher.py`) that can run automatically after each article
(see [§8](#8-making-auto-publish-actually-automatic-step-5-hook)) or on demand
for everything already generated (see [§10](#10-publishing-articles-you-already-generated)).

---

## 2. File manifest

| File | Where it lives | What it does |
|---|---|---|
| `automation.py` | project root | Phases 1–5. The core pipeline. Also auto-installs its own Python dependencies (rich, requests, lxml, newspaper4k, Jinja2, Pillow, opencv, nltk, beautifulsoup4) the first time it runs. |
| `wordpress_publisher.py` | project root | Phase 6. Uploads + publishes to WordPress. Can also run standalone (`python wordpress_publisher.py`) to publish everything already generated. |
| `pipeline_gui.py` | project root | **The Control Panel.** A desktop app (CustomTkinter) with Dashboard / Settings / Logs / Articles tabs — start here if you don't want to touch the command line. |
| `rank-math-rest-meta.php` | your WordPress site, in `wp-content/mu-plugins/` | One-time unlocker so the WordPress REST API accepts Rank Math's SEO fields. Free Rank Math is fine. |
| `pipeline_config.json` | project root | Written by the GUI (or by hand). Holds your WordPress credentials, Live/Draft + Auto switches, SEO plugin, image format/resolution, and CSV path. **Contains a live Application Password in plaintext — treat it like a secret** (don't zip/share this file). |
| `Links.csv` (or any name) | wherever you keep it | Your list of URLs to process, one per line, with optional category/status columns. See [§6](#6-the-csv-file--full-format-reference). |
| `Skills/seo_skill.md` | auto-created | The SEO rewriting instructions given to `agy`. Auto-generated on first run if missing — edit it to change the writing style. |
| `pipeline_output/` | auto-created | One subfolder per URL (named by an 8-char hash of the URL), each containing its own `pipeline_state.db`, `images/`, `rendered/`, and `final_output.html`. |
| `build.py` | project root | Packages everything into a double-click Windows installer. See [§11](#11-building-a-standalone-windows-installer). |
| `installer.py` | project root | Source for the installer itself — gets frozen into `Install ContentPipeline.exe` by `build.py`. You don't run this directly. |
| `README_SETUP.md` | project root | This file. |

---

## 3. One-time setup (do this once)

### Step 1 — Install Rank Math (free) on your WordPress site
WP Admin → **Plugins** → **Add New** → search **"Rank Math SEO"** → Install → Activate.
The free version is all you need — no Pro required.

### Step 2 — Add the REST API unlocker file
WordPress hides custom SEO meta fields from the REST API by default; this small
must-use plugin opens them up so the pipeline can write Rank Math's title/
description/focus-keyword fields.

1. Open your site's files (hosting **File Manager** or FTP/SFTP).
2. Go to `wp-content/`.
3. If there's **no** folder named `mu-plugins`, create one — the name must be exactly `mu-plugins`.
4. Upload `rank-math-rest-meta.php` into `wp-content/mu-plugins/`.

"mu" means *must-use* — it activates itself, there's no Activate button and no
way to accidentally leave it disabled.

### Step 3 — Create a WordPress Application Password
This is a scoped, revocable credential just for the pipeline — never use your
real login password here.

1. WP Admin → **Users** → **Profile**.
2. Scroll to **Application Passwords**.
3. Type a name like `pipeline` → **Add New Application Password**.
4. Copy the password shown (format: `abcd EFGH ijkl MNOP qrst UVWX`). You only see it once — if you lose it, revoke it and generate a new one.

> If "Application Passwords" isn't visible, your site needs **HTTPS** and **WordPress 5.6+**.

### Step 4 — Enter your credentials
Easiest: open the **Control Panel** (`python pipeline_gui.py`) → Settings tab →
fill in Site URL / Username / Application Password → **Save Settings**. This
writes `pipeline_config.json`, which both `automation.py`'s publish step and
`wordpress_publisher.py` read.

Alternative (no GUI): create a `.env` file next to `automation.py`:

```
WP_URL=https://yoursite.com
WP_USER=your_wp_login_name
WP_APP_PASSWORD=abcd EFGH ijkl MNOP qrst UVWX
WP_STATUS=draft
```

(Keep the spaces in the application password exactly as shown. `.env` values
are loaded as defaults — `pipeline_config.json`, if present, overrides them.)

### Do ONE test run first (strongly recommended)
1. Set status to **Draft** (GUI: flip the Live/Draft switch to Draft; `.env`: `WP_STATUS=draft`).
2. Run the pipeline on a CSV with just **one** URL.
3. Open that post in the WordPress editor and check: feature image is set,
   section images show with alt text, Rank Math title/description/focus
   keyword boxes are filled, category matches what you expected.
4. If it looks right, flip to **Live** and run your full CSV.

---

## 4. The Control Panel (GUI)

```
python pipeline_gui.py
```

First run auto-installs `customtkinter` and `Pillow` if missing. The window
has a sidebar with four tabs:

### 🏠 Dashboard
- **▶ Start Pipeline / ■ Stop / ⇪ Publish All Generated** — the main controls.
- **Stat cards**: Total URLs, Pending, Completed, Failed (read live from your
  CSV), and Published (read live from every article's `pipeline_state.db`).
- **Batch Progress** bar — Completed ÷ Total from the CSV.
- **Latest Feature Image** — a live thumbnail of the most recently rendered
  feature image, so you can eyeball image quality without leaving the app.
- **Recent Activity** — a rolling colorized tail of the log (green = success,
  amber = warning, red = error, blue = info). "View Full Log →" jumps to the
  Logs tab.
- A pulsing dot + status text in the header shows Idle vs. Running.

### ⚙ Settings
- **WordPress Connection**: Site URL, username, Application Password, **Test
  Connection** button.
- **Publishing**: Live/Draft switch, Auto ON/OFF switch (see [§8](#8-making-auto-publish-actually-automatic-step-5-hook)
  for what Auto actually requires), SEO plugin (Rank Math / None), image ALT
  text source (section heading / post title).
- **Images**: output format (WebP / JPEG) and resolution — pick a preset or
  **Custom…** to type an exact WIDTH × HEIGHT. See [§7](#7-image-output--format--resolution).
- **Run**: CSV file picker, "Fresh run" checkbox (wipes cached images/renders
  for a clean re-generation without re-scraping or re-writing text).
- **💾 Save Settings** writes everything to `pipeline_config.json`.

### 📜 Logs
The full live output of whatever's running (pipeline / connection test /
publish-all), colorized, with **Clear** and **Export…** (save to a `.txt` file).

### 📰 Articles
Every article the pipeline has ever generated, pulled directly from each
article's own `pipeline_state.db` — title, category, source URL, a thumbnail,
and a **Published** / **Generated** status pill. Published articles get a
**🔗 View Post** button (opens the live WordPress post); generated ones get a
**📄 Local HTML** button (opens `final_output.html` in your browser). Filter
by typing in the search box; **🔄** refreshes.

All of this reads the *same* `pipeline_config.json` and `pipeline_output/`
that the command-line tools use — the GUI is a control surface, not a
separate system.

---

## 5. Running from the command line

### `automation.py` — phases 1–5

```
python automation.py --csv Links.csv [options]
```

| Flag | Values | Default | Meaning |
|---|---|---|---|
| `--csv PATH` | any CSV path | prompts if omitted | The URL list to process |
| `--fresh` | flag | off | Wipe cached images/renders for this run (extract + rewrite text are still cached — only images/renders are cleared) |
| `--image-format` | `webp`, `jpeg` | `webp` | Output format for every generated/rendered image |
| `--resolution` | `sd`, `hd`, `fhd`, `2k`, or `WIDTHxHEIGHT` | `hd` | See [§7](#7-image-output--format--resolution) |

It runs forever in a loop, pulling the next pending URL from the CSV until
every row is `done`, then exits. `Ctrl+C` stops it safely — all progress up
to that point is already checkpointed in SQLite; re-running resumes exactly
where it left off.

### `wordpress_publisher.py` — phase 6 (standalone)

```
python wordpress_publisher.py [options]
```

| Flag | Meaning |
|---|---|
| `--test` | Only verify the WordPress connection/credentials, then exit |
| `--dry-run` | List what *would* be published, without posting anything |
| `--root DIR` | Pipeline output folder to scan (default: `pipeline_output`) |

Credentials come from `pipeline_config.json` (if present) or `.env`/environment
variables (`WP_URL`, `WP_USER`, `WP_APP_PASSWORD`, `WP_STATUS`, `WP_SEO_PLUGIN`,
`WP_ALT_FROM`, `WP_AUTO_PUBLISH`, `WP_VERIFY_SSL`).

---

## 6. The CSV file — full format reference

One row per URL. Columns are comma-separated; extra whitespace is trimmed.
Blank lines and lines starting with `#` are skipped.

| Columns | Example | Meaning |
|---|---|---|
| 1 | `https://example.com/article` | URL only — no category assigned, not yet processed |
| 2 (status) | `https://example.com/article,done` | 2nd column is `done` or `failed` (case-insensitive) → treated as **status**, no category |
| 2 (category) | `https://example.com/article,Technology` | 2nd column is anything else → treated as **category** |
| 3 | `https://example.com/article,Technology,done` | category **and** status together |

**How the 2-column case is disambiguated:** if the second value is exactly
`done` or `failed` it's a status; otherwise it's treated as a category. This
means your old 2-column `url,done` CSVs keep working unchanged after
upgrading — no migration needed.

**What the category does:** if a row has a category, it's forced onto the
article's `category` field right after the SEO rewrite step — overriding
whatever category the AI would have picked on its own — and that override is
saved into the article's cache, so it's still correct even if you publish it
later with `wordpress_publisher.py` standalone. `wordpress_publisher.py`
creates that WordPress category if it doesn't already exist.

**Status values:**
- *(empty)* — pending, will be picked up next
- `done` — fully processed, permanently skipped on future runs
- `failed` — 3 consecutive crashes on this URL, permanently skipped (edit the
  CSV and clear the status to retry it)

The pipeline reloads the CSV before picking each URL, so you can add/edit
rows (including categories) while it's running.

Example file:
```
https://contabo.com/blog/what-is-a-gpu,done
https://blog.imaginationtech.com/imagination-chiplets,Semiconductors
https://example.com/some-ai-article,AI,done
https://example.com/uncategorized-article
```

---

## 7. Image output — format & resolution

Controlled by `--image-format` / `--resolution` (CLI) or the **Images** card
in Settings (GUI). Applies to every image the pipeline produces: the raw
AI-generated images, the composited "rendered" images (with the heading
overlay), and the feature/hero image.

### Format
| Value | File extension | Notes |
|---|---|---|
| `webp` (default) | `.webp` | Smaller files, same visual quality — recommended |
| `jpeg` | `.jpg` | Use if a target (theme, CDN, older tooling) doesn't handle WebP |

### Resolution presets
Section images use a 16:9 ratio; the feature/hero image uses roughly the
1.91:1 Open Graph ratio (what Facebook/Twitter/LinkedIn expect for link
previews) — both derived from a single width:

| Preset | Section images | Feature image |
|---|---|---|
| `sd` | 854 × 480 | 854 × 448 |
| `hd` *(default)* | 1200 × 675 | 1200 × 630 |
| `fhd` | 1920 × 1080 | 1920 × 1008 |
| `2k` | 2560 × 1440 | 2560 × 1344 |

### Custom resolution
Pass `WIDTHxHEIGHT` instead of a preset name, e.g.:
```
python automation.py --csv Links.csv --resolution 1000x1000
```
or in the GUI, pick **Custom…** in the Image resolution dropdown and type the
width/height into the two fields that appear. Unlike the presets, a custom
resolution is applied **exactly as given, with no derived aspect ratio** — a
`1000x1000` request produces square images for *both* the section and feature
images. Valid range is 64–8000px per side; anything outside that (or a
malformed value) is rejected with a clear error before the pipeline starts.

Where the files land:
```
pipeline_output/<hash>/images/feature.webp          ← raw AI feature image
pipeline_output/<hash>/images/sec_00.webp            ← raw AI section images
pipeline_output/<hash>/rendered/feature_rendered.webp  ← composited (used in the post)
pipeline_output/<hash>/rendered/sec_00_rendered.webp   ← composited (used in the post)
```

---

## 8. Making AUTO-publish actually automatic (Step 5 hook)

The GUI's **AUTO** switch and the `"auto_publish": true` setting describe
*intent* — they don't by themselves wire Phase 6 into the pipeline. You still
need to add one hook to `automation.py`, once:

**Find this** near the end of `run_one_url()` in `automation.py`:
```python
            rendered  = phase_render(structured, raw_paths, out_dir, url, db)
            html_path = phase_compile(structured, rendered, out_dir)
            article_summary(url, structured, html_path, t0)
            db.close()
            return "done"          # ← success
```

**Replace it with** (adds the highlighted lines):
```python
            rendered  = phase_render(structured, raw_paths, out_dir, url, db)
            html_path = phase_compile(structured, rendered, out_dir)
            article_summary(url, structured, html_path, t0)

            # ── PHASE 6: auto-publish to WordPress ──────────────
            try:
                from wordpress_publisher import phase_publish, PublishError
                phase_publish(structured, rendered, out_dir, url, db)
            except PublishError as e:
                warn(f"WordPress publish failed (article saved locally): {e}")

            db.close()
            return "done"          # ← success
```

Without this edit, `automation.py` only generates articles into
`pipeline_output/` — nothing reaches WordPress until you separately run
`python wordpress_publisher.py` or click **⇪ Publish All Generated** in the
GUI. This is intentional: it lets you review everything as drafts locally
before deciding to wire up true one-click automation.

---

## 9. How resume / idempotency works

Everything is tracked in each article's own `pipeline_output/<hash>/pipeline_state.db`:

| Table | Tracks |
|---|---|
| `runs` | Extract + full Transform results, keyed by URL + phase |
| `transform_batches` | Each SEO-rewrite batch, so a mid-transform crash only re-does the unfinished batches |
| `images_done` | Every individual generated image (feature + each section) |
| `render_done` | Every composited/rendered image on disk |
| `wp_published` | (added by `wordpress_publisher.py`) URL → WordPress post id/URL — a URL here is never posted twice |
| `wp_media` | (added by `wordpress_publisher.py`) local file → WordPress media id — a file here is never re-uploaded |

Practical implications:
- Killing the pipeline (Ctrl+C, closing the GUI, a crash) never loses work —
  re-running picks up from the last completed checkpoint for that URL.
- `--fresh` only clears the `images/` and `rendered/` folders for a URL — the
  extracted article and the SEO rewrite are still cached and are **not**
  re-fetched or re-written, so a fresh re-render is fast.
- Hitting Imagen's quota mid-run doesn't lose anything: the pipeline saves
  state, waits `quota_wait_hours` (default 6h) with a live countdown, then
  resumes the same URL automatically — no restart needed.
- 3 consecutive crashes on the *same* URL marks it `failed` in the CSV so the
  batch keeps moving instead of looping forever on one bad page; clear the
  status in the CSV to retry it later.

---

## 10. Publishing articles you already generated

If you have finished articles sitting in `pipeline_output/` that were never
published (or you're testing without the Step 5 hook):

```
python wordpress_publisher.py --dry-run     # preview what would be published
python wordpress_publisher.py               # publish everything pending
```

or click **⇪ Publish All Generated** in the GUI. Already-published URLs are
skipped automatically (checked against `wp_published` in each article's DB).

---

## 11. Building a standalone Windows installer

If you want to run this on a PC without a Python environment set up, or just
want a normal double-click app with a Desktop icon:

```
python build.py
```

**Windows only.** This:
1. Installs PyInstaller if it's missing.
2. Freezes `automation.py`, `wordpress_publisher.py`, and `pipeline_gui.py`
   into three standalone `.exe` files, plus copies `Skills/`, the Rank Math
   mu-plugin, and this README alongside them — all into
   `build_output/ContentPipeline/`.
3. Bundles that whole folder into one file: `build_output/Install ContentPipeline.exe`.

**That last file is what you (or anyone) double-clicks to install.** It:
- Copies the app to `%LOCALAPPDATA%\ContentPipeline`
- Creates a **Desktop shortcut** and a **Start Menu shortcut**
- Registers an entry in Windows **Settings → Apps** with a working uninstaller
- Offers to launch the app immediately after installing

Running it again later (a new build) offers to reinstall/update in place.

**What to expect:**
- The build bundles opencv, lxml, newspaper4k, and customtkinter, so it takes
  several minutes and produces a few hundred MB of output — that's normal
  given this project's dependencies, not a sign something's wrong.
- The installer is unsigned, so Windows SmartScreen / your antivirus may
  flag it on first run ("Windows protected your PC") — this is standard for
  any unsigned indie `.exe`; click **More info → Run anyway**. Getting a code
  signing certificate is the only way to remove this warning, and is
  unnecessary for personal/internal use.
- The `agy` CLI is **not** bundled — it's an external tool `automation.exe`
  shells out to, so it must still be installed separately on whatever
  machine runs the built app (same requirement as running from source).
- The three `.exe` files must stay together in the same folder — the GUI
  finds `automation.exe` and `wordpress_publisher.exe` by looking next to
  its own executable. The installer keeps them together automatically; if
  you copy the app manually, copy the whole folder.

To remove it later: **Settings → Apps → Content Pipeline → Uninstall**, or
run `Uninstall.bat` inside the install folder directly.

---

## 12. Troubleshooting

| Symptom | Fix |
|---|---|
| `401 Unauthorized` | Wrong username or Application Password. Re-check [Step 3/4](#step-3--create-a-wordpress-application-password). Use the *Application* Password, not your real login password. |
| Rank Math boxes are blank after publishing | The unlocker mu-plugin isn't in place. Confirm `rank-math-rest-meta.php` is in `wp-content/mu-plugins/` (exact folder name). The publisher also prints a warning when this happens. |
| `Cannot reach REST API` | Check `base_url` (needs `https://`, no trailing slash). Make sure the REST API isn't blocked by a security plugin/firewall. |
| Images missing in the post | The rendered images weren't found on disk — make sure Phase 4 (Render) fully finished before publishing. Check `pipeline_output/<hash>/rendered/`. |
| SSL error on a local/dev site | Local self-signed sites only: set `"verify_ssl": false` in `pipeline_config.json`. Leave it `true` for a real site. |
| AUTO switch is ON but nothing publishes during a run | The Step 5 hook isn't in `automation.py` yet — see [§8](#8-making-auto-publish-actually-automatic-step-5-hook). Until then, click **Publish All Generated** manually after a run. |
| `agy not found` | Install the Antigravity CLI: `curl -fsSL https://antigravity.google/cli/install.sh | bash`, and make sure it's on PATH. This is required whether you run from source or from a built `.exe`. |
| Pipeline seems stuck / repeatedly waits "quota reached" | Some Imagen quota/billing messages are detected generically — if `agy`'s output happens to contain words like "billing" or "upgrade" for unrelated reasons, it can be misread as a quota hit. Check the log for what `agy` actually printed. |
| Invalid `--resolution` error | Custom resolutions must be `WIDTHxHEIGHT` with both sides between 64 and 8000, e.g. `1000x1000`. Preset names are `sd`, `hd`, `fhd`, `2k`. |
| Category from the CSV isn't showing up on the post | Make sure the CSV row actually has a category column and the URL hasn't already been fully transformed with the old category cached — re-running the same URL re-applies the CSV category on top of the cache automatically, so just re-run it. |
| Built `.exe` won't start / Windows SmartScreen warning | Expected for an unsigned app — click **More info → Run anyway**. If it still won't launch, try running `ContentPipeline.exe` from a terminal (`cmd`) to see the actual error instead of a silent failure. |
| GUI's Start/Test/Publish buttons do nothing in the built app | `automation.exe` / `wordpress_publisher.exe` must be in the same folder as `ContentPipeline.exe`. Reinstall via `Install ContentPipeline.exe` rather than copying files individually. |
| `python build.py` fails partway with a missing-module error at runtime (not build time) | PyInstaller occasionally misses a package's non-Python data files. Note which import failed in the built exe's console output and re-run the build with an extra `--collect-all <package>` flag added to that entry's build step in `build.py`. |

---

## 13. FAQ

**Does re-running the pipeline ever create duplicate WordPress posts?**
No — `wordpress_publisher.py` checks `wp_published` in the article's own DB
before creating a post, and skips URLs already published there.

**Can I edit the SEO writing style?**
Yes — edit `Skills/seo_skill.md` after it's auto-created on first run. It's
plain Markdown instructions given to `agy` for every rewrite call.

**Can I change image quality?**
Not exposed as a flag currently — both WebP and JPEG save at a fixed quality
(88) balancing size vs. visual fidelity. Ask if you want this configurable too.

**Where do I change how many sections get rewritten per `agy` call?**
`CONFIG["batch_size"]` in `automation.py` (default 3). Smaller batches
checkpoint more often (safer against crashes) but make more API calls.

**Is it safe to edit the CSV while the pipeline is running?**
Yes — it's reloaded before every URL, so you can add rows, add categories, or
fix a `failed` status back to pending mid-run.
