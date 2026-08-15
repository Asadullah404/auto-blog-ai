# Auto Content Pipeline — Complete Setup & Reference Guide

Extract an article from a URL → rewrite it for SEO → generate AI images → render
a finished page → publish it to WordPress with Rank Math SEO fields filled in.
Runs one URL at a time from a CSV, checkpoints every phase in SQLite so it can
be killed and resumed at any point, and can be packaged into a double-click
Windows installer.

This guide covers everything: one-time setup, the CSV format, every image/
resolution option, both ways to run it (GUI and command line), how auto-publish
and resume/idempotency work, and how to build a standalone `.exe` installer.

---

## Table of Contents

1. [How it works — the six phases](#1-how-it-works--the-six-phases)
2. [File manifest](#2-file-manifest)
3. [One-time setup (do this once)](#3-one-time-setup-do-this-once)
4. [The Control Panel (GUI)](#4-the-control-panel-gui)
5. [Running from the command line](#5-running-from-the-command-line)
6. [The CSV file — full format reference](#6-the-csv-file--full-format-reference)
7. [Image output — format, resolution & text overlay](#7-image-output--format-resolution--text-overlay)
8. [How auto-publish is controlled](#8-how-auto-publish-is-controlled)
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
| 3 | **Images** | `automation.py` | Generates one feature/hero image + one image per section (+ an optional Pinterest pin image) via `agy` (Imagen). Sequential, with an `img_inter_delay` pause between calls. Each image is DB-tracked individually — a retry skips images already done. On quota exhaustion it waits `quota_wait_hours` (default 6h) and resumes automatically. |
| 4 | **Render** | `automation.py` | Composites each section heading onto its image (gradient overlay + fitted text) using Pillow, at the configured resolution and format — independently for section images, the feature image, and the Pinterest pin. |
| 5 | **Compile** | `automation.py` | Builds the final standalone `final_output.html` (Jinja2 template, no server needed to preview it). |
| 6 | **Publish** | `wordpress_publisher.py` | Uploads images (with alt text) to WordPress, sets the featured image, rebuilds the post body as clean Gutenberg blocks, sets the category/tags, fills in Rank Math SEO fields, and publishes. Idempotent — a URL that's already published is skipped. |

`automation.py` runs all six phases in one pass: phases 1–5 always run, and
phase 6 fires automatically right after phase 5 for every article —
**gated entirely by the Live/Draft and AUTO switches** (see
[§8](#8-how-auto-publish-is-controlled)), no code edits required. You can
also run `wordpress_publisher.py` on its own at any time to publish
everything already generated (see [§10](#10-publishing-articles-you-already-generated)).

---

## 2. File manifest

| File | Where it lives | What it does |
|---|---|---|
| `automation.py` | project root | Phases 1–6 end to end. Also auto-installs its own Python dependencies (rich, requests, lxml, newspaper4k, Jinja2, Pillow, opencv, nltk, beautifulsoup4) the first time it runs. |
| `wordpress_publisher.py` | project root | Phase 6 in isolation. Imported by `automation.py` for the automatic publish step, and can also run standalone (`python wordpress_publisher.py`) to publish everything already generated. |
| `pipeline_gui.py` | project root | **The Control Panel.** A desktop app (CustomTkinter) with Dashboard / Settings / Logs / Articles tabs — start here if you don't want to touch the command line. |
| `rank-math-rest-meta.php` | your WordPress site, in `wp-content/mu-plugins/` | One-time unlocker so the WordPress REST API accepts Rank Math's SEO fields. Free Rank Math is fine. |
| `pipeline_config.json` | project root (git-ignored) | Written by the GUI (or by hand). Holds your WordPress credentials, Live/Draft + Auto switches, SEO plugin, per-image-type format/resolution/text-overlay settings, and CSV path. **Contains a live Application Password in plaintext — never commit or share this file.** |
| `.env` | project root (git-ignored) | Optional no-GUI alternative to `pipeline_config.json` — see [§3 Step 4](#step-4--enter-your-credentials). Also holds a live Application Password; also never commit or share it. |
| `Links.csv` (or any name, git-ignored) | wherever you keep it | Your list of URLs to process, one per line, with optional category/status columns. See [§6](#6-the-csv-file--full-format-reference). |
| `Skills/seo_skill.md` | auto-created | The SEO rewriting instructions given to `agy`. Auto-generated on first run if missing — edit it to change the writing style. |
| `pipeline_output/` | auto-created (git-ignored) | One subfolder per URL (named by an 8-char hash of the URL), each containing its own `pipeline_state.db`, `images/`, `rendered/`, and `final_output.html`. |
| `build.py` | project root | Packages everything into a double-click Windows installer. See [§11](#11-building-a-standalone-windows-installer). |
| `installer.py` | project root | Source for the installer itself — gets frozen into `Install ContentPipeline.exe` by `build.py`. You don't run this directly. |
| `.gitignore` | project root | Keeps credentials (`.env`, `pipeline_config.json`), your personal `Links.csv`, and generated `pipeline_output/` out of version control. |
| `README.md` | project root | This file. |

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
Neither file is ever committed to git — both are listed in `.gitignore`.

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
- **Publishing**: Live/Draft switch, Auto ON/OFF switch (see [§8](#8-how-auto-publish-is-controlled)),
  SEO plugin (Rank Math / None), image ALT text source (section heading / post title).
- **Images**: shared output format (WebP / JPEG), then three independent cards:
  - **Heading Images** — resolution + a checkbox for whether the section heading is pasted onto each section image.
  - **Feature Image** — its own resolution + a checkbox for whether the post title is pasted onto it.
  - **Pinterest Pin** — a toggle to also generate a tall pin image for the post, plus its own resolution.

  Every resolution picker accepts a preset or **Custom…** width/height. See [§7](#7-image-output--format-resolution--text-overlay).
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

### `automation.py` — full pipeline (phases 1–6)

```
python automation.py --csv Links.csv [options]
```

| Flag | Values | Default | Meaning |
|---|---|---|---|
| `--csv PATH` | any CSV path | prompts if omitted | The URL list to process |
| `--fresh` | flag | off | Wipe cached images/renders for this run (extract + rewrite text are still cached — only images/renders are cleared) |
| `--image-format` | `webp`, `jpeg` | `webp` | Output format for every generated/rendered image |
| `--resolution` | `sd`, `hd`, `fhd`, `2k`, or `WIDTHxHEIGHT` | `hd` | Section/heading image resolution — see [§7](#7-image-output--format-resolution--text-overlay) |
| `--feature-resolution` | same as above | same as `--resolution` | Feature/hero image resolution, set independently |
| `--pin-resolution` | same as above | `1000x1500` | Pinterest pin image resolution |
| `--feature-text` | flag | off | Paste the post title onto the feature image |
| `--no-heading-text` | flag | off (headings ON by default) | Do **not** paste section headings onto section images |
| `--pinterest-pin` | flag | off | Also render (and, on publish, upload) a tall Pinterest pin image |

It runs forever in a loop, pulling the next pending URL from the CSV until
every row is `done`, then exits. `Ctrl+C` stops it safely — all progress up
to that point is already checkpointed in SQLite; re-running resumes exactly
where it left off. After phases 1–5 finish for a given article, it publishes
automatically per your Live/Draft and AUTO settings ([§8](#8-how-auto-publish-is-controlled))
before moving to the next URL.

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

## 7. Image output — format, resolution & text overlay

Controlled by CLI flags (see [§5](#5-running-from-the-command-line)) or the
**Images** cards in Settings (GUI). Format is shared across all images; every
other setting — resolution and whether text is pasted on — is independent
**per image type**: section/heading images, the feature/hero image, and the
optional Pinterest pin.

### Format
| Value | File extension | Notes |
|---|---|---|
| `webp` (default) | `.webp` | Smaller files, same visual quality — recommended |
| `jpeg` | `.jpg` | Use if a target (theme, CDN, older tooling) doesn't handle WebP |

### Text overlay
- **Heading images** — the section heading is pasted onto each section image by default (gradient overlay + fitted text). Turn off with `--no-heading-text` or the GUI checkbox.
- **Feature image** — the post title is *not* pasted onto the feature image by default. Turn on with `--feature-text` or the GUI checkbox.

### Resolution presets
Section images use a 16:9 ratio; the feature/hero image uses roughly the
1.91:1 Open Graph ratio (what Facebook/Twitter/LinkedIn expect for link
previews); the Pinterest pin defaults to a tall 2:3 ratio — each derived from
a single width, and each configured independently:

| Preset | Section images | Feature image |
|---|---|---|
| `sd` | 854 × 480 | 854 × 448 |
| `hd` *(default)* | 1200 × 675 | 1200 × 630 |
| `fhd` | 1920 × 1080 | 1920 × 1008 |
| `2k` | 2560 × 1440 | 2560 × 1344 |

Pinterest pin defaults to `1000x1500` (custom, not a preset).

### Custom resolution
Pass `WIDTHxHEIGHT` instead of a preset name, e.g.:
```
python automation.py --csv Links.csv --resolution 1000x1000 --feature-resolution 1200x630
```
or in the GUI, pick **Custom…** in a resolution dropdown and type the
width/height into the two fields that appear. Unlike the presets, a custom
resolution is applied **exactly as given, with no derived aspect ratio**.
Valid range is 64–8000px per side; anything outside that (or a malformed
value) is rejected with a clear error before the pipeline starts.

### Pinterest pin
Enable with `--pinterest-pin` (CLI) or the **Pinterest Pin** card's toggle
(GUI). When on, a tall pin image with the post title is generated alongside
the feature and section images, rendered at its own resolution, and — on
publish — uploaded and attached to the post like the other images.

Where the files land:
```
pipeline_output/<hash>/images/feature.webp             ← raw AI feature image
pipeline_output/<hash>/images/sec_00.webp               ← raw AI section images
pipeline_output/<hash>/rendered/feature_rendered.webp   ← composited (used in the post)
pipeline_output/<hash>/rendered/sec_00_rendered.webp    ← composited (used in the post)
pipeline_output/<hash>/rendered/pin_rendered.webp       ← composited Pinterest pin (if enabled)
```

---

## 8. How auto-publish is controlled

Phase 6 (publish) runs automatically right after phase 5 for every article —
no manual code edit needed. What actually happens is controlled entirely by
two settings:

| Setting | GUI | `.env` | Effect |
|---|---|---|---|
| Live vs. Draft | Live/Draft switch | `WP_STATUS=publish` or `draft` | Whether the post goes live immediately or is saved for review |
| Auto ON/OFF | AUTO switch | `WP_AUTO_PUBLISH=true` or `false` | Whether phase 6 runs at all after each article. OFF = the pipeline only generates into `pipeline_output/`; publish later by hand |

With **AUTO on**, every article is published (Live or Draft, per the other
switch) the moment it finishes rendering — genuinely hands-off. With **AUTO
off**, `automation.py` stops after phase 5 and you publish everything that's
piled up with **⇪ Publish All Generated** (GUI) or `python wordpress_publisher.py`
(CLI) whenever you're ready — see [§10](#10-publishing-articles-you-already-generated).

A failed publish (bad credentials, WordPress unreachable, etc.) never loses
the generated article — it stays fully rendered in `pipeline_output/` and is
retried the next time you publish, without re-doing any earlier phase.

---

## 9. How resume / idempotency works

Everything is tracked in each article's own `pipeline_output/<hash>/pipeline_state.db`:

| Table | Tracks |
|---|---|
| `runs` | Extract + full Transform results, keyed by URL + phase |
| `transform_batches` | Each SEO-rewrite batch, so a mid-transform crash only re-does the unfinished batches |
| `images_done` | Every individual generated image (feature + each section + pin), keyed by image type and position so similarly-worded section headings never collide |
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
published (AUTO was off, or a publish attempt failed):

```
python wordpress_publisher.py --dry-run     # preview what would be published
python wordpress_publisher.py               # publish everything pending
```

or click **⇪ Publish All Generated** in the GUI. Already-published URLs are
skipped automatically (checked against `wp_published` in each article's DB)
*before* any expensive work runs, so re-running this often is always safe and cheap.

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
| AUTO switch is ON but nothing publishes during a run | Publishing failed for another reason (check the log for the actual error — usually credentials or connectivity) rather than the hook being missing; the article is still saved locally in `pipeline_output/` and will be retried next time you publish. |
| `agy not found` | Install the Antigravity CLI: `curl -fsSL https://antigravity.google/cli/install.sh \| bash`, and make sure it's on PATH. This is required whether you run from source or from a built `.exe`. |
| Pipeline seems stuck / repeatedly waits "quota reached" | Some Imagen quota/billing messages are detected generically — if `agy`'s output happens to contain words like "billing" or "upgrade" for unrelated reasons, it can be misread as a quota hit. Check the log for what `agy` actually printed. |
| Invalid `--resolution` error | Custom resolutions must be `WIDTHxHEIGHT` with both sides between 64 and 8000, e.g. `1000x1000`. Preset names are `sd`, `hd`, `fhd`, `2k`. |
| Category from the CSV isn't showing up on the post | Make sure the CSV row actually has a category column and the URL hasn't already been fully transformed with the old category cached — re-running the same URL re-applies the CSV category on top of the cache automatically, so just re-run it. |
| Built `.exe` won't start / Windows SmartScreen warning | Expected for an unsigned app — click **More info → Run anyway**. If it still won't launch, try running `ContentPipeline.exe` from a terminal (`cmd`) to see the actual error instead of a silent failure. |
| GUI's Start/Test/Publish buttons do nothing in the built app | `automation.exe` / `wordpress_publisher.exe` must be in the same folder as `ContentPipeline.exe`. Reinstall via `Install ContentPipeline.exe` rather than copying files individually. |
| `python build.py` fails partway with a missing-module error at runtime (not build time) | PyInstaller occasionally misses a package's non-Python data files. Note which import failed in the built exe's console output and re-run the build with an extra `--collect-all <package>` flag added to that entry's build step in `build.py`. |
| Blurry or clipped windows on the Control Panel | If Windows display scaling is set above 100%, make sure you're on the latest `pipeline_gui.py` — older copies could lay out wider than the window at fractional scaling. Re-download/pull if you hit this. |

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
(88) balancing size vs. visual fidelity.

**Where do I change how many sections get rewritten per `agy` call?**
`CONFIG["batch_size"]` in `automation.py` (default 3). Smaller batches
checkpoint more often (safer against crashes) but make more API calls.

**Is it safe to edit the CSV while the pipeline is running?**
Yes — it's reloaded before every URL, so you can add rows, add categories, or
fix a `failed` status back to pending mid-run.

**Can I generate articles without publishing anything, to review first?**
Yes — turn AUTO off (GUI switch or `WP_AUTO_PUBLISH=false`). The pipeline
still runs phases 1–5 and saves everything to `pipeline_output/`; nothing
reaches WordPress until you run `wordpress_publisher.py` or click
**Publish All Generated**.
