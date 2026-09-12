# Research: operator experience for referral links (`/go/` and `/d/`)

Scope: what the builder running a referral or QR campaign actually needs from an admin-only
create-and-manage flow, where general-purpose link tools get this wrong, and what to deliberately
leave out. Written against the decisions already fixed in `idea.md`: no bespoke UI, the Django admin
changelist and its CSV export are the whole interface, no QR image generation, one model for both
`/go/{slug}` and `/d/{CODE}`, an optional FK to `Organisation` or an advert-code string.

Vocabulary note: FLS's own glossary reserves **"link"** for an `<a href>`; this document never uses it
as a noun for the model or its rows. The operator-facing noun throughout is **entry** (a redirect
entry), matching the idea's own "redirect table" framing. Copy aimed at the person running the
campaign says **builder**, not "administrator" or "user" (`.claude/skills/brand-guidelines/SKILL.md`).

---

## 1. The operator's real workflow

Every general-purpose link tool structures the job the same way, whether the interface is a SaaS
dashboard or (as here) a changelist: **pick a destination, pick or accept a short form, hand the
short form to someone else, then come back later to ask "is it working" and "which one is winning."**
Bitly frames its own dashboard as existing to turn "random URLs" into a history the operator can find
things in again, and its help pages describe adding a title specifically so the dashboard reads as
labelled campaigns rather than raw links
([Bitly: Unlocking Business Insights With the Bitly Dashboard](https://bitly.com/blog/bitly-dashboard/)).
Dub.co's newer "link builder" bundles the destination, a UTM template, tags/folders, and a QR code
into one creation screen precisely because operators found assembling those by hand, then hand-typing
them onto a flyer or into a partner email, was the friction point
([Dub: Introducing the new Dub Link Builder](https://dub.co/blog/new-link-builder);
[Dub Links product page](https://dub.co/links)).

Mapped onto this feature's five steps:

1. **Create the entry.** Operator supplies (or FLS derives) the code and the destination. This is
   where every tool invests the most UI, because it is where the irreversible mistakes happen (§2).
2. **Get the URL to hand off.** A partner needs `https://example.com/go/mrbeast` to put in their bio;
   a designer needs `https://example.com/d/P5H2B3C8` to hand to whoever renders the QR image (FLS
   does not generate the image — the operator or their designer does, from the plain URL, per the
   idea's decision). The friction here is entirely about whether the operator has to *assemble* that
   string themselves (concatenate domain + path + code by hand, easy to typo) or can copy it
   finished. Bitly, Rebrandly and Short.io all hand back a copy-ready finished short URL the instant
   the entry is created — none of them make the user construct it.
3. **Check whether it is working.** The operator reopens the tool days or weeks later and asks "has
   anyone used this yet." This is a changelist-reading task, not a creation task (§3).
4. **Compare entries.** "Which of my five dealer codes is actually producing traffic." Also a
   changelist task — sorting/filtering by hit count.
5. **Retire one.** A campaign ends, a partner relationship ends, a print run gets pulped. The
   operator wants the code to stop working (or keep working but stop mattering) without losing what
   already happened on it (§5).

The friction industry tools name most often, matched against this feature's shape:

- **Assembling the final URL by hand** — solved for free here: the admin's own base URL plus the
  code is deterministic, so a computed, copyable field on the change form (§2, §8) removes this
  entirely, no bespoke UI required.
- **Not knowing if a QR code is dead until someone complains.** BL.INK's product marketing calls
  this out directly: QR codes break silently when a destination changes or was wrong to start with,
  and by the time anyone notices, the print run is already circulating
  ([bl.ink: Say goodbye to broken QR codes and dead-end links](https://www.bl.ink/blog/broken-qr-codes-dead-end-links)).
  A hit-count column that reads zero after a poster has been up for two weeks is this feature's own
  (much cheaper) version of that same signal — the idea file already names this as the reason hits are
  timestamped rather than just counted ("it's the cheapest way to tell 'QR never scanned' from
  'scanned, cookie lost' when a dealer column reads zero").
- **Losing track of which entry is which once there are more than a handful** — this is the naming
  problem (§4), and it is the complaint that shows up hardest in practice: Bitly's own marketing
  leads with "instead of staring at random URLs, title links like 'Summer Sale – Instagram Story'"
  because an untitled dashboard becomes unusable at scale
  ([Bitly dashboard](https://bitly.com/blog/bitly-dashboard/)).

## 2. Creating an entry without a mistake

Four concrete failure modes, and what stops each one being expensive:

**A mistyped target URL that only surfaces after printing.** Nothing in a plain `URLField` catches a
target that is syntactically valid but wrong (a live competitor's domain typed instead of the
client's, a `http://` copied where `https://` was meant, a trailing path segment missing). The cheapest
mitigation that is genuinely worth building is a **"test this" affordance on the change form**: a
button or link that performs the redirect (or previews the final resolved URL including appended
tracking parameters) without incrementing the hit count, so the operator sees exactly where a scan
would land before it is committed to paper. This is standard practice in every reviewed tool —
Bitly, Rebrandly and Dub.co all show the destination and let the operator click through it from the
edit screen before publishing anywhere. A full "preview of the final redirect target with tracking
parameters appended" (not just the raw target URL) is worth building specifically *because* this
feature appends parameters server-side — the operator otherwise cannot see the string a partner's
analytics will actually record. **Validating the target is reachable** (a live HTTP HEAD/GET check at
save time) is the next tier down: useful, but it adds an outbound network call to an admin save and
cannot catch "reachable but wrong" (a valid URL for the wrong campaign), so it is polish, not the
build.

**A slug that collides or is already taken.** `django.db.models.SlugField` plus a `unique=True`
constraint (scoped to `Site`, per FLS's tenancy model) gives Django's own admin form validation for
free — the save fails with a field-level error before the row is written, which is exactly Bitly's own
behaviour ("this custom link is taken... you need to use a different back-half";
[Bitly Support: What can I do if my customized link has been taken?](https://support.bitly.com/hc/en-us/articles/230561307-What-can-I-do-if-my-customized-link-has-been-taken)).
Nothing further is needed — Django's uniqueness validation at the form layer is the whole mitigation
and it is already free.

**Forgetting the tracking parameters.** Not applicable in the same shape here as in Bitly/Rebrandly,
because per the idea and prior decisions this feature appends tracking parameters server-side at
redirect time rather than asking the operator to hand-assemble a UTM-laden target URL (that is the
job Dub's "UTM builder with saved templates" exists to do for tools where the operator *does* type the
full destination by hand —
[Dub: Ultimate Guide to UTM Tracking](https://dub.co/blog/utm-guide);
[Dub UTM Builder](https://dub.co/tools/utm-builder)). The risk that remains is narrower: the operator
gets the *destination* wrong, which the preview affordance above already covers.

**An entry created against the wrong site on a multi-tenant install.** This is an FLS-specific risk
with no analogue in single-tenant tools. `SiteAwareModelAdmin` (`freedom_ls/site_aware_models/admin.py`)
already `exclude`s the `site` field and every existing site-aware admin (`LegalConsentAdmin`,
`SiteSignupPolicyAdmin`) relies on the current-site middleware to set it invisibly on save — so this
failure mode is already closed by the base class this model will subclass, not something the create
form needs to solve itself.

**What is worth the build vs. polish, summarised:**

| Mitigation | Worth building | Why |
| --- | --- | --- |
| Copyable finished URL on the change form (no hand assembly) | Yes | Near-zero cost, removes a whole class of transcription error |
| "Test this" / preview of final redirect incl. tracking params | Yes | The one thing an operator cannot otherwise see before printing |
| Slug uniqueness validation | Yes (free) | `SlugField(unique=True)` + `Site` scoping is stock Django |
| Live reachability check of target URL on save | Polish | Extra outbound call per save; doesn't catch "wrong but valid" |
| Bespoke non-admin create form/wizard | Out of scope | Idea has already ruled this out — admin only |

## 3. What the changelist has to show

The questions an operator opens the screen to answer, matched to changelist mechanics:

- **"Is entry X live, and what does it point at?"** → `list_display` needs the code/slug, the
  target (or a truncated display method for it — a raw `URLField` value is long and unfielded),
  and the active flag.
- **"Which entries are producing traffic, and which are dead?"** → hit count as a **column**, sortable.
  This is cheap: it is a denormalised integer already kept on the row per the idea's own model shape
  ("redirect table... hit count"), so displaying it costs nothing beyond listing the field name in
  `list_display`. What it does *not* do for free is answer "producing traffic *recently*" — a raw
  cumulative count reads identically for "50 hits last week" and "50 hits two years ago, then
  nothing." If that distinction matters, the honest way to get it without a bespoke UI is a computed
  `list_display` method that also reports the most recent hit timestamp (from the hit-log side), not
  a second denormalised counter.
- **"Is this a `/go/` or a `/d/` entry?"** → belongs as a filter, since one model serves both routes
  per the idea's decision and the operator will frequently want to see referrals separately from QR
  codes. Cheap to derive (either an explicit route/kind field, or computed from which of `slug`/`code`
  is populated) and low-cardinality, so it is exactly the shape `list_filter` wants.
- **"Which entries belong to Organisation X / advert campaign Y?"** → `Organisation` FK is a natural
  `list_filter` (Django renders FK filters as a dropdown of the related objects automatically — see
  §8) and low-cardinality by construction (there are only as many organisations as the deployment
  has). The advert-code string is a different case: free text, and its cardinality is exactly as
  unbounded as the number of adverts ever run. That is the shape the sibling `referal_tracking` spec
  explicitly calls a trap and resolves by keeping near-unique fields off the filter list and on the
  detail view and export only ("Click identifiers... are near-unique per visitor. They appear on the
  detail view and in the export, never in a filter" —
  `spec_dd/2. in progress/referal_tracking/1. spec.md` §5.7). The same reasoning applies here: advert
  code is a reasonable `search_fields` entry (exact or partial text match) but a poor `list_filter`
  entry once a deployment has run more than a handful of campaigns, because Django's default
  `list_filter` renders one sidebar option per *distinct value in the table*, and a filter with
  hundreds of near-unique options is not navigable and is expensive to render (Django's own facet-count
  documentation warns that filters "increase the number of queries on the admin changelist page in
  line with the number of filters," with `show_facets = ShowFacets.NEVER` offered as an escape hatch
  for exactly this cost —
  [Django admin reference: `ModelAdmin.list_filter`](https://docs.djangoproject.com/en/6.0/ref/contrib/admin/#django.contrib.admin.ModelAdmin.list_filter)).
- **"When was this created, and how has volume trended?"** → `date_hierarchy` on the entry's
  `created_at` (when the operator set the campaign up), not on hit timestamps — the hits are a
  separate log-shaped table (per the idea, hits get their own timestamped rows), and `date_hierarchy`
  operates on the changelist's own model, one field, via `QuerySet.datetimes()`
  ([Django admin reference: `ModelAdmin.date_hierarchy`](https://docs.djangoproject.com/en/6.0/ref/contrib/admin/#django.contrib.admin.ModelAdmin.date_hierarchy)).
  If hits get their own (probably read-only) admin, that changelist is the place for `date_hierarchy`
  on the hit timestamp — drilling "how many scans this week" belongs there, not on the entry
  changelist.
- **Search** should cover the slug/code and any label/notes field (§4) and the advert-code string —
  the free-text fields an operator would actually type into a search box trying to relocate one entry
  among many. It should not need to cover the target URL; nobody searches for a campaign by pasting
  in the destination they're trying to remember the code for.

## 4. Naming and describing an entry

A slug or code is an identifier, not a label — `/d/P5H2B3C8` tells the operator nothing eighteen
months later about which print run, which venue, or which client it was made for. Every reviewed tool
treats this as solved and non-optional:

- **Bitly** gives every link a **title** distinct from its back-half, specifically so the dashboard
  reads as labelled campaigns ("Summer Sale – Instagram Story") rather than a list of codes, and
  documents renaming a link as routine housekeeping
  ([Bitly dashboard](https://bitly.com/blog/bitly-dashboard/)).
- **Dub.co** groups entries with **tags and folders**, filterable in its analytics, precisely so an
  operator managing many campaigns at once doesn't have to remember codes at all
  ([Dub Links](https://dub.co/links)).
- **Rebrandly**'s bulk-import format takes a back-half and destination as the only required columns
  but supports additional metadata columns alongside them
  ([Rebrandly: How should I format my CSV file for importing links?](https://support.rebrandly.com/en/articles/469626-how-should-i-format-my-csv-file-for-importing-links)).

**The two-year-old-entry problem is real and specific to this feature's own naming choices.** `/go/`
slugs are operator-chosen and somewhat self-documenting by construction (`/go/mrbeast` names the
referrer). `/d/{CODE}` entries are the opposite: the idea specifies an opaque code for QR use, which
by design carries no meaning, so **for the `/d/` route specifically, a label is not a nicety — it is
the only way the operator will ever know what a code was for once the print run is a memory.** What
operators genuinely miss when this is absent, based on what every competitor ships as a baseline: a
short free-text label/title, and a longer free-text notes field (for "printed on the June flyer for
the downtown venue, retired after the venue closed"). An owner field and formal tags/campaign grouping
are more than this feature needs to invent: the FK to `Organisation` already gives *referral* entries
their grouping axis for free, and the advert-code string already gives *QR* entries a natural grouping
key if the operator chooses to reuse codes across a campaign's material. A dedicated tags/campaign
model would be new machinery duplicating what those two fields already cover — worth flagging as
something the idea should decide to build or explicitly not build, not something this research
resolves.

## 5. Deactivation, deletion and the audit trail

**Deactivation and deletion are not interchangeable, and practice is unanimous that a code circulating
on printed material must never be deleted.** QR-code and short-link vendors converge on the same
distinction: an "auto-archive"/"deactivate" style operation hides the entry from active views while
the **redirect and its history stay intact**, versus an "expire"/delete operation that actually stops
the redirect from resolving
([QR Code Generator: making short URLs and technical QR code best practices](https://www.qr-code-generator.com/blog/making-short-urls-technical-qr-code-best-practices/)).
The stated reasoning is worth repeating because it is the strongest single piece of guidance this
research surfaced: **"design the post-expiry page assuming a poster from six months ago is still
scanning into it today"** — printed material has no recall mechanism, so a scan against a retired code
must land somewhere coherent (a redirect to a generic "this campaign has ended" page, for instance)
rather than 404 or, worse, silently resolve to whatever now occupies a deleted, reused slug
([Linked.Codes: Time-limited short links — expiring URLs done right](https://linked.codes/blog/time-limited-short-links-expiring-urls)).
A second, sharper risk specific to *deletion* (as opposed to deactivation) that the same source names:
if the code is ever freed for reuse, a second entry created later with the same slug/code would
silently inherit traffic from stale printed material aimed at the first — a reason on its own to make
codes and slugs permanently unique once issued, never recycled after deletion.

For this feature's shape — `active` boolean already named in the idea's own model sketch — the
practice this research supports is: **`active=False` stops the redirect (or sends it somewhere
explicit, e.g. a "campaign ended" landing) but the row and its hit history are never deleted.** Model
deletion should be reserved for genuine mistakes (an entry created in error, never printed, never
handed to anyone) rather than for retiring a campaign. This mirrors FLS's own existing convention on
`Learner.is_active` — "means 'removed', never deleted... nothing cascades" (domain glossary) — so it
is consistent with a pattern this codebase already uses elsewhere, not a new idea being imported.

**What happens to hit history in each case:** deactivation leaves it untouched and queryable exactly
as before (it is what tells the operator the entry *used to* work before being retired). Deletion, if
it is ever allowed at all, should be understood to take the hit history with it unless the hit log
rows are deliberately kept independent of the parent row via `on_delete=SET_NULL` or similar — a
decision the spec stage needs to make explicitly rather than let cascade behaviour decide by default.

## 6. Bulk work

**Operators create these in both shapes — one at a time for referral partners, in batches for print
runs — and the two have different cheapest-adequate answers.**

`/go/{slug}` entries are created reactively, one at a time, as each referral partner is signed up —
this is inherently a one-row-at-a-time operation and the standard Django admin "Add" form is already
adequate for it.

`/d/{CODE}` entries for a print run are the batch case named directly in the worker brief ("a print
run needing fifty codes is a real case"), and it is a real pattern in the industry, not a hypothetical:
Rebrandly ships CSV bulk-import specifically for this
([Rebrandly: guide to importing links](https://support.rebrandly.com/en/articles/469544-rebrandly-s-guide-to-importing-links);
[Rebrandly: CSV format for importing links](https://support.rebrandly.com/en/articles/469626-how-should-i-format-my-csv-file-for-importing-links)),
and Short.io ships a dedicated "Bulk Create" action for generating QR-bound entries in batches
([Short.io: How to Create QR Codes in Bulk](https://blog.short.io/how-to-create-qr-codes-in-bulk/)).

Ranked by cost against this feature's "admin-only, no bespoke UI" constraint:

1. **Nothing (cheapest, and arguably adequate).** The Django admin's stock "Add" form, used fifty
   times, works. It is tedious but requires zero new code.
   ([Django admin actions](https://docs.djangoproject.com/en/6.0/ref/contrib/admin/actions/))
2. **A management command that mints N entries with generated codes.** Cheap to build, matches FLS's
   existing convention of using management commands for bulk/operational tasks (`makemigrations`,
   `migrate` are the pattern already in `CLAUDE.md`), and is the natural place to guarantee
   collision-free code generation at scale rather than relying on fifty individual admin-form retries
   against a uniqueness constraint. This is the option worth costing against actual demand — it is
   more than "nothing" but far less than a bulk-import UI.
3. **A `django.contrib.admin` "bulk add" action or CSV-upload admin view.** This is what Rebrandly and
   Short.io actually ship, but it is meaningfully more build than a management command for the same
   outcome, and it duplicates functionality a management command already gives an operator with shell
   access. Given the idea's own constraint that the admin changelist is the whole interface, and that
   the person creating fifty QR codes for a print run is plausibly the same person (or the same team)
   who can be handed a one-line command to run, this tier is the one most likely to be over-building
   for the actual audience.

**Recommendation for the idea to state explicitly:** default to the stock admin form for referral
entries (no new work), and treat batch QR-code minting as a candidate for a management command rather
than an admin bulk-upload feature, deferring the decision on whether it's needed at all until real
print-run volume is known — the same posture the sibling `referal_tracking` spec takes toward its own
key-cap setting ("nobody will know until real traffic exists").

## 7. Reporting expectations, and the gap

**What a marketer assumes a link tool tells them, drawn from the reviewed tools' own advertised
feature sets:**

- Click-through rate and engagement trends over time, not just a cumulative total
  ([Bitly dashboard](https://bitly.com/blog/bitly-dashboard/)).
- **Unique vs. total clicks** as two separate numbers — the industry-standard distinction is that
  total clicks show raw activity while unique clicks estimate *reach* (deduplicated by
  device/browser), and tools present both side by side because they answer different questions
  ([SendX: Unique Clicks vs Total Clicks](https://www.sendx.io/blog/unique-clicks-vs-total-clicks);
  [Bitly: Unique Clicks vs. Total Clicks](https://bitly.com/blog/unique-clicks-vs-total-clicks/)).
- **Conversion rate** — clicks that turned into the outcome the campaign existed for.
- **Geography and device** breakdowns of who clicked, standard in every reviewed platform's
  analytics tier.

**What this feature will actually have**, per the idea and the sibling spec: a hit count and
timestamped hit rows on the entry itself (arrival data only — no unique-visitor deduplication, no
geography, no device, no referrer beyond what the sibling capture middleware separately records for
signups), plus — where the visit goes on to a signup — attribution rows from `referal_tracking`
(`SignupAttribution`, keyed on the signed-up `User`, and `FirstTouchCount`, a daily tally per
attribution key) via that feature's cookie-based first-touch capture.

**Name the gaps explicitly, so the idea can state them as deliberate boundaries rather than silent
omissions:**

- **No unique-visitor count.** The hit log records every hit, not deduplicated visitors; "50 hits"
  could be one person refreshing fifty times or fifty different people. Nothing in either this
  feature or `referal_tracking` deduplicates by device or cookie at the hit-log level (the sibling
  spec deduplicates only the *first-touch tally*, and only within its own 90-day cookie window, not
  against this feature's hit log at all).
- **No device or geography.** Neither the idea's hit-log fields nor `referal_tracking`'s captured
  fields include device type, browser, or location. `SignupAttribution` does capture `client_ip` and
  `user_agent`, but only at signup time, on the account that eventually converts — never on the
  redirect hit itself, and never surfaced as a report.
- **No click-through rate in the conventional sense**, because there is no "impressions" denominator
  on this feature's own data — a hit count has no rate without something to divide it by.
- **Conversion rate is answerable, but only by joining forward, and only under specific conditions.**
  The sibling spec's own scope statement is precise about what is and is not reachable this way: "Joining
  forward stays possible: which channel produced learners who registered for a course, started one or
  finished it is reachable from the user" (`referal_tracking` spec §3). Concretely:
  - **Answerable by joining an entry's referral/advert code to `SignupAttribution.advert_code`
    (or the sibling feature's `ref` referrer-code work, currently deferred there) and onward to
    course registration/progress:** "of the people who scanned this QR code and signed up, how many
    registered for a course, started it, or finished it." This is the sibling spec's promised join —
    `SignupAttribution` is keyed on the signed-up `User`, and everything downstream (registration,
    `CourseProgress`) is reachable from `User` via `Learner`.
  - **Answerable, with the caveat that FLS's whole attribution model is first-touch-only:** a
    conversion rate for a *campaign*, using `FirstTouchCount` as the denominator and
    `SignupAttribution` rows sharing that campaign's key as the numerator — "signups over first
    touches, both grouped by campaign, is a conversion rate" (`referal_tracking` spec §1). This is a
    rate over an attribution *key* (UTM/advert-code tuple), not over one specific entry's hit count,
    so it only lines up cleanly with an entry's own numbers when that entry is the sole source of
    traffic carrying its advert code.
  - **Unanswerable, and worth naming as a boundary rather than a bug:** the conversion rate for one
    *specific entry's scans*, if the same advert code or referral identity is reused across more than
    one entry or channel — the sibling spec is explicit that "any slice of the denominator outside the
    tally's own key" has no answer, and this feature's hit log and `referal_tracking`'s tally are two
    separate counting systems with no shared row-level key, only a shared *value* (the advert code or
    slug string) that the operator has to line up by hand across two changelists. There is no query
    Django's admin can express, and no join FLS ships, that answers "how many of *this entry's hits*
    became signups" directly — only "how many signups carried this entry's code," which is a related
    but distinct number whenever an entry's code isn't perfectly unique to that one entry's traffic.
  - **Unanswerable regardless of joins:** multi-touch attribution (a person who scanned two different
    QR codes before signing up), and anyone who clicked but is not this system's `User` — an
    anonymous hit with no eventual signup leaves no trace beyond the hit-log row itself.

## 8. Django admin specifics worth knowing

**Free, and worth using:**

- **`readonly_fields`** can render a computed method's output (a model method or `ModelAdmin` method),
  not just stored field values, and HTML-escapes string output by default unless wrapped in
  `format_html()`. This is the mechanism for the copyable finished-URL affordance in §2 — a
  `readonly_fields` entry backed by a method that concatenates the site's domain, the route prefix
  (`/go/` or `/d/`), and the code/slug, rendered as a clickable/copyable link on the change form, with
  zero new UI beyond the admin's own change-form rendering
  ([Django admin reference: `readonly_fields`](https://docs.djangoproject.com/en/6.0/ref/contrib/admin/#django.contrib.admin.ModelAdmin.readonly_fields)).
- **`list_display` accepts the same computed methods**, and the `@admin.display(ordering=...)`
  decorator lets a computed column still be sortable by naming which underlying database field to
  sort on — relevant if hit count display ever needs to be a computed "recent activity" figure rather
  than the raw stored counter, while staying sortable
  ([Django admin reference: `ModelAdmin.list_display`](https://docs.djangoproject.com/en/6.0/ref/contrib/admin/#django.contrib.admin.ModelAdmin.list_display)).
- **`list_display_links`** controls which column(s) open the change form; useful if the copyable URL
  itself is shown as a column and should *not* be the click-target (to avoid an accidental navigation
  away when the operator meant to select the text to copy it)
  ([Django admin reference: `list_display_links`](https://docs.djangoproject.com/en/6.0/ref/contrib/admin/#django.contrib.admin.ModelAdmin.list_display_links)).
- **`actions`** (admin actions) is the free-tier way to add a "bulk deactivate" operation across
  selected rows in the changelist — a plain function operating on a queryset, no new view needed
  ([Django admin actions documentation](https://docs.djangoproject.com/en/6.0/ref/contrib/admin/actions/)).
  This is a much cheaper way to get "retire a batch of entries at campaign end" than any bespoke UI,
  and fits directly under §5 and §6.
- **`date_hierarchy`** drills the changelist by year/month/day on one `DateField`/`DateTimeField`,
  using `QuerySet.datetimes()` internally, and Django's own docs flag a caveat when `USE_TZ = True` —
  timezone-aware querysets need the same care `datetimes()` itself documents
  ([Django admin reference: `date_hierarchy`](https://docs.djangoproject.com/en/6.0/ref/contrib/admin/#django.contrib.admin.ModelAdmin.date_hierarchy)).

**Known limitations that bite for this shape of data:**

- **`list_filter` on a high-cardinality field is a documented trap, not a folk theory.** Django's own
  facet-count documentation warns that filters cost a query each, with `show_facets = ShowFacets.NEVER`
  as the prescribed mitigation when a filter set gets expensive
  ([Django admin reference: `ModelAdmin.list_filter`](https://docs.djangoproject.com/en/6.0/ref/contrib/admin/#django.contrib.admin.ModelAdmin.list_filter)),
  and the default `AllValuesFieldListFilter` behind a bare field name in `list_filter` renders one
  sidebar entry per distinct value in the table — exactly the failure mode the sibling
  `referal_tracking` admin already designed around by keeping near-unique fields (click identifiers,
  IPs, user agents) off `list_filter` entirely and reserving them for the detail view and CSV export
  (`referal_tracking` spec §5.7, quoted in §3 above). The advert-code field on this feature's entries
  is exactly this shape once a deployment has run more than a handful of campaigns.
- **Sort order on a non-indexed column costs more than it looks like it should**, because the
  changelist appends the primary key to any ordering automatically — worth an index on hit count if
  "sort by most active" becomes a real operator behaviour rather than an occasional glance.
- **`list_select_related`** is the free fix for the `Organisation` FK showing up in `list_display`
  without an N+1 query per row — `LegalConsentAdmin`'s own `list_select_related = ["user"]` is the
  precedent already in this codebase (`freedom_ls/accounts/admin.py`).
- **Unfold (`unfold.admin.ModelAdmin`)**, which every FLS admin class already subclasses via
  `SiteAwareModelAdmin` (`freedom_ls/site_aware_models/admin.py`), restyles the stock admin but does
  not change any of the above mechanics — `readonly_fields`, `list_display`, `list_filter`, `actions`
  and `date_hierarchy` all behave as documented by Django itself; Unfold is a skin, not a different
  API surface, for the purposes of this feature.

---

## What this research could not establish

- No first-party, citable source of *specific, attributed* user complaints (G2/Capterra review text)
  about link tools' naming, tagging, or slug-collision handling — review sites returned 403 to direct
  fetch, and web search summarized only vendor marketing copy rather than verbatim complaints. The
  claims in §1 and §4 about what operators miss are grounded in what competing tools *ship as a
  baseline feature* (title, tags, preview, copy-ready URL), which is a reasonable proxy for demand
  (nobody ships and markets a feature nobody asked for) but is not the same evidentiary weight as a
  quoted complaint.
- No source on whether FLS's `Organisation` model, when used as the FK target for a referral entry, is
  expected to be one-to-one with a referral partner or one-to-many (one organisation running several
  `/go/` slugs) — this is a modelling question for the spec stage, not something general
  link-management-tool research resolves, since none of the reviewed tools has an analogous
  multi-tenant "organisation" concept.
- No source establishing a numeric threshold for when an advert-code `list_filter` becomes
  "too many values to be useful" in Django's admin — the Django docs describe the cost mechanism
  (one query per filter, one option per distinct value) but not a specific cardinality above which it
  becomes unusable; the sibling spec's own precedent (near-unique fields never in `list_filter`)
  is the safest reference point rather than a numeric line.

status: ok
