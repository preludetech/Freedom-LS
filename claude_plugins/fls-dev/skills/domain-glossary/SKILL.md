---
name: domain-glossary
description: "The canonical noun for every FreedomLS concept, where each is defined, and the words already taken that must not be reused. Use whenever you are naming something: writing or reviewing a spec, idea, plan or research note; adding a model, field, function, URL name or template; or writing product docs. Consult it before inventing a word, because FLS almost certainly has one."
---

# FreedomLS Domain Glossary

The vocabulary of this system. If a concept is listed here, use the word listed here, in prose and
in identifiers alike.

If a concept is **not** listed here, find the model that represents it and use its class name and
field names. Those are the vocabulary of last resort and they beat any word you invent. Only when
neither exists is the concept genuinely new; coin a word for it, say at first use that it is new, and
define it once in terms of the nouns below.

**The code is authoritative and this file is an index over it.** When they disagree, the code is
right and this file needs fixing.

---

## Content — `freedom_ls/content_engine/models/` (a package: `courses.py`, `topics.py`, `articles.py`, `files.py`)

| Term | Defined at | Means |
| --- | --- | --- |
| `Course` | `courses.py` | A course. The top-level content collection. |
| `CoursePart` | `courses.py` | A chapter within a course. Also a collection. Product docs call it a "course part (chapter)". |
| `Topic` | `topics.py` | A page of markdown content a learner reads. |
| `Activity` | `topics.py` | Like a `Topic`, plus a difficulty `level`. Not currently used by FLS courses. |
| `Form` | `form_engine/models.py` | A form or quiz, lives in the `form_engine` app. `FormPage`, `FormContent`, `FormQuestion`, `QuestionOption` hang off it. |
| `ContentCollectionItem` | `courses.py` | **The through model.** One row links a `collection` to a `child`, with an `order` and the placement's due keys (`due_date`, `due_time`, `due_days_after_registration`, `no_due_date`). |
| `CoursePartChildDueDate` | `courses.py` | The due date one **part placement** sets for one child of its part. One row per (`part_collection_item`, `collection_item`). A part's own rows are shared by every course that places the part, so a value that differs per course lives here. |
| **placement** | `ContentCollectionItem` | One child at one position in one collection: the row itself, not a new model. A **part placement** is one whose collection is a `Course` and whose child is a `CoursePart`. |
| **collection** | `ContentCollectionItem.collection` | The `Course` or `CoursePart` a child sits in. A generic FK. |
| **child** | `ContentCollectionItem.child` | The `Topic`, `Form` or `CoursePart` sitting in a collection. A generic FK. |
| `Article` | `articles.py` | A standalone markdown content item (`ContentType.ARTICLE`) that belongs to no course and can be read publicly. Its `ArticleVisibility` is modelled on `CourseVisibility`, with only `published` and `hidden`. |
| **blog** | `freedom_ls/blog` | The public index that lists a site's published articles. |
| **byline** | article page | The line under an article's title that shows its `published_on` date and its `author`, each only when shown. |
| `File` | `files.py` | An uploaded file attached to content. |

### `ContentCollectionItem` — read this before naming anything nearby

It is the only word FLS has for "this piece of content is in this collection, at this position". A
document describing content structure names *this model* and invents no synonym.

Two accessors sit on top of it and they are **not** the same thing, which is the trap:

- `Course.items` / `CoursePart.items` — the `ContentCollectionItem` **rows** (a `GenericRelation`).
- `Course.children()`, `children_flat()`, `viewable_items()` — the resolved **children**
  (`Topic` / `Form` / `CoursePart` objects), with the `ContentCollectionItem` discarded.

So bare **"item"** is already ambiguous: `Course.items` means rows, `viewable_items()` means
children. Do not add a third sense. To be unambiguous, say **collection item** for the row and
**child** for the resolved object.

---

## Course access — `freedom_ls/learner_management/models.py`

**"Registration" is the word.** Not "enrolment", not "grant", not "entitlement".

| Term | Defined at | Means |
| --- | --- | --- |
| `Learner` | `models.py` | **A user's association with one organisation.** One row per `(user, organisation)` — `unique_learner_per_organisation`. Fields: `user`, `organisation`, `is_active`, `created_at`. See the note below. |
| `LearnerCourseRegistration` | `models.py` | One learner registered for one course. Fields: `learner`, `course`, `is_active`, `self_registered` (the learner made it, not staff; false on rows older than the field), `registered_at`. Keyed `(site, learner, course)`. It has **no** `organisation` field — that comes from `learner.organisation`. |
| `CohortCourseRegistration` | `models.py` | A cohort registered for a course. Its organisation is reached through `cohort.organisation`. |
| `Cohort` | `models.py` | A group of learners, owned by an organisation. |
| `CohortMembership` | `models.py` | One learner's membership of a cohort, keyed `(learner, cohort)`. **Not** a registration — a membership grants access via the cohort's registrations. Its `clean()` enforces that the learner and the cohort share an organisation. |
| `CohortDeadlineOverride` | `freedom_ls/deadlines/models.py` | A **deadline override** set for every learner registered for a course through one cohort. Keyed `(cohort_registration, collection_item)`; a null `collection_item` overrides the course time limit. Records `set_by` and `replaced_value`. |
| `LearnerDeadlineOverride` | `freedom_ls/deadlines/models.py` | A **deadline override** set for one learner's `CourseProgress`. Beats a `CohortDeadlineOverride` and the content default. A cohort move mints a new `CourseProgress`, so the old record's overrides stay behind. |
| `CoursePause` | `freedom_ls/deadlines/models.py` | One pause of one `CourseProgress`. Fields: `started_at`, `planned_resume_on`, `ended_at`, `reason`, `ended_reason`, `started_by`, `ended_by`. Open while `ended_at` is null; at most one is open per record. While it is open the learner's clock is stopped, and the days it lasted move every unmet deadline forward. |
| `DeadlineExtension` | `freedom_ls/deadlines/models.py` | One addition of `days` to one `CourseProgress`'s deadlines, aimed by `target_kind`. Rows stack by addition. Not a `LearnerDeadlineOverride`, which replaces a value. Records `reason` and `set_by`. |
| `SiteTimeZoneConfig` | `freedom_ls/site_aware_models/models.py` | One row per site naming the time zone its dates are read in, and whether learners see the zone. No row means the default zone. |
| **registration date** | `CourseProgress.created_at` | The date a relative deadline counts from, read in the site time zone. |
| **content default** | `CoursePartChildDueDate`, `ContentCollectionItem.due_date` / `due_time` / `due_days_after_registration` / `no_due_date`, `Course.time_limit_days` | The deadline the course author set. The lowest layer. For a child of a part, the course's part placement value (`CoursePartChildDueDate`) when it sets one, else the child's own row. A row holds the placement value from its `children:` entry, or the child file's value when the entry sets no due key. A value replaces the one below it whole; keys are never merged. |
| **deadline override** | `CohortDeadlineOverride`, `LearnerDeadlineOverride` | A deadline an admin set over the content default. |
| **time limit end** | `course_deadlines(record).time_limit` | When the course time limit runs out for one learner: registration date plus `time_limit_days`, at the end of that day. |
| **shift** | `CourseDeadlines` in `freedom_ls/deadlines/resolver.py` | The whole days a resolved deadline is moved forward by the pauses and extensions that apply to it. Computed when read, never stored. Learner copy says "moved by N days". |
| **paused days** | `CoursePause` | The length of one pause in whole days, rounded up. An open pause counts up to now. |
| **planned resume** | `CoursePause.planned_resume_on` | A date. The pause ends at 00:00 of that day in the site time zone. |
| **paused** | `CourseProgress` with an open `CoursePause` | The state of a `CourseProgress` with an open pause. Not the sign-in lockout's "paused" in `accounts/lockout.html`. |
| **unmet deadline** | `CourseDeadlines` | The resolved deadline of a collection item that is incomplete when read, and the time limit while the course is incomplete. |
| **target kind** | `DeadlineExtension.target_kind` | `collection_item`, `time_limit` or `course` (every unmet deadline and the time limit). |
| **overdue** | `is_overdue` in `freedom_ls/deadlines/resolver.py` | An incomplete item past its due instant. Deadlines are shown and flagged, never enforced. Learner-facing copy says "Deadline" and "Missed deadline", never "Due" or "Overdue". |
| `RecommendedCourse` | `freedom_ls/course_recommendations/models.py` | A course recommended to a learner. Still keyed on `User`, not `Learner` — it is a recommendation, not an enrolment. |
| `is_registered_for_course` | `learner_management/utils.py` | The access check. Every `COURSE_ACCESS_BACKEND` delegates to it. |
| `ensure_learner` | `learner_management/utils.py` | Get-or-create the `Learner` for a `(user, organisation)` pair. Idempotent, and reactivates a deactivated row. The only supported way to make one. |
| `CourseAccessDecision`, `CourseAccessBackend`, `CourseAccessType` | `course_access/backends.py` | The pluggable access layer. Note the `*Decision` suffix — it is the house pattern for a resolver's return value. |

### `Learner` — read this before naming anything nearby

`Learner` is **not** a synonym for `User`, and it is not a profile. It is the join row that says *this
person belongs to this organisation*, and it is the thing enrolment hangs off. A person studying
through two client organisations has **two `Learner` rows and one `User`**.

- **Enrolment is per-`Learner`.** `LearnerCourseRegistration` and `CohortMembership` point at `Learner`. An enrolment with no organisation cannot be represented — that is the
  point of the model.
- **Progress is per-`Learner`, keyed on the granting registration.** `CourseProgress` carries a
  `learner` FK plus exactly one of `learner_registration` / `cohort_registration` — the registration
  that minted the record — and `TopicProgress` / `FormProgress` hang off a `CourseProgress` via
  `course_progress`, not off `Learner` or `User` directly. A learner holding both an individual and a
  cohort registration for one course has two `CourseProgress` records; `course_progress_for`
  (`learner_progress/queries.py`) resolves which one a piece of work lands on, the same way
  `learner_for_course` resolves the registration. Nothing filters `CourseProgress`, `TopicProgress` or
  `FormProgress` by hand outside a short, named list of read paths — go through `course_progress_for`.
- **`is_active=False` means the learner is deactivated in this organisation**, never deleted.
  Nothing cascades: a deactivated learner keeps their registrations, memberships and progress. It is
  filtered explicitly at every call site — there is deliberately no manager that hides deactivated
  rows.
- **Never construct one directly.** Use `ensure_learner`.
- **`learners_visible_to`** (`learner_management/queries.py`) returns `Learner` rows and replaced
  the deleted `users_visible_to`. Don't reintroduce a user-shaped sibling.

---

## Staff — `freedom_ls/learner_management/`

| Term | Defined at | Means |
| --- | --- | --- |
| `StaffMember` | `models.py` | A user who helps run an organisation's learners, whether or not they teach. The counterpart of `Learner` and independent of it: one user may hold both in an organisation. `can()` counts an organisation or cohort role only while the user has an active row. A row may exist with no role. |
| `organisation_staff_viewer` | `role_based_permissions/roles.py` | An organisation-level role. Sees the names on the organisation's staff list and changes nothing. Carries `view_organisation_staff`. |
| `organisation_staff_roles_viewer` | `role_based_permissions/roles.py` | An organisation-level role. Sees the staff list with each person's roles and changes nothing. Carries `view_organisation_staff` and `view_organisation_staff_roles`. |
| `staff_member.added` | `audit_log/actions.py` | A user was made a staff member with no role. Giving a role is `role.assigned`. |
| **visible staff** (coined) | `queries.py` `visible_staff` | For one actor and one organisation, the active staff whose names the actor may see: all of them for a holder of `view_organisation_staff`, otherwise those holding a role on a cohort the actor may give `cohort_viewer` on. A set of `User` rows, since staff are users. |
| **pickable staff** (coined) | `queries.py` `pickable_staff` | The users an actor may pick when adding staff: their visible staff, plus the organisation's active learners for someone who holds `add_staffmember`. Not "candidate", which the messaging policy has taken. |
| `target` (of a role) | `queries.py` `role_target` | Where a staff role is held: `"organisation"` for a role in `ORGANISATION_ROLES`, otherwise `"cohort"`. Distinct from the `target` argument of `assign_role`, which is the object the role is given on. |
| **may edit own roles** (coined) | `role_assignment.py` `_may_act_on_self` | Whether an actor may add or deactivate their own role of a type on a target. It holds exactly when they may assign that role on that target, on an organisation or a cohort in it and never on the site. |

---

## Progress — `freedom_ls/learner_progress/models.py`

| Term | Defined at | Means |
| --- | --- | --- |
| `CourseProgress` | `models.py` | A learner's progress through a course. `verbose_name_plural = "course progress records"`, so **"course progress record" is existing FLS language** — use it. |
| `CourseItemProgress` | `models.py` | The abstract base `TopicProgress` extends. |
| `TopicProgress` | `models.py` | "Topic progress records". One row per placement per record. |
| `CourseFormAttempt` | `models.py` | "Course form attempt". The course's side of one sitting: which record it counts toward, and which placement it was sat at. Many per placement, one per attempt. |
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
| `Organisation` | `organisations/models.py` | A client **inside** a site. A grouping, **not** an isolation boundary — see `docs/product/multi-tenancy-and-isolation.md`. |
| `SiteAwareModel` / `SiteAwareModelBase` / `SiteAwareManager` | `site_aware_models/models.py` | The base model and manager that apply the site filter. |

---

## Messaging: `freedom_ls/messaging_policy/`, `freedom_ls/learner_management/queries.py`

| Term | Defined at | Means |
| --- | --- | --- |
| `MessagingDecision`, `MessagingRefusal`, `MessagingPolicy` | `comms/messaging_policy.py` | Whether one user may message another. `MessagingDecision` follows the `*Decision` suffix, the house pattern for a policy's return value; read `.allowed`, never its truthiness. |
| `Conversation` | `comms/models.py` | The one direct-message exchange between exactly two users on a site, keyed by `pair_key`. Not a group chat and not a notification. |
| `ConversationParticipant` | `comms/models.py` | One user's membership in a `Conversation`, holding their `last_read_at`. |
| `Message` | `comms/models.py` | One text a participant sent in a `Conversation`. `sender` is null once the sender's account is deleted. Distinct from Django's `messages` framework. |
| **inbox** | `comms/messaging.py` `inbox_for` | A user's list of their `Conversation` rows, newest activity first. |
| **thread** | `comms/messaging_views.py` | The page showing one `Conversation`'s messages with its composer. |
| **educator of a learner** (coined) | `learner_management/queries.py` `educators_of` | An active user holding an active grant, through a role granting `VIEW_LEARNER`, that reaches a `Learner` row: a site grant, an organisation grant on the learner's organisation, or a cohort grant on a cohort the learner belongs to. The inverse of `learners_visible_to` without its superuser branch. |
| **colleague** (coined) | `learner_management/queries.py` `colleagues_of` | An active user, other than the given one, holding an organisation- or cohort-scoped role granting `VIEW_LEARNER` in an organisation where the given user holds one too. A site-scoped role makes nobody a colleague. |
| **peer** (coined) | `learner_management/queries.py` `peers_of` | Another user's active `Learner` row in the same organisation that shares a cohort with the given learner, or a course both hold an active registration for (individually or through a cohort). Course peers stay inside the organisation because a course is not owned by one. |
| **candidate** (coined) | `messaging_policy/policy.py` | A relationship that could let one user start a conversation with another, before the settings layers decide whether it is open. A candidate that resolves open allows the start; one that resolves closed is refused with `CLOSED_BY_CONFIGURATION`; no candidate at all is `NO_RELATIONSHIP`. Today every cohort the sender shares with another learner is one. |
| **offered educator** (coined) | `messaging_policy/policy.py` `offered_roles_for` | An educator of a learner whose role is on the offered list (`MESSAGING_OFFERED_EDUCATOR_ROLES`), always narrowed to roles granting `VIEW_LEARNER`. Only an offered educator can resolve open as a candidate; an educator through any other role is still a candidate and resolves closed. |
| **oversight** (coined) | `educator_interface/messaging.py` `oversight_conversations_for` | Read-only access, for holders of `freedom_ls_comms.view_conversation`, to a learner's `Conversation` rows whose other participant is in `educators_of(learner)`. Reached from the learner page only. It never marks a thread read and never goes through participant code paths; each open writes one `conversation.viewed` audit entry. |
| **rollup** (coined) | `base/notification_categories.py` `NotificationCategory.rollup`, `comms/notify.py` `raise_notification` | A notification category that keeps one unread `Notification` per user and target. A further event updates that row (`created_at` then means "last changed") instead of adding one; once the row is read, the next event starts a new one. Keyed by `Notification.rollup_key`. |

---

## HR attributes — `freedom_ls/hr_attributes/models.py`

| Term | Defined at | Means |
| --- | --- | --- |
| `JobTitle`, `Department`, `Location` | `models.py` | A per-organisation list entry. `is_active=False` retires one from every picker; it is never deleted, because a learner may still hold it. |
| `LearnerHRAttributes` | `models.py` | The one-to-one on `Learner` (`learner.hr_attributes`). Holds one `job_title`, `department` and `location`, plus `organisation_start_date`, `job_title_start_date`, `department_start_date` and `location_start_date`. `organisation_start_date` is the hire date. |
| `OrganisationHRSettings` | `models.py` | The one-to-one on `Organisation` (`organisation.hr_settings`). Holds `registration_rules_enabled`, the switch: off by default, and off when no row exists. |

---

## Changes — `freedom_ls/audit_log/actions.py`, `freedom_ls/base/webhook_event_types.py`

A change to the system is named once, as a `noun.verb` code. The audit action and the webhook
event type for the same change are **the same string**: `registration.deactivated` is what the
audit log stores and what a receiver gets as `type`. The full table of codes, with the label each
shows in the UI, is `freedom_ls/audit_log/README.md`; `freedom_ls/audit_log/tests/invariants/test_vocabulary.py`
fails a code that steps outside this section.

The noun is a glossary noun in snake_case: `learner`, `cohort`, `cohort_membership`, `registration`
(a `LearnerCourseRegistration`), `cohort_registration`, `role`, `staff_member` (a `StaffMember`),
`user`, `course`, `bulk_action`, `import`, `conversation`, `api_key` (an `ApiKey`), `deadline` (a deadline extension), `audit_log` (the log the `AuditLogEntry` rows make up). The verb comes from this list and nowhere else:

| Verb | Means | Not |
| --- | --- | --- |
| `created` | A standalone object now exists: `cohort.created`. | |
| `added` | An association now exists: a learner in an organisation (`learner.added`), in a cohort (`cohort_membership.added`), or registered for a course (`registration.added`, `cohort_registration.added`), or a user made a staff member with no role (`staff_member.added`). | `registered`, `enrolled`, `granted` |
| `deactivated` / `reactivated` | An `is_active` flag went False / True, on any model that has one. | `unregistered`, `suspended`, `removed`, `revoked` (for an `is_active` flip), `reregistered` |
| `removed` | An association row was deleted: `cohort_membership.removed`, `role.removed` (a role row deleted with its cohort). | |
| `deleted` | A standalone object was deleted: `cohort.deleted`. | |
| `assigned` | A role was given to a user. Its opposite is `role.deactivated`. | `granted` |
| `viewed` | Something was read, not changed: `conversation.viewed`, a conversation opened under oversight. Only for a read worth auditing. | `opened`, `accessed`, `read` |
| `issued` | An API key was created and its key text shown once: `api_key.issued`. | `generated`, `minted` |
| `revoked` | An API key was ended for good: `api_key.revoked`. One-way and never cleared, unlike `deactivated`, which a `reactivated` undoes. | `deactivated`, `cancelled`, `disabled` |
| `paused` / `resumed` | A `CoursePause` opened / ended on a `CourseProgress`: `course.paused`, `course.resumed`. | `suspended`, `unsuspended`, `held` |
| `extended` | Days were added to a learner's deadlines by a `DeadlineExtension`: `deadline.extended`. | `postponed`, `moved` |
| `exported` | A copy of records left the system as a file: `audit_log.exported`. | `downloaded` |
| `moved`, `renamed`, `resent`, `completed`, `committed`, `signed_up` | As read. `user.signed_up` is an account being created at signup — never `user.registered`, since registration means course access. A verb may carry the thing it acted on when the noun alone would mislead: `learner.setup_email_resent`. | |

The audit log groups codes by the noun's family in the "What" filter. `course.paused`,
`course.resumed` and `deadline.extended` sit in the **Course progress** group.

The words a person reads follow the same verbs:

- **Buttons and dialogs** use the verb: Deactivate, Reactivate, Remove, Delete, Register, Assign.
- **The state** of a row whose `is_active` is False is **Inactive** — in a badge, a filter, a status
  column. Not "Removed", "Suspended" or "Deactivated".
- **A registration that exists** is "Registered" (`registration.added` reads "Learner registered
  for course"); one switched off has its "Learner course registration deactivated". An audit
  label names the noun first (Learner, Cohort, Staff member), since the "What" filter lists it
  under that group.
- A webhook event that is also an audit action carries the audit action's label. A webhook-only
  event (`user.signed_up`, `course.completed`) follows the same `noun.verb` shape.

---

## Words that are already taken

Do not give these a second meaning.

| Word | What it already means | Use instead |
| --- | --- | --- |
| **staff member** | What the educator interface calls a user who holds an organisation or cohort role in an organisation: the Staff section at `/<org>/staff`, "Add staff member", "Staff member deactivated". The row is a `StaffMember` (`learner_management/models.py`), the audit noun is `staff_member` (`staff_member.deactivated`), and the Python names say staff too (`StaffDataTable`, `AddStaffMemberAction`, `STAFF_ROLES`, `staff_of`). One word in the GUI and in the code. | staff, staff member. Not member, `OrganisationMember`, `member.*`: those were the old names and are retired. |
| **grant** | A *role or object permission* — `learner_management/queries.py` ("per-cohort guardian grant", `granted_cohorts`, `assign_object_role`), `context_processors.py`, `docs/product/learner-tracking.md` ("their access grants"). | For course access: **registration**. (The verb is fine: "the registration that granted access".) |
| **item** | Ambiguous already — `Course.items` are `ContentCollectionItem` rows, `viewable_items()` are children, `content_item` is the resolved `Topic`/`Form`. | **collection item** for the row, **child** for the object. |
| **link** | An `<a href>` in ~280 template and view usages. | Fine as a verb ("links a collection to a child"); not as a noun for a model or field. |
| **slot** | `Course.accent_slot`, palette slots, cotton template slots. | Something else. |
| **course item** | Positional content in a course — `view_course_item`, `docs/product/educator-interface.md`. Today it means the resolved `Topic`/`Form`. | Only reuse it deliberately, and say so. |
| **collection** | `ContentCollectionItem.collection` only. | Keep it for that; don't widen it. |
| **is_active** | Several different things across several models: a learner active in the organisation (`Learner`), a registration in force (`LearnerCourseRegistration`, `CohortCourseRegistration`), an active cohort (`Cohort`), a staff member active in the organisation (`StaffMember`), an account that cannot sign in (`User`), a role assignment in force (`SiteRoleAssignment`, `ObjectRoleAssignment`), and a list entry retired from the pickers (`JobTitle`, `Department`, `Location`). | Fine to reuse — it is the house flag name. But a sentence naming two of them must name the model. Setting it to False is **deactivating**; setting it back is **reactivating**; the state is **Inactive** — in UI copy, audit log labels, webhook event types, identifiers and docs alike (see the Changes section above). Not "unregister", "suspend", "remove" or "revoke" for an `is_active` flip ("revoke" is kept for ending an `ApiKey`, `api_key.revoked`): those either name a different action or invent a new one. "Remove" and "delete" are kept for rows that are actually deleted, such as a `CohortMembership`. The one exception is the list entries, which are **retired**. |
| **registered**, **registration** | Course access: a `LearnerCourseRegistration` or `CohortCourseRegistration`. | For an account being created: **signup** (`SiteSignupPolicy`, `user.signed_up`). |
| **removed** | A row that was actually deleted (`cohort_membership.removed`, `role.removed`). One copy exception: the **Remove from cohort** button on a person's cohort role deactivates the role (`role.deactivated`), and `RemoveFromCohortBulkAction` keeps the label for its real deletion of a `CohortMembership`. | For an `is_active` flip: **deactivated**; for the state: **inactive**. |
| **learner** | `Learner`, the `(user, organisation)` association row — and also the everyday English word for the person. | In prose either is fine. As an identifier, `learner` means the model; write `learner.user` / `learner__user` when you mean the account. |
| **role**, bare **title** | Reserved, not in use. `role` is a permission role (`assign_object_role`), and a bare `title` is a content title. | `JobTitle` / `job_title` for what a learner does at work. |
| **start date** | `organisation_start_date` is the hire date: when the learner started at the organisation, not at a course. | For a course, `started_at` on `CourseProgress`. |
| **suspend** | Retired. Pausing a learner's course is a `CoursePause`; the verbs are `paused` and `resumed`. | pause, `CoursePause` |

---

## Prose vs. code

`.claude/skills/brand-guidelines/voice.md` §Terminology holds the **copy-scoped** Use/Not table:
learners not students, content not curriculum, extend not customise, builders not administrators,
learning system not LMS, foundation not platform.

**The word is *learner*.** That is settled, in prose and in code alike.

The codebase has caught up. `learner-terminology-rename` moved the three apps to `learner_management`,
`learner_progress` and `learner_interface`, renamed their app labels, and reset their migration history to a single `0001_initial` each. No `student_*` namespace is left to match.

- **Never introduce a `student_*` name** (app, module, class, field, function, template, URL name or
  test). Nothing is left for it to be consistent with.
- **A `student` you find in the tree is one of three things**, none of them a naming convention to
  follow: another product's word in research prose (Open edX's `StudentModule`, SCORM's), a stale
  `__pycache__` directory from before the rename, or a genuine miss — fix the last one.
- **`user` is not the same question.** Where a model's field genuinely is `user`
  (`FormProgress.user`, `Learner.user`, `RecommendedCourse.user`), that is Django's own noun for an
  account, not the old word for a learner. Leave it alone — renaming it to `learner` would be wrong,
  because `Learner` is a different thing.
- **But do check which one a model *should* key on.** Enrolment moved from `User` to `Learner`
  (`unique_user_course_registration` is gone; the constraint is now
  `unique_learner_course_registration`), and `CourseProgress` followed, keying on `learner` rather than
  `user`. `FormProgress` has not moved yet — it still keys on `user` directly, since a form can be sat
  outside a course. A new model keying on `user` should be able to say why.

---

## Where else to look

- `freedom_ls/*/models.py` — the canonical nouns. Model class names and field names are a document's
  nouns, and the vocabulary of last resort.
- `docs/product/README.md` — the index, and one-paragraph definitions of every concept.
  `docs/product/learner-tracking.md` is the progress vocabulary; `learner-experience.md` the player's.
- `freedom_ls/audit_log/README.md` — every audit action code with its label, target and details,
  and which of them are also webhook event types.
- `docs/app_structure.md` — the canonical app names and the authoritative dependency graph.
- `claude_plugins/fls-content/skills/content-types/SKILL.md` — the author-facing `content_type` values.
- `freedom_ls/content_base/schema.py` — `ContentType` as a `StrEnum`.
