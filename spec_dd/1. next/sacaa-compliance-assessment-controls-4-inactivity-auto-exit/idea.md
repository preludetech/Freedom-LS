# Inactivity auto exit

Spec 4 of 7 in the SACAA assessment controls effort. Read the "SACAA assessment controls" section of
`spec_dd/1. next/roadmap.md` first: it holds the build order, what this spec depends on and may
run beside, the decisions already taken and the assumptions every idea in the effort makes.

## What

Authors can turn on an inactivity rule in the front matter of a topic, a form or a course part. The rule has an interaction interval (any length, for example 2.5 minutes), a warning time (default 1 minute) and an exit (the learner dashboard, or log out). When the warning time is reached a dialog opens with a countdown and an "I'm still here" button. Any interaction resets the clock. At zero the learner is sent to the dashboard or logged out.

This spec also builds the shared activity signal: a client interaction detector on learner content pages, and a server record of the learner's last interaction on that page. The server enforces the rule with that record, so a closed tab or switched-off JS does not get round it.

## Why

Regulation: "the programme must regulate interaction during learning every 2 min and 30 seconds or logout the student automatically;"

The learner interface measures nothing about presence today. There is no heartbeat, no per-page timer and no last-interaction record. A client timer alone can be bypassed, so the server must hold the truth. `sacaa-compliance-assessment-controls-5-test-disturbance` and `sacaa-compliance-assessment-controls-6-minimum-learning-time` both build on the signal this spec creates.

## What is settled

- The rule is off by default. It is set in front matter on `Topic`, `Form` and `CoursePart`, with three values: interaction interval, warning time (default 1 minute) and exit (dashboard or logout). Each new key needs a pydantic field, a model column and a migration, because `save_with_uuid` rejects keys that are not model columns (`freedom_ls/content_engine/content_save.py:295-384`). The offline validator and the content-editing docs list the new keys too.
- A course part's setting applies to its children unless a child sets its own. It is resolved at request time by walking the item's `ContentCollectionItem` to its parent part, as `get_course_index` does, not copied onto each row. A topic can be placed twice, so resolution is per placement.
- The warning dialog is a plain native `<dialog>` with its own Alpine component, registered with `Alpine.data` (the Alpine build is the CSP build, so no inline expressions). It does not use the panel framework's modal host, because `extract_panels_framework-5-package-and-install` is moving that framework into a package. It has a countdown and an "I'm still here" button (WCAG 2.2.1).
- Any interaction resets the clock, including the button. A hidden tab keeps counting down. The countdown uses `Date.now()` deltas, as the toast component does (`freedom_ls/base/static/base/js/alpine-components.js:250-370`).
- At zero the learner goes to `learner_interface:dashboard`, or is logged out with allauth's POST logout (a form submit or a `fetch` POST with the CSRF header; there is no GET logout).
- The server enforces the rule. A request on an enforced page after the interval has lapsed with no recorded interaction is treated as an auto exit: the learner gets the configured exit, not the page.
- The signal is per page and separate from the coarse `User` last-active time that `sacaa-complianc-deletion-and-declaration-1-force-delete` (in progress) adds. This spec does not write that field and does not read it. Coupling them would tie a throttled, site-wide write to a per-page compliance check.
- Reference topics have a separate route (`course_reference_topic`) and sit outside the rule.
- An auto exit on a test is a disturbance, but what happens to the attempt belongs to `sacaa-compliance-assessment-controls-5-test-disturbance`. This spec only exits and makes the exit observable to it.
- This spec's signal is what `sacaa-compliance-assessment-controls-6-minimum-learning-time` reads to accumulate active seconds. That spec owns the accumulation; this one owns the detector and the last-interaction record.
- `sacaa-compliance-content-versions-and-access-2-retire-removed-content` (in progress) adds columns on `Topic`, `CoursePart` and `Form`. The migrations run in parallel, so they must not depend on each other.
- Nothing needs to be built on `Course`, on a cohort or on a per-learner override.

## Open until the spec

- What counts as an interaction. Recommend pointer movement or press, key press, scroll and touch. HTMX requests count only if they come from one of these.
- How often the client pings the server. Recommend a throttled ping on interaction, at most once per a fraction of the interval (for example a quarter of it), so the server sees activity without a write per event.
- Where the last interaction is stored. Recommend a small per-learner, per-placement record updated by the ping, not columns on `TopicProgress`, so a page that has no progress row (a form start page) is covered. Weigh against what `-6-minimum-learning-time` needs.
- Where the server check runs. Recommend one shared gate called by the player routes beside `_course_access_redirect` and `_blocked_item_redirect` (`freedom_ls/learner_interface/views.py:1203`, `1326`), not a middleware, so it only touches enforced pages. A template-only check would repeat the old outline-only gate bug (`views.py:1341-1344`).
- What a paused or closed course does to the rule. Recommend the rule does not apply while the course is paused or the item is closed, since no progress is written then.
- How the exit shows on the next page. Recommend a short message on the dashboard or login page that says the learner was exited for inactivity.

## Out of scope

- What happens to a test attempt on auto exit (`sacaa-compliance-assessment-controls-5-test-disturbance`).
- Accumulating learning time and minimum-time gates (`sacaa-compliance-assessment-controls-6-minimum-learning-time`).
- Moving the `User` last-active field, or any change to the force-delete spec.
- Focus-loss and tab-switch detection, per-cohort overrides, and identity verification.
- Rules on reference topics.

## Resources

- `../sacaa-compliance-assessment-controls/research_learning_time_and_inactivity.md`, sections 1, 2, 3, 5 and 6.
- `../sacaa-compliance-assessment-controls/research_regulation_and_prior_art.md`.
- Regulation source: the SA-CATS 141 e-learning criteria, quoted in `../sacaa-compliance-assessment-controls/idea.md` under "Auto exit". The criteria themselves have not been read; the quote is as the owner supplied it.
