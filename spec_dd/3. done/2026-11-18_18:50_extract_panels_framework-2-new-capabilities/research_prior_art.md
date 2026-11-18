# Prior art: panel framework new capabilities

Question: what has already been tried for this, here or elsewhere, and what happened?
All paths are relative to the repo root. Worktree state is the code after spec 1 merged
(`d19089147 ... close out the worktree`, `a762fc492 ... start the spec`). I had no shell, so I did
not run `git log`; commits are cited only where a spec or QA report names them.

## Headline findings (these change the idea)

1. **Expandable table rows already exist in the framework.** The idea's "Open until the spec" first
   question ("Did the audit log build expandable rows inside `educator_interface`?") resolves as
   follows: the audit log spec (`spec_dd/3. done/2026-11-08_09:13_design_educator_interface_audit_log/`)
   built the row detail generically **in `panel_framework`**, not in `educator_interface`, and it is
   merged. The idea's premise ("`data-table.html` has no row-detail slot", "only a per-cell
   `<details>` exists") is out of date.
   - `DataTable.row_detail_template_name` (renamed from `row_detail_template` by spec 1) and the
     per-row predicate `has_row_detail(row)`: `freedom_ls/panel_framework/tables.py:276-281`, rows
     marked at `:516-521`, context at `:553`.
   - Table render: `freedom_ls/panel_framework/templates/cotton/data-table.html:91-172` (`x-data="rowDetail"`
     on the `<table>`, leading toggle column with sr-only "Details" header, chevron button with
     `aria-expanded`/`aria-controls`, hidden `<tr data-row-detail>` indented past the toggle column).
     Card render below `md`: `templates/cotton/data-table-card.html:31-68` and `data-table.html:189`.
   - Alpine: `rowDetail` in `static/panel_framework/js/alpine-components.js:1080-1097`. Opens rows
     independently, flips `aria-expanded` on the button and `hidden` on the detail, server renders
     everything closed, an HTMX swap of the region resets it, no `x-transition` (a `hidden` attribute
     cannot animate; only the chevron turns, via CSS keyed on `aria-expanded`).
   - Tests exist: `tests/components/test_data_table.py`, `test_data_table_card.py`, `test_tables.py:1597-1645`,
     `tests/stub_panels.py:404` + `tests/templates/panel_framework/test_row_detail.html`,
     Playwright `tests/playwright/test_data_table_flow.py:810-868` (mouse and keyboard, table and card).
   - Consumer: `AuditLogEntryTable` in `freedom_ls/educator_interface/views.py:916-924`
     (`audit_row_detail.html`, `has_row_detail`).
   - What spec 2 therefore has left for expandable rows: nested child rows (the course outline), the
     "does the detail load inline or lazily" question, an `as_of`-style reference entry, and a
     **compact density** option. **No density option exists** (grep for `density` in
     `freedom_ls/panel_framework` finds nothing; the audit log's "compact" is per-cell classes in
     `educator_interface`, e.g. `audit_when.html`, `audit_what.html` with `truncate`, plus
     `md:flex-nowrap` on `panel_framework/partials/datetime.html`, fixed in `4d7419c71`).
   - Deciding point: the answers file says nested child rows are covered and the outline moves onto
     `<c-data-table>`. The existing mechanism is a *detail block under a row*, not child rows, so the
     work is a second mode on the existing capability, not a fresh build. The idea's name
     `row_detail_template` is stale: the live name is `row_detail_template_name` (spec 1's rule,
     `spec_dd/3. done/2026-11-16_19:13_extract_panels_framework-1-gather-generic-code/1. spec.md:279`,
     "Template attributes end in `_template_name`"; breaking change listed in that spec's
     `upgrade_notes.md:47-50`).

2. **The leading-chevron design was a deliberate redesign mid-spec.** The audit log plan
   (`2. plan.md:904, 921`) first drew a trailing "More" toggle and a tinted full-width open panel.
   Commit `22cd0717e` ("redesign", named in the QA report) changed it to a leading chevron under a
   hidden "Details" header, an untinted open detail indented to the first data column, and an inline
   card variant with labelled rows. QA recorded the plan deviations as "not a code defect: the spec and
   plan are out of date" (`.../qa_report.md:164-166`, bug B3 left as a doc defect). Constraint for spec
   2: keep that look; do not reintroduce a tinted panel or a trailing control.

3. **`LazyBodyPanel` has no place to put "as of" except `_lazy_region.html`.**
   `freedom_ls/panel_framework/lazy_panels.py:27-62` (moved by spec 1) builds `is_loaded`, `loaded_url`,
   `skeleton_*`, `load_label`, and `too_large_message`. `templates/panel_framework/panels/_lazy_region.html`
   leaves the loaded state as an empty `{% block loaded_body %}` that each panel's region template fills,
   so the framework owns no wrapper around the loaded content. A stamp must be added in that
   shared frame (before or after `loaded_body`) and be opt-in per the answers (`answers.md`: "Opt-in.
   Off by default"). Spec 1's own UX research planned a test that "the skeleton region has no stamp so
   spec 2's change is visible" (`spec_dd/3. done/2026-11-16_19:13_extract_panels_framework-1-gather-generic-code/research_ux_patterns.md:27`).
   Spec 1's idea says `LazyBodyPanel` "moves without an `as_of` value. The `as_of` stamp is spec 2's"
   (`.../idea.md:73`).

4. **A required-reason dialog was already hand-built once, outside the framework.** `freedom_ls/deadlines/forms.py:37-38`
   defines its own `ReasonForm(forms.Form)` with a required `reason` (`CharField(max_length=REASON_LENGTH,
   widget=UnfoldAdminTextareaWidget)`), used by `PauseCourseForm`, `ResumeCourseForm`, `ExtendDeadlineForm`.
   That is Django admin (Unfold) action forms, not the panel framework, and it shadows the framework
   name. It shows the demand is real, and it is a name-collision risk for anyone importing both, but it
   is not reusable here (admin widgets).

## 1. Reason dialog (G5)

What exists (`freedom_ls/panel_framework/`):

- `actions.py:720-750` `ReasonMixin(PanelAction)`: `reason_form_class`, adds `reason_form` to the dialog
  context, `handle_submit` validates and on failure re-renders the fragment with status **422**, then
  calls `handle_confirmed_submit(replace(ctx, reason=...))`. Docstring rules: list the mixin first in
  the bases; an action with its own submit overrides `handle_confirmed_submit`, never `handle_submit`.
- `forms.py:15-32` `ReasonForm`: `reason_label = "Reason (optional)"`, `reason_help_text`,
  `reason_max_length` (default `REASON_LENGTH = 500`); the field is hard-coded `required=False`.
- `templates/panel_framework/partials/reason_field.html` includes `partials/form.html` with `reason_form`;
  `modal/confirm.html:28` renders it in `{% block reason %}`.
- Invariant `tests/invariants/test_reason_mixin.py`: every `ReasonMixin` subclass submits through the
  mixin's `handle_submit` (no `handle_submit` override). Spec 2's choice variant must keep this true.
- Consumers: `EducatorReasonMixin` (`educator_interface/actions.py:375`) plus about ten actions
  (deactivate learner, cohort, registration, role, staff member; remove from cohort; delete empty cohort),
  `EducatorReasonForm` (`educator_interface/forms.py:288`). These must stay untouched.

Decided and recorded earlier:

- G5 (`spec_dd/3. done/2026-11-16_19:13_extract_panels_framework-1-gather-generic-code/research_framework_completeness.md:191`):
  "add a required-reason variant (`reason_required = True`) and an optional reason-choice list."
  Rated "Generic, small". The idea.md uses the same attribute name.
- Demand: `spec_dd/1. next/educator-interface-full-polish/application-review-ui/idea.md:67,200,247`
  (`request_changes` and `reject` "require" an applicant-visible message; stored in
  `ApplicationStateTransition.message`, `:143`; the idea proposes an "intermediate action page", which
  the dialog replaces). The multi-step applications spec's reason-from-a-fixed-set is listed in
  `research_framework_completeness.md` section 4. I found no concrete shape for the choice list in any
  idea; so the declaration shape is genuinely open (the idea defaults to following existing naming).
- Existing naming to follow: `reason_form_class`, `reason_label`, `reason_help_text`, `reason_max_length`
  (all on the form; the mixin owns only `reason_form_class`). `reason_required` on the action, per G5,
  would need to reach the form (the form builds its field in `__init__`), or move to the form like
  `reason_max_length` did. Spec 1 settled that length lives on the form subclass
  (`SKILL.md:34-35`); consistency argues for the same for requiredness.
- No rejected approaches recorded for reasons. No QA feedback has been captured about the reason
  dialog's look. The skill's dialog rules apply (`claude_plugins/fls-dev/skills/panel-framework/SKILL.md`
  lines about dialogs: one footer, Cancel left, the reason of a disabled confirm in the body under its
  field, errors under the field with `role="alert"` and the message alone, 422 on error, `reason_field`
  is a framework partial).

## 2. `as_of` on lazy panels (G6)

- G6 (`research_framework_completeness.md:192`): move the panel and "add an `as_of` value to the
  context". Demand: `deadlines-7-educator-at-risk` ("Their common complaint is stale data, so the view
  shows when it was computed", `spec_dd/1. next/deadlines-7-educator-at-risk/idea.md:22`, and "says when it
  was computed, with the time zone", `:50`). `CohortNeedsAttentionPanel` is currently an empty stub there
  (`:23`).
- That idea says whether a surface is live or gathered is "spec 10's" to decide, so what `as_of` means
  for deadlines-7 is not settled; spec 2 should stay generic (value supplied by `get_loaded_context`,
  else render time), as the idea says.
- No earlier attempt at a stamp exists in the repo (grep for `as_of` / "as of" in app code finds none
  in panels). The only "as of" strings are in research files.
- The framework's existing date formatting is `templates/panel_framework/partials/datetime.html` and
  `cotton/data-table-cells/datetime.html` (the audit log used `<time datetime>` with offset;
  `audit_when.html`). The audit log's spec decision 2 and UX research require `<time datetime="...">`
  with offset for every timestamp, "absolute time available to assistive technology, not just on hover"
  (`spec_dd/3. done/2026-10-29_08:48_educator-interface-11-audit-log/research_ux_patterns.md:85`).
- Pattern constraint from spec 1: `PanelBodyTooLargeError` path (`too_large_message`) has no loaded body;
  the stamp must not show there.

## 3. Expandable rows and compact density

Prior work (see headline 1 and 2). Further history and rules:

- The first audit log spec (`spec_dd/3. done/2026-10-29_08:48_educator-interface-11-audit-log/`) used a
  per-cell `<details>`/`<summary>` for "Show 14 learners" (`research_ux_patterns.md:86`: "keyboard
  operable with a clear label. Do not use hover-only reveals"). The design spec replaced it with the
  row detail and explicitly says "There is no `<details>`/`<summary>` or 'More' disclosure"
  (`.../1. spec.md:95`, `upgrade_notes.md` removes `audit_details.html`).
- The idea for the design spec (`.../idea.md:3`) asked: "Make layout of logs more compact. Allow
  expandable accordian style rows". Compactness was delivered as one-line rows through column templates,
  not as a table option. The design spec lists "Keeping rows expanded across pagination, filtering or a
  refresh swap" as out of scope (`1. spec.md:35`), so state loss on swap is accepted behaviour.
- Rules from the skill (`claude_plugins/fls-dev/skills/panel-framework/SKILL.md`): "An ordered list with
  per-entry actions is a data table: rows spaced by their cell padding only, the chevron and the small
  action button inside the row next to its text"; a disclosure shows the icon chevron that turns up
  while open; a table whose columns do not fit shows as cards via `cards_when_narrow`, never a sideways
  scroll; a button is 44px tall on a phone.
- Invariants that will bite: `tests/invariants/test_templates.py:584-603`
  `test_every_expand_chevron_turns_when_its_control_opens` (every `<c-icon name="dropdown">` needs a
  `rotate-180` variant on itself or its wrapper), `:483-501`
  `test_no_template_hand_writes_a_table_outside_the_table_components`, and
  `tests/invariants/test_alpine_registration.py` (every `x-data` name a framework template uses must be
  registered in the framework JS, "unless the host supplies it"). If the outline moves onto
  `<c-data-table>`, `courseOutline` (registered in `educator_interface/static/educator_interface/js/alpine-components.js:2-21`)
  must either move into the framework or be replaced by a framework component. Note the CSP Alpine
  build: no inline expressions or arguments; toggle names rows through data attributes.
- Audit log QA bug history relevant to this work: B1 avatar colour (not related), B2 the When cell wrapping
  at 768px making rows 57px instead of 49px, fixed by `md:flex-nowrap` on the shared datetime partial in
  `4d7419c71` (`.../qa_report.md:171`). A compact density option must hold one-line rows at tablet width.
  Tablet is where the audit log failed QA.
- The earlier research flagged `tailwind.components.css` rules: an open `data-row-detail` row takes its
  data row's bottom border and shares its hover (`.../upgrade_notes.md:55-56`), so any density option
  that changes row padding must be checked against those `tbody tr` rules, and `npm run tailwind_build`
  is required after CSS or new utility classes.
- No compact/density option was ever specified elsewhere. The closest precedents are not table
  options: `panel-empty-state size="compact"` (spec 1, `1. spec.md:222`), a `variant="compact"` on
  learner course cards, and `data-compact` on the footer bar. These show the naming convention for a
  compact variant is `size="compact"` or `variant="compact"` rather than `density=`; the idea's default
  is to follow the naming of existing `DataTable` options, so a class attribute (like
  `cards_when_narrow`) is the likelier shape.

### The course outline (nested child rows)

History:

- Built in `spec_dd/3. done/2026-11-12_11:54_educator-interface-course-content-preview/` (spec at
  `1. spec.md:53`, plan at `2. plan.md:124`, frontend QA at `3. frontend_qa.md:44-45` and `qa_report.md:69`).
  The template `educator_interface/panels/course_content.html` states why it is hand-rolled: "The markup
  and classes are the data-table component's, hand-rolled because the rows come from
  `Course.collection_items()`, not a queryset."
  So there are two reasons it is exempt, not one: (a) tree rows, and (b) a non-queryset source. The
  exemption text in `HAND_WRITTEN_TABLE_EXEMPTIONS` only gives (a). A spec moving it onto
  `<c-data-table>` has to answer (b) as well: does a `DataTable` take a list of non-model rows (check
  `get_rows` and the static table path; `panel-table` is the static-table component)?
- Behaviour decided and QA-passed: groups open by default, **no persistence** ("an educator reads the whole
  outline"), a part has no content of its own so its row only expands, an empty part shows a child row
  "No items in this part.", a one-page form is a single row, the chevron is `size-8` with `aria-expanded`
  and `aria-controls` naming its child rows, and a child row hides with **any group above it**
  (nested hiding through `data-parents`; only `x-show` with `data-parents`, no `x-collapse`).
  Depth is shown by `ps-8/ps-12/ps-16`. Notes rows span three columns. The mobile view is the same
  table (the `Type` column is `hidden md:table-cell`); it has **no card layout**, so moving onto
  `<c-data-table>` changes mobile (cards) unless `cards_when_narrow` is off or a card template mirrors
  the tree. This needs a decision.
- The row-detail chevron markup in the outline was copied from `data-table.html` (same classes
  `group ... aria-expanded:text-primary` and the `motion-safe:transition-[rotate] group-aria-expanded:rotate-180`
  span). The two chevrons are already visually identical; the outline's is `size-8` with `-my-1`.
- Rejected earlier: an "expand all / collapse all" control (`research_ux_patterns.md:80` in that spec:
  optional, "project rule 'don't build functionality not explicitly requested' applies"); `localStorage`
  persistence as in the learner TOC `coursePart` component (not copied); a whole-row click target
  (conflicts with the toggle and with the skill's rule that a row is clickable only as a row link).
- The design hint "allow fully custom child-row overrides" in the answers file has no precedent in the
  repo; `card_template_name` and `row_detail_template_name` are the only per-row template hooks, and
  `Column(template_name=)` per cell.

## 4. Roadmap constraints

`spec_dd/1. next/roadmap.md` "Panel framework extraction" (lines 88-111):

- Spec 2 runs beside spec 3 (**both edit `tests/conftest.py`**: a collision to rebase) and blocks spec 4
  (template contract). The collision list under "Account area on panels" says the two learner-profile
  framework specs edit "panel framework actions and form templates, as do
  `extract_panels_framework-2-new-capabilities` and `extract_panels_framework-4-template-contract`.
  Whichever lands second rebases." Their specs add file upload actions
  (`learner-profile-use-panels-framework-1-file-upload-actions`) and an editable list panel (`-2`); the
  fit research says spec 2 "does not add upload or a row-list shape"
  (`spec_dd/1. next/learner-profile-use-panels-framework/research_panel_framework_fit.md:178`).
- Decided: no shared core package; the package ships overridable primitives; multi-site stays; the
  app label is `panel_framework`; no data migrated. So anything spec 2 adds must have no FLS naming
  (idea restates this) and must not add models or migrations.
- Open question named in the roadmap: where `sidePanel`/`refreshTimer` live (answered by spec 1: they
  went to `shell-components.js`, a host loads both bundles).
- Educator interface notes (roadmap `:82`): `educator-interface-misc-polish`, `-data-table-filter-design`,
  `-dark-mode` change framework templates or JS; they were meant to land before spec 1 and may rebase
  across spec 2 if they touch `data-table.html`. `educator-interface-misc-polish` includes "show and hide
  table columns" and smaller mobile buttons, which touch `data-table.html` and toolbar partials as well.
- Spec 1's spec lists spec 2's scope in one line: "expandable rows, compact density, `as_of`, and the
  required-reason and reason-choice dialogs" (`spec_dd/3. done/2026-11-16_19:13_extract_panels_framework-1-gather-generic-code/1. spec.md:42`).
  Spec 1 research on completeness (section "Can wait until after extraction",
  `research_framework_completeness.md:202`) described expandable rows as "Additive: a `row_detail_template`
  on `DataTable` and a small Alpine toggle", and flagged "human review of the design is still pending";
  the idea's open question was never closed because the audit log merged first (`educator-interface-12`
  QA screenshot `audit-log-desktop.png` and `design_educator_interface_audit_log` are both under
  `spec_dd/3. done/`).
- The docs in `claude_plugins/fls-dev/skills/panel-framework/SKILL.md` do not yet mention
  `row_detail_template_name` or `rowDetail` in the "what lives where" list (grep for "row detail" finds
  only the card and chevron rules); a spec updating the skill should add the three new capabilities, and
  the idea has no step for it. (Not verified beyond grep.)

## 5. Captured rules and feedback that constrain this work

- No `feedback` files exist under `spec_dd/` that cover these features (glob found none relevant).
- From the skill and invariants, apply to everything this spec adds:
  - Template attributes end in `_template_name` (spec 1 decision); use `reason_*`/`row_detail_*` prefixes
    consistent with that; `Column(template_name=)`.
  - 422 for dialog validation errors (project CLAUDE.md); error text under its field, message alone,
    `role="alert"`.
  - Every `<c-icon name="dropdown">` must carry `rotate-180` on itself or its wrapper.
  - No hand-written `<table>` outside `data-table.html` / `panel-table.html` once the exemption goes.
  - Every `x-data` name used by a framework template must be registered in the framework JS.
  - The CSP Alpine build allows no inline expressions or call arguments.
  - Components and role tokens only; nothing hardcoded (spec 4 audits it).
  - `docs`: reference page entries in `freedom_ls/panel_framework/reference.py` and
    `templates/panel_framework/reference/_examples.html`; the Playwright reference-flow test
    `tests/playwright/test_component_reference_flow.py` exists and spec 1 added examples there (for
    instance `empty-state-compact`).
- Spec 1's frontend QA pass (`spec_dd/3. done/2026-11-16_19:13_extract_panels_framework-1-gather-generic-code/qa_report.md`)
  checked compact empty states, reports and messages, and found no recorded blocking issue related to
  reasons or lazy panels. I did not read the report in full; the headline says only the rows I grepped.

## Outside prior art (brief)

- Django admin has no row-expansion; the nearest generic ones are DataTables' child rows and
  Bootstrap Table's `detailView`. Both render the detail either from the row data (inline) or fetched
  on first open; accessibility guidance (WAI-ARIA Authoring Practices "Disclosure" and the
  "Treegrid" pattern) is the source for `aria-expanded` + `aria-controls` on a button, which the
  existing `rowDetail` follows. A tree of rows that hide with their ancestors is the ARIA **treegrid**
  pattern (`role="treegrid"`, `aria-level`, `aria-expanded` on the row); the outline uses plain table
  roles and a button, which is what the repo's own QA accepted. I did not fetch these references
  (no web research was done for this topic); treat them as background knowledge, not verified.
- Prior art for the as-of stamp and the reason-choice list is in the research files already cited
  (`deadlines-7` idea; application review idea). Nothing outside the repo was needed.

## What this means for the spec (short)

1. Re-scope capability 3: expandable detail rows exist; add nested child rows (outline), decide the
   non-queryset source and mobile treatment, add compact density, and delete the exemption. Record the
   audit-log answer as "built generically in the framework by `design_educator_interface_audit_log`;
   no move needed".
2. Use `row_detail_template_name`, not `row_detail_template`.
3. Put the as_of stamp in `_lazy_region.html`, opt-in, hidden when `too_large_message` is set, skeleton
   state unstamped; `<time datetime>` with offset.
4. Reason dialog: keep `ReasonMixin.handle_submit` the single validation point (invariant), keep
   422, put `required` and choices where `reason_max_length` lives (the form) or on the action and
   pass into the form, and don't touch the ten educator actions.
5. Collisions to plan for: `tests/conftest.py` with spec 3; framework templates with
   `learner-profile-use-panels-framework-*` and spec 4.

status: ok · reason: complete; no shell was available, so git history is cited via spec and QA records, not `git log`
