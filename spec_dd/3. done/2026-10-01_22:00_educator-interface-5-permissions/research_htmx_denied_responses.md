# Research: htmx denied responses (403/404) for the educator interface

Scope: how htmx 2.x handles non-2xx swaps, what this repo already does with
403/404 in the panel framework and error-page templates, and where the 403
fragment described in `idea.md`'s "denied experience" should render for each
surface. Read alongside `research_permission_ux_patterns.md` (general UX
principles, not repeated here) and the roadmap.

## 1. How htmx 2 treats 403/404 by default

htmx's default `responseHandling` table
(https://htmx.org/docs/#response-handling):

```js
htmx.config.responseHandling = [
    {code:"204", swap: false},
    {code:"[23]..", swap: true},
    {code:"[45]..", swap: false, error: true},
    {code:"...", swap: false},
]
```

Any `4xx`/`5xx` — which is what a plain 403 or 404 is — matches `[45]..`:
`shouldSwap` is `false` and `isError` is `true`. htmx fires
`htmx:responseError` and leaves the DOM untouched; nothing the server sent is
rendered anywhere. This is not 422-specific behaviour to work around — it is
the default for the whole 4xx/5xx range, 403 and 404 included.

Four ways to change this, from narrowest to broadest:

1. **`HX-Retarget`/`HX-Reswap` response headers.** The server names a CSS
   selector (`HX-Retarget`) and/or a swap strategy (`HX-Reswap`) on the
   response itself. These headers are read inside htmx's own `beforeSwap`
   handling and win over the request's `hx-target`/`hx-swap`, but they do
   **not** change `shouldSwap` — a 403 with `HX-Retarget` set still will not
   swap unless something else also flips `shouldSwap` to `true`. They answer
   "where", not "whether".
   (https://htmx.org/reference/#response_headers)
2. **A project `htmx:beforeSwap` listener.** Inspect `evt.detail.xhr.status`
   (or response body) and set `evt.detail.shouldSwap = true` /
   `evt.detail.isError = false` for the cases you want to render. This is
   exactly what this repo already does for 422 and for OOB toast fragments
   (see §2) — it is the established local pattern, not a new one.
   (https://htmx.org/events/#htmx:beforeSwap)
3. **`htmx.config.responseHandling` entries.** Add a rule (e.g.
   `{code:"403", swap: true}`) globally instead of a listener. Equivalent to
   (2) but declarative and applies to every request; a `beforeSwap` listener
   is finer-grained (can inspect body/target) and is what this repo already
   has, so extending it is less churn than introducing a second mechanism.
4. **The `response-targets` extension** (`hx-target-error`, `hx-target-4xx`,
   `hx-target-40*`, per-code `hx-target-404`, etc.). Declared as an
   attribute, not global config. Its handler explicitly sets
   `evt.detail.shouldSwap = true` when a match is found — the extension
   itself does the "flip shouldSwap" job that a bare `HX-Retarget` header
   cannot do alone. This is the only option that reads as a per-trigger HTML
   attribute rather than JS; it needs its own `<script>` include, and is not
   currently loaded in `_base.html`.
   (https://htmx.org/extensions/response-targets/,
   https://github.com/bigskysoftware/htmx-extensions — `response-targets.js`
   sets `shouldSwap = true` and `evt.detail.target = target` when a
   `hx-target-<code>` match is found on the triggering element.)

None of these change status codes or exception mechanics on the Django side;
they only decide whether/where the browser paints the body Django already
sent.

## 2. What this repo already does

**Global listener, already extended past 422.**
`freedom_ls/base/static/base/js/alpine-components.js:9-27` listens for
`htmx:beforeSwap` on `document` and:
- forces swap for `422` (`shouldSwap = true`, `isError = false`) — the
  form-revalidation case;
- for **any** `4xx`/`5xx` whose body contains
  `hx-swap-oob="beforeend:#toast-region-`, forces `shouldSwap = true` (leaving
  `isError` untouched) so a server-rendered OOB toast still lands even on a
  hard error. This already covers "denied and there's a toast in the body",
  but only for the toast region — it does not retarget the *main* swap target,
  so a fragment meant to replace the form itself needs a different path (see
  §3).

**No `HX-Retarget`, `HX-Reswap`, or `response-targets` extension anywhere.**
Grepped `freedom_ls/`, `config/`, JS and templates — zero matches. The
extension script is not vendored or loaded.

**The panel framework's action endpoint already returns a bare, unstyled
403 — this is the exact gap the spec is closing.**
`freedom_ls/panel_framework/views.py:352-362` (`_handle_action`):

```python
def _handle_action(request: HttpRequest, resolved: _ResolvedAction) -> HttpResponse:
    """Check permission, then submit (POST, DELETE) or render (GET) the action."""
    action = resolved.action
    ctx = resolved.ctx
    if not action.has_permission(request, ctx.instance):
        return HttpResponse(status=403)
    ...
```

`action.has_permission` is also the hide-not-disable check
(`freedom_ls/panel_framework/panels.py:125-129` filters `get_actions()` by
it before rendering), so today the only way to *hit* this 403 at all is a
stale page or a hand-made request — which is precisely the "role changed
while the page was open" case the idea names. Right now that request gets an
empty body, no message, and (per §1) htmx will not even swap it — the button
click just silently does nothing. There is no fragment, no "what happened,
why, who to ask", and nothing renders where the form was.

**Every panel-framework denial today is 404, not 403.**
`Panel.check_access` / `authorise_instance`
(`freedom_ls/panel_framework/panels.py:70-95`) always raises `Http404` — for
a missing scope attribute, an unauthenticated request, *and* a denied
`authorise_instance` override. There is no 403 branch in the read path at
all; the only 403 in the whole framework is the action-submission one above.
This matches the idea's framing ("current code returns 404 for organisation
scope on purpose") but also means the 403 side of the split does not exist
yet anywhere except that one bare `HttpResponse(status=403)`.

**Django's own 403/404 handling.** No `handler403`, `handler404`,
`PermissionDenied` usage, or `403.html`/`404.html` templates exist in
`freedom_ls/`/`config/` (confirmed by
`spec_dd/3. done/2026-09-06_11:53_error-pages/research_django_error_wiring.md`,
§1 and §5 — this project is still on Django's stock handlers, and that spec
is closed/done but the templates were, per that doc's own text, not created
during it — verify current state before relying on this; the doc is dated
2026-09-06). 404/403/400 render with the full `RequestContext` (all context
processors), unlike 500. Relevant for the full-page 403/404 case in §3.

**HTMX conventions from `templates_and_cotton.md` / project skills.** The
addendum (`claude_plugins/fls-dev/resources/templates_and_cotton.md`) only
covers template path/theming conventions, not response-handling; the generic
`ds:template`/`ds:htmx` conventions it defers to were not found as a
separate skill file under `claude_plugins/` (no `ds*htmx*` path exists in
this checkout — likely a plugin-bundled skill resolved at runtime, not a
resource file in this repo). The authoritative in-repo precedent for "how do
we make htmx swap an error" is therefore `alpine-components.js` (§2 above)
and the 422 path in `panel_framework/actions.py` (`FormPanelAction.form_invalid`,
`DeleteAction.handle_submit`'s `ProtectedError` branch) — both re-render the
*same* fragment/template that was already on the page, at the same target,
with a non-2xx status, and rely on the existing `beforeSwap` listener to let
it through. A 403 fragment for a denied action should follow the identical
shape: same template family (the action's own `template_name`, or a shared
"denied" partial), same target, and either (a) status `403` plus a
`beforeSwap` rule extended to also match 403, or (b) `HX-Retarget` to be
explicit about the target when the denial is discovered somewhere other than
where the form renders (e.g. a stale table row action whose target no longer
exists).

**The dialogs spec's conventions this must fit inside**
(`spec_dd/1. next/educator-interface-3-panel-framework-dialogs/idea.md`):
forms "post to itself and swap itself"; 422 re-renders the form with errors
and moves focus to the error summary; success is 204 + `HX-Trigger`. A 403 on
the same endpoint should read as a sibling of the 422 case — same swap
target, same "the fragment carries its own heading" rule — not a new
mechanism. The modal's rule that "a form posts to itself and swaps itself"
implies the 403 fragment replacing a modal form's body should also carry
focus-management (move focus to the denial heading, same as 422 moves it to
the error summary) so the dialog spec's focus contract still holds when the
swap is a denial instead of a validation error.

## 3. Where the 403 fragment renders, per surface

All four surfaces already have an htmx swap target the framework or the
dialog spec defines; the 403 fragment reuses it rather than inventing a new
one:

- **Native `<dialog>` modal (spec 3).** The form "posts to itself and swaps
  itself" inside the modal body. A denial discovered on submit swaps the
  modal body with a fragment that has the same heading slot as any other
  modal content, states what happened/why/who to ask, and offers only a
  close/back action (no retry — the permission is gone, not transient).
  Backdrop click is disabled for form content per the dialog spec; the denial
  fragment should behave like the destructive-confirmation case (focus moves
  to the close/cancel control) rather than like a form, since there is
  nothing left to type. No page navigation needed — the instance underneath
  is unaffected.
- **Quick-view drawer (spec 3).** The drawer already has an inline
  error-with-retry contract ("Errors render inline in the body with a retry
  button. The drawer never auto-closes on error."). A 403 while fetching
  drawer content is a **degenerate case of that same contract**: same inline
  slot, but the idea's "who to ask" copy in place of a generic error, and no
  retry button (retrying a permission denial does not help, unlike a network
  blip) — this is a small, spec-owned deviation from "always show retry" that
  the dialogs spec should be told about, since it currently doesn't
  distinguish denial from transient failure.
- **Inline table-row action (a row's own action button, e.g. delete/edit on
  a learner row).** No dialog is open; the action's own endpoint response
  needs to be retargeted to somewhere within the row or to a toast, since
  there may be no "form" location left once the row itself has changed
  underneath the user (the idea's own example: cohort membership changed
  while the page was open). This is the case `HX-Retarget` earns its keep:
  the server can point the 403 fragment at a stable per-row or per-panel
  container (e.g. the panel's own `region_id`, which every `Panel` already
  computes) rather than assuming the button's own DOM node still makes sense
  as a swap target. Where no stable container exists (a plain row action with
  no panel wrapper), fall back to the OOB toast path already wired in
  `alpine-components.js` — swap nothing in place, but surface the "who to
  ask" message as a toast, then have the row re-fetch/refresh via the
  existing `panelChanged`-style HX-Trigger convention so the stale row
  corrects itself.
- **Full page load** (a direct URL, a bookmark, a stale tab reload). This is
  not an htmx request at all (or is a boosted navigation that
  `interface-swap-fallback.js` already forces into a real navigation when the
  response lacks `#interface-main`). It gets Django's ordinary `403.html`
  under `handler403`/`PermissionDenied`, rendered with the full
  `RequestContext` (§2) — same chrome as every other page, "what happened,
  why, who to ask" as page content, and a link back to the last
  reachable scope (the organisation dashboard, or the site's root). No
  `403.html` exists yet (§2) — this spec's implementation needs it created
  or needs to confirm the (separately tracked, "3. done") error-pages spec
  already shipped one; check current tree state rather than trusting the
  dated research doc.

## 4. The 404/403 line, and what GitHub/GitLab/Canvas do

**The line this spec draws (from `idea.md`, already settled, restated for
clarity):** 404 is about *scope* — an organisation, or an instance whose
containing scope, the user cannot reach at all (they have no role that grants
visibility into that organisation, or the object is outside every scope they
hold). 403 is about *capability inside a scope the user can see* — the
organisation or cohort is visible to them (it appears in their nav, their
list, their scope), but the specific action or object is not theirs to touch,
typically because a grant changed underneath them.

Applied to the idea's own example — an instructor opening a cohort by URL
that they have no grant on:
- If the cohort belongs to an organisation the instructor has **no** grant on
  at all → 404. They cannot see the organisation exists; showing 403 would
  confirm a cohort ID resolves to a real, named organisation, which is exactly
  the slug-enumeration risk `idea.md` names for organisation scope.
- If the cohort belongs to an organisation the instructor **does** have a
  grant on (they see the organisation, its dashboard, its other cohorts) but
  this specific cohort is not one they're assigned to → this is the harder
  case. Strictly by the settled rule ("scope is the organisation for
  organisation roles and the cohort for cohort roles" — an instructor's scope
  *is* the cohort, not the organisation), a cohort outside an instructor's
  assigned set is outside their scope, so 404 is the literal reading of the
  settled rules, even though the organisation itself is visible. This is an
  open question worth confirming explicitly with the product owner (§
  Implications) because it is easy to build either way without noticing
  which one shipped.

**GitHub**: returns 404, not 403, for private repositories a token/session
cannot see — deliberately, "GitHub does not disclose the existence of
resources you are not authorized to see... a token cannot be used to
enumerate private repositories." This is a blanket policy, not scoped to
"outside every reachable org" — GitHub applies it even to a repo inside an
org the user is otherwise a legitimate member of, if they lack per-repo
access.

**GitLab**: inconsistent by GitLab's own admission — several long-running
issues (`gitlab-org/gitlab-foss#65271`, `gitlab-org/gitlab#20878`, a GitLab
forum thread "404 when 403 was expected — is this on purpose?") track cases
where the Release API and others return 404 for a permission failure when
users/maintainers expected 403, with no fully settled resolution across the
API surface. The practical lesson for FLS: **pick the rule once, write it
down (as this spec's table already starts to), and hold the line test to it**
— the alternative is GitLab's years-long inconsistency, discovered
piecemeal via bug reports.

**Canvas LMS**: renders an in-app "unauthorized" page (`shared/unauthorized`
view, distinct from a 404) for content the user is logged in and enrolled
near but cannot open — e.g. an unpublished assignment, or a masquerade
permission gap — with guidance to contact the teaching team. Canvas does not
use anti-enumeration 404s inside a course the user is already enrolled in;
enrolment itself is the visible scope boundary, and everything inside it that
they can't yet use is a 403-shaped "access denied", closer to this spec's
"an action they can see but may not perform" than to its "organisation
scope" case. This is the closer analogue to FLS's instructor/cohort scenario
than GitHub's blanket 404 policy is, since Canvas's course ≈ FLS's
organisation and Canvas already draws the line at "enrolled" vs "not
enrolled" the same way FLS's settled rule draws it at "granted a role in this
scope" vs not.

## Implications for FLS

1. **Extend the existing `beforeSwap` listener, don't add a new mechanism.**
   `alpine-components.js` already special-cases 422 and OOB-toast 4xx/5xx.
   Add a 403 branch (or generalise the OOB-toast branch to also catch
   non-toast denial fragments by a body marker, e.g. a
   `data-htmx-denied="true"` attribute on the root element of the denial
   partial) so `_handle_action`'s 403 and any panel-read-path 403 actually
   render. This is strictly additive to code that already exists and already
   ships to production; no `response-targets` extension or global
   `responseHandling` config change is needed unless a future surface needs
   per-attribute per-code targeting that a body-content check can't express.
2. **Give the panel framework a real 403 fragment, not a bare status.**
   `_handle_action` in `panel_framework/views.py` needs a template (a shared
   "denied" partial, on the model of `delete_confirmation.html`) carrying
   what happened / why / who to ask, rendered with `status=403`, at the same
   target the action's own template already uses. `PanelAction` gains a hook
   (e.g. `denied_response(ctx)`) so `DeleteAction`, `EditAction`,
   `FormPanelAction` all get it for free, matching the shape of
   `form_invalid`.
3. **Give `Panel.authorise_instance` a way to say 403 instead of always
   404.** Today it can only raise `Http404`. Spec 5 needs it (or a sibling
   hook) able to distinguish "you cannot see this scope" (404, unchanged)
   from "you can see the scope but not this capability" (403, new) — likely
   by having `authorise_instance` raise `PermissionDenied` for the second
   case and leaving `Http404` for the first, then wiring a project
   `handler403`/`403.html` (confirm whether the error-pages spec already
   shipped one before building it again).
4. **"Who to ask" should name a role, then a person, derived from data
   already queried for scoping — never invented copy per view.** For an
   organisation-scoped denial, the answer is "an organisation_staff member of
   this organisation" (or a specific name, if exactly one exists — check via
   the same `organisations_accessible_to`-style helpers the interface already
   uses to scope lists, not a fresh query, so leakage is bounded by the same
   rules that decide visibility). For a cohort-scoped denial, "an instructor
   or organisation_staff member with a grant on this cohort." Never surface a
   list of every staff member's identity to a user who cannot otherwise see
   the organisation's roster — only to a user for whom the organisation
   itself (not just this one action) is already in scope.
5. **Open questions for the product owner (with suggested defaults):**
   - Cohort outside an instructor's assigned set, inside an organisation they
     otherwise see (§4): confirm 404 (literal reading of "scope is the
     cohort for cohort roles") is intended, not 403. **Suggested default:
     404** — consistent with the settled scope rule and avoids a second,
     harder-to-test carve-out for "organisation-visible but cohort-invisible."
   - Should the denial fragment differentiate "your role changed" from "you
     never had this role" (both currently collapse to the same
     `has_permission() is False`)? The idea's own scenario is specifically
     the *changed-while-open* case. **Suggested default: no differentiation
     for v1** — the message is truthful either way ("you do not currently
     have permission to do this"), and distinguishing them needs an audit
     trail read that spec 11 owns, not this one.
   - Does the drawer's "no retry on 403" deviation from its own idea's
     blanket "errors render inline with a retry button" need a line in the
     dialogs spec, or is it implied by "who to ask" copy replacing the retry
     affordance? **Suggested default: state it explicitly** in whichever
     spec ships first (this one or spec 3, whichever is written second should
     cross-reference), since two specs currently describe overlapping
     drawer-error behaviour and neither currently mentions the other's
     denial case.

## Sources

- https://htmx.org/docs/#response-handling
- https://htmx.org/events/#htmx:beforeSwap
- https://htmx.org/reference/#response_headers
- https://htmx.org/extensions/response-targets/
- https://github.com/bigskysoftware/htmx-extensions (response-targets source, `shouldSwap = true` on match)
- https://gitlab.com/gitlab-org/gitlab-foss/-/issues/65271 (GitLab: "return 403 instead of 404 when not enough permissions")
- https://gitlab.com/gitlab-org/gitlab/-/issues/20878 (GitLab: "404 could also indicate a permissions problem")
- https://forum.gitlab.com/t/404-when-403-was-expected-is-this-on-purpose/88268
- https://devbytes.co.in/news/why-github-shows-404-error-for-inaccessible-private-repos (GitHub anti-enumeration 404 policy)
- https://github.com/dgilperez/canvas-lms-1/blob/master/app/views/shared/unauthorized.html.erb (Canvas's in-app unauthorized view)
- `freedom_ls/panel_framework/views.py:352-362` (`_handle_action`, the repo's one existing 403)
- `freedom_ls/panel_framework/panels.py:70-95` (`Panel.check_access`/`authorise_instance`, always `Http404` today)
- `freedom_ls/base/static/base/js/alpine-components.js:9-27` (existing `beforeSwap` extension for 422 and OOB-toast 4xx/5xx)
- `spec_dd/3. done/2026-09-06_11:53_error-pages/research_django_error_wiring.md` (Django error-page/context mechanics in this repo)

status: ok
