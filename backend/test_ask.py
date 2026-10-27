import asyncio
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import database
import gemini
import main


async def request(path, body, method="POST"):
    messages = []
    sent = False

    async def receive():
        nonlocal sent
        if not sent:
            sent = True
            return {"type": "http.request", "body": json.dumps(body).encode(), "more_body": False}
        return {"type": "http.disconnect"}

    async def send(message):
        messages.append(message)

    await main.app({
        "type": "http", "asgi": {"version": "3.0"}, "http_version": "1.1",
        "method": method, "scheme": "http", "path": path, "raw_path": path.encode(),
        "query_string": b"", "headers": [(b"content-type", b"application/json")],
        "client": ("127.0.0.1", 12345), "server": ("127.0.0.1", 8000),
    }, receive, send)
    status = next(message["status"] for message in messages if message["type"] == "http.response.start")
    payload = b"".join(message.get("body", b"") for message in messages if message["type"] == "http.response.body")
    return status, json.loads(payload)


class AskTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        db_patch = patch.object(database, "DB_PATH", Path(self.directory.name) / "test.db")
        db_patch.start()
        self.addCleanup(db_patch.stop)

    def call(self, question):
        async def run():
            async with main.lifespan(main.app):
                return await request("/ask", question)
        return asyncio.run(run())

    def test_full_retrieval_to_mocked_gemini_with_real_documents(self):
        def generate(body):
            fragments = json.loads(body["contents"][0]["parts"][0]["text"])["fragments"]
            source_id = fragments[0]["id"]
            return {"model": "test-model", "text": json.dumps({"answer": f"Consultá el resumen en el portal [{source_id}].", "source_ids": [source_id]})}
        with patch.object(gemini, "_generate_content", side_effect=generate):
            status, result = self.call({"question": "¿Dónde consulto el resumen?"})
        self.assertEqual(status, 200)
        self.assertEqual(result["model"], "test-model")
        self.assertEqual(result["sources"][0]["document"], "resumen.md")
        self.assertIn("content", result["sources"][0])

    def test_unrelated_question_does_not_call_gemini(self):
        with patch.object(gemini, "_generate_content") as generate:
            status, result = self.call({"question": "astronomia galactica"})
        self.assertEqual(status, 200)
        self.assertEqual(result, {"answer": gemini.NO_INFORMATION, "sources": [], "model": None})
        generate.assert_not_called()

    def test_invalid_questions_are_rejected_by_http_validation(self):
        for body in ({}, {"question": " "}, {"question": 42}, {"question": "x" * 2001}, {"question": "resumen", "extra": True}):
            with self.subTest(body=str(body)[:60]), patch.object(gemini, "_generate_content") as generate:
                self.assertEqual(self.call(body)[0], 422)
                generate.assert_not_called()

    def test_provider_errors_keep_the_http_status(self):
        for status in (429, 502, 503, 504):
            with self.subTest(status=status), patch.object(gemini, "_generate_content", side_effect=gemini.GeminiError(status, "Error de prueba")):
                actual_status, body = self.call({"question": "resumen"})
            self.assertEqual(actual_status, status)
            self.assertEqual(body["detail"], "Error de prueba")

    def test_health_and_legacy_routes(self):
        self.assertEqual(asyncio.run(request("/health", {}, "GET")), (200, {"status": "ok"}))
        self.assertEqual(asyncio.run(request("/tickets", {}, "GET"))[0], 404)


if __name__ == "__main__":
    unittest.main()
