# PLAN: Live Q&A rooms — anonymous participation via QR (IIW #43 demo)

Deadline: working demo well before Nov 3 (IIW #43, ~300 attendees, flaky wifi).
Primary success path: facilitator asks a question in a live room → throws QR →
people answer on phones without accounts → room auto-closes → permanent
static artifact with final results and consolidation story.

## Summary

A live room is a **mode of an existing private Group**, not a parallel feature:

- The room is a Group with `is_room=TRUE` and `is_public=FALSE`. The existing
  site-wide feed exclusion (`_exclude_private_groups()`) keeps room content
  off every public surface — the "own universe" requirement is inherited, not
  built.
- Answers are Reckoning rows (`type=concept`, `group_id=room`,
  `user_id=NULL`). `Reckoning.user_id` is already nullable.
- The founding question is the question; `created_by` is the facilitator;
  `GroupStatus` open/closed is the lifecycle; QR share links already exist.
- Similarity matching reuses `find_similar_texts_with_join(threshold,
  group_id)` — the per-room threshold is that existing parameter.
- The closed room page **is** the permanent artifact, with a print
  stylesheet. No separate artifact page.
- The one new primitive is **anonymous participation**: a device cookie plus
  per-room hashed identity, deliberately room-agnostic so later anonymous
  features reuse it.
- **No live results for anyone** (client decision): before close, nobody —
  participants or facilitator — sees the answers, rankings, or vote totals.
  The only pre-close view of another answer is the private similar-answer
  nudge shown to a single device at submit time.

## Confirmed requirements

| # | Requirement | Decision |
|---|---|---|
| 1 | Anonymous answers, no signup | Fully anonymous |
| 2 | Visibility | Invisible to public; admin access; private-group isolation |
| 3 | One answer per device per question | Enforced; editable until close; "edited" marker |
| 4 | Re-scan QR after answering | Device returns to their answer (edit view) |
| 5 | **No live results page** | Before close nobody sees answers or totals, including the facilitator |
| 6 | **Swap tracking** | Record who switched from their own wording to another answer; report swaps in the artifact; no logins required |
| 7 | **Auto-close** | Default 1 hour, facilitator-set duration, extendable while open; manual close anytime |
| 8 | **Final results on open tabs** | Waiting page auto-refreshes; on close it becomes the artifact |
| 9 | Who can ask | Any account holder |
| 10 | Artifact | Final ranking by support + facilitator's closing note; frozen page with print stylesheet; permanent link |
| 11 | Network | Flaky wifi: auto-refresh waiting page; device cookie survives reconnects |
| 12 | Submit flow | Answer saved immediately; private similar screen with copy "Someone in the room said something similar. Would you like to support that instead?"; *Support that instead* = swap (their support moves, their wording withdraws) |
| 13 | Post-close moderation | Facilitator cannot moderate pre-close (no visibility); admin can tombstone inappropriate answers after close |
| 14 | Parallel rooms | Room boundary = the question; a facilitator may run several |

## Existing-model preservation guarantee

The room is a mode, not a fork. Invariant:

> `is_room = FALSE` ⇒ behaviour identical to today, everywhere.

Blast radius — all additive:

| Surface | Change | Effect on existing behaviour |
|---|---|---|
| `Group` | +5 nullable columns (`is_room` default FALSE, `closing_note`, `similarity_threshold`, `close_at`, `closed_at`) | None |
| `Reckoning` | +2 nullable columns (`edited_at`, `removed_at`) | None |
| `roomparticipant` / `roomswap` | New tables | Unused by existing features |
| Shared code paths | Navbar legend removal, "Live Q&A" nav item | Client-requested UI change |
| Routes/pages | New `/live`, `/room/[slug]`, `/live/all` | Existing routes untouched |

No destructive migration steps; additive DDL via both alembic and
`scripts/db_migrate.py`, against a fresh backup.

Regression invariant test (P5 gate): with existing groups + reckonings seeded,
add rooms, then assert existing surfaces render identical output.

## Schema

```
group   + is_room BOOLEAN DEFAULT FALSE
        + closing_note TEXT NULL              # facilitator note at manual close
        + similarity_threshold FLOAT NULL     # NULL = 0.55 default
        + close_at TIMESTAMP NULL             # deadline; auto-close at/after
        + closed_at TIMESTAMP NULL            # set when closed (manual or auto)

reckoning
        + edited_at TIMESTAMP NULL            # non-null => "edited" marker
        + removed_at TIMESTAMP NULL           # post-close admin tombstone

roomparticipant                               # one per device per room
  id PK
  room_id FK group.id
  device_hash VARCHAR UNIQUE                  # sha256(device cookie + room slug)
  current_answer_id FK reckoning.id NULL      # their live answer
  supported_answer_id FK reckoning.id NULL    # set when they swap
  created_at / last_seen_at

roomswap                                      # the consolidation story
  id PK
  room_id FK group.id
  participant_id FK roomparticipant.id
  from_reckoning_id FK reckoning.id           # their original wording
  to_reckoning_id FK reckoning.id             # the answer they switched to
  created_at
```

Room slug: unguessable (`secrets.token_urlsafe`). Device cookie `rhiz_device`:
256-bit random token, 1-year max-age; only per-room hashes are stored.
Audit trail: existing `Log` table.

## Timing & auto-close semantics

- Duration is chosen at creation (15/30/60/90/120 min; default 60) and stored
  as `close_at = created_at + duration`.
- **Lazily enforced server-side**: every room read/write first calls
  `enforce_deadline()` — if `status=open` and `close_at <= now`, the room
  closes (`status=closed`, `closed_at=now`). No background scheduler; late
  submissions/edits are rejected even if no page is open.
- **Extend**: facilitator adds +15 min per click while open.
- **Manual close**: anytime, with optional closing note.
- Auto-close sets no closing note.

## Swap & support semantics

- Submitting = implicit self-support (no vote rows; support is derived).
- Final support for an answer = (1 if its author has not swapped away else 0)
  + number of swaps into it.
- **Swap** (from the similar screen): participant's original answer loses the
  author's implicit +1; if nobody swapped into it, it is deleted (row +
  embedding); if others had swapped into it, it remains (support = inbound
  swaps). A `roomswap` row records from → to + participant + time.
- After a swap the device supports the target and cannot submit a new answer
  (v1: one authorship or one swap per device per room).
- **Edit**: own answer, while open; content re-embedded; `edited_at` set.
- **Admin removal** (post-close): `removed_at` set; content masked
  everywhere; tombstone renders at its ranked position.

## Pages & flows

### `/live` — facilitator dashboard (login required)
- My rooms: open (question, countdown, answers count, participants count,
  QR + link, extend, close-with-note) and closed (artifact link)
- New room: question, duration, similarity threshold (Loose/Balanced/Tight)
- Per-room threshold stays adjustable while open (affects new submissions)

### `/room/[slug]` — the room (public; device-cookie identity; own `RoomState`)
Minimal header, no site navigation, mobile-first. State machine by
(device, has answer, status):

1. **Open, hasn't answered**: question + answer box only. Submit → saved
   immediately.
2. **Just submitted + similar found**: private comparison screen with the
   specified copy; *Keep my answer* → waiting; *Support that instead* → swap.
3. **Open, has answered**: their answer + edit affordance + waiting note.
   No list of other answers is ever shown.
4. **After swap**: waiting screen ("You're supporting another participant's
   answer").
5. **Closed** (or deadline passed): the final artifact.
6. Waiting screens auto-refresh every ~20s; at close they render the artifact.

### Facilitator controls (on the room page for the owner + on `/live`)
- Countdown, extend (+15 min), close-with-note, threshold select.
- No interim answers or results are shown to the facilitator.

### Artifact = the closed room page
- Final ranking (support desc, ties by created_at asc), "N switched to this"
  per answer, tombstones inline, closing note, swap total.
- Zero interactivity for participants; print stylesheet; same URL, permanent.

### Admin
- `/live/all` (admin role): every room, status, counts, links.
- Admin can tombstone answers from a closed room's artifact.

## Live-page removal wins

- No ranked feed polling. The only background activity is the waiting
  screen's ~20s auto-refresh (one lightweight page load), roughly an order of
  magnitude lighter than the previously planned 2.5s ranked polling —
  important on conference wifi with ~300 phones.
- No facilitator live view to build; the facilitator watches the room, not a
  screen.

## Guardrails

- Room slug unguessable; room pages render a minimal header (no site nav)
- Rate limits: 1 authorship/device/room; edits ≥10s apart; one swap/device;
  answer length capped at the main-site limit
- Content pipeline identical to main-site submissions (validation → embed)
- Removed answers never render, including print
- Room creation is `logged_in` only (deliberately not `GROUP_CREATE_MIN_ROLE`)
- Anonymous room pages emit no PostHog identify events

## Isolation audit (hard gate before deploy)

- every site-wide surface applies `_exclude_private_groups()` (verified in
  `reckonings.py`; re-verify after room answers exist)
- room answers have `user_id NULL` → safe from `your_concepts`/`your_drafts`
- room similarity is scoped via the `group_id` param; main-site similarity
  filters `group_id IS NULL`
- `/live/all` is the deliberate admin exception

## Explicitly deferred

- Publish-to-site (graduation machinery exists when prioritised)
- Un-vote, comments, downvotes
- Live moderation pre-close (structurally impossible without a live page)

## Test checklist

1. Fresh phone → QR → question + answer box only → submit → saved instantly
2. Similar screen at threshold; copy exactly as specified
3. Keep mine → waiting screen; support-instead → swap recorded, wording
   withdrawn (deleted when nothing swapped into it)
4. Edit before close; "edited" marker; re-scan returns to their answer
5. One answer per device; edit ≥10s apart; one swap per device
6. Auto-close at deadline: late edit/submit rejected even with no reader;
   waiting tab becomes the artifact on next refresh
7. Extend adds 15 min; manual close with note freezes everything
8. Facilitator sees countdown/controls but never answers before close
9. Artifact: ranked, swap counts, closing note, print stylesheet, permanent
10. Admin: /live/all lists all rooms; post-close removal → tombstone
11. Isolation audit: no room content on any site-wide surface
12. Regression invariant: existing groups render identically with rooms present
13. Load: 300 waiting tabs refreshing every 20s within budget
14. Wifi drop mid-flow → recovery, no data loss
