# Research: GA4 event taxonomy for FLS

Written 2026-09-18, landing pages and lead forms added 2026-09-19. This replaces the event table in `research_events_to_track.md` §6. The full list
of Google's recommended events is in `research_ga4_recommended_events.md`.

## 1. Why the shipped events need replacing

The branch sends four events with no parameters: `sign_up`, `generate_lead`, `tutorial_begin` and
`tutorial_complete`.

- `tutorial_begin` and `tutorial_complete` are Google's words for app onboarding. FLS has no
  tutorials. GA builds no report from them, so the borrowed names buy nothing.
- No event says which course it was about. GA cannot answer "which courses convert".
- Expressing interest in a coming-soon course sends nothing. Neither does registering for a course.
- `generate_lead` covers applications only, and a second kind of lead would be indistinguishable
  from the first.

More course access backends are coming, each with its own way into a course. The event set should
take a new backend without a new event type.

## 2. Design rule

Event names describe funnel moments that every backend shares. Anything that varies by backend goes
in a parameter value.

A payments backend adds the value `request_kind=purchase`. It adds no event name, no enum member, no
GA key event and no funnel step. The GA funnel built today keeps working the day that backend ships.

The alternative is one event name per backend action, such as `course_application_submitted` and
`course_interest_expressed`. That reads slightly better in GA's event list, and it lets a key event
cover applications without covering interest. GA's admin can already do the second thing. "Create
event" derives a new event from `course_access_requested` where `request_kind = application`, and
that derived event can be a key event. So per-backend names cost work every time a backend lands and
return almost nothing.

## 3. The events

| Event | Fires when | Parameters |
| --- | --- | --- |
| `sign_up` | An account is created | `method` |
| `course_access_requested` | A learner asks for a course they cannot enter yet | course parameters, `request_kind` |
| `course_registered` | A registration is created in the learner's own browser request | course parameters, `registration_method` |
| `course_started` | `CourseProgress.started_at` is first stamped | course parameters, `registration_source` |
| `course_completed` | `CourseProgress.completed_time` is first stamped | course parameters, `registration_source` |
| `generate_lead` | A visitor submits a marketing contact form, such as "call me back" | `lead_form`, optional course parameters |

`sign_up` keeps Google's name. Its meaning matches FLS exactly, and GA predefines the `method`
dimension for it. `method` is `email` today. Social login would add its provider name.

`generate_lead` is Google's name too, and it is kept for the same reason. Google defines it as
"submits a form or a request for information", which is what a callback form is. Marketing
dashboards and ad tools look for that name. It does not cover course applications or interest.
Those are `course_access_requested`. See §4.4.

The other four are custom. Any GA4 event can be marked a key event, and any key event can be
imported into Google Ads as a conversion, so a custom name loses nothing there.

The names follow the domain glossary. "Registered" matches `LearnerCourseRegistration`, "started"
matches `started_at` and "completed" matches `completed_time`. "Enrolment" appears nowhere.

### 3.1 Course parameters

Sent on every `course_*` event.

| Parameter | Value | Registered as a custom dimension |
| --- | --- | --- |
| `course_slug` | `Course.slug`, cut to 100 characters | Yes |
| `course_id` | `str(Course.id)` | No |
| `access_type` | Reported by the access backend | Yes |

`course_slug` is the readable one, and it matches the page URLs GA already records.

`course_id` is the UUID that the `course.registered` and `course.completed` webhooks carry. It
survives a slug rename, and it joins GA data to webhook data in BigQuery. It stays unregistered on
purpose. Google treats any dimension with more than 500 values as high cardinality and starts
folding rows into "(other)". An unregistered parameter still reaches BigQuery and DebugView, and it
uses none of the 50 dimension slots.

`access_type` is `free` or `application_gated` today. A paid backend would report `paid`. The value
has to come from the backend, because `Course.access_config` is backend-private and
`AccessBadge.label` is display copy that could be translated. See §10.

### 3.2 Parameters that vary by backend

| Parameter | On event | Values today | Values a later backend might add |
| --- | --- | --- | --- |
| `request_kind` | `course_access_requested` | `interest`, `application` | `purchase`, `waitlist`, `access_code` |
| `registration_method` | `course_registered` | `self_registration` | `application_approved`, `purchase`, `access_code` |
| `registration_source` | `course_started`, `course_completed` | `individual`, `cohort` | none expected |
| `lead_form` | `generate_lead` | none in FLS itself | Whatever the concrete project names its forms, such as `call_me_back` |

`registration_source` reads which FK is set on the course progress record, `learner_registration`
or `cohort_registration`. It matters because cohort and admin registrations never appear as
`course_registered`. See §8.

All values are lowercase snake_case constants. No value is free text.

### 3.3 Fire points

| Event | Where | Request shape |
| --- | --- | --- |
| `sign_up` | `AccountAdapter.save_user()`, `accounts/allauth_account_adapter.py:150`. Unchanged | POST then redirect |
| `course_access_requested`, `interest` | `partial_express_interest`, `course_interest/views.py:58` | HTMX partial |
| `course_access_requested`, `interest` | `deferred_express_interest`, `course_interest/views.py:116`, the path an anonymous visitor takes after signing in | GET then redirect |
| `course_access_requested`, `application` | `apply`, `course_applications/views.py:104`, for a course with no application form | POST then redirect |
| `course_access_requested`, `application` | `application_check_answers`, `course_applications/views.py:245`, after `form_progress.complete()` | POST then redirect |
| `course_registered` | `initiate_course_access`, `learner_interface/views.py:892`, only when `update_or_create` reports a new row | GET then redirect |
| `course_started` | `view_course_item`, `learner_interface/views.py:1023`. Same place as `tutorial_begin` today | Same response |
| `course_completed` | `course_finish`, `learner_interface/views.py:1641`. Same place as `tutorial_complete` today | Same response |
| `generate_lead` | The concrete project's form view, after the form validates and saves. FLS ships no such form | Whatever that view does |

Both interest views call `get_or_create` and throw away the `created` flag. The event should fire
only when the row is new, so a repeat click sends nothing.

## 4. Page views, landing pages and lead forms

Concrete projects will build landing pages, send paid and organic traffic to them, and want to know
who arrived and what they did next. Most of that needs no new event.

### 4.1 What GA records with no code

`page_view` is automatic. The `gtag('config', ...)` call in `_base.html` sends one on every full
page load. Enhanced measurement sends another whenever the browser history changes, which covers
`hx-boost` and `hx-push-url` navigation. `research_ga4_integration.md` §3 covers the HTMX side and
why FLS must not hand-fire `page_view`. Google does not let a property switch `page_view` off.

GA also sends these by default. The first five rows are enhanced measurement, per Google's Help
page. The last row is GA's automatic collection.

| Event | Fires when |
| --- | --- |
| `scroll` | The visitor first reaches 90% of a page's height |
| `click` | The visitor follows a link to another domain |
| `file_download` | The visitor clicks a link to a file such as a PDF |
| `video_start`, `video_progress`, `video_complete` | An embedded YouTube video plays |
| `form_start`, `form_submit` | The visitor touches or submits any HTML form |
| `session_start`, `first_visit` | A session or a new visitor begins |

GA also reads `utm_source`, `utm_medium`, `utm_campaign`, `utm_content` and `utm_term` from the URL
of the first page in a session. It fills the session source, medium and campaign dimensions from
them. No code is involved. The links have to carry the tags.

### 4.2 Landing pages need no event

GA already has a session-scoped "Landing page" dimension. It is the path of the first page viewed in
a session. The Landing page report under Engagement lists sessions, new users and key events per
landing page. That report answers "are people getting there" and "did they go on to sign up" with
nothing added. It counts any first page as a landing page, including a course page someone reached
from a search engine.

I wrote the description of that dimension and report from memory. Google's Help page for the
Landing page report returned a 404 when I fetched it, so check the report in a live property.

A `landing_page_visited` event would repeat the `page_view` that already fired, and someone would
have to keep it in step with the URL list.

The one gap is telling a marketing landing page from any other first page without a URL pattern.
Concrete projects may not keep landing pages under one prefix. GA's built-in content group fills
that gap. The landing page template sets one value on the config call.

```
gtag('config', 'G-XXXX', {content_group: 'landing_page'});
```

Every event sent from that page, `page_view` included, then carries "Content group = landing_page".
Content group is a predefined dimension, so it uses no custom dimension slot and needs no
registration. A funnel's first step becomes `page_view` where content group is `landing_page`, and
it holds for any URL layout.

FLS should expose this as a template block in `_base.html` that a landing page template fills in.
FLS's own pages leave it empty for now. Naming groups for the catalogue, course pages and the player
is possible later and costs nothing in GA.

One caveat. The config call runs once per full page load. After an `hx-boost` navigation the value
from the original page sticks to later history-based page views. Landing pages should link onward
with normal full-page links, which is how a separate marketing template behaves anyway.

### 4.3 Seeing what visitors do next

All of these work from the automatic `page_view` plus the events in §3.

- The Landing page report, with key events per landing page and per session source.
- A funnel exploration. Step one is `page_view` with content group `landing_page`. Later steps are
  `page_view` on a course page, then `sign_up`, `course_access_requested`, `course_registered` and
  `course_started`. Break it down by landing page or by session campaign.
- A path exploration starting at a landing page, which shows the actual next pages and events.

The Landing page dimension is scoped to one session. Someone who lands on Monday and signs up on
Thursday is credited to Thursday's first page. GA's "First user source / medium / campaign"
dimensions carry the original traffic source across sessions, but GA has no first-user landing page.
FLS already stores that server-side. `SignupAttribution.landing_path` holds the first-touch landing
path and the UTM values for every signup, so the cross-session answer comes from FLS, not GA.

### 4.4 Lead forms

Enhanced measurement's `form_submit` looks like it covers this. It does not. It fires for every form
on the site, including sign-in and every quiz page. It fires when the browser submits, so a
submission that fails server-side validation still counts. It can miss forms that HTMX submits. Its
`form_id` and `form_name` parameters also need registering before reports show them.

So a lead form sends `generate_lead` from the server side of the form view, after the form validates
and saves, through the same one-shot session mechanism as every other event. `lead_form` names the
form, for example `call_me_back` or `brochure_request`. A form that belongs to one course also sends
the course parameters from §3.1, so leads line up with the course funnel.

The form's field values never go to GA. No phone numbers, names or messages. See §9.

Consider turning "Form interactions" off in the data stream's enhanced measurement settings. With
quizzes on the site, `form_start` and `form_submit` are mostly noise, and `generate_lead` replaces
the part that mattered.

FLS ships no lead forms. Concrete projects build them. That means the recording function has to be
usable from outside FLS, with event names FLS has never heard of. See §10.

### 4.5 Campaign links and referral codes

GA attributes a session from the `utm_*` tags on the landing URL. FLS's referral links, `/go/{code}`
and `/d/{CODE}`, redirect with a 302, so GA never sees the redirect itself. `build_redirect_url` in
`referral_tracking/codes.py` passes the visitor's query string through to the destination and adds
`ref={code}`. UTM tags on the short link therefore reach the landing page and GA reads them there.

GA ignores `ref`. A referral link with no UTM tags shows in GA as direct traffic or as whatever site
the visitor came from. To see a campaign in GA, put the `utm_*` tags on the link or in the referral
code's destination URL.

## 5. Events considered and left out

**`course_application_started`.** Out. Every application form page already sends `page_view`, so a
GA funnel can use the first form page as its "started" step. A dedicated event would duplicate that.

**`login`.** Out. `user_id` already marks signed-in sessions, and no funnel question here depends
on the login moment. Adding it later is one receiver on allauth's `user_logged_in` signal.

**Quiz and topic completion.** Out for now. They fire far more often than the funnel events, and
nobody has asked a question they would answer. The quiz result page sends `page_view`, which gives
a rough count. If they come later, the same rule applies. One `course_child_completed` event with a
`content_type` parameter, not one event per content type.

**Payments.** Not built, so nothing to send. When a payment flow lands it should use Google's
`begin_checkout` and `purchase` with an `items` array, where `item_id` is the course slug. Ecommerce
is the one area where Google's names feed built-in reports, so it is worth taking them there.
`course_registered` with `registration_method=purchase` follows the purchase.

**`generate_lead` for applications.** Dropped. The previous design used it for course applications.
Sending it next to `course_access_requested` would count each application twice. The name now
belongs to marketing contact forms only. See §4.4.

**`landing_page_visited`.** Out. GA records this already, three ways. See §4.2.

**Call-to-action click events.** Out. A landing page button leads to a course page or the signup
page, and that arrival is a `page_view`. Links to other domains send GA's automatic `click` event.

## 6. GA property setup

Each GA property needs this once. It belongs in `docs/product/deployment.md` when the code ships.

Register six event-scoped custom dimensions under Admin, Custom definitions: `course_slug`,
`access_type`, `request_kind`, `registration_method`, `registration_source` and `lead_form`. A standard property
allows 50. Reports pick a dimension up 24 to 48 hours after registration, and I believe they do not
backfill, so register before launch.

Mark five key events: `sign_up`, `generate_lead`, `course_access_requested`, `course_registered`
and `course_completed`.

Build the funnel in Explore, Funnel exploration, with these steps: `sign_up`, then
`course_access_requested` or `course_registered`, then `course_started`, then `course_completed`.
Break it down by `course_slug` or `access_type`. For campaign traffic, put `page_view` with content
group `landing_page` in front as the first step. See §4.3.

In the data stream's enhanced measurement settings, leave "Page changes based on browser history
events" on and consider turning "Form interactions" off. See §4.4.

To count applications apart from interest, use Admin, Events, Create event. Match
`course_access_requested` where `request_kind` equals `application`, name the result, and mark it a
key event.

The Admin API can script all of this. `properties.customDimensions.create` and
`properties.keyEvents.create` need the `analytics.edit` scope. Six dimensions and five key events
are quick by hand, so a script only pays off once several deployments need the same setup.

## 7. Google's limits

From the Analytics Help pages on collection limits and naming rules, fetched 2026-09-18.

| Limit | Value | Effect here |
| --- | --- | --- |
| Event name length | 40 characters | Longest is `course_access_requested`, 23 |
| Parameter name length | 40 characters | Fine |
| Parameter value length | 100 characters | `Course.slug` allows 500, so cut it |
| Parameters per event | 25 | Most used is 4 |
| Event-scoped custom dimensions | 50 standard, 125 on 360 | 6 used |
| High-cardinality guidance | More than 500 values | Why `course_id` stays unregistered |

Names take letters, digits and underscores, start with a letter, and are case sensitive. Reserved
parameter names include `user_id`, `session_id`, `currency`, `uid`, `cid` and `customer_id`.
Reserved prefixes are `_`, `ga_`, `google_`, `firebase_` and `gtag.`. None of the names above
collide.

## 8. What client-side events cannot see

A `gtag` event needs the learner's browser. Three ways into a course happen elsewhere.

- Staff create a `LearnerCourseRegistration` in the Django admin.
- A cohort gains a `CohortCourseRegistration`, or a learner joins a cohort that has one.
- A reviewer approves an application, once application review exists.

None of these send `course_registered`. Those learners still send `course_started` when they open
their first page, and `registration_source` records whether they came through a cohort. So the
funnel's later steps stay complete, and only the registration step undercounts.

The real fix is GA's Measurement Protocol, which sends events from the server. It needs the GA
client id, and `SignupAttribution.ga_cookie` already stores it, at
`referral_tracking/models.py:76`. That is a separate piece of work.

## 9. Privacy

No parameter carries personal data. No emails, names, application answers or free text. Course
slugs and UUIDs describe content, not people. A lead form sends the form's name and nothing the
visitor typed into it.

The privacy policy still needs a change. `legal_docs/_default/privacy.md:23-32` lists what
analytics collects as pages viewed, device information, a cookie identifier and the numeric account
ID. Course events tied to that account ID go past the list. Add one line saying that analytics
records which courses a learner requests, registers for, starts and completes.

## 10. Implementation sketch

Enough to judge the size of the change. Not a plan.

- `freedom_ls/base/google_analytics.py`. The session list holds `{name, params}` dicts, not bare
  names. Dedupe compares the whole dict, so two courses in one session both report. Replace the enum
  members. "Flag" stops describing what the functions carry, so rename them to say "event".
- The same module is the public entry point for concrete projects. The recording function takes
  any event name as a `str` and checks it against Google's naming rules from §7. FLS's own names
  stay in the `StrEnum`, whose members are strings already. A downstream lead form then records
  `generate_lead` without touching FLS.
- `base/templates/_base.html:102`. Add a template block inside the `gtag('config', ...)` call so a
  landing page template can set `content_group`.
- `freedom_ls/course_access/backends.py`. Add a config-only method that returns the `access_type`
  string, next to `get_access_badge` at `:119`. `FreeOnlyCourseAccessBackend` returns `free`,
  `ApplicationCourseAccessBackend` returns the configured type, and `VisibilityEnforcingBackend`
  delegates.
- A helper in `course_access` that builds the three course parameters from a `Course`.
  `course_interest`, `course_applications` and `learner_interface` already depend on
  `course_access`, so this adds no cross-app dependency.
- `base/templates/partials/google_analytics_events.html`. Serialise parameters as JSON. The current
  per-value `escapejs` does not stretch to an object.
- `course_interest/partials/express_interest_cta.html` includes the events partial. HTMX runs inline
  scripts on swap, so the interest event fires at the click. Without this it waits in the session
  for the next full page, which could be a day later.
- Tests. Several assert the literal string `gtag('event', 'sign_up')` and the list-of-strings
  session shape. They live in `base/tests/test_google_analytics.py`,
  `deployment/tests/test_context_processors.py`, `accounts/tests/test_account_webhook_events.py`,
  `course_applications/tests/test_views.py`, `learner_interface/tests/test_view_course_item.py` and
  `learner_interface/tests/test_course_completion_webhook_events.py`.
- Docs. The privacy policy line from §9, the GA setup steps from §6 in
  `docs/product/deployment.md`, and the module docstring, which no longer needs to explain
  "tutorial".

## Sources

- [Analytics Help: [GA4] Event collection limits](https://support.google.com/analytics/answer/9267744?hl=en)
- [Analytics Help: [GA4] Event naming rules](https://support.google.com/analytics/answer/13316687?hl=en)
- [Analytics Help: [GA4] About the (other) row](https://support.google.com/analytics/answer/13331684?hl=en)
- [Analytics Help: [GA4] Custom dimensions and metrics](https://support.google.com/analytics/answer/14240153?hl=en)
- [Analytics Help: [GA4] Recommended events](https://support.google.com/analytics/answer/9267735?hl=en)
- [Developer reference: recommended events](https://developers.google.com/analytics/devguides/collection/ga4/reference/events)
- [Analytics Help: [GA4] Enhanced measurement events](https://support.google.com/analytics/answer/9216061?hl=en)
- [Analytics Help: [GA4] Content groups](https://support.google.com/analytics/answer/11523339?hl=en)
- [Admin API: customDimensions.create](https://developers.google.com/analytics/devguides/config/admin/v1/rest/v1beta/properties.customDimensions/create)
