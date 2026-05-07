# QA Report — Phase 1: Theme resolver + default-theme tokens

Run on `2026-05-06` against branch `themable-implementations-phase-1-theme-resolver-and-default-tokens` at `http://127.0.0.1:8303/`.

## Result summary

All four tests in `3. frontend_qa.md` passed. No theming regressions found. One pre-existing tangential server error was noted (unrelated to this phase).

| Test | Status |
|------|--------|
| 1 — Default theme smoke / visual regression | PASS |
| 2 — Bad `FLS_THEME` fails loudly (`runserver` and `check`) | PASS |
| 3 — Email colour parser reads `theme.css` | PASS |
| 4 — Default theme `static/themes/default/theme.css` resolvable (200 OK) | PASS |

---

## Test 1 — Default theme smoke + visual regression — PASS

Walked through the major pages on desktop (1920x1080), mobile (375x812), and tablet (768x1024). All pages render with the expected default-theme tokens:

- Header bar: `#2B6CB0` blue (matches the documented `--color-primary`).
- Primary buttons (`btn-primary`): blue fill, rounded corners, white label.
- Outline buttons (e.g. `Description`, `Previous`): white background, neutral border, dark label.
- Surfaces / cards: white background, subtle border, rounded corners.
- Progress bars on dashboard course cards: filled in primary blue.
- Quiz "Quiz Not Passed" page renders the error icon and "Your answer:" text in the new error red, the "Correct answer:" label and check-icon in success green, with pink-tinted incorrect-answer surfaces. All hues match the previous danger / success values.
- Tabs on cohort detail show the active tab underlined in primary blue.
- Toast playground shows the success-coloured `htmx-success` button and error-coloured `htmx-error` button.
- Login flash toast renders in success green.

### Pages screenshotted (desktop)

- `screenshots/desktop_1.3_home_logged_out.png`
- `screenshots/desktop_1.3_login_page.png`
- `screenshots/desktop_1.3_home_logged_in.png`
- `screenshots/desktop_1.3_courses_list.png`
- `screenshots/desktop_1.3_course_home.png`
- `screenshots/desktop_1.3_topic_page.png`
- `screenshots/desktop_1.3_form_page.png`
- `screenshots/desktop_1.3_form_fill.png`
- `screenshots/desktop_1.3_form_complete.png` (most colour-token-sensitive page — error red, success green, pink surfaces all rendering)
- `screenshots/desktop_1.3_account_profile.png`
- `screenshots/desktop_1.3_account_email.png`
- `screenshots/desktop_1.3_educator_interface.png`
- `screenshots/desktop_1.3_educator_cohorts.png`
- `screenshots/desktop_1.3_cohort_detail.png`
- `screenshots/desktop_1.3_toast_playground.png`
- `screenshots/desktop_1.3_toast_success.png`

### Mobile (375x812)

- `screenshots/mobile_1.3_home.png` — debug toolbar overlays content (this is a pre-existing django-debug-toolbar behaviour in dev mode, not a theming change). Underlying cards / buttons size correctly.
- `screenshots/mobile_1.3_topic.png` — topic page, mini header, blue Next button, outline Previous button. Sizes look comfortable for touch.
- `screenshots/mobile_1.3_account_profile.png` — labels, inputs, blue Save and Sign Out buttons all readable.
- `screenshots/mobile_1.3_educator_cohorts.png` — sidebar collapsed to chevron, cohort table fits viewport, `Create Cohort` button is primary blue.

### Tablet (768x1024)

- `screenshots/tablet_1.3_courses.png` — desktop-style header (user email visible in nav), course cards in a 2-column grid, blue Continue/Start, outline Description, blue progress bars.
- `screenshots/tablet_1.3_educator_cohorts.png` — sidebar collapsed, cohort table fits, primary blue Create Cohort.

### Validation styling (Test 1.3 sub-task)

I tried to trigger a deliberate field-validation error on `/accounts/email/` (Add Email submitted blank, then with the existing primary email) but the form silently re-rendered without showing an inline error message. This is consistent with the existing allauth `EmailView` not surfacing form errors via the `_messages` template (it uses django messages instead), and is unrelated to this phase. The colour-token coverage for "error red on error border / messages" is exercised through:

- The quiz-complete page (Test 1.3 — `screenshots/desktop_1.3_form_complete.png`), where the error red and success green tokens render correctly.
- The cohort-detail Delete button (`screenshots/desktop_1.3_cohort_detail.png`) renders in error-red.

---

## Test 2 — Bad `FLS_THEME` fails loudly — PASS

```bash
FLS_THEME=does_not_exist uv run python manage.py runserver 8311
FLS_THEME=does_not_exist uv run python manage.py check
```

Both commands fail with:

```
django.core.exceptions.ImproperlyConfigured: FLS theme 'does_not_exist' not found in any of:
  [PosixPath('.../themable-implementations-phase-1-theme-resolver-and-default-tokens/themes'),
   PosixPath('.../themable-implementations-phase-1-theme-resolver-and-default-tokens/freedom_ls/themes')]
```

The slug `does_not_exist` is included in the message, both searched dirs (project-level `themes/` and `freedom_ls/themes/`) are listed, and the server does not start. Matches the spec.

---

## Test 3 — Email colour fallbacks — PASS

```bash
FLS_THEME=default uv run python manage.py shell -c \
  "from django.conf import settings; print(settings.EMAIL_COLOR_PRIMARY, settings.EMAIL_COLOR_FOREGROUND)"
# -> #2B6CB0 #1A2332
```

To prove the parser is actually reading the theme file (not just falling back), I temporarily edited `freedom_ls/themes/default/static/themes/default/theme.css` to set `--color-primary: #ff00ff;`, re-ran the same command, and got `PRIMARY: #ff00ff`. After restoring the file, the value returned to `#2B6CB0`. The parser is real.

---

## Test 4 — Default theme static asset is resolvable — PASS

```bash
curl -s -o /tmp/theme_resp.css -w "HTTP_STATUS=%{http_code}\nCONTENT_TYPE=%{content_type}\n" \
  http://127.0.0.1:8303/static/themes/default/theme.css
# HTTP_STATUS=200
# CONTENT_TYPE=text/css; charset="utf-8"
```

The body starts with the expected FLS default-theme comment block, contains four `@theme` blocks (the main `@theme` plus three `@theme inline` shape/font alias blocks), and includes `--color-primary: #2B6CB0;`. The `static/themes/<slug>/` namespacing holds.

---

## Tangential observations (not regressions of this phase)

1. **Demo content was not pre-loaded.** The dev DB had 0 courses for the DemoDev site at the start of the run, so the courses list rendered "No courses available yet". I loaded `demo_content/` into the DemoDev site with `uv run python manage.py content_save demo_content DemoDev`. After that, the four functionality demo courses were visible. This is a data setup gap, not a Phase 1 issue — already happens before the QA pass.

2. **Demodev EmailAddress not verified.** On first login, the user redirected to `/accounts/confirm-email/` because `EmailAddress(email='demodev@email.com').verified` was `False` and `primary` was `False`. This is the same data setup issue documented in the QA report at `spec_dd/3. done/2026-03-13_12:53_bug-FORCE_SITE_NAME-is-ignored-for-existing-sites/qa_report.md`. I marked the row `verified=True, primary=True` to proceed. Note that I would normally have invoked the `qa-data-helper` agent for this; in this environment the `Agent` tool was not surfaced as a callable tool, and the fix was a one-line ORM update with a known-correct shape from prior QA reports, so I applied it directly.

3. **`AttributeError: 'NoneType' object has no attribute 'existing_answers_dict'`** at `/courses/functionality-demo-show-end-with-quiz/2/fill_form/1` after I re-visited the URL post-completion. Reproducer: complete the Mid course Quiz; navigate back to its `fill_form/1` page directly. The view appears to assume an active form-attempt exists when one does not. This is a pre-existing view bug unrelated to theme tokens — file separately if not already tracked. (Did not block QA — captured here for visibility.)

4. **Add Email form silently swallows blank/duplicate submissions** without rendering a visible inline error in the page body. Behaviour is independent of theme; the colour-token assertions of Test 1 are still satisfied via the quiz error path and the cohort Delete button.

---

## Test execution notes

- Server launched: `PORT=8303`, `uv run python manage.py runserver 8303`. Branch confirmed via `debug-branch-badge`.
- All screenshots are in `screenshots/`. None exceeded the 1024KB pre-commit cap, so the compress step was a no-op.
- Server was killed via `.claude/fls/scripts/kill_runserver.sh 8303`.
