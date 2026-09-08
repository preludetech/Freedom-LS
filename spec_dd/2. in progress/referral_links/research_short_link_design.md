# Research: short-link and vanity-URL code design, and redirect semantics

Scope: `/go/{slug}` (human-handed referrer vanity URLs) and `/d/{CODE}` (opaque QR codes), one model,
302 redirect to a target URL on the same FLS site, with an attribution-capture middleware (in progress
in `spec_dd/2. in progress/referal_tracking/`) reading tracking parameters off the resulting landing GET.

**FLS vocabulary note up front.** The domain glossary
(`.claude/skills/domain-glossary/SKILL.md`) already takes **"link"** for an `<a href>` — ~280 usages,
fine as a verb, never as a model or field noun. Every naming candidate below that would otherwise
reach for "link" (ShortLink, LinkHit, link_code) is flagged. The referral-tracking idea file
(`spec_dd/2. in progress/referal_tracking/idea.md`) already establishes **"referrer code"** for the
`ref` parameter an `/go/` entry represents and **"advert"**/`advert code` for the thing a `/d/` entry
represents (`v`, the advert identifier) — reuse those nouns rather than coining new ones for the same
concepts.

---

## 1. Reference implementations

| System | Model / what it holds | Code generation | Target editable after issue | What it logs | Worth imitating? |
|---|---|---|---|---|---|
| **Bitly** | short code (their "back-half" if custom), destination URL, click count, redirect history | random by default; user can supply a custom "back-half" | **Yes** — "the short URL and any associated QR Code stay exactly the same — only the destination changes," and Bitly "logs every destination change" as redirect history, with clicks attributed to each version | per-click analytics, and per-destination click counts across the edit history | **Yes, on the two decisions that matter most here**: (a) the code is permanent, only the target is editable, and (b) Bitly keeps a history of destination changes rather than overwriting silently. FLS's brief doesn't ask for per-version history, but the pattern is worth knowing about for §6 below. |
| **Rebrandly** | short URL + custom domain + destination, tags, UTM builder, "intelligent traffic routing based on location, device type, date/time, language" | custom or random back-half per branded domain | yes (implied by "redirect" as a first-class action across their docs) | click reports: total clicks, daily/hourly, country-level; advanced tier adds device/language/social-source | Feature surface (geo/device routing, UTM builder baked into link creation) is more than FLS needs. The core "branded domain + slug + destination" shape is the right shape, but skip the routing features. |
| **Dub.co** (open source, inspectable) | `Link` object: `id`, `domain`, **`key`** (their name for the slug — "a random 7-character slug will be generated" if not supplied), `url` (destination), `clicks`, `lastClicked`, `expiresAt`, **`expiredUrl`** (where to send traffic once expired), `password`, `disabledAt`, `externalId`, `tenantId`, plus a full UTM/`ref` parameter set stored *on the link itself* | random key by default, custom key allowed; stored in Redis for edge-speed lookup, MySQL for source of truth, Clickhouse for click analytics | yes, `url` is mutable | individual click events land in Clickhouse (a real analytics store), separate from the link metadata table | The two field names worth stealing as **naming precedent, not identifiers** (careful — "link" is taken in FLS): `key` for the code/slug field, and the retiring pair `disabledAt` + `expiredUrl` (a *fallback destination* for a code taken out of service) is exactly the shape §6 below needs. Its infra (Redis edge cache, Clickhouse) is overkill for FLS's traffic and stack — skip it. |
| **Short.io** | domain, slug, destination, per-click event: "status code, method, referrer, and user agent" | random or custom | yes | one row per click, not just a counter | Confirms hit-per-event logging (not just a rolling counter) is the norm among modern tools, matching the FLS decision already made ("Log hits with timestamp"). |
| **YOURLS** (self-hosted PHP, closest philosophically to a self-hosted admin-driven tool) | `keyword` (short code), `url`, `title`, `timestamp`, `ip`, `clicks` (a counter, not per-hit rows in core — click logging is a plugin, `random-keywords` is also a plugin not core) | **sequential by default** (base62 of an autoincrement ID); an optional plugin swaps in random keywords | yes, target editable via admin | click counter in core; per-click detail only via plugin | Worth noting as a **counter-example**: YOURLS's random-keyword plugin has no collision-avoidance beyond retry, and "will enter an infinite loop trying to find a free short URL... and the page will eventually time out" if the keyword space is exhausted at a given length — a documented, real failure mode. Its core sequential IDs are also a leak (see §2). Its architecture (single PHP app, MySQL, no queue) is not a model for FLS's Django app either. Not worth imitating structurally; worth citing as the "don't do this" for both random-code retry loops and sequential codes. |
| **`django.contrib.redirects`** | `site`, `old_path`, `new_path` — Django's own contrib app for exactly this shape of "path maps to target URL" per Django `Site` | none — `old_path` is typed by an admin, not generated | yes, edit the row | none — no click count, no timestamp, no hit log; a matching row with a non-empty `new_path` 301-redirects | **Confirms the site-scoping pattern** (FLS is already `Site`-aware via `site_aware_models`) and that Django's own idiom for "admin types both sides of a path-to-URL mapping" is a plain model with no code-generation logic. **Not worth reusing directly** — no hit tracking of any kind, and it 301s, which the FLS decision explicitly avoids (see §4). But it is the nearest first-party precedent for "an admin-authored URL redirect table keyed by `Site`," and this feature's model should look more like an enriched `contrib.redirects` row than like a hashed-ID shortener. |
| **django-shorturls** (Simon Willison / Ben Firshman) | maps a *prefix* to a Django model's `get_absolute_url()` — it shortens URLs to *content already in the app*, not to arbitrary external destinations | derives the code from the linked object's own PK/slug, not independently generated | N/A — the "destination" is just wherever the linked object's `get_absolute_url()` points, changes automatically when that does | none found — no hit count, no per-hit log | **Not worth imitating.** Different problem: it's an "internal object → short path" mapper, not an "admin types an arbitrary external target URL" redirector. Maintenance status could not be established from the GitHub page content (no visible commit dates), but the get_absolute_url-coupling design doesn't fit FLS's requirement of an operator-typed, freestanding `target_url` field regardless. |
| **django-url-shortener** (tehranian) | base62-encodes the row's own database ID for the code; "keeps count of how many time each URL is followed" | base62 of autoincrement PK — i.e. **sequential**, base62-encoded | not established from available docs | a counter is mentioned; whether it logs individual hit timestamps could not be established | Confirms base62-of-PK as a common pattern, but see §2 — base62-of-PK is sequential under a thin disguise and leaks the same information an autoincrement ID does once decoded (base62 decoding is trivial). Maintenance status could not be established. |

**Bottom line for FLS:** no reference implementation is a drop-in fit. The two closest philosophical
matches are `django.contrib.redirects` (admin-authored, `Site`-scoped, target editable) for the model
shape, and Bitly/Dub.co for two specific decisions worth copying: the code is a **permanent identifier**
and only the **target is mutable**, and a **retired/expired code needs its own fallback destination**
field (Dub.co's `expiredUrl` is the clearest precedent — see §6).

Sources:
- https://support.bitly.com/hc/en-us/articles/360021057871-Are-Bitly-Links-case-sensitive
- https://bitly.com/blog/bitly-redirect/
- https://www.rebrandly.com/blog/rebrandly-vs-dub
- https://dub.co/docs/api-reference/endpoint/create-a-new-link
- https://dub.co/docs/local-development
- http://short.io/features/tracked-clicks/
- https://github.com/YOURLS/random-keywords
- https://github.com/orgs/YOURLS/discussions/2902 ("Sequential or random?")
- https://github.com/YOURLS/YOURLS/issues/2321
- https://docs.djangoproject.com/en/dev/ref/contrib/redirects/
- https://github.com/bfirsh/django-shorturls
- https://github.com/tehranian/django-url-shortener

---

## 2. Code and slug design

**Alphabet choices, established general facts:**
- **Base62** = `[0-9A-Za-z]`, 62 symbols. Compact, URL-safe with no percent-encoding needed, and the
  most common choice for opaque codes across the industry (Bitly, TinyURL, and most tutorials/blog
  writeups use it). Case-sensitive by construction — upper and lower `A`/`a` are different symbols.
- **Base58** (Bitcoin-address alphabet) deliberately drops `0`/`O` and `I`/`l` (and non-alphanumeric
  symbols) to reduce transcription error when a human reads or retypes the code. Costs a small amount
  of length efficiency vs base62 for the same collision resistance.
- **Crockford base32** goes further: alphabet `0123456789ABCDEFGHJKMNPQRSTVWXYZ` — excludes `I`, `L`,
  `O`, *and* `U` (32 symbols total). The exclusions are explicitly for **human transcription**: `I`/`l`
  vs `1`, `O`/`o` vs `0`, and `U` specifically "to prevent accidental obscenity" and confusion with `V`.
  It is also explicitly **case-insensitive by design** — Crockford's own spec treats upper and lower as
  the same symbol, so a Crockford-alphabet decoder normalizes input case before decoding.

**Length vs collision probability (base62, random assignment, birthday-bound):** for a 6-character
random base62 code, ~50% cumulative collision probability is reached around ~280,000 codes issued, and
~1% odds around ~34,000 codes; a 7-character code has 62⁷ ≈ 3.5 trillion possible values, pushing the
practical collision floor far out. **Caveat: this specific figure came from a single secondary source
(a marketing/SEO explainer) and could not be cross-checked against a primary source in this pass** — treat
the order of magnitude as directionally right, not as a number to cite verbatim in a spec. The
qualitative point holds regardless: FLS's `/d/{CODE}` volume (adverts/QR placements set up by marketing,
not millions of end-user-generated links) is nowhere near where random-assignment collision risk becomes
a real design constraint at 6+ characters in any of these alphabets — this is a solved problem at this
scale, not a design axis worth spending review time on.

**Sequential vs random codes, what sequential leaks:** established practice (general web-security
literature, not link-shortener-specific) is that sequential/incrementing identifiers leak the *count* of
resources at any point in time, the *rate of creation* (compare two snapshots), and the *relative order*
of creation between resources — the same reasoning behind avoiding autoincrement PKs in any
publicly-exposed identifier (Stripe's public writing on this is widely cited: "integer IDs are a security
nightmare" for enumeration). Applied here: a sequential `/d/{CODE}` numbering scheme (or `django-url-shortener`'s
base62-of-PK — which is sequential underneath a base62 skin, and trivially decodable back to the PK)
would tell a competitor roughly how many QR placements marketing has issued and how fast, from nothing
but two codes printed on two pieces of collateral. This is a low-severity leak for FLS (marketing
volume, not user account IDs), but it costs nothing to avoid: generate the code, don't derive it from
the row's PK.

**Case sensitivity — the two families should not be treated the same way:**
- `/d/{CODE}` is an **opaque code printed into a QR code**. It is scanned by a camera, not typed, so
  human-transcription error is largely moot for the *primary* use — but marketing collateral routinely
  also prints the code as text underneath the QR (for people without a working scanner, or for spoken
  reference — "go to d-slash-K7M9Q2"), which puts it back in transcription-error territory.
- `/go/{slug}` is a **vanity slug a person types from memory or reads off a business card/social post**
  (`/go/mrbeast`). This is the harder transcription case — no camera involved — and it is also the case
  where the human wants it to read as a *word or name*, not a random string.

**What the FLS attribution work has actually settled — checked directly, not assumed.** The task brief
for this research asserted the referrer-code alphabet is already "Crockford-style." That is **not quite
what the code in progress specifies.** `spec_dd/2. in progress/referal_tracking/idea.md` gives the
validation regex for `ref` as:

```
^[A-Z0-9]{3,10}(-[A-Z0-9]{2,6})?$
```

That is **uppercase alphanumeric, full 36-symbol alphabet** (`0-9A-Z`) — it does **not** exclude `I`,
`L`, `O`, `U`. It is uppercase-normalized (matching Crockford's case-insensitivity-by-uppercasing
convention) and hyphen-segmented (also a Crockford/ISO-style readability convention), but it is not
actually the reduced 32-symbol Crockford alphabet. **This is worth flagging to whoever specs the
`/d/` code alphabet**: if the intent is consistency with the referrer-code shape, matching it exactly
means `[A-Z0-9]`, not Crockford's `I`/`L`/`O`/`U`-excluded set. If the intent was Crockford proper (to
get the transcription-error protection), the referrer-tracking regex should be tightened to match, not
the other way around — but that decision belongs to whoever owns that in-progress spec, not to this
feature.

**Recommendation for `/d/{CODE}`:** given the code is read aloud/retyped often enough that marketing
prints it as backup text, prefer the reduced, ambiguity-free alphabet (uppercase, no `I`/`L`/`O`/`U` —
whether that's spelled as "Crockford base32" or as "the same `[A-Z0-9]` shape as `ref` codes minus the
four ambiguous letters" is an editorial choice, not a functional one) over full base62. Case-insensitive
lookup (normalize to uppercase before querying) removes an entire class of "scanned fine, typed wrong"
support tickets regardless of which alphabet is chosen.

**Recommendation for `/go/{slug}`:** this is a *vanity* slug, not a generated code — it should be
whatever the admin types (lowercase, mixed case, hyphens — `mrbeast`, `MrBeast`, `mr-beast` are all
plausible admin input) with **case-insensitive lookup** to avoid a link that "doesn't work" because
someone typed `/go/MrBeast` instead of `/go/mrbeast`. This is a stronger argument than for `/d/`: a
vanity slug is explicitly meant to be memorized and typed by strangers who have no way to know what case
convention the admin used when creating it. Uniqueness should therefore be enforced case-insensitively
too (reject `mrbeast` if `MrBeast` already exists), or two admins will unknowingly create colliding
entries that resolve unpredictably depending on case-folding order.

Sources:
- http://www.crockford.com/base32.html
- https://news.ycombinator.com/item?id=36511423 (accidental-obscenity rationale discussion)
- https://ssojet.com/compare-binary-encoding/base58-vs-base62/
- https://dev.to/pazvanti/exposing-sequential-ids-is-bad-here-is-how-to-avoid-it-1mjp
- https://news.ycombinator.com/item?id=20005674
- https://support.bitly.com/hc/en-us/articles/360021057871-Are-Bitly-Links-case-sensitive
- `spec_dd/2. in progress/referal_tracking/idea.md` (repo, in-progress spec — read directly, not web)

---

## 3. Reserved words and collisions

General practice for reserved-word lists on user-chosen path segments (established from vanity-URL/
username-collision precedent — GitHub Gists collecting reserved-username lists for Rails/generic apps
are the most commonly cited community reference for this problem, e.g.
https://gist.github.com/caseyohara/1453705 and https://gist.github.com/goopi/5479701) groups reserved
words into distinct buckets, and FLS's situation maps onto them directly:

1. **Structural/path collisions** — anything that is, or could become, a real Django URL under `/go/`
   or `/d/`. Since these are FLS's own top-level path prefixes (not a shared namespace with unrelated
   app routes), the practical list is short: reserve the prefixes themselves if a bare `/go` or `/d`
   route ever needs to exist, and reserve anything the Django admin, static files, or health-check
   endpoints might plausibly use if they ever moved under these prefixes. Because `/go/{slug}` and
   `/d/{CODE}` are isolated path namespaces rather than sharing a namespace with page routes (unlike,
   say, a `/{username}` scheme that collides with `/settings`, `/login` etc.), this category is
   smaller for FLS than for a typical vanity-username product — worth confirming explicitly rather than
   importing a generic reserved-word list wholesale.
2. **Impersonation/authority words** — `admin`, `support`, `staff`, `security`, `billing`, `help`,
   `official`, the site's own brand name, and organisation names already in the system. This bucket
   matters for `/go/{slug}` specifically because it's a *human-facing, memorable* namespace handed out
   externally — `/go/admin` or `/go/support` reads as an official channel even though it's just a
   marketing redirect the admin typed. It matters much less for `/d/{CODE}`, which is opaque by design.
3. **Profanity/offensive strings** — relevant to `/go/{slug}` (human-chosen, publicly visible, printed
   on collateral) and essentially irrelevant to `/d/{CODE}` (system-generated opaque strings won't
   spell words unless the alphabet and length make that likely — another minor point in favour of
   excluding vowel-adjacent ambiguous letters in the `/d/` alphabet, though this is a secondary benefit,
   not the primary rationale from §2).
4. **Future-route headroom** — words the product team might want as real page routes later. Concrete
   for FLS: `/go/{slug}` is created by admins for specific people/organisations, and the useful
   mitigation is a validation check at creation time against Django's own resolved URL patterns for the
   relevant prefix (a small, code-derived reserved list, i.e. reuse the existing routing configuration
   rather than maintaining a hand-authored word list that drifts from it) plus a short hand-authored
   list for the impersonation/profanity buckets, which aren't derivable from code.

**Could not establish**: no single canonical "the" reserved list exists across the industry — every
system (Rails apps, GitHub, Slack) hand-curates its own, tuned to what routes and brand words it
actually has. There is no universal file to import; FLS needs its own short list combining (a) a
code-generated check against real URL patterns under the relevant prefix and (b) a small hand-authored
impersonation/profanity list.

Sources:
- https://gist.github.com/caseyohara/1453705
- https://gist.github.com/goopi/5479701
- https://syrashid.medium.com/custom-vanity-urls-with-rails-5f45a2a78a38

---

## 4. Redirect semantics

**301 vs 302 vs 307/308 — settle on 302, and this is not a close call for a trackable redirect:**
- **302 is the correct choice and matches the decision the idea file already states** ("routes ... → 302").
  With a 302, "every click, first or fiftieth, makes the stop at the server, so each click is counted."
  Browsers revalidate a 302 on each visit rather than caching the redirect itself.
- **301 actively breaks hit counting.** "Browsers cache 301 responses aggressively and often
  indefinitely... cached browsers bypass the redirect server entirely, so repeat visits from the same
  user are invisible to your click analytics" — a returning visitor's second, third, tenth click never
  reaches Django at all once the browser has cached the 301, so the hit count and the timestamp log both
  silently undercount. This is the mechanical reason the "QR never scanned vs scanned, cookie lost"
  diagnostic goal stated in the idea file requires 302, not 301.
- **307/308** exist to preserve the HTTP method and body across the redirect (a POST stays a POST).
  Irrelevant here — every hit on `/go/{slug}` and `/d/{CODE}` is a browser/camera-initiated GET, so there
  is no method-preservation problem 307/308 would solve, and no reason to reach for them.

**`Cache-Control` on the redirect response.** Even a 302 can be cached by an intermediary or a
misbehaving client if no explicit caching header is set, and — separately from the browser-caching
question — CDNs/reverse proxies make their own caching decisions from `Cache-Control` if it's absent.
Practice for a redirect whose destination might change and whose *hit* is itself the thing being
measured is to send an explicit `Cache-Control: no-store` (or the stronger conventional set
`no-cache, no-store, must-revalidate`) so neither the browser nor any intermediate cache serves a stale
hit without a fresh request reaching Django. This is a small addition on top of "use 302" and closes the
gap 302's weaker default caching semantics leave open.

**`Referrer-Policy` on the redirect.** The `Referrer-Policy` header on the *redirect response itself* is
honoured while the browser follows that redirect (i.e. it governs what `Referer` header, if any, the
browser sends on the next hop to the destination) — separate from any `Referrer-Policy` the destination
page itself sets. Browsers' modern default is `strict-origin-when-cross-origin`, which sends the full
referrer for same-origin requests and only the origin for cross-origin ones. **Relevance to this
feature**: because the FLS redirect targets are same-site (`target_url` restricted to the current site's
own host — see §5), the destination is effectively "same-origin" from the redirect's point of view for
this purpose, and the default policy already sends the full referrer chain through; no explicit
`Referrer-Policy` override on the redirect response looks necessary given the same-site-only
restriction. If `target_url` were ever cross-origin, an explicit policy would need deciding, but that
scenario is out of scope per the same-site restriction this research recommends in §5.

**Query-string handling — preserve incoming, then append tracking params, and this is where the
"already-settled" decision needs one more sentence.** The idea/spec state the redirect "302s to the
target URL with referral/advert tracking parameters appended" so the existing attribution middleware
sees them on the landing GET. General practice (from redirect-tooling documentation, not link-shortener-specific)
is: forward whatever query string the visitor arrived with, then append the redirect's own tracking
parameters, because "appending the same parameter twice can produce confusing reports and inconsistent
attribution" if a naive concatenation collides with a same-named key already on the incoming URL or
already present on the stored `target_url`. Concretely for FLS: an entry's `target_url` might itself
already carry a query string (e.g. `?utm_campaign=launch`), and/or a visitor might arrive at
`/go/mrbeast?utm_source=youtube` hoping to override or supplement that. **Recommended precedence, since
none of the FLS specs so far state one explicitly**: the redirect's own attribution parameter (the
`ref`/advert code identifying *this* entry) should always win on collision — it's the whole point of the
entry — while parameters already present on the stored `target_url` should be treated as the redirect
owner's fixed configuration and also win over anything the visitor's own incoming query string supplies,
since an admin-configured `target_url` query string is a deliberate, reviewed setting and a visitor's
incoming query string is not (the visitor's incoming query string arriving at `/go/{slug}` is also
unusual — normally nothing but the slug arrives on a hand-typed or QR-scanned link, so this may be a
low-frequency edge case in practice, but the precedence should still be defined explicitly in the spec
rather than left to whatever the implementation happens to do first).

Sources:
- https://url-shortening.com/blog/301-vs-302-redirects-in-shorteners-speed-seo-and-caching
- https://reslug.com/guides/301-vs-302-redirects
- https://megamorf.gitlab.io/2019/01/07/prevent-browsers-from-caching-redirects/
- https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/Referrer-Policy
- https://developer.mozilla.org/en-US/docs/Web/Security/Practical_implementation_guides/Referrer_policy
- https://www.redirhub.com/blog/how-to-preserve-utm-parameters-through-redirects
- (general redirect-status-code semantics, cross-checked against multiple summaries) https://redirect-radar.com/guides/redirect-status-codes

---

## 5. Open redirect safety

**The actual risk profile here is materially lower than the generic open-redirect writeups assume, and
the FLS brief's own framing is correct about why.** OWASP's Unvalidated Redirects and Forwards guidance
treats the danger as arising specifically from **untrusted, user-supplied** redirect targets: "accepting
user-supplied URLs" lets an attacker "redirect the request to a URL contained within untrusted input,"
enabling phishing (send a victim through a trusted domain to a look-alike site) or laundering an OAuth
flow through a legitimate domain. **FLS's `target_url` is typed by an authenticated Django-admin
operator, not submitted by an anonymous site visitor** — the threat model OWASP is describing (an
attacker crafting a malicious `?next=` parameter that an unauthenticated request controls) does not
apply directly, because the attacker has no path to set `target_url` without already having admin
access, at which point they have far more direct routes to cause damage than an open redirect.

**What residual risk remains even with an operator-controlled target:**
- **Compromised or careless admin account.** If an attacker phishes or otherwise obtains an admin
  session, they could set `target_url` to a phishing page and abuse the site's own trusted domain (in
  `/go/{slug}`'s email/social-share form) to lend it credibility — the classic open-redirect abuse
  pattern, just with a higher bar to reach (admin compromise) than the OWASP baseline scenario assumes.
- **Operator mistake, not malice**: an admin pastes the wrong URL, including e.g. a URL with embedded
  credentials, a typo'd domain that happens to be squatted, or (accidentally) an internal-only URL not
  meant for public traffic.
- **Same-site restriction is a defence against both**, and OWASP's own primary recommendation — "map
  user input to a short name, ID or token which is mapped server-side to a full target URL," i.e.
  exactly the redirect-table pattern this feature already is — is the "highest degree of protection"
  they describe, but that's about protecting *against attacker-supplied* short codes resolving to
  attacker URLs, which isn't quite FLS's scenario (the operator picks both the code and the target).

**Recommendation: restrict `target_url` to the current `Site`'s own host, not an open allowlist, with an
explicit, deliberate exception path if marketing needs to point at a landing page hosted elsewhere.**
Rationale:
- It matches OWASP's core recommendation of allowlisting hosts over accepting arbitrary URLs, applied
  here as defence-in-depth against the admin-compromise and operator-mistake scenarios above, not
  against a generic external attacker (who has no input to this field at all).
- It matches the FLS convention this feature already sits inside: `Site` is described in the domain
  glossary as "the tenant, and the isolation boundary" — a redirect entry pointing off-site is, by that
  same logic, pointing outside the tenant boundary it was created inside, which is worth a deliberate
  decision rather than an unrestricted text field.
- **The tension the brief calls out — same-site-only vs "the legitimate need to point at a landing
  page"** — resolves cleanly *if* the landing pages in question are themselves served by this same FLS
  site (which `spec_dd/0. noop/landing-pages/` suggests is the actual deployment shape: marketing
  landing pages living on the site, not on a separate marketing domain). If FLS ever needs a `/go/`
  entry to point at a genuinely external domain (a partner's page, a hosted-elsewhere campaign site),
  same-host-only as a hard constraint would block a legitimate use case — the practical resolution used
  elsewhere for this exact tension is a **narrow allowlist of additional trusted hosts** (configured, not
  free-text) rather than either a fully open field or a rule with no escape hatch. **This decision
  (same-site-only vs. a small configured allowlist) is a spec-level call this research surfaces but does
  not make** — it depends on whether FLS's marketing plans to ever target a genuinely external domain,
  which is not established in any file read for this research.

**Could not establish**: whether marketing's actual, current use case ever needs a target outside the
FLS site's own host — that's a product question for the spec author, not something resolvable by
research into external systems.

Sources:
- https://cheatsheetseries.owasp.org/cheatsheets/Unvalidated_Redirects_and_Forwards_Cheat_Sheet.html
- https://owasp.org/www-community/attacks/open_redirect
- `.claude/skills/domain-glossary/SKILL.md` (repo — `Site` definition)

---

## 6. Changing a target after the code is in circulation

**Editing the target is the norm, not the exception, and is exactly why 302 (not 301) matters (§4).**
Bitly: "When you redirect a Bitly link, the short URL and any associated QR Code stay exactly the
same — only the destination changes," and it logs a full redirect history so "clicks each version
received" stay attributable. Dynamic-QR industry writeups make the same point about the *reason* this
matters for printed material specifically: "A dynamic QR code usually points to a short redirect URL
controlled inside a dashboard... you can edit that destination later without changing the printed
image" — versus a static QR code, where the destination is baked into the pixels and can only be
changed by reprinting. **FLS's design (a redirect model an admin edits, referenced by a printed code) is
already a dynamic-QR pattern by construction** — this is a property to preserve, not something to add.

**Retiring a code — three options and what practice says about each:**
1. **404 the retired code.** Simplest, but industry guidance explicitly names this the failure mode to
   avoid: "Create a durable fallback destination you can redirect to later. This prevents the
   worst-case scenario: printed code → 404." A 404 on printed collateral is unrecoverable — nobody can
   fix a QR code already on a physical flyer, and the person scanning it gets a dead end with no
   recourse.
2. **Redirect to a fallback destination.** This is what the reference implementations converge on:
   Dub.co's `expiredUrl` field is exactly this — a separate, explicit "where to send traffic once this
   link is no longer live" destination, distinct from the primary `url`/`target_url` field. **This is
   the pattern worth adopting**: a retired/inactive entry should still 302, just to a configured fallback
   (a generic "this offer has ended" or site-homepage landing page) rather than to nothing.
3. **Leave the code active indefinitely, pointed at something else.** This is what "editing the target"
   already gives you for free — a code doesn't need a distinct "retired" state at all if the operator
   just repoints it at a currently-relevant page instead of a dead one. Whether FLS needs a distinct
   `active`/`inactive` flag *in addition to* an editable `target_url` is a design question this research
   surfaces rather than answers: the idea file already lists `active` as a field, so the flag exists;
   what it means when `active=False` (404? fallback redirect? excluded from hit logging but still
   redirects?) is not yet specified anywhere read for this research and should be pinned down explicitly
   — option 2 (fallback redirect, not 404) is what the cited practice recommends if a distinct inactive
   state is kept.

**What happens to accumulated hit history when a target changes.** None of the reference
implementations researched here delete or reset a code's click count when the destination changes —
Bitly explicitly keeps clicks-per-destination-version as part of its redirect history, and the hit
count in every system surveyed is a property of the **code**, not of any particular destination it has
pointed at. For FLS, this means: the per-hit log (timestamp per access) and the hit counter belong to
the redirect entry as a whole and should **not** be zeroed, migrated, or partitioned when an admin edits
`target_url` — a hit logged in week 1 against `/d/K7M9Q2` remains a true statement about that code being
scanned in week 1, regardless of what the code points to today. **FLS is not required to go as far as
Bitly's per-destination-version click attribution** (that's a materially bigger feature — versioned
targets, not just a mutable one) — the brief's stated requirement is a hit count and a timestamp log per
entry, and that's satisfiable without target-versioning at all. Whether a future FLS iteration wants
Bitly's version-attributed click history is a scope question, not something this research resolves.

Sources:
- https://bitly.com/blog/bitly-redirect/
- https://support.bitly.com/hc/en-us/articles/360021057871-Are-Bitly-Links-case-sensitive
- https://rocketlink.io/blog/can-you-change-a-qr-code-link-after-printing
- https://redirect.pizza/resources/marketing/how-to-use-qr-codes-for-website-redirects
- https://dub.co/docs/api-reference/endpoint/create-a-new-link (`expiredUrl`, `disabledAt` fields)

---

## Naming flags for the spec author

Concepts below need a noun, and **"link" is unavailable** as a model/field noun in FLS
(`.claude/skills/domain-glossary/SKILL.md`):

- **The model itself** covering both `/go/` and `/d/` entries — needs a name that isn't `Link`,
  `ShortLink`, or `LinkRedirect`. `Redirect` (matching Django's own `contrib.redirects` naming) or
  something built on FLS's existing "referrer code"/"advert" vocabulary is available; this research
  doesn't pick one, it flags the constraint.
- **The slug/code field** — Dub.co's precedent name is `key`; the idea file already just says `slug`
  for the model and separately describes `{CODE}` for the opaque family. Either is available; `link`,
  `link_code`, `short_link` are not.
- **The per-access log row** — whatever this is called, avoid `LinkHit`/`LinkAccess`. `RedirectHit` or
  a name built from "referrer code"/"advert" is available.
- **The fallback-destination field** (§6) — Dub.co's `expiredUrl` is the clearest naming precedent if
  FLS adopts a distinct fallback destination for retired codes; attribute it to Dub.co if borrowed
  verbatim, since it's their coined term, not an FLS or general-industry standard.

---

status: ok
