---
name: password-reset-student-command
description: qa_create_password_reset_student command + the shared demodev_s1@email.com QA fixture email
metadata:
  type: reference
---

For QA of the password-reset email (/accounts/password/reset/), the only requirement is an
active User with the target email. Command:

`uv run python manage.py qa_create_password_reset_student [--site-name DemoDev]`

Creates User via `UserFactory(... site=site)` (explicit site, since no `mock_site_context`
in mgmt commands), plus a verified+primary allauth EmailAddress. Idempotent: matches on the
globally-unique `User.email`, reuses + reactivates + resets password (password == email).

Gotcha: the email `demodev_s1@email.com` is a SHARED QA fixture. It is also created/owned by
[[course-player-student-command]] (`qa_create_course_player_student`), which additionally
enrols it in demo courses and sets progress. So this email may already exist with enrolments.
If a test needs a pristine, enrolment-free account, use a different email, don't assume
demodev_s1 is bare.

DemoDev site is id=3, domain 127.0.0.1:8000. See [[verified-student-setup]] for the
three-record login-ready pattern (User + verified EmailAddress + UserCourseRegistration);
password reset only needs the first.
