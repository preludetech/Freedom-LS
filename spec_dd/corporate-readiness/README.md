# Corporate readiness: what FLS needs to win large corporate clients

_Written 2026-09-27. This is a recommendation, not a spec. Nothing here is on the spec roadmap
yet. Each numbered item below is meant to become one idea (or a cut effort) under `spec_dd/1. next/`
when you decide to pick it up._

The research behind this is in the three `research_*.md` files next to this one, with a URL on
every claim:

- `research_procurement.md`: what IT, security, legal and procurement check before a 1,000+
  employee company will sign.
- `research_corporate_features.md`: what corporate L&D teams expect that academic systems don't
  offer.
- `research_open_source_enterprise.md`: how Moodle Workplace, Totara, Open edX, ILIAS and Chamilo
  got into (or failed to get into) the enterprise market.

## The short version

A large corporate buyer runs two gates, in this order.

1. **The security and IT gate.** InfoSec, IT and legal go through a checklist before anyone
   looks at the learning features. SSO, MFA, a security questionnaire, a pen-test report, a
   DPA with real retention and deletion terms, and an accessibility conformance report. Fail
   any one of these and the deal stops, however good the product is.
2. **The L&D gate.** Once past security, the L&D team wants four things academic systems don't
   have. Compliance training that renews itself. Automatic registration driven by HR
   attributes like department and role. A line-manager view. And the ability to load the
   SCORM courses they already own.

FLS today is mostly an academic-shaped system with a strong multi-tenant foundation. Sites,
organisations, cohorts, registrations, deadlines, cohort reports, webhooks and signed consent
records are all real advantages. Most of what is missing is plumbing that connects FLS to a
company's identity provider, HR system and existing content.

My recommended order:

| Phase | Theme | Items | Why this order |
|---|---|---|---|
| 1 | Pass the security review | SSO, MFA, retention and deletion, accessibility conformance, pull forward planned security fixes | Hard gates. Without them you never reach a demo. Most are cheap because allauth and existing specs already do half the work. |
| 2 | Accept their content | SCORM 1.2/2004 and cmi5 import and playback | Corporates own years of Articulate/Storyline content and will not rewrite it in markdown. This is the single biggest product gap. |
| 3 | Plug into HR | Public API, SCIM provisioning, HR attributes on users | Every compliance feature in phase 4 needs to know someone's department, role, manager and start date. |
| 4 | Compliance automation | Certificates with expiry, recertification, rule-based registration, relative due dates, manager view and escalation, scheduled reports | The corporate anchor use case. Builds on 1 to 3. |
| 5 | Later, driven by a real client | Multi-language UI, virtual classroom, content marketplaces, programmes, per-organisation branding | Real, but a specific client should pull each one in. |

Phase 2 and phase 3 don't depend on each other. With two people they can run in parallel.

## What is already on the roadmap (and matters here)

These count towards corporate readiness and are already planned. Finish them. Don't re-plan them.

- **Educator interface rebuild, specs 6 to 11.** Cohort and learner administration outside the
  Django admin, CSV import, educator administration, reporting dashboards and an append-only
  audit log. Corporate admins will never be given the Django admin, so all of this is
  prerequisite. The audit log (spec 11) matters most here: procurement checklists score it
  directly.
- **The educator interface authorisation gap** on the Courses list and course detail pages
  (product roadmap). A security reviewer who finds it will stop the deal. Fix it before the first
  corporate pilot, even ahead of spec 6 if needed.
- **Notification email** (`user-communication-2-notification-email`). Reminders and escalations
  in phase 4 go out by email. The in-app bell alone won't do it.
- **`file-scanning`**, **`content_snapshots`** and **`compliance-form-randomization`**. All three
  are what a compliance auditor asks about: is uploaded content safe, what exactly did the
  learner see, and can learners share the answer sheet?
- **Application review** (not yet cut). Less important for corporates than for academic intakes.
  Leave it where it is.

Items that are on the product roadmap as known gaps but have no spec yet: MFA, completion
certificates, data retention and subject rights, enforcing CSP. Each one shows up below with a
reason to move it up.

## Phase 1: pass the security review

### 1. Single sign-on (SAML 2.0 and OIDC), configured per site or per organisation

**Gap.** FLS only has email and password login. The allauth `socialaccount` app is not installed.
No SAML or OIDC code exists anywhere.

**Why first.** SSO against Entra ID (Azure AD), Okta or Google Workspace is the most consistently
cited hard requirement for buyers of this size. At the enterprise level it's table stakes, not
an upsell (see `research_procurement.md`). It also removes a lot of other questions: password
policy, lockout, and offboarding all become the customer's IdP's problem.

**Shape.** allauth already ships OIDC and SAML providers, and its provider apps are
site-aware, so a lot of this is configuration and UX. The FLS-specific decisions:

- Is the IdP configured per `Site` or per `Organisation`? A site that hosts several client
  companies needs per-organisation IdPs and some kind of home-realm discovery (email
  domain → IdP).
- Just-in-time provisioning: a first SSO login creates the `User` and calls `ensure_learner`
  for the right organisation.
- "SSO only" enforcement per organisation, so employees can't fall back to a password account.
- How this sits with `SiteSignupPolicy` and legal consent.

### 2. MFA for password accounts

**Gap.** Listed on the product roadmap as "not built". Nothing exists.

**Why now.** Security reviews test for MFA directly, especially on staff and admin accounts.
Once SSO exists, most corporate learners go through their IdP's MFA anyway. So the scope can be
narrow: TOTP and passkeys through `allauth.mfa`, enforceable per role, required for anyone with
staff or organisation-admin roles.

### 3. Data retention, deletion and subject rights

**Gap.** On the product roadmap as not built. User deletion is a manual database operation.
Cohort report PDFs and application uploads are kept forever.

**Why now.** Every EU corporate client will send a DPA to sign. It asks what you keep, for how
long, and how deletion works, including deletion from backups. Today the honest answer is
"forever, and by hand", which legal will not accept. Scope: configurable retention periods per
data class, a scheduled sweep (the `fls_run_housekeeping` pattern already exists), an erasure
workflow that anonymises rather than cascades, and a per-user data export.

### 4. Accessibility conformance (WCAG 2.2 AA) and an ACR

**Gap.** FLS has had a mobile responsiveness audit but never an accessibility audit. Nothing
claims WCAG conformance.

**Why now.** Public-sector, education and EU buyers treat this as a hard gate. Since June 2025
the European Accessibility Act makes EN 301 549 conformance a legal requirement for e-learning
services sold into the EU. Procurement asks for an Accessibility Conformance Report (a filled-in
VPAT). You can't write an honest one without an audit. The work is an audit of the learner
interface, the course player, forms and quizzes, and the educator interface, then fixes, then
publishing the ACR. Do it after the educator interface rebuild lands, or you'll audit it twice.

### 5. Pull forward the planned security items

Enforce the Content Security Policy (it's report-only today), fix the authorisation gap above,
land `file-scanning`, and route media downloads through the access check (product roadmap,
"per-request access-controlled media downloads"). Individually they're small. Together they're
the answers to a SIG or CAIQ questionnaire that turn "no" into "yes".

### The non-code half of this gate

The research is blunt about this one. SOC 2 Type II or ISO 27001, an annual third-party pen test,
a 99.9% uptime SLA with a status page, and a DPA template attach to **whoever runs the
deployment**, not to the code. FLS is a library installed into other Django projects, so FLS
itself can never hold a SOC 2 report. Someone has to host FLS projects and hold the paperwork.
That could be you, a hosting partner, or the client's own IT.

Moodle and Chamilo both landed on the same model: the core stays open, and a vetted partner tier
sells hosting, support and the enterprise layer (`research_open_source_enterprise.md`, sections
6 and 7). FLS can make the paperwork easier by keeping `docs/deployment-security-checklist.md`
and `security-and-data-handling.md` accurate enough to answer a questionnaire from. It's worth
deciding early who is going to hold the certificates, because it changes whether items 1 to 5
are enough.

## Phase 2: accept the content they already have

### 6. SCORM 1.2 / 2004 and cmi5 import and playback

**Gap.** FLS content is markdown in git, loaded with `content_save`. There is no package import.
The `xapi_learning_record_store` app is a commented-out stub.

**Why this is second, ahead of the compliance features.** Corporate L&D teams author in
Articulate Storyline and Rise, iSpring, Captivate and similar tools, and they buy compliance
courses from vendors like OpenSesame and Go1. All of it ships as SCORM. Every buyer guide in the
research treats SCORM as non-negotiable. A company with 200 existing SCORM courses isn't going
to rewrite them as markdown, and git-based authoring is a non-starter for a non-technical L&D
team. Without SCORM, phase 4 has nothing to run on for most buyers.

I'd argue this also resolves the "no GUI editor" question the right way. Don't build a WYSIWYG
editor. Let authoring tools the customer already pays for produce the content, and let FLS host,
track and report on it. Markdown courses stay the FLS-native path for teams that want it.

**Shape.** A SCORM package becomes a new child type in a `ContentCollectionItem`, so it can sit
inside a `Course` next to topics and forms. It needs:

- upload and unpack into private storage;
- a sandboxed player with the SCORM runtime JavaScript API;
- mapping of `cmi.completion_status`, `cmi.success_status` and score onto FLS progress
  (`TopicProgress`, or a new sibling progress model);
- suspend data for resume.

cmi5 is the modern replacement and needs an xAPI statement store, so revive the xAPI stub as a
real LRS at the same time, or right after. AICC is legacy. Skip it.

The upload path has to decide how it lives with the git-as-source-of-truth model. Packages are
binaries uploaded by admins, not authored files.

## Phase 3: plug into their HR systems

### 7. A public REST API

**Gap.** `django-ninja` is already a dependency but the API in `config/urls.py` is commented
out. There is no token auth and no documented endpoints. Webhooks exist for outbound events.

**Why.** Buyers score "REST API + webhooks" as a checklist item. More to the point, it's how a
customer's IT team syncs FLS with their HR system, BI tooling and intranet without waiting on
you. Start with the objects they actually integrate on. Users and learners, organisations,
cohorts, registrations, course progress records, and certificates once phase 4 lands. Scoped API
tokens per organisation. Read-heavy first.

### 8. SCIM 2.0 provisioning and deprovisioning

**Gap.** Nothing exists. Users are created by self-signup, by admin, or (once spec 8 lands) by
CSV.

**Why.** Automated deprovisioning is how IT makes sure a leaver loses access on their last day,
and security reviews treat it as a breach-risk control. Entra ID and Okta both push users and
groups over SCIM. SCIM also covers most of the value of native Workday or SuccessFactors
connectors. The research says buyers accept SCIM or API middleware in place of a native HRIS
connector, so skip native connectors until a client pays for one. SCIM user deactivation maps
cleanly onto `Learner.is_active=False` and `User.is_active`. SCIM groups could map onto cohorts.

### 9. HR attributes on users

**Gap.** `User` has email, first and last name. `Learner` has no department, job title,
location, employee ID, start date or manager. `user-profile-upgrades` adds phone and date of
birth, which is a different need.

**Why.** Every phase 4 feature keys on these. "Everyone in Sales in Germany must redo the
anti-bribery course every year" needs a department and a location. "Remind the manager when it's
overdue" needs a manager. They arrive through SSO claims (item 1) and SCIM (item 8), so they
belong per `Learner` (per organisation), not per `User`. A person's department at one client
company says nothing about the next. A small fixed set of standard fields plus
organisation-defined custom fields is the usual pattern.

## Phase 4: compliance training automation

This is the corporate anchor use case. Every corporate-focused product in the research (Docebo,
Cornerstone, Moodle Workplace, Totara, ILIAS) has a version of each item below, and academic
systems have almost none of them.

### 10. Completion certificates, with expiry

**Gap.** On the product roadmap as not built. The finish page produces nothing downloadable.

**Why.** A certificate is the evidence an auditor asks for. For corporates it needs an issue date,
an expiry date, and a stable record in the database, not just a PDF. The cohort report's
WeasyPrint pipeline and organisation co-branding can be reused. Verifiable public links and Open
Badges are nice-to-haves for later.

### 11. Recertification

**Gap.** Nothing renews. The educator interface effort explicitly puts "deliberate retakes or
progress resets" out of scope.

**Why.** "Complete fire safety every 12 months" is the most common corporate training rule
there is. The mechanism is to attach a validity period to a course or certificate, open a new
cycle before it expires, send reminders, and reset the window on completion.

**Watch out.** FLS keys course progress records on the registration that minted them. So a new
cycle is most naturally a new registration with a new `CourseProgress`, which keeps the old
record as evidence. That needs designing deliberately, and it's the same question the retakes
deferral put off. Settle it once for both.

### 12. Rule-based automatic registration

**Gap.** Registration is by self-signup, by application, or by an admin adding a learner or
cohort.

**Why.** Corporate admins don't register people by hand. They write rules. "All new starters get
Onboarding". "Everyone with job title Driver gets Road Safety". "Everyone in the EU gets GDPR
Basics". The rules re-run whenever SCIM or SSO changes a person's attributes. This is the
defining difference from academic systems (Docebo enrolment rules, Cornerstone dynamic
assignment, Moodle Workplace dynamic rules). The rule's output should be ordinary
`CohortCourseRegistration` or `LearnerCourseRegistration` rows, so nothing downstream changes.
Rule-maintained cohorts ("dynamic cohorts") may be the cheapest way in.

### 13. Due dates relative to an event

**Gap.** `CohortDeadline.deadline` and its siblings are fixed datetimes.

**Why.** "Due 30 days after registration" or "due within 14 days of start date" is how corporate
compliance deadlines work, because people join continuously. Absolute dates only work for
academic intakes. This is a modest extension of the deadline models, but it has to agree with
rules (12) and recertification (11). The educator interface effort also says a deadline rework
is coming separately. Fold this into it.

### 14. Line-manager view and escalation

**Gap.** FLS roles are site, organisation, cohort and course scoped (educators, instructors,
TAs, organisation staff). There is no concept of a person's manager.

**Why.** Managers are accountable for their team's compliance, and RFP templates list manager
dashboards and escalation reminders explicitly. The minimum version: a manager (from item 9)
sees their direct reports' required training, status and overdue items, and gets an email when
someone on the team goes overdue. Approvals (a manager approves a registration request) can wait.

### 15. Scheduled and emailed reports

**Gap.** Listed as a deliberate deferral in "Cohort Report Deferrals". Reports are on demand, from
the admin. Spec 10 brings on-screen dashboards and a roster CSV.

**Why.** Compliance leads want "every Monday, email me the overdue list for my region" and a
monthly export for their auditors. Also move the at-risk rules out of code as that deferral
already plans. Corporates will want to set their own thresholds.

## Phase 5: later, when a client asks

These showed up in the research as real but not deal-breaking. I'd wait for a specific client
to pull each one in.

- **Multi-language UI and content.** FLS has `USE_I18N = True` but only a handful of templates use
  translation tags and there are no locale files. This jumps to phase 1 the day your first client
  has a non-English workforce. Retrofitting translation tags gets harder the more templates exist,
  so a cheap step now is to start using `{% translate %}` in new templates.
- **Programmes (multi-course learning paths).** Table stakes in some buyer guides. FLS courses
  with course parts cover much of it. A thin programme layer on top of rules (12) is enough.
- **Virtual classroom and instructor-led sessions.** Session scheduling, Zoom or Teams links,
  attendance fed into completion. Important for blended-learning clients, irrelevant for
  e-learning-only ones.
- **Content marketplace integrations** (Go1, OpenSesame, LinkedIn Learning). These mostly arrive
  as SCORM or cmi5, so item 6 gets you most of the way.
- **Per-organisation branding, domains and extended enterprise.** FLS is already unusually well
  placed for "train your customers and partners" because of sites, course prices and
  applications. The per-organisation theme and domain deferral on the product roadmap is what
  would unlock selling it that way.
- **External training records.** Weakly evidenced in the research. Wait.
- **Skills frameworks, AI recommendations, gamification, social learning.** Vendors market these
  hard, but buyer guides rank them as differentiators or nice-to-haves. Don't build them to win
  corporate deals.

## Where FLS already has an edge

Worth saying out loud in a sales conversation, because the research found no other Django or
Python LMS with an enterprise story at all:

- Real multi-tenancy, which Moodle only offers in its paid Workplace product.
- Organisations as a first-class layer between site and cohort, so one site can serve many client
  companies.
- An append-only legal consent trail tied to exact document versions.
- Webhooks, per-app settings, template overrides and themes: it's built to be extended by a
  client's own developers, which is what large IT departments want from open source.
- Git as the content audit trail, which regulated clients like once someone explains it.

## Open questions for you

- Who holds SOC 2 or ISO 27001 and runs the SLA: you, a partner, or each client? This decides how
  much of phase 1 is code versus paperwork.
- Is your first target client EU-based? If so, retention and deletion (3) and accessibility (4)
  come before MFA (2), and multi-language may move into phase 1.
- Do you want FLS to be the system of record for compliance (phase 4 in full), or the delivery
  and tracking layer under a client's existing HR suite (phases 1 to 3 plus API reporting)? The
  second is a smaller build and a narrower market.
