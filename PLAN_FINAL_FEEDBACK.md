# Plan: Client Feedback — Final Issues and Requests

## 1. Azure bill reduction ($93/month)

**Current resources in `reckon-rg`:**
- Container App `rhiz-backend`: 0.5 CPU, 1Gi RAM, min 1 replica, max 3
- Static Web App `rhiz-web`: Free tier
- ACR `rhizregistry`: Basic tier (~$19/mo)
- **3 Log Analytics workspaces** (PerGB2018, 30-day retention) — likely the biggest cost
- Dev VM `reckon` (Ubuntu VM with disk) — if running, ~$20-40/mo
- Container Environment `reckon-acs`

**Cost-saving actions:**
- **Delete 2 of the 3 Log Analytics workspaces** — Container Apps only needs one. Each workspace at PerGB2018 with 30-day retention costs ~$10-15/mo. Saving ~$20-30/mo.
- **Stop or deallocate the dev VM `reckon`** — if it's not actively used, deallocate it. Saving ~$20-40/mo.
- **Set min replicas to 0** on the Container App — scale to zero when idle. The app takes ~5-10s to cold-start but saves compute costs during low traffic. Saving ~$15-25/mo.
- **Consider downgrading ACR to free tier** — if image storage is under 10GB. The Basic tier is ~$19/mo; Free tier has 10GB included.

**Action:** Investigate and implement cost-saving measures. Client to approve which resources to trim.

## 2. PostHog

PostHog is already wired:
- **Client-side:** `posthog.js` loaded in `<head>` with project API key — tracks page views automatically
- **Server-side:** PostHog Python client initialized, `capture()` calls for `signup`, `vote_cast`, `group_created`, `group_answer_submitted`
- The `.env` has a placeholder `POSTHOG_SECRET_KEY` but the init logic uses `POSTHOG_PROJECT_API_KEY` which IS set, so server-side events fire

**Action:** Verify in PostHog dashboard that events are appearing. If server-side events aren't firing, check the PostHog Python library version compatibility. No code change needed unless events aren't showing up.

## 3. Group redirect after signup via QR code

**Current behavior:** When someone signs up via a group link (`/signup?next=/group/slug`):
- `signup_group_slug` is saved on the User model
- For group-origin signups: verification email is sent, user goes to `/verify_email_sent`
- After verification: `verify_and_enable()` enables the account, redirects to `/login?next=/group/slug`
- After login: `_post_login_target()` returns the `?next` param or falls back to `signup_group_slug`

**Issue:** The client says users aren't being taken to the group after signup. The flow has too many steps (signup → email verify → login → group). If `AUTO_SIGNUP_ENABLED` is on, group-origin signups should skip the email verification and go straight to the group.

**Fix:** When `auto_signup_enabled` is true AND the signup is group-origin, auto-enable the account, log them in, and redirect directly to the group page. Skip the email verification step entirely when auto-signup is on.

**Files:** `rhiz/state/auth.py` — `signup()` method

## 4. TiptapEditor juddering text (substituting letters)

**Current fix (in `tiptap_editor.jsx`):**
```javascript
const internalChange = React.useRef(false)
// onUpdate sets internalChange = true, onChange fires
// useEffect checks internalChange — if true, skips sync; resets to false
```

**Remaining issue:** The fix prevents the feedback loop when `value` is updated by the same keystroke, but there may be a timing issue where:
1. The `onChange` → state update → re-render happens synchronously
2. The `useEffect` fires before `internalChange.current` is set to `true` (race condition)
3. Or Reflex debounces/batches the state update, causing a delayed sync

**Fix:** Instead of a ref that's reset at the end of the effect, use a more robust approach — compare the actual editor content with the incoming `value` and only sync if they differ by more than trivial HTML normalization. The simplest robust fix: skip the sync entirely if the editor has focus (user is actively typing).

**Files:** `rhiz/components/tiptap_editor.jsx`

## 5. Graduate function on concepts, not groups

**Current behavior:** The "Graduate" button on the Your Groups page toggles `Group.is_public` (graduates ALL concepts in the group). The graduation-cap icon on individual concepts sets `group_id=NULL` (graduates a single concept).

**Client wants:** Move the graduate function to individual concepts only. Remove the group-level "Graduate" button from Your Groups page.

**Fix:**
- Remove the "Graduate/Ungraduate" button from `group_common.py` (the `toggle_public` button)
- Keep the graduation-cap icon on individual concepts (already implemented in `reckonings.py`)
- The group's `is_public` field can remain for potential future use but won't be exposed in the UI

**Files:**
- `rhiz/pages/group_common.py` — remove Graduate/Ungraduate button
- `rhiz/pages/your_groups.py` — remove `toggle_public` handler (or keep but don't expose)
- `rhiz/pages/groups_admin.py` — same

## 6. Cannot delete test groups ("error, contact administrator")

**Current `delete_group()` in `rhiz/utils/groups.py`:**
```python
session.exec(sa_delete(Reckoning).where(Reckoning.group_id == group_id))
session.delete(group)
session.commit()
```

**Likely cause:** The `sa_delete(Reckoning).where(Reckoning.group_id == group_id)` only deletes reckonings that have `group_id` set directly. But comments and votes on those concepts may have `group_id` propagated (from our recent fix), OR they may have `group_id=NULL` if they were created before the propagation fix. The comments/votes reference the concept via `parent_reckoning_id`, and the concept references the group via `group_id`. If we delete the concept first (via `group_id` filter), the child comments/votes still reference it via FK → `ForeignKeyViolation`.

**Fix:** Use a recursive CTE or two-pass deletion: first delete all child reckonings (comments, votes) that are descendants of group concepts, then delete the group concepts themselves, then delete the group.

**Files:** `rhiz/utils/groups.py` — `delete_group()`

## 7. Blank page / download text on login

**Cause:** This is likely the Reflex SPA not hydrating properly. When the frontend dev server is slow to start or the WebSocket connection fails, the browser shows the raw HTML shell (which can look like a text download). On production (Static Web Apps), this could be:
- A stale JS bundle being served (CDN cache)
- The `__spa-fallback.html` being served as raw text
- A slow cold-start of the Container App backend (WebSocket can't connect)

**Fix:** Investigate the Static Web App caching. Add proper cache-control headers. Verify the SPA fallback is serving HTML content-type. Check if min replicas = 0 causes cold-start delays where the backend is unreachable.

**Files:** `deploy/staticwebapp_config.json` — add cache headers; `deploy-backend.yml` — consider min replicas = 1

## Implementation Order

1. **Delete group crash** (#6) — critical bug, blocks client testing
2. **TiptapEditor juddering** (#4) — UX-breaking bug
3. **Group redirect after signup** (#3) — onboarding flow
4. **Move graduate to concepts** (#5) — remove group-level graduate
5. **Azure cost trimming** (#1) — infrastructure
6. **PostHog verification** (#2) — analytics
7. **Blank page on login** (#7) — investigate and fix
