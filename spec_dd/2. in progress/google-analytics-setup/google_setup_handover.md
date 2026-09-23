# Google Analytics 4 and Google Ads: platform setup

This is the source of truth for how GA4 and Google Ads are configured for an FLS deployment. Follow
it top to bottom. Every setting has a value, so nothing is left to decide. It assumes you know your
way around both platforms, so it lists what to set, not where to click.

If something here turns out to be wrong, fix it in this file first, then on the platforms.

## What FLS sends

One gtag.js tag on every page. Page views come from GA4's enhanced measurement, not from FLS.
Signed-in visitors carry `user_id` set to their numeric account ID. No email, name or phone number
is sent anywhere.

| Event | Sent when | Parameters |
| --- | --- | --- |
| `sign_up` | An account is created | `method` = `email` |
| `course_access_requested` | A learner registers interest in a coming-soon course, or submits a course application | course params, `request_kind` = `interest` or `application` |
| `course_registered` | A learner registers themselves for a course | course params, `registration_method` = `self_registration` |
| `course_started` | A learner opens their first page of a course | course params, `registration_source` = `individual` or `cohort` |
| `course_completed` | A learner completes a course | course params, `registration_source` |
| `generate_lead` | A marketing form in the downstream project is submitted. FLS itself never sends it | `lead_form`, sometimes course params |

The course params are `course_id` (the course's UUID), `course_slug` and `access_type` (`free` or
`application_gated`).

Landing pages may also set the predefined `content_group` dimension to `landing_page`. It needs no
setup.

Staff and cohort registrations happen away from the learner's browser, so they never produce
`course_registered`. That funnel step undercounts. `course_started` still covers those learners.

Consent Mode is set in the tag itself: denied for visitors in the EEA, the UK and Switzerland. Nothing
to configure for it.

## Environments

| Environment | GA4 | Google Ads |
| --- | --- | --- |
| Production | Its own property, set up as below | Set up as below |
| Staging | Its own property, set up exactly as below | None. No Ads ID and no labels, or test sign-ups count as real conversions |

The measurement ID and Ads ID are set once per FLS deployment. Every site that deployment serves
shares one GA4 property and one Ads account. Sites are told apart by the Hostname dimension.

## 1. GA4 property

Do this before launch. GA4 applies a custom dimension only to events that arrive after it's
registered, and it never backfills.

**Property.**

| Setting | Value |
| --- | --- |
| Reporting time zone | South Africa (GMT+02:00) |
| Currency | South African Rand (ZAR) |
| Reporting identity | Blended |
| Event data retention | 2 months |
| Reset user data on new activity | On |
| Google Signals | Off |
| User-provided data collection | Off |

2-month retention only limits explorations. Standard reports keep their data.

**Data stream.** One Web stream for the production domain.

| Setting | Value |
| --- | --- |
| Enhanced measurement: Page views | On |
| Enhanced measurement: Page changes based on browser history events | On. Most FLS navigation changes the URL without a full page load |
| Enhanced measurement: Form interactions | Off. It fires on every form, quiz pages included |
| Enhanced measurement: Scrolls, Outbound clicks, Site search, Video engagement, File downloads | On |
| Redact data: Email | On |
| Redact data: Query parameters | On, with no extra parameters listed |
| Define internal traffic | One rule named `Team`, `traffic_type` = `internal`, IP addresses of the team's office and VPN (the operator supplies the list) |
| List unwanted referrals | Empty |

**Data filters.**

| Filter | State |
| --- | --- |
| Internal Traffic | Active |
| Developer Traffic | Active |

**Custom dimensions.** Register these seven, all event-scoped. The dimension name is the parameter
name.

| Dimension / parameter name | Scope |
| --- | --- |
| `course_id` | Event |
| `course_slug` | Event |
| `access_type` | Event |
| `request_kind` | Event |
| `registration_method` | Event |
| `registration_source` | Event |
| `lead_form` | Event |

`course_id` never changes. A slug can be renamed, which splits a course's history across two
`course_slug` values, so report on `course_id` and show `course_slug` beside it for readability.
`method` stays unregistered.

**Created event.** `course_access_requested` mixes interest clicks with applications. Create:

| Setting | Value |
| --- | --- |
| Custom event name | `course_application_submitted` |
| Matching condition 1 | `event_name` equals `course_access_requested` |
| Matching condition 2 | `request_kind` equals `application` |
| Copy parameters from the source event | On |

**Key events.** Mark exactly these five:

- `sign_up`
- `course_registered`
- `course_application_submitted`
- `course_completed`
- `generate_lead` (fires only once the downstream project has a lead form; mark it now anyway)

`course_access_requested` stays unmarked. Marked, it would count every application twice and every
interest click as a conversion. `course_started` stays unmarked because it's a funnel step.

**Funnel exploration.** Name it `Course funnel`. Open funnel, steps:

1. `sign_up`
2. `course_access_requested` OR `course_registered`
3. `course_started`
4. `course_completed`

Breakdown: `course_id`, with `course_slug` as a second dimension.

## 2. Google Ads account

Production only.

| Setting | Value |
| --- | --- |
| Auto-tagging | On |
| Enhanced conversions for web | Off |
| GA4 link | Link the production GA4 property. Import site metrics on. Personalised advertising off |

## 3. Conversions in Google Ads

There are two ways a conversion reaches Ads: an **Ads tag** conversion action that FLS fires in the
browser, or an **imported** GA4 key event. Both can run together, but each moment below goes through
exactly one of them, so nothing counts twice and nothing needs primary/secondary juggling between
routes.

Ads tag is used wherever FLS can fire it. It reaches bidding within hours and counts view-through
and engaged-view conversions, which Display, YouTube, Demand Gen and Performance Max campaigns use.
Search doesn't need either, but this setup works for all of them without changes.
Applications and completions are imported because they exist as separate events only inside GA4.

| Moment | Route | Ads conversion action name | Goal category | Primary / secondary |
| --- | --- | --- | --- | --- |
| Course registration | Ads tag, fired on `course_registered` | `FLS course registration` | Sign-up | Primary |
| Application submitted | Import GA4 key event `course_application_submitted` | `FLS application submitted` | Submit lead form | Primary |
| Lead form | Ads tag, fired on `generate_lead` | `FLS lead` | Submit lead form | Primary |
| Account created | Ads tag, fired on `sign_up` | `FLS sign-up` | Sign-up | Secondary |
| Course completed | Import GA4 key event `course_completed` | `FLS course completed` | Other | Secondary |

`sign_up` is secondary because bidding on it chases accounts that never register for a course.
`course_completed` is secondary because it lags the ad click by weeks.

Do not import the GA4 key events `sign_up`, `course_registered` or `generate_lead` into Ads. The Ads
tag already reports those three.

**Settings for all five conversion actions:**

| Setting | Value |
| --- | --- |
| Value | Don't use a value |
| Count | One |
| Click-through conversion window | 30 days |
| Engaged-view conversion window | 3 days |
| View-through conversion window | 1 day |
| Attribution model | Data-driven |

The three Ads tag actions are Website actions set up manually with code, not from a URL rule. Each
one's tag snippet contains `send_to: 'AW-XXXXXXXXX/LABEL'`. The part after the slash is the label.
`FLS lead` will show as inactive until a lead form exists. That's expected.

## 4. Values for the deployer

Production:

| Environment variable | Value |
| --- | --- |
| `GOOGLE_ANALYTICS_MEASUREMENT_ID` | The production data stream's `G-…` ID |
| `GOOGLE_ADS_CONVERSION_ID` | The Ads account's `AW-…` ID |
| `GOOGLE_ADS_CONVERSION_LABELS` | `course_registered=<label of FLS course registration>,generate_lead=<label of FLS lead>,sign_up=<label of FLS sign-up>` |

Staging:

| Environment variable | Value |
| --- | --- |
| `GOOGLE_ANALYTICS_MEASUREMENT_ID` | The staging data stream's `G-…` ID |
| `GOOGLE_ADS_CONVERSION_ID` | Unset |
| `GOOGLE_ADS_CONVERSION_LABELS` | Unset |

If campaigns ever target a country other than South Africa, tell the deployer. FLS's Content
Security Policy allows only `www.google.co.za` of Google's country domains, and Ads calls the one for
the visitor's country.

## 5. Checking it works

On production, with Tag Assistant connected, sign up, register for a free course, open its first
page, complete it, and submit an application for an application-gated course. In GA4 DebugView each
event appears once with the parameters in the first table, and `user_id` appears after sign-in. In
Tag Assistant, `sign_up` and `course_registered` each carry a `conversion` event with the matching
`send_to`. Within a few hours the Ads tag conversion actions move to "Recording conversions". The
two imported ones follow within about a day.
