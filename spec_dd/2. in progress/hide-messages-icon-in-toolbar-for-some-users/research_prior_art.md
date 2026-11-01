# Research: prior art for hiding the Messages button for some learners

## Summary

- The header Messages button today is gated by one global setting only: `MESSAGING_ENABLED`. It is not gated by who the signed-in user may message.
- The earlier `user-communication` effort anticipated exactly this case (a free-course learner who can message no one) but only handled it inside the messages page (empty states), not the header button. The header button was deliberately specified as "the one signal for new messages, for everyone".
- Elsewhere (Moodle), messaging has a site-wide switch that removes the icon, and no per-user or per-role mechanism to hide it. Moodle's history shows leftover entry points are the common bug when hiding is done piecemeal.

## Here

### What the code does now
- `freedom_ls/comms/config.py` line 30: `MESSAGING_ENABLED` setting, default `False`. `config/settings_base.py:520` False; `config/settings_dev.py:71` True.
- `freedom_ls/comms/templatetags/comms_tags.py` `messages_button()` (lines 45-51): returns `{"enabled": False}` only when `MESSAGING_ENABLED` is off. It takes no request or user, and the template tag intentionally does no query so no page pays for the unread count (the badge loads itself).
- `freedom_ls/educator_interface/views.py:826`: the educator Messages section is gated by `MESSAGING_ENABLED and super().has_permission(request)`, so the educator side already combines the global flag with a per-user check.
- `freedom_ls/comms/views.py:77`: messaging pages 404 when the flag is off.
- Tests toggle the flag via `settings.MESSAGING_ENABLED` (e.g. `freedom_ls/comms/tests/test_bell_tag.py` lines 112-195 cover the on/off states of the tag).

### What was decided earlier, and why
- `docs/product/messaging.md`: "Messaging is off by default"; "The header Messages button is the one signal for new messages, for everyone, educators included"; while off, "no messaging button, tab or box is shown and the messaging pages do not exist". "A user with nobody to message is not offered anyone" (inside the page, not the header).
- `docs/product/configuration-and-extension.md` (Messaging Policy section, line 80): who may message whom is a swappable messaging policy; out of the box learners may message educators, and peer messaging is closed.
- `spec_dd/1. next/roadmap.md` (user-communication effort, decision 3, ~line 211): "Messaging permissions are layered and closed by default... configured at site, organisation, cohort or course registration, and learner level, the most specific level winning. A free course sign-up must not let a learner message staff or other learners; a premium arrangement may let a learner message their cohort admin. The policy is a swappable class, like `COURSE_ACCESS_BACKEND`." This is the direct precedent: the free-course learner was foreseen, but the consequence for the header button was not drawn.
- `spec_dd/1. next/user-communication/design_brief.md` lines 22-25: "A learner on a free course may be able to message no one... The design must never offer a recipient the user cannot reach, and must read naturally when the list of permitted recipients is empty." Related design screens (`design.md` rows 5 and 7): learner inbox states "empty and messaging not available" and recipient picker "no one to message". So the chosen answer then was an empty-state page, reachable via a visible button.
- `spec_dd/1. next/user-communication/research_comms_ux_pitfalls.md` line 51: best practice is a persistent unread badge on a dedicated icon visible on every page, never buried. That argument favours always showing the icon for users who can message, and is silent on users who cannot.
- `spec_dd/1. next/user-communication/research_messaging_relationships_and_surfaces.md`: maps the relationships (cohort, course registration, organisation, roles) and the `AppSettings` config pattern (`freedom_ls/base/app_settings.py`, `course_access/config.py`, `learner_management/config.py` `DEADLINES_ACTIVE` boolean flag). Useful for any new setting.
- `spec_dd/1. next/user-communication/research_comms_patterns.md` line ~537: proposed a settings-driven `FLS_COMMS_CONFIG` controlling which modalities are enabled (older research, partly superseded by the policy class).
- `spec_dd/1. next/user-communication-6-moderation/idea.md` and `user-communication-help-desk/idea.md`: later comms specs that add more surfaces; any visibility rule should be consistent with them.

### Related earlier bug (same flag)
- `spec_dd/2. in progress/downstream_bugs_oct_29/sidebar-sections-test-assumes-messaging-is-enabled/idea.md`: a downstream project leaving messaging at default failed a sidebar test because the educator "Messages" sidebar entry renders only when `MESSAGING_ENABLED` is true. Lesson: every visibility rule needs tests for both states, and tests must set the flag explicitly. `freedom_ls/educator_interface/tests/test_sidebar.py:216` now parametrizes both.

### Not found
- No earlier spec, TODO or `@claude` comment about per-user hiding of the header Messages button, per-site messaging toggles beyond the global flag, or self-registration/free-course specific messaging visibility (searched `spec_dd/` and `docs/`). The only mention of "free course" and messaging is the design brief and roadmap decision 3 above.

## Elsewhere

- Moodle: "Enable messaging system" (Site administration > Advanced features) removes the "Toggle messaging drawer" icon from the user menu site-wide. A separate "Allow site-wide messaging" limits who can be found (users who share no course) but does not hide the icon. No per-user or per-role mechanism to hide the icon was found.
- Moodle leftover entry points when messaging is disabled: MDL-28186 (messaging preferences page still reachable by URL), MDL-52338 (course overview block still linked to messaging), MDL-79913 (messaging icons still showing in grade reports; fixed in 4.2.7 and 4.3.4). Lesson: when hiding, hide every entry point, and make the underlying pages refuse too (FLS already 404s the pages when the flag is off).
- MDL-82539 (unresolved): proposal to turn the messaging drawer into a popover.
- Canvas: not searched in depth; no result found within this brief research. Treat as unknown.

References:
- https://tracker-old.moodle.org/browse/MDL-28186
- https://tracker-old.moodle.org/browse/MDL-52338
- https://tracker-old.moodle.org/browse/MDL-79913
- https://tracker-old.moodle.org/browse/MDL-82539
- https://tracker-old.moodle.org/browse/MDL-64495
- https://tracker-old.moodle.org/browse/MDL-66396

## Implications for the spec

- Precedent supports deriving visibility from the messaging policy (already per site/organisation/cohort/registration/learner) rather than adding a second parallel toggle: the free-course learner is "a user who can message no one".
- Constraint from `messages_button()` design: no per-page query cost. A per-user check must be cheap or cached, or the badge/partial must resolve it lazily.
- Hide all entry points consistently (header button, pages, educator surfaces) and test both states.

status: ok
