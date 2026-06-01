# Research: Admin / Reviewer Side of Course Applications

Companion to `0. idea.md`. Focused on the workflow that begins after an applicant submits: review, decision, and the manual hand-off to the existing cohort + course-registration flow.

Three constraints from the idea file shape everything:
1. Different courses can have different application requirements.
2. Approval is **not** auto-enrolment — admins still take off-platform steps before manually adding the learner to a cohort.
3. Subscriptions spec already adopts [`django-fsm-2`](https://github.com/django-commons/django-fsm-2); use the same library here.

---

## 1. Application states / FSM design

### 1.1 Survey

Common admissions states across the industry:
- **Submitted** ([USF](https://admissions.usf.edu/blog/what-does-each-college-application-status-mean), [GSU](https://admissions.gsu.edu/kb/i-do-not-understand-my-application-status-what-does-it-mean/))
- **Awaiting Materials** ([GSU](https://admissions.gsu.edu/kb/i-do-not-understand-my-application-status-what-does-it-mean/))
- **Under Review / Processing Review** ([NCSU](https://grad.ncsu.edu/faculty-and-staff/slate/application-status/))
- **Awaiting Decision / Awaiting Confirmation** ([Quora discussion](https://www.quora.com/Why-did-my-graduate-school-application-go-from-awaiting-decision-to-awaiting-confirmation-Its-been-a-few-days-and-I-m-not-sure-if-its-a-good-sign-or-bad-sign))
- **Accepted / Denied / Waitlisted** ([Command Education](https://www.commandeducation.com/resource/accepted-waitlisted-rejected/), [Fastweb](https://www.fastweb.com/college-search/articles/college-rejection-letters-and-wait-lists-moving-forward))
- Withdrawn, Expired

### 1.2 Recommended V1 state set

`draft`, `submitted`, `under_review`, `changes_requested`, `approved`, `rejected`, `withdrawn`. Optional system state `expired`.

Out of V1 (flag in spec): `waitlisted`, multi-stage review, score rubrics, reviewer assignment.

### 1.3 Transition matrix

| Transition | Actor | From → To | Notes |
|---|---|---|---|
| `submit` | Applicant | draft → submitted | Validates required answers. |
| `withdraw` | Applicant | draft / submitted / changes_requested → withdrawn | |
| `pick_up` | Reviewer | submitted → under_review | Optional but improves queue UX. |
| `request_changes` | Reviewer | under_review → changes_requested | **Requires** a feedback message. |
| `resubmit` | Applicant | changes_requested → submitted | Re-runs validation. |
| `approve` | Reviewer | under_review → approved | Optional internal note. |
| `reject` | Reviewer | under_review → rejected | Optional reason. |
| `expire` | System cron | changes_requested → expired | Out-of-V1 unless cheap. |

`django-fsm-2` supports `source=[...]` lists for the `withdraw` collapse cleanly.

### 1.4 Approved ≠ enrolled

`approved` is terminal on the Application. The application screen, after approval, should expose an "Enrol this learner" deep-link into the existing `educator_interface` cohort + registration flow with the user pre-filled — keeps the manual hand-off frictionless without binding the FSM to enrolment.

---

## 2. Reviewer UX patterns

### 2.1 Queue/list view

Convergent pattern across [TargetX](https://www.targetx.com/solutions/increase-enrollment-with-recruitment-suite/application-review/), [Salesforce Education Cloud](https://trailhead.salesforce.com/content/learn/modules/recruitment-and-admissions-with-education-cloud/manage-application-reviews), [Kissflow](https://kissflow.com/solutions/education/student-application-review-workflow/), [Liaison WebAdMIT](https://help.liaisonedu.com/WebAdMIT/Reviewing_Applicants/Application_Review_Workflow):
- Top-of-page state-count metrics
- Filterable table (state, course, date, reviewer)
- Search by applicant name/email
- Default sort: oldest-submitted first (FIFO, keeps SLA honest)
- Row click → full review screen, not a modal

[Kissflow](https://kissflow.com/solutions/education/student-application-review-workflow/) and [TargetX](https://www.targetx.com/solutions/increase-enrollment-with-recruitment-suite/application-review/) both call out manual reviewer **assignment** as the standard bottleneck.

### 2.2 Single-application review screen

[Liaison TargetX docs](https://help.liaisonedu.com/TargetX_Help_Center/TargetX_Application_Review_Tool/Getting_Started/Application_Review_Tool):
- Main area: applicant answers + inline document previews
- Sticky right sidebar: decision actions, internal notes, history
- State-aware buttons (disabled when not applicable)
- Confirmation modal for `request_changes` and `reject` (these need a message)

### 2.3 Bulk vs single review

Bulk approve/reject is an antipattern (cited in [Reltio review-data-changes](https://docs.reltio.com/en/objectives/manage-workflow-tasks/workflow-management-at-a-glance/workflow-management-reference/workflow-use-cases/reviewing-data-changes)). **No bulk decision actions in V1.** Bulk "mark under review" or CSV export are safe but not needed for V1.

### 2.4 Multiple reviewers

Out of V1, flag in spec. Two-reviewer agreement, score averaging, escalation patterns covered by [TargetX Application Review Types](https://help.liaisonedu.com/TargetX_Help_Center/TargetX_Application_Review_Tool/Getting_Started/Application_Review_Tool). For V1, FSM guards naturally serialise concurrent reviewer actions (second wins / loses cleanly).

### 2.5 Internal notes

Separate `ApplicationNote` model (`application`, `author`, `body`, `created_at`). Staff-only. Must be structurally distinct from the applicant-facing feedback message attached to `request_changes` — mixing them is the easiest way to leak internal commentary.

### 2.6 Audit trail

Two options:
1. [`django-simple-history`](https://medium.com/@baselshisir/effortless-audit-trails-in-django-with-django-simple-history-166d4ccdfed8) — full snapshots, heavy.
2. Custom `ApplicationStateTransition` model — `from_state`, `to_state`, `actor`, `at`, `message`. Lighter, sufficient for "who decided what and when" — see also [python-statemachine integrations](https://python-statemachine.readthedocs.io/en/latest/integrations.html) and the [Django AuditTrail wiki](https://code.djangoproject.com/wiki/AuditTrail).

**Recommendation: option 2.**

---

## 3. Communication with the applicant

### 3.1 Notifications

Email is **out of scope for V1** (consistent with subscriptions spec). Fire a Django `application_state_changed` signal on every transition so an email backend can be added later without touching the FSM.

### 3.2 In-app status page

Per [USF](https://admissions.usf.edu/blog/what-does-each-college-application-status-mean) and [GSU](https://admissions.gsu.edu/kb/i-do-not-understand-my-application-status-what-does-it-mean/):
- Plain-language current state
- Checklist of what's missing when in `changes_requested` (give the list, not just the label)
- Edit/Resubmit button when in `changes_requested` or `draft`
- Final decision text + applicant-visible message for `approved` / `rejected`

### 3.3 Feedback on `request_changes`

Two distinct fields, never merged:
- **Applicant-visible message** — required, shown on status page.
- **Internal note** — optional, staff-only.

Heed the misleading-status problem from the [GitHub PR review UX thread](https://github.com/orgs/community/discussions/17875): when applicant resubmits, the reviewer view must clearly mark "resubmitted since your last review" — show resubmit timestamp prominently, link back to the previous reviewer message in the transition log.

---

## 4. Permissions

### 4.1 Reviewers

Codebase already uses `django-guardian` (see `freedom_ls/educator_interface/views.py` — `get_objects_for_user(request.user, "view_cohort", klass=Cohort)`). Define:
- `view_application`
- `change_application` (for state-changing transitions)

### 4.2 Site isolation

Application model **must** inherit from `SiteAwareModel` (`freedom_ls/site_aware_models/models.py`). The existing `SiteAwareManager` then guarantees Site A reviewers never see Site B applications. The `fls:multi-tenant` skill documents this.

### 4.3 Where the review UI lives

Three candidates:
1. Django admin (Unfold) — quick but wrong audience
2. **`educator_interface`** (recommended) — already houses cohort/student/registration UI, already uses `guardian` per-cohort scoping, already styled for non-admin staff
3. New dedicated app — premature

**Recommendation: `educator_interface`.** Reviewers are educators / programme managers, not Django superusers. The post-approval enrol step lives there already. Django admin should still expose the model (read-mostly, transitions hidden via `custom={"admin": False}`) for support/debugging.

---

## 5. `django-fsm-2` patterns

### 5.1 Transition decorator essentials

From [django-fsm-2 README](https://github.com/django-commons/django-fsm-2/blob/main/README.md), [Viewflow FSM options](https://docs.viewflow.io/fsm/options.html), [django-fsm transitions reference](https://tessl.io/registry/tessl/pypi-django-fsm/2.8.0/files/docs/transitions.md):

```python
from django_fsm import FSMField, transition

class CourseApplication(SiteAwareModel):
    state = FSMField(default="draft", protected=True)

    @transition(
        field=state,
        source="under_review",
        target="approved",
        permission=lambda inst, user: user.has_perm("applications.approve_application", inst),
    )
    def approve(self, by_user, internal_note=""): ...

    @transition(
        field=state,
        source="under_review",
        target="changes_requested",
        permission="applications.change_application",
        conditions=[lambda inst: inst.has_pending_feedback_message()],
    )
    def request_changes(self, by_user, message): ...
```

Key params: `field`, `source` (string / list / `"*"` / `"+"`), `target`, `conditions` (callables on instance), `permission` (string OR callable), `custom` (e.g. `{"admin": True, "label": "..."}`). `protected=True` blocks direct field assignment — strongly recommended.

### 5.2 Permission checks in views/templates

```python
from django_fsm import has_transition_perm
if has_transition_perm(application.approve, request.user):
    ...

for t in application.get_available_user_state_transitions(request.user):
    ...  # t.name, t.target, t.custom
```

Drive button rendering off `get_available_user_<field>_transitions()` so templates never hardcode state→button mappings.

### 5.3 Admin integration

Use [`django-fsm-admin`](https://github.com/gadventures/django-fsm-admin) (works with `django-fsm-2`). Set `FSM_ADMIN_FORCE_PERMIT = True` so transitions are opt-in via `custom={"admin": True}` — prevents accidentally exposing new transitions to admin users.

### 5.4 Existing FSM usage in FLS

Verified via grep: **no current `django-fsm` / `django-fsm-2` / `FSMField` usage** anywhere in the codebase. The applications spec and the subscriptions spec will introduce the dependency together — they should agree on a single `uv add django-fsm-2` and a consistent transition-log pattern (preferably the `StateTransition` model from §2.6, but don't pre-extract a shared mixin until both apps actually exist).

### 5.5 Alternative considered

[Stop Over-Engineering Django State Machines (Kubeblogs, 2026)](https://www.kubeblogs.com/stop-over-engineering-django-state-machines-use-this-instead-of-django-fsm/) argues a hand-rolled state field + dict suffices for simple cases. Worth knowing, but consistency with the subscriptions spec wins. Stick with `django-fsm-2`.

---

## 6. Anti-patterns

| Anti-pattern | Mitigation for FLS |
|---|---|
| Slow document loading | Inline preview, lazy load; signed URLs only on actual click |
| Lost context navigating away | Side-panel/iframe document viewer; preserve scroll |
| No cross-application comparison | Out of V1, flag |
| Unclear what changed on resubmit | Prominent "resubmitted at X" + transition log entry "applicant resubmitted in response to your changes request of …" |
| Misleading status after resubmit ([GitHub PR thread](https://github.com/orgs/community/discussions/17875)) | `resubmit` transition must move state cleanly back to `submitted`; no UI residue of `changes_requested` |
| Bulk decision buttons | Don't ship bulk approve/reject in V1 |
| Mixed internal/applicant comments | Two separate fields with distinct UI labelling |
| No SLA visibility | Default queue sort oldest-first; show "submitted N days ago" |

---

## 7. Recommendations for FLS

**State list (V1):** `draft`, `submitted`, `under_review`, `changes_requested`, `approved`, `rejected`, `withdrawn`. Out-of-V1: `waitlisted`, `expired`, multi-stage review, score rubrics, multi-reviewer, bulk actions.

**FSM library:** `django-fsm-2` (matches subscriptions spec). Use `FSMField(protected=True)`, callable `permission=` integrated with `django-guardian`, `get_available_user_<field>_transitions()` in templates, `django-fsm-admin` with `FSM_ADMIN_FORCE_PERMIT = True`.

**Where the review UI lives:** `educator_interface`. Add: queue panel, single-application review screen (main = applicant data + docs; sticky sidebar = decision actions + transition log + internal notes), "Enrol approved learner" deep-link into existing cohort + registration flow. Keep Django admin (Unfold) for read-mostly support access; hide most transitions there.

**Permission scope:** `view_application` and `change_application` (optionally `decide_application` for approve/reject) as object-level perms via `django-guardian`, granted per course or per site. Site isolation comes free from inheriting `SiteAwareModel`. State-changing transitions use `permission=` callables that delegate to `user.has_perm("...", instance)`.

**Supporting models:** `Application` (with FSMField state, applicant, course, submitted_at, decided_at, JSON answers); `ApplicationNote` (internal); `ApplicationStateTransition` (audit + applicant-visible message source). Fire `application_state_changed` signal on every transition.

**Don't build in V1:** email notifications, bulk decisions, multi-reviewer / inter-rater workflows, field-level diff between application versions, cross-application comparison, auto-expire (unless cheap), score rubrics.

---

## Key codebase findings

- `freedom_ls/site_aware_models/models.py` — `SiteAwareModel` + `SiteAwareManager` for automatic site filtering
- `freedom_ls/educator_interface/views.py` — already uses `guardian.shortcuts.get_objects_for_user` for cohort scoping; uses a panel framework (`InstanceView`, `DataTablePanel`, `Tab`) that the application review screen could plug into
- `freedom_ls/student_management/models.py` — `Cohort`, `CohortMembership`, `CohortCourseRegistration`, `UserCourseRegistration` are the existing enrolment primitives the post-approval flow will hit
- **No existing `django-fsm` usage** — adding it is greenfield
