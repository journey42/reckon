#!/usr/bin/env python3
"""Make an exported frontend bundle safe for the host's navigation fallback.

Two jobs, both about files rather than markup:

1. ``reflex export`` writes ``__spa-fallback.html`` when it prerenders routes and
   copies it to ``404.html``. In SPA mode (``--no-ssr``) it writes only
   ``index.html``, but ``deploy/staticwebapp.config.json`` — shared with
   production — keeps rewriting every unknown path there. Without the file every
   deep link 404s, so create it. Fixing this in the bundle rather than by
   retargeting the config means a staging experiment cannot change what
   production serves.

2. Optionally empty the shell's prerendered body (``--strip-chrome``), kept for
   the record: it was measured and it does *not* affect hydration either way.

Deliberately absent: any marker written into the HTML. Stamping the prerendered
route — as a ``<meta>``, then as an attribute on ``<html>`` — was tried on the
deployed site twice, and both variants made *every* prerendered route log React
error #418. The whole document, head and root element included, is the tree
React hydrates, so no edit to it is neutral. The entry therefore mounts on the client
(``client_render_plugin.py``).

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

# The markup Reflex/React Router renders into the shell: the toaster portal, the
# Radix root theme and Reflex's connection banner, plus React Router's
# HydrateFallback hint. Only used by the optional --strip-chrome experiment.
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
            print(f"  {name}: removed {len(html) - len(stripped)} bytes of prerendered chrome")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
