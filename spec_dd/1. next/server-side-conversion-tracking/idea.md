# Server-side conversion tracking

Send FLS's conversion events from the server as well as from the browser: Meta's Conversions API,
TikTok's Events API and Google's Measurement Protocol, for GA4 and Ads. Browser tags lose events to
ad blockers and browser privacy features. Each platform recommends running a server route next to
the browser tag, with the two deduplicated.

This follows `tracking-pixels`, which adds the Meta and TikTok browser pixels, and depends on it.
`tracking-pixels/research_meta_pixel.md` §4, `tracking-pixels/research_tiktok_pixel.md` §4 and
`tracking-pixels/research_multi_platform_tag_patterns.md` (deduplication) cover what each platform
expects.

Open questions for research:

- Deduplication. Meta and TikTok need the same `event_id` on the browser and server copies of an
  event. TikTok also expects a gap between the two copies.
- Click IDs and cookies (`fbclid`/`_fbp`/`_fbc`, `ttclid`/`_ttp`, GA's `client_id`), which only
  exist in the browser. `referral_tracking` already captures some of them for signup attribution.
- Access tokens and API secrets, one per platform.
- Whether to send hashed email for better match quality. FLS sends no email, name or phone number
  anywhere today, and hashing is pseudonymisation, not anonymisation.
- Moments that happen away from the learner's browser, such as staff and cohort registrations, which
  the browser tags never see.
