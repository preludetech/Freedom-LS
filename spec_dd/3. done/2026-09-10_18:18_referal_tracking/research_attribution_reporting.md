# Research: what makes attribution data actually usable

## Findings that would change a design decision

1. **Normalise `utm_source`/`utm_medium`/`utm_campaign` at write time, not read time.** Case and
   spelling drift is the single most common cause of attribution data being useless (`Facebook`,
   `facebook`, `FaceBook`, `fb`, `FB `, `facebook%20ads` all landing as distinct values). If the row is
   write-once with no reprocessing path, any drift baked in at capture time is permanent — there is no
   later "merge these rows" operation the way there is in a event-log system. Store both a `raw_*` value
   (exactly what arrived, for audit/debugging) and a `source`/`medium`/`campaign` normalised value
   (trimmed, lower-cased, URL-decoded) used for filtering and grouping. Read-time normalisation (e.g. a
   admin `list_filter` that groups case variants) is much weaker here because Django admin filters do
   exact-match on stored values — messy stored values means a fragmented, useless filter dropdown.

2. **This design cannot answer "what is our conversion rate" or "what channel converts best," and the
   idea document should say so explicitly rather than let stakeholders assume it does.** A write-once
   row per *signed-up user* has no denominator (no record of visits/clicks that didn't convert), so
   there is no rate, no funnel, no multi-touch, and no time-to-signup. It can only answer counting
   questions ("how many signups came from X"), not efficiency or comparative-performance questions
   ("which channel performs best per visitor"). This is the most common thing marketing/partnerships
   people actually want and the most common thing this design cannot give them — worth a one-line
   caveat in the idea doc so it isn't rediscovered as a bug later.

3. **The admin changelist is the entire interface — so `list_filter`, `search_fields`, and
   `date_hierarchy` are not incidental, they are the whole product.** For this to answer the
   commonly-asked questions without SQL, the changelist needs: `date_hierarchy` on the first-seen
   timestamp; `list_filter` on `utm_source`, `utm_medium`, `utm_campaign`, and `organisation`
   (referrer/partner code) — not on `gclid`/`fbclid`/cookie values, which are high-cardinality and
   useless as filters; `search_fields` covering the user's identifying field, `utm_campaign`, and the
   referrer/partner code; and list_display columns showing normalised source/medium/campaign,
   organisation, landing path, and first-seen date so the two most-asked questions ("signups by
   campaign in a date range" and "signups by partner") are answerable by clicking filters, not typing
   queries.

4. **CSV formula injection is a real, specific risk here because several of the stored fields are
   attacker-controllable query-string values** (`utm_campaign`, `utm_content`, `utm_term`, referrer
   code, `Referer` header) that get exported verbatim into a spreadsheet a human opens. Any stored value
   beginning with `=`, `+`, `-`, `@`, or a tab/CR that survives into the CSV can execute as a formula in
   Excel/LibreOffice when opened. This needs handling in the export code specifically (prefix such
   cells, e.g. with a leading `'`, or escaping character), separate from and in addition to normal CSV
   quoting/escaping. See OWASP: https://owasp.org/www-community/attacks/CSV_Injection

5. **Represent "no attribution data" honestly, not as a blank/null column.** Direct/organic entry with
   no referrer and no UTMs is typically the largest single bucket in real attribution data — often
   30–50%+ of traffic in comparable systems — and mostly is *not* garbage, it's dark social (links
   pasted into WhatsApp/Slack/email, brand-name searches, typed URLs) plus broken/stripped-parameter
   arrivals. If the admin shows this as an empty cell it looks like a missing/failed row; a filterable
   literal value (e.g. `direct`) in `list_filter` lets it be counted and reported on like any other
   channel rather than being invisible or, worse, looking like a data-quality bug.

---

## 1. Questions signup attribution data is actually asked to answer

Ranked roughly by how often they come up in marketing/partnerships operations (based on how comparable
tools such as Plausible, PostHog, and affiliate-tracking products such as FirstPromoter structure their
reporting around these exact axes):

1. **Signups per campaign / source / medium over a period** — "how many people signed up from the
   October LinkedIn campaign," "how did email vs. paid social compare last quarter." The single most
   common question; it's a count with a date range and a group-by.
2. **Signups per partner/referrer organisation** — "how many signups did Partner X refer this month,"
   often tied to a commercial agreement. This is the second most common question and the reason the
   `Organisation`-linked referrer code exists at all.
3. **Which channel/source produced signups that went on to do something valuable** (register for a
   course, complete a course) — the join-to-outcome question. Commonly asked, but requires the
   attribution row to be joinable to progress data (see §5) — it is not answerable from the attribution
   table alone.
4. **Where did a specific user come from** — a one-off lookup ("this learner says a colleague referred
   them, does that match our records"), typically via search, not a report.
5. **Conversion rate by channel** ("what fraction of people who clicked this ad signed up") — commonly
   *wanted*, but requires visitor-level (not just signup-level) data, which this design does not
   capture. See §2.
6. **Time-to-signup / lag from first click to registration**, and **multi-touch paths** ("they clicked
   the ad, then came back later via a Google search and signed up") — asked by more sophisticated
   marketing teams, essentially never answerable without event-level history.
7. **Cost-per-acquisition by campaign** — requires joining to ad-spend data external to this system;
   only meaningful if utm_campaign/utm_source values are clean enough to match spend records
   campaign-for-campaign (see §4).

## 2. What a single write-once row per user can and cannot answer

**Answerable:**
- Counts and group-bys over signups: per source, medium, campaign, content, term, organisation,
  landing path, and date/date-range (all of §1.1, §1.2, and the "lookup a specific user" case §1.4).
- Simple joins forward in time to outcome data, provided the attribution row carries a stable key to
  the user (see §5).
- Distinguishing paid-click arrivals from organic/direct/referral arrivals, if `gclid`/`fbclid`
  presence is treated as a signal even when UTMs are absent (ad platforms increasingly favour click IDs
  over UTMs for their own attribution — see Matomo's note below).

**Structurally impossible, and worth naming explicitly rather than letting someone infer it works:**
- **Conversion rate of any kind.** There is no record of visits, clicks, or page views that did not
  result in a signup — no denominator. "What fraction of Facebook ad clicks converted" cannot be
  computed; only "how many signups had Facebook ad UTMs" can be.
- **Multi-touch attribution.** A user who saw an ad, then later searched and clicked an organic result
  and signed up, is represented as one row with one set of parameters (whatever landed on the signup
  page, or whatever was first captured — a first-touch/last-touch choice made once at write time, see
  below). The other touches are invisible; there is no "touchpoint 1, touchpoint 2" sequence stored.
- **Time-to-signup / lag analysis.** Only a first-seen timestamp exists, not a click timestamp separate
  from a signup timestamp for the same visitor across multiple sessions, so "how long between first ad
  click and signup" cannot be derived unless first-seen genuinely is the first click and the account
  creation timestamp is captured elsewhere and joined (feasible, but not from this table alone).
- **Anything about visitors who bounced.** By definition, only signed-up users get a row.

A related decision the idea document should make explicit even though it's a decision, not new
research: whether the single row captures **first-touch** (first-seen values, frozen even if the user
returns later via a different channel) or **last-touch** (values from the session in which they
actually signed up). PostHog's model is instructive here — it keeps *both* by storing `initial_utm_*`
(first-touch, backfilled once and frozen) and `utm_*` (last-touch, latest values) as separate
properties on the same person record
(https://posthog.com/docs/data/utm-segmentation). A write-once single-row design forces a choice
between the two; "first-seen" as specified favours first-touch, which is the more common choice for
partner/campaign-credit questions but throws away last-touch entirely — worth confirming that's
intended, since "signups per campaign" usually means "credit the campaign that actually drove the
signup," which is more often a last-touch question in practice.

## 3. Consequences of admin-only, and what the changelist needs to expose

What people do when attribution lives only in an admin changelist plus CSV, in practice: they use the
changelist for quick "how many / which ones" checks during the period, and they export to CSV and do
the actual grouping/summing in a spreadsheet (pivot table) whenever the question is anything beyond a
single filter combination. That means the changelist's job is to get to the *right slice* quickly, and
the CSV's job is to be pivot-table-ready once there.

Concretely, for the common questions in §1 to be answerable without SQL:

- **`date_hierarchy`** on the first-seen timestamp — this is what lets "signups in October" be a click
  path rather than a date-range query typed by hand.
- **`list_filter`**: `utm_source` (normalised), `utm_medium` (normalised), `organisation` (partner
  referrer), and — if a fixed campaign taxonomy stabilises — `utm_campaign`. Do **not** put `gclid`,
  `fbclid`, `_ga`/`_fbp`/`_fbc`, IP, or user agent in `list_filter`: these are high-cardinality
  per-visitor values, and a filter dropdown with thousands of unique entries is worse than no filter
  (Django admin will also warn/perform badly on high-cardinality `list_filter` fields).
- **`search_fields`**: the user's email/identifying field (so "look up this one signup" works),
  `utm_campaign`, `referrer_code`/organisation name, and `landing_path`.
- **`list_display`**: normalised source, medium, campaign, organisation (if present), landing path,
  first-seen date — the columns someone scans to sanity-check a filtered list before exporting. Raw/dirty
  values, click IDs, cookie values, IP, and user agent belong in the detail view only, not the list
  columns — they add noise without helping the "which campaign/partner" scan.
- **CSV export** action on the changelist queryset, so the export always matches whatever is currently
  filtered — this is what makes admin-only viable at all for period/campaign-scoped questions, since
  the person doing the asking filters first, then exports just that slice.

## 4. The messy-data problem

This is where most of the risk in this feature lives, because campaign parameters are free-text query
parameters set by whoever built the link, not a closed vocabulary enforced anywhere upstream.

**Case and spelling drift.** GA4 and most analytics platforms treat UTM values as case-sensitive and do
no normalisation, so `Facebook`, `facebook`, `FACEBOOK` land as separate values and fragment reporting —
this is called out as one of the most common causes of "my numbers look worse than reality" in campaign
reporting (https://missinglinkz.io/blog/utm-case-sensitive-ga4/,
https://www.digitalapplied.com/blog/utm-governance-campaign-taxonomy-2026-tracking-reference). Plausible
addresses this in its own dashboard by automatically consolidating `utm_source` variants in its
top-level Sources view, while leaving other UTM fields (medium, campaign, content, term) unmerged
because case variance there is harder to disambiguate automatically
(https://plausible.io/blog/utm-tracking-tags). The practical takeaway for a write-once row: normalise
`source`/`medium`/`campaign` at write time (trim, lower-case) and keep the raw value alongside for
audit — normalising only at read time (e.g. in an admin filter) doesn't work well because Django admin
`list_filter` values are exact-match against what's stored, so unnormalised storage still fragments the
filter dropdown.

**Whitespace, trailing punctuation, URL-encoding artefacts.** `%20`, `+` (which decodes to a literal
space in query strings), trailing slashes/periods copied from a shared link, and stray whitespace from
copy-paste are common and should be resolved by URL-decoding and trimming before storage, not left for
a human to notice in the CSV.

**No agreed vocabulary for `utm_medium`.** Google's own documented values for GA4's Default Channel
Grouping are `organic`, `cpc`, `email`, `social`, `referral`, `affiliate`, `display` (plus grouping
recognises variants like `paid_social`, `banner`, `video`, `push`); anything outside that set doesn't
resolve to a known channel and effectively becomes "Unassigned" in GA4
(https://accs-net.com/glossary/medium/, https://www.shopify.com/blog/utm-parameters). Enforcing a closed
set at write time (reject or normalise-into-the-set) is defensible and low-cost since the field feeds a
filter dropdown that only stays useful if bounded; the tradeoff is that a legitimate but unanticipated
medium either gets rejected (annoying for whoever built the link) or silently bucketed as "other" (loses
information). A closed set with an explicit `other` fallback that preserves the raw value is the usual
middle ground.

**Self-referral.** The site's own domain arriving in the `Referer` header (e.g. a redirect through the
site's own login/checkout flow) is a well-known contaminant in referral reporting — Google Analytics'
own documentation addresses it with a referral-exclusion list precisely because self-referrals
overstate "referral" traffic and understate whatever the real originating source was
(https://support.google.com/analytics/answer/6350128). The more damaging variant for a
signup-attribution use case is **internal links carrying stale UTM parameters**: if any internal page
(a shared/bookmarked page, an old email, an internal nav link) carries UTM parameters from a past
campaign, clicking it overwrites the real originating source with the stale campaign
(https://support.google.com/analytics/answer/6350128). If first-seen/first-touch is the chosen model,
this matters less (only the first visit's parameters count); if last-touch is used, this is a live
data-integrity problem worth flagging.

**The "direct / none" bucket.** In mainstream analytics this is typically the largest single bucket —
GA4 buckets any session it can't attribute a source/medium to as `(direct)/(none)`, and industry
commentary attributes a large share of it to "dark social" (links pasted into WhatsApp, Slack, email,
private DMs) rather than genuine direct navigation
(https://www.seerinteractive.com/insights/direct-traffic-is-dark-traffic-and-thats-ok,
https://odd.dog/blog/how-to-determine-what-google-analytics-directnone-traffic-is-from/). It should be
stored as an explicit, filterable value (e.g. a literal `direct` in the normalised source field) rather
than left null — a null column reads as "we failed to capture this" rather than "this person arrived
with no attribution data," and a null can't be filtered/counted in the admin the way a value can.

**Bot and scanner traffic.** Automated scanners, link-preview crawlers (Slack/Discord/WhatsApp
unfurling a shared link), and referral-spam bots will hit signup-adjacent URLs and, if they happen to
carry query parameters, can pollute campaign values with gibberish
(https://databox.com/google-analytics-bot-traffic-guide,
https://searchengineland.com/guide/spam-traffic). Because this table is write-once *per signed-up user*
(not per visit), the practical exposure is much smaller than in a visit-log system — a bot can't sign
up — but the `Referer`/IP/user-agent fields captured alongside a genuine signup can still carry crawler
noise if a signup flow is proxied through a bot-driven test/monitoring tool; this is a minor,
low-priority risk given the write-once-per-user model, not a design blocker.

## 5. Joining to outcomes

Conventional outcome measures for a learning platform, in increasing order of commitment: **registered
for a course** (enrolled/joined a cohort), **started** (first progress recorded on any topic),
**completed** (course marked complete). For "which channel produced learners who went on to complete a
course" to be answerable later without a schema redesign, the attribution row needs a **stable,
join-able key to the user** (the FK to the user model already implied by "once per signed-up user" is
sufficient) and nothing else — the join happens by querying learner_progress/learner_management data
filtered by users whose attribution row matches a given source/campaign/organisation. The attribution
row does **not** need to duplicate or cache outcome state (e.g. a denormalised "completed" boolean) —
that would go stale and violate the general principle of not repeating data that already lives
elsewhere in the system. The only design requirement here is: keep the FK to the user as the join key,
and don't scope attribution data by site/cohort in a way that would prevent joining across the
site-aware user model to registration/progress records later.

## 6. How comparable products present this

- **Plausible** — a Campaigns report broken down by UTM Medium/Source/Campaign/Term/Content tabs,
  filterable and combinable with Goals (conversions). Auto-consolidates `utm_source` case variants but
  not other UTM fields. https://plausible.io/blog/utm-tracking-tags,
  https://plausible.io/docs/manual-link-tagging
- **PostHog** — stores both frozen first-touch (`$initial_utm_source` etc., set once and never
  overwritten) and live last-touch (`utm_source` etc., updated per session) as person properties, so
  operators can pick either model per-report rather than the system forcing one.
  https://posthog.com/docs/data/utm-segmentation
- **Matomo** — does *not* auto-capture `gclid`/`fbclid`/`msclkid` by default; they must be explicitly
  captured as custom dimensions, and Matomo's own guidance notes ad platforms increasingly favour their
  proprietary click-ID parameters over UTMs for their own attribution loop, so both are commonly
  captured side by side rather than one replacing the other.
  https://matomo.org/faq/reports/how-to-track-ad-click-ids-in-matomo/,
  https://partialleads.com/gclid-vs-fbclid-vs-utm-parameters-whats-the-difference — Matomo also flags a
  privacy/consent obligation attached to storing click IDs, relevant to this design's storage of
  `gclid`/`fbclid` and `_ga`/`_fbp`/`_fbc` cookie values.
- **FirstPromoter / Rewardful** (partner/affiliate referral tools, the closest analogue to the
  `Organisation` referrer-code piece of this feature) — track referral links, coupon/referrer codes,
  and direct-URL attribution per partner, with a configurable first-click-vs-last-click attribution
  window, and report breakdowns by campaign, referrer, and traffic source rather than raw event logs.
  https://firstpromoter.com/features/tracking, https://docs.firstpromoter.com/api-reference-v1/tracking-api/leads-and-signups
  — the common complaint pattern in this product category is exactly the first/last-touch ambiguity and
  attribution-window question flagged in §2 above, not the underlying data model.

## 7. What the CSV export needs

- **One row per signed-up user** (matching the underlying model — no denormalisation needed since it's
  already one row per user).
- **Column set**: normalised source/medium/campaign/content/term, organisation/referrer code, landing
  path, `Referer`, first-seen timestamp, click IDs, cookie values, IP, user agent — i.e. the full row;
  admin-list columns can be a curated subset (§3) but the export is the "give me everything" path so it
  should not silently drop fields someone might need for a one-off investigation.
- **Date formatting**: ISO 8601 (`YYYY-MM-DD` or full timestamp) rather than locale-dependent formats —
  avoids the classic Excel auto-conversion problem where dates get silently reformatted or
  misinterpreted depending on the opening machine's locale.
- **Encoding**: UTF-8 with a BOM if Excel-on-Windows is a realistic consumer (Excel misdetects encoding
  without a BOM and can mangle non-ASCII characters, e.g. accented partner-organisation names); standard
  CSV quoting (RFC 4180 — quote fields containing commas, quotes, or newlines, double up embedded
  quotes) via Python's `csv` module handles the escaping mechanics correctly by default.
- **CSV formula injection** — the specific, non-generic risk here: `utm_campaign`, `utm_content`,
  `utm_term`, and referrer/organisation-adjacent free text are attacker-controllable (anyone can craft a
  link with `?utm_campaign=%3D2%2B2` etc.), and if such a value is exported verbatim into a cell
  beginning with `=`, `+`, `-`, or `@`, spreadsheet software executes it as a formula on open —
  OWASP's guidance is to prefix such values (commonly with a leading apostrophe) before writing them to
  the CSV cell (https://owasp.org/www-community/attacks/CSV_Injection,
  https://owasp.org/www-project-web-security-testing-guide/latest/4-Web_Application_Security_Testing/07-Input_Validation_Testing/21-Testing_for_CSV_Injection).
  This needs to be applied to every user-influenced text field in the export, not just the obviously
  "content" ones — `landing_path` and `Referer` are equally attacker-controlled.

status: ok
