import http.client
import json
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest.mock import patch

import console_server


class _Upstream(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.0"

    def log_message(self, format, *args):
        pass

    def do_POST(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.end_headers()
        self.wfile.write(b"data: {\"choices\":[{\"delta\":{\"content\":\"a\"}}]}\n\n")
        self.wfile.flush()
        self.wfile.write(b"data: [DONE]\n\n")
        self.wfile.flush()


class HttpSurfaceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.upstream = ThreadingHTTPServer(("127.0.0.1", 0), _Upstream)
        cls.upstream_thread = threading.Thread(target=cls.upstream.serve_forever, daemon=True)
        cls.upstream_thread.start()
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), console_server.Handler)
        cls.server_thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.server_thread.start()
        cls.base = ("127.0.0.1", cls.server.server_address[1])

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.upstream.shutdown()
        cls.server.server_close()
        cls.upstream.server_close()

    def request(self, method, path, body=None, token=None):
        conn = http.client.HTTPConnection(*self.base, timeout=10)
        headers = {"Content-Type": "application/json"}
        if token:
            headers["X-Strata-Token"] = token
        encoded = json.dumps(body).encode() if body is not None else None
        conn.request(method, path, encoded, headers)
        response = conn.getresponse()
        payload = response.read()
        conn.close()
        return response.status, response.getheaders(), payload

    def test_health_and_control_auth(self):
        status, _, body = self.request("GET", "/health")
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body)["status"], "ok")
        status, _, _ = self.request("GET", "/api/catalog")
        self.assertEqual(status, 401)
        with patch.object(console_server, "token", return_value="test-token"):
            status, _, _ = self.request("GET", "/api/catalog", token="test-token")
        self.assertEqual(status, 200)

    def test_config_rejects_absurd_values(self):
        with patch.object(console_server, "token", return_value="test-token"):
            status, _, body = self.request("POST", "/api/config", {"model": "missing", "max_context": 999999999}, "test-token")
        self.assertEqual(status, 400)
        self.assertIn("fuera de rango", json.loads(body)["error"]["message"])

    def test_gateway_rate_limit_returns_retry_after(self):
        with patch.object(console_server, "RATE_LIMIT_REQUESTS", 1), patch.object(console_server, "_rate_buckets", {}):
            first, _, _ = self.request("GET", "/v1/models")
            second, headers, body = self.request("GET", "/v1/models")
        self.assertEqual(first, 200)
        self.assertEqual(second, 429)
        self.assertTrue(dict(headers).get("Retry-After"))
        self.assertEqual(json.loads(body)["error"]["type"], "rate_limit_error")

    def test_sse_is_forwarded_chunked(self):
        upstream_port = self.upstream.server_address[1]
        with patch.object(console_server, "switch_to", return_value=upstream_port):
            status, headers, body = self.request(
                "POST", "/v1/chat/completions",
                {"model": "demo", "stream": True, "messages": [{"role": "user", "content": "hi"}]},
            )
        self.assertEqual(status, 200)
        self.assertEqual(dict(headers).get("Transfer-Encoding"), "chunked")
        self.assertIn(b"data: [DONE]", body)


if __name__ == "__main__":
    unittest.main()
