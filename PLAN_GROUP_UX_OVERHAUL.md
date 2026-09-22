# Plan: Group UX Overhaul — Client Requests

## Summary of Requests

From the exchange between Vince and Journey, there are several distinct requests:

### 1. Group signups should auto-enable (no manual approval)
**Current:** Group-origin signups get a verification email. After verifying, `verify_and_enable()` sets `enabled=True`. But normal signups (non-group) require manual admin approval (`enabled=False` by default). Journey wants to toggle auto-approval on/off.

**Change:** Add an `AUTO_SIGNUP_ENABLED` env var. When `True`, all new signups are auto-enabled (no manual approval needed). When `False` (default), current behavior is preserved. Group-origin signups already auto-enable via email verification.

**Files:**
- `rhiz/state/auth.py` — `signup()`: if `AUTO_SIGNUP_ENABLED` or `group_origin`, set `enabled=True`
- Add env var documentation

### 2. All users get groups access by default (not just admins)
**Current:** `can_manage_groups()` checks role >= admin OR `can_create_groups` flag. The navbar only shows the groups button if `user_can_manage_groups` is true. Journey wants all users to see/access groups.

**Change:** Set `GROUP_CREATE_MIN_ROLE=0` (regular user) by default. This makes `can_manage_groups()` return `True` for all enabled users.

**Files:**
- `rhiz/utils/permissions.py` — change default `GROUP_CREATE_MIN_ROLE` from `UserTypes.admin` to `UserTypes.regular`

### 3. Users who signed up via a group should land on that group after login
**Current:** After login, `_post_login_target()` returns `?next=/group/slug` if present in the URL query params. But if a user logs in later (not from the group link), there's no `next` param, so they go to `/`.

**Change:** Store the group slug on the User model (`signup_group_slug`). When a user signs up from a group page, save the group slug. On login, if no `next` param but the user has a `signup_group_slug`, redirect there.

**Files:**
- `rhiz/state/base.py` — add `signup_group_slug: Optional[str]` to User model
- `rhiz/state/auth.py` — `signup()`: save group slug from `next` param; `login()`: fall back to `signup_group_slug` in `_post_login_target()`
- `scripts/db_migrate.py` — add column

### 4. Your Groups page should show groups the user has affinity with (not just created)
**Current:** `YourGroupsState._refresh()` only shows groups where `created_by == user.id`. Journey wants any group member to access the share link/QR for groups they've signed up with.

**Change:** Show groups the user created PLUS groups they signed up from (`signup_group_slug`). For groups they didn't create, show share link + QR but hide Close/Delete/Make Public (those are creator-only).

**Files:**
- `rhiz/pages/your_groups.py` — query both created groups and `signup_group_slug`; render with read-only row for non-owned groups
- `rhiz/pages/group_common.py` — `group_row()` needs a "read-only" mode (hide Close/Delete/Make Public)

### 5. Semantic clustering decision fork on group page
**Current:** When a user submits an answer on the group page, it's created as a standalone concept and the feed reloads. There's no similarity check or decision fork.

**Change:** After submitting, run `find_similar_texts_with_join()` scoped to the group. If similar concepts exist (above threshold), show a decision fork:
- "Your idea is similar to existing concepts. You can upvote your own submission or switch your support to an existing one."
- Display the similar concepts with upvote buttons
- If no similar concepts, auto-upvote the user's own concept (frictionless publishing)

**Files:**
- `rhiz/pages/group.py` — `submit_group_answer()`: after creating concept, check for similar concepts; show decision fork or auto-upvote
- Reuse the support nudge banner infrastructure from `reckonings.py` (`AppState.show_support_nudge`, `set_support_nudge()`)

### 6. Auto-upvote first concept on a topic
**Current:** New concepts have 0 support. Journey wants the originator's concept auto-upvoted so it doesn't appear with zero support.

**Change:** In `submit_group_answer()`, after creating the concept, if no similar concepts exist, automatically create an up_vote reckoning from the submitting user on their own concept.

**Files:**
- `rhiz/pages/group.py` — `submit_group_answer()`: auto-upvote when no similar concepts

### 7. Graduate individual answers to the main site (manual publish gate)
**Current:** Group content is private by default. Making a group public (`is_public=True`) publishes ALL concepts. Journey wants to publish individual concepts.

**Change:** Add a "Graduate to Site" button on group concepts. This sets `group_id=NULL` on the concept, making it appear in site-wide feeds. If a site-wide concept with high semantic similarity already exists, show a merge prompt (long-term — not needed now).

**Files:**
- `rhiz/state/base.py` — no model change needed (setting `group_id=None` is sufficient)
- `rhiz/pages/group.py` — add `graduate_concept(rid)` handler that sets `group_id=None`
- `rhiz/pages/group_common.py` or `rhiz/pages/group.py` — add "Graduate" button to concept rendering within group context

### 8. QR code for all concepts (not just groups)
**Current:** QR codes are only on group management pages. Journey wants QR for any concept.

**Change:** Add a QR code button/dialog on the concept page (`/concept/[rid]` or `/comments/[rid]`). This is lower priority and can be done separately.

**Files:**
- `rhiz/pages/reckonings.py` — add QR button to concept rendering
- `rhiz/components/` — reuse `qr_data_uri()` helper

## Implementation Order

1. **Auto-enable group signups** (#1) — env var toggle
2. **All users get groups access** (#2) — change default role threshold
3. **Store signup group slug + redirect on login** (#3) — model + auth changes
4. **Your Groups shows affinity groups** (#4) — your_groups.py + group_common.py
5. **Auto-upvote + decision fork on submit** (#5, #6) — group.py submit flow
6. **Graduate individual concepts** (#7) — group.py + concept rendering
7. **QR for all concepts** (#8) — separate, lower priority

## Database Migration

- Add `signup_group_slug VARCHAR` to `user` table (nullable, for storing the group a user signed up from)
- No other schema changes needed (group_id is already nullable, setting it to NULL "graduates" a concept)
