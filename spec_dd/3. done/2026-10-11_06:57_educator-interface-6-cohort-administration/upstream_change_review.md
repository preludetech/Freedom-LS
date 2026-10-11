# Upstream-change review: educator-interface-6-cohort-administration

direction: changed

## What main gained

The messaging policy spec (user-communication-3-messaging-policy, now in `spec_dd/3. done/`) added relationship queries to `freedom_ls/learner_management/queries.py`: `educators_of`, `peers_of`, `peers_through`, `registrations_of`, `holds_registration_for_any_expression`, `colleagues_of`, `is_in_cohort_expression`. Verified in code:

- `registrations_of` and `holds_registration_for_any_expression` read `CohortCourseRegistration.objects.filter(..., is_active=True)` directly. Neither goes through `access_granting_cohort_registrations()` and neither checks `cohort__is_active`. So a learner whose cohort is inactive still counts as sharing a course with the other registrants, and so still counts as a peer.
- `peers_of` / `is_in_cohort_expression` link learners by `CohortMembership` alone, with no cohort state.
- `educators_of` goes through `_granted_cohorts` and `cohortmembership__learner`, with no cohort state. `learners_visible_to` is the same. They are the two directions of one relation, pinned together by an agreement test.
- The done spec deferred the Cohort.is_active question to this spec in three places: `1. spec.md` line 270 (a comment in the agreement test points at "the planned `Cohort.is_active`"), `1. spec.md` line 339 ("`Cohort.is_active` (`educator-interface-6-cohort-administration`) decides whether an inactive cohort still links peers and educators"), and `idea.md` line 174. The query research says the same. `plan.md` line 486 and the TestEducatorsOf docstring say "If one is added, change learners_visible_to and educators_of together".

The messaging spec did not decide anything this spec reopens. It handed the decision over, and it is now unmade. This spec's `1. spec.md` and `2. plan.md` never mention messaging, `educators_of` or `peers_of`.

## Why it matters for this spec

- `1. spec.md` "Access and progress resolution" says "Add one helper and use it at every read site, so the rule cannot drift". Its read-site table lists only the course-access sites, and its "Leave these alone" list names only fan-out, reports and deadlines. The new peer queries are cohort-registration reads that fit neither list, so the spec's own "every read site" claim is now false.
- The docstring of `access_granting_cohort_registrations()` ("Every access read goes through this") is also false, because `registrations_of` and `holds_registration_for_any_expression` bypass it. Today an inactive cohort grants no course access (decision 1) yet still makes its members course peers. That is an unplanned inconsistency.
- Decision 3 ("an inactive cohort is read-only") and the unchanged `cohorts_visible_to` / `learners_visible_to` mean educators still see an inactive cohort and its learners. `educators_of` must keep agreeing with `learners_visible_to`, so it can only change if both change together.
- The `2. plan.md` read-site task list (around line 74) has no task and no test for any of this.

## What to change

- `1. spec.md`, Decisions: add a decision on messaging. Recommended: an inactive cohort stops linking peers through course registrations, matching decision 1. Shared cohort membership and `educators_of` stay as they are, because decision 3 leaves the cohort and its learners visible to educators and `learners_visible_to` is unchanged. State the reasoning that an inactive cohort keeps its members and their educators but not course access. If the maintainer wants a different answer, record it instead; the point is that the choice is written down.
- `1. spec.md`, read-site table: add `queries.py` `registrations_of` and `holds_registration_for_any_expression`. Remove "Add one helper and use it at every read site" wording that implies the list is complete, or make it complete.
- `1. spec.md` "Leave these alone": add `educators_of`, `learners_visible_to`, `colleagues_of`, and the cohort-membership branch of `peers_of`, with the reason above.
- `2. plan.md`: add a task. `registrations_of` and `holds_registration_for_any_expression` use `access_granting_cohort_registrations()` (or `cohort__is_active=True` in the same `filter()` call as the existing conditions, per the one-filter-call rule). Add tests in `freedom_ls/learner_management/tests/test_queries.py`: peers sharing a course only through an inactive cohort's registration are not peers; peers sharing the inactive cohort itself still are; `educators_of` and `learners_visible_to` still agree for an inactive cohort.
- `freedom_ls/learner_management/tests/test_queries.py` TestEducatorsOf: replace the "because Cohort has none" docstring with the recorded decision, and extend the agreement world with an inactive cohort.
- `freedom_ls/learner_management/queries.py`: after the code change, the `access_granting_cohort_registrations()` docstring is true again. If the decision goes the other way, reword it to say "every course-access read" and name the peer queries as the deliberate exception beside the learner_progress one.

status: ok
