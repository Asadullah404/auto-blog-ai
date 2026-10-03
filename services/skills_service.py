"""
services/skills_service.py — Modular AI Skills Scanner & Manager
===================================================================
Scans the Skills/ directory for all Markdown instruction files (*.md).
Seeds baseline SEO, GEO, and AEO skills if absent, parses active directives,
and generates combined context strings for LLM injection.
"""

from pathlib import Path
from typing import Any, Dict, List, Optional

SEO_SKILL_DEFAULT = """# SEO Copywriting Skill v3.0
## Purpose
Rewrite web content for maximum on-page SEO (ranking in traditional search)
AND GEO — Generative Engine Optimization (being directly cited, quoted, or
summarized by AI answer engines: Google AI Overviews, ChatGPT, Perplexity,
Gemini) — while staying human, engaging, and accurate.

## Core SEO Rules
1. **Title**: Keep primary keyword within first 60 chars. Use power words (Ultimate, Complete, Best, How to, Why).
2. **Meta Description**: 145-158 chars, include primary keyword, include a CTA or benefit.
3. **Headings (H2)**: Each H2 must contain a long-tail keyword variant.
4. **Paragraphs**: First sentence of each paragraph should contain a keyword. Aim 80-120 words per paragraph.
5. **Keyword Density**: Primary keyword ~1-1.5% of total text. LSI/semantic keywords distributed naturally.
6. **Readability**: Flesch reading ease > 60. Short sentences (avg < 20 words). Active voice.
7. **E-E-A-T signals**: Include specific facts, numbers, examples, and authoritative claims.
8. **Featured snippet optimization**: For each section, include one concise 40-60 word answer block.
"""

GEO_SKILL_DEFAULT = """# GEO (Generative Engine Optimization) Skill v1.0
## Purpose
Optimize content to maximize direct citations, summaries, and source attribution by AI generative search engines (Google AI Overviews, ChatGPT Search, Perplexity AI, Microsoft Copilot, Claude).

## Core GEO Rules
1. **Answer-First Inverted Pyramid**:
   - Begin every section with a direct, assertive 1-2 sentence response to the heading's query.
   - Put the primary conclusion or fact in the very first 30 words of each section.
2. **Citable Standalone Claims**:
   - Ensure key evidentiary sentences are grammatically complete without relying on relative pronouns.
   - Sentences should remain informative when extracted out of context by an AI snippet parser.
3. **High Information Density (Information Gain)**:
   - Eliminate filler phrases ('In today's fast-paced world', 'It is important to remember').
   - Maximize named entities (tools, technologies, recognized organizations, specific standards).
   - Use concrete statistics, quantitative ranges, dates, and empirical benchmarks instead of vague adjectives.
4. **Definition & Contrast Anchors**:
   - Define new terms immediately upon first mention with a clear 'is a [category] that [function]' pattern.
   - Include comparison statements ('Unlike traditional X, Y achieves Z through...') which AI engines favor for comparative queries.
"""

AEO_SKILL_DEFAULT = """# AEO (Answer Engine Optimization) Skill v1.0
## Purpose
Optimize content for zero-click direct answers, featured snippets, voice search, and conversational query resolution in Google, Perplexity, Siri, and LLM chat interfaces.

## Core AEO Rules
1. **Direct Snippet Targeting (40-60 Word Core Answer)**:
   - For every question-based heading, provide a crystal-clear, self-contained definition or summary answer in exactly 40-60 words directly beneath the heading.
   - Match the grammatical form of the query: 'How to...' requires imperative steps; 'What is...' requires a categorical definition; 'Why does...' requires causal explanation.
2. **Structured Step & Process Formats**:
   - When explaining processes, workflows, or comparisons, use distinct sequential list items or bullet anchors.
   - Use bold lead-ins for each item (e.g. '- **Step Name**: actionable directive').
3. **Query-Intent Alignment**:
   - Address the four primary search intents explicitly within each topic:
     * Informational (What is it, how it works)
     * Comparative (Pros vs. cons, alternatives)
     * Transactional / Practical (Pricing, prerequisites, implementation)
     * Troubleshooting (Common mistakes, pitfalls to avoid)
"""


class SkillsService:
    def __init__(self, skills_dir: Path = Path("Skills")):
        self.skills_dir = Path(skills_dir)
        self.ensure_default_skills()

    def ensure_default_skills(self) -> None:
        """Seeds default skills if missing."""
        self.skills_dir.mkdir(parents=True, exist_ok=True)
        defaults = {
            "seo_skill.md": SEO_SKILL_DEFAULT,
            "geo_skill.md": GEO_SKILL_DEFAULT,
            "aeo_skill.md": AEO_SKILL_DEFAULT,
        }
        for fname, content in defaults.items():
            p = self.skills_dir / fname
            if not p.exists():
                try:
                    p.write_text(content, encoding="utf-8")
                except Exception:
                    pass

    def list_skills(self) -> List[Dict[str, Any]]:
        """Scans and returns all available skill files with metadata."""
        self.ensure_default_skills()
        skills = []
        for p in sorted(self.skills_dir.glob("*.md")):
            try:
                txt = p.read_text(encoding="utf-8")
                # Extract first heading
                lines = [line.strip() for line in txt.splitlines() if line.strip()]
                title = lines[0].lstrip("#").strip() if lines else p.stem
                skills.append({
                    "filename": p.name,
                    "title": title,
                    "chars": len(txt),
                    "path": str(p),
                    "content": txt,
                })
            except Exception as e:
                skills.append({
                    "filename": p.name,
                    "title": p.name,
                    "chars": 0,
                    "path": str(p),
                    "error": str(e),
                })
        return skills

    def get_skill_content(self, filename: str) -> Optional[str]:
        p = self.skills_dir / filename
        if p.exists():
            return p.read_text(encoding="utf-8")
        return None

    def save_skill(self, filename: str, content: str) -> bool:
        if not filename.endswith(".md"):
            filename = f"{filename}.md"
        p = self.skills_dir / filename
        p.write_text(content, encoding="utf-8")
        return True

    def delete_skill(self, filename: str) -> bool:
        p = self.skills_dir / filename
        if p.exists() and filename not in ("seo_skill.md", "geo_skill.md", "aeo_skill.md"):
            p.unlink()
            return True
        return False

    def build_combined_skills_prompt(self, enabled_files: Optional[List[str]] = None) -> str:
        """Combines all selected skill files into a single structured prompt."""
        self.ensure_default_skills()
        all_skills = sorted(list(self.skills_dir.glob("*.md")))
        if enabled_files:
            enabled_set = set(enabled_files)
            all_skills = [s for s in all_skills if s.name in enabled_set]

        blocks = []
        for s in all_skills:
            try:
                txt = s.read_text(encoding="utf-8").strip()
                if txt:
                    blocks.append(f"# === SKILL DIRECTIVE: {s.name} ===\n{txt}")
            except Exception:
                pass

        return "\n\n".join(blocks) if blocks else SEO_SKILL_DEFAULT
