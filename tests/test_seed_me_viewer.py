import base64
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from test_seed_me_epistemics import acceptance_nodes, finding, receipt
from test_seed_me_session import node, session


SCRIPT = Path(__file__).resolve().parents[1] / "skills/seed-me/scripts/viewer.py"
SPEC = importlib.util.spec_from_file_location("seed_viewer", SCRIPT)
viewer = importlib.util.module_from_spec(SPEC)
sys.path.insert(0, str(SCRIPT.parent))
try:
    SPEC.loader.exec_module(viewer)
finally:
    sys.path.pop(0)


LAUNCH_TIMEOUT_MS = 20_000
REQUIRE_BROWSER = os.environ.get("SEED_ME_REQUIRE_BROWSER") == "1"
INSTALL_HINT = "python -m pip install -r tests/requirements-browser.txt && python -m playwright install chromium"
VIEWER_ASSET = SCRIPT.parents[1] / "assets/ledger-view.html"


def browser_unavailable(reason):
    """Skip with one clear line, or fail when SEED_ME_REQUIRE_BROWSER=1 (CI)."""
    message = f"Browser tests cannot run: {reason}. Fix: {INSTALL_HINT}"
    if REQUIRE_BROWSER:
        raise RuntimeError(message)
    print(f"SKIPPED {message}", file=sys.stderr)
    raise unittest.SkipTest(message)


def first_line(error):
    return (str(error).strip().splitlines() or [type(error).__name__])[0]


def pinned_cytoscape():
    """The vendored Cytoscape build (its bytes are checked against the page's SRI pin in test_seed_me_offline_snapshot)."""
    override = os.environ.get("SEED_ME_CYTOSCAPE_PATH")
    return Path(override) if override else VIEWER_ASSET.parent / "vendor/cytoscape.min.js"


class ViewerFixture:
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = session.create(self.temp.name)
        self.server = viewer.make_server(self.directory)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.addCleanup(self.stop_server)
        self.url = f"http://127.0.0.1:{self.server.server_port}"

    def stop_server(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=5)

    def publish(self, state, reason="Synthetic test fixture transition"):
        return session.publish(self.directory, state, session.load(self.directory)["version"], reason)

    def confirm(self):
        state = session.editable(session.load(self.directory))
        state.update(goal="Recover data", origin="goal", current_question="backup")
        state["nodes"] = [node("goal", answer="Recover data"),
                          node("import-behavior", "fact", answer="Replace existing data"),
                          {**node("backup", parents=["import-behavior"]), "question": "Require a backup?"},
                          node("button-label", answer="Import backup")]
        return self.publish(state)


class TestViewerHTTP(ViewerFixture, unittest.TestCase):
    def test_serves_only_viewer_and_validated_ledger(self):
        (self.directory / "private.txt").write_text("not exposed")
        with urlopen(self.url + "/ledger-view.html") as response:
            self.assertIn(b"Draft", response.read())
            self.assertEqual(response.headers["Cache-Control"], "no-store")
        with urlopen(self.url + "/ledger.json?poll=1") as response:
            self.assertEqual(json.load(response)["origin"], None)
        for path in ("/private.txt", "/.writer.lock", "/../ledger.json", "/%2e%2e/ledger.json"):
            with self.subTest(path=path), self.assertRaises(HTTPError) as raised:
                urlopen(self.url + path)
            self.assertEqual(raised.exception.code, 404)
        self.assertEqual(self.server.server_address[0], "127.0.0.1")
        self.assertEqual((self.directory / "ledger-view.html").read_text(),
                         viewer.snapshot_page(session.load(self.directory)))

    def test_bad_host_mutation_and_corrupt_data_fail_closed(self):
        with self.assertRaises(HTTPError) as raised:
            urlopen(Request(self.url + "/ledger.json", headers={"Host": "attacker.example"}))
        self.assertEqual(raised.exception.code, 403)
        before = (self.directory / "ledger.json").read_bytes()
        with self.assertRaises(HTTPError) as raised:
            urlopen(Request(self.url + "/ledger.json", data=b"{}", method="POST"))
        self.assertEqual(raised.exception.code, 501)
        self.assertEqual((self.directory / "ledger.json").read_bytes(), before)
        (self.directory / "ledger.json").write_text("{")
        with self.assertRaises(HTTPError) as raised:
            urlopen(self.url + "/ledger.json")
        self.assertEqual(raised.exception.code, 503)


class TestViewerSnapshots(ViewerFixture, unittest.TestCase):
    def test_snapshot_is_atomic_and_escapes_script_boundaries(self):
        state = session.editable(session.load(self.directory))
        attack = '</script><script>window.injected=true</script>'
        state["draft"]["goal"] = attack
        self.publish(state)
        before = (self.directory / "ledger-view.html").read_bytes()
        with patch.object(session.os, "replace", side_effect=OSError("disk failure")):
            with self.assertRaisesRegex(OSError, "disk failure"):
                viewer.save_snapshot(self.directory)
        self.assertEqual((self.directory / "ledger-view.html").read_bytes(), before)
        path = viewer.save_snapshot(self.directory)
        html = path.read_text()
        self.assertNotIn(attack, html)
        embedded = re.search(r'<script id="ledger-data" type="application/json">\s*(.*?)\s*</script>', html, re.S)
        self.assertEqual(json.loads(embedded.group(1)), session.load(self.directory))
        self.assertEqual(path.stat().st_mode & 0o777, 0o600)

    def test_ended_viewer_cli_saves_snapshot_without_a_server(self):
        self.confirm()
        ended = session.end(self.directory, "stopped", "User stopped")
        for args in ([], ["--snapshot"]):
            with self.subTest(args=args):
                result = subprocess.run([sys.executable, str(SCRIPT), str(self.directory), *args],
                                        capture_output=True, text=True, timeout=5)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(result.stdout.strip(), (self.directory / "ledger-view.html").as_uri())
                self.assertEqual(session.load(self.directory), ended)


class TestViewerBrowser(ViewerFixture, unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            from playwright.sync_api import sync_playwright, expect
        except ImportError as error:
            browser_unavailable(f"Python Playwright is not installed ({first_line(error)})")
        cls.expect = staticmethod(expect)
        cls.playwright = sync_playwright().start()
        failures = []
        cls.browser = None
        for label, options in (("bundled Chromium", {}), ("system Google Chrome", {"channel": "chrome"})):
            try:
                cls.browser = cls.playwright.chromium.launch(headless=True, timeout=LAUNCH_TIMEOUT_MS, **options)
                break
            except Exception as error:
                failures.append(f"{label}: {first_line(error)}")
        if cls.browser is None:
            cls.playwright.stop()
            browser_unavailable("no launchable browser (" + "; ".join(failures) + ")")

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.playwright.stop()

    def setUp(self):
        super().setUp()
        self.context = self.browser.new_context()
        self.addCleanup(self.context.close)
        self.context.route("**/cytoscape.min.js", lambda route: route.abort())
        self.page = self.context.new_page()
        self.errors = []
        self.page.on("pageerror", lambda error: self.errors.append(str(error)))

    def test_live_draft_decision_answer_and_reopening_with_safe_history(self):
        state = session.editable(session.load(self.directory))
        attack = '<img src=x onerror="window.injected=true">'
        state["draft"] = {"goal": attack, "outcome": "Recover data", "options": ["Export", "Import"]}
        self.publish(state)
        self.page.goto(self.url)
        self.expect(self.page.locator("#draft")).to_be_visible()
        self.expect(self.page.locator("#draft-content")).to_contain_text(attack)
        self.expect(self.page.locator("#ledger-list")).to_contain_text("No accepted goal")
        self.assertEqual(self.page.locator("#draft img").count(), 0)
        self.expect(self.page.locator("#connection")).to_have_attribute("data-health", "live")
        self.confirm()
        self.expect(self.page.locator("#draft")).to_be_hidden()
        self.expect(self.page.locator("#current")).to_have_text("Current question: Require a backup?")
        self.expect(self.page.locator("#counts")).to_contain_text("1 decision ready")
        self.expect(self.page.locator("#detail")).to_contain_text("unresolved")
        state = session.editable(session.load(self.directory))
        state["nodes"][2].update(status="settled", answer=attack, authority="user", authority_source="fixture conversation: chose backup")
        state["current_question"] = None
        self.publish(state)
        self.expect(self.page.locator("#detail")).to_contain_text(attack)
        self.expect(self.page.locator("#counts")).to_contain_text("2 decided")
        state = session.editable(session.load(self.directory))
        state["nodes"][1].update(answer="Merge data", evidence=["fixture import.py:10: merge(existing, incoming)"])
        state["nodes"][2] = {**node("backup", parents=["import-behavior"]), "question": "Still require a backup?",
                              "reopen_reason": "Import behavior changed from replace to merge"}
        state["current_question"] = "backup"
        self.publish(state, "Fixture evidence changed from replace to merge")
        self.expect(self.page.locator("#current")).to_have_text("Current question: Still require a backup?")
        self.expect(self.page.locator("#detail > dl")).to_contain_text("unresolved")
        self.expect(self.page.locator("#detail .history").first).to_contain_text(attack)
        self.expect(self.page.locator("#detail .history").first).to_contain_text("changed from replace to merge")
        self.expect(self.page.locator('[data-node-id="button-label"]')).to_contain_text("Import backup")
        self.assertEqual(self.page.locator("#detail img, #ledger-list img").count(), 0)
        self.assertIsNone(self.page.evaluate("window.injected"))
        self.assertEqual(self.errors, [])

    def test_complete_fallback_and_selected_detail_refresh_without_reload(self):
        # The library is inlined now; take it away to prove the text view still carries everything.
        gone = patch.object(sys.modules["session"], "VENDOR", Path("/nonexistent/cytoscape.min.js"))
        gone.start()
        self.addCleanup(gone.stop)
        self.confirm()
        self.page.goto(self.url)
        self.expect(self.page.locator("#cdn-banner")).to_be_visible()
        section = self.page.locator('[data-node-id="import-behavior"]')
        section.locator("summary").click()
        section.get_by_role("button", name="Inspect node").click()
        self.expect(self.page.locator("#detail")).to_contain_text("Replace existing data")
        self.expect(self.page.locator("#detail")).to_contain_text("import.py:10")
        state = session.editable(session.load(self.directory))
        state["nodes"][1].update(answer="Merge data", evidence=["fixture import.py:10: merge()"])
        self.publish(state, "Fresh fixture evidence")
        self.expect(self.page.locator("#detail > dl")).to_contain_text("Merge data")
        self.expect(self.page.locator("#detail .history")).to_contain_text("Replace existing data")
        self.expect(section).to_have_attribute("open", "")
        self.assertEqual(self.errors, [])

    def test_graph_tracks_real_dependencies_and_clicked_node_history(self):
        try:
            library = pinned_cytoscape()
        except OSError as error:
            if REQUIRE_BROWSER:
                raise
            self.skipTest(f"Could not fetch the pinned Cytoscape file ({first_line(error)}); set SEED_ME_CYTOSCAPE_PATH to a local copy")
        self.assertTrue(library.is_file(), f"SEED_ME_CYTOSCAPE_PATH is not a file: {library}")
        self.context.unroute("**/cytoscape.min.js")
        self.context.route("**/cytoscape.min.js", lambda route: route.fulfill(path=library, content_type="application/javascript"))
        self.page.goto(self.url)
        self.page.wait_for_function("LEDGER !== null && cy === null")
        self.confirm()
        self.page.wait_for_function("cy !== null && cy.nodes().length === 3")
        self.assertEqual(self.page.evaluate("cy.getElementById('goal').length"), 0)
        self.expect(self.page.locator("#cdn-banner")).to_be_hidden()
        self.expect(self.page.locator("#cy canvas").first).to_be_visible()
        self.assertEqual(self.page.evaluate("cy.edges().map(e => [e.source().id(), e.target().id()])"),
                         [["import-behavior", "backup"]])
        self.assertTrue(self.page.evaluate("cy.getElementById('backup').hasClass('current')"))
        position = self.page.evaluate("cy.getElementById('backup').renderedPosition()")
        self.page.locator("#cy").click(position=position)
        self.expect(self.page.locator("#detail h2")).to_have_text("backup")
        state = session.editable(session.load(self.directory))
        state["nodes"][2].update(status="settled", answer="Require backup", authority="user", authority_source="fixture chat: yes")
        state["current_question"] = None
        self.publish(state)
        self.page.wait_for_function("cy.getElementById('backup').hasClass('settled')")
        state = session.editable(session.load(self.directory))
        state["nodes"][1].update(answer="Merge data", evidence=["fixture: merges may overwrite keys"])
        state["nodes"][2] = {**node("backup", parents=["import-behavior"]),
                              "reopen_reason": "Import behavior changed from replace to merge"}
        state["current_question"] = "backup"
        self.publish(state, "Fixture changed premise")
        self.page.wait_for_function("cy.getElementById('backup').hasClass('current')")
        self.expect(self.page.locator("#detail > dl")).to_contain_text("unresolved")
        self.expect(self.page.locator("#detail .history").first).to_contain_text("Require backup")
        self.assertTrue(self.page.evaluate("cy.getElementById('button-label').hasClass('settled')"))
        self.assertEqual(self.errors, [])

    def test_graph_legend_shows_every_visual_encoding_and_matches_the_real_nodes(self):
        try:
            library = pinned_cytoscape()
        except OSError as error:
            if REQUIRE_BROWSER:
                raise
            self.skipTest(f"Could not fetch the pinned Cytoscape file ({first_line(error)})")
        self.context.unroute("**/cytoscape.min.js")
        self.context.route("**/cytoscape.min.js", lambda route: route.fulfill(path=library, content_type="application/javascript"))
        state = session.editable(session.load(self.directory))
        state.update(goal="Ship it", origin="goal", current_question="d2")
        deferred = {**node("d4", parents=["d1"]), "status": "deferred", "defer_reason": "later", "revisit_condition": "after launch"}
        superseded = {**node("d5", parents=["d1"]), "status": "superseded"}
        state["nodes"] = [node("goal", answer="Ship it"), node("f", "fact", answer="A fact"),
                          node("d1", parents=["f"], answer="Settled answer"),
                          {**node("d2", parents=["d1"]), "question": "Ready?"},
                          node("d3", parents=["d2"]), deferred, superseded]
        self.publish(state)
        self.page.goto(self.url)
        self.page.wait_for_function("cy !== null && cy.nodes().length === 6")
        self.page.get_by_role("button", name="How to read").click()
        self.expect(self.page.locator("#legend")).to_be_visible()
        keys = self.page.evaluate("[...document.querySelectorAll('#legend [data-legend]')].map(e => e.dataset.legend)")
        self.assertEqual(sorted(keys), sorted(["settled", "ready", "parked", "deferred", "superseded", "current", "decision", "fact", "edge", "support"]))
        for key in keys:
            self.assertTrue(self.page.evaluate("key => document.querySelector(`#legend [data-legend=${key}]`).closest('li').textContent.trim().length > 6", key), key)
        colors = self.page.evaluate("""() => {
            const digits = v => (String(v).match(/\\d+/g) || []).slice(0, 3).join(',');
            const swatch = k => getComputedStyle(document.querySelector(`#legend [data-legend=${k}]`)).backgroundColor;
            const node = id => cy.getElementById(id).style('background-color');
            return {settled: [digits(swatch('settled')), digits(node('d1'))], ready: [digits(swatch('ready')), digits(node('d2'))],
                    parked: [digits(swatch('parked')), digits(node('d3'))], deferred: [digits(swatch('deferred')), digits(node('d4'))]};
        }""")
        for key, (legend, real) in colors.items():
            self.assertEqual(legend, real, key)
        shapes = self.page.evaluate("""() => ({
            decision: cy.getElementById('d1').style('shape'), fact: cy.getElementById('f').style('shape'),
            decisionRadius: getComputedStyle(document.querySelector('#legend [data-legend=decision]')).borderRadius,
            factRadius: getComputedStyle(document.querySelector('#legend [data-legend=fact]')).borderRadius,
            supersededStyle: getComputedStyle(document.querySelector('#legend [data-legend=superseded]')).borderTopStyle,
            currentBorder: getComputedStyle(document.querySelector('#legend [data-legend=current]')).borderTopColor})""")
        self.assertEqual(shapes["decision"], "round-rectangle")
        self.assertEqual(shapes["fact"], "round-rectangle")
        self.assertGreater(self.page.evaluate("parseFloat(cy.getElementById('f').style('corner-radius'))"),
                           self.page.evaluate("parseFloat(cy.getElementById('d1').style('corner-radius'))") + 20, "a fact is a pill")
        self.assertNotIn("50%", shapes["decisionRadius"])
        self.assertIn("50%", shapes["factRadius"])
        self.assertEqual(shapes["supersededStyle"], "dashed")
        border = self.page.evaluate("""() => {
            const digits = v => (String(v).match(/\\d+/g) || []).slice(0, 3).join(',');
            return [digits(getComputedStyle(document.querySelector('#legend [data-legend=superseded]')).borderTopColor),
                    digits(cy.getElementById('d5').style('border-color')), cy.getElementById('d5').style('border-style')];
        }""")
        self.assertEqual(border[0], border[1], "the legend's superseded border must be the graph node's border")
        self.assertEqual(border[2], "dashed")
        self.assertEqual(shapes["currentBorder"], "rgb(163, 75, 227)")
        self.expect(self.page.locator("#legend [data-legend=edge]").locator("xpath=ancestor::li")).to_contain_text("waits")
        self.assertEqual(self.errors, [])

    def graph_page(self, context=None, current="b"):
        """A small known graph on the real pinned Cytoscape: a -> b -> c, a -> d, and e on its own."""
        try:
            library = pinned_cytoscape()
        except OSError as error:
            if REQUIRE_BROWSER:
                raise
            self.skipTest(f"Could not fetch the pinned Cytoscape file ({first_line(error)})")
        context = context or self.context
        context.unroute("**/cytoscape.min.js")
        context.route("**/cytoscape.min.js", lambda route: route.fulfill(path=library, content_type="application/javascript"))
        state = session.editable(session.load(self.directory))
        state.update(goal="Ship it", origin="goal", current_question=current)
        state["nodes"] = [node("goal", answer="Ship it"), node("a", answer="A"), node("b", parents=["a"]),
                          node("c", parents=["b"]), node("d", parents=["a"]), node("e", parents=["goal"])]
        self.publish(state)
        page = context.new_page()
        page.on("pageerror", lambda error: self.errors.append(str(error)))
        page.goto(self.url)
        page.wait_for_function("cy !== null && cy.nodes().length === 5")
        return page

    def test_graph_reads_left_to_right_in_layers_without_overlap(self):
        page = self.graph_page()
        x = page.evaluate("Object.fromEntries(cy.nodes().map(n => [n.id(), Math.round(n.position('x') - n.data('w') / 2)]))")
        self.assertLess(x["a"], x["b"])
        self.assertLess(x["b"], x["c"])
        self.assertEqual(x["b"], x["d"], "nodes the same number of steps from the start share a column (their left edges line up)")
        self.assertEqual(x["a"], x["e"])
        boxes = page.evaluate("cy.nodes().map(n => { const b = n.boundingBox(); return [b.x1, b.y1, b.x2, b.y2]; })")
        for i, p in enumerate(boxes):
            for q in boxes[i + 1:]:
                self.assertTrue(p[2] <= q[0] or q[2] <= p[0] or p[3] <= q[1] or q[3] <= p[1], f"overlap {p} {q}")
        self.assertEqual(self.errors, [])

    def test_selecting_a_node_fades_the_unrelated_and_lights_its_chain(self):
        page = self.graph_page()
        page.evaluate("void cy.getElementById('b').emit('tap')")
        faded = page.evaluate("cy.nodes('.faded').map(n => n.id()).sort()")
        self.assertEqual(faded, ["d", "e"], "b's chain is its ancestors and descendants; a sibling and a separate concern fade")
        hot = page.evaluate("cy.edges('.hot').map(e => e.source().id() + '>' + e.target().id()).sort()")
        self.assertEqual(hot, ["a>b", "b>c"])
        self.assertEqual(page.evaluate("cy.edges('.faded').map(e => e.source().id() + '>' + e.target().id())"), ["a>d"])
        self.expect(page.locator("#detail h2")).to_have_text("b")
        page.evaluate("void cy.emit('tap')")
        self.assertEqual(page.evaluate("cy.elements('.faded, .hot').length"), 0, "tapping the empty canvas clears the focus")
        page.evaluate("void cy.getElementById('c').emit('mouseover')")
        self.assertEqual(page.evaluate("cy.nodes('.faded').map(n => n.id()).sort()"), ["d", "e"], "hover previews the chain")
        page.evaluate("void cy.getElementById('c').emit('mouseout')")
        self.assertEqual(page.evaluate("cy.elements('.faded').length"), 0)
        self.assertEqual(self.errors, [])

    def test_graph_follows_the_color_scheme_and_the_legend_still_matches(self):
        light = self.graph_page()
        light_fill = light.evaluate("cy.getElementById('a').style('background-color')")
        dark_context = self.browser.new_context(color_scheme="dark")
        self.addCleanup(dark_context.close)
        dark = self.graph_page(dark_context)
        dark_fill = dark.evaluate("cy.getElementById('a').style('background-color')")
        self.assertNotEqual(light_fill, dark_fill, "a dark page must not reuse the light node colors")
        self.assertEqual(dark_fill, "rgb(23,58,45)", "dark settled is a clean green on charcoal, not olive")
        self.assertEqual(dark.evaluate("getComputedStyle(document.body).backgroundColor"), "rgb(19, 20, 23)")
        for page in (light, dark):
            same = page.evaluate("""() => {
                const digits = v => (String(v).match(/\\d+/g) || []).slice(0, 3).join(',');
                return digits(getComputedStyle(document.querySelector('#legend [data-legend=settled]')).backgroundColor)
                    === digits(cy.getElementById('a').style('background-color'));
            }""")
            self.assertTrue(same, "the legend swatch must be the node color")
        self.assertEqual(self.errors, [])

    def wide_graph_page(self, context=None):
        """A chain wide enough that fitting it into the panel would shrink the labels."""
        try:
            library = pinned_cytoscape()
        except OSError as error:
            if REQUIRE_BROWSER:
                raise
            self.skipTest(f"Could not fetch the pinned Cytoscape file ({first_line(error)})")
        context = context or self.context
        context.unroute("**/cytoscape.min.js")
        context.route("**/cytoscape.min.js", lambda route: route.fulfill(path=library, content_type="application/javascript"))
        state = session.editable(session.load(self.directory))
        state.update(goal="Ship it", origin="goal", current_question="n7")
        chain = [node("goal", answer="Ship it"), node("n1", answer="One")]
        for i in range(2, 7):
            chain.append(node(f"n{i}", parents=[f"n{i - 1}"], answer=str(i)))
        chain.append(node("n7", parents=["n6"]))
        state["nodes"] = chain
        self.publish(state)
        page = context.new_page()
        page.on("pageerror", lambda error: self.errors.append(str(error)))
        page.goto(self.url)
        page.wait_for_function("cy !== null && cy.nodes().length === 7")
        return page

    def test_a_wide_graph_pans_at_readable_size_with_the_current_question_in_view(self):
        page = self.wide_graph_page()
        self.assertGreaterEqual(page.evaluate("cy.zoom()"), 0.85, "labels must not shrink to fit the panel")
        self.assertGreaterEqual(page.evaluate("parseFloat(cy.getElementById('n1').style('font-size'))"), 13)
        inside = page.evaluate("""() => { const p = cy.getElementById('n7').renderedPosition(), r = cy.container().getBoundingClientRect();
            return p.x > 0 && p.x < r.width && p.y > 0 && p.y < r.height; }""")
        self.assertTrue(inside, "the question being asked must start in view")
        self.assertEqual(self.errors, [])

    def test_the_selected_node_has_a_marker_apart_from_the_current_question(self):
        page = self.graph_page(current="d")
        page.evaluate("void cy.getElementById('b').emit('tap')")
        self.assertEqual(page.evaluate("cy.nodes('.picked').map(n => n.id())"), ["b"])
        self.assertGreater(page.evaluate("parseFloat(cy.getElementById('b').style('outline-width'))"), 0)
        self.assertEqual(page.evaluate("parseFloat(cy.getElementById('d').style('outline-width'))"), 0)
        self.assertTrue(page.evaluate("cy.getElementById('d').hasClass('current')"))
        self.assertEqual(page.evaluate("cy.getElementById('d').style('border-color')"), "rgb(163,75,227)")
        page.evaluate("void cy.emit('tap')")
        self.assertEqual(page.evaluate("cy.nodes('.picked').length"), 0)
        self.assertEqual(self.errors, [])

    def test_focus_can_be_cleared_with_a_visible_control_and_stays_cleared(self):
        page = self.graph_page()
        self.expect(page.locator("#clear-focus")).to_be_visible()  # the current question is selected on load
        self.assertEqual(page.evaluate("cy.nodes('.picked').map(n => n.id())"), ["b"])
        page.locator("#clear-focus").click()
        self.assertEqual(page.evaluate("cy.elements('.faded, .hot, .picked').length"), 0)
        self.expect(page.locator("#clear-focus")).to_be_hidden()
        self.expect(page.locator("#detail")).to_contain_text("Select a node")
        state = session.editable(session.load(self.directory))
        state["nodes"][4]["answer"] = "D"
        state["nodes"][4].update(status="settled", authority="user", authority_source="fixture chat: yes")
        self.publish(state, "Fixture settled d")
        page.wait_for_function("cy.getElementById('d').hasClass('settled')")
        self.expect(page.locator("#clear-focus")).to_be_hidden()
        self.assertEqual(page.evaluate("cy.nodes('.picked').length"), 0, "a refresh must not undo the user's clear")
        page.evaluate("void cy.getElementById('c').emit('tap')")
        self.expect(page.locator("#clear-focus")).to_be_visible()
        self.assertEqual(self.errors, [])

    def test_the_inspector_leads_with_what_matters_and_tucks_the_plumbing_away(self):
        page = self.graph_page()
        page.evaluate("void cy.getElementById('b').emit('tap')")
        names = page.evaluate("[...document.querySelectorAll('#detail > dl > dt')].map(e => e.textContent)")
        self.assertEqual(names[0], "Status")
        self.assertLess(names.index("Gate"), names.index("Owner"))
        self.assertLess(names.index("Owner"), names.index("Waits for (workflow order)"))
        for plumbing in ("ID", "Kind", "Premise revision", "Evidence"):
            self.assertNotIn(plumbing, names, "plumbing and empty fields do not lead the inspector")
        meta = page.locator("#detail .meta")
        self.expect(meta).to_contain_text("decision")
        self.expect(meta).to_contain_text("b")
        self.assertEqual(page.locator("#detail h3").count(), 0, "an empty history is a quiet line, not a heading")
        self.expect(page.locator("#detail .quiet")).to_contain_text("No earlier versions")
        self.assertEqual(self.errors, [])

    def test_the_first_view_shows_whole_cards_around_the_question_and_hints_at_panning(self):
        page = self.wide_graph_page()
        whole = page.evaluate("""ids => { const r = cy.container().getBoundingClientRect();
            return ids.every(id => { const b = cy.getElementById(id).renderedBoundingBox();
                return b.x1 >= 0 && b.y1 >= 0 && b.x2 <= r.width && b.y2 <= r.height; }); }""", ["n6", "n7"])
        self.assertTrue(whole, "the question and its prerequisite must both be whole cards in the first view")
        self.expect(page.locator("#pan-hint")).to_be_visible()
        self.assertEqual(self.errors, [])

    def test_no_pan_hint_when_the_whole_graph_is_already_in_view(self):
        page = self.graph_page()
        page.evaluate("void cy.zoom(0.45)")
        page.evaluate("void cy.center()")
        self.expect(page.locator("#pan-hint")).to_be_hidden()
        self.assertEqual(self.errors, [])

    def test_selecting_an_offscreen_node_brings_its_neighborhood_into_view(self):
        page = self.wide_graph_page()
        page.evaluate("void cy.getElementById('n2').emit('tap')")
        page.wait_for_function("""() => { const r = cy.container().getBoundingClientRect();
            return ['n1', 'n2', 'n3'].every(id => { const b = cy.getElementById(id).renderedBoundingBox();
                return b.x1 >= 0 && b.x2 <= r.width; }); }""")
        self.assertGreaterEqual(page.evaluate("cy.zoom()"), 0.85)
        self.assertEqual(self.errors, [])

    def test_the_phone_graph_fills_the_screen_stays_readable_and_never_scrolls_sideways(self):
        phone = self.browser.new_context(viewport={"width": 390, "height": 844})
        self.addCleanup(phone.close)
        page = self.wide_graph_page(phone)
        self.assertGreater(page.evaluate("document.getElementById('cy').getBoundingClientRect().height / innerHeight"), 0.4)
        self.expect(page.locator("#detail")).to_be_visible()
        self.assertGreaterEqual(page.evaluate("cy.zoom()"), 0.85)
        self.assertEqual(page.evaluate("document.documentElement.scrollWidth <= document.documentElement.clientWidth"), True)
        self.assertEqual(self.errors, [])

    def test_a_saved_snapshot_draws_the_graph_with_no_network_at_all(self):
        state = session.editable(session.load(self.directory))
        state.update(goal="Ship it", origin="goal", current_question=None)
        state["nodes"] = [node("goal", answer="Ship it"), node("a", answer="A"), node("b", parents=["a"], answer="B")]
        self.publish(state)
        session.end(self.directory, "completed", "Confirmed and saved", no_viewer="offline test")
        saved = viewer.save_snapshot(self.directory)
        context = self.browser.new_context(offline=True)
        self.addCleanup(context.close)
        requests = []
        context.on("request", lambda request: requests.append(request.url))
        page = context.new_page()
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.goto(saved.as_uri())
        page.wait_for_function("cy !== null && cy.nodes().length === 2")
        self.assertEqual([url for url in requests if not url.startswith("file:")], [], "nothing may leave the machine")
        self.expect(page.locator("#cdn-banner")).to_be_hidden()
        self.assertEqual(errors, [])

    def test_the_graph_is_the_primary_surface_and_the_ledger_is_a_toggle(self):
        page = self.graph_page()
        self.assertEqual(page.evaluate("document.body.dataset.view"), "graph")
        self.expect(page.locator("#now")).to_be_hidden()
        self.expect(page.locator("#connection")).to_be_visible()
        self.assertGreater(page.evaluate("document.getElementById('cy').getBoundingClientRect().height / innerHeight"), 0.6,
                           "the graph must fill most of the screen")
        page.evaluate("void cy.getElementById('b').emit('tap')")
        page.get_by_role("button", name="Ledger").click()
        self.assertEqual(page.evaluate("document.body.dataset.view"), "ledger")
        self.expect(page.locator("#call")).to_be_visible()
        self.expect(page.locator("main")).to_be_hidden()
        self.expect(page.locator('details[data-node-id="b"]')).to_have_attribute("open", "")
        page.get_by_role("button", name="Graph").click()
        self.assertEqual(page.evaluate("document.body.dataset.view"), "graph")
        self.assertEqual(page.evaluate("cy.nodes('.picked').map(n => n.id())"), ["b"], "the selection survives the round trip")
        self.assertGreater(page.evaluate("document.getElementById('cy').getBoundingClientRect().height"), 100, "the graph resizes on return")
        self.assertEqual(self.errors, [])

    def test_the_view_can_be_chosen_by_link_and_by_keyboard(self):
        page = self.graph_page()
        page.keyboard.press("l")
        self.assertEqual(page.evaluate("document.body.dataset.view + location.hash"), "ledger#ledger")
        page.keyboard.press("g")
        self.assertEqual(page.evaluate("document.body.dataset.view + location.hash"), "graph#graph")
        page.goto(self.url + "#ledger")
        page.wait_for_function("LEDGER !== null")
        self.assertEqual(page.evaluate("document.body.dataset.view"), "ledger")
        self.assertEqual(self.errors, [])

    def test_every_node_is_an_html_card_that_follows_pan_and_zoom(self):
        page = self.graph_page(current="b")
        self.assertEqual(page.evaluate("document.querySelectorAll('#cards .card').length"), 5)
        self.assertEqual(page.evaluate("document.querySelector('#cards .card[data-id=a] .t').textContent"), "a")
        self.assertIn("settled", page.evaluate("document.querySelector('#cards .card[data-id=a]').className"))
        question = page.evaluate("document.querySelector('#cards .card.cur').textContent")
        self.assertIn("a proposal, not a decision" if "recommendation" in question else "Your call", question)
        before = page.evaluate("document.querySelector('#cards .card[data-id=a]').getBoundingClientRect().left")
        page.evaluate("void cy.panBy({x: 60, y: 0})")
        after = page.evaluate("document.querySelector('#cards .card[data-id=a]').getBoundingClientRect().left")
        self.assertAlmostEqual(after - before, 60, delta=1)
        a = page.evaluate("(() => { const r = document.querySelector('#cards .card[data-id=a]').getBoundingClientRect(); const p = cy.getElementById('a').renderedPosition(), c = cy.container().getBoundingClientRect(); return [r.left + r.width / 2 - c.left - p.x, r.top + r.height / 2 - c.top - p.y]; })()")
        self.assertLess(abs(a[0]) + abs(a[1]), 2, "the card is centered on its node")
        self.assertEqual(self.errors, [])

    def test_zooming_out_keeps_titles_and_hides_the_detail(self):
        page = self.graph_page()
        page.evaluate("void cy.zoom(1)")
        self.assertEqual(page.evaluate("document.getElementById('cards').classList.contains('far')"), False)
        page.evaluate("void cy.zoom(0.4)")
        self.assertEqual(page.evaluate("document.getElementById('cards').classList.contains('far')"), True)
        self.assertEqual(page.evaluate("getComputedStyle(document.querySelector('#cards .card[data-id=a] .a')).display"), "none")
        self.assertNotEqual(page.evaluate("getComputedStyle(document.querySelector('#cards .card[data-id=a] .t')).display"), "none")
        self.assertEqual(self.errors, [])

    def test_cards_fade_and_pick_with_the_graph_focus(self):
        page = self.graph_page()
        page.evaluate("void cy.getElementById('b').emit('tap')")
        self.assertEqual(page.evaluate("[...document.querySelectorAll('#cards .card.dim')].map(c => c.dataset.id).sort()"), ["d", "e"])
        self.assertEqual(page.evaluate("[...document.querySelectorAll('#cards .card.pick')].map(c => c.dataset.id)"), ["b"])
        page.evaluate("void cy.emit('tap')")
        self.assertEqual(page.evaluate("document.querySelectorAll('#cards .card.dim, #cards .card.pick').length"), 0)
        self.assertEqual(self.errors, [])

    def test_the_legend_lives_behind_a_button(self):
        page = self.graph_page()
        self.expect(page.locator("#legend")).to_be_hidden()
        page.get_by_role("button", name="How to read").click()
        self.expect(page.locator("#legend")).to_be_visible()
        page.get_by_role("button", name="How to read").click()
        self.expect(page.locator("#legend")).to_be_hidden()
        self.assertEqual(self.errors, [])

    def test_independent_cards_have_a_graph_without_invented_edges(self):
        for parents in ([], ["goal"]):
            with self.subTest(parents=parents):
                state = session.editable(session.load(self.directory))
                state.update(goal="Ship it", origin="goal", current_question="first")
                state["nodes"] = [node("goal", answer="Ship it"),
                                  {**node("first", parents=parents), "question": "First?"},
                                  {**node("second", parents=parents), "question": "Second?"}]
                self.publish(state)
                before = (self.directory / "ledger.json").read_bytes()
                self.page.goto(self.url)
                self.expect(self.page.locator("main")).to_be_visible()
                self.assertEqual(self.page.evaluate("document.body.dataset.view"), "graph")
                self.assertEqual(self.page.evaluate("cy.nodes().map(n => n.id()).sort()"), ["first", "second"])
                self.assertEqual(self.page.evaluate("cy.edges().length"), 0)
                self.expect(self.page.locator('#cards [data-id="first"]')).to_contain_text("First?")
                self.expect(self.page.locator('#cards [data-id="second"]')).to_contain_text("Second?")
                self.page.get_by_role("button", name="Ledger", exact=True).click()
                self.expect(self.page.locator("main")).to_be_hidden()
                self.page.get_by_role("button", name="Graph", exact=True).click()
                self.expect(self.page.locator("main")).to_be_visible()
                self.assertEqual((self.directory / "ledger.json").read_bytes(), before)
                self.assertEqual(self.errors, [])

    def test_goal_only_session_explains_the_start_without_false_completion(self):
        state = session.editable(session.load(self.directory))
        state.update(goal="Ship it", origin="goal", current_question=None)
        state["nodes"] = [node("goal", answer="Ship it")]
        self.publish(state)
        before = (self.directory / "ledger.json").read_bytes()
        self.page.goto(self.url)
        self.expect(self.page.locator("#call")).to_contain_text("Goal confirmed")
        self.expect(self.page.locator("#status-pill")).to_have_text("In progress")
        self.expect(self.page.locator("#call")).to_contain_text("No concerns recorded yet")
        self.expect(self.page.locator("#call")).not_to_contain_text("confirm it")
        self.expect(self.page.locator("main")).to_be_hidden()
        self.expect(self.page.locator("#views")).to_be_hidden()
        self.assertIsNone(self.page.evaluate("cy"))
        self.assertEqual((self.directory / "ledger.json").read_bytes(), before)
        self.assertEqual(self.errors, [])

    def test_parked_concern_says_what_it_is_waiting_on(self):
        state = session.editable(session.load(self.directory))
        state.update(goal="Ship it", origin="goal", current_question="first")
        state["nodes"] = [node("goal", answer="Ship it"),
                          {**node("first", parents=["goal"]), "question": "First?", "label": "Pick the store"},
                          {**node("second", parents=["first"]), "question": "Second?"}]
        self.publish(state)
        self.page.goto(self.url)
        self.expect(self.page.locator("#open-list")).to_contain_text("Second?")
        self.expect(self.page.locator("#open-list")).to_contain_text("Waiting on: Pick the store")
        self.expect(self.page.locator("#open-list")).not_to_contain_text("goal")
        self.assertEqual(self.errors, [])

    def test_deferred_concern_shows_its_revisit_condition_and_bare_card_makes_no_false_claim(self):
        state = session.editable(session.load(self.directory))
        state.update(goal="Ship it", origin="goal", current_question="now")
        state["nodes"] = [node("goal", answer="Ship it"),
                          {**node("now", parents=["goal"]), "question": "Bare question?"},
                          {**node("later", parents=["goal"]), "status": "deferred", "question": "Later?",
                           "defer_reason": "not blocking", "revisit_condition": "after v1 ships"}]
        self.publish(state)
        self.page.goto(self.url)
        self.expect(self.page.locator("#deferred-list")).to_contain_text("Revisit: after v1 ships")
        self.expect(self.page.locator("#call")).not_to_contain_text("replaces the recommendation")
        self.expect(self.page.locator("#call")).to_contain_text("Reply in chat with your answer")
        self.assertEqual(self.errors, [])

    def test_many_settled_items_fold_so_open_work_stays_visible(self):
        state = session.editable(session.load(self.directory))
        state.update(goal="Ship it", origin="goal", current_question="now")
        settled = [node(f"s{i}", answer=f"Answer {i}") for i in range(1, 13)]
        for item in settled:
            item["label"] = f"Settled {item['id'][1:]}"
        state["nodes"] = [node("goal", answer="Ship it"), *settled,
                          {**node("now", parents=["goal"]), "question": "Still to decide?"},
                          {**node("later", parents=["goal"]), "question": "Open one?", "label": "Open one"}]
        self.publish(state)
        self.page.goto(self.url)
        self.expect(self.page.locator("#settled-list > li")).to_have_count(5)
        self.expect(self.page.locator("#settled-list > li").first).to_contain_text("Settled 12")
        self.expect(self.page.locator("#settled-more-sum")).to_have_text("Show 7 earlier decided")
        self.expect(self.page.locator("#settled-more")).not_to_have_attribute("open", "")
        self.expect(self.page.locator("#open-list")).to_contain_text("Open one")
        self.assertEqual(self.errors, [])

    def test_finished_interview_says_it_is_the_users_turn_and_counts_acceptances(self):
        state = session.editable(session.load(self.directory))
        state.update(goal="Ship it", origin="goal", current_question=None)
        accepted = {**node("b", parents=["goal"], answer="B"), "authority": "delegated",
                    "authority_source": "chat: your arrow", "evidence": ["x.py:1"]}
        state["nodes"] = [node("goal", answer="Ship it"), node("a", parents=["goal"], answer="A"), accepted]
        self.publish(state)
        self.page.goto(self.url)
        self.expect(self.page.locator("#call")).to_contain_text("Your turn")
        self.expect(self.page.locator("#call")).to_contain_text("Review the draft brief and confirm it")
        self.expect(self.page.locator("#call")).not_to_contain_text("Nothing is waiting")
        self.expect(self.page.locator("#status-pill")).to_have_text("Ready for review")
        self.expect(self.page.locator("#accept-summary")).to_have_text("Accepted as suggested: 1 · Chosen by you: 1")
        self.expect(self.page.locator("#settled-list")).to_contain_text("you accepted the agent's suggestion")
        self.assertEqual(self.errors, [])

    def test_standing_delegation_is_not_shown_as_the_user_accepting_a_suggestion(self):
        state = session.editable(session.load(self.directory))
        state.update(goal="Ship it", origin="goal", current_question=None)
        ordinary = {**node("b", parents=["goal"], answer="B"), "authority": "delegated",
                    "authority_source": "chat: your arrow", "evidence": ["x.py:1"]}
        standing = {**node("c", parents=["goal"], answer="C"), "authority": "delegated",
                    "authority_source": "standing delegation (human opt-in); engram lenses: pg, ka", "evidence": ["lens said C"]}
        state["nodes"] = [node("goal", answer="Ship it"), node("a", parents=["goal"], answer="A"), ordinary, standing]
        self.publish(state)
        self.page.goto(self.url)
        self.expect(self.page.locator("#settled-list")).to_contain_text("you accepted the agent's suggestion")
        self.expect(self.page.locator("#settled-list")).to_contain_text("decided under your standing delegation")
        self.expect(self.page.locator("#accept-summary")).to_have_text(
            "Accepted as suggested: 1 · Chosen by you: 1 · Under standing delegation: 1")
        self.assertEqual(self.page.locator("#settled-list .badge.delegated").count(), 2)
        self.assertEqual(self.errors, [])

    def test_summary_is_unchanged_without_a_standing_delegation(self):
        state = session.editable(session.load(self.directory))
        state.update(goal="Ship it", origin="goal", current_question=None)
        state["nodes"] = [node("goal", answer="Ship it"), node("a", parents=["goal"], answer="A")]
        self.publish(state)
        self.page.goto(self.url)
        self.expect(self.page.locator("#accept-summary")).to_have_text("Accepted as suggested: 0 · Chosen by you: 1")
        self.assertEqual(self.errors, [])

    def test_questions_waiting_for_the_user_come_before_settled_work(self):
        state = session.editable(session.load(self.directory))
        state.update(goal="Ship it", origin="goal", current_question="now")
        state["nodes"] = [node("goal", answer="Ship it"), node("a", parents=["goal"], answer="A"),
                          node("f1", "fact", answer="Fact one"),
                          {**node("now", parents=["goal"]), "question": "Now?"},
                          {**node("later", parents=["goal"]), "question": "Later?"}]
        self.publish(state)
        self.page.goto(self.url)
        order = self.page.evaluate("""() => {
            const pos = id => document.getElementById(id).compareDocumentPosition.bind(document.getElementById(id));
            const before = (a, b) => Boolean(document.getElementById(a).compareDocumentPosition(document.getElementById(b)) & Node.DOCUMENT_POSITION_FOLLOWING);
            return {call: before('call', 'open-list'), open: before('open-list', 'settled-list'), facts: before('open-list', 'facts-list')};
        }""")
        self.assertEqual(order, {"call": True, "open": True, "facts": True})
        self.assertEqual(self.errors, [])

    def test_phone_widths_never_scroll_sideways(self):
        state = session.editable(session.load(self.directory))
        state.update(goal="Take every active repo under ~/dev/active to the git-golden state, researching each branch and recommending what can go", origin="goal", current_question="now")
        long_rec = "Both from one scan: the HTML page carries the design, the terminal is the baseline, with a-very-long-unbroken-token-" + "x" * 60
        state["nodes"] = [node("goal", answer=state["goal"]), node("a", parents=["goal"], answer="A " + "word " * 40),
                          {**node("now", parents=["goal"]), "question": "Terminal, HTML or both?", "recommendation": long_rec}]
        self.publish(state)
        for width in (390, 360, 320):
            with self.subTest(width=width):
                self.page.set_viewport_size({"width": width, "height": 844})
                self.page.goto(self.url)
                self.expect(self.page.locator("#call")).to_contain_text("Terminal, HTML or both?")
                scroll = self.page.evaluate("document.documentElement.scrollWidth")
                self.assertLessEqual(scroll, width)
        self.assertEqual(self.errors, [])

    def test_facts_are_a_separate_group_and_counts_agree(self):
        state = session.editable(session.load(self.directory))
        state.update(goal="Ship it", origin="goal", current_question="now")
        state["nodes"] = [node("goal", answer="Ship it"), node("a", parents=["goal"], answer="A"),
                          node("f1", "fact", answer="Fact one"), node("f2", "fact", answer="Fact two"),
                          {**node("now", parents=["goal"]), "question": "Now?"}]
        self.publish(state)
        self.page.goto(self.url)
        self.expect(self.page.locator("#settled-h")).to_have_text("Decided (1)")
        self.expect(self.page.locator("#facts-h")).to_have_text("Findings on record (2)")
        self.expect(self.page.locator("#counts")).to_contain_text("1 decided")
        self.expect(self.page.locator("#counts")).to_contain_text("2 findings")
        self.expect(self.page.locator("#facts-list")).to_contain_text("Unclassified record")
        self.assertEqual(self.errors, [])

    def epistemic_page(self, nodes=None, graph=True, current="safety-target"):
        state = session.editable(session.load(self.directory))
        state.update(goal="Decide how skills are owned and kept safe", origin="goal", current_question=current)
        state["nodes"] = nodes or acceptance_nodes()
        self.publish(state)
        if graph:
            library = pinned_cytoscape()
            self.context.unroute("**/cytoscape.min.js")
            self.context.route("**/cytoscape.min.js", lambda route: route.fulfill(path=library, content_type="application/javascript"))
        self.page.goto(self.url + ("#graph" if graph else "#ledger"))
        if graph:
            self.page.wait_for_function("cy !== null")
        return self.page

    def test_decisions_and_findings_are_labelled_differently_and_never_both_called_settled(self):
        legacy = {**node("legacy-fact", "fact", answer="Imports replace existing data"), "label": "Old fact"}
        page = self.epistemic_page(acceptance_nodes() + [legacy], graph=False)
        self.expect(page.locator("#settled-h")).to_have_text("Decided (1)")
        self.expect(page.locator("#facts-h")).to_have_text("Findings on record (6)")
        text = page.locator("#now").inner_text()
        self.assertNotRegex(text, r"(?i)\bsettled\b")
        self.assertNotIn("verified", text.lower(), "recorded findings are not relabelled as verified")
        rows = {row.locator("strong").inner_text(): row for row in page.locator("#facts-list > li").all()}
        for label, badge in (("Live vs repository layout", "Observed"), ("Mixed live and repository ownership", "Inferred"),
                             ("Intended ownership workflow", "Not established"), ("Old fact", "Unclassified record")):
            with self.subTest(label):
                self.expect(rows[label].locator(".badge")).to_have_text(badge)
        self.expect(page.locator("#settled-list .badge.user")).to_have_text("you decided")
        self.assertEqual(page.locator("#facts-list .badge.user, #facts-list .badge.delegated").count(), 0)
        page.locator('#ledger-list details[data-node-id="mixed-ownership"] summary').click()
        detail = page.locator('#ledger-list details[data-node-id="mixed-ownership"]')
        self.expect(detail).to_contain_text("not proof the finding is true")
        self.expect(detail).to_contain_text("Nobody decided this, and accepting it would not make it true")
        self.expect(detail).to_contain_text("concluded from observations; not itself observed")
        self.expect(detail).to_contain_text("Limits")
        self.assertEqual(self.errors, [])

    def test_unknown_means_not_established_and_is_not_phrased_as_absence(self):
        page = self.epistemic_page(graph=False)
        row = page.locator("#facts-list > li", has_text="Intended ownership workflow")
        self.expect(row).to_contain_text("This investigation has not yet established the intended ownership workflow.")
        self.expect(row.locator(".badge")).to_have_text("Not established")
        self.expect(row.locator(".badge")).to_have_attribute("title", "this investigation has not established it; that is not the same as it not existing")
        self.assertNotIn("does not exist", row.inner_text())
        scoped = page.locator("#facts-list > li", has_text="Multiple command execution paths")
        self.expect(scoped).to_contain_text("Other handlers were not read")

    def test_workflow_arrows_and_evidence_arrows_are_distinct_and_evidence_is_shown_on_demand(self):
        page = self.epistemic_page(acceptance_nodes() + [{**node("after-layout", parents=["layout-observed"]), "question": "Then what?"}], current="after-layout")
        waits = page.evaluate("cy.edges().filter(e => !e.hasClass('support')).map(e => e.id())")
        self.assertEqual(waits, ["waits:layout-observed>after-layout"])
        self.assertEqual(page.evaluate("cy.edges('.support').length"), 3)
        self.assertEqual(page.evaluate("cy.edges('.support').filter(e => e.style('display') !== 'none').length"), 0, "evidence edges are hidden until a node is selected")
        page.evaluate("void cy.getElementById('mixed-ownership').emit('tap')")
        shown = page.evaluate("cy.edges('.support.shown').map(e => e.id()).sort()")
        self.assertEqual(shown, ["supports:layout-observed>mixed-ownership", "supports:mixed-ownership>ownership-policy"])
        self.assertEqual(page.evaluate("cy.edges('.hot').length"), 0, "evidence is not a workflow chain")
        page.evaluate("void cy.getElementById('layout-observed').emit('tap')")
        self.assertEqual(page.evaluate("cy.edges('.hot').map(e => e.id())"), ["waits:layout-observed>after-layout"])
        self.assertFalse(page.evaluate("cy.getElementById('mixed-ownership').hasClass('faded')"), "a supported claim stays in view")
        self.assertTrue(page.evaluate("cy.getElementById('sdk-version').hasClass('faded')"))
        page.evaluate("void cy.getElementById('mixed-ownership').emit('tap')")
        self.expect(page.locator("#detail")).to_contain_text("Relies on as evidence")
        self.expect(page.locator("#detail")).to_contain_text("Evidence for")
        page.get_by_role("button", name="How to read").click()
        legend = page.locator("#legend").inner_text()
        self.assertIn("B waits for A (workflow order only; it does not mean A proves B)", legend)
        self.assertIn("A is evidence for B", legend)
        self.assertIn("not proof it is true", legend)
        self.assertEqual(self.errors, [])

    def test_graph_cards_name_the_finding_type_and_mark_unknowns(self):
        page = self.epistemic_page()
        badges = page.evaluate("Object.fromEntries([...document.querySelectorAll('#cards .card')].map(c => [c.dataset.id, c.querySelector('.bd')?.textContent]))")
        self.assertEqual((badges["layout-observed"], badges["mixed-ownership"], badges["ownership-workflow"]), ("Observed", "Inferred", "Not established"))
        self.assertEqual(badges["ownership-policy"], "You decided")
        self.assertEqual(page.evaluate("cy.getElementById('ownership-workflow').style('border-style')"), "dotted")

    def test_changed_evidence_flags_for_review_and_leaves_the_decision_as_it_was(self):
        page = self.epistemic_page(graph=False)
        self.assertEqual(page.locator(".badge.review").count(), 0)
        state = session.editable(session.load(self.directory))
        for item in state["nodes"]:
            if item["id"] == "layout-observed":
                item.update(answer="3 live entries are symlinks; 3 are plain copies.", evidence=[receipt(observed="3 and 3", at="2026-10-03T08:00:00+00:00")])
        self.publish(state, "Re-listed the folders")
        self.expect(page.locator("#status-pill")).to_have_text("Needs a second look")
        self.expect(page.locator("#review-h")).to_have_text("Needs review (2)")
        self.expect(page.locator("#review-list")).to_contain_text("Its answer and authorization are unchanged.")
        decided = page.locator("#settled-list > li", has_text="Skill ownership")
        self.expect(decided).to_contain_text("The repository owns every skill")
        self.expect(decided.locator(".badge.user")).to_have_text("you decided")
        self.expect(decided.locator(".badge.review")).to_have_text("needs review")
        self.assertEqual(page.locator("#facts-list .badge.review").count(), 1)
        python_flags = {k: v for k, v in session.review_flags(session.load(self.directory)["nodes"]).items()}
        self.assertEqual(page.evaluate("Object.fromEntries(reviewFlags())"), python_flags, "the viewer and the helper derive the same flags")
        state = session.editable(session.load(self.directory))
        for item in state["nodes"]:
            if item["id"] in ("ownership-policy", "mixed-ownership"):
                item["label"] = item["label"] + " (renamed)"
        self.publish(state, "Rename only: a label edit is not a review")
        self.expect(page.locator("#settled-list > li", has_text="renamed")).to_contain_text("needs review")
        self.expect(page.locator("#review-h")).to_have_text("Needs review (2)")
        self.assertEqual(page.evaluate("Object.fromEntries(reviewFlags())"), session.review_flags(session.load(self.directory)["nodes"]))

    def test_review_flags_follow_the_same_rules_in_the_viewer_through_a_review_chain(self):
        nodes = acceptance_nodes() + [{**self.decision_on("contain-handlers", "command-paths")}]
        page = self.epistemic_page(nodes, graph=False)
        helper = lambda: session.review_flags(session.load(self.directory)["nodes"])

        def viewer_flags():
            page.wait_for_function("version => LEDGER && LEDGER.version >= version", arg=session.load(self.directory)["version"], timeout=8000)
            return page.evaluate("Object.fromEntries(reviewFlags())")

        def edit(**by_id):
            state = session.editable(session.load(self.directory))
            for item in state["nodes"]:
                item.update(by_id.get(item["id"], {}))
            return state

        self.publish(edit(**{"layout-observed": {"answer": "3 live entries are symlinks; 3 are plain copies."}}), "Observation changed")
        self.assertEqual(sorted(helper()), ["mixed-ownership", "ownership-policy"])
        self.expect(page.locator("#review-h")).to_have_text("Needs review (2)")
        self.assertEqual(viewer_flags(), helper())
        version = session.load(self.directory)["version"]
        session.publish(self.directory, session.editable(session.load(self.directory)), version, "Review the inference only",
                        revalidated={"mixed-ownership": "Still holds"})
        self.assertEqual(sorted(helper()), ["ownership-policy"], "reviewing the inference does not review the decision")
        self.expect(page.locator("#review-h")).to_have_text("Needs review (1)")
        self.assertEqual(viewer_flags(), helper())
        self.publish(edit(**{"command-paths": {"status": "superseded", "answer": None, "authority": None, "authority_source": None}}), "Withdraw evidence")
        self.assertEqual(sorted(helper()), ["contain-handlers", "ownership-policy"])
        self.assertEqual(viewer_flags(), helper())
        version = session.load(self.directory)["version"]
        session.publish(self.directory, session.editable(session.load(self.directory)), version, "Review the decisions",
                        revalidated={"ownership-policy": "User kept it", "contain-handlers": "User kept it without that evidence"})
        self.assertEqual(helper(), {})
        self.expect(page.locator("#review-h")).to_be_hidden()
        self.assertEqual(viewer_flags(), {})

    def decision_on(self, node_id, support):
        return {"id": node_id, "kind": "decision", "status": "settled", "prerequisites": ["goal"], "evidence": [], "owner": "User", "gate": "Choose",
                "answer": "Wrap the three handlers", "authority": "user", "authority_source": "chat turn 10: user chose it", "supported_by": [support]}

    def test_a_recommendation_is_a_proposal_and_its_rationale_is_split(self):
        page = self.epistemic_page(graph=False)
        call = page.locator("#call")
        self.expect(call).to_contain_text("Recommended by the agent — a proposal, not a decision")
        self.expect(call).to_contain_text("Why: what the current architecture allows")
        self.expect(call).to_contain_text("Only three handlers are known today")
        self.expect(call).to_contain_text("Why: your outcome or threat model")
        self.expect(call).to_contain_text("Not stated yet. This proposal rests on feasibility alone and stays provisional")
        self.assertEqual(page.locator("#settled-list").inner_text().count("Safety target"), 0, "an unaccepted proposal is not listed as decided")

    def test_receipts_show_what_was_checked_and_legacy_notes_are_labelled_as_notes(self):
        page = self.epistemic_page(graph=False)
        page.locator('#ledger-list details[data-node-id="layout-observed"] summary').click()
        detail = page.locator('#ledger-list details[data-node-id="layout-observed"]')
        for expected in ("Checked: Directory listing of the live skills folder", "When: 2026-10-02T09:15:00+00:00", "Observed: 4 entries",
                         "Exact check (stored, never run by the viewer): ls -l ~/.agents/skills", "Artifact: git:7a045e4"):
            self.expect(detail).to_contain_text(expected)
        page.locator('#ledger-list details[data-node-id="mixed-ownership"] summary').click()
        self.expect(page.locator('#ledger-list details[data-node-id="mixed-ownership"]')).to_contain_text("Unstructured note (no receipt): Inferred from layout-observed")

    def test_the_viewer_refuses_an_invalid_epistemic_snapshot(self):
        page = self.epistemic_page(graph=False)
        bad = json.loads(urlopen(self.url + "/ledger.json").read())
        next(n for n in bad["nodes"] if n["id"] == "mixed-ownership")["claim"] = {"type": "verified", "scope": "x"}
        bad["version"] += 1
        page.route("**/ledger.json*", lambda route: route.fulfill(status=200, content_type="application/json", body=json.dumps(bad)))
        self.expect(page.locator("#connection")).to_contain_text("Invalid finding type", timeout=6000)
        self.expect(page.locator("#facts-list")).to_contain_text("Mixed live and repository ownership")

    def test_long_answers_are_kept_whole_with_a_toggle(self):
        tail = "TAILMARK-end-of-a-long-answer"
        state = session.editable(session.load(self.directory))
        state.update(goal="Ship it", origin="goal", current_question="now")
        state["nodes"] = [node("goal", answer="Ship it"),
                          node("a", parents=["goal"], answer="Long answer. " * 30 + tail),
                          {**node("now", parents=["goal"]), "question": "Now?"}]
        self.publish(state)
        self.page.goto(self.url)
        self.page.get_by_role("button", name="Ledger", exact=True).click()
        self.expect(self.page.locator("#settled-list")).to_contain_text(tail)
        self.expect(self.page.locator("#settled-list")).not_to_contain_text("…")
        button = self.page.locator("#settled-list .more")
        self.expect(button).to_have_text("Show more")
        button.click()
        self.expect(button).to_have_text("Show less")
        self.assertEqual(self.errors, [])

    def test_assumed_defaults_are_listed_apart_from_decisions(self):
        state = session.editable(session.load(self.directory))
        state.update(goal="Ship it", origin="goal", current_question="now")
        state["nodes"] = [node("goal", answer="Ship it"),
                          {**node("now", parents=["goal"]), "question": "Now?"}]
        state["assumed"] = [{"text": "One user, one machine", "why": "Both answers build the same thing"}]
        self.publish(state)
        self.page.goto(self.url)
        self.expect(self.page.locator("#assumed-h")).to_have_text("I'll assume these unless you object (1)")
        self.expect(self.page.locator("#assumed-list")).to_contain_text("One user, one machine")
        self.expect(self.page.locator("#assumed-list")).to_contain_text("Why it is safe: Both answers build the same thing")
        self.expect(self.page.locator("#settled-list")).not_to_contain_text("One user")
        self.assertEqual(self.errors, [])

    def test_contradicted_decision_is_flagged_instead_of_ready_for_review(self):
        state = session.editable(session.load(self.directory))
        state.update(goal="Ship it", origin="goal", current_question=None)
        fact = {**node("f", "fact", answer="The scanner does not exist"), "contradicts": "d", "label": "Scanner missing"}
        state["nodes"] = [node("goal", answer="Ship it"),
                          {**node("d", parents=["goal"], answer="Reuse the scanner"), "label": "Reuse scanner"}, fact]
        self.publish(state)
        self.page.goto(self.url)
        self.expect(self.page.locator("#call")).to_contain_text("Needs a second look")
        self.expect(self.page.locator("#call")).to_contain_text('"Reuse scanner" is contradicted by "Scanner missing"')
        self.expect(self.page.locator("#call")).not_to_contain_text("Your turn")
        self.expect(self.page.locator("#status-pill")).to_have_text("Needs a second look")
        self.expect(self.page.locator("#settled-list")).to_contain_text("contradicted — needs a second look")
        self.assertEqual(self.errors, [])

    def test_simulated_session_is_unmistakable_and_cannot_be_confirmed(self):
        directory = session.create(self.temp.name, "simulated")
        state = session.editable(session.load(directory))
        goal = {**node("goal", answer="Ship it"), "authority": "simulated"}
        decision = {**node("d", parents=["goal"], answer="Do it"), "authority": "simulated",
                    "authority_source": "operator agent (persona: cautious): accepted"}
        state.update(goal="Ship it", origin="goal", nodes=[goal, decision])
        session.publish(directory, state, 0, "Operator agent confirmed the goal")
        server = viewer.make_server(directory)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        def stop():
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)
        self.addCleanup(stop)
        self.page.goto(f"http://127.0.0.1:{server.server_port}/ledger-view.html")
        self.expect(self.page.locator("#sim-banner")).to_be_visible()
        self.expect(self.page.locator("#sim-banner")).to_contain_text("no human decided this")
        self.expect(self.page.locator("#status-pill")).to_have_text("Simulated")
        self.expect(self.page.locator("#accept-summary")).to_have_text("Simulated answers: 1 \u00b7 Human answers: 0")
        self.expect(self.page.locator("#settled-list")).to_contain_text("simulated answer (no human)")
        self.expect(self.page.locator("#call")).to_contain_text("Awaiting a human")
        self.expect(self.page.locator("#call")).not_to_contain_text("Your turn")
        self.assertEqual(self.errors, [])

    def test_saved_ended_view_is_read_only_offline_and_after_restart(self):
        self.confirm()
        self.page.goto(self.url)
        self.expect(self.page.locator("#connection")).to_have_attribute("data-health", "live")
        state = session.editable(session.load(self.directory))
        state["nodes"][3]["answer"] = '</script><script>window.injected=true</script>'
        self.publish(state)
        ended = session.end(self.directory, "stopped", "User stopped")
        self.expect(self.page.locator("#connection")).to_have_attribute("data-health", "ended")
        snapshot = viewer.save_snapshot(self.directory)
        self.server.shutdown()
        self.page.goto(snapshot.as_uri())
        self.expect(self.page.locator("#connection")).to_have_attribute("data-health", "ended")
        self.expect(self.page.locator("#connection")).to_contain_text("Interview stopped")
        self.expect(self.page.locator('[data-node-id="backup"]')).to_contain_text("unresolved")
        self.assertIsNone(self.page.evaluate("window.injected"))
        self.assertIsNone(self.page.evaluate("timer"))
        self.assertEqual(session.load(self.directory), ended)
        self.assertEqual(self.errors, [])

    def test_active_offline_snapshot_does_not_start_polling(self):
        self.confirm()
        snapshot = viewer.save_snapshot(self.directory)
        self.page.goto(snapshot.as_uri())
        self.expect(self.page.locator("#connection")).to_contain_text("read-only")
        self.expect(self.page.locator("#current")).to_contain_text("Require a backup?")
        self.assertIsNone(self.page.evaluate("timer"))
        self.assertEqual(self.errors, [])

    def test_failed_poll_retains_state_and_same_snapshot_recovers(self):
        self.confirm()
        self.page.goto(self.url)
        self.expect(self.page.locator("#connection")).to_have_attribute("data-health", "live")
        original = (self.directory / "ledger.json").read_bytes()
        (self.directory / "ledger.json").write_text("{")
        self.expect(self.page.locator("#connection")).to_have_attribute("data-health", "error")
        self.expect(self.page.locator("#connection")).to_contain_text("last valid snapshot")
        self.expect(self.page.locator("#current")).to_contain_text("Require a backup?")
        (self.directory / "ledger.json").write_bytes(original)
        self.expect(self.page.locator("#connection")).to_have_attribute("data-health", "live")
        state = session.editable(session.load(self.directory))
        state.update(status="stopped", current_question=None)
        self.publish(state, "Fixture user stopped interview")
        self.expect(self.page.locator("#connection")).to_have_attribute("data-health", "ended")
        (self.directory / "ledger.json").write_text("{")
        self.page.wait_for_timeout(2300)
        self.expect(self.page.locator("#connection")).to_contain_text("Interview stopped")
        self.assertEqual(self.errors, [])

    def test_validate_rejects_untrusted_ledger_fields(self):
        self.confirm()
        self.page.goto(self.url)
        base = session.load(self.directory)
        def envelope(nodes):
            return {"nodes": nodes, "frontier": base["frontier"], "origin": base["origin"], "goal": base["goal"], "current_question": base["current_question"], "draft": base["draft"]}
        unresolved = json.loads(json.dumps(base["nodes"]))
        for entry in unresolved:
            if entry["id"] == "backup":
                entry.pop("owner", None)
                entry.pop("gate", None)
        wrong_authority = json.loads(json.dumps(base["nodes"]))
        for entry in wrong_authority:
            if entry["id"] == "import-behavior":
                entry["authority"] = "user"
        blank_evidence = json.loads(json.dumps(base["nodes"]))
        for entry in blank_evidence:
            if entry["id"] == "import-behavior":
                entry["evidence"] = [""]
        cases = [("unresolved decision missing owner/gate", envelope(unresolved)), ("settled fact with user authority", envelope(wrong_authority)), ("settled fact with blank evidence", envelope(blank_evidence))]
        for name, ledger in cases:
            with self.subTest(name=name):
                with self.assertRaises(Exception):
                    self.page.evaluate(f"validate({json.dumps(ledger)})")


if __name__ == "__main__":
    unittest.main()
