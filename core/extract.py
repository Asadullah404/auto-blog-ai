"""
core/extract.py — Phase 1: Structured Article Content Extraction
==================================================================
Extracts clean article title, full body text, and hierarchical sections (headings + paragraphs)
from source URLs using newspaper4k, BeautifulSoup4, and lxml fallback parsers.
"""

import json
import re
import sqlite3
from typing import Any, Dict, List, Optional

import requests
from bs4 import BeautifulSoup
from newspaper import Article

from core.checkpoints import get_checkpoint, save_checkpoint


def extract_structured(url: str, timeout: int = 30) -> Dict[str, Any]:
    """
    Downloads and extracts full structured content from a target URL.
    Returns:
        {
            "title": str,
            "raw_text": str,
            "sections": [
                {"heading": str, "body": str},
                ...
            ]
        }
    """
    title = "Untitled"
    raw_text = ""

    # Primary parse with newspaper4k
    try:
        art = Article(url)
        art.download()
        art.parse()
        title = (art.title or "Untitled").strip()
        raw_text = (art.text or "").strip()
    except Exception:
        pass

    # Secondary DOM traversal with requests + BeautifulSoup for heading-wise segmentation
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    }
    r = requests.get(url, timeout=timeout, headers=headers)
    r.raise_for_status()

    soup = BeautifulSoup(r.text, "lxml")

    # Decompose non-content clutter
    for tag in soup(["nav", "footer", "aside", "script", "style", "noscript", "header", "form", "button", "svg"]):
        tag.decompose()

    # Find main article container
    content_area = (
        soup.find("article")
        or soup.find("main")
        or soup.find(class_=re.compile(r"content|post|entry|article|story", re.I))
        or soup.body
    )
    if content_area is None:
        content_area = soup

    # If title wasn't found by newspaper, grab from H1 or <title>
    if title == "Untitled":
        h1 = content_area.find("h1") or soup.find("h1")
        if h1 and h1.get_text(strip=True):
            title = h1.get_text(strip=True)
        elif soup.title and soup.title.get_text(strip=True):
            title = soup.title.get_text(strip=True)

    sections: List[Dict[str, str]] = []
    current_heading = title
    current_body_parts: List[str] = []

    for el in content_area.find_all(["h1", "h2", "h3", "h4", "h5", "h6", "p", "li", "blockquote"], recursive=True):
        tag = el.name
        text = el.get_text(separator=" ", strip=True)
        if not text or len(text) < 5:
            continue

        if tag in ("h1", "h2", "h3", "h4", "h5", "h6"):
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

    # Drop redundant first section if it merely repeats the main title
    if sections and sections[0]["heading"].lower() == title.lower() and not sections[0]["body"]:
        sections = sections[1:]

    # Fallback chunking if no headings were present in DOM
    if not sections and raw_text:
        paras = [p.strip() for p in raw_text.split("\n\n") if p.strip()]
        chunk_size = max(3, len(paras) // 5) if paras else 1
        for i in range(0, len(paras), chunk_size):
            sections.append({
                "heading": f"Part {len(sections) + 1}",
                "body": " ".join(paras[i:i + chunk_size])
            })

    if not raw_text and sections:
        raw_text = "\n\n".join(f"{s['heading']}\n{s['body']}" for s in sections)

    return {
        "title": title,
        "raw_text": raw_text,
        "sections": sections
    }


def phase_extract(url: str, db: sqlite3.Connection, fresh: bool = False) -> Dict[str, Any]:
    """
    Executes Phase 1 with persistent SQLite caching.
    """
    checkpoint_key = "extract_v2"
    if not fresh:
        cached = get_checkpoint(db, checkpoint_key)
        if cached:
            try:
                return json.loads(cached)
            except Exception:
                pass

    extracted_data = extract_structured(url)
    save_checkpoint(db, checkpoint_key, json.dumps(extracted_data, ensure_ascii=False))
    return extracted_data
