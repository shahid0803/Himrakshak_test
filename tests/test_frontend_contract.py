from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[1]


class FrontendContractTests(unittest.TestCase):
    def test_classic_script_order_and_assets(self):
        html = (ROOT / "index.html").read_text(encoding="utf-8")
        scripts = re.findall(r'<script defer src="([^"]+)"', html)
        self.assertEqual(scripts, [
            "frontend/js/shell.js", "frontend/js/api-client.js",
            "frontend/js/state-store.js", "frontend/js/data-mappers.js",
            "frontend/js/controls.js", "frontend/js/router.js", "frontend/js/app.js",
        ])
        for asset in scripts + ["frontend/css/tokens.css", "frontend/css/layout.css",
                                "frontend/css/components.css"]:
            self.assertTrue((ROOT / asset).is_file(), asset)

    def test_no_modules_secrets_or_invented_rf_metrics(self):
        assets = [ROOT / "index.html"] + list((ROOT / "frontend").rglob("*"))
        text = "\n".join(p.read_text(encoding="utf-8") for p in assets if p.is_file())
        self.assertNotRegex(text, r"\b(import|export)\s")
        self.assertNotRegex(text, r"(HIMRAKSHAK_ADMIN_KEY|Authorization:\s*Bearer)")
        self.assertIn("No synthetic cloud state was substituted", text)
        self.assertIn("gateway_state", text)
        for marker in ("live", "delayed", "stale", "disconnected", "recovered", "unavailable"):
            self.assertIn(marker, text)
        self.assertIn("SOFTWARE SIMULATION", text)

    def test_pages_workflow_publishes_frontend(self):
        workflow = (ROOT / ".github" / "workflows" / "pages.yml").read_text()
        self.assertIn("cp -R frontend site/frontend", workflow)
        self.assertIn("site/frontend/js/app.js", workflow)
