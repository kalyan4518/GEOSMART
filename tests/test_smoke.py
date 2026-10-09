"""Read-only application smoke tests using an isolated in-memory database."""

import os
import tempfile
import unittest
from io import BytesIO
from pathlib import Path
import zipfile
from unittest.mock import patch

import cv2
import numpy as np

os.environ.setdefault("DATABASE_URL", "sqlite://")

from geosmart.app import app  # noqa: E402
from geosmart.config import BASE_DIR, Config  # noqa: E402
from geosmart.web_support import _safe_extract_zip, _validate_dataset_path  # noqa: E402


class ApplicationSmokeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        app.config.update(TESTING=True, SECRET_KEY="test-only-key")

    def setUp(self):
        self.client = app.test_client()

    def test_public_pages_render(self):
        for path in ("/", "/index", "/login", "/signup"):
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertEqual(response.status_code, 200)

    def test_static_stylesheet_is_served(self):
        response = self.client.get("/static/css/styles.css")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"GEOSMART", response.data)
        response.close()

        scripts = (
            "admin_dashboard.js",
            "analyze.js",
            "complaint.js",
            "dashboard.js",
            "municipal.js",
            "profile.js",
        )
        for script in scripts:
            with self.subTest(script=script):
                asset = self.client.get(f"/static/js/{script}")
                self.assertEqual(asset.status_code, 200)
                asset.close()

    def test_authenticated_pages_render_for_user_and_admin(self):
        self.client.post("/login", data={"email": "smoke@example.test", "password": "demo"})
        for path in ("/dashboard", "/analyze", "/complaint", "/municipal", "/profile"):
            with self.subTest(path=path):
                self.assertEqual(self.client.get(path).status_code, 200)

        self.assertEqual(self.client.get("/admin").status_code, 302)
        previous_password = Config.ADMIN_PASSWORD
        Config.ADMIN_PASSWORD = "test-only-password"
        try:
            self.client.get("/logout")
            self.client.post(
                "/admin/login",
                data={"email": Config.ADMIN_EMAIL, "password": Config.ADMIN_PASSWORD},
            )
            self.assertEqual(self.client.get("/dashboard").status_code, 200)
        finally:
            Config.ADMIN_PASSWORD = previous_password

    def test_api_requires_login_then_returns_dashboard_data(self):
        self.assertEqual(self.client.get("/api/complaints").status_code, 401)
        self.client.post("/login", data={"email": "smoke@example.test", "password": "demo"})

        complaints = self.client.get("/api/complaints")
        summary = self.client.get("/api/dashboard-summary")
        hotspots = self.client.get("/api/hotspots")
        route = self.client.get("/api/routes/optimize")
        self.assertEqual(complaints.status_code, 200)
        created = self.client.post(
            "/api/complaints",
            json={
                "issueType": "overflow",
                "priority": "normal",
                "ward": "Ward 11",
                "location": "Smoke test",
                "description": "Application smoke test complaint",
            },
        )
        self.assertEqual(created.status_code, 201)
        self.assertEqual(len(self.client.get("/api/complaints").get_json()), 1)
        self.assertEqual(summary.status_code, 200)
        self.assertEqual(hotspots.status_code, 200)
        self.assertEqual(route.status_code, 200)

    def test_model_training_endpoints_are_admin_gated(self):
        self.client.post("/login", data={"email": "smoke@example.test", "password": "demo"})
        self.assertEqual(self.client.get("/api/model/train-status").status_code, 403)

    def test_checked_in_dataset_yaml_resolves_from_project_root(self):
        dataset_yaml = BASE_DIR / "trashnet-master" / "data" / "trashnet_cls" / "data.yaml"
        summary = _validate_dataset_path(str(dataset_yaml))
        self.assertEqual(summary["classCount"], 6)

    def test_dataset_yaml_rejects_missing_train_or_validation_directories(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            yaml_path = Path(temporary_directory) / "data.yaml"
            yaml_path.write_text(
                "path: .\ntrain: missing-train\nval: missing-val\nnames: [plastic]\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(RuntimeError, "Dataset train path not found"):
                _validate_dataset_path(str(yaml_path))

    def test_admin_dataset_validation_api_checks_dataset_paths(self):
        previous_password = Config.ADMIN_PASSWORD
        Config.ADMIN_PASSWORD = "test-only-password"
        try:
            self.client.post(
                "/admin/login",
                data={"email": Config.ADMIN_EMAIL, "password": Config.ADMIN_PASSWORD},
            )
            dataset_yaml = BASE_DIR / "trashnet-master" / "data" / "trashnet_cls" / "data.yaml"
            response = self.client.post(
                "/api/model/validate-dataset", json={"dataPath": str(dataset_yaml)}
            )
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.get_json()["summary"]["classCount"], 6)
        finally:
            Config.ADMIN_PASSWORD = previous_password

    def test_image_upload_reaches_prediction_endpoint(self):
        self.client.post("/login", data={"email": "smoke@example.test", "password": "demo"})
        success, encoded = cv2.imencode(".png", np.full((32, 32, 3), 180, dtype=np.uint8))
        self.assertTrue(success)
        with patch(
            "geosmart.routes.api.verify_waste",
            return_value={
                "verified": False,
                "verification_score": 0.42,
                "predicted_type": "plastic",
                "model": "test waste classifier",
            },
        ):
            response = self.client.post(
                "/api/analyze/cnn",
                data={"image": (BytesIO(encoded.tobytes()), "sample.png", "image/png")},
                content_type="multipart/form-data",
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["predictedType"], "plastic")
        self.assertEqual(response.get_json()["confidence"], 0.42)
        self.assertEqual(response.get_json()["status"], "Needs review")

    def test_image_upload_reports_missing_model_as_service_unavailable(self):
        self.client.post("/login", data={"email": "smoke@example.test", "password": "demo"})
        success, encoded = cv2.imencode(".png", np.full((32, 32, 3), 180, dtype=np.uint8))
        self.assertTrue(success)
        with patch(
            "geosmart.routes.api.verify_waste",
            return_value={
                "verified": False,
                "verification_score": 0.0,
                "predicted_type": "unavailable",
                "model": "unavailable",
            },
        ):
            response = self.client.post(
                "/api/analyze/cnn",
                data={"image": (BytesIO(encoded.tobytes()), "sample.png", "image/png")},
                content_type="multipart/form-data",
            )
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.get_json()["status"], "Model unavailable")

    def test_image_upload_rejects_invalid_content_and_extensions(self):
        self.client.post("/login", data={"email": "smoke@example.test", "password": "demo"})
        invalid_content = self.client.post(
            "/api/analyze/cnn",
            data={"image": (BytesIO(b"not an image"), "bad.png", "image/png")},
        )
        invalid_extension = self.client.post(
            "/api/analyze/cnn",
            data={"image": (BytesIO(b"not an image"), "bad.exe", "application/octet-stream")},
        )
        self.assertEqual(invalid_content.status_code, 400)
        self.assertEqual(invalid_extension.status_code, 400)

    def test_zip_extraction_rejects_sibling_prefix_traversal(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            parent = Path(temporary_directory)
            target = parent / "extract"
            target.mkdir()
            archive_path = parent / "unsafe.zip"
            with zipfile.ZipFile(archive_path, "w") as archive:
                archive.writestr("../extract-escape/payload.txt", "outside")

            with self.assertRaisesRegex(RuntimeError, "Unsafe zip"):
                _safe_extract_zip(archive_path, target)
            self.assertFalse((parent / "extract-escape").exists())


if __name__ == "__main__":
    unittest.main()
