# Learners associated with organisations

Follow-on from the shipped Organisation layer (`spec_dd/3. done/2026-08-21_09:09_organisations`).

Today, "who belongs to this organisation" is **derived, never stored**. `users_visible_to`
(`learner_management/queries.py:163-185`) answers it by unioning "members of cohorts in this
organisation" with "holders of a `UserCourseRegistration` in this organisation". There is no way to
say a person is one of an organisation's learners *before* a registration exists, and no way for an
educator to curate the roster at all.

This cut introduces an explicit **`Learner`** model: a row recording that a user is associated with
an organisation. A user may be a Learner of several organisations on the same Site.

> **This reverses a stated non-goal of the Organisation cut** — "No organisation membership object. A
> learner's organisation comes from their registrations." That call was made to avoid Docebo's
> multi-branch cleanup pain, but Docebo's walk-back was a reaction to several branch admins editing
> one shared, mutable *profile* — not to multi-org membership as such. FLS already avoids that
> trigger: profile fields live on the one Site-wide `accounts.User`, and Organisation is explicitly
> not a profile-ownership boundary. The reversal is deliberate and the reasoning is recorded here so
> nobody re-litigates it from the old doc.

---

## Prerequisite: the terminology rename lands first

FLS mixes "student" and "learner" for the same person. That is now settled: **the word is
"learner"** — models, apps, permissions, URLs and copy alike. The rename is its own spec,
`spec_dd/1. next/learner-terminology-rename`, and **it merges before this cut.**

Everything below is written in the post-rename names, so `learner_management` is today's
`student_management`, `learner_progress` is `student_progress`, and `learner_interface` is
`student_interface`.

Doing it first is cheap for the same reason this cut skips a backfill — no live installs, and the
dev database is rebuilt from scratch — and it stops this cut from filing a model called `Learner`
inside an app named after the other word, which is the mismatch that made terminology an open
question in the first place.

---

## What a Learner row is

**A roster entry, not an access gate.** Registration and cohort membership keep working exactly as
they do today; they simply also ensure a `Learner` row exists. Nothing anywhere checks "is this
person a Learner?" before granting access to anything. `Learner` scopes what an *educator* sees and
records who an organisation considers theirs — it never decides what a *learner* can reach.

Keeping it a record rather than a gate follows Decision 5 of the Organisation cut: loosening later is
easy, tightening later is not.

**Two creation paths.**

1. **Auto-provisioned** the first time a user gets a `UserCourseRegistration` in the organisation, or
   a `CohortMembership` in one of its cohorts. This is the common case and needs no educator action.
2. **Added manually** by an educator holding a role on that organisation, for someone not registered
   for anything yet — pre-building a roster, or tracking someone who has been told they'll join.

This is the shape Canvas uses for `UserAccountAssociation` (an auto-maintained association table,
separate from `Enrollment`, that answers "which accounts does this user touch at all") plus the
manual lever that Docebo, TalentLMS and Blackboard all added once membership became a real object.
No product researched ships a membership object that admins cannot touch directly.

---

## Data

`Learner`, a `SiteAwareModel`, living in **`learner_management`**.

| Field | Notes |
|---|---|
| `user` | FK `settings.AUTH_USER_MODEL`, `CASCADE` — matches every other user FK in the app |
| `organisation` | FK `Organisation`, `PROTECT` — matches `Cohort.organisation` and `UserCourseRegistration.organisation`, and backs up the admin's refusal to delete organisations |
| `is_active` | Roster state. `False` means "removed from this organisation", never "deleted" |
| `source` | `auto` or `manual` — which of the two creation paths made this row |
| `added_by` | FK to user, nullable, `SET_NULL`. Set for manual adds only; accountability for a deliberate roster action |
| `created_at` | `auto_now_add` |

Unique on `(site, user, organisation)`, mirroring `unique_user_course_registration`. Because an
`Organisation` already belongs to exactly one Site, the `site` column there is belt-and-braces rather
than load-bearing.

**`source` is the field that makes the rest of the design safe.** It is what lets a repair command
rebuild auto-derived rows without ever clobbering a roster an educator curated by hand. Without it,
FLS would have to guess — which is exactly the position Docebo is in.

**No `pending`/`invited` status.** Every product that has those states uses them to drive
self-registration or SSO flows this cut is not building. Adding the field now with nothing to drive
it is the version of a status field the research found products regret.

**App placement: `learner_management`, not a new app and not `organisations`.** `learner_management`
already depends on both `organisations` and `accounts`, so `Learner` adds **zero new edges** to
`docs/app_structure.md`. Putting the sync receivers in `organisations` instead would force
`organisations` to import `learner_management` models as signal senders — inverting the edge that
cut deliberately established. Regenerate `docs/app_structure.md` with `/ds:app_map` regardless.

*Landmine to state in the spec:* `accounts` must never gain a runtime dependency on wherever
`Learner` lives. `learner_management → accounts` already exists, and nearly every app depends on
`accounts`, so wiring Learner creation into the signup flow itself would create a cycle through most
of the codebase. Signup alone creates no registration or cohort membership today, so nothing needs
this — but it is the direction a naive implementation reaches for.

---

## Removal

**Removing a learner is soft, and it is refused while they are still active in the organisation.**

An educator may only remove a learner from an organisation when that learner has **no active
`UserCourseRegistration` in it and no `CohortMembership` in any of its cohorts**. Otherwise the
action is refused with an explanation telling the educator to deactivate the registrations or remove
the cohort membership first.

This is the point of the rule: it makes the "enrolled but not on the roster" state — someone actively
studying who has silently vanished from their educator's list — **unreachable by construction**. No
product researched handles that state well; Moodle's cohort-sync forum threads and Docebo's
pipe-delimited CSV audits are the closest prior art, and both are widely reported as confusing.

Removal sets `is_active = False`. It **never** cascades to `UserCourseRegistration`,
`CohortMembership`, or any progress model. That cascade is precisely where Moodle's cohort sync
burned people — roster edits silently destroying course access and the appearance of learning
history. FLS is better placed than any product surveyed to avoid it cheaply, because
`UserCourseRegistration` already carries its own `is_active` and its own `organisation` FK: the two
lifecycles are decoupled by construction, not by discipline.

Re-adding a removed learner flips `is_active` back. There is no history to restore, because none was
ever at risk.

**No hard delete on `Learner` in this cut**, following the same discipline the Organisation cut
applied to `Organisation` itself. This also sidesteps a real compliance question: "delete this
learner" from Organisation A is meaningless when the same person also studies with Organisation B on
the same Site, and legal retention can override an erasure request outright.

---

## Keeping rows in sync

Three parts, all shipped together:

1. **One helper, `ensure_learner(user, organisation)`** — an idempotent `get_or_create`, the single
   source of truth for how a Learner row gets made. It also **reactivates** a row that was previously
   removed: a fresh registration or cohort membership is a live signal of re-association, and leaving
   it deactivated would recreate the invisible-learner state the removal rule exists to prevent.

2. **`post_save` receivers on `CohortMembership` and `UserCourseRegistration`**, defined in
   `learner_management`, delegating straight to the helper.

   Django's own docs advise preferring an explicit call over a signal when sender and receiver are
   both inside your project — and that advice is right, but its premise doesn't hold here. FLS ships
   as a submodule into projects **designed** to extend it; a downstream project's own code creating a
   `UserCourseRegistration` is definitionally outside FLS's project, and an explicit call can never
   fire there. A signal covers code FLS has never seen, as long as it calls `.save()`, which ordinary
   ORM usage does. That is the narrow case both Django's docs and the community critiques carve out
   as legitimate.

   A welcome side effect: the ~448 existing factory call sites across 58 test files need **no
   changes**, because `SiteAwareFactory._create` calls `obj.save()` directly. The 14 QA seeding
   commands under `qa_helpers/` — which pytest never collects, and which were an easy-to-miss trap in
   the Organisation cut — are covered for the same reason.

3. **A `rebuild_learners` management command**, following
   `learner_progress/management/commands/recalculate_progress_percentages.py`. **Ships in this
   change, not as a follow-up** — with no backfill migration it is now the *only* thing that derives
   `Learner` rows from existing `UserCourseRegistration` and `CohortMembership` data, and the only
   mitigation for the gaps a signal cannot close.

   It **only inserts missing rows**. It never deletes, never touches a `manual` row, and never
   reactivates a removed learner — otherwise every run would resurrect exactly the people educators
   deliberately took off the roster.

**Say plainly, in the model docstring and the upgrade notes, that `Learner` rows are best-effort and
eventually consistent, not a transactional guarantee**, and name `rebuild_learners` as the recovery
path. The residual gap is `bulk_create()`, `update()` and `loaddata` — all silent, no exception, no
log. The educator roster would simply under-count, with nothing prompting anyone to notice.

*Ordering hazard:* `UserCourseRegistration.save()` already fires a `course.registered` webhook on
insert. The spec must decide explicitly whether the Learner row is committed before that webhook
fires — a consumer may reasonably expect the association to exist when the event arrives.

---

## Educator interface

- **`users_visible_to`'s second branch becomes a direct fact.**
  `Q(usercourseregistration__organisation=organisation)` becomes
  `Q(learner__organisation=organisation, learner__is_active=True)`. This is a **behaviour change, not
  a refactor** — the set of visible users can shift, in both directions, depending on when Learner
  rows exist relative to registrations. Say so in the spec and test it.

- **The cohort branch survives unchanged.** It exists because a per-cohort guardian grant says
  nothing about people outside that cohort — an educator holding only a cohort grant must never see
  the organisation's individually-registered roster. That constraint is about the *educator's*
  authorisation level, not about how a learner's association is stored, so `Learner` does not touch
  it. The `.distinct()` stays for the same reason: two join paths into `User`.

- **New roster actions**: add a learner, remove a learner. One at a time. Both bounded to
  organisations the educator already holds a role on, so no new authorisation surface appears.

- **Adding a learner is a lookup, never an account creation.** The duplicate-account trap is the most
  consistently reported sharp edge across every vendor researched. The add flow searches existing
  users **on this Site** and must not create accounts. The spec should name where that lookup lives,
  because the same "does this email already have an account here?" question will be asked by any
  future self-registration path too.

- **Roster queries must filter on `Learner.organisation` as strictly as the existing querysets filter
  on `organisation`**, with the same test guarantee the Organisation cut already commits to: two
  organisations, a role on one only, assert the other returns nothing.

- Untouched: `organisation_for_learner_course` and `latest_registration` answer a different question
  ("which organisation is this course being studied through") and are not superseded.
  `CohortCourseProgressPanel` does not funnel through `users_visible_to` at all and is out of scope.

---

## Migration

**No backfill. There is no production data to protect.** FLS has no live installs, so the dev
database is dropped and rebuilt rather than migrated forward — and the Organisation cut already told
any operator with existing data not to upgrade, so nothing downstream is carrying rows that a
backfill would have to find. The earlier plan for a `RunPython` derivation step is dropped.

That leaves **one migration**: a single `CreateModel` for `Learner`, every field `NOT NULL`, unique
constraint included. Nothing existing is narrowed, so reverse is a plain table drop with no data
loss to warn about. It lands in `learner_management` and stacks on the rename spec's final
migration state, so generate it only once that spec has merged.

Notes:

- **The derivation logic still ships** — it just lives only in `rebuild_learners`, not in a
  migration. Extract it as an importable callable anyway, so the command stays thin and the rule for
  "who should be a Learner" has one home: `UserCourseRegistration(user, organisation)` ∪
  `CohortMembership.user × Cohort.organisation`.
- **Include registrations regardless of `is_active`** in that derivation. `CohortMembership` has no
  `is_active` concept at all, so excluding inactive registrations would treat the two source
  relations inconsistently for what is meant to be one fact. `Learner.is_active` is *roster* state;
  registration status stays on the registration. Someone who registered and cancelled lands on the
  roster as a live learner an educator can then legitimately remove — which they are permitted to do,
  since no active registration remains.
- **Assert, don't propagate, on cross-site rows.** Nothing in the schema stops a `Cohort` or
  registration from pointing at an organisation on another Site — no current code path produces it,
  but if the data holds one, `rebuild_learners` should fail loudly naming the offending IDs
  (precedent: `learner_management/migrations/0006_validate_no_duplicate_students.py`) rather than
  quietly minting a cross-site Learner.
- **No thread-local request exists during a management command**, exactly as none exists during
  `migrate`. The site-aware managers and the `course.registered` webhook both assume one, so
  `rebuild_learners` must resolve Site explicitly from the organisation rather than relying on
  ambient request context.
- `bulk_create(ignore_conflicts=True)` has no precedent in this repo — flag it as a genuinely new
  pattern in the plan.
- **Upgrade notes** should say: any installation that somehow *does* carry pre-existing
  registrations or cohort memberships runs `rebuild_learners` once after migrating. That is the
  substitute for a backfill, and it is the same command that serves as the ongoing recovery path.
- **QA data** should include a learner in two organisations at once, a manually-added learner with no
  registration, and a removed (`is_active=False`) learner — the three states that only exist because
  of this cut. With the database rebuilt from scratch, seeded QA data is the *only* source of
  interesting `Learner` rows, so this matters more here than it would after a backfill.

---

## Non-goals for this cut

- **No learner-facing changes.** A learner studying through two organisations still sees one merged
  course list, with the existing per-course organisation logo as the only cue. *Caveat:* the
  existing-account lookup above is a shared surface that will not stay confined to the educator
  interface — name where it lives, even though the learner UI stays out.
- **No gating.** Being a Learner is never a precondition for registering or joining a cohort.
- **No hard delete, no merge.** Same reasoning as `Organisation` itself.
- **No bulk add/remove and no CSV import.** Every product that has these has them because branches
  hold hundreds of users; FLS expects 2–5 organisations per Site.
- **No self-registration via an organisation-specific signup URL, no SSO attribute mapping, no invite
  links.** All blocked on learner-facing work, or on infrastructure FLS doesn't have.
- **No `pending`/`invited` states.**
- **No periodic reconciliation task.** FLS has a background-task system but no scheduled-task
  infrastructure; that would be net-new scope. `rebuild_learners` run by hand, or by a downstream
  project's own cron, is the v1 substitute.
- **No cross-organisation admin view.** "Show me this person across every organisation" is a real
  want, but it must be an explicitly authorised site-level capability if it is ever built — never a
  side effect of holding two organisation roles at once. That is exactly how Canvas's long-standing
  cross-account visibility leak happened.
- **Not wired into `course_interest`, `course_applications` or `RecommendedCourse`.** There is no
  organisation to attach at those points in the flow, and none of them writes a registration today.
  When application acceptance ships it will need `ensure_learner` — note it there, don't pre-build it.
- **The rename itself is not in this cut.** Standardising student → learner across the codebase
  is `spec_dd/1. next/learner-terminology-rename`, and it merges first. Folding it in here would
  bury real design work under a repo-wide mechanical change.

---

## Decided: terminology

**The word is "learner".** This model is `Learner`, it lives in `learner_management`, and the
educator interface says "learners" — the prerequisite rename makes those three agree rather than leaving
`Learner` stranded in an app named after the other word. "Learner" matches Docebo's usage and reads
well to an educator.

What still belongs to *this* cut is the copy on the screens it builds. The roster screens say
"learner" consistently, and the pass audits for "user" leaking through where "learner" is meant —
precisely where Absorb's and Docebo's own UI copy gets sloppy.

---

## Research

- `research_multi_org_learner_modelling.md` — Canvas `UserAccountAssociation`, Moodle Workplace
  tenants, Open edX, Docebo/Absorb/TalentLMS branches, Brightspace, Cornerstone, SuccessFactors
- `research_learner_lifecycle.md` — creation triggers, manual roster management, removal semantics,
  status fields, the auto-created-row trap
- `research_codebase_impact.md` — line-referenced map of what `Learner` touches in FLS
- `research_migration_and_autocreation.md` — the backfill, and signals vs explicit calls vs rebuild
- `research_cross_org_identity_ux.md` — shared profiles, visibility leakage, the invisible learner,
  duplicate accounts, GDPR, naming
