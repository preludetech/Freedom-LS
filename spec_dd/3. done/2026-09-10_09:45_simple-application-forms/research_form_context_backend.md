# Research: the `FORM_CONTEXT_BACKEND` seam

Scope: design the pluggable backend that lets a `Form` (`form_engine/models.py:43`) be answered both
inside the course player (`learner_interface`) and inside a `CourseApplication`
(`course_applications`), per §12 of `spec_dd/3. done/2026-08-24_20:56_extract_forms_into_seperate_app/1. spec.md`. The
precedent to follow is `COURSE_ACCESS_BACKEND` (`freedom_ls/course_access/`), read in full below.

## 0. The precedent, in outline

`course_access/backends.py` declares one ABC (`CourseAccessBackend`), one `*Decision` dataclass
(`CourseAccessDecision`), plus two smaller dataclasses for secondary seams (`AccessBadge`,
`DashboardContribution`), and one concrete default (`FreeOnlyCourseAccessBackend`).
`course_access/config.py` declares the setting via `AppSettings`/`Setting`. `course_access/loader.py`
resolves it lazily, `@functools.cache`d, always wrapping the configured backend in
`VisibilityEnforcingBackend` so no backend can bypass a house invariant. `course_access/checks.py`
reports a missing setting (E001, via the shared `required_settings_errors`), an unresolvable/
uninstalled backend (E003), and a config-shape mismatch after a swap (E002).
`course_applications/backends.py` is the shipped worked example of a **downstream app extending the
ABC**: it subclasses `FreeOnlyCourseAccessBackend`, widens `_ALLOWED_ACCESS_TYPES`, and is named as the
default by a **project settings string** in `config/settings_base.py:503-505` — never by a Python
import from `course_access` back to `course_applications`. That asymmetry (the base app is imported
*by* its implementations, never imports one back) is the load-bearing property this research reuses
throughout.

## 1. The interface

**§12's three fields (can-answer, exit URL, chrome partial) are necessary but not sufficient, and the
one thing they cannot be is a single shared ABC *method signature* copied verbatim from
`CourseAccessBackend.get_access(*, user, course)`.** This is the central finding of this research, so
it is stated first and justified once.

### 1.1 Why one shared typed method doesn't work here

`CourseAccessBackend.get_access` has exactly one domain noun, `Course`, across every implementation —
`course_access` imports `Course` from `content_engine` once (`course_access/backends.py:30`,
`course_access --> content_engine` in `docs/app_structure.md`) and every backend, present or future,
is keyed on it.

A form-context backend has no equivalent single noun. `form_fill_page`
(`learner_interface/views.py:1037-1247`) needs `course`, `collection_item`, `index` and
`course_progress` to build `_player_chrome_context` (`learner_interface/views.py:797-862`) — none of
which is derivable from `(user, form)` alone, because a `Form` carries no reverse link to the
`ContentCollectionItem` that places it (only `ContentCollectionItem.child` names the `Form`, not the
other way — see the domain glossary's `ContentCollectionItem` note) and a learner can hold two
registrations for one course (`learner_progress/attempts.py`'s own docstring: *"Nothing outside this
module may resolve one from `(user, form)`: that question cannot tell two records of the same course
apart"*). The application-context backend needs `CourseApplication`, an entirely different noun.

Typing a single ABC method against both would require `form_engine/backends.py` to import
`ContentCollectionItem`/`Course` **and** `CourseApplication`. `docs/app_structure.md` already has
`content_engine --> form_engine` (the loader edge, §8.1 of the extraction spec); a
`form_engine --> content_engine` import — even TYPE_CHECKING-only, since `course_access --> content_engine`
in the graph today comes from exactly such a guarded import at `course_access/backends.py:30` — would
be a two-app cycle, precisely what §13 criterion 4 of the extraction spec forbids. Importing
`CourseApplication` would be worse: it would force `form_engine --> course_applications` at the same
moment this spec adds `course_applications --> form_engine` (§3 below) — another cycle, self-inflicted.

### 1.2 The resulting split

`form_engine` owns the **return-value contract** and the **settings/loader/check plumbing**. It does
**not** own a shared abstract method signature. Each context defines its own backend class, in the app
that already legally imports that context's domain objects:

```python
# freedom_ls/form_engine/backends.py — form_engine's whole surface for this seam
from __future__ import annotations
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class FormContextDecision:
    """Decision returned by a form-context backend's get_context().

    Mirrors CourseAccessDecision's house pattern (course_access/backends.py:40-61):
    callers read only these fields, never branch on context-private state.
    """

    can_answer: bool
    exit_url: str
    # None when the form is not submit_on_exit (Form.submit_on_exit); the runner
    # never builds this URL itself, since the route name is context-owned.
    submit_and_exit_url: str | None
    chrome_partial: str
    # Deliberate: an opaque render-ready dict, exactly DashboardContribution's
    # contract (course_access/backends.py:76-88) — form_engine never inspects
    # these keys; each context owns its own chrome variables.
    chrome_context: dict[str, Any]
```

`learner_interface/backends.py` defines `CourseFormContextBackend` with its own, fully-typed method:

```python
def get_context(
    self, *, user: User, course: Course, collection_item: ContentCollectionItem, index: int
) -> FormContextDecision: ...
```

`course_applications/backends.py` defines `ApplicationFormContextBackend`:

```python
def get_context(self, *, user: User, application: CourseApplication) -> FormContextDecision: ...
```

Each app's own wrapper view (`learner_interface`'s existing `form_fill_page`/`view_form`/`form_start`/
`form_submit_and_exit`; a new equivalent in `course_applications`) resolves its own identity from its
own URL kwargs exactly as it does today, then calls **its own** configured backend directly — never
through a shared polymorphic call. This is a deliberate divergence from the `COURSE_ACCESS_BACKEND`
shape, not an oversight: `CourseAccessBackend` gets away with one method because it has one noun;
`FormContextBackend` genuinely has two, and forcing them into one signature would recreate the exact
inter-app cycle the extraction spec exists to avoid.

### 1.3 What to add to §12's three fields, and why

- **`submit_and_exit_url` alongside `exit_url`, not one field.** `form_fill_page` builds two distinct
  destinations today: `save_and_exit_url` (a GET target, `view_course_item`,
  `learner_interface/views.py:1209-1212`) and `submit_and_exit_url` (a POST target,
  `form_submit_and_exit`, `:1203-1206`). They differ per `Form.submit_on_exit` and land in different
  places (`view_course_item` vs. `course_form_complete` via `form_submit_and_exit`). A single "exit
  URL" loses this distinction; the backend must supply both, because the runner cannot `reverse()` a
  route name it does not own.
- **`chrome_context: dict[str, Any]`, not just `chrome_partial: str`.** A template name alone is
  useless without the render context to feed it (breadcrumb, TOC, progress record, …), all of which is
  context-owned data the runner must never inspect. This is not a new idea — it is
  `DashboardContribution.context` (`course_access/backends.py:84-87`) applied to the same seam.
- **No `cta_label`/`cta_url`/acquisition-copy fields.** Those exist on `CourseAccessDecision` for a
  discovery/marketing funnel (course detail page, anonymous visitors). A form-fill page is already
  inside the funnel — its "can-answer" question is binary, and the redirect target for "cannot answer"
  is **not** backend-supplied either: `_course_access_redirect` hardcodes
  `redirect("learner_interface:course_detail", ...)` itself when `can_access_content` is `False`
  (`learner_interface/views.py:602-605`) rather than reading a URL off the decision. Each form-context
  caller should do the same — hardcode its own fallback (`course_detail`-equivalent for the player,
  the application status page for applications) rather than adding a redirect-URL field the precedent
  itself doesn't use for the equivalent case.
- **404-vs-redirect stays a caller decision, not a backend field**, matching `course_access`'s own
  split: `raise_404_if_hidden_unregistered` (404, "this doesn't exist for you",
  `course_access/visibility.py:20-37`) runs *before* the backend is consulted; `can_access_content`
  (redirect, "this exists but you can't use it yet") is the backend's business. §5 below applies this
  split to applications: ownership is a 404 resolved by the calling view's own `get_object_or_404`,
  never delegated to the backend.

## 2. How the runner picks a backend

**Not one setting, not a registry keyed on `Form`, not a field on `Form`. Two independently-pluggable
settings, each read by exactly one call site.** Recommendation, with the two rejected shapes stated
once each:

- **A registry keyed on something on `Form`, or a `Form.context` field, is the wrong layer.** Both
  require the *data* to know which *code path* will orchestrate the request (redirects, chrome,
  sequential-unlock gating) — but that is already determined by which URLconf routed the request there.
  Both also carry the same footgun: a `Form` reused in two contexts (a shared "tell us about yourself"
  template authored once, referenced from a course's collection *and* from `CourseApplication.form`)
  would have to declare one context and silently mis-serve the other. Nothing here needs a `Form` to
  be single-context, and a setting shape that assumes it is buys nothing.
- **A single `FORM_CONTEXT_BACKEND` setting is the wrong shape** because — as the task states — a form
  answered inside a course and a form answered as an application need different backends *at the same
  time on the same site*. One dotted-path string cannot hold two independently-configured values.
- **Two named settings, mirroring the multiple settings already declared side by side in
  `course_access/config.py`** (`COURSE_ACCESS_BACKEND`, `OVERRIDE_COURSE_VISIBILITY_TO_VISIBLE`,
  `OVERRIDE_COURSE_ACCESS_TO_FREE` — one `AppSettings` subclass, several independent `Setting`
  entries): `COURSE_FORM_CONTEXT_BACKEND` (default: `learner_interface`'s
  `CourseFormContextBackend`) and `APPLICATION_FORM_CONTEXT_BACKEND` (default:
  `course_applications`'s `ApplicationFormContextBackend`, the shipped default exactly as
  `ApplicationCourseAccessBackend` is the shipped `COURSE_ACCESS_BACKEND` default,
  `config/settings_base.py:499-505`). Swapping one never touches the other, and no new machinery is
  needed — this is the same `AppSettings` class handling two rows instead of one.

**What makes the URL routing unambiguous:** the app's own URLconf, not a runtime lookup. A request
under `courses/<slug:course_slug>/<int:index>/…` is, unconditionally, the course-player context;
`learner_interface`'s own view reads `COURSE_FORM_CONTEXT_BACKEND`. A request under whatever route
`course_applications` defines for its own fill page (see §5 — keyed on the `CourseApplication`, not on
a course/index pair) is, unconditionally, the application context; `course_applications`'s own view
reads `APPLICATION_FORM_CONTEXT_BACKEND`. There is no dispatch step that inspects a `Form` at
request time to decide which backend applies — the dispatch already happened when Django resolved the
URL to a view in one app or the other. This is exactly the same reasoning `_course_access_redirect`
already relies on: it is a `learner_interface`-only helper, called only from course-player routes,
never reused verbatim by `course_applications`'s own `apply`/`application_status` views.

## 3. Which app owns it, and the exact new edges

`docs/app_structure.md` today: `form_engine`'s runtime deps are `accounts, content_base,
markdown_rendering, site_aware_models` — **no edge to `content_engine`, `learner_interface`, or
`course_applications`, in either direction.** `content_engine --> form_engine` and
`learner_interface --> form_engine` already exist; `course_applications --> form_engine` does **not**
exist yet.

- **`form_engine` gains no new outgoing edges.** Per §1.2, `form_engine/backends.py` and
  `form_engine/config.py`/`loader.py`/`checks.py` import nothing from `content_engine`,
  `learner_interface`, or `course_applications` — only `FormContextDecision`'s own fields (`str`,
  `bool`, `dict[str, Any]`) and the base-app machinery (`freedom_ls.base.app_settings`). This mirrors
  `course_access` never importing `course_applications` (module docstring,
  `course_access/backends.py:6-7`: *"course_access never imports course_applications"*).
- **`learner_interface --> form_engine` deepens but is not a new edge** — `learner_interface` already
  depends on `form_engine` (it imports `Form`, `count_form_questions`, etc. today); it now also
  imports `form_engine.backends.FormContextDecision` and `form_engine.config`/`loader` to read
  `COURSE_FORM_CONTEXT_BACKEND`.
- **`course_applications --> form_engine` is the one genuinely new edge.** It is required for three
  independent reasons landing together in this spec: the `CourseApplication.form` FK to `Form`, the
  `ApplicationFormContextBackend` subclassing/importing `form_engine.backends.FormContextDecision`,
  and an application-side attempt resolver (§5.4) importing `FormProgress`. **Use a direct Python
  import for the FK's target (`from freedom_ls.form_engine.models import Form`), not a string
  reference.** A string FK (`"freedom_ls_form_engine.Form"`) would dodge `/ds:app_map`'s ast-based
  scan and leave this edge real but invisible — exactly the failure mode the extraction spec's §5.4
  warns against for `content_base`. The edge needs to be visible anyway for the other two reasons, so
  hiding it at the FK would only create an inconsistency (declared everywhere else, absent at the one
  place a reader would look first).
- **No cycle:** `form_engine` has zero edges back to `course_applications` (§1.2, by construction) and
  zero to `content_engine`/`learner_interface`. Adding `course_applications --> form_engine` against a
  `form_engine` with no reverse edge is a plain DAG edge, not a two-app cycle — the same shape as
  `course_applications --> course_access` today.

This is a smaller, cleaner change to the graph than trying to force a shared ABC through `form_engine`
would have been (§1.1) — that path would have *required* the two forbidden reverse edges just to type
the method signature.

## 4. The mechanics to copy verbatim

Every one of these exists today in `course_access` and should be reproduced with `s/course access/form
context/` and, where a setting name appears, once per new setting (§2).

**Lazy resolution.** `course_access/loader.py`'s `get_course_access_backend()` is a plain function
resolved on first call, not at import time, because settings access needs the app registry populated:

```python
@functools.cache
def get_course_access_backend() -> CourseAccessBackend:
    inner_class: type[CourseAccessBackend] = import_string(config.COURSE_ACCESS_BACKEND)
    return VisibilityEnforcingBackend(inner_class())
```

Two loader functions this shape, `get_course_form_context_backend()` and
`get_application_form_context_backend()`, one per new setting. Neither needs a `VisibilityEnforcingBackend`-style
universal wrapper today — both entry points already sit behind `@login_required`, so there is no
known cross-cutting invariant equivalent to coming-soon/hidden enforcement to bolt on at the loader.
Note this as a considered-and-declined point, not an oversight, so a future reader does not assume one
is missing by accident.

**`ImproperlyConfigured` naming the setting, never a bare `ImportError`.** This is `AppSettings.__getattr__`
itself, in the shared base module (`freedom_ls/base/app_settings.py:30-47`), not something
`course_access` reimplements:

```python
if setting.required:
    raise ImproperlyConfigured(
        f"{name} is required but is not set. "
        f"Set {name} in your Django settings."
    )
```

Declaring `COURSE_FORM_CONTEXT_BACKEND: str` / `APPLICATION_FORM_CONTEXT_BACKEND: str` as
`Setting(required=True)` in `form_engine/config.py` gets this for free — nothing to write beyond the
declaration, exactly as `CourseAccessConfig` gets it (`course_access/config.py:1-20`).

**Memoization plus a clearable cache for tests.** `course_access/loader.py`'s module docstring, to be
copied verbatim (with the setting names swapped) onto both new loader functions:

> "`get_course_access_backend()` is cached for the process lifetime. Callers that use
> `override_settings(COURSE_ACCESS_BACKEND=...)` in tests MUST call
> `get_course_access_backend.cache_clear()` before and after the test to avoid the cached instance
> bleeding across tests."

**The system check for an unresolvable value.** `course_access/checks.py` has the ID scheme
documented in its module docstring (`:1-13`, `E001`/`E002`/`E003`/`W001` — `app_label.severity +
number`) and two checks worth mirroring directly:

- **E001 (missing setting)** is not hand-written per setting — it is the shared
  `required_settings_errors(config, app_label)` helper (`base/app_settings.py:62-75`), called once
  per app: `required_settings_errors(config, "freedom_ls_form_engine")` already iterates every
  `Setting(required=True)` in `declared_settings`, so adding the second setting costs nothing here.
- **E003 (backend's app not installed)**, `check_course_access_backend_app_installed`
  (`course_access/checks.py:76-104`), is hardcoded to one setting name and would need to run **twice**
  — once per `*_FORM_CONTEXT_BACKEND` setting. Per CLAUDE.md's "avoid repeating code", parametrise it
  over `[("COURSE_FORM_CONTEXT_BACKEND", ...), ("APPLICATION_FORM_CONTEXT_BACKEND", ...)]` inside one
  `form_engine/checks.py` function rather than pasting the body twice.
- **E002-equivalent (config-shape check after a swap)** has no obvious analogue yet — `Course.access_config`
  is what `CourseAccessBackend.validate_course_config` checks; there is no equivalent
  free-form config blob on the form-context seam as scoped here. Leave it out rather than invent a
  check with nothing to validate.

**Document the contract at the same time the setting is introduced.** §12 of the extraction spec
already states this as a requirement, quoting the same `course_access` precedent this research just
enumerated; nothing here changes that instruction, it only supplies the concrete text to mirror.

## 5. Authorisation, concretely

**Finding that changes the shape of this answer: `CourseApplication` has no `state` field today.**
`course_applications/models.py:17-30` is explicit that this is deliberate and deferred:

> "NOTE: when application review lands, this model gains `state = FSMField(protected=True)`, the
> submit/withdraw/pick_up/request_changes/resubmit/approve/reject transitions... Do not architect
> these away — leave this model standalone and additive."

So "the owner of a `CourseApplication` in a state that permits editing" describes a model this app's
own committed roadmap has not built yet, not a check this spec's code can perform today. The correct
scoping decision: **`can_answer` in `ApplicationFormContextBackend.get_context` is "ownership plus
binding" only, for now** — since nothing today can ever move a `CourseApplication` out of an editable
state (there is no reviewer workflow to do so), every application a user owns is editable by
construction, and adding a state gate now would either invent the state machine early (out of scope,
and explicitly reserved for `application_review` per the NOTE above) or add a dead branch that always
evaluates true. When `application_review` lands, the one change required is narrowing `can_answer` to
`application.state in EDITABLE_STATES` — the authorisation *seam* is already in the right place; only
its condition grows a clause.

### 5.1 What must be checked, and by whom

- **Ownership — a view-layer 404, not a backend decision.** Mirror `application_status`'s existing
  pattern exactly: `get_object_or_404(CourseApplication, pk=pk, user=request.user)`
  (`course_applications/views.py:76`). A request for someone else's application `pk` must 404, never
  redirect — the same "this doesn't exist for you" convention `raise_404_if_hidden_unregistered` uses
  for hidden courses (`course_access/visibility.py:20-37`), for the same reason: a redirect confirms
  the object exists.
- **Binding — the form is read off the application, never off a client-suppliable parameter.** The
  application-fill route must be keyed on the `CourseApplication`'s own `pk`
  (`course-applications/<uuid:pk>/form/<int:page_number>/`, no separate form id in the URL or POST
  body), with `form = application.form` resolved server-side. Anything that let a caller pick a
  *different* form than the one their application is bound to would let an owner answer a form they
  were never assigned — the failure mode named explicitly in the brief.
- **Anonymous users are not a concern for this backend.** `apply` already requires `@login_required`
  (`course_applications/views.py:19`), so unlike `CourseAccessBackend` — whose `RequestUser` union
  exists because anonymous visitors browse the discovery pages
  (`course_access/backends.py:32,140-141`) — `ApplicationFormContextBackend.get_context` can type
  `user: User`, not `RequestUser`.
- **Cross-application `FormProgress` bleed — the concrete failure mode a naive `(user, form)` lookup
  creates.** `FormProgress` has no uniqueness constraint beyond `(user, form)` and can hold several
  rows for that pair over time (`form_engine/models.py:197-219`); nothing in the schema stops two
  different gated courses' `CourseApplication.form` pointing at the identical `Form` row (the idea
  file itself only says application forms "might be different per course", not that they must be).
  `learner_progress/attempts.py`'s own reasoning applies verbatim here — its docstring:

  > "Nothing outside this module may resolve one from `(user, form)`: that question cannot tell two
  > records of the same course apart, and it cannot tell a course attempt from a standalone one."

  `learner_progress` solves this with `CourseFormAttempt`, a row it owns that scopes a `FormProgress`
  to `(course_progress, collection_item)`. `course_applications` needs the same shape: a resolver
  module mirroring `learner_progress/attempts.py` (`get_latest_incomplete`/`get_or_create_incomplete`
  scoped to the `CourseApplication`, not to `(user, form)` directly — most simply, a `FormProgress`
  FK stored **on** `CourseApplication` itself, minted once via `get_or_create`-under-`transaction.atomic`
  the first time the applicant starts answering, exactly the "written together" comment at
  `learner_progress/attempts.py:83-86`). Without this, an applicant with two gated-course applications
  sharing one authored `Form` would have their answers to one silently read from, or overwritten by,
  the other.

### 5.2 Failure modes to name in the spec

1. Answering another user's application → 404 (ownership).
2. Supplying/guessing a form or page not bound to the caller's own application → 404, form resolved
   server-side from `application.form` only.
3. Answering after the application leaves an editable state, once `application_review` lands →
   redirect to the status page (`can_answer=False`), not 404 — the application *is* theirs.
4. Two of the user's own applications sharing one `Form` resolving to the same `FormProgress` →
   prevented by an application-scoped attempt resolver (§5.4), never a bare `(user, form)` lookup.
5. Anonymous access to the fill route → already closed by `@login_required` at the view layer; the
   backend does not need its own anonymous-user branch.

status: ok
