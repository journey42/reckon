"""Tests for the client-render entry and the export fixups.

Every visit used to log ``Minified React error #418`` — "the server rendered HTML
didn't match the client, so this tree will be regenerated" — because Reflex's
entry hydrates the whole document, whose ``<head>`` can never equal the one React
renders. Three attempts to keep hydrating were measured on staging (see the
plugin's docstring) and each moved the error somewhere else; mounting on the
client removes it everywhere. These tests keep the reasoning from being undone
silently.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import client_render_plugin  # noqa: E402
from frontend_export_fixups import (  # noqa: E402
    FALLBACK,
    INDEX,
    NOT_FOUND,
    main,
    strip_chrome,
)

SHELLS = (FALLBACK, NOT_FOUND)


def test_entry_mounts_instead_of_hydrating():
    entry = client_render_plugin.ENTRY_CLIENT_JS
    assert "createRoot(document).render" in entry
    # Hydration of the whole document cannot match this app's exported <head>;
    # reintroducing it brings back #418 on every route.
    assert "hydrateRoot(" not in entry.split("//")[0] + "\n".join(
        line for line in entry.splitlines() if not line.strip().startswith("//")
    )


def test_entry_does_not_branch_on_route_or_annotate_the_document():
    """Both earlier designs keyed off a marker written into the HTML: a <meta>
    with the route, then an attribute on <html>. Each made the prerendered routes
    mismatch, because everything in the document is compared during hydration."""
    entry = client_render_plugin.ENTRY_CLIENT_JS
    assert "window.location" not in entry
    assert "querySelector" not in entry
    assert "data-reflex-prerendered-route" not in entry
    source = (ROOT / "scripts" / "frontend_export_fixups.py").read_text(encoding="utf-8")
    assert "data-reflex-prerendered-route" not in source
    # The fixups may copy files, never write markup.
    code = source.split('"""', 2)[-1]  # skip the module docstring, which explains the history
    assert not re.search(r"<\s*(meta|html|head|body)\b", code), "fixups must not build markup"
    assert "write_text" in source  # only used by the optional chrome strip


def test_plugin_takes_ownership_of_the_entry():
    assert client_render_plugin.ClientRenderPlugin().provides_entry_client() is True


def test_a_spa_mode_export_still_gets_the_files_the_host_rewrites_to(tmp_path, monkeypatch):
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


def test_the_exported_html_is_left_byte_identical(tmp_path, monkeypatch):
    """The fixups may copy files, never edit them: any change is part of the tree
    the browser compares."""
    page = '<html><head><title>t</title></head><body><p>route content</p></body></html>'
    (tmp_path / INDEX).write_text(page, encoding="utf-8")
    prerendered = tmp_path / "login"
    prerendered.mkdir()
    (prerendered / INDEX).write_text(page, encoding="utf-8")
    monkeypatch.setattr(sys, "argv", ["fixups", "--out", str(tmp_path)])
    assert main() == 0
    assert (prerendered / INDEX).read_text(encoding="utf-8") == page
    assert (tmp_path / INDEX).read_text(encoding="utf-8") == page
