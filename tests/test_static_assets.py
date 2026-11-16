import threading
import unittest
from http.client import HTTPConnection

from himrakshak.server import HimRakshakServer


class StaticAssetTests(unittest.TestCase):
    def setUp(self):
        self.server = HimRakshakServer(("127.0.0.1", 0), seed=1)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.host, self.port = self.server.server_address

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)

    def get(self, path):
        c = HTTPConnection(self.host, self.port, timeout=3)
        c.request("GET", path)
        r = c.getresponse()
        body = r.read()
        headers = dict(r.getheaders())
        c.close()
        return r.status, headers, body

    def test_assets_and_mime_types(self):
        status, headers, body = self.get("/frontend/css/tokens.css")
        self.assertEqual(status, 200)
        self.assertEqual(headers["Content-Type"], "text/css; charset=utf-8")
        self.assertIn(b"--pine", body)
        status, headers, _ = self.get("/frontend/js/app.js")
        self.assertEqual(status, 200)
        self.assertEqual(headers["Content-Type"], "text/javascript; charset=utf-8")

    def test_missing_and_traversal_are_safe(self):
        for path in ("/frontend/nope.js", "/frontend/../himrakshak/server.py",
                     "/frontend/%2e%2e/himrakshak/server.py",
                     "/frontend%5c..%5chimrakshak%5cserver.py"):
            status, _, _ = self.get(path)
            self.assertEqual(status, 404)

    def test_api_routes_remain_json(self):
        status, headers, _ = self.get("/api/health")
        self.assertEqual(status, 200)
        self.assertTrue(headers["Content-Type"].startswith("application/json"))
