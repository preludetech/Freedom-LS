# Profile picture on id-only rows

Follows `learner-public-profile-1-profile-picture`, which gives every `User` a profile picture and
shows it in place of the initials avatar on surfaces that already hold a loaded `User`. Read that
spec first (`spec_dd/*/*learner-public-profile-1-profile-picture/1. spec.md`).

## What

Show the profile picture on the educator surfaces that still show initials because they render from
ids rather than `User` rows:

- Dashboard and cohort attention rows (`educator_interface/panels/dashboard_region.html`,
  `panels/cohort_needs_attention_region.html`, through `panel-attention-row.html`). Their rows come
  from cached report data (`reports/screen_cache.py`) carrying only `learner_id` and `full_name`.
- Audit log who and target (`educator_interface/partials/audit_person.html`). The target comes from
  `_attach_target_users` in `educator_interface/views.py` as `values_list` data; the actor from
  `actor_id`.
- Possibly the on-screen cohort report (`panels/cohort_report_body_region.html`), never its PDF.

## What is settled

- Signed URLs are minted at render time and never stored in cached report data or a snapshot; a URL
  in the cache would expire.
- No row costs a query: each render resolves its ids with one `User` query.

## Open until the spec

- Whether the on-screen cohort report is in.
- Whether `learner_id` on these rows is always a user pk.
- The cost of the extra query per render on the dashboard.
