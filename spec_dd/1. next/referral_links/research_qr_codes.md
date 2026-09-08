# Research: QR-code-specific constraints on `/d/{CODE}`, and what a scan count means

Scope: the `/d/{CODE}` redirect family only (the QR-code route). Two decisions are already made and
respected here, not relitigated: FLS does not generate the QR image (the operator makes their own from
the URL FLS gives them), and the redirect appends tracking parameters to the target URL rather than
setting a cookie.

---

## 1. What the URL's shape costs in the printed symbol

QR (ISO/IEC 18004) defines four data-encoding modes, each with a different bit cost per character:
numeric (10 chars, ~3.3 bits/char), **alphanumeric** (45 chars — `0-9 A-Z SP $ % * + - . / :`, 11 bits
per *pair* of characters, so ~5.5 bits/char), byte (any byte, 8 bits/char), and Kanji. A single
character outside the alphanumeric 45 — critically, any **lowercase letter**, or `?`, `=`, `&`, `_`,
`~`, `#` — forces the whole segment into byte mode. [ISO/IEC 18004:2015](https://www.iso.org/standard/62021.html)
is the current normative standard (18004:2024 is the latest edition:
[ANSI blog summary](https://blog.ansi.org/ansi/iso-iec-18004-2024-qr-code-bar-code-symbology/),
[ISO catalogue entry](https://www.iso.org/standard/83389.html)); a mirrored PDF of the 2015 text is at
[github.com/yansikeim/QR-Code](https://github.com/yansikeim/QR-Code/blob/master/ISO%20IEC%2018004%202015%20Standard.pdf).

**Uppercase does keep a URL in alphanumeric mode, but only if the whole string qualifies — path
included.** The scheme and host are case-insensitive by the URL spec, so `HTTPS://EXAMPLE.COM/...`
resolves identically to lowercase. The path is not case-insensitive in general — it's whatever the
server decides. A worked, measured example from a single 18-character URL: `HTTPS://EDENT.TEL/`
(all-uppercase, alphanumeric mode) renders as a 21×21 module Version‑1 symbol, while
`https://edent.tel/` (mixed/lowercase, forced to byte mode) renders as 25×25, Version‑2 — one version
step, for a URL of essentially the same length, from case alone.
([shkspr.mobi, "Why are QR codes with capital letters smaller"](https://shkspr.mobi/blog/2025/02/why-are-qr-codes-with-capital-letters-smaller-than-qr-codes-with-lower-case-letters/),
also covered at [Hacker News discussion](https://news.ycombinator.com/item?id=39907508) and
[Hackaday](https://hackaday.com/2025/02/26/shout-for-smaller-qr-codes/).) **This is directly actionable
for FLS**: `/d/{CODE}` only stays alphanumeric end-to-end if the path segment itself is uppercase too
(`/D/{CODE}`, or a Django URL config that accepts the uppercase form) — a lowercase `d` alone forces
byte mode for the whole string despite an uppercase code. Since Django's `path()` is case-sensitive by
default, this requires either the route to literally be uppercase, or a redirect view that
case-normalises before dispatch.

**Module counts for ~30 vs ~45 character URLs**, using the standard's per-version alphanumeric
character capacities (from the [ISO/IEC 18004 version/capacity tables](https://www.iso.org/standard/62021.html),
cross-checked against secondary references such as
[qrmake.dev's capacity reference](https://qrmake.dev/blog/qr-code-capacity-reference/) — treat the exact
character-capacity numbers as indicative rather than verified against the primary standard, which sits
behind ISO's paywall):

| Version | Modules/side | Alphanumeric capacity, EC-L | EC-M | EC-Q | EC-H |
|---|---|---|---|---|---|
| 1 | 21×21 | ~25 | ~20 | ~16 | ~10 |
| 2 | 25×25 | 47 | 38 | 29 | 20 |
| 3 | 29×29 | 77 | 61 | 47 | 35 |
| 4 | 33×33 | 114 | 90 | 67 | 50 |

A ~30-character alphanumeric-mode URL fits Version 2 (25×25) at EC-L or EC-M, but needs Version 3
(29×29) at EC-Q/EC-H. A ~45-character alphanumeric-mode URL fits Version 3 (29×29) at EC-L, but pushes
to Version 4 (33×33) at EC-M/EC-Q and beyond at EC-H. Concretely: going from ~30 to ~45 characters, or
from EC-L to EC-H at fixed length, both cost roughly one QR version step (4 more modules per side each
way) — and the two effects stack, so a 45-char byte-mode URL at EC-H can be two or three versions larger
than a 30-char alphanumeric-mode URL at EC-L. The [general error-correction trade-off](https://qrmake.org/qr-code-error-correction/)
is: L restores ~7% of codewords, M ~15%, Q ~25%, H ~30% — each step up trades data capacity for
resilience to print damage/dirt/curl, and [one analysis](https://huonw.github.io/blog/2021/09/qr-error-correction/)
notes error correction can paradoxically hurt easy scanning too, because the same recovery bits raise
version/density without necessarily helping a camera's initial lock-on. For a *redirect* URL — short,
static, doesn't need Kanji/byte content — EC-M is the commonly-recommended default; EC-Q/H is worth
paying for only where the print substrate is likely to get scuffed or partly obscured (vehicle livery is
the FLS case most likely to justify it).

**Practical minimum print size.** The commonly cited rule of thumb is the "10:1" ratio: the symbol's
side should be at least 1/10 of the intended scanning distance (10 cm code for a 1 m scan, 1 inch code
for scanning at ~10 inches). Reliable practical minimum for everyday printed material is around 2×2 cm;
sub-1 cm symbols only scan reliably under ideal lighting/focus conditions, which flyers, posters and
vehicle livery cannot guarantee.
([uniqode size guide](https://www.uniqode.com/blog/qr-code-best-practices/how-to-perfectly-size-your-qr-codes),
[qrlynx 10:1 rule](https://qrlynx.com/blog/qr-code-size-guide-print).) Because Version count drives
module count and module count drives minimum legible print size at a fixed scan distance, every
character FLS adds to the `/d/{CODE}` URL (tracking parameters included, if they were ever put in the
*symbol* rather than appended server-side after redirect — which FLS's design correctly avoids) has a
knock-on cost on vehicle livery and business cards, where the print area is small and the scan distance
is short.

## 2. Dynamic vs static QR

Industry usage: a **static** QR code encodes the final destination directly in the symbol — it can never
change, and offers no scan analytics. A **dynamic** QR code encodes a short URL to a redirect service;
the service can be updated later, tracks each hit, and only the redirect owner's decision — not the
printed pattern — governs the destination. This is exactly what makes `/d/{CODE}` "dynamic": the
QR pattern is fixed at print time, but the mapping from code to `target_url` lives in the database and
can be edited without reprinting.
([hovercode](https://hovercode.com/blog/static-vs-dynamic-qr-codes/),
[Wikipedia: Dynamic QR code](https://en.wikipedia.org/wiki/Dynamic_QR_code),
[Delivr FAQ](https://delivr.com/faq/1459/what-is-the-difference-between-a-static-and-dynamic-qr-code).)

What it buys: retargeting a code without reprinting (swap `target_url`), per-code scan counts and
timestamps, and the ability to deactivate (`active=False`) a code that's being abused or is simply
retired, all without touching the physical material.

What it costs: **the printed material is now hostage to the redirect host staying up.** If FLS's domain
lapses or the app is decommissioned, every `/d/{CODE}` on every flyer, poster, and vehicle wrap in
circulation dies simultaneously and permanently — no amount of later "fixing" the redirect table
recovers a code once the resolving domain itself is gone, because the phone never gets past DNS/TLS to
reach the (now-nonexistent) redirect logic. Practitioner commentary specifically flags this for
long-lived print media: business cards circulate 1–2 years, but outdoor vinyl signage runs 3–5 years and
vehicle livery/aluminium panels 7–15 years, all well past the horizon most people plan a hosting/domain
commitment against; the 2023–2024 consolidation of QR-platform vendors is cited as a concrete instance
where third-party dynamic-QR services shut down and stranded every code that had ever pointed at them.
([qrlfy: "What actually kills a code after print"](https://www.qrlfy.com/articles/do-qr-codes-expire),
similar coverage at [uniqode](https://www.uniqode.com/blog/qr-code-basics/qr-codes-expiry) and
[qr-code-generator.com](https://www.qr-code-generator.com/blog/do-qr-codes-expire/).) For FLS this is a
first-party risk rather than a third-party-vendor risk (FLS runs its own redirect, not someone else's
platform) — which removes the "vendor goes out of business" failure mode but not the "our own domain or
deployment lapses" one; it argues for treating the domain and route as a long-term commitment once
codes are printed onto anything with a multi-year physical life (vehicle livery especially), since that
material cannot be recalled.

## 3. Why QR scan counts are systematically wrong, and by how much

This is real and unavoidable at the redirect layer; no amount of clever code on FLS's side eliminates
it, only narrows it.

**Sources of non-human hits, roughly in order of how much they inflate a raw hit log:**

- **Security/safety scanners that follow the link with no human present.** Enterprise mail gateways
  (Microsoft Defender for Office 365 "Safe Links", Proofpoint, Mimecast) rewrite links and fetch the
  destination to check for malware/phishing — for QR this shows up when a QR image is photographed and
  the URL is later emailed or messaged and passes through a scanning gateway, or when a QR-checking app
  ("Is This QR Safe?" and similar) submits the URL to VirusTotal-style reputation services before a
  human is shown the destination. ([uniqode on QR safety](https://www.uniqode.com/blog/qr-code-security/how-to-check-if-a-qr-code-is-safe),
  [isthisqrsafe.com](https://www.isthisqrsafe.com/).) In the email-click-tracking world (a close cousin
  of the same problem) a documented case found 691 of 968 reported clicks — about 71% — came from a
  single hidden/bot-only link, i.e. the "real" human click rate was roughly a third of the raw count;
  other sources describe bot clicks as "the majority" of raw click totals without giving a specific
  number. ([Braze on bot clicks](https://www.braze.com/resources/articles/bot-or-not-understanding-email-bot-clicks),
  [Klaviyo on bot clicks](https://help.klaviyo.com/hc/en-us/articles/22981852783899),
  [Inbox Collective](https://inboxcollective.com/why-bots-are-clicking-on-your-newsletters/).) **Do not
  treat 71% as *the* QR-scan bot rate** — that figure is from email link-click scanning, which has a
  much heavier concentration of gateway scanners in its funnel than a QR code scanned directly off a
  poster does. It is cited here only to establish that "the majority of raw hits are not the reported
  human" is a documented order of magnitude in an adjacent channel, not a QR-specific number — no
  QR-specific bot-inflation percentage was found in this research; treat any number a vendor quotes for
  QR scans specifically as unverified marketing copy unless they show their methodology.
- **Camera-app and messaging-app link previews that fetch the URL before the human taps through.**
  iMessage, WhatsApp, Viber and (optionally) Signal generate a rich preview by fetching the URL as soon
  as the link is *sent*, independent of whether the recipient ever opens it — a documented, deliberate
  behaviour, not a bug. ([TheHackerNews on link-preview fetching](https://thehackernews.com/2020/10/mobile-messaging-apps.html),
  [9to5Mac](https://9to5mac.com/2020/10/26/researchers-demonstrate-how-link-previews-in-apps-can-expose-data-from-users/).)
  For QR specifically, the iOS Camera app resolves and displays the target domain in the viewfinder
  before the user taps the on-screen prompt — this is a lighter-weight domain lookup rather than a full
  page fetch in Apple's implementation, but third-party scanner apps vary, and any scanner app that
  shows a URL preview, "is this safe?" badge, or thumbnail is a candidate for fetching before tap.
  ([Apple Developer QR recognition talk](https://developer.apple.com/videos/play/tech-talks/206/),
  general behaviour described at [qrplanet](https://qrplanet.com/help/article/how-can-i-see-the-url-behind-the-qr-code).)
- **Browser prefetch / speculative loading.** Modern browsers can fetch a link's target ahead of
  navigation (`<link rel=prefetch>`, the Speculation Rules API) when a URL is *displayed on a web page*
  someone is browsing (e.g. a `/d/{CODE}` URL echoed on a landing page or in a shared document) — not
  applicable to a code scanned directly off print, but relevant if the same URL is ever also embedded
  in HTML anywhere. ([MDN speculative loading](https://developer.mozilla.org/en-US/docs/Web/Performance/Guides/Speculative_loading).)
- **One person, several scans.** A user re-scanning after losing signal, showing the code to someone
  else, or scanning it out of curiosity days apart all register as separate hits with no way to collapse
  them into "one interested person" from server logs alone, absent a cookie (which this design
  deliberately does not set — see idea.md).

**Detection techniques, and how far each actually gets you:**

- **User-Agent classification** (matching against known browser/bot UA strings). Cheap, and catches the
  honest majority — most scanner and preview-fetcher UAs identify themselves plainly (e.g.
  `WhatsApp/...`, `facebookexternalhit`, vendor safe-link UAs). But User-Agent is entirely
  client-supplied and unverified; nothing stops a scanner from presenting a normal mobile-Safari UA, and
  several corporate mail-security products deliberately mimic a real browser to test how the destination
  actually renders. Treat UA matching as a **filter that removes some obvious noise, not a guarantee** —
  it under-counts bots that don't self-identify and cannot be made to over-count. ([Castle.io: "How dare
  you trust the user agent for bot detection?"](https://blog.castle.io/how-dare-you-trust-the-user-agent-for-detection/),
  [Arcjet on identifying bots](https://arcjet.com/learn/identify-ai-agents-and-bots).)
- **`Sec-Purpose` / `Purpose: prefetch` headers.** Chromium and Firefox send `Sec-Purpose: prefetch` (or
  `prefetch;prerender`) on browser-initiated speculative loads; Safari has used `Purpose: prefetch` /
  `X-Purpose: preview` historically. These are real, standard, and reliable **when present** — but they
  only cover browser-initiated prefetch, not the mail-gateway or messaging-app fetchers above, which use
  a plain GET with no such header. ([http.dev Sec-Purpose reference](https://http.dev/sec-purpose),
  [Chromium intent-to-ship](https://groups.google.com/a/chromium.org/g/blink-dev/c/0yrUBDA8uUs),
  [MDN rel=prefetch](https://developer.mozilla.org/en-US/docs/Web/HTML/Reference/Attributes/rel/prefetch).)
- **Timing patterns.** Bots/scanners overwhelmingly fetch within seconds of the link becoming reachable
  and then never return; a human's session has natural variance (browsing before deciding, showing to a
  friend, scanning at a different point in the day). A hit within a very short window of the code's
  creation with no further activity from that "visitor" is a documented heuristic for bot traffic in the
  email-click-tracking literature, but a QR code sits on physical material for weeks-to-years, so "fetch
  immediately after the code became reachable" doesn't map as cleanly onto QR as it does onto a
  just-sent email link. ([campaigncleaner on bot-click timing](https://campaigncleaner.com/blog/email-bot-opens-clicks.html).)
- **Known-bot/known-scanner allowlists.** Maintaining a list of known safe-link/preview-fetcher UAs and
  IP ranges (Microsoft's published Safe Links ranges, Meta's `facebookexternalhit`, etc.) catches the
  well-behaved, documented fetchers. It is inherently a maintenance burden and always trails new
  entrants — a static list drifts stale.
- **HEAD vs GET.** No source found supports this as a meaningful signal for QR/redirect traffic
  specifically — most safe-link scanners and preview fetchers issue a normal GET (they need the full
  response to render a preview or scan content), so HEAD-vs-GET does not reliably separate them from a
  real browser navigation, which is also a GET. Not established as a useful technique here.

**What cannot be fixed, stated plainly:** there is no server-side signal that reliably distinguishes "a
phone's camera app, after a human pointed it at the poster and tapped through" from "a corporate mail
gateway or link-preview generator, with no human ever present" for a meaningful fraction of traffic.
User-Agent and header-based heuristics reduce the noise but do not eliminate it, and the true fraction of
non-human hits in any FLS `/d/{CODE}` log is unknowable from server data alone without a much heavier
investment (behavioural fingerprinting, JS challenge, CAPTCHA) that is entirely inappropriate for a
one-shot print redirect and would break the "phone camera → immediate destination" experience the whole
feature exists for. **A raw hit count on `/d/{CODE}` should be read as an upper bound on human scans,
not an estimate of them**, and the gap between the two is unquantified and unquantifiable from within
this design.

## 4. Distinguishing "never scanned" from "scanned but the visitor dropped off"

A timestamped hit log on `/d/{CODE}` establishes only: *the code was fetched by something, at this time,
this many times.* It does **not** establish that a human saw the destination page, that the human who
fetched it is the same human who later converted, or (per §3) that the fetch was human at all.

What it **does** let a marketer diagnose, cheaply and correctly, is the specific failure mode named in
the idea: a dealer's `/d/{CODE}` column reading zero. Zero timestamped hits over a period where the
material has plausibly been seen (flyer distributed, vehicle on the road) is real, unambiguous evidence
the code was never scanned at all — as opposed to "scanned, but the tracking mechanism silently failed"
(e.g. a cookie that never got set, or got blocked) which is indistinguishable from "never scanned" in a
cookie-only design. This is exactly the value the idea's own note calls out ("cheapest way to tell 'QR
never scanned' from 'scanned, cookie lost'"), and a hit log is sufficient for it on its own — nothing
further needs to be captured at the redirect to make *that* diagnosis.

What a hit log does **not** let you diagnose, and what would need something else: whether a nonzero but
low count reflects genuine low interest versus heavy bot/scanner inflation (§3) — for that you would need
either accepted noise (report the raw count with the caveat that it's an upper bound) or a
UA-classification pass, which itself is imperfect. It also does not tell you whether a scanner reached
the destination page and then left ("scanned, but dropped off") versus reached the destination and
converted — that is downstream of the redirect, in whatever landing/conversion tracking exists elsewhere
in FLS, not in `/d/{CODE}`'s own log. The redirect's job, correctly scoped, is only "was this code ever
hit" and "when" — diagnosing drop-off after the redirect is a different question answered by a different
part of the system (the referral-tracking work referenced in idea.md), not by adding fields to this
table.

**Privacy.** This traffic is anonymous by design — no login has happened yet, and per idea.md FLS's
attribution work deliberately keeps no per-visitor landing records. That constrains what's worth adding
even for diagnosis: IP address or User-Agent string, logged per-hit, would let a UA-based bot-classifier
run *after the fact* (reclassify old hits as noise/bot when new patterns are recognised, without needing
to decide correctly at request time) — but IP address in particular starts to look like identifying data
worth being deliberate about retaining, and doing so cuts against the "anonymous traffic, no per-visitor
record" posture that governs the rest of this feature area. If any additional field is captured, User-
Agent string (not IP) is the smaller, more defensible addition: it supports later bot/human
reclassification without the same privacy weight, though even it is client-supplied and unverified
(§3). No external source addresses this trade-off directly for FLS's specific "anonymous, no per-visitor
record" constraint — this is a judgement call, not a documented industry standard.

## 5. Code design for print

**Ambiguous characters.** The commonly-cited pairs that fail when read aloud, hand-transcribed, or
OCR'd: `0`/`O`, `1`/`I`/lowercase-`l`, `5`/`S`, `8`/`B`, and `2`/`Z` and `1`/`7` in some hands and fonts.
([gajus.com on avoiding visually ambiguous characters in IDs](https://github.com/gajus/gajus-com/blob/main/src/blogPosts/2024-04-22-avoiding-visually-ambiguous-characters-in-ids/blogPost.mdx).)
FLS's attribution work already uses a Crockford-style uppercase alphabet excluding `I`, `O`, `L`, `U` for
referrer codes — that decision was made for exactly this reason and should be reused for `/d/{CODE}`
rather than re-derived: keeping one code alphabet across `/go/{slug}` and `/d/{CODE}` (where `/d/{CODE}`
is a short generated code rather than a human-chosen slug) means one rule to document and one set of
"characters that never appear" to remember, and — per §1 — an uppercase-only alphabet is also the one
that keeps the code alphanumeric-mode-compatible in the QR symbol, for free.

**Human-typable fallback.** Printing the destination as plain text alongside the QR symbol
("scan the code, or visit example.com/d/CODE") is described as standard, close to universal, practice —
both as a usability fallback for anyone who can't or won't scan, and as an accessibility requirement:
QR codes should never be the *only* route to the content, per WCAG-adjacent guidance.
([Section508.gov on QR accessibility](https://www.section508.gov/blog/accessibility-bytes/qr-codes/),
[Axess Lab QR accessibility guide](https://axesslab.com/qr-codes/),
[boia.org](https://www.boia.org/blog/are-qr-codes-accessible-for-people-with-disabilities).) This argues
for the code being short enough to read aloud and type without error — the ambiguous-character exclusion
above is what makes that safe, not just convenient.

**Practical length.** No source gives a hard number for "the right length" independent of the
alphabet size and desired collision-space; it's a product decision (how many codes will ever be printed,
times a safety margin) rather than a QR- or print-derived constraint. What print *does* constrain is
that every character in the code is also a character in the QR symbol and in the read-aloud/typed
fallback, so the alphabet-exclusion and alphanumeric-mode reasoning above bound it more than raw length
does.

## 6. Retiring a printed code

Practice for a code whose printed material is still in the world after the campaign it supported has
ended: **redirect to a current, useful destination (a homepage or current offer) rather than 404**.
Sources describe a 404 on a scanned/typed code as close to the worst outcome for user experience — the
person did the work of scanning and got nothing — and recommend that a dynamic redirect's whole point is
that the destination can be swapped to something evergreen once the original campaign is over, without
needing to reprint or physically recall the material.
([redirect.pizza on redirecting a QR code to a new URL](https://redirect.pizza/resources/marketing/how-to-use-qr-codes-for-website-redirects),
[Bitly on editing a QR code destination](https://bitly.com/blog/edit-qr-code/),
[QR Tiger: "25 reasons your QR code isn't working"](https://www.qrcode-tiger.com/qr-code-not-working).)
This maps directly onto the `active` flag and `target_url` already in the idea's proposed schema:
"retiring" a code is not deactivating it in the sense of making it error, it's re-pointing `target_url`
to a durable fallback (organisation homepage, general enquiries page) while leaving `active=True` and
the hit log still recording — the alternative, flipping `active=False` and 404ing, is explicitly what the
sourced practice above argues against for material still physically in circulation. Whether FLS wants
`active=False` to mean "hard error" or "fall through to a configured default destination" is a design
decision this research surfaces but does not settle — no source addresses a *table-driven* redirect
service's specific `active` semantics, only the general "don't 404 a retired code" principle.

---

status: ok
