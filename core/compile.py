"""
core/compile.py — Phase 5: Responsive HTML Compilation & Schema Generator
===========================================================================
Compiles the structured article content, rendered images, and schema metadata
into a self-contained, responsive, beautifully styled HTML document (final_output.html).
Includes OpenGraph tags, Twitter Cards, Schema.org Article & FAQPage JSON-LD,
Table of Contents, and styled typography.
"""

from datetime import datetime
import json
from pathlib import Path
import re
from typing import Any, Dict, List

from jinja2 import Template

HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{{ data.title }}</title>
<meta name="description" content="{{ data.meta_description }}">
<meta name="keywords" content="{{ data.keywords }}">

<!-- Open Graph / Facebook -->
<meta property="og:type" content="article">
<meta property="og:title" content="{{ data.title }}">
<meta property="og:description" content="{{ data.meta_description }}">
<meta property="og:image" content="{{ feature_img }}">

<!-- Twitter Cards -->
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="{{ data.title }}">
<meta name="twitter:description" content="{{ data.meta_description }}">
<meta name="twitter:image" content="{{ feature_img }}">

<!-- Schema.org JSON-LD -->
<script type="application/ld+json">
{{ schema_json }}
</script>

<style>
@import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&family=Playfair+Display:wght@700;900&display=swap');
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
:root {
  --bg-main: #f8fafc;
  --surface: #ffffff;
  --text-main: #0f172a;
  --text-muted: #475569;
  --accent: #0284c7;
  --accent-soft: rgba(2, 132, 199, 0.08);
  --border: #e2e8f0;
  --radius-lg: 16px;
  --radius-md: 10px;
  --shadow: 0 10px 30px -10px rgba(0, 0, 0, 0.07);
}
body {
  background: var(--bg-main);
  color: var(--text-main);
  font-family: 'Plus Jakarta Sans', -apple-system, BlinkMacSystemFont, sans-serif;
  line-height: 1.8;
  -webkit-font-smoothing: antialiased;
}
.hero {
  position: relative;
  width: 100%;
  max-height: 600px;
  overflow: hidden;
  background: #0f172a;
}
.hero img {
  display: block;
  width: 100%;
  height: 600px;
  object-fit: cover;
  opacity: 0.85;
}
.hero-overlay {
  position: absolute;
  inset: 0;
  background: linear-gradient(180deg, rgba(15, 23, 42, 0.1) 0%, rgba(15, 23, 42, 0.85) 100%);
  display: flex;
  align-items: flex-end;
  padding: 48px 24px;
}
.hero-inner {
  max-width: 900px;
  margin: 0 auto;
  width: 100%;
}
.badge-category {
  display: inline-block;
  padding: 6px 14px;
  background: var(--accent);
  color: #fff;
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 1.5px;
  text-transform: uppercase;
  border-radius: 30px;
  margin-bottom: 16px;
}
.hero h1 {
  font-family: 'Playfair Display', Georgia, serif;
  font-size: clamp(2rem, 4.5vw, 3.2rem);
  line-height: 1.2;
  color: #ffffff;
  margin-bottom: 16px;
}
.hero-meta {
  display: flex;
  align-items: center;
  gap: 16px;
  color: #cbd5e1;
  font-size: 14px;
  font-weight: 500;
}
main {
  max-width: 900px;
  margin: 0 auto;
  padding: 56px 24px 100px;
}
.intro-card {
  background: var(--surface);
  border-radius: var(--radius-lg);
  padding: 36px 40px;
  border-left: 5px solid var(--accent);
  box-shadow: var(--shadow);
  margin-bottom: 56px;
  font-size: 1.15rem;
  color: #1e293b;
  line-height: 1.85;
}
.toc-card {
  background: var(--surface);
  border-radius: var(--radius-lg);
  padding: 30px 36px;
  box-shadow: var(--shadow);
  margin-bottom: 56px;
  border: 1px solid var(--border);
}
.toc-title {
  font-size: 18px;
  font-weight: 700;
  margin-bottom: 16px;
  color: #0f172a;
}
.toc-list {
  list-style: none;
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.toc-list li a {
  color: var(--accent);
  text-decoration: none;
  font-weight: 500;
  font-size: 15px;
  transition: color 0.2s ease;
}
.toc-list li a:hover {
  text-decoration: underline;
  color: #0369a1;
}
.article-section {
  margin-bottom: 64px;
}
.section-heading {
  font-family: 'Playfair Display', Georgia, serif;
  font-size: clamp(1.4rem, 3vw, 2rem);
  color: #0f172a;
  margin-bottom: 20px;
  line-height: 1.3;
}
.section-image-wrap {
  border-radius: var(--radius-md);
  overflow: hidden;
  box-shadow: var(--shadow);
  margin: 24px 0 28px;
}
.section-image-wrap img {
  display: block;
  width: 100%;
  height: auto;
}
.section-body p {
  font-size: 1.05rem;
  color: #334155;
  margin-bottom: 18px;
  line-height: 1.8;
}
.section-body .sec-h3 {
  font-size: 1.25rem;
  font-weight: 700;
  color: #0f172a;
  margin: 28px 0 12px;
}
.section-body ul.article-list, .section-body ol.article-list {
  margin: 16px 0 24px 28px;
}
.section-body ul.article-list li, .section-body ol.article-list li {
  font-size: 1.02rem;
  color: #334155;
  margin-bottom: 10px;
  line-height: 1.7;
}
.snippet-box {
  background: var(--accent-soft);
  border: 1px solid rgba(2, 132, 199, 0.2);
  border-radius: var(--radius-md);
  padding: 20px 24px;
  margin: 24px 0;
  font-size: 1rem;
  color: #0369a1;
  font-weight: 500;
}
.conclusion-card {
  background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%);
  color: #ffffff;
  border-radius: var(--radius-lg);
  padding: 44px 40px;
  margin-top: 60px;
  box-shadow: var(--shadow);
}
.conclusion-card h2 {
  font-family: 'Playfair Display', Georgia, serif;
  font-size: clamp(1.4rem, 3vw, 2rem);
  color: #ffffff;
  margin-bottom: 18px;
}
.conclusion-card p {
  font-size: 1.05rem;
  color: #e2e8f0;
  line-height: 1.8;
  margin-bottom: 16px;
}
.pinterest-card {
  display: flex;
  justify-content: center;
  margin-top: 48px;
}
.pinterest-card img {
  max-width: 480px;
  width: 100%;
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow);
}
</style>
</head>
<body>

<header class="hero">
  <img src="{{ feature_img }}" alt="{{ data.title }}">
  <div class="hero-overlay">
    <div class="hero-inner">
      <span class="badge-category">{{ data.category }}</span>
      <h1>{{ data.title }}</h1>
      <div class="hero-meta">
        <span>🕒 {{ read_time }} min read</span>
        <span>•</span>
        <span>📅 {{ generated_at }}</span>
        <span>•</span>
        <span>📚 {{ section_count }} Sections</span>
      </div>
    </div>
  </div>
</header>

<main>
  <div class="intro-card">
    <p>{{ data.intro }}</p>
  </div>

  <div class="toc-card">
    <div class="toc-title">Table of Contents</div>
    <ul class="toc-list">
      {% for sec in data.sections %}
      <li><a href="#section-{{ loop.index }}">{{ loop.index }}. {{ sec.heading }}</a></li>
      {% endfor %}
    </ul>
  </div>

  {% for sec in data.sections %}
  <section class="article-section" id="section-{{ loop.index }}">
    <h2 class="section-heading">{{ sec.heading }}</h2>

    {% if sec.img %}
    <div class="section-image-wrap">
      <img src="{{ sec.img }}" alt="{{ sec.image_alt or sec.heading }}" loading="lazy">
    </div>
    {% endif %}

    <div class="section-body">
      {{ sec.rendered_html | safe }}
    </div>

    {% if sec.snippet %}
    <div class="snippet-box">
      <strong>Key Takeaway:</strong> {{ sec.snippet }}
    </div>
    {% endif %}
  </section>
  {% endfor %}

  {% if data.conclusion %}
  <div class="conclusion-card">
    <h2>{{ data.conclusion.heading }}</h2>
    {{ data.conclusion.rendered_html | safe }}
  </div>
  {% endif %}

  {% if data.content_html and not data.sections %}
  <div class="article-body">
    {{ data.content_html | safe }}
  </div>
  {% endif %}

  {% if pin_img %}
  <div class="pinterest-card">
    <img src="{{ pin_img }}" alt="Pinterest Pin: {{ data.title }}" loading="lazy">
  </div>
  {% endif %}
</main>

</body>
</html>
"""


def format_inline_markdown(text: str) -> str:
    """Converts bold and italic markdown markers into valid HTML tags."""
    if not text:
        return ""
    text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"__(.+?)__", r"<strong>\1</strong>", text)
    text = re.sub(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)", r"<em>\1</em>", text)
    return text


def render_content_to_html(paragraphs: List[Any]) -> str:
    """Renders paragraphs, bullet points, and subheadings into styled HTML."""
    if not paragraphs:
        return ""

    html_parts: List[str] = []
    list_items: List[str] = []

    def flush_list():
        nonlocal list_items
        if list_items:
            items_html = "\n".join(f"      <li>{format_inline_markdown(it)}</li>" for it in list_items)
            html_parts.append(f'    <ul class="article-list">\n{items_html}\n    </ul>')
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
            html_parts.append(f'    <h3 class="sec-h3">{format_inline_markdown(h_text)}</h3>')
        elif text.startswith("## ") and not text.startswith("### "):
            flush_list()
            h_text = text[3:].strip()
            html_parts.append(f'    <h3 class="sec-h3">{format_inline_markdown(h_text)}</h3>')
        elif text.startswith("- ") or text.startswith("* ") or text.startswith("• ") or re.match(r"^\d+\.\s+", text):
            lines = [l.strip() for l in text.splitlines() if l.strip()]
            for line in lines:
                if line.startswith("- ") or line.startswith("* ") or line.startswith("• "):
                    list_items.append(line[2:].strip())
                elif re.match(r"^\d+\.\s+", line):
                    list_items.append(re.sub(r"^\d+\.\s+", "", line).strip())
                else:
                    flush_list()
                    html_parts.append(f'    <p>{format_inline_markdown(line)}</p>')
        else:
            flush_list()
            html_parts.append(f'    <p>{format_inline_markdown(text)}</p>')

    flush_list()
    return "\n".join(html_parts)


def estimate_read_time(structured: Dict[str, Any]) -> int:
    """Calculates read time in minutes based on ~200 WPM."""
    words = sum(len(str(p).split()) for s in structured.get("sections", []) for p in s.get("paragraphs", []))
    words += len(str(structured.get("intro", "")).split())
    words += sum(len(str(p).split()) for p in (structured.get("conclusion") or {}).get("paragraphs", []))
    return max(1, round(words / 200))


def build_schema_json(structured: Dict[str, Any], feature_img_url: str) -> str:
    """Builds Schema.org Article and FAQPage JSON-LD graph."""
    faqs = []
    for faq in structured.get("faqs", []):
        q = faq.get("question") or faq.get("q")
        a = faq.get("answer") or faq.get("a")
        if q and a:
            faqs.append({
                "@type": "Question",
                "name": q,
                "acceptedAnswer": {
                    "@type": "Answer",
                    "text": a
                }
            })

    for s in structured.get("sections", []):
        if s.get("snippet") and "?" in s.get("heading", ""):
            faqs.append({
                "@type": "Question",
                "name": s["heading"],
                "acceptedAnswer": {
                    "@type": "Answer",
                    "text": s["snippet"]
                }
            })

    schema_graph = {
        "@context": "https://schema.org",
        "@graph": [
            {
                "@type": "Article",
                "headline": structured.get("title", ""),
                "description": structured.get("meta_description", ""),
                "image": feature_img_url,
                "author": {
                    "@type": "Organization",
                    "name": "Content Pipeline"
                },
                "datePublished": datetime.now().isoformat()
            }
        ]
    }

    if faqs:
        schema_graph["@graph"].append({
            "@type": "FAQPage",
            "mainEntity": faqs
        })

    return json.dumps(schema_graph, indent=2, ensure_ascii=False)


def phase_compile(
    structured: Dict[str, Any],
    rendered: Dict[str, Any],
    out_dir: Path
) -> Path:
    """
    Executes Phase 5: Compiles standalone HTML document and saves to final_output.html.
    """
    sections = structured.get("sections", [])
    for i, s in enumerate(sections):
        s["rendered_html"] = render_content_to_html(s.get("paragraphs", []))
        if i < len(rendered["sections"]):
            rp = Path(rendered["sections"][i])
            try:
                s["img"] = str(rp.relative_to(out_dir)).replace("\\", "/")
            except ValueError:
                s["img"] = str(rp).replace("\\", "/")
        else:
            s["img"] = None

    if structured.get("conclusion") and isinstance(structured["conclusion"], dict):
        structured["conclusion"]["rendered_html"] = render_content_to_html(
            structured["conclusion"].get("paragraphs", [])
        )

    feature_rel = str(rendered["feature"]).replace("\\", "/")
    pin_rel = str(rendered.get("pin") or "").replace("\\", "/") if rendered.get("pin") else None
    schema_json = build_schema_json(structured, feature_rel)

    html_content = Template(HTML_TEMPLATE).render(
        data=structured,
        feature_img=feature_rel,
        pin_img=pin_rel,
        generated_at=datetime.now().strftime("%d %b %Y, %H:%M"),
        section_count=len(sections),
        read_time=estimate_read_time(structured),
        schema_json=schema_json
    )

    out_file = out_dir / "final_output.html"
    out_file.write_text(html_content, encoding="utf-8")
    return out_file


def compile_html_document(
    structured: Dict[str, Any],
    feature_img: str = "feature.webp",
    pin_img: Optional[str] = None
) -> str:
    """
    Compiles a structured article dictionary into a responsive HTML5 string
    including Schema.org JSON-LD Article and FAQPage structures.
    """
    schema_json = build_schema_json(structured, feature_img)
    return Template(HTML_TEMPLATE).render(
        data=structured,
        feature_img=feature_img,
        pin_img=pin_img,
        generated_at=datetime.now().strftime("%d %b %Y, %H:%M"),
        section_count=len(structured.get("sections", [])),
        read_time=estimate_read_time(structured),
        schema_json=schema_json
    )

