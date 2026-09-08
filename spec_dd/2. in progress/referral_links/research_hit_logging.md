# Research: recording hits on `/go/{slug}` and `/d/{CODE}` — volume, correctness, bots, retention

Scope: the redirect entry's hit count and hit log only. Attribution of a hit to a *signup* is the
sibling `referal_tracking` feature's territory (`SignupAttribution`, `FirstTouchCount`) and is out of
scope here except where the two designs must not contradict each other (§5).

Vocabulary used below: **entry** for one configured `/go/{slug}` or `/d/{CODE}` row (the idea calls
it "the redirect table"; no model name is coined in the codebase yet), **hit** for one access of an
entry. **"Link" is FLS's existing word for an `<a href>`** (`.claude/skills/domain-glossary/SKILL.md`)
and must not become a model or field noun here — neither the entry nor the hit row should be called
`Link`/`LinkClick`/anything with "link" as a noun.

---

## 1. Row-per-hit vs counter vs both

**Both, and they answer different questions.** A bare counter (an integer column on the entry,
incremented per access) answers "how many times has this been hit, right now" in O(1) to read but
throws away *when* — which is exactly the information the idea's own justification depends on: "it's
the cheapest way to tell 'QR never scanned' from 'scanned, cookie lost' when a dealer column reads
zero." A counter alone cannot distinguish those two states from each other or from "scanned once, six
months ago, before the campaign that's failing now." Only a timestamped log can.

**A row-per-hit log is the right primitive here**, not a rollup-only design like `FirstTouchCount`'s,
for a reason specific to this feature and different from `referal_tracking`'s: `FirstTouchCount`
exists to compare campaigns against each other in aggregate (§5 of that spec explicitly declines to
distinguish individual visits — "bots crawl campaign URLs roughly uniformly... the tally exists to
compare campaigns against each other"). This feature's stated purpose is the opposite: telling apart
*a specific entry's* silence from its use, which needs "was there activity in the window I'm looking
at" per entry, not a comparative aggregate across many entries. A daily/hourly tally per entry would
get most of the way there, but loses the operator's ability to answer "did the QR code get scanned
in the five minutes after we put the poster up" — a rollup granularity has to be chosen up front and
is wrong for whichever question wasn't anticipated. A row-per-hit log defers that choice; any rollup
(daily counts, hourly counts) is a derived view over it, not a substitute for it.

**Realistic write volume.** A `/go/{slug}` shared by one influencer or a `/d/{CODE}` on one print run
is bursty, not steady: a mention could drive anywhere from single digits to a few thousand hits in an
hour, and a small-to-medium FLS install plausibly runs a few dozen to a few hundred such entries
total. Sustained load of even 100 inserts/second is trivial for Postgres on modest hardware — this is
nowhere near where a single-table `INSERT`-only log becomes a concern on its own. The place a
row-per-hit table for this specific feature actually gets uncomfortable is not insert throughput but
unbounded growth with no read pattern that benefits from an index doing less work than "add one more
partition" would buy — see §6. For an append-only table of this kind, [PostgreSQL's own partitioning
docs](https://www.postgresql.org/docs/current/ddl-partitioning.html) note partitioning pays off once
"a table used to respond in milliseconds starts taking seconds," which for a marketing-redirect hit
log at FLS's likely scale is a multi-year-away concern, not a day-one requirement (see §6).

**Is a denormalised count worth keeping alongside the log?** Yes, but for a narrower reason than
"it's convenient": Django admin's changelist needs `count(hits)` per entry to render an entry list
with a "hits" column, and computing that as a live aggregate per row on every page load
(`annotate(Count("hits"))`) is one query touching the whole hit table per admin page view, which is
exactly the growth-sensitive query class. A maintained counter field turns that into reading one
integer already on the row. What makes people keep a derived counter *despite* it being
recomputable from the log: cheap reads on a table that will eventually be large, and it degrades
gracefully — if the counter and the log ever disagree (a bug, a manual `DELETE` for a DSAR-style
purge), the log is the source of truth and the counter can be reconciled by an aggregate query when
that's cheap enough to run once, not on every page load. This mirrors why `FirstTouchCount.count`
exists as a maintained integer rather than being computed by `COUNT(*)` on every read — same pattern,
applied to unlike models. What it costs: an extra write per hit (see §2) and an explicit reconciliation
story if it's ever allowed to drift.

---

## 2. Getting the count right under concurrency

**`obj.count += 1; obj.save()` is a read-modify-write in Python and loses writes under concurrency.**
Two requests can both read `count = N`, both compute `N + 1`, and both save `N + 1` — one increment is
lost. [Django's own docs on `F()` expressions](https://docs.djangoproject.com/en/6.0/ref/models/expressions/#avoiding-race-conditions-using-f)
state this directly: *"having the database — rather than Python — update a field's value avoids a race
condition... If the database is responsible for updating the field, the process is more robust: it
will only ever update the field based on the value of the field in the database when the `save()` or
`update()` is executed, rather than based on its value when the instance was retrieved."* The fix for
the counter half of this feature is exactly what `referal_tracking/counters.py`'s
`increment_first_touch` already does in this codebase:

```python
Entry.objects.filter(pk=entry_id).update(hit_count=F("hit_count") + 1)
```

`QuerySet.update()` compiles to a single `UPDATE ... SET hit_count = hit_count + 1 WHERE ...`, which
Postgres executes as one atomic statement under a row lock it holds for the duration of that
statement only — not for the request's lifetime the way `select_for_update()` would.

**Row-level lock contention when many requests hit the same entry concurrently.** A viral spike on
one `/go/mrbeast` slug means many concurrent `UPDATE`s targeting the *same row* (the entry's counter),
which serialises: each waits for the previous transaction's row lock to release. At FLS's realistic
scale (§1) this is not a practical bottleneck — Postgres processes single-row `UPDATE`s in the
sub-millisecond range, so even a burst of hundreds of concurrent hits on one entry clears in well
under a second of aggregate lock-wait. It would only become a real concern at sustained
several-hundred-hits-per-second-on-one-slug traffic, which is outside this feature's stated use case
(marketing redirects, not a load-tested public API).

**The row-per-hit `INSERT`s do not contend with each other** the way the counter's `UPDATE`s do —
each is a new row, not a shared row being locked. The only place contention shows up in a
row-per-hit design is if the log rows are inserted with a monotonically-increasing integer primary
key, which produces "hot page" contention on the tail of the table's B-tree under very high concurrent
insert rates; FLS's existing `SiteAwareModel` UUID primary key (noted in the `referal_tracking` spec
as `"SiteAwareModel's UUID pk is populated before the row exists"`) avoids that specific pattern by
distributing inserts across the key space, at the cost of a somewhat larger index than a sequential
key would need — a reasonable trade at this scale.

**Alternatives, and which is right at what scale:**

- **Insert-only log with periodic rollup** (what `FirstTouchCount` does, at the granularity of a day):
  cheapest possible write (one `INSERT`, no read, no lock contention on a shared row at all), but the
  counter/tally is only as fresh as the last rollup run — wrong fit here, because the entry's `hit_count`
  needs to be current on every admin page load (an operator checking "did today's QR scan register yet"
  a minute after scanning it should see it), not lagging behind a scheduled job.
- **`INSERT ... ON CONFLICT DO UPDATE` on a per-day tally row** — Django exposes this via
  `QuerySet.bulk_create(..., update_conflicts=True, update_fields=[...], unique_fields=[...])`
  (Django 4.1+, requires Postgres 9.5+ and an actual unique constraint on `unique_fields`, not just
  `unique_together`). This is the right shape for a *rollup* table (mirrors `FirstTouchCount`'s own
  `filter().update()` — then — `create()` — then — `filter().update()` fallback under `IntegrityError`,
  which is the same idea implemented by hand rather than via `bulk_create`), but it answers "count per
  entry per day," not "current total on the entry," so it does not replace the `F()` increment above —
  it would sit alongside a per-day rollup table if one is ever added for reporting, which nothing in
  the idea currently calls for.
- **`F()` + `update()` directly on the entry's counter field**, per-hit — the right choice for keeping
  `hit_count` live at this feature's scale: one extra `UPDATE` per hit, no read, atomic, and Django
  documents it as the standard tool for exactly this ("having the database... update a field's value").

**Recommendation:** write the hit log row and increment the entry's counter with `F()` in the same
request — one `INSERT`, one `UPDATE`, both inside a single transaction so a failure between them
cannot leave the counter and the log disagreeing from an interrupted request (a crashed process after
the `INSERT` but before the `UPDATE` is the only way they'd diverge, and that's already recoverable by
treating the log as authoritative, per §1). No rollup table is needed unless a later reporting
feature asks for per-day-per-entry breakdowns.

---

## 3. Not making the visitor wait

**FLS already has a background task runner** (`django-tasks-db`, pinned `==0.12.0`, via Django 6
core's `django.tasks`) with two established patterns in this codebase for a "capture something, defer
the rest" flow: `freedom_ls/webhooks/events.py`'s `fire_webhook_event` (create a row synchronously,
enqueue a `@task()`-decorated function that takes only primitive/JSON-safe args — never model
instances — to do the rest) and `freedom_ls/mail/tasks.py`'s `_send_email_task` (a thin `@task()`
wrapper delegating to a plain function, for exactly the same reason: the task queue serialises
primitive arguments, and calling the plain function directly in tests bypasses the queue).

**Deferring the hit write itself through `django-tasks-db` is over-engineering for this feature.**
The redirect view's only necessary work before the 302 is: look up the entry by slug/code (one
indexed `SELECT`), write the hit (one `INSERT` plus one `F()` `UPDATE`, both trivial single-row
statements), and issue the redirect. That's on the order of one to two milliseconds of database time
on any reasonable Postgres instance — nothing close to the latency budget where "don't make the
visitor wait" becomes a real design pressure. Compare to why webhooks and mail *do* defer: a webhook
delivery makes an outbound HTTP call to a third party (unbounded latency, can fail, needs retry
logic) and mail sending talks to an SMTP/API upstream (same). A hit write has neither property — it
never leaves the local database, has no external dependency that can be slow or down, and there's
nothing to retry. Routing it through `django-tasks-db` would trade one guaranteed-fast local `INSERT`
for a *slower* path in the common case (the task framework's own enqueue is itself a database write —
`DBTaskResult` row creation — so "defer the write via a task queue" means "do an extra write to record
that a write needs to happen," which is strictly more database work per hit, not less) in exchange for
protection against a failure mode (a slow local `INSERT`) that isn't actually present here. The
pattern is right for webhooks/mail because their in-request alternative is genuinely unbounded; it's
the wrong tool for a same-database `INSERT` that stays under a millisecond.

**What could legitimately push this toward deferral later, and why none of it applies yet:** if hit
recording grows to include something slow (a synchronous GeoIP lookup against an external service, a
bot-classification call to a third-party API) that work should be deferred or done at read time
instead — but nothing in the field list under consideration (§5) needs an external call. If it does
in the future, the existing `fire_webhook_event` shape (write the row inline with everything known
at request time, defer only the genuinely slow enrichment step, keyed by the row's id) is the pattern
to reuse — not deferring the write itself.

---

## 4. Bots, prefetch and machine fetches

Every mechanism below has decades of prior art in link-shortener and email-click-tracking systems
because it is the same underlying problem: a redirect endpoint gets followed by things with no human
behind them, and the operator wants the hit count to mean "a human probably looked at this," not
"something, possibly nothing, requested this URL."

**What's detectable, and how reliable each signal is:**

- **`Purpose: prefetch` / `Sec-Purpose` request headers.** Browsers set these on speculative
  requests triggered by `<link rel="prefetch">`/`rel="prerender">` or the Speculation Rules API —
  i.e. the *browser itself* is fetching a link the user hasn't clicked yet, in anticipation they
  might. `Sec-Purpose` is the modern, `Sec-`-prefixed header (exempt from CORS preflight rules
  precisely because `Sec-`-prefixed headers are forbidden ones the browser controls, not the author's
  JS); `Purpose: prefetch` is the older, non-`Sec`-prefixed form some browsers still send, and `X-Moz`
  is relevant only for old Firefox. ([MDN: `Sec-Purpose`](https://developer.mozilla.org/en-US/docs/Web/HTTP/Reference/Headers/Sec-Purpose),
  [Chrome Platform Status: `Sec-Purpose: prefetch`](https://chromestatus.com/feature/6247959677108224))
  **Reliability: high when present, but it only covers browser-initiated speculative prefetch** — it
  says nothing about link unfurlers (Slack, Discord, iMessage, WhatsApp), which are a *server*
  fetching the URL to build a preview, not a browser speculating ahead of a click; those don't set
  `Sec-Purpose` at all. A `/d/{CODE}` QR code has no referring page to prefetch *from* in the first
  place, so this signal matters much more for `/go/{slug}` links pasted into chat apps than for print
  QR codes.
- **Known-bot user-agent lists.** Maintained, regex-pattern libraries exist and are widely used —
  [`monperrus/crawler-user-agents`](https://github.com/monperrus/crawler-user-agents) (an actively
  maintained fork of the original `crawler-user-agents` project, MIT-licensed, with wrapper libraries
  in several languages including Python) and similar lists cover known search-engine crawlers, SEO
  tools, and uptime monitors by user-agent string pattern. **Reliability: catches identified,
  well-behaved crawlers reliably; catches nothing that spoofs a normal browser UA**, which link
  unfurlers and security scanners routinely do — e.g. Slack's unfurler and many corporate email
  "safe link" scanners deliberately send a realistic browser UA precisely so sites don't block them,
  which is the opposite of what an operator wants for hit-counting purposes but is these vendors'
  actual behaviour.
- **HEAD vs GET.** Some prefetchers/scanners issue `HEAD` rather than `GET`; a redirect endpoint
  could refuse to log `HEAD` requests. **Reliability: partial and vendor-dependent** — many
  unfurlers and scanners issue a full `GET` because they need the response body (to render a preview
  card, or to actually inspect the target page's content for a safety verdict), so this signal misses
  exactly the categories that matter most.
- **IP-range lists.** Cloud-provider and known-crawler IP ranges (Googlebot's published ranges, AWS/
  GCP/Azure ranges commonly used by scanning services) can be matched against. **Reliability: noisy
  and maintenance-heavy** — ranges change, many legitimate mobile/corporate users share carrier-grade
  NAT ranges with scanning infrastructure, and this is the kind of list that goes stale unless
  actively maintained, which is a real ongoing cost for a shipped-to-other-projects feature with no
  dedicated maintainer for this specific list.
- **Timing heuristics.** A hit at the exact instant a message is posted to a chat app (before any
  human plausibly saw and clicked it) is a strong tell for an unfurler; a burst of hits from many
  distinct IPs within seconds of an email send is a strong tell for corporate link-scanning at scale
  (many mail security products fetch every link in every inbound email, from multiple scanning nodes,
  within seconds of delivery — a well-documented pattern in email deliverability and click-tracking
  literature going back to at least the early 2010s). **Reliability: good as a corroborating signal,
  poor as a sole classifier** — it needs another signal (UA, header) to turn "suspiciously fast" into
  "probably not a person."

**None of these signals is individually reliable enough to gate what gets recorded.** This is the
same conclusion `referal_tracking` already reached for its own, adjacent problem — its spec states
plainly under "Out of scope": *"Bot filtering"* and, on the rationale side, *"Bots crawl campaign
URLs roughly uniformly, so their inflation is noise spread across the comparison rather than a bias
between campaigns."* That specific argument (noise is uniform, so it doesn't bias a *comparison*)
does not transfer cleanly to this feature, because this feature's stated purpose is not comparing
entries to each other — it's telling one entry's silence from its use. A bot hit on a QR code that
otherwise got zero human scans *does* change the answer to "did anyone scan this," which is exactly
the question the feature exists to answer. That argues for **storing everything and marking it,
rather than discarding at write time**:

- **Filtering at write time (discarding suspected-bot hits before they're logged) is the wrong
  default here.** It makes the classification decision permanent and unauditable — a false-positive
  discard (a real scan misclassified as a bot) silently reproduces the exact "cookie lost, count reads
  zero" ambiguity this feature exists to resolve, with no way to tell afterward that a hit happened
  at all.
- **Filtering/annotating at read time is more defensible**: log every hit unconditionally (this is
  cheap — see §1–2), and record the signals available at write time (UA string or a bot classification
  derived from it, whether `Sec-Purpose`/`Purpose` was present) as columns or a boolean on the row.
  The admin can then show a raw hit count and a "likely human" filtered count side by side, or default
  to showing "all hits" with a note that automated traffic is included (mirroring `FirstTouchCount`'s
  `help_text` — *"the figure counts cookie mints, that bots and link unfurlers inflate it"* — stating
  the caveat once, on the field, rather than trying to solve it).
- This also keeps the design open to a later, better classifier (a maintained UA-pattern library
  added as a dependency, updated independently of this feature's own release cadence) without needing
  to re-derive history — the raw signal (UA string, headers present) is already on the row; only the
  *label* derived from it needs to improve.

References: [MDN, `Sec-Purpose`](https://developer.mozilla.org/en-US/docs/Web/HTTP/Reference/Headers/Sec-Purpose),
[Chrome Platform Status, `Sec-Purpose: prefetch` for `<link rel=prefetch>`](https://chromestatus.com/feature/6247959677108224),
[Wikipedia, Link prefetching](https://en.wikipedia.org/wiki/Link_prefetching),
[`monperrus/crawler-user-agents`](https://github.com/monperrus/crawler-user-agents),
[`dan-blanchard/crawler-user-agents`](https://github.com/dan-blanchard/crawler-user-agents) (the
original, now less actively updated than the `monperrus` fork).

---

## 5. What a hit row can hold

Read against `referal_tracking`'s own `research_attribution_privacy.md` (on the `referal_tracking`
branch, `spec_dd/2. in progress/referal_tracking/`), whose central finding is worth restating
precisely because it is the thing this feature must not contradict: *every field captured there
becomes personal data "the moment it exists" once written into a row, regardless of whether the
individual field would be personal data in isolation* — and its field-by-field minimisation table
(§7 of that document) is the menu this feature should draw from, not a separate analysis.

**The sibling feature's stated reason for keeping *no* per-visitor landing record is directly on
point and must be engaged with, not sidestepped:** `referal_tracking`'s `FirstTouchCount` exists
*because* a landing row keyed to an individual visitor is "pseudonymous data about someone who never
signed up, never saw a privacy notice, and has no account against which to hang a deletion request."
A hit-per-hit log on `/go/`/`/d/` redirects is, structurally, exactly that same category of thing: a
row recording one anonymous visit by someone who, in the majority of cases (anyone who doesn't go on
to sign up), never has an account. The two features are not analogous in every respect, though, and
the difference matters for what conclusion follows:

- `referal_tracking`'s landing data was going to be *joined to identity fields relevant to marketing
  attribution* (ad-network cookies, click IDs, UTM parameters) specifically so it could later be
  cross-referenced against ad platforms — that cross-linking capability is precisely what made the
  privacy research flag it as high-risk (§7 of that document: "every field with a cross-platform-
  linking capability... is also the field where minimisation costs the least relative to the stated
  attribution purpose").
- This feature's stated purpose is narrower and does not need cross-platform linking at all — it
  needs "did this specific entry get used, and when." Nothing here calls for reading `_ga`/`_fbp`/
  `_fbc` or capturing click IDs.

**So the resolution is not "row-per-hit is fine because this is different," nor "row-per-hit
contradicts the sibling and must be abandoned" — it's that the row must be minimised down to what
the stated purpose actually needs**, applying the same discipline `referal_tracking`'s privacy
research already worked out field-by-field, rather than inventing a separate standard:

| Field | What question it answers | What it costs |
| --- | --- | --- |
| **Timestamp** | The entire reason this table exists — "when," not just "how many." | Nothing on its own; not personal data in isolation. Keep at full precision (not truncated to day) since the idea's own justification ("scanned, cookie lost" vs "never scanned") depends on knowing *when* relative to when the poster went up or the influencer posted, which a day-level bucket can blur for a same-day burst. |
| **The entry** (FK to the redirect row) | Which slug/code was hit — the whole point of a *per-entry* count. | Nothing beyond ordinary FK cost; not personal data. |
| **`Referer` header** | Where the click came from, when the browser sends one — useful for `/go/{slug}` (was it clicked from the platform the influencer posted on, or forwarded elsewhere) but structurally near-useless for `/d/{CODE}` (a scanned QR code has no referring page). | `referal_tracking`'s own conclusion applies directly: store the parsed host, not the full URL — a full `Referer` "can carry the *previous* site's own query parameters, including that site's search terms or session tokens," which is a real leakage risk for data that isn't even this operator's to hold. Cheap to minimise, little lost for this feature's purpose (host-level "came from twitter.com" is enough; page-level detail isn't something this feature promises). |
| **User agent string** | Distinguishes a person's browser from a bot/scanner/prefetcher (§4) and is one of the only signals available for that. | Per the sibling's table: "rarely identifying alone... but is one of the standard fields used in device/browser fingerprinting." Parse to a coarse family (browser/OS/device class) at write time and consider not retaining the raw string at all — the bot-signal use case (§4) mostly survives on the parsed/coarse form; the raw string's marginal value here is small and its fingerprinting contribution is exactly the thing worth not collecting when it isn't needed. |
| **IP address** | The strongest available "was this the same visitor twice" and geography signal, and a real input to bot/scanner heuristics (§4). | The sibling document's finding applies without modification: *Breyer* (CJEU C-582/14) treats a dynamic IP as personal data for a controller with any legal avenue (even via a third party) to resolve it to a person, and once IP sits on a database row it is unambiguously personal data, full stop, regardless of the standalone-identifiability debate. Truncating (drop the last IPv4 octet / use a /64 for IPv6) or hashing with a rotating salt is the same minimisation the sibling recommends for its own IP field, for the same reason: it "loses exact-geolocation precision and any ability to correlate the *same* IP across records," which is a real capability loss only if per-visitor fraud/dedup detection is an actual goal — nothing in this idea asks for that. Given this feature's hits are, by construction, visits with **no account and no privacy-notice exposure at signup time** (unlike `SignupAttribution`, which only exists for people who did sign up and therefore did see a notice), the case for restraint here is at least as strong as the sibling's, arguably stronger: default to not storing raw IP at all, or store only the truncated/hashed form. |
| **Incoming query string** | For `/go/{slug}`, an influencer or affiliate might append their own tracking params; for `/d/{CODE}`, a QR generator might embed nothing extra, or a printer's variable-data campaign might embed a serial. | Free text arriving from outside the system, unbounded, and with no defined vocabulary — the same reasoning `referal_tracking` applied to `utm_medium` ("stored as it arrives, trimmed, lower-cased and truncated, with no vocabulary check... a closed set would bake a silent bucketing error in permanently") applies here: cap the length, store what's there, validate nothing. Whether to store the whole query string or only a fixed allow-list of recognised keys is a real design choice this research can't settle without knowing whether the redirect's own tracking parameters (appended to the *target* URL) are drawn from the incoming query string or generated independently — if they're drawn from it, at minimum those keys need to be captured; anything beyond that is optional and should default to off given the "capture only what the purpose needs" discipline above. |

**IP and user agent, together, are the two fields actually in tension with the sibling's position**,
and the honest answer is that a hit row carrying both at full precision *would* reproduce the exact
problem `referal_tracking` built `FirstTouchCount` to avoid — for potentially the majority of hits,
since most link/QR traffic never converts to a signup. The way to stay consistent with that position
without abandoning the row-per-hit design this feature's purpose actually needs (§1) is minimisation,
not a different table shape: truncate/hash IP, reduce UA to a coarse family, keep the referer to a
host, and treat the resulting row as still-technically-personal-but-substantially-de-risked, the same
posture the sibling document takes toward its own minimised fields (§7 of that document: minimising
doesn't make a field stop being personal data, it reduces re-identification power and narrows what
must be disclosed/justified). **This document could not establish** whether truncated-IP-plus-coarse-UA-
plus-timestamp is, in combination, still identifying enough at very low-traffic entries (a slug with
exactly one hit that week) to functionally re-identify a specific visit even without raw IP — this is
the same "combination of low-cardinality attributes can still be identifying" risk class Breyer-style
reasoning covers for IP alone, and a full assessment would need to consider it alongside actual entry
traffic volumes, which this research has no visibility into.

**Retention position for a project shipping into other people's deployments**, consistent with the
sibling's §6 conclusion (retention must be a *defensible, purpose-tied period*, not indefinite by
default, and the "operational lifetime of the interest it serves" is the right anchor): the interest
here — "can this specific entry's silence be told apart from its use" — has a natural, much shorter
horizon than marketing-attribution reporting, because the question stops being open once the
poster's run is over or the influencer's post has aged out of relevance. A default retention window
on the order of weeks to a few months for the *raw* per-hit fields (with the maintained counter, per
§1, persisting indefinitely as the derived, already-anonymous number) is defensible and considerably
shorter than the 12–24-month anchor the sibling document uses for its own, differently-scoped
attribution data — this feature's purpose simply doesn't need per-hit detail to live as long.

---

## 6. Retention and growth

**What the table looks like after two years, at this feature's realistic scale (§1):** a few hundred
entries, each accumulating anywhere from a handful to tens of thousands of hits depending on how
"viral" any given campaign got, sums to a table on the order of low hundreds of thousands to a few
million rows for a small-to-medium install running this feature continuously for two years without
any pruning. That is comfortably within what an unpartitioned, properly indexed Postgres table
handles well — `(entry, hit_at)` and `(hit_at)` indexes serve both "hits for this entry over time"
and "hits across all entries in a date range" without needing partitioning at that row count.
**Partitioning from the start is premature** for this feature at FLS's stated scale; the
[PostgreSQL partitioning documentation](https://www.postgresql.org/docs/current/ddl-partitioning.html)
frames it as valuable once query performance visibly degrades on a table that's grown very large,
which is a multi-year-away concern here, not a day-one requirement — and premature partitioning adds
real operational complexity (partition creation/maintenance, migrations that must be partition-aware)
that a downstream operator running a modest install gets no benefit from.

**Given §5's retention conclusion (raw per-hit fields kept weeks-to-months, not years), "what does it
look like after two years" changes character entirely**: if retention prunes the per-hit rows (or the
identifying fields on them) after a bounded window, the table's steady-state size is bounded by
*recent* traffic, not cumulative traffic since launch — which is a much smaller and more predictable
number, and removes the "grows without bound" property altogether for the fields that matter most for
privacy. The maintained counter (§1) is the only thing that legitimately accumulates forever, and it's
a single integer per entry — no growth concern at all.

**What a downstream operator has to be told, regardless of which retention default ships:** the same
thing `referal_tracking`'s idea already flags for its own tables and `django-tasks-db`'s own
housekeeping story (`prune_db_task_results`, referenced in
`spec_dd/3. done/2026-07-09_09:42_support-concrete-project-deployment-master-decomposed-into-specs/research_django_tasks_durable_backend.md`)
establishes as FLS's existing pattern for bounded growth: **a table that accumulates one row per
event needs an explicit retention/pruning story stated in FLS's own docs, not left to the operator to
discover.** If pruning is not built in from day one, the operator needs to be told plainly that the
table grows without bound and that they are responsible for its retention decision — silence on this
point is itself a choice, and the wrong one to make by omission for a feature whose own fields (§5)
carry a data-protection retention obligation regardless of how big the table gets.

---

## 7. Reading it back

**Django gives two things for free that matter directly here:**

- **`date_hierarchy`** on a `ModelAdmin` — drill-down navigation by year/month/day on a date/datetime
  field, at no extra code beyond naming the field. This is the direct, no-cost answer to "hits over
  time per entry": set `date_hierarchy = "hit_at"` (or whatever the timestamp field is named) on the
  hit-log admin, exactly as `referal_tracking` already does for both its own admins
  (`SignupAttributionAdmin.date_hierarchy = "signed_up_at"`, `FirstTouchCountAdmin.date_hierarchy =
  "day"`).
- **`list_filter`** — filtering the changelist by entry, by a coarse bot/human classification (§4), or
  by UA family (§5), all with no custom code beyond listing the field names, provided the underlying
  columns are indexed (`referal_tracking`'s own note: `list_filter` uses Django's default
  `AllValuesFieldListFilter`, "backed by indexes," in preference to a custom cached filter sourced from
  the larger, accumulating table — the same "keep filters cheap on the table that grows" reasoning
  applies here).

**The well-known trap: `ModelAdmin.show_full_result_count` defaults to `True`, and `count()` on a
large table for the changelist paginator is exactly what that setting controls.** Per the Django 6.0
docs: *"Set `show_full_result_count` to control whether the full count of objects should be displayed
on a filtered admin page (e.g. `99 results (103 total)`). If this option is set to `False`, a text
like `99 results (Show all)` is displayed instead. The default of `show_full_result_count=True`
generates a query to perform a full count on the table which can be expensive if the table contains a
large number of rows."*
([Django 6.0 admin docs, `ModelAdmin.show_full_result_count`](https://docs.djangoproject.com/en/6.0/ref/contrib/admin/#django.contrib.admin.ModelAdmin.show_full_result_count))
This is a real, well-documented Django admin performance trap on any table that grows large
([Django ticket #13643, "Admin changelist page very slow with postgresql and a huge table"](https://code.djangoproject.com/ticket/13643);
background on the underlying paginator behaviour in
[Django ticket #8408, "Add a way to avoid QuerySet.count() in admin pagination"](https://code.djangoproject.com/ticket/8408)),
and it is a one-line fix (`show_full_result_count = False` on the hit-log's `ModelAdmin`) that costs
nothing at small scale and avoids the trap entirely at large scale — worth setting from the start on
the hit-log admin specifically (the counter-bearing entry admin, with far fewer rows, doesn't need it).

**What the pattern already established by `SignupAttributionAdmin`/`FirstTouchCountAdmin` suggests
for a hit-log admin**, and is directly reusable: `list_select_related` for the FK to the entry (avoid
N+1 on every row rendering which entry it belongs to), `list_display` covering entry, timestamp, and
whatever coarse bot/human signal exists, `search_fields` kept to genuinely searchable text fields
only (not IP/UA, mirroring the sibling's own choice: *"Click identifiers, the three ad-cookie values,
`client_ip` and `user_agent` are near-unique per visitor. They appear on the detail view and in the
export, never in a filter"* — the same logic applies to `search_fields`/`list_filter` here: a
near-unique field belongs on the detail view, not as a list-level filter or search target, both
because it's not a useful grouping axis and because putting it in a searchable/filterable index
surface makes it easier to accidentally build a per-visitor lookup tool out of what's meant to be an
aggregate view).

---

## What this research could not establish

- Whether truncated-IP-plus-coarse-UA-plus-timestamp remains re-identifying in combination at very
  low-traffic entries (§5) — needs real traffic-volume data this research has no access to.
- Whether the redirect's own outbound tracking parameters (appended to the target URL per the idea)
  are meant to be drawn from the incoming query string or generated independently of it — this
  changes whether any part of the query string is *required* to capture, not merely optional (§5).
- A concrete default retention window in days/weeks — this research argues for "weeks to a few
  months" as shorter than the sibling's 12–24-month anchor, but the exact number is a product
  decision, not something derivable from the sources here.

---

status: ok
