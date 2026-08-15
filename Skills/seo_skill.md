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
