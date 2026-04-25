# Structure concerns — Lightweight xAPI Event Tracking

Raised by `/plan_structure_review` against the previous version of `2. plan.md`. **Resolved.**

## Original concern

The first draft of the plan introduced **six new runtime cross-app edges** by putting all tracker logic inside `experience_api`:

**Outgoing from `experience_api`:**
1. `experience_api --> accounts`
2. `experience_api --> content_engine`
3. `experience_api --> role_based_permissions`
4. `experience_api --> student_management`

**Incoming to `experience_api`:**
5. `student_interface --> experience_api`
6. `student_progress --> experience_api`

## Resolution — restructure for portability

The spec and plan were rewritten to move domain-specific logic out of `experience_api` so the app can be copied into other Django projects as generic event-logging infrastructure.

**What changed:**

- `experience_api` now depends only on `accounts` (for `User`) and `site_aware_models` (for `SiteAwareModel` and `_thread_locals`).
- Pydantic schemas, snapshot helpers, and per-event-type `track_*` wrappers live in the **owning domain app's** `xapi_events.py` module (`student_interface/xapi_events.py`, `student_progress/xapi_events.py`). Each domain app registers its schemas at `apps.py.ready()` via `experience_api.registry.register_event_type(...)`.
- Relationship-walking helpers live next to the models they walk: `content_engine/xapi_snapshots.py` and `student_management/xapi_snapshots.py`. They do not import from `experience_api`.
- The erasure "still-has-history" check is pluggable via `EXPERIENCE_API_ERASURE_BLOCKERS` (list of settings-paths). The FLS-specific blocker that checks `UserCourseRegistration` lives in `student_management/xapi_erasure.py`.
- Schemas are **not** catalogued in a cross-cutting markdown file. Each owning app's `xapi_events.py` is the source of truth for its own event types; the per-event field detail (required/optional/snapshot conventions) is captured in `1. spec.md` §"Initial event schemas (field detail)" as the authoritative description.

**New runtime edges** (four, down from six, and `experience_api` is generic):

- `experience_api --> accounts`
- `experience_api --> site_aware_models`
- `student_interface --> experience_api`
- `student_progress --> experience_api`

**Removed edge** (old app deleted):

- `xapi_learning_record_store --> site_aware_models`

**Enforced by a test:** `freedom_ls/experience_api/tests/test_import_boundaries.py` greps the `experience_api` tree for any `from freedom_ls.<app>` / `import freedom_ls.<app>` where `<app>` is not `accounts` or `site_aware_models` and asserts zero matches. This is the durable guard against a portability regression.

## Verification checklist before implementation

- [x] `experience_api` imports only `accounts` and `site_aware_models`.
- [x] Domain apps register their schemas via `register_event_type(...)` in their own `xapi_events.py`, imported from `apps.ready()`.
- [x] Shared snapshot helpers live in `content_engine/xapi_snapshots.py` and `student_management/xapi_snapshots.py`, with no imports from `experience_api`.
- [x] Erasure blocker wired via a settings-path, not an import.
- [x] Per-event field detail preserved in `1. spec.md` §"Initial event schemas (field detail)".
- [x] `docs/app_structure.md` to be regenerated via `/app_map` after implementation lands.
