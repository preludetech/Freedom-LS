# Research: best practices for a per-user referral touch timeline and frozen conversions

Scope: windows, dedupe, cookie limits, append-only records, privacy/consent, retention. Builds on
`research_attribution_models.md` (models, window numbers, cookie byte limits, ITP, ICO headline); that
material is not repeated except where a new point depends on it. Statements are marked **sourced**,
**inferred** (my reasoning from sources) or **gap**. Several legal sources are secondary (law-firm and
vendor summaries); the ICO primary text was not retrieved, so a compliance decision should be checked
against ico.org.uk.

## 1. Attribution window versus cookie window

- **Two different clocks (sourced).** The cookie window runs forward from a click; the lookback window
  runs backward from the conversion and decides which earlier touches compete for credit
  (https://ppc.land/lookback-window/). The idea's two settings (`COOKIE_MAX_AGE_DAYS`,
  `ATTRIBUTION_WINDOW_DAYS`) match this split. Best practice is to keep them as separate settings
  even when equal.
- **Window is judged at conversion time (sourced/inferred).** Networks evaluate "was the click inside
  the window when the conversion happened", not "is it inside the window now". The idea's
  `touches_in_play(when=...)` does this. It also means a touch can be valid for an early conversion
  and out of window for a later one; both are correct.
- **Window ages from the click, not the last visit (inferred, consistent with idea).** Most guidance
  says a *new* click resets the clock for the credited partner under last-click. That is not the same
  as a repeat click of the same link extending the original cookie. The idea's non-rolling `max_age`
  is a defensible choice: a rolling cookie never expires for an engaged visitor and the "window"
  stops meaning anything. Gap: no source states this rule explicitly; CAKE's docs suggest same-link
  repeats are treated as duplicates rather than new clicks
  (https://support.getcake.com/support/solutions/articles/13000118613-troubleshooting-click-discrepancies-with-your-partners).
- **Per-source windows exist but are optional (sourced).** `django-attribution` supports per-source
  overrides (see `research_attribution_models.md` section 7). Not needed for a first release; recording
  `occurred_at` per touch keeps the option open because the window is applied at query time, not at
  write time.
- **Keep the window out of the stored touch (inferred).** Because the idea stores raw touches and
  applies the window when resolving, a policy change (30 to 60 days) can be re-run over history for
  *future* conversions without migrating data. The frozen pair deliberately does not move.

## 2. Dedupe of repeat touches

- **Networks dedupe by cookie + same link inside a session (sourced).** CAKE: once a cookie is set,
  repeat clicks on the same offer inside the cookie period are flagged as duplicates, and dedupe applies
  only when the visitor already has the cookie and clicks the exact same link; a click on a *different*
  affiliate's link is a new unique click. Trackier offers a configurable session window in hours for
  duplicate clicks, and notes detection is cookie-based, so it misses browser or device switches
  (https://help.trackier.com/en/articles/6984050-can-i-block-duplicate-click).
- **"Deduplication" in the affiliate industry also means something else (sourced).** impact.com and
  Webgains use the word for resolving *which partner gets paid when several claim the same sale*
  (https://impact.com/partnerships/deduplication-affiliate-marketing,
  https://knowledgehub.webgains.com/home/what-is-webgains-deduplication-solution). That is the
  payout rule, which the idea deliberately leaves to the query writer. Worth keeping the two senses
  distinct in the spec's wording: "skip a repeat touch" versus "choose a winner".
- **Compare against the most recent entry, not the whole list (inferred).** The idea's rule (identical
  seven key values to the last entry) lets A, B, A produce three touches, which is correct for
  last-click: the return to A is the newer fact. Comparing against the whole list would erase it.
  This matches the network behaviour above, where a different partner's click intervenes.
- **Time-bucketed dedupe is the common alternative (sourced: Trackier session window).** Identical
  key within N hours counts as one touch even if another touch intervened. Not adopted by the idea;
  note as a rejected option. Reload and back-button spam are handled by the "identical to last" rule
  without a clock.
- **Dedupe in the database needs a natural key (inferred).** The idea's unique constraint on
  `(site, user, occurred_at, key_hash)` makes a double flush idempotent. Caveat: `occurred_at` must
  round-trip identically through the cookie (`ts`) or a re-flush with a truncated timestamp will
  insert a duplicate. Cookie timestamps should be stored at a fixed precision (whole seconds) and the
  live path should use the same precision, otherwise the constraint dedupes nothing across paths.
- **Live-touch dedupe needs a lookup (inferred, from `answers.md`).** Skipping a live touch identical
  to the user's latest touch costs one indexed query per authenticated tracked GET. This is fine given
  the `(site, user, occurred_at)` index and that only tracked GETs reach it.
- **Bots and link unfurlers (gap).** The fraud sources found do not name a mitigation. Practical
  controls are outside this spec: writing only on GET with tracked params already excludes most
  crawlers that do not execute sessions, but chat link-preview fetchers do issue GETs. For authenticated
  live touches this is low risk (a bot is rarely logged in); for the cookie path an unfurler gets a
  cookie nobody keeps.

## 3. Cookie size and design

Hard limits are in `research_attribution_models.md` section 5 (4096 bytes per cookie including name and
attributes, 50 cookies per domain on Safari/Edge). Additional best practice:

- **Cookies are for an identifier or a short bounded buffer; the database is the record (sourced
  principle, inferred application).** Cookie size guides recommend keeping the payload minimal because
  the cookie is sent on every request to the domain, which costs bandwidth and is a leak surface
  (https://www.browsercookielimits.iain.guru/). A bounded list of ten compact entries is within this
  principle; an unbounded one is not. The idea's cap plus byte-length eviction is the right two-layer
  guard.
- **Evict from the middle, not the ends (inferred).** The idea evicts the oldest entry while the first
  touch lives separately in the frozen keys, so first and latest both survive. Under last-click this is
  what matters. Middle loss only affects position-based or linear models, which the idea does not
  support; say so in the spec so nobody assumes full fidelity from the cookie.
- **Name the lossy point (inferred).** When eviction drops entries, the timeline in the database is
  incomplete in a way nothing records. A conversion's `first_touch` is then the earliest *surviving*
  coded touch, not necessarily the true first. Because the first touch is kept separately this is
  mostly safe, but a `recorded_via=signup_flush` row set may be shorter than what happened. Document it.
- **Signed versus plain (gap).** The existing cookie is plain JSON; a visitor can forge a referral code
  by editing it. For payouts this is the same as typing `?ref=` themselves, so signing adds little
  against the cheapest attack. It matters if tampering with *timestamps* can pull a stale touch into
  window. The flush should clamp `ts` to be no later than now and no earlier than `first_seen`, and
  reject `ts` in the future. (Inferred; the idea validates parseability only.)
- **Prefer HTTP-only and SameSite=Lax (sourced elsewhere; inferred).** The idea already sets the
  cookie server-side, so it is outside Safari's 7-day JavaScript cap. `HttpOnly` plus `SameSite=Lax`
  is the standard setting for a cookie that must survive a top-level cross-site navigation (the
  partner's link) but need not be read by scripts. Check the existing cookie's attributes in the spec
  rather than assuming.

## 4. Append-only records and freezing

- **Immutable ledger-style rows for anything a payment depends on (sourced).** Commission lifecycles
  go Pending, Approved, Reversed, Paid, and the attribution decision is recorded at conversion and not
  recomputed (Tapfiliate payout guide, cited in `research_attribution_models.md` section 2). The idea's
  frozen codes on `Conversion` follow this.
- **Corrections are new rows, not edits (inferred, standard ledger practice).** The idea's `save()`
  guard and read-only admin stop mutation, but a disputed or fraudulent attribution will eventually
  need a way to say "ignore this conversion". The idea has no reversal or void concept, and defers
  payout. Best practice is to leave room for it without building it: either an additive nullable
  `voided_at` set by a *separate* row, or a later `ConversionAdjustment` model. Flag as an open
  question for the payout spec, not this one. Note the idea's own constraint: `QuerySet.update()`
  bypasses the guard, so the guarantee is convention plus admin, not database enforcement. A
  database-level protection (a trigger or revoking UPDATE for the app role) is the strong form;
  recommend naming it as out of scope and the weakness as known.
- **Store the rule inputs alongside the result (inferred).** The idea freezes the codes and the touch
  FKs, but not the window length in force when it resolved. Recording
  `window_days_applied` (or the cutoff timestamp) on the `Conversion` costs one small integer and lets
  an auditor reproduce why a touch was or was not in play, even after the setting changes. Cheap
  and in line with "freeze what a payout rests on".
- **`PROTECT` plus a prune filter (inferred).** Using `PROTECT` so that referenced touches cannot be
  pruned is the right way to make the frozen pair durable, but it also means a user erasure request
  (CASCADE from `User`) will hit `ProtectedError` through `Conversion.first_touch`. See section 5.

## 5. Privacy, consent and data minimisation

### UK PECR / ICO (cookie storage)

- **Affiliate attribution needs consent (sourced).** The ICO's final storage and access technologies
  guidance, published 29 April 2026 (one firm reports 28 April; the date is worth checking), states
  that an affiliate marketer needs consent to use a pixel to track clicks on affiliate links and
  conversions to attribute sales to them
  (https://www.jdsupra.com/legalnews/ico-sets-out-approach-to-storage-access-3822762/,
  https://www.trethowans.com/insights/new-ico-storage-and-access-technologies-aka-cookies-guidance-published-28-april-2026/,
  https://www.cookieyes.com/blog/uk-cookie-guidance-ico-pecr/).
- **Single-purpose rule (sourced).** An exception applies only if the technology serves *only*
  purposes the exception covers; one non-exempt purpose makes consent required for the whole thing.
  Do not rely on bundling attribution with a strictly necessary cookie (session, CSRF).
- **New exceptions are narrow (sourced).** The statistical-purposes exception covers aggregate
  statistics about how a service is used in order to improve it, with clear information and a simple,
  free way to object; the appearance exception covers adapting how a service looks or works to user
  preferences
  (https://www.hunton.com/privacy-and-cybersecurity-law-blog/uk-ico-publishes-guidance-on-storage-and-access-technologies).
  A cookie identifying *who* arrived through a partner link, so a partner can be paid, is not
  aggregate improvement statistics. **Inferred:** neither exception fits referral attribution. The
  Hunton piece does not discuss affiliate use, so this is my reading, not their statement.
- **PECR covers the storing and reading of the cookie, not the database row (inferred).** The
  consent question attaches to the device access: setting the cookie on a tracked landing and reading
  it at signup. A *live* touch recorded for an authenticated user reads no stored device data;
  it records a request parameter against a known account. That path is arguably outside PECR's
  storage-and-access rule but squarely inside UK GDPR (it is personal data about the account). Do not
  treat "logged in, no cookie" as consent-free in a UK GDPR sense: it still needs a lawful basis and
  transparency. Flag this distinction for a lawyer; I did not find a source that addresses it.
- **Lawful basis for the stored timeline (inferred).** Under UK GDPR the usual candidates are
  legitimate interests (Article 6(1)(f); ICO requires a documented purpose / necessity / balancing
  test, https://ico.org.uk/for-organisations/uk-gdpr-guidance-and-resources/lawful-basis/legitimate-interests/what-is-the-legitimate-interests-basis/)
  or consent. Where PECR requires consent for the cookie, the ICO's general view (not retrieved here)
  is that consent for the storage is typically also the right basis for the later processing of what
  it collected; relying on legitimate interests for the database half while consent governs the cookie
  half is contestable. Gap: needs legal input.

### Data minimisation choices already in the idea (endorse)

- No IP, user agent, referer or raw query on touches: right. Click identifiers excluded: right.
- `landing_path` blank for cookie-carried touches: right (paths can carry personal data in some
  deployments).
- Seven short fields only. Consider whether `utm_term` and `utm_content` are needed for payout at all
  (inferred): they exist for ad-optimisation, not partner crediting. If no payout rule reads them,
  dropping them from `AttributionTouch` is the strictest minimisation. The idea keeps them so a future
  rule can be re-run; the spec should state that reason or drop them.
- Data are free text from a URL (inferred). A visitor or a hostile link can put an email address or other
  personal data into `utm_campaign`. Caps help; the admin and CSV export then display attacker-chosen
  strings (CSV injection: cells starting `=`, `+`, `-`, `@`). Best practice is to neutralise formula
  prefixes in CSV exports, or confirm `import-export` settings do. Add to the export requirement.

### Erasure and the frozen record

- **Erasure collides with `PROTECT` (inferred).** On a UK GDPR Article 17 request, deleting the user
  cascades to `AttributionTouch`, which `Conversion.first_touch`/`last_touch` protect. The delete would
  fail. The idea does not say how this resolves. Options: set the FKs to `SET_NULL` (the frozen code
  text survives, the touch row can go, and the unique "frozen" guarantee rests on the copied code
  columns, which already exist for precisely this reason); or keep `PROTECT` and write an explicit
  erasure routine. Since the frozen text columns make the FKs redundant for payout purposes, `SET_NULL`
  looks the lower-friction fit. This is a real design tension to resolve in the spec.
- **Retaining some data after erasure for legal obligations (sourced, secondary).** Where an
  organisation must keep accounting records, UK practice is six years (HMRC default "six years plus
  current"; limitation period under the Limitation Act 1980 is a common basis)
  (https://www.gov.uk/government/publications/hmrc-records-management-and-retention-and-disposal-policy/records-management-and-retention-and-disposal-policy,
  https://sprintlaw.co.uk/articles/how-long-should-you-keep-personal-data-a-uk-guide-to-gdpr-data-retention-periods/).
  This applies to the payment record (commission paid), which is outside this spec. A `Conversion`
  carrying a user email in `target_label` is personal data; a payout record can justify keeping a
  de-identified or pseudonymised form, but that is a payout-spec question.
- **`target_label` holds an email for signups (inferred).** That puts an identifier into a column
  meant to outlive pruning. If `Conversion` rows are meant to be durable and erasure-safe, the label
  for `account_signup` is better left generic ("Account signup") with the user FK providing the
  identity.

## 6. Retention

- **No regulator gives a database retention figure for an attribution timeline (gap, confirmed in the
  earlier research).** The 13-month figure is cookie lifetime guidance.
- **Practical anchors (inferred):** the attribution window (90 days) is the longest period a touch can
  matter to a *new* conversion. After it, an unreferenced touch has no payout purpose; storage
  limitation (UK GDPR Article 5(1)(e)) argues for deleting it. Referenced touches have a purpose for as
  long as the commission may be audited or disputed, which is a payout-programme decision (a common
  anchor is the commission reversal or refund hold period plus an audit allowance, then the six-year
  accounting anchor above for paid records).
- **Defaults beat arguments in docs (inferred).** `answers.md` decides: no default, no schedule, prune
  takes an argument, docs say touches stay until pruned. That matches the existing prune command, but
  the research view is that "stays forever unless an operator acts" is the weakest storage-limitation
  posture. Mitigations that remain consistent with the decision: say in the docs that the sensible
  floor for `--older-than-days` is the attribution window plus the operator's dispute period; show an
  example cron line; and let a system check or a doc note state the operator is the controller
  responsible for setting retention.
- **Retention choices are per operator (inferred).** FLS is installed into other projects; operators
  are the data controllers. The product docs should supply a retention-policy template paragraph
  rather than a number.

## 7. Items worth adding to the spec (summary)

1. Resolve the `PROTECT` versus erasure conflict (consider `SET_NULL`, since frozen code columns hold
   the answer).
2. Store the window actually applied (or its cutoff) on `Conversion`.
3. Fix timestamp precision across cookie and live paths so the unique constraint truly dedupes; clamp
   cookie `ts` values to between `first_seen` and now.
4. Keep `target_label` free of email for `account_signup`.
5. CSV formula-injection handling in the two exports.
6. Note that `QuerySet.update()` bypasses the append-only guard and that DB-level enforcement is out of
   scope.
7. Distinguish the PECR consent question (cookie) from the UK GDPR lawful-basis question (stored
   timeline, including live touches) in the Privacy Obligations text.
8. State that cookie eviction makes the timeline lossy and that the model supports first and last, not
   linear or position-based credit.
9. Docs should give operators a retention floor and an example schedule, though FLS ships none.
10. Reconsider whether `utm_term`/`utm_content` need to be stored per touch.

## Sources

- https://ppc.land/lookback-window/
- https://support.getcake.com/support/solutions/articles/13000118613-troubleshooting-click-discrepancies-with-your-partners
- https://help.trackier.com/en/articles/6984050-can-i-block-duplicate-click
- https://impact.com/partnerships/deduplication-affiliate-marketing
- https://knowledgehub.webgains.com/home/what-is-webgains-deduplication-solution
- https://www.browsercookielimits.iain.guru/
- https://www.jdsupra.com/legalnews/ico-sets-out-approach-to-storage-access-3822762/
- https://www.trethowans.com/insights/new-ico-storage-and-access-technologies-aka-cookies-guidance-published-28-april-2026/
- https://www.cookieyes.com/blog/uk-cookie-guidance-ico-pecr/
- https://www.hunton.com/privacy-and-cybersecurity-law-blog/uk-ico-publishes-guidance-on-storage-and-access-technologies
- https://ico.org.uk/for-organisations/uk-gdpr-guidance-and-resources/lawful-basis/legitimate-interests/what-is-the-legitimate-interests-basis/
- https://www.gov.uk/government/publications/hmrc-records-management-and-retention-and-disposal-policy/records-management-and-retention-and-disposal-policy
- https://sprintlaw.co.uk/articles/how-long-should-you-keep-personal-data-a-uk-guide-to-gdpr-data-retention-periods/

status: ok
