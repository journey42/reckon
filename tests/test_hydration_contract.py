"""Tests for the hydration contract between the entry and the exported HTML.

React error #418 was logged on every visit to a parameterised route: Reflex
hydrates unconditionally while the host serves those URLs a root-only shell that
cannot contain the page. Two properties have to hold for the fix to work, and
both are pinned here because each was got wrong once already, on staging:

* the entry must hydrate prerendered documents and mount client-side otherwise;
* the thing it keys on must be markup the export already writes — annotating the
  document (a ``<meta>``, then an attribute on ``<html>``) made the *prerendered*
  routes mismatch, so no marker may be added anywhere.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import hydration_plugin  # noqa: E402
from frontend_export_fixups import (  # noqa: E402
    FALLBACK,
    INDEX,
    NOT_FOUND,
    main,
    strip_chrome,
)

SHELLS = (FALLBACK, NOT_FOUND)


def test_entry_hydrates_and_has_a_client_render_path():
    entry = hydration_plugin.ENTRY_CLIENT_JS
    assert "hydrateRoot(document" in entry
    assert "createRoot(document).render" in entry
    # Reflex's own entry was unconditional; make sure it did not creep back.
    assert entry.count("hydrateRoot(") == 1
    assert entry.count("createRoot(") == 1


def test_entry_keys_on_the_framework_rendered_hint():
    entry = hydration_plugin.ENTRY_CLIENT_JS
    assert hydration_plugin.HYDRATE_FALLBACK_HINT in entry
    # The decision must come from the served document, not from a list of routes
    # (which would have to be kept in sync) and not from a marker we add.
    assert "servedFallback()" in entry
    assert "window.location.pathname" not in entry


def test_no_marker_is_written_into_the_document():
    """Both earlier attempts failed for this reason; guard against a third."""
    entry = hydration_plugin.ENTRY_CLIENT_JS
    source = (ROOT / "scripts" / "frontend_export_fixups.py").read_text(encoding="utf-8")
    for forbidden in ("querySelector(\"meta[name=", "documentElement.getAttribute", "data-reflex-prerendered-route"):
        assert forbidden not in entry, f"entry still consults a document marker: {forbidden}"
        assert forbidden not in source, f"fixups still writes a document marker: {forbidden}"


def test_plugin_takes_ownership_of_the_entry():
    assert hydration_plugin.ConditionalHydrationPlugin().provides_entry_client() is True


def test_the_hint_separates_shells_from_prerendered_pages_on_a_real_export():
    """The signal has to hold for real files, not for a fixture.

    Skipped when no export is present (a fresh clone), because inventing the two
    kinds of file here would test the test rather than Reflex's output.
    """
    out = ROOT / ".web" / "build" / "client"
    sample = out / "login" / INDEX
    shell = out / FALLBACK
    if not (sample.is_file() and shell.is_file()):
        import pytest

        pytest.skip("no exported frontend at .web/build/client")

    hint = hydration_plugin.HYDRATE_FALLBACK_HINT
    assert hint in shell.read_text(encoding="utf-8"), "the shell must carry the fallback hint"
    for prerendered in (out / INDEX, sample, out / "live" / "all" / INDEX):
        if prerendered.is_file():
            assert hint not in prerendered.read_text(encoding="utf-8"), (
                f"{prerendered.relative_to(out)} would be mounted client-side, losing its prerender"
            )


def test_a_spa_mode_export_still_gets_the_files_the_host_rewrites_to(tmp_path, monkeypatch, capsys):
    """SPA mode emits no __spa-fallback.html, and the shared host config rewrites
    unknown paths to exactly that name."""
    (tmp_path / INDEX).write_text("<html><body>shell</body></html>", encoding="utf-8")
    monkeypatch.setattr(sys, "argv", ["fixups", "--out", str(tmp_path)])
    assert main() == 0
    for name in SHELLS:
        assert (tmp_path / name).read_text(encoding="utf-8") == (tmp_path / INDEX).read_text(encoding="utf-8")
    # Idempotent: a second run must not churn the files.
    before = {n: (tmp_path / n).read_bytes() for n in SHELLS}
    monkeypatch.setattr(sys, "argv", ["fixups", "--out", str(tmp_path)])
    assert main() == 0
    assert {n: (tmp_path / n).read_bytes() for n in SHELLS} == before


def test_missing_export_is_an_error_rather_than_a_silent_empty_deploy(tmp_path, monkeypatch):
    monkeypatch.setattr(sys, "argv", ["fixups", "--out", str(tmp_path / "nope")])
    assert main() == 2


def test_strip_chrome_removes_only_the_shell_chrome():
    html = (
        '<html><head><title>t</title></head><body>'
        '<section aria-label="Notifications alt+T" tabindex="-1"></section>'
        '<div data-is-root-theme="true" class="radix-themes css-0">'
        '<div title="Connection Error: "></div></div>'
        "<script>console.log(1)</script></body></html>"
    )
    stripped = strip_chrome(html)
    assert "Notifications" not in stripped
    assert "Connection Error" not in stripped
    assert "console.log(1)" in stripped
    assert "<title>t</title>" in stripped
