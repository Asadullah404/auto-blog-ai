# Auto Content Pipeline — Complete Setup & Reference Guide

Extract an article from a URL → rewrite it for SEO **and GEO** (Generative
Engine Optimization — being citable by AI answer engines, not just ranking in
search) → generate AI images → render a finished page → publish it to
WordPress with Rank Math SEO fields filled in. Runs one URL at a time from a
CSV — which can be a plain local file or a **Google Drive share link that
multiple PCs work from together** without re-doing each other's articles —
checkpoints every phase in SQLite so it can be killed and resumed at any
point, never substitutes a blank placeholder image for a real one, and ships
as a ready-to-download Windows installer — no Python or command line required.

**📥 Download the app:** [github.com/Asadullah404/auto-blog-ai/releases/latest](https://github.com/Asadullah404/auto-blog-ai/releases/latest)
— grab `Install ContentPipeline.exe` under **Assets** and double-click it.
Full walkthrough in [§0](#0-quick-start--download-install--first-run-no-coding-required).

This guide covers everything, start to finish: downloading and installing the
app, one-time setup, the CSV format (including Google Drive multi-PC sync),
every image/resolution option, both ways to run it (desktop app and command
line), how auto-publish and resume/idempotency work, and how to build the
installer yourself from source.

---

## Table of Contents

0. [Quick Start — download, install & first run (no coding required)](#0-quick-start--download-install--first-run-no-coding-required)
1. [How it works — the six phases](#1-how-it-works--the-six-phases)
2. [File manifest](#2-file-manifest)
3. [One-time setup (do this once)](#3-one-time-setup-do-this-once)
4. [The Control Panel (GUI)](#4-the-control-panel-gui)
5. [Running from the command line](#5-running-from-the-command-line)
6. [The CSV file — full format reference (incl. Google Drive multi-PC sync)](#6-the-csv-file--full-format-reference)
7. [Image output — format, resolution & text overlay](#7-image-output--format-resolution--text-overlay)
8. [How auto-publish is controlled](#8-how-auto-publish-is-controlled)
9. [How resume / idempotency works](#9-how-resume--idempotency-works)
10. [Publishing articles you already generated](#10-publishing-articles-you-already-generated)
11. [Building a standalone Windows installer](#11-building-a-standalone-windows-installer)
12. [Troubleshooting](#12-troubleshooting)
13. [FAQ](#13-faq)

---

## 0. Quick Start — download, install & first run (no coding required)

This section is the complete A-to-Z for someone who just wants the finished
app running on their PC. It assumes **zero** prior setup — no Python, no
git, nothing. If you'd rather run from source or already have it installed,
skip to [§3](#3-one-time-setup-do-this-once).

**Requirements:** Windows 10 or 11 (64-bit). Nothing else needs to be
pre-installed — the app is self-contained.

### Step 1 — Download the installer
1. Open this link in your browser: **https://github.com/Asadullah404/auto-blog-ai/releases/latest**
2. Scroll to the **Assets** section of the release.
3. Click **`Install ContentPipeline.exe`** (~200 MB) to download it.
4. Wait for the download to finish — check your browser's download bar/folder.

### Step 2 — Run the installer
1. Open your **Downloads** folder and double-click **`Install ContentPipeline.exe`**.
2. Windows will very likely show a blue **"Windows protected your PC"**
   SmartScreen warning. This is expected — the app isn't code-signed (that
   costs money and isn't needed for a tool like this). To proceed:
   click **More info**, then click **Run anyway**.
3. A small window appears and does the following automatically (no
   "Next / Next / Finish" wizard — it just runs):
   - Copies the app to `%LOCALAPPDATA%\ContentPipeline`
   - Creates a **Desktop shortcut** named "Content Pipeline"
   - Creates a **Start Menu** entry
   - Registers the app in **Settings → Apps → Installed apps** with a
     working uninstaller
4. If a copy is already installed, it asks whether to reinstall/update in
   place — choose **Yes** to get the newest version.
5. At the end it asks **"Launch it now?"** — click **Yes** to open the
   Control Panel immediately, or click **No** and launch it later from the
   Desktop shortcut whenever you're ready.

If anything goes wrong here, see the *"Built `.exe` won't start"* and
*"GUI's Start/Test/Publish buttons do nothing"* rows in
[§12 Troubleshooting](#12-troubleshooting).

### Step 3 — Install the one external tool the app needs: `agy`
The installer bundles everything Python-related, but the actual AI text
rewriting and AI image generation is done by an external, free CLI tool
called **`agy`** (Antigravity CLI) — it is *not* bundled inside the `.exe`
because it's a separate program from Google, not a Python library. You only
need to do this once, and it works the same whether you're running the
installed app or the source code.

1. Open a terminal (press the Windows key, type `powershell`, hit Enter).
2. Run:
   ```
   curl -fsSL https://antigravity.google/cli/install.sh | bash
   ```
   (If plain PowerShell rejects `curl`/`bash` on your system, run this same
   command from **Git Bash** instead — install Git for Windows first if you
   don't have it, then reopen the command in Git Bash.)
3. Make sure the installer added `agy` to your PATH, then confirm it works
   by opening a **new** terminal window and typing:
   ```
   agy --version
   ```
   If that prints a version number, you're done. If it says "command not
   found", the install didn't finish or PATH wasn't updated — close and
   reopen your terminal (and the Content Pipeline app, if it was already
   open) and try again.
4. The first time `agy` actually runs, it will prompt you to sign in with a
   Google account in your browser — follow that prompt once; after that it
   stays signed in.

This app is **100% free to run**: `agy` uses your free Google Antigravity
quota for both the text rewriting and the Imagen image generation — no API
keys to buy, no credit card.

### Step 4 — One-time WordPress setup
Your generated articles get published to a WordPress site, so WordPress
needs a small one-time setup: installing the free Rank Math SEO plugin,
uploading one small unlocker file, and creating a scoped login credential
called an Application Password. This is a **one-time** step per WordPress
site — do the full walkthrough in [§3, Steps 1–3](#3-one-time-setup-do-this-once)
now, then come back here.

### Step 5 — Open the app and enter your settings
1. Launch **Content Pipeline** from the Desktop shortcut (or Start Menu).
2. Click the **⚙ Settings** tab in the sidebar.
3. Under **WordPress Connection**, fill in:
   - **Site URL** — e.g. `https://yoursite.com` (no trailing slash)
   - **Username** — your WordPress login username
   - **Application Password** — the one you generated in Step 4, exactly as
     shown (keep the spaces)
4. Click **Test Connection** — it should report success. If not, see
   [§12 Troubleshooting](#12-troubleshooting) (`401 Unauthorized`, `Cannot
   reach REST API`, etc.).
5. Under **Publishing**, for your very first run, set:
   - **Live/Draft** → **Draft** (so your first test post doesn't go live)
   - **Auto** → **ON** (so it publishes automatically after generating)
6. Leave **Images** settings on their defaults for now — you can fine-tune
   format/resolution/text overlay later (see [§7](#7-image-output--format-resolution--text-overlay)).
7. Click **💾 Save Settings**.

### Step 6 — Prepare your URL list
1. Create a plain text file named e.g. `Links.csv` (Notepad works fine —
   just save with a `.csv` extension) containing **one article URL per
   line**, for example:
   ```
   https://example.com/some-article-to-rewrite
   ```
   For the full format (adding categories, pre-marking rows as done, or
   sharing one list across multiple PCs via Google Drive), see
   [§6](#6-the-csv-file--full-format-reference). For your very first test,
   one line with one URL is enough.
2. Back in the app's **⚙ Settings** tab, under **Run**, use the file picker
   to select this CSV.
3. Click **💾 Save Settings** again.

### Step 7 — Run it
1. Go to the **🏠 Dashboard** tab.
2. Click **▶ Start Pipeline**.
3. Watch progress in real time:
   - The **status dot** in the header turns from Idle to Running.
   - **Recent Activity** streams what's happening (extracting → rewriting →
     generating images → rendering → publishing).
   - **Latest Feature Image** shows a live thumbnail as soon as the hero
     image is generated.
   - For the full unabridged log, switch to the **📜 Logs** tab.
4. When it finishes your one test URL, it stops automatically (it only
   loops while there are pending URLs left in the CSV).
5. Click the **📰 Articles** tab — you should see your article listed with
   a **Published** status pill and a **🔗 View Post** button. Click it to
   open the post on your WordPress site and check: feature image is set,
   section images look right, and (if you installed Rank Math per Step 4)
   the SEO title/description/focus-keyword boxes are filled in.

### Step 8 — Go live
Once a test article looks right:
1. Back in **⚙ Settings** → **Publishing**, flip **Live/Draft** to **Live**.
2. Click **💾 Save Settings**.
3. Add the rest of your real URLs to the CSV (one per line — you can add a
   category as a second column, see [§6](#6-the-csv-file--full-format-reference)).
4. Click **▶ Start Pipeline** again — it processes every pending row and
   publishes each one live as it finishes, fully unattended. You can close
   the app at any time with **■ Stop** (or just closing the window) — it
   always resumes exactly where it left off; nothing is lost. See
   [§9](#9-how-resume--idempotency-works).

### Updating later
When a new version is released, download the new `Install ContentPipeline.exe`
from the same [Releases page](https://github.com/Asadullah404/auto-blog-ai/releases/latest)
and run it — it detects the existing install and offers to update in place,
keeping your settings and generated articles.

### Uninstalling
**Settings → Apps → Content Pipeline → Uninstall**, or run `Uninstall.bat`
inside `%LOCALAPPDATA%\ContentPipeline` directly. This removes the app,
its shortcuts, and the Apps & Features entry (your `pipeline_output/`
generated articles live alongside it and are removed too — back up anything
you want to keep first).

---

## 1. How it works — the six phases

| # | Phase | File | What happens |
|---|-------|------|---------------|
| 1 | **Extract** | `automation.py` | Downloads the URL, pulls the article text/title with `newspaper4k` + BeautifulSoup. Cached in SQLite so a re-run never re-downloads. |
| 2 | **Transform** | `automation.py` | Sends the article to the `agy` CLI (Antigravity) in batches of `batch_size` sections, using the SEO **+ GEO** skill in `Skills/seo_skill.md` as instructions. Returns title, meta description, keywords, category, intro, per-section headings/paragraphs/image prompts, and a conclusion. Checkpointed **per batch**, so a crash mid-rewrite only re-does the unfinished batches. JSON parsing is self-healing (strips markdown fences, repairs trailing commas, closes truncated brackets/strings, escapes stray quotes inside prose) and falls back to rewriting sections one at a time if a batch still won't parse — it never loses content, it just does more calls. |
| 3 | **Images** | `automation.py` | Generates one feature/hero image + one image per section (+ an optional Pinterest pin image) via `agy` (Imagen). Sequential, with an `img_inter_delay` pause between calls. Each image is DB-tracked individually — a retry skips images already done. **Never substitutes a blank/grey placeholder for a real image**: a failed image is retried up to `img_max_retries` times (including a pixel-variance check that rejects flat/blank frames even if a file came back), and if it still can't produce a real photo, the whole run pauses (`quota_wait_hours`, default 6h) and automatically resumes generating that exact image — nothing fake ever ships. |
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
| `Links.csv` (or any name, git-ignored) | wherever you keep it | Your list of URLs to process, one per line, with optional category/status columns. Can instead be a Google Drive share link shared across multiple PCs. See [§6](#6-the-csv-file--full-format-reference). |
| `Skills/seo_skill.md` | auto-created | The SEO **+ GEO** rewriting instructions given to `agy`. Auto-generated on first run if missing — edit it to change the writing style. |
| `credentials.json` (git-ignored) | project root, you provide it | OAuth "Desktop app" client, downloaded from Google Cloud Console — only needed if you use a Google Drive CSV link. See [§6](#6-the-csv-file--full-format-reference). |
| `token.json` (git-ignored, auto-created) | project root | Your cached Google sign-in, created after the first browser login. Delete it to force signing in again (e.g. with a different Google account). |
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
- **▶ Start Pipeline / ■ Stop / ⏩ Resume Now / ⇪ Publish All Generated** — the main controls.
  **Resume Now** is only useful while a quota wait is in progress (see
  [§9](#9-how-resume--idempotency-works)) — it tells the pipeline to retry
  immediately instead of sitting out the rest of the wait. If quota's genuinely
  still exhausted it just picks the same countdown back up, so it's always
  safe to click. Clicking it while nothing is waiting on quota does nothing.
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
- **Run**: CSV file picker (**Browse**, or just paste a Google Drive share
  link directly into the field — see [§6](#6-the-csv-file--full-format-reference)
  for multi-PC syncing), "Fresh run" checkbox (wipes cached images/renders
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
| `--csv PATH` | local CSV path, or a Google Drive share link | prompts if omitted | The URL list to process — see [§6](#6-the-csv-file--full-format-reference) for the Drive-link, multi-PC case |
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
- `pending:<epoch>:<hostname>` — claimed by a specific PC the moment it
  started that URL (see **Google Drive sync** below). Written automatically;
  you never type this by hand.

The pipeline reloads the CSV before picking each URL, so you can add/edit
rows (including categories) while it's running.

### Google Drive sync — running the same list from multiple PCs

Pass a **Google Drive share link** as `--csv` (CLI) or paste it straight into
the CSV field in the GUI, instead of a local file path:

```
python automation.py --csv "https://drive.google.com/file/d/1AbCDefGhIJKlmnOP/view?usp=sharing"
```

Every machine pointed at the same link works off one shared list:
- Before picking a URL, it downloads the latest copy from Drive — so it sees
  claims and completions any other PC has already made.
- The instant it picks a URL, it writes `pending:<unix-timestamp>:<hostname>`
  into that row and uploads the change immediately — announcing "I'm working
  this" before any real work starts, so a second PC reading the same file a
  moment later skips it.
- If a PC crashes or is closed mid-article, its `pending` claim is simply
  left in the file — any machine that sees a claim older than
  `csv_pending_stale_hours` (`automation.py` `CONFIG`, default **3 hours**)
  treats it as abandoned and safely reclaims the row. Nothing gets
  permanently stuck waiting on a machine that's gone.
- `done` and `failed` behave exactly as in the local-file case, and are
  never reclaimed.

**One-time setup (per Google account, not per PC):**
1. Go to [Google Cloud Console](https://console.cloud.google.com/) →
   create a project (or use an existing one) → **APIs & Services → Credentials**.
2. **Create Credentials → OAuth client ID** → Application type **Desktop app** → Create.
3. Click **Download JSON** on the client you just created.
4. Save that file as **`credentials.json`** directly next to `automation.py`
   (or next to `ContentPipeline.exe`, if using the installed app).
5. Upload your CSV to Google Drive as a normal file (not a Google Sheet —
   keep it a `.csv`), and grab its share link.

The **first** run on a given PC opens a browser window asking you to sign in
with your Google account and approve access — do that once. It then caches
a `token.json` next to `automation.py` and never prompts again on that
machine. Run the same `credentials.json` + sign-in flow on each additional
PC you want to share the list with (each PC gets its own `token.json`; the
`credentials.json` OAuth client can be reused across all of them).

If `credentials.json` is missing when you pass a Drive link, the pipeline
stops with a clear message explaining exactly this setup, instead of failing
unhelpfully.

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
  resumes the same URL automatically — no restart needed. You don't have to
  wait it out blindly: press **Enter** in the console, or click **⏩ Resume
  Now** in the GUI, to retry immediately at any point. If quota's still
  exhausted, the *next* wait picks the original countdown back up instead of
  restarting a fresh 6h wait — the deadline is persisted to disk (survives a
  restart, too), so repeated early checks never push the real reset time out
  further.
- An image that can't be produced (quota, a transient `agy` failure, or a
  flat/blank frame slipping through) is **never** swapped for a placeholder —
  it's retried up to `img_max_retries` times, and if it's still not real, the
  whole run pauses and waits like a quota hit, then re-attempts that exact
  image. An article can only finish with real, generated art in every slot.
- 3 consecutive crashes on the *same* URL marks it `failed` in the CSV so the
  batch keeps moving instead of looping forever on one bad page; clear the
  status in the CSV to retry it later. (`failed` is a hard stop, never
  auto-retried — this used to silently loop forever on old builds; fixed.)
- If the CSV is a Google Drive link, this same checkpointing is what makes
  multi-PC sharing safe: a PC that crashes mid-article leaves nothing but a
  `pending` claim behind, which any machine (including itself, restarted)
  can pick back up once it goes stale — see [§6](#6-the-csv-file--full-format-reference).

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

> **Most people don't need this section.** A pre-built installer is already
> published at [github.com/Asadullah404/auto-blog-ai/releases/latest](https://github.com/Asadullah404/auto-blog-ai/releases/latest)
> — see [§0](#0-quick-start--download-install--first-run-no-coding-required)
> to just download and run it. This section is only for building it yourself
> from source (e.g. after making code changes, or to publish your own release).

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
  several minutes and produces a couple hundred MB of output (the published
  installer is ~200 MB) — that's normal given this project's dependencies,
  not a sign something's wrong.
- `build.py` also installs (if missing) and bundles `google-auth`,
  `google-auth-oauthlib`, and `google-api-python-client` — these back the
  Google Drive CSV sync feature. `automation.py` itself only installs them
  lazily on first actual use, but the frozen `.exe` needs them baked in
  ahead of time, so `build.py` installs them into the build environment
  before invoking PyInstaller.
- `build.py` explicitly excludes a list of unrelated ML packages (torch,
  tensorflow, transformers, sklearn, cupy, numba, ...) from the `automation.exe`
  build. They're never imported by this project's code, but PyInstaller's
  `--collect-all newspaper`/`--collect-all nltk` flags will sweep them in
  anyway if they happen to be installed in your Python environment (e.g. from
  an unrelated project) — without the excludes, a single machine with those
  packages present can produce an installer several **gigabytes** larger than
  it needs to be, and past GitHub's 2 GB release-asset limit. If you add a
  new import to `automation.py` and the built exe throws an `ImportError` for
  something on that exclude list, remove it from the `--exclude-module` list
  in `build.py`.
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
| Pipeline seems stuck / repeatedly waits "quota reached" | Two things can trigger this: (1) `agy`'s output literally contains quota/billing language, or (2) an image failed `img_max_retries` times in a row with no clear quota message — treated the same way on purpose, since that pattern almost always *is* exhausted quota. Either way, the run isn't broken — it's waiting `quota_wait_hours` (default 6h) and will resume the same image automatically. Check the log for what `agy` actually printed if you want to confirm, or just press **Enter**/click **⏩ Resume Now** to check right now instead of waiting. |
| I want to check if quota reset early instead of waiting the full 6h | Press **Enter** in the console, or click **⏩ Resume Now** in the GUI, at any point during a quota wait. It retries immediately; if quota's still exhausted, the wait resumes the *same* countdown instead of restarting a fresh 6h wait, so checking early never costs you anything. |
| `Could not parse JSON` in the log | Not an error — it's a recovery notice from Phase 2. The AI's response didn't parse as clean JSON (usually a stray double-quote inside prose truncating a string, or the response getting cut off), so the pipeline automatically falls back to rewriting that batch's sections one at a time instead, which is far more reliable. Nothing is lost; it just takes a couple of extra `agy` calls. If you see it on *every single batch*, edit `Skills/seo_skill.md` to reinforce rule 14 (never use `"` inside text) or lower `CONFIG["batch_size"]` in `automation.py` so each response is shorter. |
| Invalid `--resolution` error | Custom resolutions must be `WIDTHxHEIGHT` with both sides between 64 and 8000, e.g. `1000x1000`. Preset names are `sd`, `hd`, `fhd`, `2k`. |
| Category from the CSV isn't showing up on the post | Make sure the CSV row actually has a category column and the URL hasn't already been fully transformed with the old category cached — re-running the same URL re-applies the CSV category on top of the cache automatically, so just re-run it. |
| Built `.exe` won't start / Windows SmartScreen warning | Expected for an unsigned app — click **More info → Run anyway**. If it still won't launch, try running `ContentPipeline.exe` from a terminal (`cmd`) to see the actual error instead of a silent failure. |
| GUI's Start/Test/Publish buttons do nothing in the built app | `automation.exe` / `wordpress_publisher.exe` must be in the same folder as `ContentPipeline.exe`. Reinstall via `Install ContentPipeline.exe` rather than copying files individually. |
| `python build.py` fails partway with a missing-module error at runtime (not build time) | PyInstaller occasionally misses a package's non-Python data files. Note which import failed in the built exe's console output and re-run the build with an extra `--collect-all <package>` flag added to that entry's build step in `build.py`. |
| Blurry or clipped windows on the Control Panel | If Windows display scaling is set above 100%, make sure you're on the latest `pipeline_gui.py` — older copies could lay out wider than the window at fractional scaling. Re-download/pull if you hit this. |
| `Google Drive isn't set up yet — credentials.json not found` | Follow the one-time setup in [§6](#6-the-csv-file--full-format-reference): create an OAuth "Desktop app" client in Google Cloud Console, download it, save it as `credentials.json` next to `automation.py` (or the installed app's `.exe` folder). |
| A URL never gets picked up on any PC (Drive-synced CSV) | It's likely stuck with a stale `pending:` claim from a PC that hasn't checked back in within `csv_pending_stale_hours` yet (default 3h) — wait it out, lower `CONFIG["csv_pending_stale_hours"]` in `automation.py`, or just clear that row's status column by hand in the Drive file. |
| Google Drive sign-in browser window doesn't appear / times out | Make sure nothing is blocking `localhost` connections (some corporate firewalls/VPNs do) — the OAuth flow briefly runs a local web server to receive the sign-in callback. Try again off VPN if it hangs. |

---

## 13. FAQ

**Does re-running the pipeline ever create duplicate WordPress posts?**
No — `wordpress_publisher.py` checks `wp_published` in the article's own DB
before creating a post, and skips URLs already published there.

**Can I edit the SEO writing style?**
Yes — edit `Skills/seo_skill.md` after it's auto-created on first run. It's
plain Markdown instructions given to `agy` for every rewrite call, and covers
both SEO (rankings) and GEO (getting cited by AI answer engines like Google
AI Overviews, ChatGPT, and Perplexity).

**Will the pipeline ever put a blank/grey image in a published post?**
No. If a real image can't be produced — quota exhaustion, a transient `agy`
failure, or a flat/blank frame that technically comes back as a file — the
pipeline retries that exact image and, failing that, pauses the whole run and
waits (same as a quota hit) instead of ever substituting a placeholder. See
[§1](#1-how-it-works--the-six-phases) and [§9](#9-how-resume--idempotency-works).

**Can I run this on more than one PC against the same list of URLs?**
Yes — point every PC's `--csv` (or the GUI's CSV field) at the same Google
Drive share link instead of a local file. Each machine claims a URL the
moment it starts it and syncs that claim to Drive immediately, so the others
skip it; a claim from a PC that crashed or closed goes stale automatically
and gets picked back up. Full setup in [§6](#6-the-csv-file--full-format-reference).

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
