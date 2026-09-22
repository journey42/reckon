# Plan: Group Page as Group-Specific Mini-Site

## Overview

Currently, a group page (`/group/[slug]`) renders as a comments view on a single
"master concept" — the founding question is a concept (type=0) and all group
submissions are support/detract/POO comments (types 1/2/3) under it. The page
uses the existing `page()` helper from `reckonings.py` which renders a threaded
comments feed.

The client wants the group page to function as **a group-specific version of the
main site** — a self-contained space where users submit **concepts** (not
comments) as answers to the framing question. Those concepts are displayed below
the framing question, **ordered by positive support** (up_votes + supports).
Concepts and comments otherwise behave exactly as they do on the rest of the
site (upvote/downvote, support/detract/POO comments, compare, etc.). Group
content is **scoped to the group** and invisible elsewhere unless the creator
makes it public.

## PDF Mockup Summary

The PDF shows:
- **"Group Name"** as a heading
- **"Your group has asked: 'Founding question'"** as the framing text
- **"Answer in your own words"** as placeholder text in an input box

## Architecture Changes

### 1. Data Model: Add `group_id` to `Reckoning`

**File:** `rhiz/state/base.py`

Add a nullable `group_id` foreign key to the `Reckoning` model:

```python
group_id: Optional[int] = Field(
    default=None, foreign_key="group.id", nullable=True, index=True
)
```

This is the **core scoping mechanism**:
- Concepts with `group_id=X` belong to group X and are only visible on `/group/[slug]`
- Concepts with `group_id=NULL` are site-wide (the existing behavior)
- Comments under a group concept inherit the group scope implicitly (via parent chain)

### 2. Data Model: Add `is_public` to `Group`

**File:** `rhiz/state/base.py`

Add a boolean to the `Group` model:

```python
is_public: bool = Field(default=False)
```

When `False` (default), group concepts are invisible outside `/group/[slug]`.
When `True`, group concepts appear in site-wide trending/new feeds.

### 3. Migration

**File:** `scripts/db_migrate.py` (direct SQL, same pattern as current)

Add two `ALTER TABLE` statements:
```sql
ALTER TABLE reckoning ADD COLUMN IF NOT EXISTS group_id INTEGER REFERENCES "group"(id);
ALTER TABLE "group" ADD COLUMN IF NOT EXISTS is_public BOOLEAN DEFAULT FALSE;
CREATE INDEX IF NOT EXISTS ix_reckoning_group_id ON reckoning(group_id) WHERE group_id IS NOT NULL;
```

### 4. Group Creation: Set `group_id` on Founding Concept

**File:** `rhiz/utils/groups.py` — `create_group()`

Currently creates a concept with the founding question as content. After
`session.flush()` to get the concept ID, set `concept.group_id = group.id`
so the founding question itself is scoped to the group.

### 5. Group Page: New `GroupPageState`

**File:** `rhiz/pages/group.py`

Complete rewrite of `GroupPageState` to function as a group-specific concept feed.

**State fields:**
- `group_name`, `founding_question`, `group_not_found` (keep existing)
- `submission_content: str` (the answer input box)
- `group_concepts: list[Reckoning]` (concepts belonging to this group)
- Remove: `traction_ideas`, `submission_type` (no longer needed)

**`on_load()`:**
1. Look up the group by slug
2. Set `group_name`, `founding_question`
3. Load group concepts (see `_load_group_concepts()`)

**`_load_group_concepts()`:**
Query all concepts where `group_id = group.id`, ordered by traction (up_votes +
supports) descending. Use `Reckoning.assign_tallies_batch()` for efficient
tally computation (same pattern as trending pages).

SQL approach (mirrors `TrendingConceptsBySupportPageState._window_query`):
```python
ChildReckoning = aliased(Reckoning)
support_count = (
    select(ChildReckoning.parent_reckoning_id, func.count(ChildReckoning.id))
    .where(ChildReckoning.type == ReckoningTypes.support)
    .group_by(ChildReckoning.parent_reckoning_id)
    .subquery()
)
query = (
    select(Reckoning, func.coalesce(support_count.c.count, 0) + Reckoning.up_votes_count)
    .outerjoin(support_count, Reckoning.id == support_count.c.parent_reckoning_id)
    .where(Reckoning.group_id == group.id, Reckoning.type == ReckoningTypes.concept)
    .order_by(traction.desc(), Reckoning.created_at.asc())
)
```

Actually, since `up_votes` are not stored as a column but computed at runtime,
the simpler approach is: query all group concepts, call `assign_tallies_batch()`,
then sort in Python by `(r.up_votes + r.supports, r.created_at)`. This matches
how the existing traction sort works and avoids complex SQL.

**`submit_answer()`:**
1. Require login (redirect to `/signup?next=/group/[slug]` if not logged in)
2. Validate non-empty content
3. Create a new `Reckoning` with:
   - `content = submission_content`
   - `type = ReckoningTypes.concept` (not support/detract/POO!)
   - `group_id = group.id`
   - `parent_reckoning_id = None` (standalone concept, not a child of the founding question)
   - `user_id = self.user.id`
4. Generate embedding via `insert_text_with_embedding()`
5. Clear the input box
6. Reload group concepts (so the new concept appears in the sorted list)
7. Capture PostHog event

### 6. Group Page: New Layout

**File:** `rhiz/pages/group.py` — `group_page()`

The page layout changes from the current `page(GroupPageState, navbar(parent_reckoning(...)))`
to a custom layout:

```
┌─────────────────────────────────────┐
│  navbar()                            │
├─────────────────────────────────────┤
│  Group Name (heading)               │
│  "Your group has asked:"            │
│  Founding question (bold text)      │
├─────────────────────────────────────┤
│  [ Answer in your own words    ]    │  ← input box
│  [ Submit ]                         │  ← submit button
├─────────────────────────────────────┤
│  ┌─ Concept card ─────────────────┐ │
│  │ content    ↑ 12  ↓ 3          │ │  ← existing concept rendering
│  │           support detract poo  │ │     (reuse render_concept)
│  └─────────────────────────────────┘ │
│  ┌─ Concept card ─────────────────┐ │
│  │ ...                            │ │
│  └─────────────────────────────────┘ │
└─────────────────────────────────────┘
```

Each concept card reuses the existing `render_concept()` from `reckonings.py`
so all interaction (upvote, downvote, support/detract/POO comments, compare,
feedback) works identically to the main site.

Clicking "View Comments" on a concept navigates to `/comments/[rid]` which
shows the threaded comments for that concept — exactly as it works site-wide.
The comments page already inherits group scope via the concept's `group_id`.

### 7. Concept Rendering in Group Page

**File:** `rhiz/pages/group.py`

Import and reuse `render_concept` and `reckoning` from `reckonings.py`:

```python
from rhiz.pages.reckonings import reckoning, page, ReckoningsPageState
```

The group page's `foreach` loop renders each concept:
```python
rx.foreach(GroupPageState.group_concepts, lambda r: reckoning(GroupPageState, r))
```

This gives full concept interaction (upvote/downvote/comment buttons) for free.

### 8. Site-Wide Feed Filtering: Exclude Group-Scoped Concepts

**File:** `rhiz/pages/reckonings.py`

In every `_window_query()` for site-wide pages (Trending, New, Your Concepts,
Your Drafts), add a filter to exclude group-scoped concepts unless the group is
public:

```python
# Exclude private group concepts from site-wide feeds
query = query.where(
    _or(
        Reckoning.group_id.is_(None),  # site-wide concepts
        Reckoning.group_id.in_(
            select(Group.id).where(Group.is_public == True)
        ),  # public group concepts
    )
)
```

Affected pages:
- `TrendingConceptsByUpvotesPageState._window_query`
- `TrendingConceptsBySupportPageState._window_query`
- `NewConceptsPageState._window_query`
- `YourConceptsPageState._window_query` (filter by user AND not in private groups)
- `YourDraftsPageState._window_query` (same)
- `ComparePageState._window_query` (similarity search should not surface private group concepts)

### 9. "Make Public" Toggle on Your Groups Page

**File:** `rhiz/pages/your_groups.py` and `rhiz/pages/group_common.py`

Add a "Make Public" / "Make Private" button to `group_row()` that calls
`state.toggle_public(group_id)`. This flips `Group.is_public`.

**File:** `rhiz/pages/your_groups.py` — `YourGroupsState`

Add handler:
```python
def toggle_public(self, group_id: int):
    with rx.session() as session:
        group = session.exec(select(Group).where(Group.id == group_id)).first()
        if group and group.created_by == self.user.id:
            group.is_public = not group.is_public
            session.commit()
    self._refresh()
```

Same pattern in `rhiz/pages/groups_admin.py` — `GroupsAdminState`.

### 10. "How This Works" Dialog Update

**File:** `rhiz/components/how_it_works_dialog.py`

Update the explanation text to reflect the new model:
- Submit **concepts** (answers) to the framing question
- Concepts are ranked by positive support (upvotes + support comments)
- You can upvote/downvote concepts and comment on them just like the main site
- Group content is private to the group unless the creator makes it public

### 11. Delete Group: Cascade Clean-Up

**File:** `rhiz/utils/groups.py` — `delete_group()`

When deleting a group, also delete all concepts and their children that belong
to the group:
```python
# Delete all group-scoped reckonings (concepts + their comment trees)
session.exec(
    delete(Reckoning).where(Reckoning.group_id == group_id)
)
session.delete(group)
session.commit()
```

## File Change Summary

| File | Change |
|------|--------|
| `rhiz/state/base.py` | Add `group_id` to Reckoning, `is_public` to Group |
| `rhiz/utils/groups.py` | Set `group_id` on founding concept in `create_group()`, cascade delete in `delete_group()` |
| `rhiz/pages/group.py` | Full rewrite of `GroupPageState` and `group_page()` — concept feed layout with framing question + input box |
| `rhiz/pages/reckonings.py` | Add group-scope filtering to all `_window_query()` methods |
| `rhiz/pages/your_groups.py` | Add `toggle_public()` handler, pass `is_public` to group_row |
| `rhiz/pages/groups_admin.py` | Add `toggle_public()` handler, pass `is_public` to group_row |
| `rhiz/pages/group_common.py` | Add "Make Public/Private" button to `group_row()` |
| `rhiz/components/how_it_works_dialog.py` | Update explanation text |
| `scripts/db_migrate.py` | Add ALTER TABLE for `group_id` and `is_public` columns |

## Key Design Decisions

1. **Concepts, not comments** — Group answers are `type=concept` (0), not `type=support` (1). This means they get full concept treatment: upvote/downvote, compare, comments, trending.

2. **No parent_reckoning_id** — Group concepts are standalone (parent_reckoning_id=NULL), just like site-wide concepts. They don't nest under the founding question. The founding question is display-only text at the top of the page.

3. **`group_id` scoping** — A single nullable FK on Reckoning is the simplest and most robust scoping mechanism. It doesn't require changes to how comments work (they inherit scope via parent chain lookups). Site-wide feeds filter `group_id IS NULL OR group.is_public`.

4. **Traction ordering in Python** — Rather than complex SQL with subqueries for up_votes (which aren't stored as a column), we query all group concepts, compute tallies with `assign_tallies_batch()`, and sort in Python. Group concept counts will be modest (tens to low hundreds), so this is efficient enough.

5. **Reuse `reckoning()` renderer** — The existing `reckoning()` function in reckonings.py dispatches to `render_concept()` for type=0 reckonings. By using this in the group page's foreach loop, all concept interactions (vote, comment, compare, feedback) work identically to the main site for free.

6. **Comments on group concepts** — When a user clicks "View Comments" on a group concept, they go to `/comments/[rid]` which uses `CommentsPageState`. This already works — the comments page loads the concept and its children. The concept's `group_id` doesn't need to be checked there because the user arrived via a group link. Site-wide feeds won't surface the concept (filtered out), so the only way to reach it is through the group page.
