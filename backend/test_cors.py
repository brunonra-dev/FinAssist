import asyncio
import unittest

import main


async def preflight(origin: str, method: str = "POST", headers: str = "Content-Type"):
    messages = []

    async def receive():
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(message):
        messages.append(message)

    await main.app(
        {
            "type": "http",
            "asgi": {"version": "3.0"},
            "http_version": "1.1",
            "method": "OPTIONS",
            "scheme": "http",
            "path": "/ask",
            "raw_path": b"/ask",
            "query_string": b"",
            "headers": [
                (b"origin", origin.encode()),
                (b"access-control-request-method", method.encode()),
                (b"access-control-request-headers", headers.encode()),
            ],
            "client": ("127.0.0.1", 12345),
            "server": ("127.0.0.1", 8000),
        },
        receive,
        send,
    )
    start = next(message for message in messages if message["type"] == "http.response.start")
    return start["status"], {key.decode(): value.decode() for key, value in start["headers"]}


class CorsTests(unittest.TestCase):
    def test_allows_only_the_local_frontend_post(self):
        status, headers = asyncio.run(preflight("http://localhost:5173"))

        self.assertEqual(status, 200)
        self.assertEqual(headers["access-control-allow-origin"], "http://localhost:5173")
        self.assertIn("POST", headers["access-control-allow-methods"])
        self.assertIn("content-type", headers["access-control-allow-headers"].lower())
        self.assertNotIn("access-control-allow-credentials", headers)

    def test_rejects_other_origins_methods_and_headers(self):
        for origin in [
            "http://127.0.0.1:5173",
            "http://localhost:5174",
            "https://example.com",
        ]:
            status, headers = asyncio.run(preflight(origin))
            self.assertEqual(status, 400)
            self.assertNotIn("access-control-allow-origin", headers)

        for method, headers in [("DELETE", "Content-Type"), ("POST", "X-Other")]:
            status, _ = asyncio.run(preflight("http://localhost:5173", method, headers))
            self.assertEqual(status, 400)


if __name__ == "__main__":
    unittest.main()
