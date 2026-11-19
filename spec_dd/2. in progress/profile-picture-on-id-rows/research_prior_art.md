# Research: prior art (profile-picture-on-id-rows)

## Here

### Why id-only rows were left out of spec 1
`spec_dd/3. done/2026-11-15_09:21_learner-public-profile-1-profile-picture/1. spec.md` (Scope, Out) kept initials on "surfaces that render from ids rather than loaded `User`s": dashboard and cohort attention rows (cached report data in `reports/screen_cache.py`), audit log who and target (`audit_person.html`), and the cohort report on screen and PDF. It parked them in this idea. The cause was cost and shape, not a product objection: callers pass ids and names, so each needs a `User` or a precomputed URL (`research_codebase.md` there, lines 35-47: "audit log passes only `user_pk`; cohort report passes a learner id; attention row passes only `user_id`").

### Decisions from spec 1 that bind this one
- Signed URLs are minted at render time from `User.profile_picture_url`. They are never stored in a model, a report snapshot or `screen_cache`, and not cached server-side. Production `CACHES` is the database cache, so a per-avatar lookup would add a query per row. The browser re-downloads avatars on every load. This matches the idea's "settled" list.
- The panel framework stays FLS-free: `panel-avatar-chip` and `panel-person-link` take a plain `picture_url` string (bound, `:picture_url="user.profile_picture_url"`), and FLS templates resolve it. An empty value shows initials.
- No avatar code checks `is_active`: deactivated users keep their picture.
- Missing file renders initials: the URL helper is guarded, there is no `storage.exists()` per row, and `base/js/profile-picture-fallback.js` removes an `<img data-profile-picture>` that fails to load. A new surface must use the same `data-profile-picture` hook.
- The deleted-user neutral circle (`user` icon) in `audit_person.html` and `participant_avatar.html` is a separate branch with no picture. Keep it.
- Spec 1's research flagged that listing many avatars means one signature per row. Signing is local CPU, with no network call, but not free (50 rows is 50 signatures).
- `qa_report.md` / `3. frontend_qa.md` in spec 1: tests 4.1-4.3 confirmed no `<img>` on the dashboard, audit log or reports, but only weakly. No such row named a user with a picture (the QA learner had no registrations), and unit tests carry the "stays on initials" claim. The new spec's QA needs seeded data where an attention-row learner and an audit actor/target have pictures. Those unit tests that assert initials will need updating.
- Spec 1 hit a pre-existing educator-shell HTMX navigation race under load (not picture related). Don't mistake it for a regression.

### Cached data shape (`freedom_ls/reports/`)
- Cached rows (`report_data.py` lines 125-137) carry `learner_id: UUID` and `full_name: str`.
- **`learner_id` is not necessarily a user pk.** In `reports/indexes.py:207` the roster is `{m.learner_id: m.learner.user ...}` over memberships, so `learner_id` is the key of the learner-profile row, and the `User` is reached through `learner.user`. `User` pks may also be UUIDs. Check this before writing "one `User` query" (idea open question 2). The lookup may need `User.objects.filter(learner__pk__in=ids)`, or the cached data may need a `user_id`.
- `screen_cache._trim_report` / `_active_member_ids` already filter cached rows by `learner_id` on every read, and the lookup of ids per read is already a precedent. Rows hold no URLs and none should be added. The PDF uses the same data, so the on-screen resolution must happen in the view or template layer, never in `gather`.
- Per spec `2026-10-24_08:10_educator-interface-10-reporting-dashboards` the dashboard cache is a short per-cohort cache, not event-invalidated. A deactivated or removed learner is dropped on read. A picture change therefore shows at once if the picture is resolved at render time, and not after cache TTL. This is a point in favour of render-time resolution.

### Audit log
- Spec `2026-11-08_09:13_design_educator_interface_audit_log` built `audit_person.html` with the stored name label (`label`) plus a live `user_pk`. The stored name is the historical name, and the live pk is used to link. The picture must follow the live user, not the stored label. A deleted user has no pk and shows the neutral circle. `_attach_target_users` produces `values_list` data, so it needs pks batched into one `User` query per page.

### Roadmap
`spec_dd/1. next/roadmap.md` lists this as in progress, High priority, under "Learner public profiles". `learner-public-profile-5-index` reuses the picture with initials fallback and has the same many-rows-per-page concern.

## Elsewhere: caching signed URLs next to cached data
(Summarised from spec 1's `research_best_practices.md` line 82 and `research_known_complaints.md` items 7-8, plus common practice. No new web search was done.)
- A pre-signed URL stored in cached data, a cached fragment or a cached API response expires before the cache entry, which gives broken images. This is a widely listed S3 pitfall. Cache the object key or the user id and sign at render.
- Per-render signing changes the URL each time, so the browser and CDN cannot cache the image. The known mitigations are a stable same-origin view with `Cache-Control`, or time-bucketed (rounded) expiry so URLs repeat within a window. Spec 1 accepted the re-download cost and chose a small 400x400 WebP, so this spec should not reopen it.
- A page left open past the expiry shows broken images on lazy load. The `onerror` initials fallback hides this. HTMX partial swaps re-sign on each render.
- Avoid an N+1: resolve ids to users with one batched `User` query (`filter(pk__in=...)`, with `only()` of the name and picture fields) and pass a dict into the template. Don't sign in a template tag that queries per row.

status: ok
