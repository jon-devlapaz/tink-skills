# Running the tests

One command runs the whole suite, including the browser tests:

```sh
python -m pip install -r tests/requirements-browser.txt \
  && python -m playwright install chromium \
  && SEED_ME_REQUIRE_BROWSER=1 python -m unittest discover -s tests -v
```

On Linux add `--with-deps` to the `playwright install` step.

The seed-me viewer tests (`test_seed_me_viewer.py`, class `TestViewerBrowser`) drive a real browser
through Playwright, which is pinned in `tests/requirements-browser.txt`.

- **Browser launch** tries Playwright's bundled Chromium, then system Google Chrome, and gives up
  after 20 seconds each.
- **Without `SEED_ME_REQUIRE_BROWSER=1`**, a missing or unlaunchable browser skips the class and
  prints one `SKIPPED Browser tests cannot run: <cause>. Fix: <command>` line to stderr.
- **With `SEED_ME_REQUIRE_BROWSER=1`** the same condition is a hard failure. CI sets it, and its
  `browser` job also fails if any browser test is reported as skipped.
- **Cytoscape graph test** fetches the exact URL pinned in `skills/seed-me/assets/ledger-view.html`,
  checks the bytes against that page's SRI hash, and caches the file in the system temp directory.
  Set `SEED_ME_CYTOSCAPE_PATH` only to use a local copy while offline.
