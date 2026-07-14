# Cleanup terrible allauth customisations made when implementing `home` feature

The `home` feature (`spec_dd/3. done/2026-07-01_19:44_home_page`) bolted custom
`next`-threading onto the allauth / registration machinery so that a not-yet-logged-in
visitor clicking a course CTA would be carried back to their exact destination through the
forced signup + registration-completion flow. It caused a spaghetti-mess and bugs that are
hard to fix without piling on more spaghetti.

**Undo those `next`-threading changes. Let allauth work in standard, vanilla ways.** We do
not need anything fancy. If a user clicks a CTA, send them to whatever link the CTA points
at; if login is required (it is), vanilla `@login_required` + allauth already handle the
redirect perfectly well without the custom machinery.

## Hard constraints (do not violate)

- **Only revert the ALLAUTH `next`-threading added by the `home` spec.** Introduce no new
  functionality — only remove.
- **Keep the earlier "better authentication" / "better registration" changes** (commit
  `9077da89` era). Those worked great, added no spaghetti, and the vanilla behaviour we are
  restoring relies on them.
- **Ignore the other in-progress bugfix worktree/spec entirely.** It tries to fix the bugs
  by layering more trash on the trash. Do not read it, base anything on it, or fix bugs it
  surfaced. Out of scope, full stop.

## Scope (git-verified against the `home` commits)

The `home` feature's *entire* auth/allauth footprint is **two files, one change each** —
confirmed by diffing the two owning commits (`a47921bc`, `9dc71a32`) against their parents,
corroborated by the home spec's own plan + QA report and the test suite:

1. **`freedom_ls/accounts/middleware.py`** — `RegistrationCompletionMiddleware.__call__`
   (commit `a47921bc`, "Phase 5: deferred login preserves intent").
   Added a `next`-preservation block that reads/validates `?next=`, falls back to
   `request.path`, and redirects to `complete_registration?next=<quoted>`.
   → **Revert:** restore the single line
   `return redirect(reverse("accounts:complete_registration"))` and drop the now-unused
   `quote` / `url_has_allowed_host_and_scheme` imports.

2. **`freedom_ls/base/templates/partials/login_prompt.html`** (commit `9dc71a32`,
   "Phase 2: anonymous home page variant").
   → **Revert:** strip only `?next={{ request.path|urlencode }}` from both `<c-button>`
   `href`s. **Do NOT** revert the rest of that file. The same commit also restyled the
   wrapper (`mt-8 justify-center` → `flex items-center gap-2`) so the prompt fits the header
   bar — that styling belongs to the anonymous-header affordance (see below), which we keep.

### Explicitly OUT of scope — leave untouched

- **`header_bar.html`** rendering `login_prompt.html` for anonymous users — that is the
  "public browsing" header affordance, not `next`-threading. Keep it (and its styling).
- **`initiate_course_access` / `apply`** views — already plain vanilla `@login_required`;
  Django builds `?next=` automatically. Nothing custom to remove.
- **`_safe_post_completion_redirect`, `complete_registration_view`, its template's hidden
  `next` field, the allauth account adapter, `account/*` template overrides, and all
  `ACCOUNT_*` / `LOGIN_*` settings** — all pre-date the `home` feature ("better
  registration") or are stock allauth/Django. After reverting (1), the completion view
  simply never receives a `next` from the middleware and its existing guard falls back to
  `LOGIN_REDIRECT_URL` — exactly the vanilla behaviour we want.

## Tests to clean up (details for the plan phase)

Reverting removes behaviour that a handful of tests assert on. The plan should:

- **Delete** the tests that assert the removed middleware `next`-forwarding
  (`test_deferred_login.py`) and the removed `login_prompt` `?next=` markup
  (`test_anonymous_home_page.py`: `..._login_link_carries_next`,
  `..._link_carries_deeper_path`).
- **Update** `test_registration_completion_middleware.py` to drop the `next=`-in-URL
  assertions while keeping the redirect-to-completion assertions.
- **Keep** tests covering vanilla `@login_required` redirects, the pre-existing
  registration/completion `next` handling, and public-browsing behaviour — those describe
  behaviour that survives the revert.
- Some tests in the whole-cloth `test_deferred_login.py` cover vanilla/pre-existing
  behaviour and are worth preserving rather than deleting with the file — the plan decides
  keep-vs-delete per test.

## Expected outcome

Two small surgical reverts + targeted test cleanup. Vanilla allauth handles login-required
redirects; the header still shows working (un-parameterised) Login/Sign-up links for
anonymous visitors; no custom `next`-threading anywhere. No new functionality.
