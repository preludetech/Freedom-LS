# Referral codes and the redirects behind them

## The problem

Marketing has no way to hand someone a URL and later find out whether anyone used it. An affiliate
who puts a code on their own website, a QR code on a board at a trade stand, a code printed down the
side of a vehicle. Today each of those is a raw URL that leaves no trace. When a partner's column
reads zero, nobody can tell whether the code was never used or whether it was used and the tracking
failed.

`referral_tracking` answers the second half of this: who signed up, and what they arrived carrying.
It has no answer for the first half, because it only ever sees people who signed up. A code that
brought a thousand visitors and no signups looks exactly like a code nobody ever scanned.

## What we are building

A `ReferralCode`. A short code a builder creates in the admin, with a destination on the same site.
Two routes resolve it, `/go/{code}` and `/d/{CODE}`, and both 302 to that destination. Every access
writes a `ReferralCodeHit` with a timestamp.

A referral code is not an advert code. It names a source of traffic, meaning a person's website, a
printed board, a business card, rather than a campaign. A code may well appear inside an advert, and
when it does the advert's own `advert_code` and UTM values ride alongside it and behave exactly as
they already do. The two are independent and compose.

This work extends `freedom_ls/referral_tracking`, which is on `main`. That app owns the vocabulary,
the settings pattern and the admin conventions this needs a smaller version of, and the alternative
adds a third app's worth of scaffolding for one model and a view. The app has no routes or views
today, so these are its first. It is not the extractable `referral-link-tracker` that
`docs/app_conventions.md` still names as planned: codes are unique per `Site`, and an extractable app
may not depend on `site_aware_models`. `research_shipped_referral_tracking.md` describes the app as
it stands and every seam this work touches; the other research files predate it and describe its
spec.

## The two routes

One code, one table, two doors. `/go/` is the readable door, for a code a person types or reads off
someone's website, like `/go/mrbeast`. `/d/` is the short door, for a code that goes into a QR
symbol. The prefix is a presentation choice rather than a different kind of thing, and either prefix
resolves any code. Which door a visitor came through is recorded on the hit, because a `/d/` hit is
probably a scan and a `/go/` hit is probably a click, and that is worth being able to tell apart.

Codes are unique per `Site` and resolved case-insensitively. A code read aloud off a flyer gets
typed in whatever case the listener felt like, and a vanity code someone half-remembers from a
social post is the same problem. Two sites can each own `mrbeast` pointing somewhere different, the
way two sites can each have an `Organisation` named Acme.

**Case-insensitivity is also what makes a QR symbol smaller.** A QR symbol encodes an all-uppercase
URL in alphanumeric mode and anything else in byte mode, and a single lowercase character anywhere
in the string, including the `d` in `/d/`, forces the whole thing into byte mode at a cost of about
one version step. `HTTPS://EXAMPLE.COM/D/P5H2B3C8` and `https://example.com/d/P5H2B3C8` resolve to
the same entry, so a designer can generate the dense form while the human-readable line printed
under the symbol stays lowercase. This matters where print area is tight, which is exactly where QR
codes go. Business cards and vehicle livery. `research_qr_codes.md` has the module-count arithmetic.

Codes generated for `/d/` use uppercase without `I`, `O`, `L` or `U`, the exclusions that let a code
survive being read down a phone line. Codes typed for `/go/` are whatever the builder chooses, since
readable is the whole point of that door. A short reserved list keeps `/go/admin`, `/go/support` and
the site's own brand name out of builders' hands. That namespace is handed to strangers, and those
codes read as official channels.

The URL patterns carry no trailing slash. `/go/mrbeast` is the form that gets printed and spoken,
and registering the pattern with a slash would make Django issue its own redirect first, an extra
round trip before the hit is ever logged.

The destination is a path on the site, not a URL. Capture only mints on FLS's own hosts, so an
off-site destination would produce a code that appears to work while recording nothing, and a path
makes that impossible to type rather than a validation error to catch.

## How a hit reaches attribution

The redirect appends `ref={code}` to the destination and passes through everything the visitor
arrived carrying, untouched. `ref` is the parameter name `referral_tracking` reserved for this
work. Anything already on the configured destination stays, the visitor's own query string stays,
and `ref` is added.

The value appended is the code as stored on the entry, not as it was typed in the URL. Otherwise
`ref=MrBeast` and `ref=mrbeast` become two rows describing one code.

`ref` joins the tracked parameters, so a landing carrying it mints the attribution cookie like any
other tracked landing, and it joins the attribution key as a seventh value. `SignupAttribution` and
`FirstTouchCount` each gain a `referral_code` column, and it appears on both changelists and in
both exports. The column holds the code text, never a foreign key: attribution rows are written
once and copied from the cookie, and a code is never reused, so the text identifies the entry for
as long as either table exists. Without the key change the tally cannot be sliced by referral code,
and the only denominator left is the raw hit count, which counts machines as well as people.

Anyone can type `?ref=anything` onto any URL by hand. It is captured as free text, the way
`advert_code` is, and matches no entry. That is a typo in a column, visible, and not worth a query
on the mint path to prevent.

**A referral code reaches attribution only as a first touch.** The shipped design freezes the
cookie on the first tracked landing and never overwrites it. A visitor who already holds the cookie
and later follows `/go/mrbeast` is passed straight through: the hit is logged, and the code reaches
neither the tally nor the eventual `SignupAttribution` row. "How many signups carried this code"
means how many signups whose first tracked touch carried it.

**Capture must be suppressed on the two redirect routes themselves.** The middleware mints on the
response to any GET carrying a tracked parameter, whatever the status code, so a visitor arriving at
`/go/mrbeast?utm_source=twitter` would otherwise be minted from the redirect: a first touch whose
landing path is `/go/mrbeast` and which never sees the `ref` the redirect is about to append. The
mint has to happen at the destination, where the referral code and the campaign values are present
together. The suppression is by route, not by status code. A tracked landing on a page that itself
redirects to login is a real landing and is counted today.

## What a hit row holds

The timestamp, which code, which door, and whether the request looked like a machine. Nothing else.
No IP address, no user agent, no `Referer`.

That is a deliberate reading of the position `referral_tracking` already took. It writes nothing
per visitor at landing, only the day's tally, because a row about someone who never signed up is
data on a person who never saw a privacy notice and has no account against which to hang a deletion
request. A hit log is structurally the same thing, and the way to stay consistent with that position
without giving up the count is to hold nothing that describes the visitor. What survives is a row
about the code, which is not personal data at all.

The machine-fetch verdict is decided when the hit is written, from the user agent and the
`Sec-Purpose` header, and only the verdict is kept. This costs the ability to reclassify old hits
when a better bot list comes along. That is the price of not retaining the user agent, and it is
worth paying. The raw string is a fingerprinting field on an anonymous visitor, and the verdict is
all anyone reads. The verdict is on hits only. `FirstTouchCount` stays unfiltered, as the product
page says it is, which is one more reason the two counts for one code will differ.

A maintained counter on the entry sits alongside the log, incremented atomically, so the changelist
reads one integer instead of aggregating a growing table on every page load. The log is the source
of truth if the two ever disagree.

**A hit count is an upper bound on human use, not an estimate of it.** Link-preview fetchers, mail
security scanners and crawlers all follow redirects with nobody behind them, and no server-side
signal reliably separates them from a phone camera. The machine-fetch flag removes the ones that
identify themselves and misses the ones that imitate a browser. The admin says this plainly, in the
same place `FirstTouchCount` already says it about its own count, rather than presenting the number
as a scan count. `research_qr_codes.md` and `research_hit_logging.md` cover which signals exist and
how far each gets.

Hits accumulate indefinitely. A management command prunes rows older than a given age so an operator
can bound the table on their own schedule, and the counter is never pruned, so historical totals
survive the pruning. FLS documents that the table grows and whose decision it is. This is the first
retention tooling in the app; `SignupAttribution` has none and this does not add any.

## Retiring a code

An inactive code still redirects, to a configured fallback destination, and still logs its hits. It
does not 404.

Printed material cannot be recalled. A poster from eighteen months ago is still on a wall, and the
person scanning it did the work. A dead end is the worst available outcome and the one every source
argues against. Keeping the hit log running on a retired code is also how anyone finds out that a
print run everyone believed was pulped is still pulling traffic.

404 is reserved for a code that never existed.

Codes are never recycled. A new entry reusing a retired code would silently inherit traffic from
stale material aimed at the first one, and its hit log would be a blend of two campaigns.

## The admin is the whole interface

No dashboard, no partner-facing view. The changelist is the product, so the columns and filters are
the design.

`ReferralCode` is the app's first writable admin; the two it ships with are read-only. Hits get the
read-only treatment those two already have, and the CSV export that comes with the app's admin base,
so "when did the June flyer's traffic arrive" is an export rather than a feature.

The builder's real work is to create a code, hand the finished URL to a partner or a designer, come
back later to ask whether anyone used it, and retire it at the end. Two things follow.

**The finished URL is shown ready to copy.** Making someone assemble `https://` plus the host plus
the prefix plus the code by hand is a transcription error waiting to be printed onto something.
Alongside it, the resolved destination including the appended `ref`, which is the string a partner's
own analytics will record. That is the one thing a builder cannot otherwise see before it is
committed to paper.

**Every entry gets a label and notes.** `/d/P5H2B3C8` tells nobody anything eighteen months later,
and the code is opaque by design. The label is what makes the changelist readable, and the notes are
where "printed on the June flyer for the downtown venue" lives. This is the complaint that lands
hardest against every tool that treated it as optional.

The changelist carries the code, the label, the destination, whether it is active, the hit count and
the most recent hit. A cumulative count alone reads identically for fifty hits last week and fifty
hits two years ago. Search covers the code, the label and the notes. Filters stay on the
low-cardinality fields, since a filter with one entry per row is the trap `referral_tracking`'s
admin already designed around. Bulk deactivation at the end of a campaign is an admin action.

Codes are created one at a time on the stock form. A print run needing fifty codes is a real case
and a management command is the cheap answer to it, but nobody knows yet whether that case is real
here, so it waits.

## What this cannot answer

**How many people, as opposed to how many hits.** Nothing deduplicates. Fifty hits is one person
refreshing or fifty people, and there is no way to tell.

**How many of this code's hits became signups.** The hit log and `SignupAttribution` are two
counting systems that share a value rather than a row. "How many signups carried this code as their
first touch" is answerable exactly, and that is the useful question. "What fraction of this code's
hits converted" divides a signup count by a number that includes machines and repeat visitors, so
it is a floor rather than a rate.

**Anything about the visitor.** Where they came from, what device they used, where they are, whether
this is their second visit. A hit says a code was used and when, and nothing more.

## Deliberately out

**QR image generation.** FLS hands over the URL, and the operator's designer renders the symbol in
whatever tool they already use. No new dependency, no image storage, and no need for FLS to have an
opinion about error-correction level.

**Any link to `Organisation`.** An affiliate is usually a person, and making someone create an
organisation before they can be issued a code is a heavy act for no gain. The label says who the
code is for. This closes the "partner referral codes" item `referral_tracking` deferred and its
product page lists as not built, with a lighter home than the `Organisation` field that plan named,
and adds no edge to the app's dependency graph.

## Terminology

| Term | Status | Meaning |
| --- | --- | --- |
| `ReferralCode` | coined | The configured code, its destination and its counter. Supersedes the "referrer code" `referral_tracking` deferred, which was to live on `Organisation`. |
| `ReferralCodeHit` | coined | One access of a `ReferralCode`. Holds no personal data. |
| `referral_code` | coined | The column on `SignupAttribution` and `FirstTouchCount` holding the code text a first touch carried. Seventh value of the attribution key. |
| door | coined | Which of the two prefixes a hit arrived through. Only used to tell a probable scan from a probable click. |
| `advert_code` | narrowed | `referral_tracking`'s existing parameter and field. Unchanged here, and independent of a referral code. |

## Research

- `research_shipped_referral_tracking.md` describes `referral_tracking` as it is on `main`: the
  seams `ref` passes through, what the middleware does and when, the admin bases now in force, and
  the deferred items this closes. Read it first. The files below were written against the spec.
- `research_short_link_design.md` covers reference implementations, code alphabets, reserved words,
  why 302 rather than 301, and the open-redirect risk profile when the destination is builder-typed.
- `research_qr_codes.md` covers encoding modes and the cost of a lowercase character, dynamic-QR
  domain-longevity risk, and why scan counts run high.
- `research_hit_logging.md` covers counters under concurrency, bot signals and their reliability,
  the field-by-field privacy reading against `referral_tracking`'s own position, and table growth.
- `research_django_implementation.md` covers routing placement, site-aware lookup, view rather than
  middleware, response headers, the trailing-slash trade-off, and the FLS model and admin
  conventions this follows.
- `research_operator_experience.md` covers the builder's workflow, what makes a changelist usable,
  the naming problem, retirement practice, and the reporting expectations this will not meet.
