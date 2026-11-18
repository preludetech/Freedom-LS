Archived from the spec roadmap on 2026-11-18, when the last of its specs finished.

## Lead monitoring API

A read-only REST API that marketing scripts use to track leads. Parent: `apis-for-lead-monitoring`.


**Notes**
- It follows the existing API conventions: DRF, API-key auth bound to a site, cursor pagination on `(updated_at, id)`, `updated_since`. It adds its endpoint to the API docs page.
