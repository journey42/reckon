#!/usr/bin/env python3
"""Make an exported frontend bundle safe for the host's navigation fallback.

`reflex export` writes `__spa-fallback.html` when it prerenders routes, and
copies it to `404.html`. In SPA mode (`--no-ssr`) it writes only `index.html`,
but `deploy/staticwebapp.config.json` — which is shared with production — keeps
rewriting every unknown path to `/__spa-fallback.html`. Without that file every
deep link 404s, which is a worse bug than the hydration warning this is all
about. Copy the file instead of retargeting the config, so a single config stays
correct for both build modes and a staging experiment cannot change what
production serves.

Usage:
    python scripts/frontend_export_fixups.py [--out .web/build/client] [--dry-run]
"""

from __future__ import annotations

import argparse
import re
import shutil
import sys
from pathlib import Path

FALLBACK = "__spa-fallback.html"
NOT_FOUND = "404.html"
INDEX = "index.html"

# Files that are *not* any one route's prerender: the host serves them for URLs
# the export never rendered, so they must never claim to be prerendered.
SHELLS = (FALLBACK, NOT_FOUND)

#: Must match MARKER_NAME in hydration_plugin.py, which reads it in the browser.
#: It is an attribute on <html>, deliberately: the whole document, <head>
#: included, is part of the tree React hydrates, so a stamped <meta> is an
#: unexpected node and reproduces the very mismatch this exists to remove.
#: Extra *attributes* on server markup are kept and ignored instead.
MARKER_NAME = "data-reflex-prerendered-route"

_META_RE = re.compile(r'\s*data-reflex-prerendered-route="[^"]*"', re.I)
_HTML_RE = re.compile(r"(<html\b[^>]*?)(/?>)", re.I)


def route_for(relative: Path) -> str:
    """The URL an exported HTML file was prerendered for.

    ``index.html`` -> ``/``, ``login/index.html`` and ``login.html`` ->
    ``/login``, ``live/all/index.html`` -> ``/live/all``.
    """
    parts = list(relative.parts)
    if parts[-1] == INDEX:
        parts = parts[:-1]
    else:
        parts[-1] = parts[-1][: -len(".html")]
    return "/" + "/".join(parts)


def stamp(html: str, route: str) -> str:
    """Record which route this document was prerendered for, or refresh a stale one."""
    attr = f' {MARKER_NAME}="{route}"'
    if _META_RE.search(html):
        # Normalised the same way every pass, so stamping twice is a no-op.
        return _META_RE.sub(attr, html, count=1)
    return _HTML_RE.sub(lambda m: m.group(1) + attr + m.group(2), html, count=1)


def unstamp(html: str) -> str:
    """Remove the marker, leaving the document byte-identical to the export."""
    return _META_RE.sub("", html, count=1)

# The markup Reflex/React Router renders into the shell: the toaster portal, the
# Radix root theme, and Reflex's connection banner, plus React Router's
# HydrateFallback hint. The client's first render of a real page cannot match
# this, which is what makes hydrating the shell log React error #418.
_CHROME = [
    re.compile(r'<section aria-label="Notifications[^>]*></section>'),
    re.compile(r'<div data-is-root-theme="true".*?</div>(?=\s*<script|\s*</body>)', re.S),
]


def strip_chrome(html: str) -> str:
    """Return the shell with React-rendered markup removed, head/scripts intact."""
    for pattern in _CHROME:
        html = pattern.sub("", html, count=1)
    return html


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=".web/build/client", help="exported client directory")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument(
        "--strip-chrome",
        choices=("none", "fallback", "all"),
        default="none",
        help="remove server-rendered markup from the shell(s): fallback/404 only, or index.html too",
    )
    args = ap.parse_args()

    root = Path(args.out)
    if not root.is_dir():
        print(f"error: {root} is not a directory (run `reflex export` first)", file=sys.stderr)
        return 2

    index = root / INDEX
    if not index.is_file():
        print(f"error: {index} missing — the export produced nothing to serve", file=sys.stderr)
        return 2

    for name in (FALLBACK, NOT_FOUND):
        target = root / name
        if target.is_file():
            print(f"  {name}: already present ({target.stat().st_size} bytes)")
            continue
        if args.dry_run:
            print(f"  {name}: would copy from {INDEX}")
            continue
        shutil.copyfile(index, target)
        print(
            f"  {name}: created from {INDEX} ({target.stat().st_size} bytes) — "
            "the host rewrites unknown paths here"
        )

    prerendered = sorted(p.parent.relative_to(root).as_posix() for p in root.glob("*/index.html"))
    print(
        f"  prerendered routes: {len(prerendered)}"
        + (f" (e.g. {', '.join(prerendered[:4])})" if prerendered else " — SPA mode: one shell for all routes")
    )

    if args.strip_chrome != "none":
        targets = [FALLBACK, NOT_FOUND] + ([INDEX] if args.strip_chrome == "all" else [])
        for name in targets:
            target = root / name
            if not target.is_file():
                continue
            html = target.read_text(encoding="utf-8")
            stripped = strip_chrome(html)
            if stripped == html:
                print(f"  {name}: no shell chrome found to remove")
                continue
            if not args.dry_run:
                target.write_text(stripped, encoding="utf-8")
            removed = len(html) - len(stripped)
            print(f"  {name}: removed {removed} bytes of prerendered chrome")

    # Tell the browser entry which URL each document was rendered for, so it can
    # hydrate when the bytes match and mount client-side when they cannot. See
    # hydration_plugin.py for why guessing on the client is not an option.
    stamped = unstamped = 0
    if not args.dry_run:
        for html_file in sorted(root.rglob("*.html")):
            rel = html_file.relative_to(root)
            if rel.parts and rel.parts[0] == "assets":
                continue
            html = html_file.read_text(encoding="utf-8")
            if rel.as_posix() in SHELLS:
                if _META_RE.search(html):
                    html_file.write_text(unstamp(html), encoding="utf-8")
                    unstamped += 1
                continue
            route = route_for(rel)
            updated = stamp(html, route)
            if updated != html:
                html_file.write_text(updated, encoding="utf-8")
            stamped += 1
        # The fallbacks are copied from index.html above, which by then carries
        # the root route's marker; make sure neither keeps it.
        for name in SHELLS:
            shell = root / name
            if shell.is_file() and _META_RE.search(shell.read_text(encoding="utf-8")):
                shell.write_text(unstamp(shell.read_text(encoding="utf-8")), encoding="utf-8")
                unstamped += 1
    print(
        f"  marker '{MARKER_NAME}': stamped {stamped} prerendered file(s), "
        f"cleared {unstamped} shell(s)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
