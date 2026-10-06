import json
import os
import unittest
from unittest.mock import patch

import httpx
from fastapi.testclient import TestClient

from studymate.main import app


async def prepared_context(question, history, document_ids):
    return None, history[-20:], []


class ChatApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(app)
        self.environment = patch.dict(
            os.environ,
            {"OLLAMA_CHAT_MODEL": "test-model", "OLLAMA_BASE_URL": "http://ollama.test/"},
        )
        self.environment.start()
        self.preparation = patch("studymate.chat.prepare_context", side_effect=prepared_context)
        self.validation = patch("studymate.chat.validate_answer", side_effect=lambda answer, _: (answer, [], False))
        self.preparation.start()
        self.validation.start()

    def tearDown(self) -> None:
        self.environment.stop()
        self.preparation.stop()
        self.validation.stop()

    def request_with_transport(self, handler: httpx.MockTransport, history: list[dict] | None = None) -> httpx.Response:
        ollama_client = httpx.AsyncClient(transport=handler)
        with patch("studymate.llm.httpx.AsyncClient", return_value=ollama_client):
            payload = {"document_ids": ["00000000-0000-0000-0000-000000000001"], "question": "  Explain gravity  "}
            if history is not None:
                payload["history"] = history
            return self.client.post("/api/chat", json=payload)

    def test_forwards_conversation_in_order(self) -> None:
        history = [
            {"role": "user", "content": "My name is Luca"},
            {"role": "assistant", "content": "Hello Luca"},
        ]

        def respond(request: httpx.Request) -> httpx.Response:
            messages = json.loads(request.content)["messages"]
            self.assertEqual(messages[0]["role"], "system")
            self.assertEqual(messages[1:-1], history)
            self.assertEqual(messages[-1], {"role": "user", "content": "Explain gravity"})
            return httpx.Response(200, json={"message": {"content": "Answer"}})

        self.assertEqual(self.request_with_transport(httpx.MockTransport(respond), history).status_code, 200)

    def test_keeps_only_last_ten_exchanges(self) -> None:
        history = [
            {"role": role, "content": f"{index} {role}"}
            for index in range(12) for role in ("user", "assistant")
        ]

        def respond(request: httpx.Request) -> httpx.Response:
            self.assertEqual(json.loads(request.content)["messages"][1:-1], history[-20:])
            return httpx.Response(200, json={"message": {"content": "Answer"}})

        self.assertEqual(self.request_with_transport(httpx.MockTransport(respond), history).status_code, 200)

    def test_rejects_history_roles_other_than_user_and_assistant(self) -> None:
        for role in ("system", "tool"):
            with self.subTest(role=role):
                response = self.client.post("/api/chat", json={
                    "question": "Hello", "history": [{"role": role, "content": "Instructions"}]
                })
                self.assertEqual(response.status_code, 422)

    def test_returns_model_answer_and_sends_non_streaming_request(self) -> None:
        def respond(request: httpx.Request) -> httpx.Response:
            self.assertEqual(str(request.url), "http://ollama.test/api/chat")
            payload = json.loads(request.content)
            self.assertEqual(payload["model"], "test-model")
            self.assertEqual(payload["messages"][-1], {"role": "user", "content": "Explain gravity"})
            self.assertEqual(len(payload["messages"]), 2)
            self.assertIs(payload["stream"], False)
            self.assertIs(payload["think"], False)
            return httpx.Response(200, json={"message": {"content": "  Gravity attracts mass.  "}})

        response = self.request_with_transport(httpx.MockTransport(respond))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"answer": "Gravity attracts mass.", "citations": [], "grounded": False})

    def test_rejects_blank_question(self) -> None:
        response = self.client.post("/api/chat", json={"document_ids": ["00000000-0000-0000-0000-000000000001"], "question": "  \n "})
        self.assertEqual(response.status_code, 422)

    def test_returns_only_final_answer_when_thinking_is_in_content(self) -> None:
        cases = [
            ("<think>Internal analysis\nSecond line</think>\nCiao Matteo!", "Ciao Matteo!"),
            ("Internal analysis without opening tag</think>\nCiao Matteo!", "Ciao Matteo!"),
            ("<THINK>Internal analysis</THINK>Answer", "Answer"),
            ("<think>Outer<think>Inner</think>Outer</think>Answer", "Answer"),
            ("First paragraph.\n\nSecond paragraph.", "First paragraph.\n\nSecond paragraph."),
            ("Visible answer<think>Incomplete analysis", "Visible answer"),
        ]
        for content, expected in cases:
            with self.subTest(content=content):
                response = self.request_with_transport(httpx.MockTransport(
                    lambda _, content=content: httpx.Response(200, json={
                        "message": {"content": content, "thinking": "Separate internal analysis"}
                    })
                ))
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.json(), {"answer": expected, "citations": [], "grounded": False})

    def test_rejects_response_with_only_thinking(self) -> None:
        for content in ("<think>Internal analysis</think>", "<think>Incomplete analysis", "Analysis</think>"):
            with self.subTest(content=content):
                response = self.request_with_transport(httpx.MockTransport(
                    lambda _, content=content: httpx.Response(200, json={"message": {"content": content}})
                ))
                self.assertEqual(response.status_code, 502)
                self.assertEqual(response.json()["detail"], "The language model returned an invalid response")

    def test_uses_default_model_when_environment_variable_is_absent(self) -> None:
        def respond(request: httpx.Request) -> httpx.Response:
            self.assertEqual(json.loads(request.content)["model"], "qwen3:4b-instruct")
            return httpx.Response(200, json={"message": {"content": "Hello"}})

        with patch.dict(os.environ, {"OLLAMA_BASE_URL": "http://ollama.test"}, clear=True):
            response = self.request_with_transport(httpx.MockTransport(respond))
        self.assertEqual(response.status_code, 200)

    def test_reports_missing_model_configuration(self) -> None:
        with patch.dict(os.environ, {"OLLAMA_CHAT_MODEL": ""}):
            response = self.client.post("/api/chat", json={"document_ids": ["00000000-0000-0000-0000-000000000001"], "question": "Hello"})
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
