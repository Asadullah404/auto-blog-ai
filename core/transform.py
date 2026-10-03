"""
core/transform.py — Phase 2: AI Content Transformation & Skills Infusion
==========================================================================
Re-writes extracted article content into full-length, SEO-optimized, highly engaging
articles with structured schema data. Ingests modular skills (SEO/GEO/AEO),
enforces Master Text Directives, and applies requested formatting architecture.
"""

import json
import os
import platform
import re
import shutil
import sqlite3
import subprocess
import time
from typing import Any, Dict, List, Optional, Tuple

from config.constants import IMAGE_TYPES
from core.checkpoints import get_batch, get_checkpoint, save_batch, save_checkpoint

# Check for agy bridge
BRIDGE_OK = False
try:
    import agy_headless_bridge
    BRIDGE_OK = True
except ImportError:
    BRIDGE_OK = False


# ── AGY Process Execution ───────────────────────────────────────
def strip_ansi(s: str) -> str:
    """Removes ANSI terminal escape sequences."""
    return re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])').sub("", s)


def run_agy_once(prompt: str, timeout: int = 180, idle_timeout: int = 150) -> str:
    """Executes a single agy prompt headless through ConPTY or subprocess."""
    if BRIDGE_OK:
        from agy_headless_bridge import run as agy_run
        result = agy_run(
            prompt,
            timeout=timeout,
            idle_timeout=min(idle_timeout, timeout),
            extra_args=["--dangerously-skip-permissions"]
        )
        if hasattr(result, "__iter__") and not isinstance(result, str):
            return "".join(c if isinstance(c, str) else str(c) for c in result)
        return result or ""

    if platform.system() != "Windows":
        import pty, select
        master, slave = pty.openpty()
        proc = subprocess.Popen(
            ["agy", "--dangerously-skip-permissions", "-p", prompt],
            stdin=slave, stdout=slave, stderr=slave
        )
        os.close(slave)
        chunks = []
        deadline = time.time() + timeout
        while True:
            rem = deadline - time.time()
            if rem <= 0:
                proc.kill()
                break
            r, _, _ = select.select([master], [], [], min(rem, 1.0))
            if r:
                try:
                    chunk = os.read(master, 4096)
                    if chunk:
                        chunks.append(chunk.decode("utf-8", errors="replace"))
                    else:
                        break
                except OSError:
                    break
            elif proc.poll() is not None:
                break
        try:
            os.close(master)
        except OSError:
            pass
        proc.wait()
        return "".join(chunks)

    extra_kwargs = {}
    if sys.platform == "win32":
        si = subprocess.STARTUPINFO()
        si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        si.wShowWindow = 0
        extra_kwargs["startupinfo"] = si
        extra_kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW

    r = subprocess.run(
        ["agy", "--dangerously-skip-permissions", "-p", prompt],
        capture_output=True, text=True, timeout=timeout, **extra_kwargs
    )
    return r.stdout or r.stderr


def run_agy(prompt: str, timeout: int = 180, retries: int = 2) -> str:
    """Wraps run_agy_once with retries for transient empty outputs."""
    attempts = max(1, retries + 1)
    last_output = ""
    for attempt in range(1, attempts + 1):
        last_output = run_agy_once(prompt, timeout=timeout)
        if last_output and last_output.strip():
            return last_output
        if attempt < attempts:
            time.sleep(2)
    return last_output


# ── JSON Recovery & Parsing ─────────────────────────────────────
def clean_raw_llm_output(raw: str) -> str:
    """Extracts JSON substring from LLM markdown code blocks or brackets."""
    raw = strip_ansi(raw).strip()
    m = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', raw, re.IGNORECASE)
    if m:
        return m.group(1).strip()
    fb = raw.find('{')
    fl = raw.find('[')
    if fb != -1 and (fl == -1 or fb < fl):
        lb = raw.rfind('}')
        return raw[fb:lb + 1] if lb > fb else raw[fb:]
    elif fl != -1:
        ll = raw.rfind(']')
        return raw[fl:ll + 1] if ll > fl else raw[fl:]
    return raw


clean_json_response = clean_raw_llm_output


def fix_common_json_errors(s: str) -> str:
    """Fixes trailing commas before closing braces/brackets."""
    return re.sub(r',\s*([}\]])', r'\1', s)


def escape_stray_quotes(s: str) -> str:
    """Escapes internal double quotes inside JSON string values."""
    out = []
    i = 0
    n = len(s)
    in_str = False
    while i < n:
        ch = s[i]
        if ch == '\\' and in_str:
            out.append(ch)
            if i + 1 < n:
                out.append(s[i + 1])
                i += 2
            else:
                i += 1
            continue
        if ch == '"':
            if not in_str:
                in_str = True
                out.append(ch)
                i += 1
                continue
            j = i + 1
            while j < n and s[j] in ' \t\r\n':
                j += 1
            if j >= n or s[j] in ':,}]':
                in_str = False
                out.append(ch)
                i += 1
                continue
            out.append("'")
            i += 1
            continue
        out.append(ch)
        i += 1
    return "".join(out)


def heal_truncated_json(s: str) -> str:
    """Appends closing braces/brackets to incomplete JSON streams."""
    s = s.rstrip()
    if not s:
        return "{}"
    if s.endswith(','):
        s = s[:-1].rstrip()
    open_curly = s.count('{') - s.count('}')
    open_square = s.count('[') - s.count(']')
    if open_square > 0:
        s += ']' * open_square
    if open_curly > 0:
        s += '}' * open_curly
    return s


def parse_json(raw: str, expected_sections: int = 0) -> Any:
    """Fault-tolerant JSON parser with regex extraction fallbacks."""
    cleaned = clean_raw_llm_output(raw)
    try:
        return json.loads(cleaned)
    except Exception:
        pass

    try:
        fixed = fix_common_json_errors(escape_stray_quotes(cleaned))
        return json.loads(fixed)
    except Exception:
        pass

    try:
        healed = heal_truncated_json(fixed)
        return json.loads(healed)
    except Exception:
        pass

    # Regex extraction of sections array
    sec_match = re.search(r'"sections"\s*:\s*(\[[\s\S]*?\])', cleaned)
    if sec_match:
        try:
            secs = json.loads(fix_common_json_errors(sec_match.group(1)))
            return {"sections": secs}
        except Exception:
            pass

    return {}


# ── Format & Image Style Rules ──────────────────────────────────
def get_format_instructions(fmt: str = "paragraphs") -> Tuple[str, str, str]:
    """Returns (rules_text, example_json_fragment, label) for the selected article format."""
    fmt = (fmt or "paragraphs").lower()
    if fmt == "point_wise":
        rules = (
            "- FORMAT REQUIREMENT: POINT-WISE / BULLET POINTS:\n"
            "  * First item in 'paragraphs' MUST be 1 introductory context paragraph (40-60 words).\n"
            "  * Followed by 3 to 6 distinct point-wise strings, each starting with: '- **Key Concept**: detailed actionable explanation'.\n"
            "  * Conclude with 1 summary sentence string providing a takeaway or next step."
        )
        example = '["Introductory context for this section.", "- **First Point**: Detailed explanation of first key aspect.", "- **Second Point**: Practical insight or guideline.", "- **Third Point**: Critical factor to keep in mind.", "Closing takeaway sentence."]'
        label = "Point-Wise / Bullet Points"
    elif fmt == "subheadings":
        rules = (
            "- FORMAT REQUIREMENT: SUB-HEADING WISE (H2 + H3):\n"
            "  * First item in 'paragraphs' MUST be 1 overview paragraph under the main H2.\n"
            "  * Followed by 2 to 3 distinct subsections. Each subsection MUST begin with a string '### Subheading Title' (H3) followed immediately by 1-2 focused explanatory paragraphs."
        )
        example = '["Overview of this section.", "### First Subheading Title", "In-depth explanation focusing on this specific sub-topic.", "### Second Subheading Title", "Detailed explanation for the second sub-topic."]'
        label = "Sub-Heading Wise (H2 + H3)"
    elif fmt == "hybrid":
        rules = (
            "- FORMAT REQUIREMENT: HYBRID (PARAGRAPHS + BULLET POINTS):\n"
            "  * Each section 'paragraphs' MUST contain 1 to 2 rich explanatory narrative paragraphs.\n"
            "  * Followed by 3 to 5 bullet point strings starting with '- **Key Takeaway**: ' highlighting essential facts, tips, or takeaways."
        )
        example = '["In-depth explanatory paragraph detailing the background and importance...", "- **Key Takeaway 1**: Actionable summary of the primary fact.", "- **Key Takeaway 2**: Practical application or pro tip.", "- **Key Takeaway 3**: Common pitfall or expert recommendation."]'
        label = "Hybrid (Paragraphs + Bullet Points)"
    else:
        rules = "- Each section 'paragraphs' must have 2-4 comprehensive narrative paragraphs (80-120 words each)."
        example = '["Paragraph 1 text exploring the concept...", "Paragraph 2 text providing further details and facts..."]'
        label = "Standard Paragraphs"

    return rules, example, label


def get_image_style_guidance(cfg: Dict[str, Any]) -> Tuple[str, str]:
    """Builds hints for LLM feature and heading image prompt generation."""
    img_type_key = cfg.get("image_type", "photo")
    type_style = ""
    if img_type_key == "custom":
        type_style = cfg.get("image_type_custom", "").strip()
    elif img_type_key in IMAGE_TYPES:
        type_style = IMAGE_TYPES[img_type_key]["prompt"]

    master_img = cfg.get("master_image_prompt", "").strip()
    apply_all = cfg.get("apply_master_to_all_images", True)
    feat_master = cfg.get("feature_image_master_prompt", "").strip()
    head_master = cfg.get("heading_image_master_prompt", "").strip()

    feat_parts = ["hero scene 50 words"]
    if type_style:
        feat_parts.append(f"visual style: {type_style}")
    if master_img and apply_all:
        feat_parts.append(master_img)
    if feat_master:
        feat_parts.append(feat_master)

    head_parts = ["scene"]
    if type_style:
        head_parts.append(f"visual style: {type_style}")
    if master_img and apply_all:
        head_parts.append(master_img)
    if head_master:
        head_parts.append(head_master)

    return ", ".join(feat_parts), ", ".join(head_parts)


def build_sections_block(sections: List[Dict[str, str]], chars_per_section: int = 2000) -> str:
    """Formats sections into readable prompt blocks."""
    lines = []
    for i, s in enumerate(sections):
        lines.append(f"[{i + 1}] HEADING: {s['heading']}")
        body = s.get("body", "").strip()
        if body:
            lines.append(f"    BODY: {body[:chars_per_section]}")
        lines.append("")
    return "\n".join(lines)


# ── Main Transform Function ─────────────────────────────────────
def phase_transform(
    extracted: Dict[str, Any],
    url: str,
    db: sqlite3.Connection,
    skills_text: str,
    cfg: Dict[str, Any],
    category_override: str = "",
    fresh: bool = False
) -> Dict[str, Any]:
    """
    Executes Phase 2 with multi-batch checkpointing and format construction.
    """
    checkpoint_key = "transform_v3"
    if not fresh:
        cached = get_checkpoint(db, checkpoint_key)
        if cached:
            try:
                res = json.loads(cached)
                if category_override and res.get("category") != category_override:
                    res["category"] = category_override
                    save_checkpoint(db, checkpoint_key, json.dumps(res, ensure_ascii=False))
                return res
            except Exception:
                pass

    title = extracted["title"]
    sections = extracted.get("sections", [])
    if not sections:
        sections = [{"heading": title, "body": extracted.get("raw_text", "")}]

    fmt = cfg.get("article_format", "paragraphs")
    format_rules, paragraphs_example, format_label = get_format_instructions(fmt)
    feat_hint, head_hint = get_image_style_guidance(cfg)

    master_directive = cfg.get("master_text_prompt", "").strip()
    master_directive_text = f"- MASTER CONTENT & TONE DIRECTIVE:\n  {master_directive}" if master_directive else ""

    batch_size = cfg.get("batch_size", 3)
    batches = [sections[i:i + batch_size] for i in range(0, len(sections), batch_size)]

    # Batch 0 + Metadata
    base_meta_cached = get_batch(db, -1)
    batch0_cached = get_batch(db, 0)

    if base_meta_cached and batch0_cached:
        base = base_meta_cached
        all_sections = list(batch0_cached)
    else:
        rewrite_prompt = f"""{skills_text}
---
## YOUR TASK
Rewrite this article for SEO, preserving ALL {len(batches[0])} sections.
Every section MUST appear in your output — do not merge or drop any.

SOURCE TITLE: {title}
SOURCE SECTIONS:
{build_sections_block(batches[0], cfg.get("chars_per_section", 2000))}

RULES:
- Output ONLY valid JSON, no markdown fences, no preamble.
- NEVER use a double-quote character " anywhere inside a string value, not even escaped. Use single quotes ' ' instead.
- Do NOT use literal linebreaks inside JSON strings.
- Return exactly {len(batches[0])} section objects in "sections".
{format_rules}
{master_directive_text}
- Include a "conclusion" object.

JSON schema:
{{
  "title": "SEO title",
  "meta_description": "145-158 chars",
  "keywords": "kw1, kw2, kw3, kw4, kw5",
  "category": "Category",
  "intro": "article opener",
  "feature_image_prompt": "{feat_hint}",
  "sections": [
    {{"heading":"H2","paragraphs":{paragraphs_example},"image_prompt":"{head_hint}","image_alt":"alt","snippet":"answer"}}
  ],
  "conclusion": {{"heading":"Wrap-up H2","paragraphs":["para1","para2"]}}
}}
"""
        raw = run_agy(rewrite_prompt, timeout=cfg.get("agy_timeout", 180))
        base = parse_json(raw, len(batches[0]))

        if not isinstance(base, dict) or not base.get("sections"):
            base = {
                "title": title,
                "meta_description": f"Complete guide on {title}",
                "keywords": title,
                "category": category_override or "General",
                "intro": f"Welcome to our comprehensive guide on {title}.",
                "feature_image_prompt": title,
                "sections": [
                    {
                        "heading": s["heading"],
                        "paragraphs": [s.get("body", "")[:600] or f"Complete overview of {s['heading']}."],
                        "image_prompt": s["heading"],
                        "image_alt": s["heading"][:120],
                        "snippet": s.get("body", "")[:200] or s["heading"],
                    }
                    for s in batches[0]
                ],
                "conclusion": {
                    "heading": "Final Thoughts",
                    "paragraphs": ["Thank you for reading this guide.", "Apply these steps today."]
                }
            }

        meta_only = {k: v for k, v in base.items() if k != "sections"}
        save_batch(db, -1, meta_only)
        save_batch(db, 0, base.get("sections", []))
        all_sections = list(base.get("sections", []))

    # Batches 1..N
    for bi, batch in enumerate(batches[1:], start=1):
        cached_batch = get_batch(db, bi)
        if cached_batch is not None:
            all_sections.extend(cached_batch)
            continue

        sec_prompt = f"""{skills_text}
---
Rewrite these {len(batch)} sections from "{title}".
Return ONLY: {{"sections": [ ... ]}}

RULES:
- Valid JSON only, no markdown, no preamble.
- Exactly {len(batch)} section objects.
- NEVER use a double-quote character " inside any string value — use single quotes ' ' instead.
- Do NOT use literal linebreaks inside JSON strings.
{format_rules}
{master_directive_text}

Sections:
{build_sections_block(batch, cfg.get("chars_per_section", 2000))}
"""
        raw_sec = run_agy(sec_prompt, timeout=cfg.get("agy_timeout", 180))
        parsed_sec = parse_json(raw_sec, len(batch)).get("sections", [])

        if not parsed_sec:
            parsed_sec = [
                {
                    "heading": s["heading"],
                    "paragraphs": [s.get("body", "")[:600] or f"Guide to {s['heading']}."],
                    "image_prompt": s["heading"],
                    "image_alt": s["heading"][:120],
                    "snippet": s.get("body", "")[:200] or s["heading"],
                }
                for s in batch
            ]

        save_batch(db, bi, parsed_sec)
        all_sections.extend(parsed_sec)

    # Conclusion & Assembly
    meta = get_batch(db, -1) or base
    conclusion = meta.get("conclusion")
    if not conclusion:
        conclusion = {
            "heading": "Conclusion",
            "paragraphs": ["In summary, this guide covered all key aspects.", "Put these insights into practice."]
        }

    final_structured = {
        "title": meta.get("title", title),
        "meta_description": meta.get("meta_description", f"Guide to {title}"),
        "keywords": meta.get("keywords", title),
        "category": category_override or meta.get("category", "General"),
        "intro": meta.get("intro", f"Explore our guide on {title}."),
        "feature_image_prompt": meta.get("feature_image_prompt", title),
        "sections": all_sections,
        "conclusion": conclusion
    }

    save_checkpoint(db, checkpoint_key, json.dumps(final_structured, ensure_ascii=False))
    return final_structured
