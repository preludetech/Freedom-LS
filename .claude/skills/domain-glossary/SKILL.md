---
name: domain-glossary
description: "The FreedomLS domain vocabulary — the canonical noun for every concept in the system, where each one is defined, and the words that are already taken and must not be reused. Use whenever you are naming something: writing or reviewing a spec, idea, plan or research note; adding a model, field, function, URL name or template; or writing product docs. Consult this before inventing a word for a concept — FLS almost certainly already has one."
---

# FreedomLS Domain Glossary

The vocabulary of this system. If a concept is listed here, use the word listed here — in prose and
in identifiers alike.

If a concept is **not** listed here, find the model that represents it and use its class name and
field names. Those are the vocabulary of last resort and they beat any word you invent. Only when
neither exists is the concept genuinely new; coin a word for it, say at first use that it is new, and
define it once in terms of the nouns below.

**The code is authoritative and this file is an index over it.** When they disagree, the code is
right and this file needs fixing.

---

## Content — `freedom_ls/content_engine/models.py`

| Term | Defined at | Means |
| --- | --- | --- |
| `Course` | `models.py:172` | A course. The top-level content collection. |
| `CoursePart` | `:347` | A chapter within a course. Also a collection. Product docs call it a "course part (chapter)". |
| `Topic` | `:145` | A page of markdown content a learner reads. |
| `Activity` | `:159` | Like a `Topic`, plus a difficulty `level`. Not currently used by FLS courses. |
| `Form` | `:421` | A form or quiz. `FormPage`, `FormContent`, `FormQuestion`, `QuestionOption` hang off it. |
| `ContentCollectionItem` | `:381` | **The through model.** One row links a `collection` to a `child`, with an `order` and optional `overrides`. |
| **collection** | `ContentCollectionItem.collection` | The `Course` or `CoursePart` a child sits in. A generic FK. |
| **child** | `ContentCollectionItem.child` | The `Topic`, `Form` or `CoursePart` sitting in a collection. A generic FK. |
| `File` | `:580` | An uploaded file attached to content. |

### `ContentCollectionItem` — read this before naming anything nearby

It is the only word FLS has for "this piece of content is in this collection, at this position". A
document describing content structure names *this model*; it does not invent a synonym for it.

Two accessors sit on top of it and they are **not** the same thing, which is the trap:

- `Course.items` / `CoursePart.items` — the `ContentCollectionItem` **rows** (a `GenericRelation`).
- `Course.children()`, `children_flat()`, `viewable_items()` — the resolved **children**
  (`Topic` / `Form` / `CoursePart` objects), with the `ContentCollectionItem` discarded.

So bare **"item"** is already ambiguous in this codebase: `Course.items` means rows,
`viewable_items()` means children, and `content_item` on the deadline models means the resolved
`Topic`/`Form`. Do not add a third sense. When you need to be unambiguous, say **collection item**
for the row and **child** for the resolved object.

---

## Course access — `freedom_ls/learner_management/models.py`

**"Registration" is the word.** Not "enrolment", not "grant", not "entitlement".

| Term | Defined at | Means |
| --- | --- | --- |
| `Learner` | `models.py:51` | **A user's association with one organisation.** One row per `(user, organisation)` — `unique_learner_per_organisation` (`:73`). Fields: `user`, `organisation`, `is_active`, `created_at`. See the note below. |
| `LearnerCourseRegistration` | `:108` | One learner registered for one course. Fields: `learner`, `collection` (the `Course` — a legacy field name; match it, don't rename it), `is_active`, `registered_at`. Keyed `(site_id, learner, collection)` (`:120`). It has **no** `organisation` field — that comes from `learner.organisation`. |
| `CohortCourseRegistration` | `:165` | A cohort registered for a course. Its organisation is reached through `cohort.organisation`. |
| `Cohort` | `:32` | A group of learners, owned by an organisation. |
| `CohortMembership` | `:83` | One learner's membership of a cohort, keyed `(learner, cohort)` (`:88`). **Not** a registration — a membership grants access via the cohort's registrations. Its `clean()` (`:95`) enforces that the learner and the cohort share an organisation. |
| `CohortDeadline`, `LearnerDeadline`, `UserCohortDeadlineOverride` | `:191`, `:238`, `:285` | Deadlines. Each carries a `content_item` generic FK to the `Topic`/`Form`. `UserCohortDeadlineOverride` keeps its name but its field is now `learner` (`:293`). |
| `RecommendedCourse` | `:352` | A course recommended to a learner. Still keyed on `User` (`:358`), not `Learner` — it is a recommendation, not an enrolment. |
| `is_registered_for_course` | `learner_management/utils.py:69` | The access check. Every `COURSE_ACCESS_BACKEND` delegates to it. |
| `ensure_learner` | `learner_management/utils.py:104` | Get-or-create the `Learner` for a `(user, organisation)` pair. Idempotent, and reactivates a removed row. The only supported way to make one. |
| `CourseAccessDecision`, `CourseAccessBackend`, `CourseAccessType` | `course_access/backends.py:41`, `:95`, `:177` | The pluggable access layer. Note the `*Decision` suffix — it is the house pattern for a resolver's return value. |

### `Learner` — read this before naming anything nearby

`Learner` is **not** a synonym for `User`, and it is not a profile. It is the join row that says *this
person belongs to this organisation*, and it is the thing enrolment hangs off. A person studying
through two client organisations has **two `Learner` rows and one `User`**.

- **Enrolment is per-`Learner`.** `LearnerCourseRegistration`, `CohortMembership` and both deadline
  models point at `Learner`. An enrolment with no organisation cannot be represented — that is the
  point of the model.
- **Progress is per-`Learner`, keyed on the granting registration.** `CourseProgress` carries a
  `learner` FK plus exactly one of `learner_registration` / `cohort_registration` — the registration
  that minted the record — and `TopicProgress` / `FormProgress` hang off a `CourseProgress` via
  `course_progress`, not off `Learner` or `User` directly. A learner holding both an individual and a
  cohort registration for one course has two `CourseProgress` records; `course_progress_for`
  (`learner_progress/queries.py`) resolves which one a piece of work lands on, the same way
  `learner_for_course` resolves the registration. Nothing filters `CourseProgress`, `TopicProgress` or
  `FormProgress` by hand outside a short, named list of read paths — go through `course_progress_for`.
- **`is_active=False` means "removed from this organisation"**, never deleted. Nothing cascades: a
  removed learner keeps their registrations, memberships and progress. It is filtered explicitly at
  every call site — there is deliberately no manager that hides removed rows.
- **Never construct one directly.** Use `ensure_learner`.
- **`learners_visible_to`** (`learner_management/queries.py:209`) returns `Learner` rows and replaced
  the deleted `users_visible_to`. Don't reintroduce a user-shaped sibling.

---

## Progress — `freedom_ls/learner_progress/models.py`

| Term | Defined at | Means |
| --- | --- | --- |
| `CourseProgress` | `models.py:588` | A learner's progress through a course. `verbose_name_plural = "Course progress records"`, so **"course progress record" is existing FLS language** — use it. |
| `CourseItemProgress` | `:19` | The abstract base `TopicProgress` extends. |
| `TopicProgress` | `:59` | "Topic progress records". One row per placement per record. |
| `CourseFormAttempt` | `:239` | "Course form attempt". The course's side of one sitting: which record it counts toward, and which placement it was sat at. Many per placement, one per attempt. |
| `FormProgress` | `form_engine/models.py` | "Form progress records". The sitting itself: its answers, its score, when it finished. Lives in `form_engine` and knows nothing about courses, so a form can also be sat outside one. |
| `QuestionAnswer` | `form_engine/models.py` | One answer within a `FormProgress`. |
| `learner_registration` / `cohort_registration` | `CourseProgress.learner_registration` / `CourseProgress.cohort_registration` | Exactly one is set — the registration that minted this record. See `course_progress_for`. |
| `created_at` / `started_at` | `CourseProgress.created_at` / `.started_at` | Split, and not interchangeable: `created_at` is the registration date (`auto_now_add`); `started_at` is the first content access, null until then. |
| **progress percentage** | `CourseProgress.progress_percentage` | Denormalised completion percentage. |
| **resume pointer** | `CourseProgress.last_accessed_item` | Where the learner left off. `docs/product/learner-tracking.md` uses this phrase — it is not coined. A concrete `ContentCollectionItem` FK (`on_delete=SET_NULL`), not the child it resolves to — a topic placed twice in a course needs the pointer to name a position, not just the topic. |

Say **"course progress record"** rather than a bare "progress record" when more than one of the three
models is in play: all three use the phrase, so an unqualified one reads ambiguously.

Keep **"form progress record"** for the `form_engine` row and **"course form attempt"** for the
`learner_progress` row that places it in a course. They are two halves of one sitting, and a sentence
that says "the attempt" without saying which half is ambiguous wherever the split matters. Course code
resolves attempts through `learner_progress/attempts.py`, never through `FormProgress`'s own
`(user, form)` helpers, which would hand back a sitting from another record.

---

## Tenancy — `freedom_ls/organisations/`, `freedom_ls/site_aware_models/`

| Term | Defined at | Means |
| --- | --- | --- |
| `Site` | Django `Sites` | The tenant, and the isolation boundary. |
| `Organisation` | `organisations/models.py:28` | A client or department **inside** a site. A grouping, **not** an isolation boundary — see `docs/product/multi-tenancy-and-isolation.md`. |
| `SiteAwareModel` / `SiteAwareModelBase` / `SiteAwareManager` | `site_aware_models/models.py` | The base model and manager that apply the site filter. |

---

## Words that are already taken

Do not give these a second meaning.

| Word | What it already means | Use instead |
| --- | --- | --- |
| **grant** | A *role or object permission* — `learner_management/queries.py` ("per-cohort guardian grant", `granted_cohorts`, `assign_object_role`), `context_processors.py`, `docs/product/learner-tracking.md` ("their access grants"). | For course access: **registration**. (The verb is fine: "the registration that granted access".) |
| **item** | Ambiguous already — `Course.items` are `ContentCollectionItem` rows, `viewable_items()` are children, `content_item` is the resolved `Topic`/`Form`. | **collection item** for the row, **child** for the object. |
| **link** | An `<a href>` in ~280 template and view usages. | Fine as a verb ("links a collection to a child"); not as a noun for a model or field. |
| **slot** | `Course.accent_slot`, palette slots, cotton template slots. | Something else. |
| **course item** | Positional content in a course — `view_course_item`, `_paginate_course_items` (the educator matrix columns), `docs/product/educator-interface.md`. Today it means the resolved `Topic`/`Form`. | Only reuse it deliberately, and say so. |
| **collection** | `ContentCollectionItem.collection`, and `LearnerCourseRegistration.collection` (which is a `Course`). | Keep it for these; don't widen it. |
| **is_active** | Three different things on three models: removed-from-organisation (`Learner`), and registration in force (`LearnerCourseRegistration`, `CohortCourseRegistration`). | Fine to reuse — it is the house flag name. But a sentence naming two of them must name the model. |
| **learner** | `Learner`, the `(user, organisation)` association row — and also the everyday English word for the person. | In prose either is fine. As an identifier, `learner` means the model; write `learner.user` / `learner__user` when you mean the account. |

---

## Prose vs. code

`.claude/skills/brand-guidelines/SKILL.md` §Terminology holds the **copy-scoped** Use/Not table:
learners not students, content not curriculum, extend not customise, builders not administrators,
learning system not LMS, foundation not platform.

**The word is *learner*.** That is settled, in prose and in code alike.

The codebase has caught up. `learner-terminology-rename` moved the three apps to `learner_management`,
`learner_progress` and `learner_interface`, renamed their app labels, turned `StudentDeadline` into
`LearnerDeadline`, and reset those apps' migration history to a single `0001_initial` each. There is no
`student_*` namespace left to match.

- **Never introduce a `student_*` name** — not an app, module, class, field, function, template, URL
  name or test. There is nothing left for it to be consistent with.
- **A `student` you find in the tree is one of three things**, none of them a naming convention to
  follow: another product's word in research prose (Open edX's `StudentModule`, SCORM's), a stale
  `__pycache__` directory from before the rename, or a genuine miss — fix the last one.
- **`user` is not the same question.** Where a model's field genuinely is `user`
  (`CourseProgress.user`, `Learner.user`, `RecommendedCourse.user`), that is Django's own noun for an
  account, not the old word for a learner. Leave it alone — renaming it to `learner` would be wrong,
  because `Learner` is a different thing.
- **But do check which one a model *should* key on.** Enrolment moved from `User` to `Learner`
  (`unique_user_course_registration` is gone; the constraint is now
  `unique_learner_course_registration`), while progress has not moved yet. A new model keying on
  `user` should be able to say why.

---

## Where else to look

- `docs/product/README.md` — the index, and one-paragraph definitions of every concept.
  `docs/product/learner-tracking.md` is the progress vocabulary; `learner-experience.md` the player's.
- `docs/app_structure.md` — the canonical app names and the authoritative dependency graph.
- `claude_plugins/fls-content/skills/content-types/SKILL.md` — the author-facing `content_type` values.
- `freedom_ls/content_engine/schema.py` — `ContentType` as a `StrEnum`.
