"""Mount the app on the client instead of hydrating the document.

Why
---
Every visit logged ``Minified React error #418``: "Hydration failed because the
server rendered HTML didn't match the client. As a result this tree will be
regenerated on the client." Reflex's stock entry is an unconditional::

    hydrateRoot(document, createElement(HydratedRouter));

and that cannot succeed for this app. The whole document is the tree being
hydrated, and the exported HTML's ``<head>`` is not the ``<head>`` React renders:
Vite injects its scripts and stylesheets at one place, Reflex's document
component renders them, meta tags and emotion styles at another, so the two never
line up. React then throws the tree away and renders it again — the original
markup, the diff work and the console error are all wasted.

What was measured, on the deployed site rather than inferred
------------------------------------------------------------
1. Unconditional ``hydrateRoot`` (Reflex's default): #418 on every route.
2. SPA mode (``--no-ssr``): identical, because the entry still hydrates.
3. Marking the document with the prerendered route — first a ``<meta>``, then an
   attribute on ``<html>``: #418 moved to the *prerendered* routes. Anything added
   to the document is part of the tree being compared, so annotating it cannot be
   neutral.
4. ``createRoot`` instead of ``hydrateRoot``: no #418 on any route, one copy of
   each page, handlers live.

Why this is not a regression
----------------------------
Hydration's benefit is reuse of server markup. Since the tree is regenerated on
mismatch anyway, that benefit was never being collected — the markup was already
being thrown away. The prerendered files are still exported and still served, so
first paint and crawlers see real content; they are simply replaced, as they
already were, without the error.

The alternative is a Reflex upgrade, which is the eventual fix (upstream reworked
the ``ssr: false`` + ``prerender`` interaction, remix-run/react-router#12948).
This is a small, reversible local change that does not require a framework jump
the week of an event.
"""

from __future__ import annotations

from reflex.plugins.base import Plugin
from reflex.utils.prerequisites import get_web_dir
from reflex_base.constants import Embed

ENTRY_CLIENT_JS = """\
// Provided by client_render_plugin.ClientRenderPlugin — registered in
// rxconfig.py. Reflex would otherwise write its own entry here, which calls
// hydrateRoot(document, ...) and fails: the exported <head> is not the <head>
// React renders, so hydration mismatches on every route and React regenerates
// the tree anyway (React error #418). Mounting directly does the same work
// without the discarded diff and the console error.
import { createElement, startTransition } from "react";
import { createRoot } from "react-dom/client";
import { HydratedRouter } from "react-router/dom";

startTransition(() => {
  createRoot(document).render(createElement(HydratedRouter));
});
"""


class ClientRenderPlugin(Plugin):
    """Own ``.web/app/entry.client.js`` so the app mounts instead of hydrating."""

    def provides_entry_client(self) -> bool:
        """Tell the framework not to write its own entry for this build."""
        return True

    def pre_compile(self, **context) -> None:
        """Write the entry before the frontend is built.

        Runs on every compile, so an edit here cannot be masked by a stale
        ``.web`` directory left behind by a previous Reflex version.
        """
        target = get_web_dir() / Embed.ENTRY_PATH
        target.parent.mkdir(parents=True, exist_ok=True)
        existing = target.read_text(encoding="utf-8") if target.is_file() else None
        if existing != ENTRY_CLIENT_JS:
            target.write_text(ENTRY_CLIENT_JS, encoding="utf-8")
