import json
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class Phase9ReleaseContractTests(unittest.TestCase):
    def test_render_requires_external_device_token_secret(self):
        render = (ROOT / "render.yaml").read_text(encoding="utf-8")
        self.assertIn("key: HIMRAKSHAK_DEVICE_TOKENS", render)
        self.assertIn("sync: false", render)
        self.assertNotRegex(render, r"token-[A-Za-z0-9]|secret-[A-Za-z0-9]")

    def test_pages_workflow_packages_entrypoint_and_frontend_tree(self):
        workflow = (ROOT / ".github" / "workflows" / "pages.yml").read_text(
            encoding="utf-8"
        )
        self.assertIn("cp index.html site/index.html", workflow)
        self.assertIn("cp -R frontend site/frontend", workflow)
        self.assertIn("actions/upload-pages-artifact", workflow)
        self.assertIn("actions/deploy-pages", workflow)

    def test_wokwi_diagram_is_valid_json(self):
        diagram = json.loads(
            (ROOT / "wokwi_esp32_demo" / "diagram.json").read_text(encoding="utf-8")
        )
        self.assertIsInstance(diagram.get("parts"), list)
        self.assertTrue(diagram["parts"])

    def test_static_assets_contain_no_credentials(self):
        paths = [ROOT / "index.html"] + list((ROOT / "frontend").rglob("*"))
        text = "\n".join(
            path.read_text(encoding="utf-8")
            for path in paths
            if path.is_file()
        )
        self.assertNotIn("HIMRAKSHAK_ADMIN_KEY", text)
        self.assertNotRegex(text, r"X-HimRakshak-Device-Token")
        self.assertNotRegex(text, r"device-\d+")

    def test_device_auth_documentation_is_consistent(self):
        api = (ROOT / "docs" / "api-contract.md").read_text(encoding="utf-8")
        deployment = (ROOT / "docs" / "deployment.md").read_text(encoding="utf-8")
        self.assertIn("HIMRAKSHAK_DEVICE_TOKENS", api)
        self.assertIn("X-HimRakshak-Device-Token", api)
        self.assertIn("HIMRAKSHAK_DEVICE_TOKENS", deployment)
        self.assertIn("X-HimRakshak-Device-Token", deployment)


if __name__ == "__main__":
    unittest.main()
