"""
tests/test_core.py — Unit Tests for Core Pipeline Modules
===========================================================
Validates configuration dimensions, checkpoint database, skills scanning,
HTML compilation, and resilient JSON cleaning.
"""

import json
import shutil
import tempfile
import unittest
from pathlib import Path

from config.settings import resolve_dimensions, load_config
from core.checkpoints import CheckpointManager
from core.compile import compile_html_document
from core.transform import clean_json_response
from services.skills_service import SkillsService


class TestCoreModules(unittest.TestCase):
    def setUp(self):
        self.test_dir = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_resolve_dimensions(self):
        """Test preset and custom dimension resolution."""
        # Presets
        w_hd, h_hd = resolve_dimensions("hd", aspect=9 / 16)
        self.assertEqual(w_hd, 1200)
        self.assertEqual(h_hd, 675)

        w_fhd, h_fhd = resolve_dimensions("fhd", aspect=9 / 16)
        self.assertEqual(w_fhd, 1920)
        self.assertEqual(h_fhd, 1080)

        # Named Resolution Presets
        w_land, h_land = resolve_dimensions("landscape_16_9")
        self.assertEqual(w_land, 1200)
        self.assertEqual(h_land, 675)

        w_og, h_og = resolve_dimensions("opengraph_1200_630")
        self.assertEqual(w_og, 1200)
        self.assertEqual(h_og, 630)

        w_sq, h_sq = resolve_dimensions("square_1_1")
        self.assertEqual(w_sq, 1024)
        self.assertEqual(h_sq, 1024)

        # Custom WIDTHxHEIGHT
        w_cust, h_cust = resolve_dimensions("1000x1500")
        self.assertEqual(w_cust, 1000)
        self.assertEqual(h_cust, 1500)

        w_c2, h_c2 = resolve_dimensions("1600x900")
        self.assertEqual(w_c2, 1600)
        self.assertEqual(h_c2, 900)

    def test_checkpoint_manager(self):
        """Test SQLite checkpoint persistence and retrieval."""
        db_path = self.test_dir / "test_pipeline.db"
        mgr = CheckpointManager(db_path=db_path)
        mgr.init_db()

        # Save checkpoint
        mgr.save_checkpoint(
            url="https://example.com/test-article",
            status="completed",
            phase=5,
            data={"title": "Test Title", "word_count": 500}
        )

        chk = mgr.get_checkpoint("https://example.com/test-article")
        self.assertIsNotNone(chk)
        self.assertEqual(chk["status"], "completed")
        self.assertEqual(chk["phase"], 5)
        self.assertEqual(chk["data"]["title"], "Test Title")

    def test_skills_service(self):
        """Test scanning and default creation of SEO/GEO/AEO skills."""
        skills_dir = self.test_dir / "Skills"
        srv = SkillsService(skills_dir=skills_dir)
        skills = srv.list_skills()

        self.assertGreaterEqual(len(skills), 3)
        filenames = [s["filename"] for s in skills]
        self.assertIn("seo_skill.md", filenames)
        self.assertIn("geo_skill.md", filenames)
        self.assertIn("aeo_skill.md", filenames)

        combined = srv.build_combined_skills_prompt(["seo_skill.md"])
        self.assertIn("SEO Copywriting Skill", combined)

    def test_clean_json_response(self):
        """Test resilient markdown backtick stripping and extraction."""
        raw_markdown = """```json
        {
            "title": "Cleaned Article",
            "content": "Sample content"
        }
        ```"""
        cleaned = clean_json_response(raw_markdown)
        data = json.loads(cleaned)
        self.assertEqual(data["title"], "Cleaned Article")

    def test_compile_html(self):
        """Test HTML5 document generation with Schema.org JSON-LD."""
        article_data = {
            "title": "Testing Compiler",
            "meta_description": "A meta description test.",
            "content_html": "<p>This is test content.</p>",
            "category": "Technology",
            "url": "https://example.com/test",
            "faqs": [
                {"question": "What is this?", "answer": "A test FAQ."}
            ]
        }

        html = compile_html_document(article_data)
        self.assertIn("<!DOCTYPE html>", html)
        self.assertIn("Testing Compiler", html)
        self.assertIn("application/ld+json", html)
        self.assertIn("FAQPage", html)
        self.assertIn("This is test content.", html)


if __name__ == "__main__":
    unittest.main()
