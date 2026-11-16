import json
import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class FrontendIntegrationContractTests(unittest.TestCase):
    def run_node(self, script):
        result = subprocess.run(
            ["node", "-e", script],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=True,
        )
        return json.loads(result.stdout)

    def test_api_client_normalizes_http_status_and_retry_metadata(self):
        script = r"""
const fs = require("fs"), vm = require("vm");
const source = fs.readFileSync("frontend/js/api-client.js", "utf8");
const context = {
  HimRakshak: {}, location: {protocol: "http:"},
  setTimeout: setTimeout, clearTimeout: clearTimeout,
  AbortController: AbortController,
  fetch: () => Promise.resolve({
    ok: false, status: 429,
    headers: {get: (name) => name === "Retry-After" ? "3" : null},
    text: () => Promise.resolve(JSON.stringify({
      error: {message: "rate limited", classification: "rate_limit"}
    }))
  })
};
context.window = context;
vm.runInNewContext(source, context);
context.HimRakshak.api.request("/api/state").then(
  () => process.exit(2),
  (error) => process.stdout.write(JSON.stringify({
    kind: error.kind, status: error.status, retryAfter: error.retryAfter,
    classification: error.classification, message: error.message
  }))
);
"""
        self.assertEqual(self.run_node(script), {
            "kind": "http",
            "status": 429,
            "retryAfter": "3",
            "classification": "rate_limit",
            "message": "rate limited",
        })

    def test_api_client_keeps_standalone_mode_offline(self):
        script = r"""
const fs = require("fs"), vm = require("vm");
const source = fs.readFileSync("frontend/js/api-client.js", "utf8");
const context = {HimRakshak: {}, location: {protocol: "file:"}};
context.window = context;
vm.runInNewContext(source, context);
context.HimRakshak.api.health().then(
  () => process.exit(2),
  (error) => process.stdout.write(JSON.stringify({
    kind: error.kind, message: error.message
  }))
);
"""
        self.assertEqual(self.run_node(script), {
            "kind": "standalone",
            "message": "Standalone browser mode has no backend connection.",
        })

    def test_phase3_refresh_contracts_are_present(self):
        app = (ROOT / "frontend" / "js" / "app.js").read_text(encoding="utf-8")
        self.assertIn("root.setInterval", app)
        self.assertIn("5000", app)
        self.assertIn("document.hidden", app)
        self.assertIn("visibilitychange", app)
        self.assertIn("refreshPromise.then", app)
        self.assertIn("latest.generation", app)
        self.assertIn("Protected simulation requires local backend mode.", app)
        self.assertIn("Last known state is preserved.", app)

    def test_phase3_api_surface_and_no_v2_endpoints(self):
        client = (ROOT / "frontend" / "js" / "api-client.js").read_text(encoding="utf-8")
        for endpoint in [
            "/api/health",
            "/api/state",
            "/api/stations",
            "/api/stations/",
            "/readings",
            "/simulate",
            "/faults/",
        ]:
            self.assertIn(endpoint, client)
        self.assertNotRegex(client, r"/api/v2|/radio|/gateway|/power|/solar")

