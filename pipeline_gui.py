#!/usr/bin/env python3
"""
pipeline_gui.py  —  CONTROL PANEL for the Auto Content Pipeline
================================================================
A modern desktop control panel that sits on top of your pipeline.

  🏠 Dashboard  — live stats, progress, latest image, recent activity
  ⚙  Settings   — WordPress connection, publishing switches, images, CSV
  📜 Logs       — full colorized live log, export to file
  📰 Articles   — everything generated/published, with quick-open links

All settings are saved to  pipeline_config.json , which wordpress_publisher.py
reads — so these switches actually control what the running pipeline does.

RUN IT (from the folder that contains automation.py):
    python pipeline_gui.py

NOTE: For AUTO mode to publish during a run, the Phase 6 hook must be in
automation.py (see README_SETUP.md, Step 5). Without the hook you can still
generate, then click "Publish All Generated".
"""

import os
import re
import sys
import csv
import json
import queue
import sqlite3
import webbrowser
import subprocess
import threading
import importlib
from pathlib import Path

# Ensure UTF-8 stdout/stderr streams on Windows
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


# ── auto-install the GUI toolkit (matches your pipeline's auto-install style) ──
def _ensure(pkg, imp=None):
    imp = imp or pkg
    try:
        return importlib.import_module(imp)
    except ImportError:
        print(f"Installing {pkg} ...")
        subprocess.run([sys.executable, "-m", "pip", "install", pkg, "-q"])
        return importlib.import_module(imp)

ctk = _ensure("customtkinter")
_ensure("Pillow", "PIL")
import tkinter as tk
from tkinter import filedialog
from PIL import Image

# Windows fractional display scaling (125%/150%) makes customtkinter apply its
# own DPI correction on top of what Tk already gets from the OS, so widgets
# are laid out ~scale-factor too wide and overflow the window. Disabling
# automatic DPI awareness here (must happen before any CTk window is created)
# lets Tk's own scaling be the only one in effect, so content fits the window.
ctk.deactivate_automatic_dpi_awareness()


CONFIG_PATH = os.environ.get("PIPELINE_CONFIG", "pipeline_config.json")

DEFAULTS = {
    "base_url":     "",
    "username":     "",
    "app_password": "",
    "status":       "publish",   # LIVE by default
    "auto_publish": True,        # AUTO ON by default
    "seo_plugin":   "rankmath",
    "alt_from":     "heading",
    "csv_path":     "",
    "fresh":        False,
    "verify_ssl":   True,
    "image_format":         "webp",
    "image_resolution":     "hd",      # heading/section images
    "feature_resolution":   "hd",      # feature image — independent of the above
    "pin_resolution":       "1000x1500",  # Pinterest pin image
    "heading_text_overlay": True,      # paste each section heading onto its image
    "feature_text_overlay": False,     # paste the post title onto the feature image
    "pinterest_pin":        False,     # also render + upload a Pinterest pin image
}

SEO_LABELS = {"Rank Math (free)": "rankmath", "None": "none"}
SEO_LABELS_REV = {v: k for k, v in SEO_LABELS.items()}
ALT_LABELS = {"Section heading": "heading", "Post title": "title"}
ALT_LABELS_REV = {v: k for k, v in ALT_LABELS.items()}
FORMAT_LABELS = {"WebP (smaller files)": "webp", "JPEG": "jpeg"}
FORMAT_LABELS_REV = {v: k for k, v in FORMAT_LABELS.items()}
RESOLUTION_LABELS = {
    "SD  (854×480)":   "sd",
    "HD  (1200×675)":  "hd",
    "Full HD (1920×1080)": "fhd",
    "2K  (2560×1440)": "2k",
    "Custom…":         "custom",
}
RESOLUTION_LABELS_REV = {v: k for k, v in RESOLUTION_LABELS.items()}
_CUSTOM_RES_RE = re.compile(r'^(\d{2,5})[xX](\d{2,5})$')

# ── Palette — one accent (#2563eb) shared with the generated article template ──
COLORS = {
    "bg":           "#0b0f19",
    "bg_alt":       "#0f1626",
    "sidebar":      "#080b12",
    "card":         "#121a2b",
    "card_alt":     "#1a2338",
    "border":       "#22293b",
    "text":         "#e5e7eb",
    "text_dim":     "#a7b0c0",
    "text_mute":    "#6b7686",
    "accent":       "#2563eb",
    "accent_hover": "#1d4ed8",
    "accent_soft":  "#182544",
    "green":        "#16a34a",
    "green_hover":  "#15803d",
    "green_dim":    "#0f4429",
    "amber":        "#f59e0b",
    "red":          "#ef4444",
    "red_hover":    "#dc2626",
    "slate":        "#2b3446",
    "slate_hover":  "#38435a",
}


# ── .env support (dependency-free) ────────────────────────────
def _load_dotenv(path=None):
    p = Path(path or os.environ.get("DOTENV_PATH", ".env"))
    if not p.exists():
        return
    for raw in p.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, val = line.split("=", 1)
        key, val = key.strip(), val.strip().strip('"').strip("'")
        if key:
            os.environ.setdefault(key, val)

_load_dotenv()

def _env_bool(name, default):
    v = os.environ.get(name)
    return default if v is None else v.strip().lower() in ("1", "true", "yes", "on", "y")

def _from_env():
    vals = {
        "base_url":     os.environ.get("WP_URL", ""),
        "username":     os.environ.get("WP_USER", ""),
        "app_password": os.environ.get("WP_APP_PASSWORD", ""),
        "status":       os.environ.get("WP_STATUS", ""),
        "seo_plugin":   os.environ.get("WP_SEO_PLUGIN", ""),
        "alt_from":     os.environ.get("WP_ALT_FROM", ""),
    }
    out = {k: v for k, v in vals.items() if v}
    if os.environ.get("WP_AUTO_PUBLISH") is not None:
        out["auto_publish"] = _env_bool("WP_AUTO_PUBLISH", True)
    if os.environ.get("WP_VERIFY_SSL") is not None:
        out["verify_ssl"] = _env_bool("WP_VERIFY_SSL", True)
    return out


def load_cfg():
    merged = dict(DEFAULTS)
    merged.update(_from_env())                 # .env / environment fills the base
    p = Path(CONFIG_PATH)
    if p.exists():                             # saved GUI settings win on top
        try:
            merged.update(json.loads(p.read_text(encoding="utf-8")))
        except Exception:
            pass
    return merged


def save_cfg(cfg):
    Path(CONFIG_PATH).write_text(json.dumps(cfg, indent=2), encoding="utf-8")


# ─────────────────────────────────────────────────────────────
# Data helpers — CSV stats + pipeline_output scan (used by Dashboard/Articles)
# ─────────────────────────────────────────────────────────────
def _parse_csv_rows(path):
    """Mirrors automation.py's csv_load() status/category heuristic."""
    rows = []
    try:
        with open(path, newline="", encoding="utf-8") as f:
            for raw in csv.reader(f):
                if not raw:
                    continue
                url = raw[0].strip()
                if not url or url.startswith("#"):
                    continue
                status = ""
                if len(raw) >= 3:
                    status = raw[2].strip().lower()
                elif len(raw) == 2:
                    second = raw[1].strip().lower()
                    if second in ("done", "failed"):
                        status = second
                rows.append({"url": url, "status": status})
    except Exception:
        pass
    return rows


def _csv_stats(path):
    if not path or not Path(path).exists():
        return {"total": 0, "done": 0, "failed": 0, "pending": 0}
    rows = _parse_csv_rows(path)
    done = sum(1 for r in rows if r["status"] == "done")
    failed = sum(1 for r in rows if r["status"] == "failed")
    total = len(rows)
    return {"total": total, "done": done, "failed": failed, "pending": total - done - failed}


def _scan_pipeline_output(root="pipeline_output"):
    """Read every article's own pipeline_state.db. Returns (articles, published_count)."""
    articles, published = [], 0
    root_path = Path(root)
    if not root_path.exists():
        return articles, published

    for db_path in sorted(root_path.glob("*/pipeline_state.db"),
                           key=lambda p: p.stat().st_mtime, reverse=True):
        out_dir = db_path.parent
        try:
            con = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True, timeout=1)
        except Exception:
            continue
        try:
            row = con.execute(
                "SELECT url, data FROM runs WHERE phase='transform_v3' AND status='done' "
                "ORDER BY id DESC LIMIT 1").fetchone()
            if not row:
                continue
            url, data = row
            try:
                structured = json.loads(data)
            except Exception:
                structured = {}

            pub = None
            try:
                pub = con.execute(
                    "SELECT post_id, post_url FROM wp_published WHERE url=?", (url,)).fetchone()
            except sqlite3.OperationalError:
                pub = None  # never published — table doesn't exist yet

            html_path = out_dir / "final_output.html"
            thumb = None
            for ext in ("webp", "jpg", "jpeg", "png"):
                cand = out_dir / "rendered" / f"feature_rendered.{ext}"
                if cand.exists():
                    thumb = cand
                    break

            articles.append({
                "url":       url,
                "title":     structured.get("title") or url,
                "category":  structured.get("category") or "",
                "html_path": html_path if html_path.exists() else None,
                "post_url":  pub[1] if pub else None,
                "thumb":     thumb,
            })
            if pub:
                published += 1
        finally:
            con.close()
    return articles, published


def _load_thumb(path, size):
    if not path or not Path(path).exists():
        return None
    try:
        img = Image.open(path).convert("RGB")
        img.thumbnail(size)
        return ctk.CTkImage(light_image=img, dark_image=img, size=img.size)
    except Exception:
        return None


def _classify_line(line):
    if "✗" in line or "Traceback" in line:
        return "err"
    if "⚠" in line:
        return "warn"
    if "✓" in line:
        return "ok"
    if "→" in line:
        return "info"
    if line.startswith("$ ") or line.startswith("["):
        return "dim"
    return None


# ─────────────────────────────────────────────────────────────
# First-run setup wizard — shown once, when no WordPress credentials are saved yet
# ─────────────────────────────────────────────────────────────
class SetupWizard(ctk.CTkToplevel):
    def __init__(self, parent, on_done):
        super().__init__(parent)
        self.on_done = on_done
        self.title("Welcome — Connect WordPress")
        self.geometry("460x460")
        self.resizable(False, False)
        self.configure(fg_color=COLORS["bg"])

        ctk.CTkLabel(self, text="⚡  Welcome to Content Pipeline",
                    font=ctk.CTkFont(size=18, weight="bold"),
                    text_color=COLORS["text"]).pack(anchor="w", padx=24, pady=(24, 4))
        ctk.CTkLabel(self, text="Connect your WordPress site to get started. You only "
                                "do this once — it's saved for every time after.",
                    font=ctk.CTkFont(size=12), text_color=COLORS["text_mute"],
                    wraplength=410, justify="left").pack(anchor="w", padx=24, pady=(0, 18))

        def field(label, show=None):
            ctk.CTkLabel(self, text=label, anchor="w", text_color=COLORS["text_dim"]).pack(
                fill="x", padx=24)
            e = ctk.CTkEntry(self, height=36, show=show, placeholder_text=label,
                             fg_color=COLORS["bg_alt"], border_color=COLORS["border"])
            e.pack(fill="x", padx=24, pady=(4, 12))
            return e

        self.e_url  = field("Site URL  (https://yoursite.com)")
        self.e_user = field("WordPress username")
        self.e_pass = field("Application password", show="•")

        ctk.CTkLabel(self, text="Need an Application Password? WP Admin → Users → Profile "
                                "→ Application Passwords → Add New.",
                    font=ctk.CTkFont(size=10), text_color=COLORS["text_mute"],
                    wraplength=410, justify="left").pack(anchor="w", padx=24)

        self.hint = ctk.CTkLabel(self, text="", text_color=COLORS["amber"],
                                 font=ctk.CTkFont(size=11), wraplength=410, justify="left")
        self.hint.pack(fill="x", padx=24, pady=(8, 0))

        btns = ctk.CTkFrame(self, fg_color="transparent")
        btns.pack(fill="x", padx=24, pady=(12, 20), side="bottom")
        ctk.CTkButton(btns, text="Skip for now", fg_color="transparent",
                      hover_color=COLORS["card_alt"], text_color=COLORS["text_mute"],
                      command=self._skip).pack(side="left")
        ctk.CTkButton(btns, text="Save & Continue", height=38, fg_color=COLORS["accent"],
                      hover_color=COLORS["accent_hover"], font=ctk.CTkFont(size=13, weight="bold"),
                      command=self._save).pack(side="right")

        self.protocol("WM_DELETE_WINDOW", self._skip)
        self.after(80, self._make_modal)

    def _make_modal(self):
        # deferred so the window is actually mapped/visible before grab_set (Windows quirk)
        self.transient(self.master)
        self.grab_set()
        self.e_url.focus()

    def _skip(self):
        self.grab_release()
        self.destroy()
        self.on_done(saved=False)

    def _save(self):
        url  = self.e_url.get().strip().rstrip("/")
        user = self.e_user.get().strip()
        pw   = self.e_pass.get().strip()
        if not (url and user and pw):
            self.hint.configure(text="Please fill in all three fields.")
            return
        if not (url.startswith("http://") or url.startswith("https://")):
            self.hint.configure(text="Site URL should start with http:// or https://")
            return
        self.grab_release()
        self.destroy()
        self.on_done(saved=True, base_url=url, username=user, app_password=pw)


# ─────────────────────────────────────────────────────────────
class ControlPanel(ctk.CTk):
    def __init__(self):
        super().__init__()
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")
        self.configure(fg_color=COLORS["bg"])

        self.title("Content Pipeline — Control Panel")
        self.geometry("1280x840")
        self.minsize(1120, 700)

        self.cfg = load_cfg()
        self.proc = None
        self.log_q = queue.Queue()
        self._running = False
        self.res_pickers = {}   # cfg_key -> {"menu","e_w","e_h"}, filled by _resolution_picker

        self.grid_columnconfigure(0, weight=0)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=0)
        self.grid_rowconfigure(1, weight=1)
        self.grid_rowconfigure(2, weight=0)

        self._build_header()
        self._build_sidebar()
        self._build_pages()
        self._build_footer()

        self._refresh_badges()
        self._log("Ready. Fill in your WordPress details, Save, then Start.\n")
        self.after(120, self._drain_log)
        self.after(300, self._refresh_dashboard)
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        if self._needs_setup():
            self.after(250, self._show_setup_wizard)

    def _needs_setup(self):
        return not (self.cfg.get("base_url") and self.cfg.get("username")
                   and self.cfg.get("app_password"))

    def _show_setup_wizard(self):
        SetupWizard(self, on_done=self._on_setup_done)

    def _on_setup_done(self, saved, base_url="", username="", app_password=""):
        if saved:
            self.e_url.delete(0, "end");  self.e_url.insert(0, base_url)
            self.e_user.delete(0, "end"); self.e_user.insert(0, username)
            self.e_pass.delete(0, "end"); self.e_pass.insert(0, app_password)
            self._save()
            self._log(f"✓ WordPress details saved for {base_url}\n")
            self._show_page("Dashboard")
            self.on_test()
        else:
            self._log("⚠ Skipped WordPress setup — add it anytime in Settings.\n")
            self._show_page("Settings")

    # ── header ──────────────────────────────────────────────
    def _build_header(self):
        head = ctk.CTkFrame(self, corner_radius=0, height=64, fg_color=COLORS["bg_alt"])
        head.grid(row=0, column=0, columnspan=2, sticky="ew")
        head.grid_propagate(False)

        left = ctk.CTkFrame(head, fg_color="transparent")
        left.pack(side="left", padx=20, pady=10)
        ctk.CTkLabel(left, text="⚡", font=ctk.CTkFont(size=26)).pack(side="left", padx=(0, 10))
        title_box = ctk.CTkFrame(left, fg_color="transparent")
        title_box.pack(side="left")
        ctk.CTkLabel(title_box, text="Content Pipeline", font=ctk.CTkFont(size=18, weight="bold"),
                     text_color=COLORS["text"]).pack(anchor="w")
        ctk.CTkLabel(title_box, text="Extract → Rewrite → Publish", font=ctk.CTkFont(size=11),
                     text_color=COLORS["text_mute"]).pack(anchor="w")

        right = ctk.CTkFrame(head, fg_color="transparent")
        right.pack(side="right", padx=20, pady=10)

        self.mode_badge = ctk.CTkLabel(
            right, text="", font=ctk.CTkFont(size=12, weight="bold"),
            fg_color=COLORS["accent"], corner_radius=8, padx=12, pady=5)
        self.mode_badge.pack(side="right")

        status_wrap = ctk.CTkFrame(right, fg_color="transparent")
        status_wrap.pack(side="right", padx=(0, 16))
        self.pulse_canvas = tk.Canvas(status_wrap, width=10, height=10,
                                      highlightthickness=0, bg=COLORS["bg_alt"])
        self.pulse_dot = self.pulse_canvas.create_oval(1, 1, 9, 9, fill=COLORS["text_mute"], outline="")
        self.pulse_canvas.pack(side="left", padx=(0, 6))
        self.status_lbl = ctk.CTkLabel(status_wrap, text="Idle", font=ctk.CTkFont(size=12, weight="bold"),
                                       text_color=COLORS["text_dim"])
        self.status_lbl.pack(side="left")

    # ── sidebar nav ───────────────────────────────────────────
    def _build_sidebar(self):
        nav = ctk.CTkFrame(self, corner_radius=0, fg_color=COLORS["sidebar"], width=200)
        nav.grid(row=1, column=0, sticky="nsw")
        nav.grid_propagate(False)

        self.nav_btns = {}
        for i, (name, icon) in enumerate((
            ("Dashboard", "🏠"), ("Settings", "⚙"), ("Logs", "📜"), ("Articles", "📰"),
        )):
            b = ctk.CTkButton(
                nav, text=f"   {icon}   {name}", anchor="w", height=42, corner_radius=8,
                fg_color="transparent", hover_color=COLORS["card_alt"], text_color=COLORS["text_dim"],
                font=ctk.CTkFont(size=14, weight="bold"), command=lambda n=name: self._show_page(n))
            b.pack(fill="x", padx=12, pady=(16 if i == 0 else 4, 4))
            self.nav_btns[name] = b

        ctk.CTkLabel(nav, text="Phase 1–5 · Phase 6 Publish", text_color=COLORS["text_mute"],
                     font=ctk.CTkFont(size=10)).pack(side="bottom", pady=14)

    # ── page container ───────────────────────────────────────
    def _build_pages(self):
        container = ctk.CTkFrame(self, corner_radius=0, fg_color=COLORS["bg"])
        container.grid(row=1, column=1, sticky="nsew")
        container.grid_rowconfigure(0, weight=1)
        container.grid_columnconfigure(0, weight=1)

        self.pages = {}
        for name, builder in (
            ("Dashboard", self._build_dashboard),
            ("Settings",  self._build_settings_page),
            ("Logs",      self._build_logs_page),
            ("Articles",  self._build_articles_page),
        ):
            frame = ctk.CTkFrame(container, corner_radius=0, fg_color=COLORS["bg"])
            frame.grid(row=0, column=0, sticky="nsew")
            builder(frame)
            self.pages[name] = frame
        self._show_page("Dashboard")

    def _build_footer(self):
        bar = ctk.CTkFrame(self, corner_radius=0, height=28, fg_color=COLORS["bg_alt"])
        bar.grid(row=2, column=0, columnspan=2, sticky="ew")
        bar.grid_propagate(False)
        ctk.CTkLabel(bar, text=f"config: {CONFIG_PATH}", text_color=COLORS["text_mute"],
                     font=ctk.CTkFont(size=10)).pack(side="left", padx=16)
        ctk.CTkLabel(bar, text="Auto Content Pipeline", text_color=COLORS["text_mute"],
                     font=ctk.CTkFont(size=10)).pack(side="right", padx=16)

    def _show_page(self, name):
        self.pages[name].tkraise()
        for n, btn in self.nav_btns.items():
            active = n == name
            btn.configure(fg_color=COLORS["accent_soft"] if active else "transparent",
                         text_color=COLORS["text"] if active else COLORS["text_dim"])
        if name == "Articles":
            self._populate_articles(self.e_search.get() if hasattr(self, "e_search") else "")

    # ── shared card helper ───────────────────────────────────
    def _card(self, parent, icon, title, subtitle=None):
        card = ctk.CTkFrame(parent, corner_radius=12, fg_color=COLORS["card"],
                            border_width=1, border_color=COLORS["border"])
        card.pack(fill="x", padx=4, pady=10)
        head = ctk.CTkFrame(card, fg_color="transparent")
        head.pack(fill="x", padx=18, pady=(16, 4))
        ctk.CTkLabel(head, text=f"{icon}  {title}", font=ctk.CTkFont(size=15, weight="bold"),
                     text_color=COLORS["text"]).pack(anchor="w")
        if subtitle:
            ctk.CTkLabel(head, text=subtitle, font=ctk.CTkFont(size=11),
                         text_color=COLORS["text_mute"]).pack(anchor="w", pady=(2, 0))
        body = ctk.CTkFrame(card, fg_color="transparent")
        body.pack(fill="x", padx=18, pady=(4, 18))
        return body

    def _resolution_picker(self, parent, label, cfg_key, default_wh=("1000", "1000")):
        """Build a resolution dropdown (+ custom W/H fields) bound to self.cfg[cfg_key].
        Stores the widgets in self.res_pickers[cfg_key] and returns that dict."""
        ctk.CTkLabel(parent, text=label, anchor="w", text_color=COLORS["text_dim"]).pack(fill="x")

        stored_res = str(self.cfg.get(cfg_key, "hd"))
        custom_match = _CUSTOM_RES_RE.match(stored_res)
        if stored_res in RESOLUTION_LABELS_REV:
            initial_label = RESOLUTION_LABELS_REV[stored_res]
            init_w, init_h = default_wh
        elif custom_match:
            initial_label = "Custom…"
            init_w, init_h = custom_match.group(1), custom_match.group(2)
        else:
            initial_label = "HD  (1200×675)"
            init_w, init_h = default_wh

        menu = ctk.CTkOptionMenu(parent, values=list(RESOLUTION_LABELS.keys()),
                                 command=lambda choice, k=cfg_key: self._on_resolution_change(k, choice))
        menu.set(initial_label)
        menu.pack(fill="x", pady=(2, 8))

        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", pady=(0, 12))
        ctk.CTkLabel(row, text="Width", text_color=COLORS["text_dim"]).pack(side="left")
        e_w = ctk.CTkEntry(row, width=80, height=32, placeholder_text=default_wh[0],
                           fg_color=COLORS["bg_alt"], border_color=COLORS["border"])
        e_w.insert(0, init_w)
        e_w.pack(side="left", padx=(6, 16))
        ctk.CTkLabel(row, text="Height", text_color=COLORS["text_dim"]).pack(side="left")
        e_h = ctk.CTkEntry(row, width=80, height=32, placeholder_text=default_wh[1],
                           fg_color=COLORS["bg_alt"], border_color=COLORS["border"])
        e_h.insert(0, init_h)
        e_h.pack(side="left", padx=(6, 0))
        ctk.CTkLabel(row, text="px  (\"Custom…\" only)",
                     text_color=COLORS["text_mute"], font=ctk.CTkFont(size=10)).pack(side="left", padx=(10, 0))

        picker = {"menu": menu, "e_w": e_w, "e_h": e_h}
        self.res_pickers[cfg_key] = picker
        self._on_resolution_change(cfg_key, initial_label)
        return picker

    def _on_resolution_change(self, cfg_key, choice):
        picker = self.res_pickers[cfg_key]
        is_custom = RESOLUTION_LABELS.get(choice) == "custom"
        state = "normal" if is_custom else "disabled"
        picker["e_w"].configure(state=state)
        picker["e_h"].configure(state=state)

    def _resolve_resolution(self, cfg_key):
        """Return the resolution to pass to automation.py: a preset key or WIDTHxHEIGHT."""
        picker = self.res_pickers[cfg_key]
        sel = RESOLUTION_LABELS.get(picker["menu"].get(), "hd")
        if sel != "custom":
            return sel
        w, h = picker["e_w"].get().strip(), picker["e_h"].get().strip()
        if not (w.isdigit() and h.isdigit()):
            self._log(f"⚠ Invalid custom resolution '{w}x{h}' for {cfg_key} — falling back to HD.\n")
            return "hd"
        return f"{w}x{h}"

    def _on_pinterest_toggle(self):
        """Grey out the pin resolution picker when the Pinterest pin feature is off."""
        enabled = self.pinterest_var.get()
        picker = self.res_pickers.get("pin_resolution")
        if not picker:
            return
        picker["menu"].configure(state="normal" if enabled else "disabled")
        if enabled:
            self._on_resolution_change("pin_resolution", picker["menu"].get())
        else:
            picker["e_w"].configure(state="disabled")
            picker["e_h"].configure(state="disabled")

    # ── DASHBOARD ─────────────────────────────────────────────
    def _build_dashboard(self, page):
        page.grid_rowconfigure(0, weight=1)
        page.grid_columnconfigure(0, weight=1)
        wrap = ctk.CTkScrollableFrame(page, corner_radius=0, fg_color=COLORS["bg"])
        wrap.grid(row=0, column=0, sticky="nsew", padx=24, pady=20)
        wrap.grid_columnconfigure((0, 1, 2, 3, 4), weight=1)

        actions = ctk.CTkFrame(wrap, fg_color="transparent")
        actions.grid(row=0, column=0, columnspan=5, sticky="ew", pady=(0, 18))
        self.btn_start = ctk.CTkButton(actions, text="▶  Start Pipeline", height=44, width=180,
                                       fg_color=COLORS["green"], hover_color=COLORS["green_hover"],
                                       font=ctk.CTkFont(size=14, weight="bold"), command=self.on_start)
        self.btn_start.pack(side="left", padx=(0, 8))
        self.btn_stop = ctk.CTkButton(actions, text="■  Stop", height=44, width=110,
                                      fg_color=COLORS["red"], hover_color=COLORS["red_hover"],
                                      command=self.on_stop)
        self.btn_stop.pack(side="left", padx=8)
        ctk.CTkButton(actions, text="⇪  Publish All Generated", height=44,
                      fg_color=COLORS["slate"], hover_color=COLORS["slate_hover"],
                      command=self.on_publish_all).pack(side="left", padx=8)
        ctk.CTkButton(actions, text="🔄", width=44, height=44, fg_color=COLORS["slate"],
                      hover_color=COLORS["slate_hover"], command=self._refresh_dashboard).pack(side="right")

        self.stat_vals = {}
        for i, (key, icon, label) in enumerate((
            ("total", "📄", "Total URLs"), ("pending", "⏳", "Pending"),
            ("done", "✅", "Completed"), ("failed", "⚠️", "Failed"),
            ("published", "🌐", "Published"),
        )):
            self._stat_card(wrap, key, icon, label).grid(row=1, column=i, sticky="nsew", padx=6, pady=6)

        prog_card = ctk.CTkFrame(wrap, corner_radius=12, fg_color=COLORS["card"],
                                 border_width=1, border_color=COLORS["border"])
        prog_card.grid(row=2, column=0, columnspan=5, sticky="ew", padx=6, pady=(6, 14))
        prow = ctk.CTkFrame(prog_card, fg_color="transparent")
        prow.pack(fill="x", padx=16, pady=(12, 4))
        ctk.CTkLabel(prow, text="Batch Progress", font=ctk.CTkFont(size=13, weight="bold"),
                     text_color=COLORS["text"]).pack(side="left")
        self.progress_pct_lbl = ctk.CTkLabel(prow, text="0%", text_color=COLORS["text_mute"])
        self.progress_pct_lbl.pack(side="right")
        self.progress_bar = ctk.CTkProgressBar(prog_card, progress_color=COLORS["accent"],
                                               fg_color=COLORS["bg_alt"], height=10)
        self.progress_bar.set(0)
        self.progress_bar.pack(fill="x", padx=16, pady=(0, 16))

        thumb_card = ctk.CTkFrame(wrap, corner_radius=12, fg_color=COLORS["card"],
                                  border_width=1, border_color=COLORS["border"])
        thumb_card.grid(row=3, column=0, columnspan=2, sticky="nsew", padx=6, pady=6)
        ctk.CTkLabel(thumb_card, text="🖼  Latest Feature Image", font=ctk.CTkFont(size=13, weight="bold"),
                     text_color=COLORS["text"]).pack(anchor="w", padx=16, pady=(14, 6))
        self.thumb_label = ctk.CTkLabel(thumb_card, text="No images generated yet", height=180,
                                        text_color=COLORS["text_mute"], fg_color=COLORS["bg_alt"],
                                        corner_radius=8)
        self.thumb_label.pack(fill="x", padx=16, pady=(0, 16))

        mini_card = ctk.CTkFrame(wrap, corner_radius=12, fg_color=COLORS["card"],
                                 border_width=1, border_color=COLORS["border"])
        mini_card.grid(row=3, column=2, columnspan=3, sticky="nsew", padx=6, pady=6)
        mhdr = ctk.CTkFrame(mini_card, fg_color="transparent")
        mhdr.pack(fill="x", padx=16, pady=(14, 6))
        ctk.CTkLabel(mhdr, text="📟  Recent Activity", font=ctk.CTkFont(size=13, weight="bold"),
                     text_color=COLORS["text"]).pack(side="left")
        ctk.CTkButton(mhdr, text="View Full Log →", width=120, height=22, fg_color="transparent",
                      hover_color=COLORS["card_alt"], text_color=COLORS["accent"],
                      command=lambda: self._show_page("Logs")).pack(side="right")
        self.mini_log = ctk.CTkTextbox(mini_card, height=180, corner_radius=8,
                                       font=ctk.CTkFont(family="Consolas", size=11),
                                       fg_color=COLORS["bg_alt"], text_color=COLORS["text_dim"])
        self.mini_log.pack(fill="both", expand=True, padx=16, pady=(0, 16))
        self._tag_log_widget(self.mini_log)

    def _stat_card(self, parent, key, icon, label):
        card = ctk.CTkFrame(parent, corner_radius=12, fg_color=COLORS["card"],
                            border_width=1, border_color=COLORS["border"])
        ctk.CTkLabel(card, text=icon, font=ctk.CTkFont(size=20)).pack(anchor="w", padx=14, pady=(12, 0))
        val = ctk.CTkLabel(card, text="0", font=ctk.CTkFont(size=26, weight="bold"), text_color=COLORS["text"])
        val.pack(anchor="w", padx=14)
        ctk.CTkLabel(card, text=label, font=ctk.CTkFont(size=11),
                     text_color=COLORS["text_mute"]).pack(anchor="w", padx=14, pady=(0, 12))
        self.stat_vals[key] = val
        return card

    def _refresh_dashboard(self):
        csv_path = self.e_csv.get().strip() if hasattr(self, "e_csv") else self.cfg.get("csv_path", "")
        stats = _csv_stats(csv_path)
        articles, published = _scan_pipeline_output()

        self.stat_vals["total"].configure(text=str(stats["total"]))
        self.stat_vals["pending"].configure(text=str(stats["pending"]))
        self.stat_vals["done"].configure(text=str(stats["done"]))
        self.stat_vals["failed"].configure(text=str(stats["failed"]))
        self.stat_vals["published"].configure(text=str(published))

        frac = (stats["done"] / stats["total"]) if stats["total"] else 0
        self.progress_bar.set(frac)
        self.progress_pct_lbl.configure(text=f"{frac*100:.0f}%  ({stats['done']}/{stats['total']})")

        latest_thumb = next((a["thumb"] for a in articles if a.get("thumb")), None)
        img = _load_thumb(latest_thumb, (420, 220))
        if img:
            self.thumb_label.configure(image=img, text="")
            self.thumb_label.image = img
        else:
            self.thumb_label.configure(image=None, text="No images generated yet")

        self.after(5000, self._refresh_dashboard)

    # ── SETTINGS ──────────────────────────────────────────────
    def _build_settings_page(self, page):
        page.grid_rowconfigure(0, weight=1)
        page.grid_columnconfigure(0, weight=1)
        s = ctk.CTkScrollableFrame(page, corner_radius=0, fg_color=COLORS["bg"])
        s.grid(row=0, column=0, sticky="nsew", padx=24, pady=20)

        def entry(parent, label, key, show=None):
            ctk.CTkLabel(parent, text=label, anchor="w", text_color=COLORS["text_dim"]).pack(fill="x")
            e = ctk.CTkEntry(parent, height=36, show=show, placeholder_text=label,
                             fg_color=COLORS["bg_alt"], border_color=COLORS["border"])
            e.pack(fill="x", pady=(4, 12))
            if self.cfg.get(key):
                e.insert(0, self.cfg[key])
            return e

        # WordPress connection
        wp = self._card(s, "🔌", "WordPress Connection", "Your site URL and Application Password")
        self.e_url  = entry(wp, "Site URL  (https://yoursite.com)", "base_url")
        self.e_user = entry(wp, "WordPress username", "username")
        self.e_pass = entry(wp, "Application password", "app_password", show="•")
        self.btn_test = ctk.CTkButton(wp, text="Test Connection", height=34,
                                      fg_color=COLORS["slate"], hover_color=COLORS["slate_hover"],
                                      command=self.on_test)
        self.btn_test.pack(fill="x")

        # Publishing
        pub = self._card(s, "🚀", "Publishing", "Controls what happens when an article finishes")
        row = ctk.CTkFrame(pub, fg_color="transparent"); row.pack(fill="x", pady=4)
        self.live_var = tk.BooleanVar(value=(self.cfg.get("status") == "publish"))
        self.live_sw = ctk.CTkSwitch(row, text="", variable=self.live_var,
                                     onvalue=True, offvalue=False, command=self._refresh_badges,
                                     button_color="#ffffff", progress_color=COLORS["green"])
        self.live_sw.pack(side="right")
        self.live_lbl = ctk.CTkLabel(row, text="", anchor="w", font=ctk.CTkFont(size=14, weight="bold"))
        self.live_lbl.pack(side="left")

        row2 = ctk.CTkFrame(pub, fg_color="transparent"); row2.pack(fill="x", pady=4)
        self.auto_var = tk.BooleanVar(value=bool(self.cfg.get("auto_publish", True)))
        self.auto_sw = ctk.CTkSwitch(row2, text="", variable=self.auto_var,
                                     onvalue=True, offvalue=False, command=self._refresh_badges,
                                     button_color="#ffffff", progress_color=COLORS["accent"])
        self.auto_sw.pack(side="right")
        self.auto_lbl = ctk.CTkLabel(row2, text="", anchor="w", font=ctk.CTkFont(size=14, weight="bold"))
        self.auto_lbl.pack(side="left")

        ctk.CTkLabel(pub, text="SEO plugin", anchor="w", text_color=COLORS["text_dim"]).pack(
            fill="x", pady=(8, 0))
        self.seo_menu = ctk.CTkOptionMenu(pub, values=list(SEO_LABELS.keys()))
        self.seo_menu.set(SEO_LABELS_REV.get(self.cfg.get("seo_plugin", "rankmath"), "Rank Math (free)"))
        self.seo_menu.pack(fill="x", pady=(2, 8))

        ctk.CTkLabel(pub, text="Image ALT text from", anchor="w", text_color=COLORS["text_dim"]).pack(fill="x")
        self.alt_menu = ctk.CTkOptionMenu(pub, values=list(ALT_LABELS.keys()))
        self.alt_menu.set(ALT_LABELS_REV.get(self.cfg.get("alt_from", "heading"), "Section heading"))
        self.alt_menu.pack(fill="x", pady=(2, 0))

        # Images — format (shared) + independent settings per image type
        img = self._card(s, "🖼", "Images", "Output format, and separate resolution/text-overlay controls per image type")
        ctk.CTkLabel(img, text="Image format", anchor="w", text_color=COLORS["text_dim"]).pack(fill="x")
        self.format_menu = ctk.CTkOptionMenu(img, values=list(FORMAT_LABELS.keys()))
        self.format_menu.set(FORMAT_LABELS_REV.get(self.cfg.get("image_format", "webp"),
                                                    "WebP (smaller files)"))
        self.format_menu.pack(fill="x", pady=(2, 12))

        # Heading (section) images
        head_img = self._card(s, "📝", "Heading Images", "The per-section images inside the article")
        self._resolution_picker(head_img, "Resolution", "image_resolution")
        self.heading_text_var = tk.BooleanVar(value=bool(self.cfg.get("heading_text_overlay", True)))
        ctk.CTkCheckBox(head_img, text="Paste the section heading onto each image",
                        variable=self.heading_text_var).pack(fill="x", pady=(2, 0))

        # Feature image
        feat_img = self._card(s, "🌟", "Feature Image", "The post's featured/hero image")
        self._resolution_picker(feat_img, "Resolution", "feature_resolution")
        self.feature_text_var = tk.BooleanVar(value=bool(self.cfg.get("feature_text_overlay", False)))
        ctk.CTkCheckBox(feat_img, text="Paste the post title onto the feature image",
                        variable=self.feature_text_var).pack(fill="x", pady=(2, 0))

        # Pinterest pin image
        pin_img = self._card(s, "📌", "Pinterest Pin", "Optional extra tall image, uploaded and attached to the post")
        self.pinterest_var = tk.BooleanVar(value=bool(self.cfg.get("pinterest_pin", False)))
        ctk.CTkCheckBox(pin_img, text="Also generate a Pinterest pin image for the post",
                        variable=self.pinterest_var,
                        command=lambda: self._on_pinterest_toggle()).pack(fill="x", pady=(0, 10))
        self.pin_res_frame = ctk.CTkFrame(pin_img, fg_color="transparent")
        self.pin_res_frame.pack(fill="x")
        self._resolution_picker(self.pin_res_frame, "Pin resolution (tall, e.g. 1000×1500)",
                                "pin_resolution", default_wh=("1000", "1500"))
        self._on_pinterest_toggle()

        # Run
        run = self._card(s, "▶", "Run", "Pick the CSV of URLs to process (url,category,status)")
        ctk.CTkLabel(run, text="CSV file of URLs", anchor="w", text_color=COLORS["text_dim"]).pack(fill="x")
        csvrow = ctk.CTkFrame(run, fg_color="transparent"); csvrow.pack(fill="x", pady=(4, 8))
        self.e_csv = ctk.CTkEntry(csvrow, height=36, placeholder_text="path to urls.csv",
                                  fg_color=COLORS["bg_alt"], border_color=COLORS["border"])
        self.e_csv.pack(side="left", fill="x", expand=True)
        if self.cfg.get("csv_path"):
            self.e_csv.insert(0, self.cfg["csv_path"])
        ctk.CTkButton(csvrow, text="Browse", width=80, command=self.on_browse).pack(side="right", padx=(6, 0))

        self.fresh_var = tk.BooleanVar(value=bool(self.cfg.get("fresh", False)))
        ctk.CTkCheckBox(run, text="Fresh run (wipe cached images / renders)",
                        variable=self.fresh_var).pack(fill="x", pady=(2, 0))

        self.btn_save = ctk.CTkButton(s, text="💾  Save Settings", height=42,
                                      fg_color=COLORS["accent"], hover_color=COLORS["accent_hover"],
                                      font=ctk.CTkFont(size=14, weight="bold"), command=self.on_save)
        self.btn_save.pack(fill="x", padx=4, pady=(6, 20))

    # ── LOGS ──────────────────────────────────────────────────
    def _build_logs_page(self, page):
        page.grid_rowconfigure(1, weight=1)
        page.grid_columnconfigure(0, weight=1)

        bar = ctk.CTkFrame(page, fg_color="transparent")
        bar.grid(row=0, column=0, sticky="ew", padx=24, pady=(20, 8))
        ctk.CTkLabel(bar, text="📜  Live Log", font=ctk.CTkFont(size=16, weight="bold"),
                     text_color=COLORS["text"]).pack(side="left")
        ctk.CTkButton(bar, text="Clear", width=70, height=28, fg_color=COLORS["slate"],
                      hover_color=COLORS["slate_hover"], command=self._clear_log).pack(side="right", padx=(6, 0))
        ctk.CTkButton(bar, text="Export…", width=80, height=28, fg_color=COLORS["slate"],
                      hover_color=COLORS["slate_hover"], command=self._export_log).pack(side="right")

        card = ctk.CTkFrame(page, corner_radius=12, fg_color=COLORS["card"],
                            border_width=1, border_color=COLORS["border"])
        card.grid(row=1, column=0, sticky="nsew", padx=24, pady=(0, 20))
        card.grid_rowconfigure(0, weight=1)
        card.grid_columnconfigure(0, weight=1)
        self.log = ctk.CTkTextbox(card, corner_radius=8, font=ctk.CTkFont(family="Consolas", size=12),
                                  fg_color=COLORS["bg_alt"], text_color=COLORS["text"])
        self.log.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
        self._tag_log_widget(self.log)

    def _tag_log_widget(self, widget):
        widget.tag_config("err", foreground=COLORS["red"])
        widget.tag_config("warn", foreground=COLORS["amber"])
        widget.tag_config("ok", foreground=COLORS["green"])
        widget.tag_config("info", foreground="#60a5fa")
        widget.tag_config("dim", foreground=COLORS["text_mute"])

    def _export_log(self):
        path = filedialog.asksaveasfilename(
            defaultextension=".txt", filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
            title="Save log as")
        if not path:
            return
        Path(path).write_text(self.log.get("1.0", "end"), encoding="utf-8")
        self._log(f"\n💾 Log exported → {path}\n")

    # ── ARTICLES ──────────────────────────────────────────────
    def _build_articles_page(self, page):
        page.grid_rowconfigure(1, weight=1)
        page.grid_columnconfigure(0, weight=1)

        bar = ctk.CTkFrame(page, fg_color="transparent")
        bar.grid(row=0, column=0, sticky="ew", padx=24, pady=(20, 8))
        ctk.CTkLabel(bar, text="📰  Generated Articles", font=ctk.CTkFont(size=16, weight="bold"),
                     text_color=COLORS["text"]).pack(side="left")
        self.article_count_lbl = ctk.CTkLabel(bar, text="", text_color=COLORS["text_mute"])
        self.article_count_lbl.pack(side="left", padx=12)

        ctk.CTkButton(bar, text="🔄", width=36, height=28, fg_color=COLORS["slate"],
                      hover_color=COLORS["slate_hover"],
                      command=lambda: self._populate_articles(self.e_search.get())).pack(side="right")
        self.e_search = ctk.CTkEntry(bar, width=240, placeholder_text="Filter by title or category…",
                                     fg_color=COLORS["bg_alt"], border_color=COLORS["border"])
        self.e_search.pack(side="right", padx=(6, 6))
        self.e_search.bind("<KeyRelease>", lambda e: self._populate_articles(self.e_search.get()))

        self.articles_list = ctk.CTkScrollableFrame(page, corner_radius=0, fg_color=COLORS["bg"])
        self.articles_list.grid(row=1, column=0, sticky="nsew", padx=24, pady=(0, 20))
        self.articles_list.grid_columnconfigure(0, weight=1)

    def _populate_articles(self, filter_text=""):
        for w in self.articles_list.winfo_children():
            w.destroy()
        articles, _ = _scan_pipeline_output()
        ft = (filter_text or "").strip().lower()
        if ft:
            articles = [a for a in articles if ft in a["title"].lower() or ft in a["category"].lower()]
        self.article_count_lbl.configure(text=f"{len(articles)} article(s)")
        if not articles:
            ctk.CTkLabel(self.articles_list,
                        text="No articles generated yet — start the pipeline to see results here.",
                        text_color=COLORS["text_mute"]).grid(row=0, column=0, pady=40)
            return
        for i, art in enumerate(articles):
            self._article_card(self.articles_list, art).grid(row=i, column=0, sticky="ew", pady=6)

    def _article_card(self, parent, art):
        card = ctk.CTkFrame(parent, corner_radius=10, fg_color=COLORS["card"],
                            border_width=1, border_color=COLORS["border"])
        card.grid_columnconfigure(1, weight=1)

        thumb_lbl = ctk.CTkLabel(card, text="🖼", width=72, height=48, fg_color=COLORS["bg_alt"],
                                 corner_radius=8, text_color=COLORS["text_mute"])
        img = _load_thumb(art.get("thumb"), (72, 48))
        if img:
            thumb_lbl.configure(image=img, text="")
            thumb_lbl.image = img
        thumb_lbl.grid(row=0, column=0, rowspan=2, padx=14, pady=14)

        ctk.CTkLabel(card, text=art["title"], anchor="w", font=ctk.CTkFont(size=13, weight="bold"),
                    text_color=COLORS["text"], wraplength=440, justify="left").grid(
                        row=0, column=1, sticky="w", padx=(0, 10), pady=(14, 0))
        meta = art["category"] or "Uncategorized"
        ctk.CTkLabel(card, text=f"{meta}   ·   {art['url']}", anchor="w",
                    font=ctk.CTkFont(size=11), text_color=COLORS["text_mute"],
                    wraplength=440, justify="left").grid(row=1, column=1, sticky="w", padx=(0, 10), pady=(2, 14))

        ctk.CTkLabel(card, text="Published" if art["post_url"] else "Generated",
                    fg_color=COLORS["green"] if art["post_url"] else COLORS["slate"],
                    corner_radius=8, padx=10, pady=4,
                    font=ctk.CTkFont(size=10, weight="bold")).grid(row=0, column=2, sticky="e",
                                                                    padx=14, pady=(14, 4))

        btns = ctk.CTkFrame(card, fg_color="transparent")
        btns.grid(row=1, column=2, sticky="e", padx=14, pady=(0, 14))
        if art["post_url"]:
            ctk.CTkButton(btns, text="🔗 View Post", width=104, height=26,
                         fg_color=COLORS["accent"], hover_color=COLORS["accent_hover"],
                         command=lambda u=art["post_url"]: webbrowser.open(u)).pack(side="left", padx=4)
        if art["html_path"]:
            ctk.CTkButton(btns, text="📄 Local HTML", width=104, height=26,
                         fg_color=COLORS["slate"], hover_color=COLORS["slate_hover"],
                         command=lambda p=art["html_path"]: webbrowser.open(p.resolve().as_uri())
                         ).pack(side="left", padx=4)
        return card

    # ── status / mode badges ─────────────────────────────────
    def _refresh_badges(self):
        live = self.live_var.get()
        auto = self.auto_var.get()
        self.live_lbl.configure(text="LIVE (publish)" if live else "DRAFT (review)",
                                text_color=COLORS["green"] if live else COLORS["amber"])
        self.auto_lbl.configure(text="AUTO mode ON" if auto else "AUTO mode OFF",
                                text_color=COLORS["accent"] if auto else COLORS["text_mute"])
        badge = ("LIVE · AUTO" if live and auto else
                 "LIVE · MANUAL" if live else
                 "DRAFT · AUTO" if auto else "DRAFT · MANUAL")
        self.mode_badge.configure(text=badge, fg_color=COLORS["green"] if (live and auto) else COLORS["accent"])

    def _set_running(self, running, tag=""):
        self._running = running
        self.btn_start.configure(state="disabled" if running else "normal")
        if running:
            self.status_lbl.configure(text=f"Running · {tag}" if tag else "Running",
                                      text_color=COLORS["green"])
            self._pulse_tick()
        else:
            self.status_lbl.configure(text="Idle", text_color=COLORS["text_dim"])
            self.pulse_canvas.itemconfig(self.pulse_dot, fill=COLORS["text_mute"])

    def _pulse_tick(self):
        if not self._running:
            return
        cur = self.pulse_canvas.itemcget(self.pulse_dot, "fill")
        nxt = COLORS["green"] if cur != COLORS["green"] else COLORS["green_dim"]
        self.pulse_canvas.itemconfig(self.pulse_dot, fill=nxt)
        self.after(550, self._pulse_tick)

    def collect_cfg(self):
        return {
            "base_url":     self.e_url.get().strip().rstrip("/"),
            "username":     self.e_user.get().strip(),
            "app_password": self.e_pass.get().strip(),
            "status":       "publish" if self.live_var.get() else "draft",
            "auto_publish": bool(self.auto_var.get()),
            "seo_plugin":   SEO_LABELS.get(self.seo_menu.get(), "rankmath"),
            "alt_from":     ALT_LABELS.get(self.alt_menu.get(), "heading"),
            "csv_path":     self.e_csv.get().strip(),
            "fresh":        bool(self.fresh_var.get()),
            "verify_ssl":   self.cfg.get("verify_ssl", True),
            "image_format":         FORMAT_LABELS.get(self.format_menu.get(), "webp"),
            "image_resolution":     self._resolve_resolution("image_resolution"),
            "feature_resolution":   self._resolve_resolution("feature_resolution"),
            "pin_resolution":       self._resolve_resolution("pin_resolution"),
            "heading_text_overlay": bool(self.heading_text_var.get()),
            "feature_text_overlay": bool(self.feature_text_var.get()),
            "pinterest_pin":        bool(self.pinterest_var.get()),
        }

    def _save(self):
        self.cfg = self.collect_cfg()
        save_cfg(self.cfg)

    def _flash(self, btn, text, color, revert_text, revert_color, ms=1400):
        btn.configure(text=text, fg_color=color)
        self.after(ms, lambda: btn.configure(text=revert_text, fg_color=revert_color))

    # ── log plumbing ────────────────────────────────────────
    def _log(self, text):
        for line in text.splitlines(keepends=True):
            tag = _classify_line(line)
            for widget in (self.log, self.mini_log):
                if tag:
                    widget.insert("end", line, tag)
                else:
                    widget.insert("end", line)
                widget.see("end")
        self._trim_mini_log()

    def _trim_mini_log(self):
        total_lines = int(self.mini_log.index("end-1c").split(".")[0])
        if total_lines > 200:
            self.mini_log.delete("1.0", f"{total_lines - 150}.0")

    def _clear_log(self):
        self.log.delete("1.0", "end")
        self.mini_log.delete("1.0", "end")

    def _drain_log(self):
        try:
            while True:
                self._log(self.log_q.get_nowait())
        except queue.Empty:
            pass
        self.after(120, self._drain_log)

    def _find_script(self, name):
        for candidate in (
            Path(name),
            Path("..") / name,
            Path(__file__).parent / name,
            Path(__file__).parent.parent / name,
        ):
            if candidate.exists():
                return candidate.resolve()
        return None

    def _tool_cmd(self, basename, args):
        """
        basename: 'automation' or 'wordpress_publisher'.
        Frozen (built .exe): run the sibling <basename>.exe directly, next to
        this running .exe — build.py places all three exes flat in one folder.
        Dev mode: fall back to `python <basename>.py` like before.
        Returns (cmd_list, run_dir) or (None, None) if not found.
        """
        if getattr(sys, "frozen", False):
            exe_path = Path(sys.executable).parent / f"{basename}.exe"
            if exe_path.exists():
                return [str(exe_path), *args], exe_path.parent
            return None, None
        py_path = self._find_script(f"{basename}.py")
        if py_path:
            return [sys.executable, str(py_path), *args], py_path.parent
        return None, None

    def _run(self, cmd, tag="process", target_dir=None):
        if self.proc and self.proc.poll() is None:
            self._log("⚠ Something is already running. Stop it first.\n")
            return
        self._save()
        run_cwd = str(target_dir) if target_dir else os.getcwd()
        self._log(f"\n$ {' '.join(cmd)}\n")
        self._set_running(True, tag)
        env = dict(os.environ, PYTHONUNBUFFERED="1", PYTHONIOENCODING="utf-8", PIPELINE_CONFIG=CONFIG_PATH)
        try:
            self.proc = subprocess.Popen(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, encoding="utf-8", errors="replace", bufsize=1, env=env, cwd=run_cwd)
        except FileNotFoundError as e:
            self._log(f"✗ Could not start: {e}\n"); self._set_running(False); return
        threading.Thread(target=self._reader, args=(self.proc, tag), daemon=True).start()

    def _reader(self, proc, tag):
        for line in proc.stdout:
            self.log_q.put(line)
        code = proc.wait()
        self.log_q.put(f"\n[{tag} finished · exit code {code}]\n")
        self.after(0, lambda: self._set_running(False))
        self.after(200, self._refresh_dashboard)

    # ── button actions ─────────────────────────────────────
    def on_browse(self):
        path = filedialog.askopenfilename(
            title="Choose your CSV of URLs",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")])
        if path:
            self.e_csv.delete(0, "end"); self.e_csv.insert(0, path)

    def on_save(self):
        self._save()
        self._log("💾 Settings saved to " + CONFIG_PATH + "\n")
        self._flash(self.btn_save, "✓  Saved", COLORS["green"], "💾  Save Settings", COLORS["accent"])

    def on_test(self):
        cmd, run_dir = self._tool_cmd("wordpress_publisher", ["--test"])
        if not cmd:
            self._log("✗ wordpress_publisher not found (script or .exe).\n"); return
        self._run(cmd, tag="connection test", target_dir=run_dir)

    def on_start(self):
        csv_path = self.e_csv.get().strip()
        if not csv_path or not Path(csv_path).exists():
            self._log("✗ Pick a valid CSV file first (Browse).\n"); return
        args = ["--csv", csv_path,
                "--image-format", FORMAT_LABELS.get(self.format_menu.get(), "webp"),
                "--resolution", self._resolve_resolution("image_resolution"),
                "--feature-resolution", self._resolve_resolution("feature_resolution"),
                "--pin-resolution", self._resolve_resolution("pin_resolution")]
        if self.fresh_var.get():
            args.append("--fresh")
        if self.feature_text_var.get():
            args.append("--feature-text")
        if not self.heading_text_var.get():
            args.append("--no-heading-text")
        if self.pinterest_var.get():
            args.append("--pinterest-pin")
        cmd, run_dir = self._tool_cmd("automation", args)
        if not cmd:
            self._log("✗ automation not found (script or .exe).\n"); return
        self._run(cmd, tag="pipeline", target_dir=run_dir)

    def on_stop(self):
        if self.proc and self.proc.poll() is None:
            self.proc.terminate()
            self._log("\n■ Stop requested — process terminating.\n")
            self._set_running(False)
        else:
            self._log("Nothing is running.\n")

    def on_publish_all(self):
        cmd, run_dir = self._tool_cmd("wordpress_publisher", [])
        if not cmd:
            self._log("✗ wordpress_publisher not found (script or .exe).\n"); return
        self._run(cmd, tag="publish all", target_dir=run_dir)

    def _on_close(self):
        if self.proc and self.proc.poll() is None:
            self.proc.terminate()
        self.destroy()


if __name__ == "__main__":
    ControlPanel().mainloop()
