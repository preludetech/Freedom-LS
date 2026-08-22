# Research: terminology and UX conventions for the student → learner rename

Scope: backs up idea.md §7's instruction to "audit for 'user' leaking through where 'learner' is
meant" and gives the spec concrete copy-quality rules, an industry survey, an in-tree audit of
user-visible strings, and a recommendation on configurable labels.

## Summary

- **Verdict on "learner" being the right word: yes, unambiguously.** It is what the relevant
  standards converged on (SCORM 2004 deliberately renamed `cmi.core.student_id` →
  `cmi.learner_id`; xAPI and LTI/1EdTech both use "Learner" as the canonical role/actor term), it is
  what most of the corporate/vocational LMS market uses, and — decisively for this repo — **FLS's
  own in-tree brand-guidelines skill already mandates it**: `.claude/skills/brand-guidelines/SKILL.md`
  has a terminology table with `learners` under "Use This" and `students` under "Not This", reasoned
  as "works across corporate, self-paced, and academic contexts." This rename is FLS's code catching
  up to its own documented brand voice, not a new stylistic decision.
- **Verdict on configurability: out of scope for this spec, and I'd advise against a generic
  `LEARNER_LABEL` setting even as a fast-follow.** FLS has no i18n infrastructure in place today
  (verified: no `locale/` directory, no `LocaleMiddleware`, `USE_I18N = True` is just Django's
  untouched default, `LANGUAGE_CODE = "en-us"` hardcoded, `gettext_lazy` used in only 5 files and
  only for a couple of `verbose_name`s — not user-facing template strings). Naive string
  interpolation for a configurable role label is a well-documented i18n trap (plurals, possessives,
  capitalisation, sentence position all break under a single substituted noun). If tenant-specific
  labelling is ever wanted, it should be scoped as its own spec built on proper Django i18n
  (`gettext`/`ngettext`), not bolted onto this rename.
- FLS is South-African-authored — verified in-repo via POPIA data-residency content in
  `docs/product/security-and-data-handling.md` and SACAA (South African Civil Aviation Authority)
  aviation-training research in `spec_dd/0. drafts/xx. sacaa question-pools-and-remediation/`. South
  Africa's vocational/skills-development sector (SETA / QCTO / Skills Development Act) uses
  "learner" as its statutory term (a "learnership" is the named legal instrument), reinforcing that
  "learner" is the regionally natural choice, not just an internationally trendy one.
- FLS's domain model genuinely supports multiple roles per person on different courses (a `User` can
  be an educator on one course and a learner on another via `ObjectRoleAssignment` /
  `SystemRoleAssignment` / `SiteRoleAssignment` — see §4 below), so "user" is correct wherever the
  code means *any authenticated person regardless of role*, and "learner" is correct only where the
  code means *a person in the act of, or registered for, taking a course*.
- Nine user-visible strings found in-tree that this rename touches beyond what idea.md already
  named; most are mechanical, three need a genuine rewrite rather than a search-replace (see table
  in §5).

---

## 1. Industry convention: "learner" vs "student"

**Standards** (official spec / documentation — authoritative):

| Source | Term used | Notes |
|---|---|---|
| SCORM 1.2 (ADL) | `student` — `cmi.core.student_id`, `cmi.core.student_name` | Predates the terminology shift. |
| SCORM 2004 (ADL) | `learner` — `cmi.learner_id`, `cmi.learner_name` | **Deliberate rename between spec versions**, replacing the SCORM 1.2 `student_*` data-model elements with `learner_*` ones. This is a near-exact precedent for what this spec is doing: the same organisation renamed the same concept for the same reason. |
| xAPI / Experience API (ADL / IEEE 9274.1.1-2023) | `learner` (as one of several `actor` roles: learner, instructor, admin, etc.) | Statements follow `[actor] [verb] [object]`; the actor is not required to be a learner, but the canonical example role is "learner." |
| LTI / 1EdTech (formerly IMS Global) | `Learner`, `Instructor`, `TeachingAssistant`, `ContentDeveloper`, `Mentor`, `Administrator` | LIS/LTI context-role vocabulary (`http://purl.imsglobal.org/vocab/lis/v2/membership#Learner`). Also explicitly documents that **the same person can be `Learner` in one context and `Instructor` in another** — directly analogous to FLS's own multi-role model (§4). |

**Products** (docs / community — some anecdotal, flagged):

| Product | Term used | Configurable? | Notes |
|---|---|---|---|
| Open edX | **Learner** ("Learner Dashboard", "View Learner Data") | No | Modern, actively-developed platform; consistently "learner" throughout current docs. |
| Moodle | **Student** (role name), but "learner" appears in marketing/community copy | Role *display names* can be renamed per-site via Moodle's language customisation feature, but the default and most documentation still say "Student." | Moodle predates the corporate-LMS wave and kept academic framing. |
| Totara (Moodle-derived, enterprise/corporate fork) | **Learner** | N/A found | Corporate/workforce-development positioning explains the divergence from its own Moodle base. |
| Docebo | **Learner** (community forum explicitly discusses the SCORM `student_name`→`learner_name` mapping) | Not verified | Corporate LMS vendor; community material consistently says "learner." |
| Canvas (Instructure) | **Student** | Not verified | Academic-market LMS; consistent with its higher-ed customer base. |

**The semantic distinction, as sources justify it:** "student" implies enrolment in a formal
educational institution pursuing a course of study; "learner" is the broader term, covering anyone
acquiring knowledge or skills through any means — corporate training, vocational/occupational
learning, self-directed study, or formal education. Community/anecdotal sources (a corporate-training
glossary and a "Learner vs Student" explainer) describe this as *"learner" emphasises the process of
acquiring skills, "student" implies a formal educational setting.* One data point worth citing
precisely: the AACSB (the international accreditation body for business schools) changed its 2020
accreditation standards to refer to business-education consumers as "learners" instead of
"students" — an explicit, named, citable instance of an educational standards body making exactly
this switch, with the stated rationale "students study and learners learn."

**Regional (South Africa) — verified relevant, not directly about FLS's brand copy but consistent
with it:** the Skills Development Act 97 of 1998 and its "learnership" mechanism, administered by
SETAs (Sector Education and Training Authorities) and the QCTO (Quality Council for Trades and
Occupations), use "learner" as the statutory noun for a person on a structured
work-integrated-learning programme. FLS's own repo has POPIA (South Africa's data-protection act)
content and SACAA (civil-aviation regulator) research that consistently uses "learner," so the
rename aligns with both FLS's documented brand voice and the regulatory vocabulary of its home
jurisdiction.

---

## 2. Should the user-visible word be configurable?

**Pattern in the market:** the products that expose configurable role labels almost universally do
it as a *display-name-only* relabelling of a role object (e.g. Moodle's "customise this language
pack" / role-rename feature), not a global find-and-replace of a noun across every sentence in the
UI. That distinction matters: renaming a *role* ("Student" → whatever the admin wants to call it on
the roster page) is contained to specific labelled UI elements; substituting a *word* into every
sentence that currently reads naturally ("No students are currently enrolled...") requires either
(a) rewriting every such sentence to be label-agnostic, or (b) grammatically-aware templating
(plurals, possessives, articles) that most naive implementations get wrong. Known failure modes
reported in Django's own i18n tracker and community discussion:

- **Pluralisation**: `f"{n} {label}s"` breaks for any label that doesn't pluralise with a bare `s`,
  and breaks in every locale with more than the English two plural forms (Django's own
  `verbose_name_plural` mechanism has open, unresolved tickets — Django ticket #3373, #14844 —
  precisely because it doesn't compose with `ngettext`'s locale-aware plural rules).
  `ngettext`/`ngettext_lazy` exist to solve count-based pluralisation correctly, but a raw
  `settings.LEARNER_LABEL` string substituted into a sentence bypasses them entirely.
- **Possessives**: "the learner's progress" vs "the learners' progress" — a substituted noun doesn't
  know which grammatical case it's in.
- **Capitalisation**: a label configured as "learner" reads wrong mid-sentence-capitalised ("No
  Learner is..."), and reads wrong as a lowercase column header ("learner" vs "Learner").
- **Sentence-embedding**: any label-substitution scheme still has to handle articles ("a" vs "an"),
  verb agreement, and word order — none of which a single-token substitution setting can express.
- **Translation**: `gettext`'s whole model assumes the *sentence*, not a token inside it, is the
  translatable unit — because in many languages the label's grammatical form changes depending on
  its role in the sentence (case, gender agreement, etc.), which a token substitution can't capture.
  Mixing a runtime-configurable brand word with `gettext`-based translation compounds the problem:
  you'd need a translated string *per configured label per locale*, which no tooling here supports.

**FLS's current i18n state (verified in-repo):**
- No `locale/` directory anywhere in the repo (`Glob **/locale/** → no matches`).
- `MIDDLEWARE` in `config/settings_base.py` has no `django.middleware.locale.LocaleMiddleware`.
- `LANGUAGE_CODE = "en-us"` is hardcoded; `USE_I18N = True` is Django's own default and isn't
  evidence of active translation work.
- `gettext_lazy` is imported in exactly 5 files
  (`freedom_ls/student_management/models.py`, `freedom_ls/organisations/models.py`,
  `freedom_ls/course_access/backends.py`, `freedom_ls/content_engine/models.py`,
  `freedom_ls/accounts/forms.py`), and where checked (`student_management/models.py`) it's used only
  for a single `verbose_name` on a `CharField`, not for user-facing template prose.
- No template in the repo uses `{% trans %}` / `{% blocktrans %}` (not found by search).

**Recommendation:** per-tenant configurable copy is **not in scope for this spec** — the idea
explicitly frames this as "a pure rename... no behaviour changes, no new features," and building
configurability now would violate that framing while also requiring i18n infrastructure FLS doesn't
have. If a future spec wants per-tenant relabelling, it should scope it as: (1) build proper
`gettext`/`ngettext` i18n first (locale middleware, message catalogues, `{% blocktrans %}` in
templates), (2) treat the configurable word as a set of pre-translated strings selected by tenant
config, not a token substituted at render time, and (3) accept that this is real feature work with
its own design cost, not a follow-up to a rename. My advice if asked directly: it's a legitimate
idea for a white-label multi-tenant product, but doing it *well* is expensive relative to its
payoff for an LMS that has, per idea.md, "no live installs" yet — I'd defer it until there's a
concrete tenant asking for a different word.

---

## 3. Copy-quality guidance for the rename

Grounded in FLS's own brand-guidelines skill (`.claude/skills/brand-guidelines/SKILL.md`), which
already states the following voice rules relevant here:

> **Show, don't tell** — Don't say "flexible"... Every bold claim needs immediate evidence.
> **Direct over diplomatic** — No hedging, no fluff.
> **Respect the reader's time** — Front-load important information. If a sentence doesn't add value,
> cut it.
> Terminology table: `learners` (not `students`) — "Works across corporate, self-paced, and academic
> contexts."
> Error-message rules: "Name the specific problem. Suggest a specific fix. Use plain language...
> No exclamation points on routine actions."
> Empty-state sample: `"No courses yet. Drop some Markdown files into your content directory and add
> a course.yaml to get started."` — i.e. empty states should be specific and actionable, not a bare
> restatement of the row-count in prose form.

Concrete rules for whoever does the rewrite:

1. **Plural**: "learners" (regular `-s` plural, no exceptions to track).
2. **Possessive**: singular — "a learner's progress"; plural — "learners' progress." Never write
   "learners's."
3. **Article**: "a learner" (consonant sound), never "an learner."
4. **Capitalisation**:
   - Column headers / UI labels: Title Case per FLS's existing pattern (`"Student"` → `"Learner"`,
     not `"learner"`).
   - Mid-sentence: lowercase — "No learners are currently enrolled," not "No Learners..."
5. **Mechanical swap reads badly — needs a rewrite, not a search-replace:**
   - `"No students are currently enrolled in this cohort."` → `"No learners are currently enrolled
     in this cohort."` is actually fine mechanically (the noun swap alone reads naturally here) —
     but if the rewriter wants to align fully with the brand voice's "specific and actionable" empty
     states (see the sample copy above), consider whether an educator landing on an empty cohort
     roster would benefit from a next action, e.g. `"No learners are enrolled in this cohort yet. Add
     learners from the cohort page."` — **flag as a judgement call, not mandatory** (idea.md is a
     pure rename; only make this call if the spec explicitly wants a copy upgrade, not just a
     word-swap).
   - `"Students X–Y of Z"` → `"Learners X–Y of Z"` — mechanical, safe.
   - `"Student"` column header → `"Learner"` — mechanical, safe.
6. **When "learner" is wrong — decision rule:** see §4 below; the short version is "learner" names a
   *role in a course*, "user" names *an authenticated account regardless of role*. If a string is
   talking about authentication, account settings, permissions that apply platform-wide, or webhook
   payloads describing "who did this" without regard to their course role, it should say "user," not
   "learner." If it's naming *someone who is not authenticated at all* (e.g. an anonymous visitor
   browsing public course listings), neither "learner" nor "user" is correct — use "you" (second
   person, if addressing them directly) or avoid the noun.
7. **Column headers, empty states, counts, button labels:**
   - Counts follow the existing `"{Noun} X–Y of Z"` pattern already used for `"Items"` in the same
     template (`course_progress_panel.html:164`) — keep that pattern, just swap the noun.
   - Button labels: FLS's brand voice favours direct, specific verbs (`"Fork It on GitHub"`, not
     generic CTAs) — if any button currently reads `"View Students"` or similar, prefer `"View
     Learners"` over a vaguer alternative; don't invent new copy patterns as part of a pure rename.

---

## 4. The "user vs learner" audit decision procedure

FLS's actual role model (verified in `freedom_ls/role_based_permissions/roles.py` and
`freedom_ls/accounts/models.py`, `freedom_ls/student_management/models.py`):

- `User` (`freedom_ls/accounts/models.py`) is the single authentication identity — email/password,
  `is_staff`, `is_superuser`, no notion of "role" baked into the model itself.
- Roles are assigned separately and are **scoped** — `SCOPE_SYSTEM`, `SCOPE_SITE`, or `SCOPE_OBJECT`
  (`role_based_permissions/types.py`, consumed by `BASE_ROLES` in `roles.py`). The role catalogue
  today is `site_admin`, `instructor`, `ta`, `organisation_staff`, `system_admin`, `student`
  (→ `learner`), `observer`.
- Object-scoped roles (`instructor`, `ta`, `student`/`learner`, `observer`) are assigned **per
  object** — i.e. per course or similar — via `ObjectRoleAssignment`-style records, which is exactly
  why the same `User` can hold `instructor` on one course and `student`/`learner` on another. This is
  explicit and structural, not incidental: `roles.py:13`'s TODO ("no mention of rights over students,
  only rights over users") already names this exact ambiguity as a known problem to fix.
- `UserCourseRegistration`, `CohortMembership`, `UserCohortDeadlineOverride` all key on `user`, not
  on a role — correctly, since registration is an account-level fact ("this `User` is registered for
  this course"), and the model itself doesn't need to assert that the user is *only* ever a learner.

**Decision procedure for an occurrence of "user" in code or copy:**

1. Is the sentence/variable/field about the **account** — authentication, identity, site membership,
   who-did-this audit trail, permissions or roles that could be held by *any* role (instructor,
   admin, learner alike)? → **Stays "user."** Examples already correct per idea.md's out-of-scope
   list: `User`, `UserCourseRegistration`, `CohortMembership`.
2. Is it about **taking a course** specifically — progress, deadlines, submissions, the
   course-facing app/URL namespace, a roster of people *enrolled in* something? → **Becomes
   "learner."** This is the bulk of the rename: `student_management`/`student_progress`/
   `student_interface`, `StudentDeadline`, the educator-interface roster copy.
3. Is the same variable used in a context where the person **might not be enrolled at all** (e.g. an
   anonymous visitor, or a general webhook payload keyed by `user_id`/`user_email` regardless of
   role — see `UserCourseRegistration.save()`'s `fire_webhook_event(..., {"user_id": ..., "user_email":
   ...})`)? → **Stays "user."** Webhook payload keys are also an external contract (downstream
   consumers depend on the field name), which is an independent reason not to touch them as part of
   a copy rename even where "learner" might read more naturally.
4. Is it a **permission codename** that tracks a model name (`view_cohort`, `add_cohort`, etc.)? →
   Not part of this rename per idea.md — codenames track model names, and no model here is called
   `Learner`.
5. **Ambiguous case worth flagging explicitly:** `role_based_permissions/roles.py:93-94`'s role key
   `"student"` and `display_name="Student"` is a *role*, and role display names by definition
   describe what the person *is doing in this context* (learner of a course), not their whole
   identity — so it becomes `"learner"` per idea.md §6, consistent with rule 2 above.

---

## 5. In-tree user-visible copy inventory

Everything found by grepping `[Ss]tudent` across `freedom_ls/*/templates/` and `freedom_ls/themes/`
(no theme in-tree currently has student-named copy — confirmed by an empty grep result against
`freedom_ls/themes`). The table below covers items **beyond** what idea.md already names verbatim
(the "Student" header, "Students X–Y of Z", and the "No students..." empty state), plus those three
for completeness since the spec should have one authoritative list.

| path:line | current string | suggested replacement | needs human judgement? |
|---|---|---|---|
| `freedom_ls/educator_interface/templates/educator_interface/partials/course_progress_panel.html:74` | `Student` (column header) | `Learner` | No |
| `freedom_ls/educator_interface/templates/educator_interface/partials/course_progress_panel.html:173` | `Students {{ student_page.start_index }}–{{ student_page.end_index }} of {{ student_page.paginator.count }}` | `Learners {{ ... }}` | No |
| `freedom_ls/educator_interface/templates/educator_interface/partials/course_progress_panel.html:184` | `No students are currently enrolled in this cohort.` | `No learners are currently enrolled in this cohort.` (mechanical) — optionally add a next-action per §3.5, but only if the spec wants a copy upgrade, not just a rename | **Yes** — whether to add a call-to-action is a scope decision |
| `freedom_ls/base/templates/cotton/data-table.html:125` | `{'header': 'Student Count', ...}` (comment/worked example in a docstring-style usage block, not live UI copy) | `{'header': 'Learner Count', ...}` | No |
| `freedom_ls/base/templates/cotton/data-table.html:138` | `{'header': 'Students', ...}` (same — worked example) | `{'header': 'Learners', ...}` | No |
| `freedom_ls/student_interface/templates/student_interface/course_form_complete.html:76` | `data-testid="student-answer-{{ item.question.id }}"` | `data-testid="learner-answer-{{ item.question.id }}"` | No — but note `data-testid` values are test-selector contract; check Playwright specs reference this exact string before renaming (out of this research's scope to grep the test suite, but flag for the implementer) |
| `freedom_ls/student_interface/templates/student_interface/course_form_complete.html:77` | `{% for option in item.student_selected %}` | Depends on the backing context-variable name chosen by the view rewrite (`student_selected` → presumably `learner_selected`); not copy, but must move in lockstep with the Python-side rename idea.md §7 already scopes (`student_count`, etc.) | No — mechanical once the view's context key is renamed |

**Not found as live prose (checked and clear):** no other template under `freedom_ls/*/templates/`
or `freedom_ls/themes/` contains the word "student" in rendered text — every other hit from the
broad grep (46 lines) was a URL name (`student_interface:...`), a static-file path
(`{% static 'student_interface/js/...' %}`), an `{% include %}`/`{% extends %}` template path, or an
inline HTML comment referencing the app name — all covered by idea.md's §4 (template/static
directory move) and §3 (URL namespace move), not new copy findings.

**Flag:** none of the found strings are semantically ambiguous about learner-vs-user (all are
squarely about people taking a course), so §4's audit procedure doesn't surface any "should actually
be 'user'" cases in this specific set of UI strings — the audit is more likely to matter in Python
variable/method names and code comments than in the rendered copy itself, per idea.md's own framing
of the risk ("mechanical renaming fixes the wrong word; it does not fix the vague one" — i.e. the
risk is in places doing a search-replace on "student" *misses* because the code already, incorrectly,
says "user").

---

## Reference URLs

- [SCORM Run-Time Reference Chart for SCORM 1.2 and SCORM 2004](https://scorm.com/scorm-explained/technical-scorm/run-time/run-time-reference/) — official
- [GetLearnerInformation & UserID :: Choosing the Right UserID – Rustici Software Knowledge Base](https://support.scorm.com/hc/en-us/articles/206167466-GetLearnerInformation-UserID-Choosing-the-Right-UserID) — official/vendor
- [What else is there besides cmi.core.student_name (SCORM 1.2) / cmi.learner_name (SCORM 2004)? – Docebo Community](https://community.docebo.com/product-q-a-7/what-else-is-there-besides-cmi-core-student-name-scorm-1-2-cmi-learner-name-scorm-2004-10166) — community, corroborating
- [What Is xAPI? – LMSPedia](https://lmspedia.org/what-is-xapi-tin-can-api/) — community/industry explainer
- [xAPI-Spec / xAPI-Data.md — adlnet/xAPI-Spec (GitHub)](https://github.com/adlnet/xAPI-Spec/blob/master/xAPI-Data.md) — official spec repo
- [xAPI.com Homepage](https://xapi.com/) — official (ADL-affiliated)
- [1EdTech Learning Tools Interoperability Basic LTIv1 Implementation Guide](https://www.imsglobal.org/specs/ltiv1p0/implementation-guide) — official standard
- [Learning Tools Interoperability (LTI) Names and Role Provisioning Services v2.0](https://www.imsglobal.org/spec/lti-nrps/v2p0) — official standard
- [LTI Vocabulary – Instructure Community](https://community.instructure.com/en/kb/articles/637146-lti-vocabulary) — vendor/community, corroborating role vocabulary
- [Moodle Learner Profiles — Open edX Product Management Wiki](https://openedx.atlassian.net/wiki/spaces/OEPM/pages/3901554743/Moodle+Learner+Profiles) — community
- [View Learner Data — Open edX Documentation](https://docs.openedx.org/en/latest/educators/how-tos/data/view_learner_data.html) — official product docs
- [Guide to Role-Specific Course Views — Open edX Documentation](https://docs.openedx.org/en/latest/educators/references/roles_for_viewing.html) — official product docs
- [Teacher role - MoodleDocs](https://docs.moodle.org/502/en/Teacher_role) — official product docs
- [Learner vs Student: Meaning And Differences](https://thecontentauthority.com/blog/learner-vs-student) — community/anecdotal
- [Developing Learners vs. Teaching Students | AACSB](https://www.aacsb.edu/insights/articles/2020/07/developing-learners-vs-teaching-students) — official standards body (accreditation)
- [Terminology: "Learners" vs "Students" - Learning Savant](https://www.learningsavant.com/p/terminology-learners-vs-students) — community/anecdotal
- [Corporate training terms, glossary & terminology worth knowing](https://symondsresearch.com/corporate-training-glossary/) — community/anecdotal
- [Skills Development Act 97 of 1998 (South Africa) — ICNL](https://www.icnl.org/research/library/south-africa_saskillsdevelop1998/) — official statute reference
- [UNDERSTANDING QCTO VS SETA QUALIFICATIONS IN SOUTH AFRICA'S EVOLVING SKILLS DEVELOPMENT LANDSCAPE](https://www.compliancehub.co.za/post/understanding-qcto-vs-seta-qualifications-in-south-africa-s-evolving-skills-development-landscape) — industry/community
- [Transition from SETA to QCTO — Leadership Institute](https://www.leadershipinstitute.co.za/transition-from-seta-to-qcto/) — industry/community
- [#3373 (verbose_name_plural and internationalization) – Django](https://code.djangoproject.com/ticket/3373) — official issue tracker
- [#14844 (i18n blocktrans tag pluralization feature limited by gettext constraints) – Django](https://code.djangoproject.com/ticket/14844) — official issue tracker
- [Advanced Django internationalization - Lokalise Blog](https://lokalise.com/blog/advanced-django-internationalization/) — vendor/community

**In-repo sources cited (verified in this repo, not web):**
- `spec_dd/2. in progress/learner-terminology-rename/idea.md`
- `.claude/skills/brand-guidelines/SKILL.md`
- `freedom_ls/accounts/models.py`
- `freedom_ls/student_management/models.py`
- `freedom_ls/role_based_permissions/roles.py`
- `config/settings_base.py`
- `docs/product/security-and-data-handling.md`
- `spec_dd/0. drafts/xx. sacaa question-pools-and-remediation/research_sacaa_requirements.md`
- `freedom_ls/educator_interface/templates/educator_interface/partials/course_progress_panel.html`
- `freedom_ls/base/templates/cotton/data-table.html`
- `freedom_ls/student_interface/templates/student_interface/course_form_complete.html`

status: ok
