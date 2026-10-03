"""
tests/test_api.py — Integration Tests for REST API Endpoints
==============================================================
Validates HTTP responses for dashboard UI, pipeline controls, settings,
queue, skills, and logs endpoints.
"""

import json
import unittest
from app import create_app


class TestRestAPI(unittest.TestCase):
    def setUp(self):
        self.app = create_app()
        self.app.config["TESTING"] = True
        self.client = self.app.test_client()

    def test_root_index_renders_ui(self):
        """Root GET / should render Windows 11 Fluent Studio HTML."""
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        html = response.data.decode("utf-8")
        self.assertIn("Content Pipeline Pro", html)
        self.assertIn("fluent-shell", html)
        self.assertIn("workflow-split-layout", html)

    def test_pipeline_status(self):
        """GET /api/pipeline/status should return pipeline state."""
        response = self.client.get("/api/pipeline/status")
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertIn("state", data)
        self.assertIn("progress", data)

    def test_settings_get_and_post(self):
        """GET /api/settings and POST /api/settings should work."""
        response = self.client.get("/api/settings")
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        settings = data.get("settings", data)
        self.assertIn("image_engine", settings)

        # Update a setting
        update_resp = self.client.post(
            "/api/settings",
            json={"image_resolution_preset": "landscape_16_9"},
            content_type="application/json"
        )
        self.assertEqual(update_resp.status_code, 200)
        updated_data = json.loads(update_resp.data)
        self.assertTrue(updated_data.get("ok") or updated_data.get("status") == "success")

    def test_skills_list(self):
        """GET /api/skills should return scanned skills."""
        response = self.client.get("/api/skills")
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertTrue("skills" in data or isinstance(data, list))

    def test_queue_endpoints(self):
        """GET /api/queue should return list of queued URLs."""
        response = self.client.get("/api/queue")
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertTrue("links" in data or "items" in data)

    def test_articles_catalog(self):
        """GET /api/articles should return article catalog list."""
        response = self.client.get("/api/articles")
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertIn("articles", data)

    def test_run_single_validation(self):
        """POST /api/pipeline/run-single requires valid URL."""
        res_empty = self.client.post(
            "/api/pipeline/run-single",
            json={"url": ""},
            content_type="application/json"
        )
        self.assertEqual(res_empty.status_code, 400)

    def test_custom_visual_settings(self):
        """POST /api/settings should persist custom resolution, custom style, and featured image."""
        payload = {
            "image_resolution": "1600x900",
            "feature_resolution": "1920x1080",
            "image_type": "custom",
            "image_type_custom": "hyper-realistic oil painting, Rembrandt chiaroscuro",
            "feature_image_master_prompt": "epic wide-angle establishing shot",
            "feature_text_overlay": True,
            "render_font_family": "Montserrat-ExtraBold.ttf",
            "render_header_font_size": 52,
            "render_scrim_enabled": True,
            "article_format": "point_wise",
        }
        res = self.client.post(
            "/api/settings",
            json=payload,
            content_type="application/json"
        )
        self.assertEqual(res.status_code, 200)
        data = json.loads(res.data)
        self.assertTrue(data.get("ok"))
        settings = data.get("settings", {})
        self.assertEqual(settings.get("image_resolution"), "1600x900")
        self.assertEqual(settings.get("feature_resolution"), "1920x1080")
        self.assertEqual(settings.get("render_w"), 1600)
        self.assertEqual(settings.get("render_h"), 900)
        self.assertEqual(settings.get("feature_w"), 1920)
        self.assertEqual(settings.get("feature_h"), 1080)
        self.assertEqual(settings.get("article_format"), "point_wise")



if __name__ == "__main__":
    unittest.main()
