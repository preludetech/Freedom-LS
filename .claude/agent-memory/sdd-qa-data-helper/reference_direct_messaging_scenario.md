---
name: reference-direct-messaging-scenario
description: qa_create_direct_messaging_scenario (--site-name DemoDev) personas/conversations, and the "s1 has zero conversations" variant
metadata:
  type: reference
---

`uv run python manage.py qa_create_direct_messaging_scenario --site-name DemoDev` resets everything
(personas *@qa.test, password == email; 7 conversations; site/org/cohort/learner messaging configs deleted
back to defaults). Cohort A (Northside) = l1,l2,l3, edu = cohort_admin; Cohort S (Southside) = s1.

"Sam has zero conversations" variant (asked Nov 2026, hide-messages-icon branch): delete the one
south.admin <-> s1 Conversation via `Conversation._base_manager.filter(participants__user__email='s1@qa.test')`;
cascade = 1 Conversation, 2 ConversationParticipant, 1 Message.

Verification gotchas: CohortMembership FK is `learner` (use `learner__user__email`), not `user`.
Roles: `role_based_permissions.utils.get_object_roles(user, obj)`. Config model:
`messaging_policy.models.OrganisationMessagingConfig`.
