# Research: referrer code design

Scope note: the consumer is the Django admin only, staff create and assign codes (no partner
self-service portal), and there is no reward/payout mechanic. Several findings below are
established practice for partner- or user-facing self-serve programmes; I flag explicitly where a
finding's rationale depends on self-service or payout and therefore weakens (but rarely
disappears entirely) for FLS.

## Findings most likely to change the design decision

1. **The draft alphabet (`A-Z0-9`) keeps the two most typo-prone pairs (`0`/`O`, `1`/`I`).** A
   code that goes on a printed flyer or is read aloud is exactly the case Crockford's Base32 was
   designed for: it drops `I`, `L`, `O`, `U` from the encoding alphabet, and on *decode* treats
   `O`→`0` and `I`/`L`→`1` as equivalent rather than rejecting them ([Crockford Base32
   spec via iain/crockford](https://github.com/iain/crockford), [base64.sh
   explainer](https://www.base64.sh/crockford32/)). FLS doesn't need full Crockford Base32 (that's
   an *encoding* for structured data); the transferable finding is the **excluded-glyph set**:
   avoid `I`, `O`, `1`/`L` ambiguity, and consider dropping `U` too (Crockford drops it to reduce
   accidental obscenity when codes are randomly generated — less relevant here since FLS codes are
   staff-chosen, but still cheap to keep). A system-generated code should be drawn from an alphabet
   with these excluded; a staff-typed vanity code should still be *validated* against a wider set
   since staff will want to type organisation-related words, but the validator should warn (not
   necessarily block) on ambiguous characters landing in it.

2. **Case sensitivity should not exist at the validation layer — normalise, don't compare
   case-sensitively.** Every referral/promo-code source found agrees on this: "the best practice
   is to normalize codes to uppercase... on the backend... Case sensitivity is the most common
   source of referral code entry failures" ([refgrow.com](https://refgrow.com/what-is-a-referral-code)).
   The normalisation point is the *input boundary* — the query-parameter parser (or the admin form
   that stores the code) — not the storage layer twice-over: store canonical uppercase, and
   uppercase the incoming `ref` value before the table lookup. This means the DB column should
   itself be constrained to the canonical case (e.g. a validator/constraint that rejects lowercase
   at write time) so there is only ever one representation to look up, and no unique-constraint
   trap where `ACME` and `acme` are both saved as "different" codes.

3. **A query parameter is what mature programmes actually ship for exactly this print/social/
   flyer use case — but query strings get silently stripped by intermediate shorteners and
   redirect chains, and that risk is orthogonal to whether the parameter is `ref` or something
   else.** Evidence: "Services like Bitly, TinyURL, and custom short domains can strip UTM
   parameters if not configured correctly... many redirect configurations strip query parameters
   by default" ([bluefroganalytics.com](https://bluefroganalytics.com/blog/utm-parameters-redirects-killing-attribution/),
   [flyn.to](https://www.flyn.to/blog/do-short-links-keep-tracking-parameters)). This is a risk that
   applies whenever *anyone downstream* of FLS's own link (a partner's own link shortener, a social
   platform's link-wrapping, an email client's safe-link rewriter) sits between the click and FLS's
   landing page — it is not solved by FLS choosing a path (`/r/CODE/`) instead of a query parameter,
   because the partner can shorten either form equally. What *does* change is copy-paste
   resilience on FLS's own domain: a path segment survives a user manually re-typing or partially
   copying a URL (e.g. pasting into a browser bar and hitting enter after the domain, or a chat
   client auto-linking only the bare URL) in cases where a `?ref=` suffix commonly gets dropped
   because users perceive "everything after the question mark" as disposable tracking cruft. If
   the partner primarily distributes the link (rather than the code being read/typed
   independently), a short path-based redirect (`https://lms.example/r/ACME/` → sets the cookie →
   302 to the real landing page) is the pattern mature affiliate/referral tooling converges on
   (vanity/branded short links: [bitly.com](https://bitly.com/blog/what-is-a-vanity-url/),
   [refersion.com](https://support.refersion.com/en/articles/5843478-how-to-automatically-create-vanity-urls-for-affiliates)).
   Given the draft's assumption is a query parameter arriving at an existing landing page (not a
   dedicated redirect endpoint), the two are not mutually exclusive: `?ref=` remains the low-effort
   default for embedding in existing marketing copy, and a `/r/<code>/` redirect view can be added
   later as a thin wrapper that sets the same cookie and 302s to `/` (or wherever) without
   restructuring the validation/storage model. This is an inference, not something I found stated
   outright, but it follows from every source treating "the short link" as a redirect layer in
   front of a parameterised destination, not a replacement for the parameter.

## 1. Code format

- **Alphabet.** Every consumer-facing source converges on the same two rules: (a) exclude
  characters that are visually or aurally ambiguous — "avoid O's, zeros, ones, capital I's, and
  lower case L's, as these get confused"
  ([refgrow.com](https://refgrow.com/what-is-a-referral-code)); (b) normalise case on input rather
  than making the code case-sensitive. Crockford Base32
  ([github.com/iain/crockford](https://github.com/iain/crockford)) is the canonical
  ambiguity-safe alphabet for *system-generated* codes: `0123456789ABCDEFGHJKMNPQRSTVWXYZ` — note
  `I`, `L`, `O`, `U` are absent. FLS's draft regex `[A-Z0-9]` still admits `I`, `O`, `1` — worth
  excluding for generated codes; a staff-chosen vanity code will legitimately want to spell an
  organisation's initials or name, which may collide with an excluded letter (e.g. an organisation
  called "IOTA") — the fix there is a *lint/warning* in the admin form, not a hard block, since
  a human enters it once and re-reads it once, unlike a randomly generated string nobody chose to
  proofread.
- **Length.** Common consumer promo/referral codes run 6-10 characters
  ([tapfiliate.com](https://tapfiliate.com/blog/referral-code/),
  [growsurf.com](https://growsurf.com/blog/referral-code/)); the draft's 3-10 lower bound of 3 is
  short for a system-generated code (small alphabet × 3 chars is a small space) but entirely
  reasonable for a *staff-chosen* short vanity code for a well-known partner (e.g. `BBC`, `NHS`).
  Given codes here are staff-assigned to a known, finite set of partner organisations (not
  self-served by end users at volume), the practical constraint is "must not collide with an
  existing code," not "must resist brute-force" (see §6).
- **Case normalisation rule.** "The best practice is to normalize codes to uppercase... on the
  backend, so that if someone shares the code `SARAH20` verbally and the recipient types
  `sarah20`, it should still work... Case sensitivity is the most common source of referral code
  entry failures" ([refgrow.com](https://refgrow.com/what-is-a-referral-code)). This belongs at
  the point the code is *received* (both the incoming `?ref=` value and the admin's create/edit
  form should uppercase before validation/lookup), so storage, comparison and display never
  diverge.
- **The suffix segment (`-XX` to `-XXXXXX`).** I found no authoritative external source describing
  exactly this two-part `CODE-SUBCODE` convention by name, but the *pattern* it encodes — a base
  partner code plus a sub-identifier for campaign, salesperson, or placement — is exactly what
  UTM's `utm_source`/`utm_campaign` split already does at the query-parameter level, and what
  affiliate platforms do with **sub-IDs** appended to an affiliate's base tracking ID (e.g.
  Impact.com, ShareASale, and CJ Affiliate all support a `subid`/`sid` parameter alongside the
  base affiliate ID, precisely so one affiliate can distinguish which of their own placements
  converted). The FLS draft's inline hyphen-suffix is a more compact encoding of the same idea.
  Given the idea doc already proposes separate `utm_*` capture, **the suffix is likely redundant
  with UTM campaign tracking** unless the intent is specifically "sub-codes issued by the partner
  organisation itself to their own downstream contacts" (e.g. an umbrella body handing numbered
  sub-codes to its member schools) — that's a real, named use case (multi-level affiliate/reseller
  sub-IDs) but is a materially different feature (a code that resolves to *both* an Organisation
  and a free-text or FK sub-entity) from a flat code-to-Organisation mapping, and is worth an
  explicit decision rather than folding into the regex unexamined.
- **Vanity vs generated, collisions, reserved words, and offensive/impersonating codes.** Because
  FLS's only actor creating codes is staff via the admin (per the decided scope), the standard
  self-service risks — an end user choosing `ADMIN`, `NULL`, a competitor's brand name, or a slur
  as their own vanity code — **do not apply in their usual form**: there's no open submission path
  for a member of the public to claim a code. The residual version of this risk is narrower:
  a staff member typing a code that accidentally collides with a reserved path segment (`admin`,
  `api`, `static` if codes ever appear in a URL path) or a future built-in code namespace. A
  reserved-words denylist and a straightforward `unique` constraint cover this; a moderation/
  profanity-filter layer (as used for open username registration —
  [cleanspeak.com](https://cleanspeak.com/help-center-article/should-you-filter-and-moderate-usernames))
  is disproportionate here and would be scope creep.

## 2. Relationship to `Organisation.slug`

Reading `freedom_ls/organisations/models.py` in this repo: `Organisation.slug` is a
`SlugField(allow_unicode=True)`, unique per `(site, slug)`, derived on save from `name` ("Derived
on save, never typed" per the field's own comment) and used for URL-safe identification of the
organisation within its site. A referrer code is a **different thing with different constraints**,
and reusing the slug is not a good fit for three independent reasons:

- **Unicode vs restricted alphabet.** `allow_unicode=True` exists specifically so a non-Latin
  organisation name "keeps its own script in the URL rather than reducing to nothing." A referral
  code needs the opposite property — a restricted, typeable-on-a-flyer, speakable-aloud ASCII
  alphabet (see §1). Forcing the slug to also satisfy the code's ASCII/ambiguity constraints would
  break the slug's own stated purpose for any non-Latin-named organisation.
- **Derivation vs assignment.** The slug is explicitly "derived on save, never typed" — it tracks
  the organisation's *name*, and by implication can change if the name changes (nothing in the
  model prevents a rename recomputing the slug, and no code inspected here freezes it once set).
  A referral code must be the opposite: stable for the life of every historical row that
  references it, specifically *not* recomputed when the organisation renames. Tying attribution to
  a field whose job is to track the current name risks silently breaking every outstanding printed
  code and every stored historical redirect if a rename ever regenerates it.
- **Guessability/predictability.** The slug is derived deterministically from the organisation's
  public name, so it is inherently guessable by design (that's fine for a slug, whose job is
  exactly to be predictable and SEO-friendly). A referral code being *equal to* the guessable
  slug removes any distinction between "the organisation's public identifier" and "the credential
  a partner was issued to distribute" — not a security problem here (§6 — no reward, so
  guessability doesn't enable fraud) but it does collapse two conceptually distinct fields into
  one, and forecloses ever having more than one code per organisation (§4) or a code that outlives
  a slug change.

Conclusion (inference, not sourced externally — this is a judgement about *this* codebase): a
separate field is justified. The unique-per-site constraint pattern already used for slug
(`unique_organisation_slug_per_site`) is a directly reusable template for a new
`unique_referral_code_per_site` (or global, if codes should be unique across sites — worth
deciding explicitly since `Organisation` itself is only unique within a `Site`).

## 3. Link shape: query parameter vs path vs subdomain

- **Query parameter (`?ref=CODE`).** Cheapest to embed in existing marketing copy/landing pages
  (no new routes), matches the pattern already used for UTMs in the same idea doc, and is what the
  draft already assumes. Weakness: perceived as disposable "tracking junk" by users who manually
  edit URLs, and vulnerable to any redirect hop in the chain (partner's own shortener, social
  platform's link wrapper, email safe-links) dropping the query string — "many redirect
  configurations strip query parameters by default"
  ([bluefroganalytics.com](https://bluefroganalytics.com/blog/utm-parameters-redirects-killing-attribution/)).
- **Path-based short link (`/r/CODE/`).** What dedicated affiliate/referral tooling converges on
  for the "prints on a flyer / says on air" use case — a short, memorable, branded path that
  redirects to the real destination while setting tracking state
  ([bitly.com — vanity URLs](https://bitly.com/blog/what-is-a-vanity-url/),
  [refersion.com — automatic vanity URLs for affiliates](https://support.refersion.com/en/articles/5843478-how-to-automatically-create-vanity-urls-for-affiliates)).
  Its robustness comes from being a single hop *FLS controls end-to-end*: the code lives in the
  path (survives naive copy-paste better than a query string, which users sometimes truncate at
  the `?`), and the redirect target is decided server-side, so there's no reliance on any
  downstream tool preserving a parameter. Cost: a second concept in the URL space (the redirect
  view) alongside the destination page, and every printed/social placement needs to encode the
  full `/r/CODE/` path rather than appending one parameter to whatever page is already being
  advertised.
  - Note this doesn't eliminate query-string stripping risk *upstream* of FLS (a partner's own
    bit.ly link wrapping `lms.example/r/ACME/` can still get mangled) — it only removes FLS's own
    landing page from needing to preserve the parameter through its own template/canonical-URL
    logic, and gives users a URL that "looks complete" without a query string to discard.
- **Subdomain.** No source found recommending a subdomain (`acme.lms.example`) for this scale of
  programme; subdomains are typically reserved for either a materially different application
  surface (multi-tenant white-labelling) or enterprise vanity domains, and would require DNS/TLS
  provisioning per organisation — disproportionate for an attribution-only feature with no
  partner-facing surface.
- **Recommendation implied by the sources, stated as inference:** ship the query parameter first
  (matches the existing UTM-capture design, zero new routes, correct for a `Site`-scoped
  Django app with `Site`-based routing already in place), and treat `/r/CODE/` as a
  straightforward additive redirect view later if flyer/print distribution proves the query
  string is getting lost in practice — it is not an either/or architectural fork, since the
  redirect view can terminate in exactly the same `?ref=`-carrying URL and reuse the same
  validation/lookup.

## 4. Code lifecycle

- **Deactivate, don't delete, is the dominant pattern.** Stripe's `PromotionCode` object has an
  `active` boolean that can be toggled off and back on (conditional on the underlying `Coupon`
  still being valid), and the `code` string itself is immutable post-creation — Stripe's own
  documented workaround for "I want to reuse this exact code text" is: deactivate the old
  promotion code object, then create a *new* object with the same code string
  ([docs.stripe.com/api/promotion_codes](https://docs.stripe.com/api/promotion_codes)). That is a
  directly transferable pattern for FLS: an `is_active` flag on the code, historical rows keep
  their FK to the (now inactive) code row, and "reissuing" the same code text to a different
  organisation is a new row, not a mutation of the old one's `organisation` FK.
- **Reassignment to a different organisation should be forbidden, not just discouraged.** No
  external source documents reassignment as a supported operation for coupon/promo/referral
  systems — the closest is Coupa's user-deactivation pattern, where a deactivated entity's
  historical relationships are deliberately *not* reassigned automatically, because doing so would
  misattribute the historical record
  ([Coupa lifecycle notes surfaced via search](https://www.stitchflow.com/user-management/coupa/manual)).
  The FLS-specific reasoning is stronger and simpler: if `Code → Organisation` is a live FK and
  that FK is repointed, every historical attribution row that stored only the code (not a
  denormalised snapshot of "organisation as of click time") silently changes which organisation
  it appears to credit. If the attribution row already snapshots the organisation at the time of
  capture (as the idea doc's "written once, never updated" attribution row suggests it might),
  reassignment is less catastrophic but still confusing for reporting ("this code has meant two
  different organisations depending on which month you're looking at"). Simplest rule: a code's
  `organisation` FK is set at creation and never changed; retiring a code means deactivating it
  and, if the same text is wanted for a new organisation, creating a new code row (which needs a
  uniqueness scope that accounts for inactive-but-existing codes — e.g. unique on active codes
  only, mirroring the `one_default_organisation_per_site` partial-unique-constraint pattern
  already used in this exact model file for `is_default`).
- **Multiple codes per organisation.** Nothing in the researched sources forbids this, and the
  suffix-segment discussion in §1 (sub-codes per campaign/salesperson) is itself evidence that
  multiple codes resolving to one entity is a normal shape, whether achieved via a
  one-to-many `Code → Organisation` FK or via the compound `CODE-SUFFIX` pattern the draft
  proposes. If the suffix is *not* adopted, a one-to-many table (multiple `ReferralCode` rows per
  `Organisation`) covers the same need directly and more simply.
- **Deletion.** Given every source above converges on "deactivate, never delete" specifically to
  preserve the audit/attribution trail, and FLS's own stated purpose for the code is exactly that
  trail, hard deletion should not be exposed at all — `is_active=False` is the terminal state, or
  (if the FK is nullable and the historical Organisation itself gets deleted) FLS's usual pattern
  for that would apply, but that is outside this topic's scope.

## 5. Unknown, stale and mistyped codes

The draft says: unknown codes are dropped silently, never stored, never prefilled. Arguments both
ways:

**For silent drop (the draft's position):**
- Simplicity — no new table, no PII/traffic-shape data retained for a code that was never valid.
- Avoids ever surfacing to the visitor that "code XYZ doesn't exist," which is minor UX kindness
  (no error banner on a landing page for a parameter most visitors never look at anyway) — this
  mirrors how the draft treats malformed `v` values (silently default to `a`).

**For recording the attempt (the counter-argument, and I think the stronger one here given FLS's
stated purpose):**
- Real referral/promo systems document a recurring failure mode that is exactly what silent-drop
  hides: "your friend's referral code has reached the maximum number of redemptions" or has
  expired, and the person who mistyped or used a stale code from an old flyer never finds out
  ([getareferral.co.uk](https://www.getareferral.co.uk/what-to-do-if-referral-code-doesnt-work/),
  [waribiki.click](https://waribiki.click/en/articles/referral-code-troubleshooting)). In FLS's
  case there's no end-user-visible failure to fix (no signup blocked, no reward withheld — it's
  silent attribution, not a redemption gate), so the *user* doesn't need to know, but **the partner
  organisation staff issuing codes do** — if a partner's own print run has a typo, or a partner
  keeps distributing a flyer with a code that was deactivated eighteen months ago, nobody
  currently has a way to notice, because the draft's silent-drop discards exactly the signal that
  would reveal it (a spike of `ref=ACEM` hits, or a steady trickle of hits on a code marked
  `is_active=False`).
- This does not require storing anything per-visitor or building a support-facing feature — even
  a minimal unstructured counter (`unrecognised_code → count, last_seen`) or a log-level record
  gives an admin something to check periodically. This is a much lighter proposal than "store the
  invalid code against the visitor" (which the draft is right to avoid — there's no reason to key
  junk data to a specific person's cookie/session).
- The distinction worth drawing explicitly to whoever writes the spec: "never prefilled / never
  attributed to a learner" (which the draft is correct to keep) is a separate decision from
  "never recorded in aggregate for partner-hygiene purposes" (where the draft's blanket "dropped
  silently" arguably throws away a low-cost, high-value signal). I'd flag this as worth revisiting
  rather than treat the draft's silent-drop as settled, since it's framed in the idea doc as an
  implementation detail ("Possible implementation") rather than a firm decision.

## 6. Abuse

Because there is no reward or payout mechanic (per the decided scope), most of the abuse surface
that referral-code literature discusses **stops mattering**, and it's worth being explicit about
which:

- **Enumeration/guessability of the code space.** Matters when a guessed code unlocks a reward
  (a discount, a free month, a payout to whoever "referred" the signup). With no reward, a
  correctly-guessed code just attributes a signup to the wrong (but real) partner organisation in
  reporting — a data-quality nuisance, not a financial exposure. Short codes (3+ chars) are fine
  on this basis; entropy/CWE-331-style "insufficient entropy" concerns
  (referenced generically in enumeration/brute-force literature) are a non-issue here because
  there's nothing to steal by finding a valid code.
- **Self-referral.** Meaningless without a reward — "self-referral" as a named problem exists
  specifically because a user refers themselves (e.g. a second account, or clicking their own
  link) to claim a reward twice. FLS has no reward to double-claim, so this class of abuse has no
  analogue.
- **A partner spamming their own code.** Also not really an abuse vector without a
  reward — a partner driving as much traffic as possible through their own code and being
  over-represented in attribution reporting is the *intended function* of the feature (that's
  what a referral/attribution code is for), not a misuse of it.
- **Bots.** The one abuse vector that *does* still matter, but it's a generic web-traffic-quality
  problem (bot/crawler noise polluting attribution counts), not specific to referral codes — it
  applies equally to UTM parameters, landing-page hit counts, and any other traffic-shape metric
  the idea doc's middleware captures. No referral-code-specific mitigation is implied; whatever
  general bot-filtering FLS applies (or doesn't) to its traffic metrics governs this too.

**Net finding:** the abuse-hardening measures common in referral/promo-code literature (rate
limiting redemption attempts, per-account single-use enforcement, CAPTCHA on submission, entropy
requirements) are all responses to a reward being at stake, and none of them are load-bearing for
FLS's attribution-only use case. The one genuinely relevant residual concern is data-quality (bots,
partner over/under-representation from unrelated causes), which is a general traffic-metrics
problem rather than something the code design itself should solve.

## 7. First-touch stickiness

- **The draft's rule (first-touch, `ref` never overwritten) is the conventional choice for
  partner/affiliate attribution specifically**, as opposed to marketing-channel attribution (UTMs,
  click IDs), which the same draft correctly treats as last-touch. This split matches documented
  practice: "first-touch attribution... credits the originating partner with the conversion
  regardless of whether a different partner delivered the most recent click," while last-touch
  "gives 100% credit to the final interaction... each click from a new affiliate... resets the
  cookie" ([rewardful.com](https://www.rewardful.com/articles/first-touch-vs-last-touch-attribution)).
  The draft applying first-touch to `ref` and last-touch to UTMs/click-IDs in the same cookie is
  itself a documented hybrid pattern, not an invented one — some attribution tooling tracks both a
  first-touch and a last-touch field simultaneously precisely so different downstream questions
  ("who introduced this learner" vs "what campaign converted them") can each be answered correctly
  ([webocreation.com — first-touch vs last-touch UTMs with two cookie fields](https://webocreation.com/first-touch-vs-last-touch-utms-with-cookies-track-with-two-fields-for-better-attribution/)).
- **Visitor arrives via partner A, leaves, returns months later via partner B.** Under strict
  first-touch with no expiry, partner A keeps the credit indefinitely — this is the documented
  trade-off of first-touch, not a bug: "first touch attribution... credits the originating
  partner... regardless of whether a different partner delivered the most recent click"
  ([rewardful.com](https://www.rewardful.com/articles/first-touch-vs-last-touch-attribution)).
  What real programmes conventionally add on top is a **cookie/attribution window** — an expiry
  after which a stale first-touch no longer counts and a fresh visit can establish new
  attribution: "any clicks that occur after that first click are de-duped within the cookie
  duration (which is 30 days by default)... set your cookie length to correspond with your typical
  sales cycle" ([support.getcake.com](https://support.getcake.com/support/solutions/articles/5000545958-understanding-first-touch-vs-last-touch-attribution)).
  The idea doc already proposes a 90-day cookie (`fc_attr`) — that duration *is* the de facto
  attribution window; worth being explicit in the spec that "first-touch, never overwritten" means
  "never overwritten within the 90-day cookie's life," not "never overwritten, ever" — after the
  cookie expires, a new first touch legitimately starts a new 90-day window, and that is the
  documented mechanism by which "partner A gets everything forever" is avoided, not an
  additional feature to design.
- **What partners typically expect/complain about**, per the same first-touch-vs-last-touch
  literature: partners who invest early in awareness (blogs, content, initial referral) want and
  expect first-touch, because last-touch systematically undercredits the awareness-stage referrer
  in favour of whoever happens to close it out — "a customer might find a product through a blog
  from Affiliate A but later complete their purchase using a discount link from Affiliate B...
  with first touch attribution, Affiliate A earns the commission"
  ([rewardful.com](https://www.rewardful.com/first-or-last-touch-attribution)). Since FLS's
  partners are presumably the "introduced this learner" kind (organisations, not
  transaction-closing discount codes), first-touch is the correct default and matches what this
  category of partner conventionally expects. The predictable complaint under first-touch is the
  mirror image: a partner B who put in the effort to bring a returning visitor back (inside the
  cookie window) gets no credit because partner A's stale first touch still holds — this is an
  inherent, accepted cost of first-touch attribution in every source reviewed, not something FLS's
  design is failing to solve; it's the trade-off the draft is knowingly making by choosing
  first-touch for `ref`.

status: ok
