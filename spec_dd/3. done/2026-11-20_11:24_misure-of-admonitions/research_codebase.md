# Research: codebase (misure-of-admonitions)

Paths are relative to the worktree root. Line numbers are from this worktree.

## 1. Every `<c-callout>` use

The component: `freedom_ls/base/templates/cotton/callout.html`. It takes `level` (info, warning, error, success), `title` and `class`. The box is `my-6 p-4 border-l-4 rounded-r-lg` (line 9). The title is an `<h4 class="text-xl font-semibold">` with a `size-5` icon (lines 10-14). The body is `px-4 space-y-4 pt-2` (line 15). `info` uses `bg-primary/10` / `border-primary`, not an info token (line 22). An unknown level renders nothing (no `{% else %}`, lines 21-37).

### App templates (9 in `freedom_ls/`, 11 tag uses)

| File:line | Level | Title | Message | Wrapper |
|---|---|---|---|---|
| `base/templates/account/login.html:18` | info | "New here?" | Offer to create an account, plus a `<c-button>`. Only after a failed login when `allow_signups`. | Inside `<div role="alert">` (line 12) beside `text-error text-sm` non-field errors (lines 13-15). |
| `course_applications/templates/course_applications/applicant_details.html:13` | error | "We couldn't use those details" | `form.non_field_errors` | `<div data-testid="details-errors" role="alert">` |
| `course_applications/templates/course_applications/check_your_answers.html:26` | error | none | `required_answers_error` | none |
| `course_applications/templates/course_applications/check_your_answers.html:80` | success | none | "Your application has been submitted…" | none |
| `course_applications/templates/course_applications/form_page.html:30` | info | none | "This application has been submitted and can no longer be changed." (`read_only`) | none |
| `educator_interface/templates/educator_interface/panels/course_content.html:13` | info | none | "Learners can't see this outline yet. The course is marked as still in development." Uses `class="my-0"` to cancel the component's margin, inside a `px-4 pt-4 sm:px-6` wrapper. | none |
| `form_engine/templates/form_engine/partials/answer_errors.html:11` | error | "Missing answers" | `required_answers_error` | `data-testid="required-answers-error" role="alert"` |
| `form_engine/templates/form_engine/partials/answer_errors.html:19` | error | "Invalid answers" | `rejected_answers_error` | `data-testid="rejected-answers-error" role="alert"` |
| `form_engine/templates/form_engine/question.html:61` | error | none | `ERROR! UNHANDLED FORM TYPE {{ question.type }}`. Developer-facing. | none |
| `learner_interface/templates/learner_interface/course_detail.html:76` | info | none | The educator paused the course. The text varies with `planned_resume_on`. | `<div data-testid="course-paused-callout">` |
| `learner_interface/templates/learner_interface/course_detail.html:86` | warning | none | "Your access to this course ended on …" | none |

Also in the panel framework reference page: `freedom_ls/panel_framework/templates/panel_framework/reference/_examples.html:499-505`. It is a "Callout" section, id `callout-info`, with the text "This is `c-callout`; the kit builds nothing new here." This is a tenth template that references `c-callout`. The reference has to change when the component is deleted.

`educator_interface/views.py:2568` names `staff_only_admin_callout.html`, but that partial already renders `<c-panel-notice>` (partial line 8). It only has "callout" in its filename.

First Class's `landing_pages` `lp/step.html` also uses `c-callout`. It is outside this repo and is covered by the upgrade notes.

### Tests that touch callout

- `freedom_ls/base/tests/components/test_callout_component.py`: the whole file tests the component. It asserts `text-on-{warning,success}-light` and not bare `text-{level}` (lines 15-22), and that a passed class lands on the box (`rounded-r-lg mx-auto max-w-reading`, lines 25-30). It is deleted with the component. The new component's test can inherit the two intents (readable text on the tint, and class passthrough).
- `freedom_ls/markdown_rendering/tests/test_markdown_utils.py:60-96, 694-708`: these tests assert that `<c-callout>` in markdown is stripped by nh3, because it is not in `MARKDOWN_ALLOWED_TAGS`. They use the literal string, not the component, so they keep passing after deletion. They guard against re-adding the tag, so leave them.
- `freedom_ls/accounts/tests/test_views.py:292-380`: tests named `test_*callout*`. They check the login page's "New here?" box through `role="alert"` (helper `accounts/tests/_auth_page_helpers.py:27-33` takes the last `role="alert"` region). They depend on the wrapper `<div role="alert">`, not on callout classes.
- `freedom_ls/educator_interface/tests/test_views.py:8142` (`test_course_content_callout_shows_only_while_in_development`) and `freedom_ls/learner_interface/tests/views/test_course_paused.py:284-305` (asserts `data-testid="course-paused-callout"`). Both depend on text and test ids.
- `freedom_ls/learner_interface/tests/views/test_course_player.py:4462-4474` (`test_the_closed_notice_is_not_a_callout`). It asserts that no node under the item-closed notice's parent has the `border-l-4` class. It couples to callout's current class, so the new alert's class list matters here. If the new alert drops `border-l-4`, this test stops guarding anything and needs reworking, or it could assert on the new alert's marker instead.
- `freedom_ls/panel_framework/tests/invariants/test_templates.py:643-660` has `FORBIDDEN_IN_DIALOGS`, including `"<c-callout>": re.compile(r"<c-callout\b")`. It forbids callout in dialog templates, and the new alert will need the same rule there. If `c-callout` is deleted, that entry is dead and should be re-pointed at the new alert (dialogs use `c-panel-notice`).
- `freedom_ls/panel_framework/tests/test_reference.py:37-60`: `COMPONENT_NAMES` includes `"callout"`, which must match an example id in `_examples.html` (`callout-info`).

## 2. Other ad-hoc alert, notice or banner markup the new alert could absorb

Existing overlap, which matters most:

- **`<c-panel-notice>`** (`freedom_ls/panel_framework/templates/cotton/panel-notice.html`) already exists. It takes `tone` (info, warning, error, success) and `title`. It renders `rounded-md border p-3 text-sm text-on-surface` with `border-X/20 bg-X/10`, and `role="alert"` for error and `role="status"` for success (line 15). It has no outer margin and it uses real `info`/`warning` tokens. It is used in 17 files, mostly educator dialogs and panels. Its docstring calls it "a compact boxed sentence inside a panel or dialog". It is nearly the new component already. Open design question for the spec: new component, or promote or extend `panel-notice` for general UI (it lives in `panel_framework` and the learner app would depend on the educator framework)? The user has settled on a new component, so the spec has to say how it relates to `panel-notice`.
- **`.alert`, `.alert-success`, `.alert-error` and `.alert-info`** in `tailwind.components.css:371-386` are themeable CSS component classes: `block px-4 py-3 rounded-md border text-on-surface`, with `bg-X/10 border-X/30`. There is no `.alert-warning`. `first_class` overrides them (`freedom_ls/themes/first_class/static/themes/first_class/theme.css:165-175`). `docs/how tos/theme-fls.md:8, 257, 277, 427` documents them as Tier-2 theme overrides. A grep finds no template using `class="alert…"`, so they are an unused theme hook. The new component should probably be built on these classes (adding `.alert-warning`) so themes can reshape it. That is a strong reuse candidate.
- `freedom_ls/base/templates/partials/form.html:20`: `<div class="bg-error/10 border border-error/20 rounded-md p-3 text-sm text-error">` is a hand-built form error box.
- `freedom_ls/panel_framework/templates/panel_framework/partials/error_summary.html:10`: `rounded-md border border-error/20 bg-error/10 p-3 text-sm text-error`. It is a dialog form error summary, and the panel-framework skill says to use it with panel-notice.
- Plain text errors with `role="alert"`:
  - `course_applications/templates/course_applications/claim.html:54`
  - `course_applications/templates/course_applications/partials/claim_link_notice.html:90`
  - `base/templates/account/login.html:14` (`text-error text-sm` non-field errors, next to the callout)
  - `comms/templates/comms/partials/composer.html:88, 93`, `comms/partials/messages_button.html:52`, `comms/partials/notification_bell.html:44` (inline field-adjacent or panel-failure text)

  These are likely inline field-level feedback, not boxed alerts. The spec should decide the boundary.
- **Django messages**: `freedom_ls/base/templates/partials/messages.html` (included from `_base.html:130`) and `partials/_toast.html` render toasts. They are dismissible, fixed-position and severity-routed (error goes to an assertive region, the rest to a polite one). They are a different thing from a static in-page alert and are out of scope. Their severity mapping (`border-error`, `border-warning`, `border-success`, `border-primary` for info) is a reference for icon names (`error`, `warning`, `success`, `info`).
- `freedom_ls/base/templates/cotton/error-page.html:20-24`: error, warning and info marks use `bg-{error,warning,info}-light text-on-*-light`. It is a full-page treatment, not an alert.
- Content-engine boxes that are not to be touched: `content_engine/templates/cotton/card.html:37`, `file-download.html:25`, `pdf-embed.html:42`, `picture.html:167`. These are `bg-error/10` error boxes inside content components.
- The brand guideline already says a page a person cannot use (closed or blocked) shows a large centred icon with text, "never a callout box" (`.claude/skills/brand-guidelines/visual.md:85, 134`). The test in `test_course_player.py:4462` enforces it.
- `docs/product/learner-experience.md:212` describes the "Invalid answers" callout in a screenshot caption. The screenshot is `docs/product/screenshots/learner_application_form_invalid_answer.png`, and the screenshot and caption may need a refresh.

## 3. Existing cotton components in `freedom_ls/base/templates/cotton/`

back-link, content-header, error-page, header-button, dropdown-menu, dropdown-menu-separator, chip, button-group, date, datetime, callout, button, form-page-link, breadcrumbs, markdown-container, pagination, loading-indicator, section-pagination, page, media-card.

No `alert.html` exists, so `<c-alert>` is free in base. Naming sits next to `c-chip`, `c-callout`. The panel framework cottons are named `panel-*` (`c-panel-notice`, `c-panel-status-badge`, and so on) and the brand guidelines table lists the rest. The learner app also has its own `learner_interface/templates/cotton/` (course-card, course-card-shell).

## 4. Theme tokens

- Default theme (`freedom_ls/themes/default/static/themes/default/theme.css`):
  - base: `--color-success #38A169` (line 26), `--color-warning #F6E05E` (28), `--color-error #D23319` (30), `--color-info #0EA5E9` (32)
  - `-light` tints: `#F0FFF4`, `#FFFFF0`, `#FFF5F5`, `#EBF8FF` (37-40)
  - `-hover` (71-74), `-soft` for success (78)
- `first_class` theme: success `#38A169`, warning `#D69E2E`, error `#D71D1D`, info `#3182CE` (lines 22-28), the same light tints (33-36).
- The paired foregrounds `text-on-{success,warning,error,info}-light` are used by `callout.html` (warning and success), `admonition.html:39-52`, `comms/partials/notification_row.html:6-9`, and `error-page.html`. `docs/how tos/theme-fls.md:148` says: "Light tints are named replacements for ad-hoc opacity modifiers in chip and alert backgrounds. The paired `on-*-light` foregrounds are darker and legible on near-white tints."
- Warning is pale yellow (`#F6E05E`) in the default theme. Warning text on its own `/10` tint is unreadable, so `text-on-warning-light` or `text-on-surface` is needed. This is why `test_callout_component.py` exists. The new component's test should keep the same guard.
- `callout.html` colours info with `primary`, not the `info` token. `panel-notice` and `.alert-info` use `info`.

## 5. Brand guidelines and skills that mention callout, alert or admonition

- `.claude/skills/brand-guidelines/visual.md`:
  - line 20 and line 41: colour table rows ("Warning: callouts, non-critical alerts"; "Warning callouts" contrast row)
  - **line 84**: row "A callout in a page" gives `<c-callout level="info|warning|error|success" title="…">`. This is the row to replace.
  - line 85 and line 134: the blocked-page rule ("never a callout box")
  - line 86: the course-content row `<c-admonition type=…>`. Keep it and add a "never in app pages" note.
  - lines 163-165: an example snippet using `<c-callout level="info" title="Note">`. It must be updated.
- `claude_plugins/fls-dev/skills/panel-framework/SKILL.md`:
  - line 213-215: a notice inside a dialog or panel is `<c-panel-notice>`, "never `<c-callout>` or a hand-built `bg-error/10` box"
  - line 327: the invariant list names `<c-callout>`
  - lines 249 and 377: the word "callout" is used descriptively
- `claude_plugins/fls-dev/resources/markdown_content.md:29-50, 76`: documents `c-admonition` as a content widget and has its `MARKDOWN_ALLOWED_TAGS` entry. It should state that content widgets are for markdown only, which fits the "don't use content-engine components willy nilly" instruction.
- `claude_plugins/fls-content/skills/widget-reference/**` and `markdown-conversion/**` are content-authoring and unaffected.
- `claude_plugins/fls-dev/skills/notifications/SKILL.md:74` uses "alert" in the sense of a notification. See the glossary below.
- `claude_plugins/django-stack/` mentions only `ADMONITION_TYPES` (`skills/app-settings/SKILL.md:77`). It is generic and must stay untouched (CLAUDE.md "Plugins").
- `.claude/agent-memory/ds-code-reviewer/project_admonition_widgets.md:18` says "Don't flag developer-facing `c-callout` template usage as needing migration". That reviewer memory is now wrong. It lives in agent memory, and CLAUDE.md says not to use memory, so flag it to the user and don't edit it.
- `claude_plugins/fls-dev/resources/ ... templates_and_cotton.md` is the HTMX and cotton conventions file referenced from CLAUDE.md. I did not open it. Check it for a component list before the plan.

## 6. Domain glossary: is "alert" a taken word?

`claude_plugins/fls-dev/skills/domain-glossary/SKILL.md` has no "alert", "notice" or "banner" entry. Its only related lines are about `Message` and `Conversation` (lines 170-175): `Message` is "Distinct from Django's `messages` framework". So "alert" is free as a UI-component word, with these caveats:

- "alert" is overloaded in the code. `role="alert"` is the ARIA role. `composer.alert` and `alert=` in `comms/messaging_views.py:135-195, 385-506` is a string for the composer error. `notifications/SKILL.md:74` says "doubles every alert", and `docs/product/notifications.md` mentions "pop-up alerts" as not built. A `<c-alert>` component does not clash with these, but the spec should add a glossary row for it.
- The glossary is in `fls-dev`, the right home for a new row. It must not go into generic plugins.

## 7. Existing invariant and template-scanning tests the guard can mirror

- `freedom_ls/panel_framework/tests/invariants/test_templates.py`. This is the closest model. It builds `TEMPLATES_DIR`, `COMPONENTS_DIR` (lines 26-31), then scans with `rglob("*.html")` against forbidden-pattern dicts. See `FORBIDDEN_IN_DIALOGS` (lines 643-660) with `re.compile(...)` per rule and `@pytest.mark.parametrize("rule", sorted(...))`, and `RAW_HEX_COLOUR` and `RAW_TAILWIND_PALETTE_CLASS` (lines 54-59). It also uses `FREEDOM_LS_PACKAGE_DIR` from `freedom_ls.base.theming`.
- `freedom_ls/base/tests/invariants/test_profile_picture_fallback.py:13, 29-31`: `sorted(Path(__file__).parents[3].rglob("templates/**/*.html"))`, with one parametrised test per template (`ids=lambda path: path.name`). Simple scan-every-template shape.
- `freedom_ls/icons/tests/invariants/test_no_font_awesome.py:18, 50`: `TEMPLATE_DIR.glob("**/*.html")` plus an allowlisted path (`COTTON_ICON_PATH`). It is a good model for a scan with a carve-out.
- `freedom_ls/base/tests/invariants/test_stylesheet_boundary.py:28-37` maps CSS class prefixes to the single owning template, including the content-engine cottons (`flashcard.html`, `accordion.html`, `picture.html`).
- `freedom_ls/base/tests/invariants/` is the likely location (also `test_error_pages.py`, `test_alpine_registration.py`). `educator_interface/tests/invariants/test_answer_key_flag.py:16` and `comms/tests/invariants/test_boundaries.py:38` are other models for a ban on one directory.
- Directory convention: tests live in `<app>/tests/invariants/`. `base` is the owner of cross-app rules.

## 8. Where content-engine components legitimately render (guard carve-outs)

The 21 components in `freedom_ls/content_engine/templates/cotton/`: accordion, article-card, admonition, article-link, content-link, article-byline, code-block, card, pull-quote, youtube, file-download, organisation-mark, picture, organisation-byline, table, course-price, pdf-embed, flashcard, equation, image-grid, grid.

They fall into two groups, and the guard must not treat the folder as one set.

**A. Content widgets** (markdown only). Their names are the keys of `MARKDOWN_ALLOWED_TAGS` in `config/settings_base.py:390-410`: c-youtube, c-picture, c-content-link, c-article-link, c-article-card, c-course-card, c-pdf-embed, c-file-download, c-pull-quote, c-equation, c-grid, c-image-grid, c-table, c-code-block, c-admonition, c-flashcard, c-accordion, c-card, c-slot. Markdown is rendered by `markdown_rendering/markdown_utils.py`: nh3 sanitisation, then `_cotton_compiler.process(...)` (lines 59-66) compiles `<c-foo>` to cotton tags. The callers are the content-body templates:
- `learner_interface/templates/learner_interface/course_topic.html`, `course_form.html`
- `form_engine/templates/form_engine/partials/page_children.html`
- `content_engine/templates/content_engine/partials/course_details_body.html`
- `educator_interface/templates/educator_interface/modal/content_preview.html`
- `blog/templates/blog/article_detail.html`, `accounts/templates/accounts/legal_doc.html`, `cotton/markdown-container.html`

The python side: `content_engine/templatetags/content_tags.py`, `content_base/models.py`, `form_engine/models.py`, `accounts/legal_docs.py`. These render markdown strings, which are not template files, so a template-file scan never sees them. Cotton tags inside `.md` content are not scanned either (and demo content is under `demo_content/`).

**B. Components that app templates use directly today (a guard that bans the folder wholesale would fail on these):**
- `c-course-price`: `learner_interface/course_detail.html:56`, `partials/course_listing_price.html:13, 15`, `partials/markdown_course_card_body.html:10`, `content_engine/partials/course_details_hero.html:27`
- `c-organisation-byline` and `c-organisation-mark`: `learner_interface/course_detail.html:129`, `cotton/course-card-shell.html:31`, `partials/course_row_eyebrow_left.html:9`, `content_engine/.../course_details_hero.html:55`
- `c-article-byline`, `c-article-card` and `c-grid`: `base/templates/cotton/content-header.html:21-26`, `blog/article_detail.html:40`, `blog/article_list.html:15-19`
- Content-engine cottons nesting one another: `article-card` uses `article-byline`, `organisation-byline` uses `organisation-mark`, `image-grid` uses `grid`.

So the guard has to be an explicit list, not the whole folder. Design options for the spec:
- ban only the widgets that exist only for markdown (admonition, accordion, flashcard, pull-quote, equation, youtube, pdf-embed, file-download, code-block, table, picture, image-grid, card, content-link, article-link), or
- derive "content-only" from `MARKDOWN_ALLOWED_TAGS` minus an explicit "also used by app pages" allowlist (`c-grid`, `c-article-card`, `c-course-card`, and so on), or
- keep a per-component allowlist of template paths.

Note also that `c-course-card` is in `MARKDOWN_ALLOWED_TAGS` but lives in `learner_interface/templates/cotton/course-card.html`. It is used in the learner app and by markdown (`markdown_course_card_body.html`). A rule keyed on the content-engine directory would not see it.

Template locations to treat as "content rendering" for the scan: files inside `freedom_ls/content_engine/templates/` itself, the cotton components themselves (`.../cotton/*.html` reference each other), and `*test*` fixtures. App-template scan scope is `freedom_ls/*/templates/**/*.html` minus those. The scan must also skip `{% comment %}` blocks and docstrings: `callout.html:3-6`, `file-download.html:9-10`, `grid.html`, `image-grid.html:4-9` and `content-header.html:21-26` mention `<c-...>` in comments. `content-header.html:26` shows `<c-article-byline>` in a comment slot example and `course_details_hero.html:12` mentions `<c-course-price>` in a comment. `panel_framework/reference/_examples.html:499-505` writes the string `c-callout` in prose.

## 9. Docs mentions of `c-callout`

- `docs/how tos/landing-pages.md:18`: "`<c-page>`, `<c-button>`, `<c-callout>`, `<c-chip>` and `<c-media-card>` are available" to downstream landing-page authors. It must change to the new component, and it is where the downstream break (`lp/step.html` in First Class) is visible.
- `README.md:148, 158` and `docs/product/*` (configuration-and-extension.md:54, 143; content-editing-workflow.md:137) mention callouts only as content admonitions. No change needed.
- `docs/product/learner-experience.md:212` has the "Invalid answers" callout screenshot caption (see section 2).
- `docs/how tos/theme-fls.md:8, 148, 257, 277, 427` document `.alert` and `.alert-*` as the theme hook. If the new component uses them, update the docs. Add `.alert-warning` to the list if it is added.
- No `docs/` upgrade-notes file. Upgrade notes are per spec, `<spec-dir>/upgrade_notes.md`, authored by `claude_plugins/fls-dev/commands/update_upgrade_notes.md` (schema at lines 14-50). Recent examples are under `spec_dd/3. done/*/upgrade_notes.md`. The migration is a downstream step ("replace `<c-callout level=… title=…>` with the new alert"), and it should also note the `my-6` margin and `text-xl` title differences.

## 10. Conflicts and risks to carry into the spec

1. `panel-notice` (and `.alert*` CSS) already do most of this job. The spec must say whether the new component wraps or replaces them, and must avoid a third notice style. The panel-framework skill currently tells authors to use `panel-notice` in panels and dialogs, so the new alert's "general UI" scope vs `panel-notice`'s "panel or dialog" scope needs a stated rule.
2. The visual change: `callout` has `my-6` and an `h4 text-xl` title. Pages that rely on its margin (`check_your_answers`, `form_page`, `course_detail`) will lose vertical spacing when swapped. `course_content.html:13` passes `class="my-0"` to fight it. Decide whether the alert has a margin (panel-notice has none, "the parent spaces its children").
3. Accessibility wrappers: 4 call sites wrap the callout in a bare `<div role="alert">` (`login.html:12`, `applicant_details.html:12`, `answer_errors.html:10, 18`). `panel-notice` puts `role="alert"` on the box itself for error. Moving the role into the component would change the 422 re-render announcement tests that use `_auth_page_helpers.py:27-33` ("last `role="alert"` region"). The base layout's toast region also has `role="alert"` (`messages.html:70`).
4. `login.html:12-23` mixes plain error text and the info callout inside one `role="alert"` div. That is an existing quirk to look at in the plan.
5. `test_course_player.py:4462-4474` keys on `border-l-4` (see section 1).
6. `.claude/agent-memory/ds-code-reviewer/project_admonition_widgets.md:18` is stale (section 5).
7. Tailwind: `tailwind.components.css` is the stylesheet, built with `npm run tailwind_build`. Any new `.alert-warning` class means a rebuild. Check `test_stylesheet_boundary.py` for rules about which CSS classes may live in the shared stylesheet.

status: ok
