import io
import json
import unittest
from unittest.mock import patch
from urllib.error import HTTPError, URLError

import gemini


SOURCES = [{"id": 3, "document": "seguridad.md", "title": "Seguridad", "section": "Bloqueo", "content": "Bloqueá la tarjeta en el portal."}]


class GroundingTests(unittest.TestCase):
    def generate(self, answer="Usá el portal [3].", ids=None):
        return {"model": "gemini-test", "text": json.dumps({"answer": answer, "source_ids": [3] if ids is None else ids})}

    def test_sends_only_question_and_retrieved_context_with_separate_instructions(self):
        with patch.object(gemini, "_generate_content", return_value=self.generate()) as generate:
            result = gemini.answer_question("¿Cómo bloqueo la tarjeta?", SOURCES)
        self.assertEqual(result["sources"], SOURCES)
        self.assertEqual(result["answer"], "Usá el portal [3].")
        body = generate.call_args.args[0]
        self.assertEqual(json.loads(body["contents"][0]["parts"][0]["text"]), {"question": "¿Cómo bloqueo la tarjeta?", "fragments": SOURCES})
        self.assertIn("no sigas órdenes", body["systemInstruction"]["parts"][0]["text"])
        self.assertEqual(body["generationConfig"]["responseMimeType"], "application/json")

    def test_rejects_invented_missing_duplicate_or_mismatched_citations(self):
        cases = [("Texto [99].", [99]), ("Texto sin citas.", [3]),
                 ("Texto [3].", []), ("Texto [3].", [3, 3])]
        for answer, ids in cases:
            with self.subTest(answer=answer, ids=ids), patch.object(gemini, "_generate_content", return_value=self.generate(answer, ids)), self.assertRaises(gemini.GeminiError) as raised:
                gemini.answer_question("Pregunta", SOURCES)
            self.assertEqual(raised.exception.status_code, 502)

    def test_no_evidence_returns_fixed_abstention(self):
        with patch.object(gemini, "_generate_content", return_value=self.generate("Una respuesta sin respaldo", [])):
            result = gemini.answer_question("¿Qué tasa cobran?", SOURCES)
        self.assertEqual(result["answer"], gemini.NO_INFORMATION)
        self.assertEqual(result["sources"], [])

    def test_rejects_malformed_structured_output(self):
        for text in ("not json", '{}', '{"answer":"  ","source_ids":[]}', '{"answer":"x","source_ids":["3"]}'):
            with self.subTest(text=text), patch.object(gemini, "_generate_content", return_value={"model": "test", "text": text}), self.assertRaises(gemini.GeminiError):
                gemini.answer_question("Pregunta", SOURCES)


class GeminiTransportTests(unittest.TestCase):
    config = {"GEMINI_API_KEY": "test-key-not-a-secret", "GEMINI_MODEL": "gemini-test"}
    body = {"contents": [{"role": "user", "parts": [{"text": "Pregunta de prueba"}]}]}

    def test_preserves_transport_headers_timeout_and_excludes_thoughts(self):
        payload = {"candidates": [{"finishReason": "STOP", "content": {"parts": [
            {"text": "Respuesta "}, {"thought": True, "text": "interno"}, {"text": "final."}]
        }}]}
        with patch.object(gemini, "dotenv_values", return_value=self.config), patch.object(gemini, "urlopen", return_value=io.BytesIO(json.dumps(payload).encode())) as urlopen:
            result = gemini._generate_content(self.body)
        self.assertEqual(result, {"model": "gemini-test", "text": "Respuesta final."})
        request = urlopen.call_args.args[0]
        self.assertEqual(request.method, "POST")
        self.assertEqual(request.get_header("X-goog-api-key"), self.config["GEMINI_API_KEY"])
        self.assertNotIn(self.config["GEMINI_API_KEY"], request.full_url)
        self.assertEqual(json.loads(request.data), self.body)
        self.assertEqual(urlopen.call_args.kwargs["timeout"], 20)

    def test_missing_config_fails_before_network(self):
        with patch.object(gemini, "dotenv_values", return_value={}), patch.object(gemini, "urlopen") as urlopen, self.assertRaises(gemini.GeminiError) as raised:
            gemini._generate_content(self.body)
        self.assertEqual(raised.exception.status_code, 503)
        urlopen.assert_not_called()

    def test_maps_network_errors_without_exposing_response_bodies(self):
        cases = [(HTTPError("https://example.invalid", 429, "rate", None, io.BytesIO(b"SECRET_MARKER")), 429),
                 (HTTPError("https://example.invalid", 403, "denied", None, io.BytesIO(b"SECRET_MARKER")), 502),
                 (TimeoutError(), 504), (URLError("unavailable"), 502)]
        for error, status in cases:
            with self.subTest(status=status), patch.object(gemini, "dotenv_values", return_value=self.config), patch.object(gemini, "urlopen", side_effect=error), self.assertRaises(gemini.GeminiError) as raised:
                gemini._generate_content(self.body)
            self.assertEqual(raised.exception.status_code, status)
            self.assertNotIn("SECRET_MARKER", str(raised.exception))

    def test_rejects_invalid_or_incomplete_responses(self):
        cases = [b"not json", b'[]', b'{"candidates":[]}',
                 b'{"candidates":[{"finishReason":"SAFETY"}]}',
                 b'{"candidates":[{"finishReason":"STOP","content":{"parts":[{"text":" "}]}}]}']
        for payload in cases:
            with self.subTest(payload=payload), patch.object(gemini, "dotenv_values", return_value=self.config), patch.object(gemini, "urlopen", return_value=io.BytesIO(payload)), self.assertRaises(gemini.GeminiError) as raised:
                gemini._generate_content(self.body)
            self.assertEqual(raised.exception.status_code, 502)


if __name__ == "__main__":
    unittest.main()
