# Infinite scroll for reckoning list pages

**Date:** 2026-06-22
**Status:** Approved

## Goal

Replace "load the entire result set on page load" with batched server-side
windowing plus viewport-triggered infinite scroll, on the flat list pages.
This bounds the per-load work — only the visible batch gets `compute_tallies`
— and complements the N+1 / index performance fix.

## Scope

In scope (flat, SQL-ordered lists sharing the `page()` helper):

- New Concepts (`NewConceptsPageState`)
- Trending by upvotes (`TrendingConceptsByUpvotesPageState`)
- Trending by support (`TrendingConceptsBySupportPageState`)
- Your Concepts / your reckonings list (`YourConceptsPageState`, route `/your_concepts`)
- Your Drafts (`YourDraftsPageState`)

Out of scope (each defines its own `get_reckonings`): single-concept page
(`ConceptPageState`), Compare top-10 (`ComparePageState`), Comments tree
(`CommentsPageState`).

Note `YourConceptsPageState` additionally calls `cache_parent_details` per row,
so the base needs a per-row post-process hook (default = `compute_tallies`
only).

All in-scope pages order in SQL (Trending via a count subquery; others by
`created_at`), so `OFFSET/LIMIT` windowing preserves ordering.

## Approach (selected)

IntersectionObserver + hidden trigger button. A sentinel element sits below the
list; an injected observer script (same pattern as the existing
`scrollToSavedPosition`/`saveScrollPosition` JS) clicks a hidden button bound to
`load_more` when the sentinel enters the viewport. No new dependencies or
components. Rejected alternatives: a custom JSX `on_intersect` component (more
code, same UX) and `on_scroll` polling (changes scroll model, fights existing
scroll save/restore, chatty).

## Reflex constraint discovered during implementation

A **public** event handler is dispatched to the substate that *defines* it, so an
inherited `get_reckonings`/`load_more` on the base runs with `self` bound to the
base `ReckoningsPageState` substate (wrong `_window_query`, wrong `reckonings`
node). Therefore: shared logic lives in **private** helpers (`_load_first_window`,
`_append_next_window`, `_load_window`, `_window_query`, `_post_process_row`) —
private methods are plain calls that preserve `self` — and each flat-list
subclass defines thin public `get_reckonings`/`load_more` wrappers so the
handlers dispatch to the correct substate. The base also keeps a default
`load_more` so the shared view's `state.load_more` reference resolves on
out-of-scope pages (no-op there, since `has_more` stays False).

## State (`ReckoningsPageState`, shared base)

New vars:
- `page_size: int = 20`
- `loaded_count: int = 0`
- `has_more: bool = True`
- `is_loading: bool = False`

Each subclass replaces its `get_reckonings()` body with `_window_query(session)`
returning the SQLAlchemy `select` (its existing filters + ordering, minus
`.all()`).

Base methods:
- `_load_window(append: bool)` — open session, build `_window_query`, apply
  `.offset(self.loaded_count).limit(self.page_size)`, fetch; normalize
  `(Reckoning, count)` tuples vs bare model rows; run `compute_tallies(uid,
  session=session)` on the batch only; append to or replace `self.reckonings`;
  update `loaded_count += len(batch)`; set `has_more = len(batch) == page_size`.
- `get_reckonings()` — reset (`loaded_count = 0`, `has_more = True`) then
  `_load_window(append=False)`. Preserves existing call sites
  (on_load, set_search, delete, vote reload).
- `load_more()` — guard `if not self.has_more or self.is_loading: return`; set
  `is_loading=True`; `_load_window(append=True)`; `is_loading=False`.

## View (`page()` helper)

After the `rx.grid(rx.foreach(state.reckonings, ...))`:
- Hidden `rx.button(on_click=state.load_more, id="infinite-load-trigger",
  display="none")`.
- The sentinel is the **last grid item** (`rx.cond(state.has_more,
  rx.box(id="infinite-scroll-sentinel", gridColumn "1 / -1"), rx.fragment())`)
  so it sits below all cards despite the grid's `h=100vh`.
- The IntersectionObserver lives in the **external asset `assets/scrolling.js`**
  (already loaded via `head_components`), NOT an inline `rx.script` —
  React-rendered `<script>` tags do not execute. It observes the sentinel
  (rootMargin 300px), clicks the hidden trigger on intersection, inits once via
  a `window` guard, and re-attaches across client navigations via a 500ms
  `ensure()` check.

## Known interaction (accepted)

Voting saves scroll position, redirects to the same path, and restores scroll on
load. With windowing the reload starts at window 1, so a deep saved position
can't be restored until more batches load — page lands near the top after
voting. Accepted for now; revisit later if needed (e.g. scroll-aware
preloading or in-place vote mutation).

## Out of scope / not done

- Pagination of Comments tree, Compare, single-concept pages.
- Scroll-aware preloading after vote.
