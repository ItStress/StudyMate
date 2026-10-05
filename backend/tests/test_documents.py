import os
import unittest
from io import BytesIO
from unittest.mock import patch
from urllib.parse import urlparse
from uuid import UUID

import psycopg
from fastapi.testclient import TestClient
from pypdf import PdfWriter

from studymate.body_limit import MAX_PDF_BYTES, MAX_REQUEST_BYTES
from studymate.main import app
from studymate.migrations import migrate


def sample_pdf(encrypted: bool = False) -> bytes:
    writer = PdfWriter()
    writer.add_blank_page(width=72, height=72)
    if encrypted:
        writer.encrypt("secret")
    output = BytesIO()
    writer.write(output)
    return output.getvalue()


class DocumentTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.database_url = os.getenv("TEST_DATABASE_URL")
        if not cls.database_url:
            raise RuntimeError("TEST_DATABASE_URL must point to a separate PostgreSQL test database")
        if not urlparse(cls.database_url).path.endswith("_test"):
            raise RuntimeError("TEST_DATABASE_URL must name a database ending in _test")
        migrate(cls.database_url)
        cls.client = TestClient(app)

    def setUp(self) -> None:
        self.created_ids: list[str] = []
        self.database_patch = patch.dict(os.environ, {"DATABASE_URL": self.database_url})
        self.database_patch.start()

    def tearDown(self) -> None:
        self.database_patch.stop()
        with psycopg.connect(self.database_url) as conn:
            for document_id in self.created_ids:
                conn.execute("DELETE FROM documents WHERE id = %s", (UUID(document_id),))

    def upload(self, content: bytes, name: str = "sample.pdf", mime: str = "application/pdf"):
        response = self.client.post(
            "/api/documents", files={"file": (name, content, mime)}
        )
        if response.status_code == 201:
            self.created_ids.append(response.json()["id"])
        return response


class DocumentApiTests(DocumentTestCase):
    def test_health(self) -> None:
        self.assertEqual(self.client.get("/health").json(), {"status": "ok"})

    def test_upload_list_preview_and_delete(self) -> None:
        content = sample_pdf()
        uploaded = self.upload(content)
        self.assertEqual(uploaded.status_code, 201)
        metadata = uploaded.json()
        self.assertEqual(metadata["filename"], "sample.pdf")
        self.assertEqual(metadata["size_bytes"], len(content))
        self.assertEqual(metadata["page_count"], 1)

        with TestClient(app) as new_client:
            listed = new_client.get("/api/documents")
            self.assertEqual(listed.status_code, 200)
            self.assertIn(metadata["id"], [item["id"] for item in listed.json()])
            retrieved = new_client.get(f'/api/documents/{metadata["id"]}/content')
        self.assertEqual(retrieved.content, content)
        self.assertEqual(retrieved.headers["content-type"], "application/pdf")
        self.assertEqual(retrieved.headers["x-content-type-options"], "nosniff")

        deleted = self.client.delete(f'/api/documents/{metadata["id"]}')
        self.assertEqual(deleted.status_code, 204)
        self.assertEqual(self.client.get(f'/api/documents/{metadata["id"]}/content').status_code, 404)
        self.assertEqual(self.client.delete(f'/api/documents/{metadata["id"]}').status_code, 404)

    def test_rejects_non_pdf_and_invalid_pdf(self) -> None:
        cases = [
            (b"plain text", "notes.pdf", "application/pdf", 415),
            (sample_pdf(), "notes.txt", "application/pdf", 415),
            (sample_pdf(), "notes.pdf", "text/plain", 415),
            (b"%PDF-broken", "notes.pdf", "application/pdf", 422),
            (b"", "notes.pdf", "application/pdf", 422),
            (sample_pdf(encrypted=True), "locked.pdf", "application/pdf", 422),
        ]
        for content, name, mime, expected in cases:
            with self.subTest(name=name, expected=expected):
                self.assertEqual(self.upload(content, name, mime).status_code, expected)

    def test_filename_is_display_only(self) -> None:
        uploaded = self.upload(sample_pdf(), "../report.pdf")
        self.assertEqual(uploaded.status_code, 201)
        self.assertEqual(uploaded.json()["filename"], "report.pdf")

        suspicious = self.upload(sample_pdf(), "x'); DROP TABLE documents;--.pdf")
        self.assertEqual(suspicious.status_code, 201)
        self.assertEqual(self.client.get("/api/documents").status_code, 200)

    def test_size_boundary_and_request_cap(self) -> None:
        at_limit = b"%PDF-" + b"x" * (MAX_PDF_BYTES - 5)
        self.assertEqual(self.upload(at_limit).status_code, 422)
        self.assertEqual(self.upload(at_limit + b"x").status_code, 413)
        oversized_body = self.client.post(
            "/api/documents",
            content=b"x" * (MAX_REQUEST_BYTES + 1),
            headers={"content-type": "multipart/form-data; boundary=test"},
        )
        self.assertEqual(oversized_body.status_code, 413)

    def test_database_failure_returns_503(self) -> None:
        with patch.dict(os.environ, {"DATABASE_URL": "postgresql://bad:bad@127.0.0.1:1/bad"}):
            self.assertEqual(self.client.get("/api/documents").status_code, 503)


if __name__ == "__main__":
    unittest.main()
