# Tracking where learners come from

## The problem

FLS records nothing about how a learner found it. An operator running adverts and working with
partner organisations cannot tell which of them produced a signup, and has no way to settle a
partner's claim that they sent the traffic.

## What we are building

Two things, both read only in the Django admin.

One `SignupAttribution` row per signed-up `User`, recording where that person came from, written once
at signup. And a `FirstTouchCount`, a daily tally of how many people arrived through each campaign,
advert and partner in the first place. The tally is what makes the attribution rows mean anything:
without it you know a campaign produced eleven signups but not whether that came off a hundred
arrivals or ten thousand.

Arrivals come from two places the operator controls:

- **Adverts.** A landing URL carries an advert code, an opaque identifier like `P5H2B3C8` naming one
  advert.
- **Referrer codes.** A code issued to a partner so their traffic is identifiable. A referrer code
  belongs to an `Organisation`.

Alongside those, the row carries the standard campaign parameters and click identifiers, so paid
traffic carrying no advert code of ours is still attributable.

## First touch, and only first touch

The values are frozen at the visitor's first landing and never overwritten. Someone who arrives via
a partner in January and via a paid ad in February keeps January's row. Partner, campaign and landing
path then all describe the same visit, so the row is one coherent account of how the person arrived
rather than a blend of two.

The window is the cookie's 90-day life, which is GA4's own default. "Never overwritten" means never
within those 90 days. Once the cookie expires the next arrival establishes a fresh first touch, and
that expiry is what stops a partner owning a visitor forever. It is not a separate thing to build.

The cost is that "which campaign converted them" becomes unanswerable. That is accepted.

## How the values survive until signup

A first-party cookie carries them. It is set on a GET that arrives with at least one tracked
parameter and on no other request, so ordinary traffic is untouched. It is signed, `HttpOnly`,
`SameSite=Lax`, `Secure` outside development, and host-only. An FLS `Site` is one domain, so landing
and signup happen on the same host.

**The cookie is the only durable store.** Nothing writes to the session on a landing GET. Doing so
would force a session row and a session cookie onto every anonymous visitor carrying a query
parameter, bots included, and the session expires after two weeks against the cookie's ninety.
Someone who lands in March and signs up in May must still be attributable.

**The row is written on the signup POST**, from the request that submitted the form. It cannot be
written at email confirmation. Verification is mandatory, so the confirmation link is often clicked
on a phone, in a different browser from the one that landed, where the cookie does not exist. That is
the normal path, not an edge case. FLS already writes `LegalConsent` this way, at signup, from a
request that has both the cookie and the new user.

Every signup gets a row. A visitor who arrived with nothing tracked is recorded as `direct`, not as
an absent row or a column of nulls. Otherwise "we have no idea where this person came from" looks
identical to a capture bug, and cannot be counted or filtered like any other channel.

## What the row holds

Frozen at first landing: the advert code, the referrer code as it was seen plus the `Organisation` it
resolves to, `utm_source`, `utm_medium`, `utm_campaign`, `utm_content`, `utm_term`, `gclid`,
`gbraid`, `wbraid`, `fbclid`, the landing path, the `Referer`, the raw query string, and the
first-seen timestamp.

Taken from the signup request itself: the `_ga`, `_fbp` and `_fbc` cookie values when the deployment
runs Google Analytics or the Meta Pixel and they are present, the client IP, and the user agent.

Three entries in that list are decisions rather than inventory.

**`gbraid` and `wbraid` are in from the start.** Safari's Private Browsing strips `gclid`, `fbclid`
and `msclkid` from URLs before the page loads, and those two exist precisely to survive it. `gclid`
alone under-counts Safari traffic, and the gap is widening. `msclkid`, `ttclid` and `li_fat_id` stay
out until someone actually runs those platforms.

**The `Referer` is corroboration, not a source.** Browsers now default to
`strict-origin-when-cross-origin`, so a genuine external referral yields the partner's origin and
nothing more. Good for confirming a referrer code came from where it should have. Worthless as a
primary signal.

**The raw query string is stored once**, truncated, instead of a raw copy of every parsed field. It
is the only way to work out later why a partner's link builder produced something unparseable.

Values arriving from a URL are attacker-controlled. Capture trims them, URL-decodes them, strips
control characters and truncates. `utm_source` and `utm_medium` are lower-cased, because `Facebook`,
`facebook` and `FaceBook` otherwise fragment the one admin filter that matters. `utm_campaign`,
`utm_content` and `utm_term` keep their case, which is often meaningful. Where a parameter appears
twice in one URL, Django's own last-value-wins applies.

The client IP comes from the resolver FLS already uses for `LegalConsent` and django-axes, not from
reading `X-Forwarded-For` directly. Worth knowing about that resolver before anyone investigates the
data: behind a proxy with no trusted header configured, it falls back to `REMOTE_ADDR`, which is the
proxy's own address and therefore identical on every row. That fails quietly.

The row keys on `User`, not `Learner`. Attribution is a fact about the account, established the
moment it is created, before the person is associated with any organisation, and one person may later
hold several `Learner` rows. It is a `SiteAwareModel` like everything else.

## Referrer codes

A referrer code is a field on `Organisation`, unique within its `Site`. Uppercase, no separator
segment, drawn from an alphabet that excludes `I`, `O`, `L` and `U`. Those are Crockford's
exclusions, and they are what lets a code survive being read down a phone line or printed on a flyer.
Incoming codes are uppercased before lookup, so a partner who writes theirs in lower case still
works.

It is a new field, not the existing `slug`. The slug is derived from the organisation's name on save
and allows unicode, so it can change under a rename and can be non-ASCII. Both are fatal for
something printed on material that stays in circulation for years.

Two consequences follow from the code living on `Organisation`, and both are worth stating rather
than discovering later.

**An individual referrer needs an `Organisation` row.** A person referring learners is represented as
an organisation on the site. That is what `Organisation` already is, a grouping inside a site, but it
does mean issuing a code to a person is no lighter an act than issuing one to a company.

**One code per organisation, and the row must not depend on the field surviving.** Because the code
is a field rather than its own table, clearing or changing it would silently rewrite history if the
attribution row held only a foreign key. So the row stores both the code string it saw and the
`Organisation` it resolved to at the time.

An unrecognised code is never attributed to a learner and never prefilled, so a stranger cannot
credit themselves to a partner by inventing one. The attempt is still counted, in the first-touch
tally below.

Checking the code at landing rather than at signup is what makes that counting possible. It is the
only database read on the capture path, it happens only on requests carrying a referrer code, and it
needs the current site already resolved, since `Organisation` is scoped to one. A code that fails the
check never enters the cookie.

No reward is attached to a referrer code, so most of what the referral literature worries about does
not apply. Guessing a valid code misattributes a signup rather than paying anyone, and a partner
driving traffic through their own code is the feature working.

## Advert codes

An advert code is stored as it arrives, trimmed and truncated like everything else, but validated
against nothing. There is no advert table and no admin surface for creating adverts. Whoever runs the
campaigns keeps the list of codes outside FLS and reconciles against the export.

The trade-off is that the admin shows `P5H2B3C8` rather than "September Facebook carousel", and a
mistyped code looks the same as a real one. A table can be added later without changing what is
captured.

## Counting first touches

`SignupAttribution` exists only for people who signed up, so by itself it has no denominator. A
`FirstTouchCount` row supplies one: per site, per day, per attribution key, incremented once each
time a new attribution cookie is minted.

Because the cookie is minted exactly once per visitor per 90 days, the tally counts unique first
touches rather than raw hits, which is the denominator worth having. Signups from
`SignupAttribution` over first touches from `FirstTouchCount`, both grouped by campaign, gives
conversion rate per campaign. That is the question people ask most and the one this feature would
otherwise have had no answer to.

It holds no personal data. No visitor identifier, no IP, no user agent, no row per person. That is
the point of doing it this way. A landing record keyed to an individual would be pseudonymous data
about someone who never signed up, never saw a privacy notice, and has no account to hang a deletion
request on, which is a worse position than the one this feature is already in rather than a better
one. The tally also costs one write per cookie mint instead of one per landing.

It subsumes the unrecognised-code problem too. A referrer code that fails validation never enters the
cookie, but it still increments a row recording the code as seen and the fact that it did not
resolve. That is how anyone finds out a partner's print run has a typo in it, or that a flyer bearing
a code retired eighteen months ago is still pulling traffic.

Two things about the tally need deciding in the spec.

**The key can be forced to explode.** It includes campaign values typed by whoever crafted the URL.
Someone sending random `utm_campaign` values while discarding cookies between requests mints a fresh
first touch every time and creates a new row every time. The key space has to be bounded somehow,
whether by capping distinct new keys per day, counting only values matching a known advert or
referrer code, or something else.

**Bots inflate it.** Crawlers and link unfurlers mostly discard cookies, so each visit reads as
another first touch. The denominator runs high and conversion rate therefore reads low. It is a
usable number for comparing campaigns against each other, not an accurate absolute one, and the admin
should not dress it up as more than that.

## The admin is the whole interface

There is no report, no dashboard and no partner-facing view. The changelist and its export are what
the operator gets, which makes the filters the product rather than a detail. The two questions people
actually ask are "how many signups came from this campaign last month" and "how many did this partner
send". So the changelist needs a date hierarchy on first-seen, filters on source, medium, campaign
and organisation, and search across the learner's email, the campaign and the referrer code. Click
identifiers, cookie values, IP and user agent are near-unique per visitor. They belong on the detail
view, never in a filter.

The tally gets its own changelist, filtered and date-hierarchied the same way, so "how many people
did this campaign bring in" and "how many of them signed up" are two screens rather than a report
someone has to build. Both are read-only in the admin, the way `LegalConsent` is.

**The export has to escape formula characters.** A value beginning with `=`, `+`, `-` or `@` executes
when the CSV is opened in Excel or Sheets, and `utm_campaign`, the landing path, the `Referer` and
the referrer code are all typed by whoever crafted the URL. This is the one consumer this feature
has, and the values reaching it come from strangers. FLS has no existing export to inherit escaping
from.

## What this deliberately cannot answer

Conversion rate per campaign works, off the tally. Anything needing a per-person history does not.
There is no multi-touch path and no time from first click to signup, because nothing connects a
particular landing to the particular person who later signed up. The denominator also cannot be
sliced by anything outside the tally's own key, so questions like "what is the conversion rate for
people who landed on this specific page" have no answer.

All of that is the deliberate consequence of not keeping per-visitor landing records. It is worth
knowing before someone asks, because the missing pieces are the ones people assume attribution data
comes with.

Joining forward to outcomes stays possible. Which channel produced learners who registered for a
course, started one, or finished it can be answered later, because the row keys on the user and the
progress data is reachable from there. The row should cache none of that. It would go stale.

## Deferred, with the reasons

Neither of these is dropped. Both get their own spec.

**A per-`Site` switch for attribution capture.** Capture is on by default in this work, with no way
to turn it off. The switch belongs beside `SiteSignupPolicy`, since one operator on a shared install
may have a consent mechanism covering this and another may not.

**Erasure and anonymisation.** This work captures and stores. It ships no path to remove or anonymise
a row. "Written once, never updated" here means no in-place edits through the normal write path, not
that the data can never be removed.

## What capturing this obliges the operator to do

FLS is installed into other people's projects, and the operator is the data controller. The whole row
is personal data under GDPR and POPIA the moment it exists, because every field in it is keyed to a
named account. Three things follow that a downstream operator has to know, and that FLS's
documentation therefore has to say.

**The attribution cookie is very unlikely to be "strictly necessary"** under ePrivacy and PECR. It
serves the operator's commercial interest, not a service the visitor asked for, which is the actual
test. In the EU and UK the safe assumption is that it needs consent like an analytics cookie.

**Reading a `_ga`, `_fbp` or `_fbc` cookie is itself regulated.** Article 5(3) covers gaining access
to information already stored, not only storing it. A downstream banner saying "we use analytics
cookies" does not obviously cover a second application copying that identifier into a permanent
record against the person's name. That is a different purpose, and purpose limitation is where it
bites.

**A DPIA is likely required**, not merely prudent, because this combines cookie values, ad-network
identifiers, IP and user agent against an identity.

None of this changes what gets built. It changes what ships alongside it: the field list, the
retention position and the data flow, written so an operator's own assessment is a filling-in
exercise rather than an investigation of FLS internals. `research_attribution_privacy.md` has the
citations.

## Terminology

| Term | Status | Meaning |
| --- | --- | --- |
| `SignupAttribution` | coined | The write-once row recording where one signed-up `User` came from. No existing FLS noun covers it. |
| `FirstTouchCount` | coined | The daily tally of first touches per attribution key. Holds no personal data. |
| referrer code | coined | The code issued to a partner, held on `Organisation`. Distinct from `slug`. |
| advert code | coined | The opaque identifier naming one advert. Free text, no table. |
| first touch | coined | The visitor's first landing within the cookie's 90 days. Everything in the row describes that one visit. |

## Research

- `research_attribution_capture.md` covers cookie and session mechanics, the 90-day window, click
  identifiers, `Referer` reliability, and the injection and caching failure modes.
- `research_referral_codes.md` covers code alphabets, why the slug is the wrong field, code
  lifecycle, and which abuse concerns evaporate without a reward.
- `research_attribution_privacy.md` covers the GDPR, POPIA and ePrivacy obligations, with citations.
- `research_django_implementations.md` covers middleware placement, why the signup POST is the only
  viable hook under mandatory verification, and why no third-party package is worth the dependency.
- `research_attribution_reporting.md` covers what makes the admin changelist usable, the messy-data
  problem, and what the export needs.
