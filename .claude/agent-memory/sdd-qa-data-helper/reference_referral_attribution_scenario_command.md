---
name: reference-referral-attribution-scenario-command
description: qa_create_referral_attribution_scenario — referral-attribution-over-time QA seed: reuses 3 demo courses, PARTNERA/B codes, 3 learners + 1 no-perm staff, password QaPass!2026x; purges touches/conversions/interest
metadata:
  type: reference
---

`uv run python manage.py qa_create_referral_attribution_scenario [--site-name DemoDev]` (Nov 2026,
branch referral-attribution-over-time). Idempotent; destructive only for its own 4 accounts.

- Reuses demo-content courses (asserts their shape, never edits them):
  free `functionality-demo-show-end-with-topic`, gated+form `functionality-demo-application-gated-course`
  (any application_gated course takes BOTH signed-in and anonymous applications —
  `_anonymous_applications_allowed` only checks access_type), coming-soon `content-widgets-demo-reference`.
- PARTNERA / PARTNERB ReferralCodes already existed on DemoDev (pks cd2dfb1e..., fdf80407...);
  command creates/re-activates only if needed. ReferralCode admin refuses delete; code text read-only.
- Learners qa.live/qa.login/qa.selfreg@example.com (pks 87-89), staff qa.staffnoperm@example.com (pk 90).
- Purge order: Conversion BEFORE AttributionTouch (first_touch/last_touch RESTRICT), then
  SignupAttribution, CourseInterest; course data via qa_create_clean_applicant._purge_course_data.
- `_ensure_user` in qa_create_clean_applicant now takes an optional `password` (default = email).
- REQUIRE_TERMS_ACCEPTANCE gates SIGNUP only, not login; LegalConsent rows are added anyway
  (via get_legal_doc version/git_hash) to mirror a real signup.
- Admin model URLs use the app label: /admin/freedom_ls_referral_tracking/<model>/ (not
  /admin/referral_tracking/...: that 404s and looks like a permission result). No-perm staff gets
  /admin/ 200 and 403 on those changelists.
- Login probe: demodev password is `demodev@email.com` (config.md QA Login), not "demodev".
