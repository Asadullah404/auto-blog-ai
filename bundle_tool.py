# ==============================================================================
# 📦 OFFLINE BUNDLE TOOL — Auto Content Pipeline
# ==============================================================================
# Creates, inspects, and manages all-in-one self-contained offline bundle files.
# A bundle contains EVERYTHING needed to run without Firebase or cloud quotas:
#   1. WordPress connection & credentials
#   2. AI image generator settings & custom GPU server URL
#   3. Image resolutions, formats, and overlay options
#   4. Complete list of URLs, categories, and their done/pending status
# ==============================================================================

import os
import sys
import csv
import json
import argparse
from pathlib import Path

if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if sys.stderr and hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

DEFAULT_CONFIG_PATH = Path("pipeline_config.json")
DEFAULT_CSV_PATH = Path("Links.csv")
DEFAULT_BUNDLE_PATH = Path("offline_bundle.json")

def load_csv_links(csv_path: Path) -> list:
    """Reads a CSV and returns a normalized list of link dicts."""
    links = []
    csv_path = Path(csv_path)
    if not csv_path.exists():
        return links

    with open(csv_path, "r", encoding="utf-8", errors="replace") as f:
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

def save_csv_links(csv_path: Path, links: list):
    """Exports link dicts back to a standard CSV."""
    with open(csv_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["url", "category", "status"])
        for item in links:
            writer.writerow([item.get("url", ""), item.get("category", ""), item.get("status", "pending")])

def create_bundle(settings: dict, links: list, out_path: Path, name: str = "Offline Pipeline Bundle") -> dict:
    """Builds and writes an all-in-one offline bundle JSON."""
    bundle = {
        "bundle_version": "1.0",
        "name": name,
        "created_at": str(Path(out_path).name),
        "settings": settings,
        "links": links
    }
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(bundle, f, indent=2, ensure_ascii=False)
    return bundle

def load_bundle(bundle_path: Path) -> dict:
    """Loads and validates an offline bundle file."""
    bundle_path = Path(bundle_path)
    if not bundle_path.exists():
        raise FileNotFoundError(f"Bundle file not found: {bundle_path}")
    with open(bundle_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict) or "settings" not in data or "links" not in data:
        raise ValueError(f"Invalid bundle format in {bundle_path}. Expected keys 'settings' and 'links'.")
    return data

def update_bundle_link(bundle_path: Path, url: str, status: str):
    """Updates the status of a specific URL inside the bundle file."""
    data = load_bundle(bundle_path)
    updated = False
    for item in data.get("links", []):
        if item.get("url") == url:
            item["status"] = status
            updated = True
            break
    if updated:
        with open(bundle_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

def inspect_bundle(bundle_path: Path):
    """Prints human-readable details of a bundle file."""
    data = load_bundle(bundle_path)
    links = data.get("links", [])
    settings = data.get("settings", {})
    total = len(links)
    done = sum(1 for l in links if l.get("status") == "done")
    failed = sum(1 for l in links if l.get("status") == "failed")
    pending = total - done - failed

    print("\n" + "=" * 65)
    print(f"📦 BUNDLE INSPECTION: {bundle_path}")
    print("=" * 65)
    print(f"  Name:             {data.get('name', 'Offline Bundle')}")
    print(f"  WordPress URL:    {settings.get('base_url', 'Not configured')}")
    print(f"  WordPress User:   {settings.get('username', 'Not configured')}")
    print(f"  Publish Status:   {settings.get('status', 'draft')}")
    print(f"  Image Engine:     {settings.get('image_engine', 'my_server')}")
    print(f"  Server URL:       {settings.get('server_url', 'None')}")
    print(f"  Resolutions:      Heading: {settings.get('image_resolution', 'hd')} | Feature: {settings.get('feature_resolution', 'hd')}")
    print(f"  Text Overlays:    Heading: {settings.get('heading_text_overlay', False)} | Feature: {settings.get('feature_text_overlay', False)}")
    print(f"  Article Format:   {settings.get('article_format', 'paragraphs')}")
    if settings.get("feature_image_master_prompt"):
        print(f"  Feature Master:   {settings.get('feature_image_master_prompt')}")
    if settings.get("heading_image_master_prompt"):
        print(f"  Heading Master:   {settings.get('heading_image_master_prompt')}")
    print("-" * 65)
    print("📊 URL Statistics:")
    print(f"  Total URLs:       {total}")
    print(f"  Pending:          {pending}")
    print(f"  Done:             {done}")
    print(f"  Failed:           {failed}")
    print("=" * 65)
    if pending > 0:
        print("\nNext pending URLs:")
        count = 0
        for l in links:
            if l.get("status") not in ("done", "failed"):
                print(f"  [{count+1}] {l.get('url')} (Category: {l.get('category', 'None')})")
                count += 1
                if count >= 5:
                    break
        if pending > 5:
            print(f"  ... and {pending - 5} more")
    print()

def interactive_menu():
    print("\n" + "=" * 65)
    print("📦 AUTO CONTENT PIPELINE — OFFLINE BUNDLE CREATOR")
    print("=" * 65)
    print("Create an all-in-one file with your settings + URLs for 100% offline 24/7 runs.\n")
    print("  [1] Quick Build: Merge pipeline_config.json + Links.csv -> offline_bundle.json")
    print("  [2] Custom Build: Pick custom settings file and CSV file")
    print("  [3] Inspect an existing bundle file")
    print("  [4] Export bundle URLs back to CSV")
    print("  [5] Exit")
    print("-" * 65)

    choice = input("Select an option [1-5, default=1]: ").strip() or "1"

    if choice == "1":
        cfg = {}
        if DEFAULT_CONFIG_PATH.exists():
            with open(DEFAULT_CONFIG_PATH, "r", encoding="utf-8") as f:
                cfg = json.load(f)
            print(f"✓ Loaded settings from {DEFAULT_CONFIG_PATH}")
        else:
            print(f"⚠ {DEFAULT_CONFIG_PATH} not found. Using default empty settings.")

        csv_file = DEFAULT_CSV_PATH
        if not csv_file.exists():
            custom_csv = input("Links.csv not found. Enter path to your CSV: ").strip()
            csv_file = Path(custom_csv)

        links = load_csv_links(csv_file)
        print(f"✓ Loaded {len(links)} URLs from {csv_file}")

        out = Path("offline_bundle.json")
        create_bundle(cfg, links, out)
        print(f"\n🎉 SUCCESS: All settings and URLs saved to: {out.resolve()}")
        inspect_bundle(out)

    elif choice == "2":
        cfg_path_str = input(f"Settings JSON path [default={DEFAULT_CONFIG_PATH}]: ").strip() or str(DEFAULT_CONFIG_PATH)
        csv_path_str = input(f"Links CSV path [default={DEFAULT_CSV_PATH}]: ").strip() or str(DEFAULT_CSV_PATH)
        out_path_str = input("Output bundle path [default=offline_bundle.json]: ").strip() or "offline_bundle.json"

        cfg = {}
        if Path(cfg_path_str).exists():
            with open(cfg_path_str, "r", encoding="utf-8") as f:
                cfg = json.load(f)
        links = load_csv_links(Path(csv_path_str))
        create_bundle(cfg, links, Path(out_path_str))
        print(f"\n🎉 SUCCESS: Bundle created at {out_path_str}")
        inspect_bundle(Path(out_path_str))

    elif choice == "3":
        b_path = input("Enter bundle file path [default=offline_bundle.json]: ").strip() or "offline_bundle.json"
        inspect_bundle(Path(b_path))

    elif choice == "4":
        b_path = input("Enter bundle file path [default=offline_bundle.json]: ").strip() or "offline_bundle.json"
        out_csv = input("Enter output CSV path [default=exported_links.csv]: ").strip() or "exported_links.csv"
        data = load_bundle(Path(b_path))
        save_csv_links(Path(out_csv), data.get("links", []))
        print(f"✓ Exported {len(data.get('links', []))} links to {out_csv}")

    else:
        print("Exiting.")

def main():
    parser = argparse.ArgumentParser(description="Manage offline pipeline bundles.")
    parser.add_argument("--create", action="store_true", help="Create an offline bundle from config and CSV")
    parser.add_argument("--config", default="pipeline_config.json", help="Path to pipeline_config.json")
    parser.add_argument("--csv", default="Links.csv", help="Path to URLs CSV file")
    parser.add_argument("--out", default="offline_bundle.json", help="Output bundle file path")
    parser.add_argument("--inspect", help="Inspect a bundle file")
    parser.add_argument("--export-csv", help="Export a bundle file links back to CSV")
    args = parser.parse_args()

    if args.create:
        cfg = {}
        if Path(args.config).exists():
            with open(args.config, "r", encoding="utf-8") as f:
                cfg = json.load(f)
        links = load_csv_links(Path(args.csv))
        create_bundle(cfg, links, Path(args.out))
        print(f"✓ Created offline bundle at {args.out} with {len(links)} links.")
    elif args.inspect:
        inspect_bundle(Path(args.inspect))
    elif args.export_csv:
        data = load_bundle(Path(args.export_csv))
        out_csv = Path(args.out if args.out != "offline_bundle.json" else "exported_links.csv")
        save_csv_links(out_csv, data.get("links", []))
        print(f"✓ Exported {len(data.get('links', []))} links to {out_csv}")
    else:
        interactive_menu()

if __name__ == "__main__":
    main()
