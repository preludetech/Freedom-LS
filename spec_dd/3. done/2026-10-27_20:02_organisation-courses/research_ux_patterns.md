# Research: UX patterns for organisation-scoped courses

Topic: ux_patterns. Question: how to show organisation affiliation on course cards, tell same-named courses apart, and assign courses to organisations in admin.

## Evidence quality

Web search returned little first-hand detail. Findings from outside FLS are partly general knowledge and are marked as such. Treat them as direction, not citation-grade fact.

## 1. External patterns

- Coursera: the provider appears as an "Offered by" line, with the partner name (and on catalog cards a small partner logo above or beside the title). The search found only the course-page "Offered by" wording, not the card spec. Source: https://www.coursera.org/de-DE/projects/market-new-business-canva
- Sponsored or enterprise programs (Coursera for an institution): the interface swaps in the sponsor's logo and learners are told to enrol only in courses labelled "Sponsored by <Org>". This is the closest match to the FLS case, where the label distinguishes otherwise identical offerings. Source: https://nus.atlassian.net/wiki/x/VFQrAg
- Partner thumbnails: universities brand their own thumbnails to Coursera guidelines (image size, format, brand elements). Source: https://exstadmin.umd.edu/support-resources/marketing-and-communications/moocs-resources
- Cards in general (NN/g): the top and left of a card read as most important. Cards need not carry the same fields, and secondary metadata can sit apart from the main content. Whole-card clickability is normal. Source: https://www.nngroup.com/articles/cards-component/
- General knowledge, not verified in this run:
  - edX and Coursera put the partner logo or name as small metadata above the title, not in the hero image.
  - LinkedIn Learning shows author and "Custom content from <Org>" style labels.
  - Corporate LMS catalogues (Moodle, Totara) usually hide what a learner cannot access instead of showing it locked. Admins assign audiences or cohorts through a multi-select or autocomplete widget.

Distilled patterns:

1. Affiliation is a single small line or chip ABOVE the title (eyebrow or meta line), logo plus name, not a hero overlay.
2. Same-named courses are told apart by that affiliation label, so the title stays identical. Do not suffix titles with the organisation name.
3. A course open to everyone shows no affiliation, so the label means "specific to this organisation".
4. Logo is optional. Fall back to the name alone.

## 2. How this fits FLS

### Existing card structure

- The single dashboard card is `/home/sheena/workspace/lms/freedom-ls-worktrees/organisation-courses/freedom_ls/learner_interface/templates/learner_interface/partials/course_card.html`. It renders every state from `course.listing_status`, on top of the shell `/home/sheena/workspace/lms/freedom-ls-worktrees/organisation-courses/freedom_ls/learner_interface/templates/cotton/course-card-shell.html`.
- The shell has a hero (accent colour plus icon, `h-28`). Inside the body it has an `eyebrow` slot (status label or access badge), the default slot (title link, price, next-up, details link) and a `footer` slot (progress bar).
- The markdown widget `cotton/course-card.html` fills the eyebrow with the access badge via the `course_access_badge` filter in `templatetags/course_card_tags.py`. A sibling `course-row-shell.html` and `partials/course_row.html` cover the row layout, so any new element must work in both shells.
- The eyebrow is already contended. A comment in `course_card.html` says the status eyebrow is "the single place status is ever shown". The org label should therefore NOT be another chip in that eyebrow competing with status.

### Recommendation: placement

- Add a dedicated organisation line in the card body directly under the title (or between eyebrow and title). It is a new, small, muted `text-sm text-muted` row: optional small logo plus organisation name.
- Why under the title and not in the eyebrow: status and access chips stay the one signal per slot. Reading order becomes status, title, "who is this for".
- Logo choice: `Organisation.logo` is for light backgrounds, `logo_on_dark` for dark ones. The card body is `.surface` (light), so use `logo`. The hero is an accent colour, so do not put the logo there. The model help text for `logo_on_dark` says a surface without a dark variant should fall back to the organisation's name, which matches pattern 4.
- Best fit: a small shared Cotton component (for example an organisation byline) that takes the organisation and renders logo (fixed small height, `alt` = name, or no `alt`/aria-hidden when the name is also shown as text) plus name. Reuse it in card, row and the in-progress state so the three requirements do not repeat markup (CLAUDE.md: avoid repeating code).
- Do not use `c-panel-status-badge` for this. Brand guidance says it is for the state of a record. An organisation is not a status. If a chip form is wanted, `c-chip variant="secondary|muted" size="xs"` is the "label that isn't a status" component (brand-guidelines `visual.md`, Components table). A plain byline is preferred because it can carry a logo.
- Brand rules to follow (`/home/sheena/workspace/lms/freedom-ls-worktrees/organisation-courses/.claude/skills/brand-guidelines/visual.md`): style with role tokens (`text-muted`, `text-on-surface`), no hard-coded colours. Surfaces stay flat. Progressive disclosure means essentials only on the card, so show name (and logo), not address or description. Keep it obvious and not clever.

### When the line shows (matches the idea)

- Dashboard "can apply" cards (`not_registered`): show it only if the course is scoped to exactly ONE organisation. For two or more organisations a single name would be wrong. Options for the spec to decide: omit, or show a neutral label. Recommend omit, since the idea only asks about single-organisation courses.
- In-progress cards (`registered` / `in_progress`): the idea asks for organisation info. Open question for the spec: which organisation, given many-to-many. The natural answer is the organisation the learner's own registration or membership belongs to, not just the course's scope list. This is not resolved in this research.
- Completed cards: the idea is silent. Showing it there keeps the same card consistent, since the same template is used for all states. Flag for the spec.
- The anonymous catalogue/markdown widget path (`cotton/course-card.html`) is a separate template. The idea only names the learner dashboard, so leave it alone unless the spec says otherwise (do not build unrequested functionality).

### Distinguishing same-named courses

- Because versions "just have the same name", the card affiliation line is the sole differentiator. Same-named cards for the same learner should be rare, because courses are scoped to organisations the learner belongs to. Where a learner belongs to two organisations that each have a "Course X", both cards will show different organisation lines and look correct.
- Slug collisions are a data concern, not UX. The card links via `course.slug`, so same-named courses need unique slugs. That is a data-model research topic and out of scope here.
- Detail pages: the same byline should appear near the course title on the detail page, so a learner who clicks through knows which version they are in. The idea does not request it, so list it as an optional follow-on.
- Accessibility: the organisation name must be real text in the DOM (not only in a logo image), so a screen reader hears it in card context.

### Admin UX for assigning courses to organisations

Codebase conventions already seen:

- Organisation admin lives in `freedom_ls/organisations/admin.py`. It has a documented seam: `ORGANISATION_SUMMARIES` for read-only summaries and `OrganisationAdmin.inlines` (change page only) so other apps can add their own inlines. `organisations` must not import other apps' models.
- Many admins use `autocomplete_fields` (see `registration_rules/admin.py`, `learner_management/admin.py`). `OrganisationAdmin` already defines `search_fields = ["name"]`, so autocomplete on Organisation works.

Patterns, in order of fit:

1. On the Course admin, a many-to-many field with `filter_horizontal` (dual list) or `autocomplete_fields`. Courses are assigned from the course's perspective ("who may see this course"). Autocomplete scales better if there are many organisations. `filter_horizontal` is friendlier for a handful. Empty selection should mean "available to all organisations" (the current behaviour), and the field help text must say so. This is the key admin UX risk. Without help text, an empty field looks like "no one".
2. Reverse view on the Organisation change page, via the existing inline or summary seam: a read-only list of the courses scoped to that organisation. Direction matters because `organisations` cannot import course models, so the course app contributes it.
3. If the relationship is an explicit through model (in case of extra fields later), a `TabularInline` with `autocomplete_fields = ["organisation"]` on the Course admin matches existing style. Not needed unless the through model carries data.
4. A `list_filter` by organisation and a `list_display` column on the Course admin help admins find same-named courses. This matters here, since the same title appears multiple times. Showing the organisation names in the changelist is the most useful admin affordance for this feature.
5. Admin copy follows `voice.md` (not read in this run).

Operational note: the Course admin is likely a content-sync-managed model (courses come from markdown). If so, the assignment may be editable only in admin and must survive content re-imports. That is a data/content-sync concern for other research units.

## 3. Summary of recommendations

- One new reusable organisation byline component (muted line, optional small `logo`, name text), placed under the title in the shared card body.
- Show it on single-organisation "can apply" cards and on registered/in-progress cards. Leave other states and the anonymous widget to the spec.
- Do not reuse the status eyebrow or `c-panel-status-badge`. Prefer a plain byline over `c-chip`, because only a byline can carry a logo.
- Admin: M2M on Course admin with autocomplete or `filter_horizontal`, "empty = all organisations" help text, an organisation column and filter in the changelist, and a read-only reverse listing on the Organisation admin through the existing seams.

## References

- https://www.nngroup.com/articles/cards-component/
- https://www.coursera.org/de-DE/projects/market-new-business-canva
- https://nus.atlassian.net/wiki/x/VFQrAg
- https://exstadmin.umd.edu/support-resources/marketing-and-communications/moocs-resources
- Local: `.claude/skills/brand-guidelines/SKILL.md` and `visual.md`; `freedom_ls/learner_interface/templates/cotton/course-card-shell.html`; `.../partials/course_card.html`; `freedom_ls/organisations/models.py`; `freedom_ls/organisations/admin.py`

status: ok
