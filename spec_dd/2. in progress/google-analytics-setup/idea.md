# Google Analytics 4

Add Google Analytics 4 to FLS the same way PostHog is added. One measurement ID per deployment comes
from an environment variable, declared in `DeploymentSettings` next to the PostHog settings. When the
ID is set, every page loads `gtag.js`. When it is not set, nothing loads and nothing is sent, so
development and unconfigured deployments stay silent. It is a template snippet, as with PostHog, and
adds no dependency. `research_ga4_integration.md` covers the snippet, the setting name and why
django-analytical was passed over.

We want GA to show the learner funnel: new sign-ups, course applications, course starts and course
completions.

## Page views

GA4's default page-view tracking handles HTMX navigation already. FLS uses `hx-boost` and
`hx-push-url` widely, and GA4's enhanced measurement records a page view on each history change.
Nothing FLS-side fires page views by hand, because doing so would double-count.

FLS sends no page view from allauth's two token-bearing pages, `accounts/confirm-email/<key>/` and
`accounts/password/reset/key/…`, so live one-time keys never reach Google in `page_location`.

## Events

Events are sent client-side with GA4's recommended event names, so GA's standard reports work
without extra setup. The action records a one-shot flag and the next full page render emits the
`gtag('event', …)`. None of these moments happens in an HTMX partial.

| FLS moment | GA4 event | Where it happens |
| --- | --- | --- |
| Account created | `sign_up` | `AccountAdapter.save_user()`, beside the `user.registered` webhook |
| `CourseApplication` submitted | `generate_lead` | On form completion in `application_check_answers`; on creation in `_start_application` for courses whose application has no form |
| First content access on a course | `tutorial_begin` | Where `CourseProgress.started_at` is first stamped, in `view_course_item` |
| Course completed | `tutorial_complete` | `course_finish`, beside the `course.completed` webhook |

`tutorial_*` is GA's name for the begin/complete pair. FLS's own vocabulary is unchanged.

A course start is first content access, not registration. Cohort and admin registrations happen
while the learner is not in the browser, so a client-side event could never see them, whereas every
learner opens their first topic or form.

Out of scope for now:

- `login`: FLS has no hook for it.
- `CourseInterest`: its views are HTMX partials and need a different way to emit events.
- Topic- and quiz-level events.
- `begin_checkout`/`purchase`: `course-prices` only displays prices.
- Server-side Measurement Protocol: it needs a second credential and `client_id` plumbing, and no
  FLS action happens outside a browser request yet.

`research_events_to_track.md` has the full flow-to-event mapping, including the call sites.

## Identifying users

For a logged-in user, send `user_id` as `str(user.pk)`. The pk is an opaque integer that FLS already
exposes in URLs, and Google's PII policy allows it. Nothing is hashed, and no emails, names or phone
numbers are sent. `User.email` is globally unique and each user belongs to one site, so the pk needs
no site qualifier. GA's hostname dimension separates sites that share a property.
`research_user_id_and_pii.md` has the policy detail.

## Consent and privacy

South Africa-only operation needs no cookie banner. POPIA allows legitimate interest as a basis for
first-party analytics. South Africa has no ePrivacy-style cookie law, and Google's EU consent policy
and Consent Mode v2 cover only the EEA, UK and Switzerland. `research_consent_south_africa.md` has
the sources.

What does go with this work:

- **Privacy policy.** `legal_docs/_default/privacy.md` says nothing about analytics today, including
  the PostHog that already runs. It should name GA4 and PostHog, say what they collect, and give an
  opt-out route such as Google's opt-out browser add-on.
- **One place that decides whether analytics loads.** A downstream deployment serving EU/UK learners
  can then add consent by overriding that one place instead of rewriting how the snippets load. No
  banner is built.
- **CSP.** Add GA4's domains and PostHog's domains to `SECURE_CSP_REPORT_ONLY`. Neither is listed
  today, and both must be listed before the policy can move to enforcing mode.

## Operator setup

These GA4 property settings are the operator's job and belong in `docs/product/deployment.md` next to
the PostHog entry:

- Reporting identity set to Blended or Observed. Without it, `user_id` has no effect on reports.
- Google Signals left off.
- Ads personalisation off.
- Data retention at 2 months.
- Email and query-parameter redaction on.
- Internal-traffic filters as wanted.
