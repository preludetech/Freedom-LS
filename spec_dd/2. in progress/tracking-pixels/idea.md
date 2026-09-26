# Meta and TikTok pixels

We are starting to advertise on Meta (Facebook and Instagram) and TikTok. FLS loads each platform's
browser pixel and reports the same conversion moments it already reports to Google Ads, so that both
platforms can measure and bid on the same funnel.

The audience is South African, and campaigns target South Africa only, as with Google. Learners are
adults.

## What we build on

`freedom_ls/google_tag` already does this for Google. A view records a one-shot event in the session
when something happens. The next render, whether a full page or an HTMX swap, pops the queue and
emits the calls. An event that has an Ads conversion label also sends that conversion.
`docs/how tos/google-analytics-and-ads.md` lists the events and how each one reaches Ads.
`research_fls_tracking_integration.md` covers the queue, the two include points, the CSP host groups
and the consent seam in detail.

## Where the code lives

Meta and TikTok support goes in its own app or apps, separate from `google_tag`. A project can then
switch GA4, Meta and TikTok on or off independently by leaving an app out of `INSTALLED_APPS`, the
way `google_tag` is switched off today.

Views keep calling one recorder, and every installed platform reads the same recorded events. The
recorder, the event enum and the session key are all Google-named today
(`record_google_analytics_event`, `GoogleAnalyticsEvent`, `google_analytics_events`), so they get
platform-neutral names and move somewhere every platform app can import them from. The how-to
documents `record_google_analytics_event` as the way a downstream project records `generate_lead`,
so the rename is a breaking change and goes in the upgrade notes. The event names stay the same, so
GA4 reports and funnels carry on unchanged.

## Configuration

One pixel ID per platform per deployment comes from environment variables, the same as the GA4 and
Ads IDs. If a platform's ID is not set, nothing of that platform loads. Staging leaves both unset, so
test sign-ups never reach a production pixel.

Which FLS event becomes which platform event is fixed in code. There are no labels to configure the
way Google Ads has, because Meta and TikTok take event names directly. Which events count as primary
or secondary conversions is set in each platform's ads manager, not in FLS.

## Conversions

These are the same five moments Google Ads counts, with the same primary/secondary split:

| Moment | FLS event | Meta | TikTok | Goal |
| --- | --- | --- | --- | --- |
| Course registration | `course_registered` | `CompleteRegistration` | `CompleteRegistration` | Primary |
| Application submitted | `course_access_requested` with `request_kind=application` | `SubmitApplication` | `SubmitApplication` | Primary |
| Lead form | `generate_lead` | `Lead` | `SubmitForm` | Primary |
| Account created | `sign_up` | custom event | custom event | Secondary |
| Course completed | `course_completed` | custom event | custom event | Secondary |

Neither platform has a standard event for enrolling on a course, finishing one or creating an
account. `CompleteRegistration` fits two of those moments. It goes to course registration, the primary goal,
because standard events get more optimisation signal on both platforms. Account creation and
course completion become custom events. On Meta, a custom event needs a custom conversion built in
Events Manager before a campaign can optimise on it. TikTok registers custom events in its Events
Manager. `research_meta_pixel.md` §2 and `research_tiktok_pixel.md` §2 have the candidate mappings
and the reasons against the alternatives.

Interest registrations (`course_access_requested` with `request_kind=interest`) and `course_started`
are not sent. Neither one is a Google conversion either.

## Page views

Each pixel fires one `PageView` when it loads. Both pixels also fire their own `PageView` on every
`pushState` or `replaceState` change, which covers FLS's `hx-boost` and `hx-push-url` navigation.
FLS never fires a page view by hand, because doing so would count each navigation twice. GA4 follows
the same rule. The spec confirms against the real swap behaviour that each navigation counts exactly
once.

## Which pages

The pixels load on every page gtag loads on, except the educator interface. Staff pages are not an
advertising audience. Like gtag, they never load on allauth's two token-bearing pages.

## Privacy and consent

- **No consent banner.** South African visitors are covered by legitimate interest, as GA4 is. This
  basis is weaker for ad pixels than it was for GA4. Meta and TikTok use the data for their own
  purposes, which makes each of them an independent responsible party, and the data leaves South
  Africa. We accept that. `research_ad_pixel_privacy_and_consent.md` sets out the reasoning and the
  options we passed over.
- **EEA, UK and Swiss visitors.** For these visitors the pixels stay dormant (`fbq('consent',
  'revoke')`, `ttq.holdConsent()`, never granted), matching the Consent Mode denial GA4 applies.
  Google works out the visitor's region in the browser. Meta and TikTok take no region, and FLS has
  no way to tell where a visitor is. The spec researches how to find out, for example a proxy or CDN
  country header, a GeoIP lookup or the browser's time zone, and what happens when the country is
  unknown. Meta's Business Tools Terms require consent before its cookies are set for these
  visitors, so leaving them ungated is not an option.
- **No personal data.** No email, name or phone number goes to either platform. The deployer guide
  says to switch automatic advanced matching off in both Events Managers, because it scrapes form
  fields without FLS choosing to send them.
- **Adults only.** Meta's terms forbid sharing data about children under 13, and TikTok's forbid it
  for any minor. The deployer guide makes an adult-only learner population a condition of setting a
  pixel ID.
- **Privacy policy.** Both platforms require the privacy policy to name them. The default
  `legal_docs/_default/privacy.md` talks about "analytics and advertising services" in general, so
  it needs to name Meta and TikTok, or the deployer guide needs to tell the operator to.

## Deployer guide

The existing how-to is Google-only. The spec decides whether to extend it or add a sibling. Either
way it covers what FLS sends, the settings in each Events Manager (automatic advanced matching off,
the custom conversions), the environment variables per environment, and how to check it works with
each platform's Pixel Helper and Test Events.

## CSP

Each platform gets its own host group in `SECURE_CSP_REPORT_ONLY`, with a comment giving the reason,
and a test in `freedom_ls/base/tests/test_csp.py` in the shape of the existing ones. The hosts are
roughly `connect.facebook.net` and `www.facebook.com` for Meta, and `analytics.tiktok.com` for
TikTok. The spec confirms them against a live trace.

## Out of scope

- **Server-side tracking** (Meta Conversions API, TikTok Events API, Google Measurement Protocol).
  It gets its own idea, `server-side-conversion-tracking`, covering all three platforms together.
  Browser-only pixels lose events to ad blockers. We accept that for now.
- Pinterest, Snap and other platforms.
- A consent banner.
- Per-site pixel IDs for multi-site deployments. Every site a deployment serves shares one pixel per
  platform, as with GA4.
- Marketing-editable mapping, through the admin or a tag manager. `research_multi_platform_tag_patterns.md`
  covers GTM, CDPs and how course platforms such as Kajabi and Thinkific handle this.
