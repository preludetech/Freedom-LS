# Error pages

FLS ships no error pages. When a visitor hits a dead link, an unhandled exception, a form submitted
on a stale session or a tripped rate limit, Django or allauth answers with a hardcoded fallback:
unstyled black-on-white text, no header, no theme, no way back into the app.

The worst of them is not the 404. Seven of allauth's rate-limit scopes fall through to a literal HTML
string with no stylesheet at all, and three of those seven are reachable by a signed-in learner in
their account settings. Django's CSRF-failure page is rendered by a bare template engine that knows
nothing about this project's loaders or theme.

There is one precedent to build on. `accounts/lockout.html`, served by django-axes, already returns
429 through FLS's own entrance layout with a heading, a way back to sign-in and a password-reset
link. Every other surface gets nothing.

Designs are at `/home/sheena/workspace/lms/designs/Learner experience/Error States.html`. They were
produced by a tool that knows nothing about FLS's infrastructure, and drawn against the `first_class`
theme. We take the layout and the tone from them. We do not take the functionality they imply.

## The pages

| Page | Served when | Shell | Way forward |
| --- | --- | --- | --- |
| 404 | Dead link, renamed content, mistyped URL | Full | Dashboard; browse courses |
| 403 | Permission denied on something the visitor knows exists | Full | My courses; sign in as another account |
| 400 | Malformed or suspicious request | Full | Dashboard |
| 403 CSRF | Form posted on a stale session | Full | Sign in again, then retry |
| 429 | Any rate limit or lockout | Full | Wait, then try again |
| 500 | Unhandled failure | Standalone | Reload; dashboard |
| 503 | Maintenance | Standalone | Try again later |

FLS ships the 503 and never serves it. Downstream projects point a maintenance middleware or a proxy
at it. We build no maintenance mode and no switch to turn one on.

We restyle `accounts/lockout.html` to match the new 429, keeping its status code and both its links.

## What is settled

**The 500 stands alone.** Django calls `handler500` with no request and no context, so no context
processor runs. No site name, no logo, no header, no user menu, no working CSRF token. `500.html`
therefore extends nothing and queries nothing. It links the compiled stylesheet and that is all. It
is visibly plainer than the other six, and it is the one page that cannot fail while rendering. The
503 is built the same way, because whatever serves it may be running with the app down.

**Nothing on a page that the page cannot verify.** This cuts most of what the designs show. The
progress-saved reassurance goes ("saved through Module 4 · Section 4.1" names a hierarchy FLS does
not have, and a 500 is the one moment when nothing about the request's state is trustworthy). So do
the invented reference codes, the ticking countdown, the named requests-per-minute figure, and "the
team has been paged". A rate-limit page carries no countdown and no limit number. FLS cannot read a
remaining cooldown back out of allauth's cache keys or axes' rows, and a countdown that does not
match when access actually returns is worse than none.

**No support or status affordances.** No contact link, no reference code, no status-page link, no
"report a broken link". FLS has no support-contact setting and surfaces no Sentry event ID, and this
work adds neither. Each page offers navigation back into the app and nothing else.

**Existing role tokens only, no new ones.** Status marks pair a `*-light` background with its
`on-*-light` foreground. Never `text-warning`, which under the `default` theme is a pale yellow
chosen to be a background and is illegible on a light tint. The designs' four-step foreground ramp
collapses onto FLS's two tiers, and radii and type come from tokens, so these pages read
tighter-cornered and system-font under `default` than the mockups do under `first_class`. That is the
token layer doing its job.

**Copy follows GOV.UK's rules.** Plain language, no blame, no jokes, no "oops", no exclamation marks,
no HTTP jargon as the headline. One primary action rather than a menu of links. The status code
appears as a small secondary label. A 404 is low-stakes and asks the visitor to check the address. A
500 is our fault and says so.

**Retry is offered only where retrying can work.** That means 500, 503 and 429. Never 404, 403 or
400, where the same request fails the same way.

**Status codes stay honest.** Each page returns its real code and carries `noindex`. No soft 404s,
and no redirecting misses to the dashboard.

**Accessibility is part of the page, not a pass over it.** A distinct `<title>` per page, exactly one
`<h1>`, icons hidden from assistive technology, and colour never the only signal of severity. Every
page still has to read correctly with no stylesheet. On a page that exists because something broke,
that is a live possibility.

Several of the designs' icons have no FLS semantic name. Add the few these pages need to the icon
registry and address them through `<c-icon>` as usual, never a raw icon-set class.

## Out of scope

The designs draw four states FLS cannot honestly build. 401 session-expired, where allauth already
handles sign-out and the "3 drafts kept locally" claim has nothing behind it. 410 course retired. 402
payment declined, since FLS has no billing domain at all. And the offline state, which assumes a
service worker, a content cache and a sync queue that do not exist. 504 is left to whatever proxy
generates it.

The designs' in-context failures and toast variants are also out. FLS already has a toast system with
the same four severities, and nothing there needs changing.

One real gap stays open and should become its own spec. HTMX does not swap non-2xx responses, and FLS
has no global handler for them. Inside the course player, `interface-swap-fallback.js` forces a full
reload onto the real error page. Everywhere else, an htmx request that 404s or 500s changes nothing
on screen. The visitor is left looking at a page that silently stopped working, and will never see
any of the pages this work builds.

## QA

Every rate limit has to be tripped, not just the two obvious ones.
`research_rate_limit_surfaces.md` lists all thirteen scopes, which of them are reachable, what each
renders today and how to provoke it. Three constraints shape the QA plan.

- Dev sets `ACCOUNT_RATE_LIMITS = False`, which zeroes every allauth scope rather than only the two
  FLS overrides. QA needs a throwaway settings module to restore them. The axes lockout is
  independent and fires in plain dev.
- Dev's cache is per-process `LocMemCache` with no reset command, so clearing allauth counters
  mid-session means restarting the server.
- None of the Django-served templates render under `DEBUG=True`. Flipping to `DEBUG=False` locally
  needs `ALLOWED_HOSTS` populated, or every request 400s before reaching the page under test.

Check the 429 inside the signed-in shell as well as the signed-out one. `change_password`,
`manage_email` and `reauthenticate` are all reachable from account settings.

## Research

- `research_rate_limit_surfaces.md` covers all thirteen throttles, what each renders today, and the QA recipe.
- `research_django_error_wiring.md` covers what Django passes each handler, why the 500 is starved, and how to exercise the templates locally.
- `research_error_states_design.md` holds the design inventory, the capability audit, and the design-token to role-token mapping.
- `research_error_page_ux.md` holds the content, accessibility, SEO and security rules the pages are held to.
