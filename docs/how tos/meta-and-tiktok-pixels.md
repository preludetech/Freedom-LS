# Meta and TikTok pixels

This is the sibling to [Google Analytics 4 and Google Ads](./google-analytics-and-ads.md). Each
platform app is switched on separately, and this guide only covers the Meta and TikTok setup; GA4
and Google Ads are documented there.

## What FLS sends

Each pixel loads once per page and, from then on, tracks boosted and `hx-push-url` navigation
through its own history listener. FLS sends no page-view call of its own. No email, name, phone
number or other personal data is sent to either platform.

An analytics event reaches a pixel only when it appears in that platform's mapping. Every other
event, including an interest registration, `course_started`, and any name a downstream project
records, sends nothing to either pixel.

**Meta:**

| Analytics event | Condition | Call |
| --- | --- | --- |
| `course_registered` | | `fbq('track', 'CompleteRegistration', params)` |
| `course_access_requested` | `request_kind` is `application` | `fbq('track', 'SubmitApplication', params)` |
| `generate_lead` | | `fbq('track', 'Lead', params)` |
| `sign_up` | | `fbq('trackCustom', 'SignUp', params)` |
| `course_completed` | | `fbq('trackCustom', 'CourseCompleted', params)` |

**TikTok:**

| Analytics event | Condition | Call |
| --- | --- | --- |
| `course_registered` | | `ttq.track('CompleteRegistration', params)` |
| `course_access_requested` | `request_kind` is `application` | `ttq.track('SubmitApplication', params)` |
| `generate_lead` | | `ttq.track('SubmitForm', params)` |
| `sign_up` | | `ttq.track('SignUp', params)` |
| `course_completed` | | `ttq.track('CourseCompleted', params)` |

`params` is the same object GA4 gets: the course params (`course_id`, `course_slug`, `access_type`)
where the event is about a course, plus `request_kind`, `registration_method` or
`registration_source` where the GA4 guide's table lists them. Neither platform gets `user_id`.

## Conditions for setting a pixel ID

Set `META_PIXEL_ID` or `TIKTOK_PIXEL_ID` only once all three of these hold:

- The learner population is adults only. Both platforms' Business Tools terms forbid sending data
  about children.
- The privacy policy names the platform. `legal_docs/_default/privacy.md` already names Meta and
  TikTok; a project with its own privacy policy does the same before either ID is set.
- `VISITOR_COUNTRY_HEADER` is set, and the header it names is set by a fronting proxy that
  overwrites it on every request. A visitor who could set that header themselves could fake a
  country and defeat the gate. Without the header, neither pixel ever loads, for anyone.

## Environments

| Environment | `META_PIXEL_ID` | `TIKTOK_PIXEL_ID` |
| --- | --- | --- |
| Production | Set | Set |
| Staging | Unset | Unset |

Staging traffic is test traffic. An unset ID keeps it out of both platforms' event counts and match
rates.

## 1. Meta Events Manager

| Setting | Value |
| --- | --- |
| Automatic Advanced Matching | Off |

FLS sends no email or phone number for Advanced Matching to find, and Automatic Advanced Matching
scans the page's own forms for them regardless of what FLS's code sends. Leaving it off keeps the
pixel's behaviour matching what this guide documents.

`CompleteRegistration`, `SubmitApplication` and `Lead` are Meta's own standard events and need no
extra setup to use as conversion goals. `SignUp` and `CourseCompleted` go through
`fbq('trackCustom', ...)`, so each needs a **custom conversion** built in Events Manager before it
can be a goal.

| Conversion | Goal category | Primary / secondary |
| --- | --- | --- |
| `CompleteRegistration` (`course_registered`) | Sign-up | Primary |
| `SubmitApplication` (`course_access_requested`, application) | Submit lead form | Primary |
| `Lead` (`generate_lead`) | Submit lead form | Primary |
| `SignUp` custom conversion (`sign_up`) | Sign-up | Secondary |
| `CourseCompleted` custom conversion (`course_completed`) | Other | Secondary |

`sign_up` and `course_completed` are secondary for the same reasons the Google Ads doc gives:
bidding on account creation chases people who never register for a course, and a completion lags
the ad click by weeks.

## 2. TikTok Events Manager

| Setting | Value |
| --- | --- |
| Automatic Advanced Matching | Off, for the same reason as Meta's |

`CompleteRegistration`, `SubmitApplication` and `SubmitForm` are TikTok's own standard events.
`SignUp` and `CourseCompleted` are not, so both need registering as **custom events** in Events
Manager before they can be goals.

| Event | Goal category | Primary / secondary |
| --- | --- | --- |
| `CompleteRegistration` (`course_registered`) | Sign-up | Primary |
| `SubmitApplication` (`course_access_requested`, application) | Submit lead form | Primary |
| `SubmitForm` (`generate_lead`) | Submit lead form | Primary |
| `SignUp` (`sign_up`) | Sign-up | Secondary |
| `CourseCompleted` (`course_completed`) | Other | Secondary |

## 3. Checking it works

With a test pixel ID set and `VISITOR_COUNTRY_HEADER` sending a South African country code, load a
page and step through sign-up, a course registration and a course completion.

**Meta Pixel Helper** (the Chrome extension) shows the base code loading and each event firing on
the page that triggers it. **Meta Events Manager's Test Events** tab shows the same events arriving
server-side, with their parameters.

**TikTok Pixel Helper** shows the same on the browser side. **TikTok Events Manager's Test Events**
tab confirms TikTok received them.

With the country header set to a gated country, or left unset entirely, neither pixel's script tag
should render at all, and neither extension should report anything.

## 4. For developers of a concrete project

**Turning it off.** A project that wants neither pixel leaves `freedom_ls.meta_pixel` and
`freedom_ls.tiktok_pixel` out of `INSTALLED_APPS` and drops their context processors. Events FLS's
views record are still recorded if `freedom_ls.google_tag` is installed; only their emission to
Meta and TikTok is dropped.

**Pages that don't extend `_base.html`.** Include `partials/meta_pixel.html` and
`partials/tiktok_pixel.html` in the `<head>`, alongside `partials/google_analytics.html`, and
`partials/analytics_events.html` directly before `</body>`.

**Unmapped events.** A downstream project's own event, recorded through
`freedom_ls.base.analytics_events.record_analytics_event`, sends to GA4 if it's a valid event name,
but sends nothing to Meta or TikTok unless that project adds the name to
`freedom_ls.meta_pixel.events.MAPPING` or `freedom_ls.tiktok_pixel.events.MAPPING`.
