# Idea: Public browsing for unauthenticated users

A visitor who is **not logged in** should be able to see what the platform is about
and explore courses *before* creating an account. Account creation is only required at
the moment the visitor takes a committing action (enrol / apply).

## Goal

Reduce the "login wall before any value" problem: today anonymous visitors are bounced
to the login page the instant they try to see anything. We want them to browse a
home page, the course catalogue, and course detail pages freely, and only hit the
login/signup step when they choose to enrol in or apply to a course.

## Current behaviour

- Anonymous users are redirected to the login page when they try to access anything.
- The gating is almost entirely Django `@login_required` decorators on the
  `student_interface` views (dashboard, course catalogue, course detail, course content,
  enrol/apply, etc.). `config/settings_base.py` sets `LOGIN_REDIRECT_URL = "/"`.
- Good news from research: the backend is **already mostly anonymous-safe**. The course
  listing and course-access utilities already handle `AnonymousUser` (they return empty
  personalised data and treat all courses as "not registered"). Site/multi-tenant
  filtering works identically for anonymous users. So the work is largely about *removing
  the gate on the right views* and *adapting the templates*, not rebuilding logic.

## Wanted behaviour (the three public surfaces)

### 1. Home page (dashboard-style, for anonymous users)

- Reuse the existing dashboard at `/` and branch on authentication, rather than building a
  separate marketing page.
- **Hide personalised sections** for anonymous users (welcome-back greeting, my/current
  courses, completed courses, recommended-for-you, in-flight applications).
- **Replace** them with discovery content (a few featured/available courses + a clear path
  into the catalogue). Important: do **not** render empty personalised sections with a
  "sign in to see this" placeholder — that reads as a locked, dead-end page. Omit or
  replace instead.
- Keep auth prompts minimal: "Log in" / "Sign up" in the header (and at most one body CTA).

### 2. Course catalogue

- The catalogue (`all_courses`) becomes publicly viewable.
- Each course card should give anonymous visitors enough to self-qualify: title, short
  description, difficulty/level, duration, and a clear access-model indicator
  (Free / By application). Reuse the existing card; surface the access model.
- Links go to the public course detail page.

### 3. Course detail page

- Publicly viewable. Show the existing course info to anonymous users: title, about,
  learning outcomes, and the content table-of-contents (locked items already render as
  blocked — that's fine and expected).
- Show the **access-model badge** (Free vs By application) near the CTA so the visitor
  knows what clicking will do.
- Use **action-forward CTA wording**: "Enrol for free" / "Apply now". The button does not
  mention login; the auth requirement appears only after the click (deferred login).

## Deferred login flow (the committing action)

When an anonymous user clicks the CTA:

- **Presentation:** reuse the existing full-page Django login/signup flow via `?next=`
  (no modal). The login/signup screen should restate intent in its heading, e.g.
  "Create a free account to enrol in <Course>". This is lower-risk, reuses existing auth,
  and is the more accessible option.
- **Intent is auto-completed:** after the user logs in *or signs up*, the action they
  intended completes automatically and they land on the course content (free enrol) or the
  application form (gated course) — no second click.
  - This means the enrol/apply target must be reachable as the `next` destination and
    behave idempotently: an authenticated user arriving there performs the action and moves
    on, rather than showing a "you need to enrol" page that requires another click.
  - `next` must be threaded through **both** the login form and the **signup** form (the
    new-user path is where intent is most commonly lost) and honoured in both success
    handlers.
- **Security:** any `next` value read from the request must be validated with
  `url_has_allowed_host_and_scheme` (same-host paths only) to avoid open-redirect/phishing.
  Where possible the server constructs the `next` target from the course slug rather than
  trusting a client-supplied value.
- **Application forms:** do not render a gated application form to an anonymous user (its
  data would be lost across login). Prompt login first, then render the form for the
  authenticated user.

## Basic SEO / discoverability (in scope)

Because the catalogue and course pages are now public, make them discoverable:

- Server-rendered public URLs (already the case — no JS-only rendering of course info).
- `<title>` + `<meta name="description">` per public course/catalogue page.
- `schema.org/Course` JSON-LD on course detail pages (and `ItemList` of `Course` on the
  catalogue) for rich results.
- An XML sitemap covering public catalogue + course URLs; ensure `robots.txt` does not
  block them.
- Keep it "basic" — no ratings/structured-data fields we don't have data for.

## Out of scope (for now — leave for future specs)

- Content previews / sample lessons for anonymous users (beyond the existing blocked ToC).
- Guest checkout / paid-course purchasing flows.
- Catalogue search and rich filtering (beyond what already exists).
- Per-site configuration toggles for how much is public.

## Anti-patterns to avoid (from research)

- Forcing signup before any value is shown (the thing we're fixing — don't reintroduce it
  on sub-pages).
- Empty personalised sections shown to anonymous users as "log in to see this".
- Unclear gating: a visitor should be able to tell Free vs By application *before* clicking.
- Landing the user on a generic dashboard after login instead of completing their intent.
- Losing the new-user signup path's `next` (test this path explicitly).

## Research

See the companion research files in this directory:

- `research_guest_browsing_patterns.md` — how Coursera/edX/Udemy/Khan/Moodle/Canvas etc.
  let logged-out users browse; home/catalogue/detail patterns; pitfalls; SEO/a11y.
- `research_deferred_login_ux.md` — the login-wall-on-action moment; intent preservation
  via `next`; CTA wording; open-redirect safety; accessibility.

## Notes

This file is intentionally high-level. The detailed surface-by-surface behaviour,
view/template changes, and the exact enrol/apply auto-completion mechanics belong in the
spec (`/spec_from_idea`).
