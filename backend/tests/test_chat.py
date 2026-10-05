import json
import os
import unittest
from unittest.mock import patch

import httpx
from fastapi.testclient import TestClient

from studymate.main import app


class ChatApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(app)
        self.environment = patch.dict(
            os.environ,
            {"OLLAMA_CHAT_MODEL": "test-model", "OLLAMA_BASE_URL": "http://ollama.test/"},
        )
        self.environment.start()

    def tearDown(self) -> None:
        self.environment.stop()

    def request_with_transport(self, handler: httpx.MockTransport) -> httpx.Response:
        ollama_client = httpx.AsyncClient(transport=handler)
        with patch("studymate.llm.httpx.AsyncClient", return_value=ollama_client):
            return self.client.post("/api/chat", json={"question": "  Explain gravity  "})

    def test_returns_model_answer_and_sends_non_streaming_request(self) -> None:
        def respond(request: httpx.Request) -> httpx.Response:
            self.assertEqual(str(request.url), "http://ollama.test/api/chat")
            payload = json.loads(request.content)
            self.assertEqual(payload["model"], "test-model")
            self.assertEqual(payload["messages"][-1], {"role": "user", "content": "Explain gravity"})
            self.assertIs(payload["stream"], False)
            self.assertIs(payload["think"], False)
            return httpx.Response(200, json={"message": {"content": "  Gravity attracts mass.  "}})

        response = self.request_with_transport(httpx.MockTransport(respond))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"answer": "Gravity attracts mass."})

    def test_rejects_blank_question(self) -> None:
        response = self.client.post("/api/chat", json={"question": "  \n "})
        self.assertEqual(response.status_code, 422)

    def test_uses_default_model_when_environment_variable_is_absent(self) -> None:
        def respond(request: httpx.Request) -> httpx.Response:
            self.assertEqual(json.loads(request.content)["model"], "qwen3:4b")
            return httpx.Response(200, json={"message": {"content": "Hello"}})

        with patch.dict(os.environ, {"OLLAMA_BASE_URL": "http://ollama.test"}, clear=True):
            response = self.request_with_transport(httpx.MockTransport(respond))
        self.assertEqual(response.status_code, 200)

    def test_reports_missing_model_configuration(self) -> None:
        with patch.dict(os.environ, {"OLLAMA_CHAT_MODEL": ""}):
            response = self.client.post("/api/chat", json={"question": "Hello"})
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["detail"], "OLLAMA_CHAT_MODEL is not configured")

    def test_reports_unavailable_ollama(self) -> None:
        def fail(request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("connection refused", request=request)

        response = self.request_with_transport(httpx.MockTransport(fail))
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["detail"], "The language model is unavailable")

    def test_reports_ollama_timeout(self) -> None:
        def fail(request: httpx.Request) -> httpx.Response:
            raise httpx.ReadTimeout("timed out", request=request)

        response = self.request_with_transport(httpx.MockTransport(fail))
        self.assertEqual(response.status_code, 504)
        self.assertEqual(response.json()["detail"], "The language model timed out")

    def test_reports_ollama_error_without_exposing_response(self) -> None:
        response = self.request_with_transport(
            httpx.MockTransport(lambda _: httpx.Response(404, text="internal model details"))
        )
        self.assertEqual(response.status_code, 502)
        self.assertEqual(response.json()["detail"], "The language model returned an error")

    def test_rejects_invalid_ollama_response(self) -> None:
        response = self.request_with_transport(
            httpx.MockTransport(lambda _: httpx.Response(200, json={"message": {"content": " "}}))
        )
        self.assertEqual(response.status_code, 502)
        self.assertEqual(response.json()["detail"], "The language model returned an invalid response")


if __name__ == "__main__":
    unittest.main()
