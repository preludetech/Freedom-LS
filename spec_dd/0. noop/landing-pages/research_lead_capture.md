# Research: lead capture ("leave your contact details, no account")

Scope: the fourth landing-page call to action — a public visitor leaves contact details without
creating a `User`. The other three CTAs (sign up, apply to a course, register interest in a
coming-soon course) already exist and all require an account; this is genuinely new ground for FLS.

## 1. The data

### Naming

FLS has no existing noun for this row. Checked against
`.claude/skills/domain-glossary/SKILL.md` §"Words that are already taken" (`grant`, `item`, `link`,
`slot`, `collection`, `course item`, `is_active`, `learner`) — none of them fit or are threatened by
this concept, and no model in the tree is called `Lead`, `LeadCapture` or similar
(`freedom_ls/**/models.py` grepped clean). **"Lead" is coined here** — it is the ordinary marketing
word for "a contact who is not yet a `User`, `Learner`, `CourseInterest` or `CourseApplication`" —
and is used for the rest of this document on that basis. It does not collide with `CourseInterest`
(which requires a `User`, see §2) or with the `referal_tracking` idea's future "attribution row"
(`spec_dd/2. in progress/referal_tracking/idea.md`), which is keyed to a learner and does not exist
yet.

### The minimum row

Following the shape of `CourseInterest` and `CourseApplication`
(`freedom_ls/course_interest/models.py`, `freedom_ls/course_applications/models.py`) — a
`SiteAwareModel` (UUID pk + site FK, `freedom_ls/site_aware_models/models.py:108`) — a `Lead` needs:

| Field | Shape | Why |
| --- | --- | --- |
| `site` | inherited from `SiteAwareModel` | Tenancy boundary — see `fls-dev:multi-tenant`. Auto-set from request context, never by hand. |
| `email` | `EmailField` | The one contact detail the form cannot do without — it is also the field abuse-prevention and dedup logic keys on. |
| `name` | `CharField(blank=True)` | Optional. FLS's `User.first_name`/`last_name` split (`freedom_ls/accounts/models.py:74`) is a precedent, but a lead form is a single field of free text in most marketing UX — don't force the two-name split on a person who hasn't committed to an account yet. |
| `message` | `TextField(blank=True)` | Optional free text ("what are you interested in"), if the landing page's CTA needs it. Landing pages are developer-authored per campaign (per the idea), so whether this field is exposed is a template/form choice, not a schema one. |
| `course` | `ForeignKey(Course, null=True, blank=True)` | Set when the CTA is scoped to a specific campaign course; null for a general "keep me posted" lead. Mirrors `CourseInterest.course` / `CourseApplication.course`. |
| `source` | `CharField` | The landing page (slug or path) the lead came in on. Landing pages are developer-authored templates, not database rows (per the idea's own framing — "a separate Django app that renders a bunch of templates"), so this is a string, not a FK. |
| `campaign` | `CharField(blank=True)` | The advertising/campaign identifier, if the landing page carries one. **Coordinate the field name with `referal_tracking`** (`spec_dd/2. in progress/referal_tracking/idea.md`): that in-progress idea defines `ref` (first-touch referrer code) and `utm_source`/`utm_medium`/`utm_campaign`/`utm_content`/`utm_term` (last-touch) captured off the query string into a first-party cookie (`fc_attr`) and, at signup only, copied into an "attribution row keyed to the learner." A `Lead` has no learner to key that row to, so if a lead is meant to carry the same attribution, it has to carry those fields itself (or a subset — `ref` and `utm_campaign` at minimum) using referal_tracking's own field names, not a synonym invented here. This is a genuine open dependency between the two ideas, not something this research can close alone. |
| `created_at` | `DateTimeField(auto_now_add=True)` | When. |
| `consent_text_version` / similar | see §3 | What the visitor was told, if the form makes any marketing-consent claim. |

What it must **not** hold: a password or any account-shaped field (a lead is explicitly not an
account); free-text fields beyond what the visitor typed (no server-side enrichment — see §3 on
purpose limitation); `is_active`/state machinery (`CourseApplication`'s own doc comment says a state
machine is a deliberately deferred addition for *applications*, and a lead is a strictly smaller
concept than an application — it doesn't need one at all); and no field that silently doubles as an
authentication oracle (see §4).

### Reuse or new model?

`CourseInterest` cannot represent this without changing its shape. Its `user` FK
(`freedom_ls/course_interest/models.py:28`) is `on_delete=CASCADE`, non-nullable, and is half of the
`unique_course_interest` constraint on `(site, user, course)`
(`freedom_ls/course_interest/models.py:41`) — there is no anonymous-visitor path through that model
today; every entry point (`freedom_ls/course_interest/views.py`) either requires
`request.user.is_authenticated` outright or defers the anonymous click through login
(`_PENDING_INTEREST_SESSION_KEY`) and only ever writes the row after sign-in. Making `user` nullable
would break the unique constraint's meaning (two anonymous rows with `user=None` and the same course
would either collide or the constraint would need `email` folded in) and would turn a model whose
entire spec (`spec_dd/3. done/2026-07-03_07:52_courses_coming_soon/`) is "an authenticated learner's
expressed interest" into two different concepts sharing one table. **A `Lead` is a new, small model.**
It is not a variant of `CourseInterest` and should not inherit from it or share its table.

## 2. Relationship to the concepts FLS already has

- **`User`** (`freedom_ls/accounts/models.py:68`) — an account with a password, a session, and
  everything gated behind `@login_required`. A `Lead` has none of that. A lead is not a partial user
  and must not be modelled as one (no `is_active=False` `User` row, no shadow account).
- **`Learner`** (`freedom_ls/learner_management/models.py:51`, per the glossary) — a `User`'s
  membership of an `Organisation`. Two steps further removed than `User`; irrelevant until a lead
  converts.
- **`CourseInterest`** — requires a `User` and is specifically "coming-soon course, notify me at
  launch." A lead is broader (any campaign CTA, any course or none) and requires no account. They are
  siblings in intent, not the same model, per §1.
- **`CourseApplication`** — requires a `User` and represents a real application-gated-course request
  that a reviewer will act on (`spec_dd/2. in progress/simple-application-forms/idea.md` lists the
  real fields an applicant answers: age, `heard_about`, province, etc.). A lead is *upstream* of an
  application, not a lightweight version of one — it is what happens before someone is ready to
  commit to a real application or an account.

### What happens on conversion

When the same person later signs up or applies, **recommend leaving the `Lead` row alone: no
reconciliation, no dedup-on-conversion, no FK from `User` back to `Lead`.**

Reasoning:

- FLS has no cross-table identity resolution machinery today (a `User`'s email is `unique=True`
  per-site, but nothing walks other tables matching on email at signup time), and building one is a
  disproportionate amount of new plumbing for a marketing courtesy. Matching people by email string
  alone is also unsound: a lead could have entered a role or work email different from the one they
  register with, and confidently merging on a bare string match risks attaching one person's
  marketing enquiry to a different person's account.
  - **What it costs to link them anyway** (if a later product decision wants this): a `LegalConsent`
    -shaped append-only join row (`lead`, `user`, `linked_at`, `method`) written the first time a
    signup's email matches an existing lead's email on the same site — additive, never mutates the
    `Lead` row, and is honest that it is a best-effort match rather than a merge. That is future work,
    not something to build in the first landing-pages release.
- Leaving the row alone also has an operational upside for §3: the `Lead` row is inert once the
  person becomes a `User` — it is exactly the kind of record retention policy can time out and delete
  without touching the account it's about (see the retention discussion below).

## 3. Consent and data protection

**This section reports obligations with a source. It is not a legal opinion, and a lead-capture
form touching real people's data needs an actual legal review before it ships**, particularly because
FLS's own placeholder privacy policy (`legal_docs/_default/privacy.md`) already names GDPR and POPIA
explicitly and says site operators "MUST replace it... before relying on it for compliance" — the
same caveat applies to anything a lead form promises.

### Lawful basis

- **GDPR** (EU, and UK GDPR) requires processing to rest on one of six lawful bases under
  Article 6. For an unsolicited marketing lead-capture form, **consent** is the basis that fits
  cleanly — the visitor is volunteering contact details specifically so the operator can market to
  them, which is squarely what Article 6(1)(a) consent is for. **Legitimate interest**
  (Article 6(1)(f)) is a real alternative used for direct marketing in some contexts, but per ICO
  guidance it is not the right basis to reach for where consent is the more natural fit, and it
  requires the operator to run and document a three-part necessity/balancing test up front — that is
  an operator policy decision, not something the system can discharge for them.
  [ICO — legitimate interests](https://ico.org.uk/for-organisations/uk-gdpr-guidance-and-resources/lawful-basis/legitimate-interests/when-can-we-rely-on-legitimate-interests/)
- **POPIA** (South Africa — FLS's first concrete deployment) treats *storing* the contact details
  and *marketing to them electronically* as two different questions. Section 69 specifically governs
  direct marketing by electronic communication (email, SMS): it is opt-in by default, consent must be
  "voluntary, specific and informed," and every subsequent marketing message must carry a clear,
  free, easy opt-out.
  [POPIA §69 — direct marketing by electronic communication](https://popia.co.za/section-69-direct-marketing-by-means-of-unsolicited-electronic-communications/),
  [golegal.co.za — direct marketing legislation](https://www.golegal.co.za/legislation-direct-marketing/).
  A narrow "existing customer, similar product" exception exists under both POPIA §69(3) and the UK's
  PECR "soft opt-in" (Regulation 22(3)) — but a landing-page visitor is, by definition, not yet a
  customer, so that exception does not reach a first-touch lead form.
  [ICO — electronic mail marketing / soft opt-in](https://ico.org.uk/for-organisations/direct-marketing-and-privacy-and-electronic-communications/guide-to-pecr/electronic-and-telephone-marketing/electronic-mail-marketing/)

**What this means concretely for the form**: if the CTA is framed as "leave your details and we'll be
in touch" (a human follow-up, not an automated marketing sequence), a single unambiguous checkbox or
clearly-stated submit action at the point of collection is enough to establish consent for *that*
use. If the operator intends to add the lead to an email newsletter or automated drip sequence, that
is a **separate, specific** consent, and the form must ask for it separately rather than bundling it
into "submit this form" — POPIA's "specific" requirement and the general GDPR consent standard both
rule out one broad checkbox covering both "contact me about this course" and "add me to your
mailing list."

### What the form must say

At minimum, at the point of collection: who is collecting the data (the operator/site, not "FLS"),
what it will be used for (respond to this enquiry — and, only if applicable and separately consented
to, ongoing marketing), and where the full privacy policy is
(`legal_docs/<site>/privacy.md` or `legal_docs/_default/privacy.md`, the same document the signup
flow already links to). This is a copy/UX requirement on the landing-page template, not a schema
requirement — but the *evidence* that it was shown (see next) is a schema requirement.

### Can `LegalConsent` record this?

**No, not as it stands.** `LegalConsent.user` (`freedom_ls/accounts/models.py:178`) is a required FK
to `settings.AUTH_USER_MODEL` — there is no `User` at lead-capture time, so a lead consent event
cannot be written to that table without either making `user` nullable (which the `registration` skill
and the model's own docstring treat as an append-only, per-user audit trail — weakening that
guarantee for every existing consumer to accommodate one new anonymous case is the wrong trade) or
adding a second nullable identity column purely for this one case. Simplest honest answer: **a lead's
consent evidence lives on the `Lead` row itself** — the same fields `LegalConsent` uses for the same
reason (`document_version`, `git_hash` or a lighter "which copy variant was shown," `timestamp`,
`ip_address` via the existing `get_client_ip` helper, `freedom_ls/accounts/utils.py:20`) rather than
inventing a new consent model. If a lead later converts to a `User` and formally accepts Terms/Privacy
at signup, that produces its own proper `LegalConsent` row through the existing signup path — the
lead's consent record and the account's `LegalConsent` are not the same evidence and neither
supersedes the other.

### Retention, deletion, and access requests

- **Retention**: a lead is a courtesy row with no account behind it, so it has less legal reason to
  live forever than `LegalConsent` (which FLS's own placeholder policy retains for 7 years as
  evidence of *account* consent). The honest default is a short, operator-configurable retention
  window (e.g. "delete unconverted leads after N days") — POPIA requires personal information be
  destroyed once the purpose it was collected for has been served, and "we never followed up" is a
  purpose that expires.
- **Data-subject access / erasure**: POPIA gives a data subject the right to confirm whether their
  personal information is held and to request a record of it (§23), and the right to have inaccurate,
  irrelevant, excessive, or unlawfully obtained data corrected or deleted.
  [POPIA §23 — access to personal information](https://popia.co.za/section-23-access-to-personal-information/).
  GDPR gives equivalent rights (Articles 15 and 17). For a table of `Lead` rows this is *simpler* than
  for a `User` — there's no cascade to worry about, no progress records, no `Learner` rows — a lookup
  by email and a hard delete (or export) fully discharges it. **What the system must support**: an
  admin-visible, filterable-by-email `Lead` list an operator can find and delete a row from (the
  standard Django admin gives this for free once `Lead` is registered — see §5). **What is the
  operator's problem, not the system's**: actually operating a process that responds to a request
  within the statutory window, verifying the requester's identity, and deciding retention policy
  numbers. FLS should not silently promise SLA-bound DSAR handling in code; it should make the
  underlying data trivially findable and deletable.
- **Double opt-in**: neither GDPR nor POPIA *requires* double opt-in (a confirmation email before the
  lead is added to a marketing list), but it is common practice specifically because it produces
  strong proof of consent and reduces the value of the form as a spam vector (see §4). Recommend
  double opt-in as a **should**, not a **must**, and *only* for the "add me to your mailing list"
  branch, not for "someone from the team will follow up" leads — a person who filled in a form asking
  for a human callback should not have to click a confirmation email before that callback happens.

## 4. Abuse

A public, unauthenticated POST endpoint with no existing precedent in FLS. What's actually in the
codebase today:

- **`django-axes`** (`pyproject.toml`, configured `config/settings_base.py:311-341`) — brute-force
  *login* lockout, keyed on `(ip_address, username)` and `username` alone. It protects
  `/admin/login/` and the allauth login view. It has nothing to do with an anonymous public form and
  doesn't apply here.
- **allauth's own per-IP rate limiting** (`ACCOUNT_RATE_LIMITS`, `config/settings_base.py:430-433`) —
  `"signup": "5/m/ip"` for account creation, `"login_failed": "10/m/ip,5/5m/key"` for failed logins.
  This is FLS's one existing precedent for throttling a public write endpoint, and it's a useful
  reference point: 5 signups/minute/IP is what FLS already considers a reasonable ceiling for a
  similar-shaped anonymous write.
- **No honeypot, no captcha, no reCAPTCHA/Turnstile/hCaptcha, and no generic `django-ratelimit`**
  anywhere in the tree (`freedom_ls/`, `config/`, `pyproject.toml` all grepped clean of those terms
  outside test/spec files unrelated to this feature).

### What to do, proportionate to the actual risk

A lead form's abuse surface is: bots submitting garbage rows (cost: noise in an admin list and wasted
storage, not account takeover), and using the form as an **oracle** to test which emails are already
registered `User`s (see below) or already leads (email enumeration).

Recommended, cheapest-first:

1. **A honeypot field.** A hidden input real visitors never fill and bots reliably do — OWASP's Bot
   Management and Anti-Automation cheat sheet describes exactly this pattern, and reporting from 2024
   automated-threat monitoring found roughly 78% of form-spam bots fill every field they find
   regardless of CSS visibility, meaning a honeypot alone catches most of the volume. It costs real
   visitors and assistive technology nothing, because it is never rendered to them at all — the
   accessibility win a captcha cannot claim.
   [OpenReplay — honeypot fields](https://blog.openreplay.com/honeypot-fields-stop-bots/)
2. **A minimum-time-on-page check** (reject a submission that arrives implausibly fast after the page
   loaded) — cheap, no user-facing cost, catches naive scripted submission the honeypot misses.
3. **Per-IP rate limiting on the submit endpoint**, matching the shape FLS already uses for signup
   (`5/m/ip` is the existing precedent) — this is the one gap between what's proven in this codebase
   and what a lead form needs; nothing currently rate-limits an anonymous form POST outside allauth's
   own views.
4. **Captcha (Cloudflare Turnstile or hCaptcha) — hold in reserve, not default-on.** A captcha is
   itself a conversion cost on a page whose entire purpose is converting a visitor with as little
   friction as possible; it is proportionate to deploy only if 1–3 prove insufficient for a specific
   site under real abuse, not to ship pre-emptively on every landing page. If it is ever needed,
   Turnstile is the better-fitting choice of the two on privacy grounds — it runs without sending
   visitor data to a third party the way classic reCAPTCHA does, which matters on a page whose whole
   point is minimising what's collected about an anonymous visitor.

### The oracle problem

Two enumeration risks, and they are different:

- **"Is this email already a registered `User`?"** — FLS already treats this as a real threat:
  `ACCOUNT_PREVENT_ENUMERATION = True` (`config/settings_base.py:411`) exists specifically so signup
  and login don't reveal whether an email is registered. A lead form must not undo that. Concretely:
  never reject or special-case a lead submission because the email matches an existing `User` — accept
  it identically either way, and do any "oh, this person already has an account" handling later,
  out-of-band (e.g. a human noticing on follow-up), never in the response the form gives back.
- **"Is this email already a `Lead`?"** — lower stakes than the account case (a lead list isn't an
  authentication credential store), but the same principle applies: `get_or_create`-style idempotency
  that silently no-ops a duplicate email is fine *internally*, but the HTTP response must not say
  "you've already submitted this" in a way that lets a script binary-search a list of emails against
  the endpoint. A generic "thanks, we'll be in touch" response regardless of whether the row was
  new or already existed closes this off, and costs nothing extra to implement.

## 5. What happens after capture

Recommend the cheapest honest answer, not a dashboard:

- **Confirmation to the visitor**: a static "thanks, we'll be in touch" response (HTMX partial or a
  plain redirect, matching the `course_interest`/`course_applications` CTA-partial pattern already in
  the codebase). No email confirmation required unless double opt-in is in play for the marketing-list
  branch (§3).
- **Notification to the operator**: an email to a configured operator address is the cheapest thing
  that actually gets someone to follow up — FLS already sends transactional email (allauth's own
  verification/reset flows), so this reuses existing plumbing rather than adding a new channel.
- **Is it a webhook event?** Genuinely worth it. FLS's webhook event registry
  (`freedom_ls/base/webhook_event_types.py`) already uses a `noun.past_participle` naming convention —
  `user.registered`, `course.completed`, `course.registered` — and a downstream CRM or marketing tool
  is exactly the kind of consumer `freedom_ls/webhooks/` exists to serve
  (`spec_dd/3. done/2026-03-16_16:20_outward-webhooks/`). A `lead.captured` event, fired the same way
  `fire_webhook_event` is called elsewhere (`freedom_ls/webhooks/events.py:10`), with a payload
  shaped like the existing samples (`WEBHOOK_EVENT_TYPE_SAMPLES` in the same module) is a natural,
  low-cost fit and arguably a better integration point than building any in-app lead UI at all — most
  operators' actual CRM lives outside FLS.
- **Educator interface, reports app, or admin?** Not the educator interface
  (`freedom_ls/educator_interface/`) or `freedom_ls/reports/` — both are learner-progress-shaped
  surfaces built around cohorts and courses a learner is registered for; a `Lead` is neither, and
  bolting a marketing-lead list onto either would be scope creep into a UI those apps don't own.
  **The Django admin, via `SiteAwareModelAdmin`** (`fls-dev:admin-interface`), is the cheapest honest
  surface: it gives an operator a filterable, searchable, exportable (CSV via a small admin action, or
  Unfold's built-in export if configured) list of leads for free, respects site isolation
  automatically, and needs no new frontend. Combine with the webhook event for anyone who wants leads
  to land in a real CRM instead of being read out of `/admin/`.

## 6. The scope-cut question

**Smallest useful version**: one new `Lead` model (site, email, optional name, optional course,
`source`, `created_at`, plus whatever consent-evidence fields the copy on the landing page actually
needs), one POST view with a honeypot field, a minimum-time-on-page check, and per-IP rate limiting
matching FLS's existing `5/m/ip` signup precedent, a generic non-committal confirmation response, an
operator notification email, and a read-only `SiteAwareModelAdmin` registration. No webhook event in
v1 unless the outward-webhooks feature already has a consumer waiting for it — it's a small addition
on top of the model, but it is still one more thing to get right (payload shape, registry entry,
sample data) and nothing currently downstream needs it. No mailing-list/marketing-consent branch,
no double opt-in, and no reconciliation-to-`User`-on-conversion in v1 — all three are real features
with real legal and product surface area of their own (§2, §3) and none of them block "a visitor can
leave their details."

**Defer explicitly**: double opt-in / marketing-list consent, lead-to-user reconciliation, the
webhook event (until a consumer exists), and any dashboard/reporting UI beyond the admin list.

**Should lead capture ship in the first landing-pages release at all?** The honest finding is: it can,
but *only* the minimal version above, and **only if the consent copy and retention policy are treated
as a real legal-review item before ship, not an afterthought** — because unlike the other three CTAs
(sign up, apply, express interest), which all reuse FLS's existing account-and-consent machinery
end to end, this is the one CTA with no existing consent story in FLS at all, and it is the one being
built first for a South African deployment where POPIA's direct-marketing rules are concrete, current
law with an active regulator, not a hypothetical. If the landing-pages release timeline can't
accommodate that legal review, cutting this CTA entirely and shipping the other three first is the
more defensible choice than shipping a lead form with placeholder consent copy.

---
status: ok
