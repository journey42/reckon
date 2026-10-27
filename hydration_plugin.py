"""Hydrate only when the served HTML was actually rendered for this route.

Why this exists
---------------
Reflex builds the frontend with React Router in ``ssr: false`` +
``prerender: true`` mode. That prerenders every *static* route to a real HTML
file and leaves *parameterised* routes — ``/group/[slug]``, ``/room/[slug]``,
``/concept/[rid]`` and five others — to the host's root-only SPA fallback.

Reflex's stock entry is unconditional::

    hydrateRoot(document, createElement(HydratedRouter));

so for those URLs the browser is handed markup that cannot contain the page it is
about to render. React calls that a hydration failure
(`Minified React error #418 <https://react.dev/errors/418>`_), discards the tree
and re-renders from scratch — on the app's most-visited pages, during the event,
on phones.

What was measured, on the deployed site rather than inferred
------------------------------------------------------------
* Exporting in SPA mode (``--no-ssr``) is *worse*: every route serves the shell,
  so every route mismatches instead of only the parameterised ones.
* Emptying the shell's body changes nothing — the mismatch is not about the
  container's contents once ``hydrateRoot`` is used.
* Marking the document (a ``<meta>`` with the route, then an attribute on
  ``<html>``) made *prerendered* routes mismatch too. Anything added to the
  document is part of the tree being hydrated, so the marker cannot live there.

So the entry has to recognise the fallback from markup that already exists.
React Router renders its ``HydrateFallback`` hint into the shell and only the
shell (``404.html`` / ``__spa-fallback.html``); prerendered route files never
contain it. That hint is this file's signal: hydrate when it is absent, mount
client-side when it is present — which is exactly what a fallback asks for.

Upstream is the eventual fix: React Router reworked the ``ssr: false`` +
``prerender`` interaction (remix-run/react-router#12948). This is a small,
reversible local fix that does not require a framework jump the week of an event.
"""

from __future__ import annotations

from reflex.plugins.base import Plugin
from reflex.utils.prerequisites import get_web_dir
from reflex_base.constants import Embed

#: React Router's HydrateFallback hint, as rendered into the SPA shell. Present
#: only in files the export never rendered for a specific route.
HYDRATE_FALLBACK_HINT = "Hey developer"

ENTRY_CLIENT_JS = """\
// Provided by hydration_plugin.ConditionalHydrationPlugin — registered in
// rxconfig.py. Reflex would otherwise write its own unconditional entry here.
//
// Hydrate only when this document was rendered for *this* route. Reflex
// prerenders the static routes and leaves parameterised ones to the host's SPA
// fallback; hydrating that fallback is React error #418 on every visit, which
// costs a discarded tree and a full re-render.
//
// The signal is markup the export already writes, not a marker of our own:
// every attempt to annotate the HTML (a <meta>, then an attribute on <html>)
// changed the tree React hydrates and made the *prerendered* routes mismatch.
// React Router renders its HydrateFallback hint into the shell, and only the
// shell, so its presence means "this is the fallback, not this route's HTML".
import { createElement, startTransition } from "react";
import { createRoot, hydrateRoot } from "react-dom/client";
import { HydratedRouter } from "react-router/dom";

const FALLBACK_HINT = "%(hint)s";

function servedFallback() {
  return document.documentElement.innerHTML.indexOf(FALLBACK_HINT) !== -1;
}

startTransition(() => {
  if (servedFallback()) {
    createRoot(document).render(createElement(HydratedRouter));
  } else {
    hydrateRoot(document, createElement(HydratedRouter));
  }
});
""" % {"hint": HYDRATE_FALLBACK_HINT}


class ConditionalHydrationPlugin(Plugin):
    """Own ``.web/app/entry.client.js`` so hydration becomes conditional."""

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
