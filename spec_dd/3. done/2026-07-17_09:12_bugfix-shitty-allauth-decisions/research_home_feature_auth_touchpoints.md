# Research: home-feature auth/allauth touchpoints (for surgical revert)

## Tooling caveat — read this first

This worker has **no shell/`Bash` tool** in this environment (only `Read`, `Grep`, `Glob`,
`Write`, `WebFetch`, `WebSearch`). I could not run `git log`, `git show`, or `git blame`
against the named commits (`bf41d7fc 845cd79a e0b5b8c9 9dc71a32 8baac57d a47921bc 608008d4`)
to independently re-derive diffs. Everything below is therefore reconstructed from:

1. The **current working-tree code** (`Read`/`Grep` on `main`).
2. `spec_dd/3. done/2026-07-01_19:44_home_page/2. plan.md` and `1. spec.md` — the
   implementation plan, which was written and re-verified against the code *before*
   implementation and quotes the pre-change line(s) verbatim for both touchpoints below
   (this is why the "vanilla" reconstruction is high-confidence even without `git show`).
3. `spec_dd/3. done/2026-07-01_19:44_home_page/qa_report.md` — confirms exactly these two
   surfaces (and no others) were the QA'd deferred-login behaviour.
4. The two named commits from the prompt (`9dc71a32` for `login_prompt.html`, `a47921bc`
   for `middleware.py`) are taken as given per the task's "already-known facts" — I did not
   independently verify the hash↔file mapping via `git show <hash>`.

If exact commit diffs are required before the revert lands, re-run this research with a
worker that has `Bash` access to execute the `git show`/`git log -p` commands the task
description asked for. The findings below should still be sufficient to scope the revert:
the auth-machinery footprint is genuinely two files, corroborated by three independent
sources (code, plan, QA report) plus test assertions (below).

---

## 1. Confirmed inventory of home-feature auth/allauth touchpoints

### 1.1 `freedom_ls/accounts/middleware.py` — `RegistrationCompletionMiddleware.__call__`

- **Current lines:** 118–134 (the `next`-preservation block + `redirect(target)`), plus the
  now-required imports `from urllib.parse import quote` (line 23) and
  `from django.utils.http import url_has_allowed_host_and_scheme` (line 30).
- **Commit:** `a47921bc` (Phase 5.2, "deferred login preserves intent").
- **What it does now:** reads `request.GET.get("next")`; validates it with
  `url_has_allowed_host_and_scheme(candidate, allowed_hosts={request.get_host()},
  require_https=request.is_secure())`; falls back to `request.path` if absent/invalid;
  builds `target = f"{reverse('accounts:complete_registration')}?next={quote(candidate)}"`;
  redirects there instead of a bare redirect to the completion view.
- **Pre-home ("vanilla") state**, per plan.md §5.2 (which quotes the old call site
  verbatim as the diff's "before"):
  ```python
  return redirect(reverse("accounts:complete_registration"))
  ```
  i.e. no `next` was carried at all — a user forced into `complete_registration` lost
  whatever page/action they were trying to reach and landed on the completion form with
  no memory of where to go after.
- **Revert action:** delete the `next`-preservation block (current lines ~118–133) and
  restore the single-line `return redirect(reverse("accounts:complete_registration"))`.
  Remove the now-unused `quote` and `url_has_allowed_host_and_scheme` imports if nothing
  else in the file needs them (grep confirms these two imports are used **only** in this
  block: `quote` appears once, `url_has_allowed_host_and_scheme` appears once, both inside
  `__call__`).
  The docstring at the top of the file (lines 1–15) does not reference `next` and needs no
  change.

### 1.2 `freedom_ls/base/templates/partials/login_prompt.html`

- **Current content (verified via `Read`, 12 lines):**
  ```django
  {% url 'account_login' as login_url %}
  <div class="flex items-center gap-2">
      <c-button href="{{ login_url }}?next={{ request.path|urlencode }}">
          Login
      </c-button>
      {% if allow_signups %}
          {% url 'account_signup' as signup_url %}
          <c-button href="{{ signup_url }}?next={{ request.path|urlencode }}">
              Sign up
          </c-button>
      {% endif %}
  </div>
  ```
- **Commit:** `9dc71a32` (Phase 2.3, "header auth affordance").
- **Pre-home state**, per plan.md §2.3 (the plan explicitly frames this as adding the
  `?next=` querystring to buttons that previously had none — the "Update it to append the
  current path" instruction, with the before/after both shown):
  ```django
  {% url 'account_login' as login_url %}
  <c-button href="{{ login_url }}">Login</c-button>
  {% if allow_signups %}
    {% url 'account_signup' as signup_url %}
    <c-button href="{{ signup_url }}">Sign up</c-button>
  {% endif %}
  ```
  (Exact original wrapper markup — e.g. the `<div class="flex items-center gap-2">` vs. the
  plan's illustrative `mt-8 flex justify-center` block mentioned in passing — should be spot
  checked against `git show 9dc71a32~1:freedom_ls/base/templates/partials/login_prompt.html`
  when `Bash` is available, but the **substantive** pre-state — no `?next=` param on either
  button — is corroborated by both the plan text and by the fact that `login_prompt.html`
  already existed and was referenced by two earlier, unrelated specs
  (`spec_dd/3. done/2026-05-05_17:24_layout-spacing-cleanup/2. plan.md` and
  `spec_dd/1. next/system_qa/research_repo_surface.md`) — i.e. this partial predates the
  home feature; only the `?next=` addition is home-feature-owned.)
- **Revert action:** drop `?next={{ request.path|urlencode }}` from both `href` attributes,
  restoring plain `href="{{ login_url }}"` / `href="{{ signup_url }}"`.

### 1.3 `freedom_ls/base/templates/partials/header_bar.html` — context only, NOT itself an auth-machinery change

- **Current lines 18–24:**
  ```django
  <nav class="flex-shrink-0 ml-2 sm:ml-4">
      {% if user.is_authenticated %}
          {% include "partials/header_bar_user_menu.html" %}
      {% else %}
          {% include "partials/login_prompt.html" %}
      {% endif %}
  </nav>
  ```
- **Commit:** `9dc71a32` (same commit as 1.2, Phase 2.3).
- This is the "public browsing" template change that makes `login_prompt.html` render at
  all for anonymous users (previously the `<nav>` rendered nothing when logged out). It is
  **out of scope** for this revert per the task's framing — the header login/signup
  affordance for anonymous visitors is part of the "public views" feature, not the
  "deferred-login `next`-threading" mess. **Do not revert this** unless the cleanup is
  explicitly widened beyond auth machinery; noted here only so the blast radius of 1.2 is
  understood (i.e. reverting `login_prompt.html`'s `?next=` still leaves anonymous users
  with working, un-parameterised Login/Sign up links in the header — vanilla allauth then
  bounces them through its own `?next=` generation only when they hit a `@login_required`
  view, exactly per §1.4 below).

### 1.4 `initiate_course_access` / `apply` — confirmed NOT modified (vanilla `@login_required`)

- `freedom_ls/student_interface/views.py:455-456` (`initiate_course_access`) and
  `freedom_ls/course_applications/views.py:19-20` (`apply`) both remain plain
  `@login_required` with no custom `next=` construction anywhere in either view (grepped
  both files for `login_required|next=` — no hits inside the view bodies beyond the
  decorator itself).
- Per plan.md §5.1: *"The committing-action targets (`initiate_course_access`, `apply`)
  stay `@login_required`. The detail-page CTA links straight at them; Django's
  `@login_required` builds `?next=<that-url>` automatically for anonymous clicks... most of
  this phase is verification + one middleware fix"* — i.e. this is **vanilla Django/allauth
  behaviour already**, not custom code. Nothing to revert here.

### 1.5 Settings (`config/settings_base.py`) — confirmed NOT touched for auth/next by the home feature

- Grepped `LOGIN_URL|LOGIN_REDIRECT_URL|ACCOUNT_*|REDIRECT_FIELD_NAME` (lines 332–382).
  `LOGIN_REDIRECT_URL = "/"` (line 382) and the `ACCOUNT_*` block (lines 333–352) are
  standard allauth config with no `next`/redirect-flow customisation, and nothing in the
  spec/plan (Phase 6 SEO settings changes are `INSTALLED_APPS += django.contrib.sitemaps`,
  unrelated to auth) touches this block. No settings revert needed.
  *(Not independently verified via `git log -p` on the phase commits — see tooling caveat —
  but the plan's Phase list has no settings-auth line item, and the content reads as
  pre-existing/unrelated.)*

### 1.6 URLconf (`config/urls.py`) — confirmed NOT touched

- `path("accounts/", include("allauth.urls"))` (line 68) is the sole allauth URL wiring;
  no project-level override of `account_login`/`account_signup` URL names. No revert needed.

### 1.7 `account/*` template overrides — confirmed NOT touched by the home feature

- `freedom_ls/base/templates/account/signup.html` is the **only** project override of an
  allauth `account/` template (besides transactional-email templates under
  `accounts/templates/account/email/`, which are unrelated to login/signup flow). It already
  emits `{{ redirect_field }}` (line 71) — plan.md §5.1 explicitly says this was
  **"confirmed present"**, i.e. verified as pre-existing, not added by the home feature.
- `allauth/templates/account/login.html` (vendored, inside `.venv`) is unmodified — the
  plan also confirms this ("confirmed present").
- No `account/login.html` override exists in the project at all (grepped
  `freedom_ls/*/templates/account/**` — only `signup.html` and the `email/` subtree).
- **Conclusion:** nothing to revert in allauth template overrides.

### 1.8 `freedom_ls/accounts/views.py` (`_safe_post_completion_redirect`,
`complete_registration_view`) and `freedom_ls/accounts/templates/accounts/complete_registration.html`
— confirmed PRE-EXISTING, not home-feature-owned

- `_safe_post_completion_redirect` (lines 60–68) reads `request.POST.get("next") or
  request.GET.get("next")`, validates with `url_has_allowed_host_and_scheme`, falls back to
  `settings.LOGIN_REDIRECT_URL`.
- `complete_registration_view` (lines 76–113) already reads/re-renders `next` (line 107,
  passed to the template as `"next": next_value`).
- `accounts/templates/accounts/complete_registration.html` already emits
  `<input type="hidden" name="next" value="{{ next }}">` (lines 16–18) inside the form.
- All three are attributed by the task's "already-known facts" to the earlier **"better
  registration"** feature (commit `9077da89`), and plan.md §5.2 corroborates this by
  describing them as already-existing machinery that the middleware fix (1.1) merely needed
  to *feed* correctly ("The `complete_registration` view already reads and re-emits `next`
  ... but the value never reaches them because the middleware drops it on the forced
  redirect"). **Out of scope for this revert** — these stay untouched; reverting 1.1 alone
  simply means `next` is never populated on entry to `complete_registration_view`
  (`next_value` will be `""` whenever the middleware is the referrer), and the pre-existing
  `_safe_post_completion_redirect` gracefully falls back to `LOGIN_REDIRECT_URL` in that
  case — exactly the vanilla behaviour being restored.

### 1.9 `freedom_ls/accounts/allauth_account_adapter.py` (`AccountAdapter`) — confirmed no redirect customisation

- Read in full (189 lines). Contains `send_mail`, `save_user` (webhook firing),
  `send_notification_mail`, `is_open_for_signup` (per-site signup policy). No override of
  `get_login_redirect_url`, `get_signup_redirect_url`, or any `next`-related allauth adapter
  hook. Confirms the prompt's already-known fact. Nothing to revert.

---

## 2. Test impact map

| Test file | Test(s) | Ties to reverted behaviour | Disposition on full revert |
|---|---|---|---|
| `freedom_ls/accounts/tests/test_deferred_login.py` (326 lines, new file added whole-cloth by `a47921bc`) | `test_middleware_preserves_next_from_get_param` | Directly asserts the middleware's `?next=` forwarding (1.1) | **DELETE** — tests the exact code block being removed |
| same | `test_middleware_falls_back_to_request_path_when_no_next_param` | Directly asserts middleware's `request.path` fallback (1.1) | **DELETE** |
| same | `test_middleware_rejects_off_host_next_and_falls_back_to_path` | Directly asserts middleware's open-redirect guard (1.1) | **DELETE** |
| same | `test_next_survives_complete_registration_step` | Asserts the **full chain** incl. middleware forwarding; the `complete_registration_view`/`_safe_post_completion_redirect` half (1.8) stays, but this test's setup narrative simulates the middleware forwarding `next` | **DELETE or rewrite** — as written it validates the now-removed middleware behaviour end-to-end; if a chain test is wanted post-revert it would need to be rebuilt around vanilla behaviour (no `next` reaching `complete_registration` via the middleware) |
| same | `test_unsafe_next_in_complete_registration_falls_back_to_login_redirect` | Tests `complete_registration_view`'s own POST-time `next` validation (pre-existing, 1.8) — **not** middleware-owned | **KEEP** (belongs to pre-existing "better registration" behaviour, not the home-feature mess) |
| same | `test_anonymous_access_to_initiate_redirects_to_login_with_next` | Tests vanilla `@login_required` redirect (1.4) — not custom code | **KEEP** |
| same | `test_deferred_login_free_course_enrolls_and_redirects` | Tests `initiate_course_access` idempotent enrol behaviour (not next-threading-specific; uses `logged_in_client`, doesn't exercise the middleware/login_prompt) | **KEEP** |
| same | `test_anonymous_access_to_apply_redirects_to_login_with_next` | Tests vanilla `@login_required` redirect (1.4) | **KEEP** |
| same | `test_deferred_login_gated_course_lands_on_apply_page` | Tests `apply` GET confirmation page behaviour, unrelated to next-threading specifics | **KEEP** |
| same | `test_complete_registration_get_with_safe_next_renders_hidden_field` | Tests pre-existing `complete_registration_view`/template `next` re-emission (1.8) | **KEEP** |
| `freedom_ls/accounts/tests/test_registration_completion_middleware.py` (modified by `a47921bc`; file itself pre-existing) | `test_user_with_incomplete_forms_redirected_to_completion` | Asserts `f"next={profile_url}" in response.url` (line 72) — the middleware's fallback-to-`request.path` behaviour (1.1) | **UPDATE** — drop the `next=` assertion, keep the `response.status_code == 302` / `response.url.startswith(completion_url)` assertions (those describe vanilla redirect-to-completion behaviour that survives the revert) |
| same | `test_settings_default_drives_forms_when_no_policy` | Same `f"next={profile_url}" in response.url` assertion (line 89) | **UPDATE** — same as above |
| same | `test_substring_match_does_not_exempt` | Comment says "with next= preserved" but the actual assertion (lines 201–203) only checks `status_code == 302` and `response.url.startswith(completion_url)` — no literal `next=` assertion | **KEEP as-is** (just stale comment, optionally reword "with next= preserved" → drop that clause) |
| all other tests in this file (`test_anonymous_request_passes_through`, `test_superuser_passes_through_...`, `test_user_with_no_incomplete_forms_passes_through`, `test_policy_overrides_settings...`, `test_allauth_exempt_url_names_pass_through`, `test_legal_doc_url_is_exempt`, `test_completion_view_url_is_exempt`, `test_health_path_exempt`, `test_cache_short_circuits_second_request`, `test_changing_dotted_paths_invalidates_cache`, `test_completion_submit_clears_cache`) | — | Test the exempt-list / caching machinery, unrelated to `next` | **KEEP unchanged** |
| `freedom_ls/student_interface/tests/test_anonymous_home_page.py` (new file, home feature) | `test_anonymous_dashboard_login_link_carries_next` (line 97) | Directly asserts `login_prompt.html`'s `?next=` on the Login link (1.2) | **DELETE** — tests the exact markup being reverted |
| same | `test_anonymous_login_link_carries_deeper_path` (line 109) | Same, against `/courses/` instead of `/` (1.2) | **DELETE** |
| same | `test_anonymous_dashboard_shows_login_link` (line 86) | Only asserts the Login link/text is present, no `next=` assertion | **KEEP** — untouched by the revert (header still shows Login for anon users per 1.3, out of scope) |
| same | `test_anonymous_dashboard_shows_signup_when_allowed` (line 124, and presumably more below the read window) | Only asserts "Sign up" text presence | **KEEP** (verify the full remainder of the file, not fully read here, for any other `next=` assertions before executing the revert) |
| all other tests in this file (hero headline, browse-all CTA, hidden sections, no-placeholder, no `get_dashboard_contributions` call, authenticated-unchanged) | — | Public-browsing behaviour, not auth machinery | **KEEP**, out of scope |

Note: `test_anonymous_home_page.py` was only read through line 130; re-grep/re-read the full
file before the revert PR to confirm no further `next=`/`login_prompt` assertions exist below
that point.

---

## 3. Blast-radius summary table

| File | Lines (current) | Commit | Revert action | Tests affected |
|---|---|---|---|---|
| `freedom_ls/accounts/middleware.py` | ~23, 30, 118–134 | `a47921bc` | Restore `return redirect(reverse("accounts:complete_registration"))`; drop `quote` / `url_has_allowed_host_and_scheme` imports (verify unused elsewhere first) | 3 DELETE + 1 DELETE-or-rewrite in `test_deferred_login.py`; 2 UPDATE (+1 stale-comment) in `test_registration_completion_middleware.py` |
| `freedom_ls/base/templates/partials/login_prompt.html` | 3, 8 | `9dc71a32` | Drop `?next={{ request.path|urlencode }}` from both `<c-button href>` attrs | 2 DELETE in `test_anonymous_home_page.py` |
| `freedom_ls/base/templates/partials/header_bar.html` | 18–24 | `9dc71a32` | **No action** — out of scope (public-browsing header affordance, not next-threading) | none (its own tests, e.g. `test_anonymous_dashboard_shows_login_link`, are unaffected by the revert) |
| `freedom_ls/student_interface/views.py` (`initiate_course_access`), `freedom_ls/course_applications/views.py` (`apply`) | n/a | n/a (unchanged by home feature) | **No action** — vanilla `@login_required` already | `test_anonymous_access_to_initiate_redirects_to_login_with_next`, `test_anonymous_access_to_apply_redirects_to_login_with_next` stay as-is (they test Django/allauth stock behaviour) |
| `config/settings_base.py`, `config/urls.py`, `account/*` templates, `allauth_account_adapter.py`, `accounts/views.py` (`_safe_post_completion_redirect`, `complete_registration_view`), `accounts/templates/accounts/complete_registration.html` | n/a | n/a (pre-existing / untouched by home feature) | **No action** | n/a |

**Bottom line:** the home feature's authentication/allauth footprint is exactly as small as
the preliminary dig suggested — **two files, one behavioural block each**: the
`next`-preservation branch added to `RegistrationCompletionMiddleware.__call__`
(`middleware.py`, commit `a47921bc`) and the `?next=` querystring appended to the two
`<c-button href>` links in `login_prompt.html` (commit `9dc71a32`). Everything else that
*looks* next/redirect-related in this codebase — `_safe_post_completion_redirect`, the
`complete_registration` view/template's `next` handling, allauth's own `@login_required` →
`?next=` generation on `initiate_course_access`/`apply`, the account templates, the adapter,
and all `ACCOUNT_*`/`LOGIN_*` settings — predates the home feature or is vanilla
allauth/Django behaviour untouched by it. A revert is a two-file surgical patch (restore one
line in the middleware, strip a query param in one template) plus deleting/updating the
handful of tests in the table above that specifically assert on the removed `next`-threading;
no other view, backend, setting, URL route, or allauth template requires changes.

status: ok
