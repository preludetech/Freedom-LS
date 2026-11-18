# Research: prior art for misure-of-admonitions

Limit: this worker had no shell, so `git log -S'c-callout'` was not run. Origin is inferred from spec files, not commits. Paths are repo-relative.

## 1. How `c-callout` came to be used in app pages

- Born as a **content** widget in `content_engine`. `spec_dd/3. done/2026-06-18_14:35_more_course_widgets/1. spec.md` §3 and §7.2 moved it. The spec said `c-callout` was "used in exactly one application template" (`course_form_page.html:111`), moved `callout.html` to `freedom_ls/base/templates/cotton/`, and dropped `{% markdown slot %}` for a plain `{{ slot }}`. It removed `c-callout` from `MARKDOWN_ALLOWED_TAGS` and migrated demo content to `c-admonition`. The reviewer memory `.claude/agent-memory/ds-code-reviewer/project_admonition_widgets.md` records the same decision: "Don't flag developer-facing `c-callout` template usage as needing migration".
- That spec made `c-callout` the "application-level" component by default, one use deep. It never designed it as a theme-fit alert. The markup is content-styled: `my-6 p-4 bg-X/10 border-l-4 rounded-r-lg`, an `h4 text-xl` title, and a `px-4 space-y-4 pt-2` body (`freedom_ls/base/templates/cotton/callout.html`).
- Spread afterwards. Later specs reused it because it was the only "page note" component:
  - `2026-09-29_14:19_educator-interface-4-panel-framework-components`: idea.md line 36 says "Use `c-callout` from `base`", and spec line 25 says to leave its markup alone.
  - `2026-11-15_13:44_deadlines-3-extensions-and-pause`: `research_ux_patterns.md` and spec line 251 use `c-callout level="info"` for the paused-course CTA slot.
  - `2026-10-24_06:02_anon-application-improvements`, `2026-09-10_09:45_simple-application-forms`, `2026-09-27_07:08_more-prominent-signup-button` and others in the grep hit list.
- Today it is used by 9 FLS templates:
  - `base/account/login.html`
  - `course_applications/{applicant_details,check_your_answers,form_page}.html`
  - `educator_interface/panels/course_content.html`
  - `form_engine/partials/answer_errors.html`
  - `form_engine/question.html`
  - `learner_interface/course_detail.html`
  - the panel-framework reference `_examples.html`
- `.claude/skills/brand-guidelines/visual.md` lines 84-86 and 163 tell authors "A callout in a page → `<c-callout>`". Line 85 says a blocked page uses an icon "never a callout box". Line 86 maps content callouts to `c-admonition`. So the skill split content from page callouts by name only; the split is not enforced.
- `docs/how tos/landing-pages.md:18` offers `<c-callout>` to downstream landing pages. The user's answers say First Class `lp/step.html` also uses it.

## 2. A prior, partial fix: `c-panel-notice`

- `spec_dd/3. done/2026-11-16_19:13_extract_panels_framework-1-gather-generic-code/` found the problem for panels and dialogs.
  - `research_consistency_audit.md` lines 47-53: `c-callout` is "a course-content component: `my-6`, `border-l-4`, `text-xl` title" used in two deactivate dialogs. Hand-written `border-error/20 bg-error/10 p-3` notice boxes appeared in about 7 places.
  - The spec (glossary line 33) coined `<c-panel-notice tone title>`. It is explicitly "Not `<c-callout>`, which stays the course-content component". That wording is wrong: `c-callout` is not the content component, `c-admonition` is. It shows how the terms were muddled.
- Result: `freedom_ls/panel_framework/templates/cotton/panel-notice.html`. It has `rounded-md border p-3 text-sm`, tone tints at `/10` with `/20` borders, and `role="alert"` for error and `role="status"` for success. It has no icon, no dismiss, and no outer margin. It is a compact notice for panels and dialogs only.
- Used in 17 files across `panel_framework` and `educator_interface`.
- Guard added: `freedom_ls/panel_framework/tests/invariants/test_templates.py` lines 643-660. `FORBIDDEN_IN_DIALOGS` includes `"<c-callout>": re.compile(r"<c-callout\b")` and `"a bg-error/10 box"`. `test_no_dialog_template_hand_writes_what_a_component_owns` scans only `DIALOG_BODIES`, not all app templates. The panel-framework skill (`claude_plugins/fls-dev/skills/panel-framework/SKILL.md:213-215, 327`) states the rule: "never `<c-callout>` or a hand-built `bg-error/10` box".
- What this means for the spec:
  - A theme-fit page alert is a second widget next to `c-panel-notice`. The two will overlap unless the spec says how: compact versus page-level, or a shared base.
  - The test guard covers dialogs only. Learner, application and form pages are unguarded, which is how `c-callout` spread.
  - `c-callout` still lives in `base` and is still described as the page callout in `visual.md`, so skill text and tests disagree.

## 3. Tests that exist around callout and admonition

- `freedom_ls/base/tests/components/test_callout_component.py`: tests text colours and class passthrough. It will be deleted or replaced.
- `freedom_ls/markdown_rendering/tests/test_markdown_utils.py` lines 60-96 and 694-708: assert that `<c-callout>` in markdown is stripped by nh3 and the body survives. Keep these: they guard the content side if the component is deleted. Check they do not need the component to exist.
- `freedom_ls/content_engine/tests/templatetags/test_content_tags.py` (42 hits) and `content_engine/tests/test_checks.py`: cover `c-admonition` config. No test stops `c-admonition`, `c-flashcard`, `c-accordion` or `c-table` being used in app templates (no template does today).
- `freedom_ls/base/tests/invariants/test_stylesheet_boundary.py` is the closest model for the requested invariant. It parametrizes (selector, owner) pairs, and uses `pytestmark = pytest.mark.fls_internal`. The panel-framework template invariants use regex scans over template files in the same way.
- Feature tests assert on the callouts' presence by `data-testid` or text, for example `accounts/tests/test_views.py:292-380`, `learner_interface/tests/views/test_course_paused.py:284-303` (`data-testid="course-paused-callout"`), and `educator_interface/tests/test_views.py:8142`. A replacement should preserve these hooks. `test_course_player.py:4462` ("the closed notice is not a callout") shows an earlier "no callout here" decision.

## 4. Feedback and rules captured

- No `capture-feedback` rule file about callouts or alerts was found in `claude_plugins/fls-dev/resources/`; the only `callout` hits there are the review-output header `callout: Structure concern`, an unrelated meaning.
- `docs/product/learner-experience.md:212` describes the application form's "Invalid answers" callout in a screenshot caption. This is user-facing doc that will need a wording check.
- `spec_dd/1. next/extract_panels_framework-4-template-contract/idea.md` lines 26 and 142 list `c-callout` among the base components the extracted panel framework would depend on. Deleting it touches that planned spec; `roadmap.md` has related `admonition` mentions.
- `spec_dd/3. done/2026-11-15_13:44_deadlines-3-extensions-and-pause/research_ux_patterns.md:33` says new states "must reuse the existing parts (chip, callout, eyebrow) and will inherit whatever that restyle does". Authors reuse the nearest component and expect a later restyle, which is the failure mode described in the idea.

## 5. Elsewhere (brief)

- Docusaurus separates the markdown admonition (`:::note`, styled by Infima, with custom types mapped via a swizzled `Admonition/Types`) from UI components. Bootstrap's `.alert` is a UI feedback component with fixed variants. Bridges exist, such as a Markdig extension that maps admonitions onto Bootstrap alert classes. This worker found no source that states the split as a guarded rule, or that describes a test enforcing it; that part is my own reading.
- URLs: https://github.com/facebook/docusaurus/issues/9307 , https://lightrun.com/answers/facebook-docusaurus-gfm-like-admonitionscallouts , https://www-1.nuget.org/packages/MarkdigExtensions.Bootstrap.Admonitions , https://help.splunk.com/en/splunk-style-guide/admonitions-and-text-callouts

## 6. Takeaways for the spec

1. Reuse the `c-panel-notice` lesson. The earlier split relied on prose plus a dialog-only regex test, and it still leaked. The invariant must scan every non-content template.
2. Decide the relation to `c-panel-notice`. `c-panel-notice` has a smaller scale and a different base, so this spec needs to say whether the new alert shares tokens, tones and ARIA roles with it.
3. Reuse its tones and ARIA mapping: tones info, warning, error and success, with `role="alert"` for error and `role="status"` for success, plus an icon via `c-icon`. Static only, per answers.
4. Update `visual.md` lines 84-86, 134 and 163, the panel-framework skill, `docs/how tos/landing-pages.md:18` and the product docs. Fix the wrong glossary line ("`c-callout` stays the course-content component"). Write upgrade notes covering the First Class `lp/step.html` migration.
5. Keep the markdown-stripping tests for `c-callout`. They guard the content side once the component is gone.

status: ok
