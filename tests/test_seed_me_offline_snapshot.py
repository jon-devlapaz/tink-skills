"""The graph library is vendored and inlined, so the live page and every saved snapshot work with no network."""
import base64
import hashlib
from pathlib import Path
import re
import unittest
from unittest.mock import patch

from test_seed_me_session import node, session


SKILL = Path(__file__).resolve().parents[1] / "skills/seed-me"
VENDORED = SKILL / "assets/vendor/cytoscape.min.js"
TEMPLATE = (SKILL / "assets/ledger-view.html").read_text()


class TestVendoredGraphLibrary(unittest.TestCase):
    def tag(self):
        return re.search(r'<script[^>]*id="graph-library"[^>]*>', TEMPLATE).group(0)

    def test_the_vendored_file_is_exactly_the_build_the_page_pins(self):
        self.assertTrue(VENDORED.is_file(), "vendor the pinned build at assets/vendor/cytoscape.min.js")
        pinned = re.search(r'integrity="sha384-([^"]+)"', self.tag()).group(1)
        actual = base64.b64encode(hashlib.sha384(VENDORED.read_bytes()).digest()).decode()
        self.assertEqual(actual, pinned, "the vendored bytes must match the SRI hash in the template")
        self.assertIn("/3.30.2/", self.tag())

    def test_the_vendored_file_can_sit_inside_an_inline_script(self):
        text = VENDORED.read_text(encoding="utf-8")
        self.assertNotIn("</script", text.lower())
        self.assertNotIn("<!--", text)

    def test_its_license_and_origin_travel_with_it(self):
        notes = (SKILL / "assets/vendor/README.md").read_text()
        for needed in ("MIT", "3.30.2", "sha384-", "cdnjs.cloudflare.com"):
            self.assertIn(needed, notes)


class TestSnapshotIsSelfContained(unittest.TestCase):
    def ledger(self):
        return {"schema_version": 1, "session_id": "s", "version": 1, "revision": 1, "created_at": "t", "updated_at": "t",
                "status": "active", "draft": {"goal": "", "outcome": "", "options": []}, "goal": None, "origin": None,
                "current_question": None, "frontier": [], "nodes": [], "assumed": [], "operator": "human"}

    def test_the_page_carries_the_library_and_no_external_script(self):
        page = session.snapshot_page(self.ledger())
        self.assertEqual(re.findall(r"<script[^>]+src=", page), [], "no script may be fetched from the network")
        self.assertIn('<script id="graph-library">', page)
        self.assertIn(VENDORED.read_text(encoding="utf-8")[:200], page)
        self.assertEqual(page.count("</script>"), len(re.findall(r"<script", page)), "every script tag closes exactly once")

    def test_without_the_vendored_file_the_pinned_cdn_tag_remains_as_the_fallback(self):
        with patch.object(session, "VENDOR", Path("/nonexistent/cytoscape.min.js")):
            page = session.snapshot_page(self.ledger())
        self.assertIn("cdnjs.cloudflare.com", page)
        self.assertIn('integrity="sha384-', page)


if __name__ == "__main__":
    unittest.main()
