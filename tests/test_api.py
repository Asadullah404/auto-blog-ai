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
        self.assertIn("workflow-canvas", html)

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


if __name__ == "__main__":
    unittest.main()
