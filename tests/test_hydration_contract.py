"""Tests for the hydration contract between the entry and the export fixups.

React error #418 was logged on every visit to a parameterised route: Reflex
hydrates unconditionally, but the host serves a root-only shell for those URLs,
so the markup can never contain the page. The fix splits into two halves that
have to agree on a marker name, which is what these tests pin down.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import hydration_plugin  # noqa: E402
from frontend_export_fixups import (  # noqa: E402
    INDEX,
    MARKER_NAME,
    SHELLS,
    route_for,
    stamp,
    unstamp,
)


def test_the_two_halves_agree_on_the_marker_name():
    """The entry reads what the fixups write; a rename on one side must fail here."""
    assert hydration_plugin.MARKER_NAME == MARKER_NAME


def test_entry_hydrates_only_on_a_matching_marker_and_otherwise_mounts():
    entry = hydration_plugin.ENTRY_CLIENT_JS
    assert "hydrateRoot(document" in entry
    assert "createRoot(document).render" in entry
    # The decision must be made from the marker and the URL, not from a guess
    # about which routes are dynamic — new routes come free.
    assert 'meta[name="${MARKER}"]' in entry
    assert "window.location.pathname" in entry
    assert "function normalize" in entry
    # Reflex's own entry was unconditional; make sure it did not creep back.
    assert entry.count("hydrateRoot(") == 1


def test_plugin_takes_ownership_of_the_entry():
    plugin = hydration_plugin.ConditionalHydrationPlugin()
    assert plugin.provides_entry_client() is True


def test_route_for_maps_exported_files_back_to_urls():
    assert route_for(Path("index.html")) == "/"
    assert route_for(Path("login/index.html")) == "/login"
    assert route_for(Path("login.html")) == "/login"
    assert route_for(Path("live/all/index.html")) == "/live/all"
    assert route_for(Path("group/[slug].html")) == "/group/[slug]"


def test_stamping_round_trips_and_replaces_a_stale_route():
    html = "<html><head><title>t</title></head><body><p>hi</p></body></html>"
    once = stamp(html, "/login")
    assert f'<meta name="{MARKER_NAME}" content="/login"/>' in once
    # Idempotent, and a second pass with a different route replaces rather than
    # piles up a second marker.
    assert stamp(once, "/login") == once
    twice = stamp(once, "/demo")
    assert twice.count(MARKER_NAME) == 1
    assert 'content="/demo"' in twice
    assert unstamp(twice) == html


def test_html_without_a_head_still_gets_the_marker():
    html = "<html><body><p>hi</p></body></html>"
    assert MARKER_NAME in stamp(html, "/x")


def test_the_shells_that_stand_for_unrendered_urls_are_never_stamped():
    """404.html and __spa-fallback.html are served for URLs that were never
    rendered, so a marker on them would tell the entry to hydrate falsely."""
    assert set(SHELLS) == {"404.html", "__spa-fallback.html"}
    assert INDEX not in SHELLS  # the root route's own prerender must stay stamped
