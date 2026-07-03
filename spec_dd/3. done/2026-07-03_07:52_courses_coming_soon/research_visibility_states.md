# Research: Course Visibility / Lifecycle State Modeling

## 1. Data Modeling Options

### Option A: Single Status Enum (Recommended)

A single `CharField` with `TextChoices`, following the project's existing pattern (`DifficultyLevel`):

```python
class CourseStatus(models.TextChoices):
    DRAFT    = "draft",       _("Draft")
    HIDDEN   = "hidden",      _("Hidden")
    COMING_SOON = "coming_soon", _("Coming Soon")
    PUBLISHED = "published",  _("Published")
```

Added to `Course`:
```python
status = models.CharField(
    max_length=20,
    choices=CourseStatus.choices,
    default=CourseStatus.PUBLISHED,
)
```

Pros:
- Mutually exclusive states are enforced at the DB level — no combination of flags can create an invalid state (e.g., a course can't be both `hidden` and `coming_soon` simultaneously)
- Single indexed column; filtering is a simple `filter(status=CourseStatus.PUBLISHED)`
- Extending to new states is a one-line addition to the TextChoices class
- Consistent with how `DifficultyLevel` is already modeled in this codebase
- `get_all_courses()` becomes `Course.objects.filter(status=CourseStatus.PUBLISHED)` for students — a trivial change
- Educator query remains `Course.objects.all()` — educators always see everything
- Migration is safe: set `default=CourseStatus.PUBLISHED` and all existing rows get `published` automatically

Cons:
- If two attributes are genuinely orthogonal in the future (e.g., "is this a paid tier course" AND "is this visible?"), a single enum can grow combinatorially if you try to express all combinations. For the current two-feature scope this is not a problem.

### Option B: Orthogonal Boolean Flags

```python
is_published = models.BooleanField(default=True)
is_hidden    = models.BooleanField(default=False)
is_coming_soon = models.BooleanField(default=False)
```

Pros:
- Easy to read in isolation
- Natural if states are genuinely independent

Cons:
- Invalid combinations are possible: `is_published=True, is_hidden=True, is_coming_soon=True` — what does that mean? You need `clean()` validators to guard against this.
- Student-facing filter requires a compound `Q()` expression, e.g. `filter(is_published=True, is_hidden=False, is_coming_soon=False)`, which is error-prone and must be kept in sync across every query site.
- Three DB columns instead of one.
- Adding a new state (e.g., "archived") requires a fourth column and more compound logic.

### Option C: Visibility Enum + Separate Published Flag

```python
class Visibility(models.TextChoices):
    LISTED   = "listed",   _("Listed")
    HIDDEN   = "hidden",   _("Hidden")
    UNLISTED = "unlisted", _("Unlisted")

is_published = models.BooleanField(default=True)
visibility   = models.CharField(...)
```

Pros:
- Separates "is this ready?" from "who can find it?" — mirrors how some platforms think
- Could be useful if a course needs to be in draft/published state independently of its discoverability

Cons:
- Overkill for the current feature scope. The FLS currently has no concept of drafts (all courses come from a content directory); there's no editor authoring workflow that needs a draft state distinct from published
- Two fields to reason about and keep consistent; more complex student-facing queries
- For the idea doc's scope (two new states: coming_soon and hidden), a single enum handles it cleanly

### Recommendation

**Use Option A (single enum)** with four values: `draft`, `hidden`, `coming_soon`, `published`. The single-column design eliminates invalid states, keeps filtering simple, aligns with the codebase's conventions, and is trivially extensible.

If a genuine "work in progress, not ready to show educators either" state is never needed (the current idea doc doesn't mention it), `draft` can be omitted and the enum starts with just `hidden | coming_soon | published`. Adding `draft` later is a one-line TextChoices addition.

---

## 2. Reference Implementations

### YouTube (Public / Unlisted / Private)

YouTube's three-state model is the canonical example of separating "findable" from "accessible":

- **Public**: Appears in search, channel pages, recommendations. Anyone can view.
- **Unlisted**: Only accessible via direct URL. Does not appear in search or the channel listing. Anyone with the link can watch — no account needed.
- **Private**: Only the creator and explicitly invited users can access. Does not appear anywhere for others.

The key insight: "unlisted" is not "private". A student already on a course landing page with a direct link can still see an unlisted video; a private one returns nothing.

Sources: [YouTube Help – Change video privacy settings](https://support.google.com/youtube/answer/157177), [VPNMentor – YouTube Private vs Unlisted](https://www.vpnmentor.com/blog/youtube-private-vs-unlisted/)

### Thinkific (Draft / Pre-order-Coming-Soon / Published / Private / Hidden)

Thinkific separates publication state from discoverability:

- **Draft**: Not purchasable, not enrollable, not shown in site listings.
- **Pre-order (Coming Soon)**: Users can purchase/enroll immediately but cannot access content. Card shows "Coming Soon" label on the student dashboard.
- **Published**: Fully accessible — purchase, enroll, access content.
- **Private**: Landing page is public (for marketing) but checkout/enrollment is blocked. Enrolment is by admin invite only.
- **Hidden**: Not indexed by Google; won't appear in search engines. Still accessible via direct URL.

The critical distinction Thinkific makes: "Private" controls **enrollment access**, "Hidden" controls **discoverability**. These are orthogonal on Thinkific (you can have a published-but-hidden course, for instance). In FLS, however, the idea doc's "hidden" merges both — hidden means "not discoverable by students at all" — so a single enum value is sufficient.

Source: [Thinkific – Private and Hidden Products](https://support.thinkific.com/hc/en-us/articles/360030738053-Private-and-Hidden-Products), [Thinkific – Publishing Your Products](https://support.thinkific.com/hc/en-us/articles/360030738133-Publishing-Your-Products)

### LearnWorlds (Draft / Coming Soon / Private / Enrollment Closed / Paid / Free)

LearnWorlds offers six "course types" that blend status and pricing:

- **Draft**: Invisible, under development.
- **Coming Soon**: Card displays "coming soon" message; students can see the overview and course outline but cannot access content.
- **Private**: Only accessible to enrolled users (admin assigns enrollment).
- **Enrollment Closed**: Visible but new enrollments blocked.
- **Paid** / **Free**: Published states with pricing models.

Notable pattern: Coming Soon is a separate state from Draft — the course IS visible/discoverable but content is not accessible.

Source: [LearnWorlds Help – Different Course Statuses](https://support.learnworlds.com/support/solutions/articles/12000040783-different-course-statuses-in-learnworlds)

### WordPress (post_status)

WordPress uses a single `post_status` string field with eight built-in values:

- `publish` — visible to all
- `draft` — not visible, author is editing
- `future` — scheduled for a future date
- `pending` — awaiting review/approval
- `private` — visible only to admins/editors
- `trash` — soft-deleted

The `future` status is closest to "coming soon" — the content exists and is scheduled to become visible. WordPress's use of a single field for all of these is the original precedent for the single-enum pattern.

Sources: [WordPress Docs – Post Status](https://wordpress.org/documentation/article/post-status/), [PublishPress – What is a Post Status?](https://publishpress.com/blog/publishpress-statuses/what-is-a-post-status-in-wordpress/)

### Django conventions

Django does not have a framework-level "published" convention; the community pattern for status fields is a `CharField` with `TextChoices` and a `default`. The existing FLS `DifficultyLevel` follows this exactly. A `default` on the field means `makemigrations` can apply the migration without interactive prompting for a one-off value, and existing rows are back-filled during the migration.

---

## 3. "Hidden" Semantics

### Unlisted vs. Draft/Private

The spectrum from most to least discoverable:

1. **Listed / Published**: Appears in all course listings. Anyone can find and register.
2. **Coming Soon**: Appears in all course listings. Students can see the card and landing page but cannot register. They can express interest / join a waitlist.
3. **Unlisted (YouTube model)**: Not in listings. Accessible via direct URL. Students who have the URL can see the detail page.
4. **Hidden/Private (FLS proposal)**: Not in listings AND detail page either returns 404 or redirects. No student-facing surface at all.
5. **Draft**: Educator/admin only. Students get 404 on all routes.

The idea doc says: "Hidden courses are in the system but are not discoverable by students." This corresponds to option 4 above — they do not appear in listings AND student-facing detail pages should return 404 (or at minimum not be linked anywhere). This is closer to YouTube's "Private" than "Unlisted", because "unlisted" implies the URL still works.

### What happens to already-registered students when a course becomes hidden?

Two reasonable interpretations:
- **Access preserved**: Registered students can still access the course via direct URL (their dashboard still links to it). The course is hidden from the *browse/discover* surface only. This is the YouTube "Unlisted" behavior and is gentler for learners.
- **Access revoked**: All student-facing URLs return 404. Registration records remain in the DB but the UI surfaces nothing.

The idea doc does not specify. For a first implementation the pragmatic default is: **registered students retain access** (their dashboard course list still shows it; their direct URL still works). The "hidden" filter only applies to the course discovery/browse surface (`get_all_courses()` in student_interface). This avoids surprising students who are mid-course when an educator hides it.

If full access revocation is needed later, it can be added as a separate "archived" or "deactivated" state without changing the data model.

### Direct-URL access to a hidden course's detail page (unregistered students)

For the hidden state: an unregistered student who somehow has the URL to a hidden course's detail page should get a 404. There is nothing to discover. This keeps the semantics clean and avoids partial-access confusion.

For coming_soon: the detail page (if one exists) should be reachable — students need somewhere to land after clicking the card and to submit a waitlist/interest form. So coming_soon detail pages: visible. Hidden detail pages: 404 for non-registered students.

---

## 4. Default / Migration Strategy

When adding the `status` field to existing courses, the default must be `published` so that all currently visible courses remain visible after migration:

```python
status = models.CharField(
    max_length=20,
    choices=CourseStatus.choices,
    default=CourseStatus.PUBLISHED,
)
```

Django's migration generated from `makemigrations` will add the column with `DEFAULT 'published'` at the DB level and back-fill existing rows. No data migration is needed. This is the standard Django approach and is safe.

The course-loading infrastructure (content directory import) should also default new courses to `published` unless explicitly overridden in course metadata, preserving backward compatibility.

---

## 5. Educator / Admin Visibility

Yes — educators and admins should always see all courses regardless of status. This is already the case in the codebase:

- `educator_interface/views.py`: `Course.objects.all()` — no filter.
- `student_interface/utils.py`: `get_all_courses()` returns `Course.objects.all()` — this is the single site-filtered query that student-facing views use.

The change needed is surgical:

- **Student-facing**: `get_all_courses()` (and the student dashboard querysets) filter to `status=CourseStatus.PUBLISHED` (and `status=CourseStatus.COMING_SOON` for the "browse all" view that should also show coming-soon cards). Hidden courses are excluded entirely.
- **Educator-facing**: No change. `Course.objects.all()` stays as is. Educators see all states, with a status badge visible in the course table.
- **Admin (Django admin)**: All courses visible; status is an editable field.

This separation means the only code change for filtering is in `get_all_courses()` and any other student-interface query sites. The educator path is untouched.

---

## Summary Recommendation

| Decision | Recommended choice | Rationale |
|---|---|---|
| Data model | Single `status` CharField with TextChoices | Mutually exclusive states, no invalid combos, aligns with codebase conventions |
| States | `published`, `coming_soon`, `hidden` (+ optionally `draft`) | Matches idea doc; `draft` deferred unless needed |
| Default | `published` | Preserves all existing course visibility |
| Hidden detail page (unregistered) | 404 | Fully non-discoverable |
| Hidden + registered student | Retain access | Avoid disrupting learners mid-course |
| Coming soon detail page | Accessible | Students need somewhere to express interest |
| Educator visibility | All states always visible | No change to educator queries |
| Student filtering | `get_all_courses()` gains a `status__in=[published, coming_soon]` filter | Single choke-point for student visibility |

---

## Sources

- [YouTube Help – Change video privacy settings](https://support.google.com/youtube/answer/157177)
- [VPNMentor – YouTube Private vs Unlisted: Complete Guide](https://www.vpnmentor.com/blog/youtube-private-vs-unlisted/)
- [EntreResource – YouTube Unlisted and Private Visibility](https://entreresource.com/private-vs-unlisted-youtube-visibility/)
- [Thinkific – Private and Hidden Products](https://support.thinkific.com/hc/en-us/articles/360030738053-Private-and-Hidden-Products)
- [Thinkific – Publishing Your Products](https://support.thinkific.com/hc/en-us/articles/360030738133-Publishing-Your-Products)
- [LearnWorlds Help – Different Course Statuses](https://support.learnworlds.com/support/solutions/articles/12000040783-different-course-statuses-in-learnworlds)
- [WordPress Documentation – Post Status](https://wordpress.org/documentation/article/post-status/)
- [PublishPress – What is a Post Status?](https://publishpress.com/blog/publishpress-statuses/what-is-a-post-status-in-wordpress/)
- [Teachable – Publishing Your Course](https://support.teachable.com/hc/en-us/articles/224560588-Publishing-Your-Course)
- [Django Model Field Reference](https://docs.djangoproject.com/en/5.2/ref/models/fields/)

status: ok
