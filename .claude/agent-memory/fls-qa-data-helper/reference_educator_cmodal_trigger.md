---
name: educator-cmodal-trigger
description: How to give a QA educator a reachable c-modal trigger in the educator interface (delete-confirmation / modal-form flows)
metadata:
  type: reference
---

The educator interface renders `<c-modal>` via two `panel_framework` action partials:

- `delete_confirmation.html` — rendered by `DeleteAction` (in `freedom_ls/panel_framework/actions.py`). On the **cohort detail page** (`/educator/cohorts/<uuid>`), `CohortInstanceView.get_actions()` returns a `DeleteAction`. Trigger = red **"Delete"** button at top of page. Opens a `c-modal` titled "Confirm Deletion".
- `modal_form.html` — rendered by `CreateInstanceAction`/`EditAction`. The **cohort list page** (`/educator/cohorts`) has `CreateCohortAction` → **"Create Cohort"** button opening a `c-modal`.

Actions only render if `action.has_permission(request, instance)` passes (gated in `panel_framework/views.py` `_render_instance_actions`). Perm checks:

- `DeleteAction.has_permission` → object-level `request.user.has_perm("freedom_ls_student_management.delete_cohort", cohort)`. Grant with `assign_perm("delete_cohort", educator, cohort)` (guardian).
- `CreateInstanceAction.has_permission` → model-level `add_cohort` (no instance).
- Cohort also needs object-level `view_cohort` for it to appear in the list and for the detail page to be reachable (`CohortDataTable` filters via `get_objects_for_user(user, "view_cohort", ...)`).

Important: `Cohort._meta.app_label == "freedom_ls_student_management"` (set via `apps.py` `label =`), NOT `student_management`. The full perm string is `freedom_ls_student_management.delete_cohort`.

To verify a modal renders for an educator: `Client.login()` fails under django-axes ("AxesBackend requires a request"). Use `client.force_login(user)` instead, then GET the page and assert `"Confirm Deletion"` / `"__actions/delete"` are in the body.

Command `qa_create_educator_modal_target <site_name>` (in qa_helpers) builds the minimal setup: login-ready educator (`qa_educator@example.com`, password == email, verified+primary EmailAddress), a `QA Modal Cohort` with view+delete perms, one student member, and a course registration (for the modal's cascade summary). Idempotent.
