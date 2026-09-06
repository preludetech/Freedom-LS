---
name: reference-qa-run-residue-cleanup
description: Tearing down the residue of a manual QA run (ad hoc signup user, CourseInterest rows, a self-service course enrolment) without touching the seed fixtures — cascade shapes and the one PROTECT that blocks it
metadata:
  type: reference
---

Recipe for "clear the dev-DB residue left by the manual QA run" (first asked on
`bug-interested-login-405`, Sep 2026, site DemoDev). Four kinds of residue, four different
cascade shapes.

## Sizing a delete: `Collector` is only half the story

`Collector.collect([obj])` puts *loaded* cascades in `c.data` but everything Django can delete
without loading in `c.fast_deletes` (a list of querysets). **Printing only `c.data` under-reports
the blast radius** — for a User it showed just `User` + `EmailAddress` and hid two `LegalConsent`
rows. Always print both:

```python
for model, objs in c.data.items(): ...          # loaded cascades
for qs in c.fast_deletes: print(qs.model._meta.label, qs.count())
for (fld, val), qss in c.field_updates.items(): ...   # SET_NULL; usually empty QuerySets
```

`field_updates` prints entries even when every queryset in it is empty, so check the querysets,
not the keys, before reporting "N rows were nulled".

## 1. A signup-flow user (allauth deferred-login / express-interest run)

Everything a browser signup leaves behind cascades off `User`; a single `user.delete()` is
sufficient and returns the counts. Real shape for a user who signed up and expressed interest:

```
(4, {'freedom_ls_accounts.LegalConsent': 2, 'account.EmailAddress': 1, 'freedom_ls_accounts.User': 1})
```

- **`LegalConsent`: expect 2, not 1** — the signup checkbox writes one row per document type
  (`terms` + `privacy`, each with `document_version`, `git_hash`, `ip_address`,
  `consent_method='signup_checkbox'`).
- `EmailConfirmation` is normally **0 rows** even after a verification click (allauth is on
  HMAC keys here); don't treat an empty result as "the confirmation is missing".
- A user who only expressed interest has **no `Learner` row** and therefore no registrations —
  `Learner` is the join everything enrolment-y hangs off, and interest does not create one.
- `User._meta.related_objects` inbound CASCADE set worth knowing: `admin.LogEntry`,
  `guardian.UserObjectPermission`, `form_engine.FormProgress`, `accounts.LegalConsent`,
  `learner_management.Learner`, all three `*RoleAssignment`, `course_applications.CourseApplication`,
  `course_interest.CourseInterest`, `course_recommendations.RecommendedCourse`,
  `account.EmailAddress`. SET_NULL: `reports.GeneratedReport.requested_by`,
  `*RoleAssignment.assigned_by`.

## 2. `CourseInterest`

Zero inbound relations, no delete signals: always exactly 1 row, no cascade. See the note in
MEMORY.md and [[reference_admin_constraint_fixtures_command]] — the `demodev@email.com` /
`content-widgets-demo-reference` row (pk `b016c94e-…`) is a uniqueness-constraint fixture and
must survive; guard on its pk in the delete script.

## 3. A self-service ("Enrol for free") `LearnerCourseRegistration` — the PROTECT

`CourseProgress.learner_registration` is **PROTECT**, so deleting the registration raises
`ProtectedError`. The progress row was minted by the registration's own `post_save`
(`learner_progress/signals.py`, which deliberately has *no* post_delete counterpart), so removing
it is part of removing the enrolment, not collateral. Order:

```python
CourseProgress._base_manager.filter(learner_registration=reg).delete()  # takes TopicProgress (CASCADE)
reg.delete()
```

Check `topic_progress` / `form_attempts` counts on the progress row **before** deleting and report
them — a QA run that opened one lesson leaves a `TopicProgress` that goes too.
`LearnerDeadline.learner_course_registration` is CASCADE but is usually 0.

## Gotchas that cost a round-trip

- `CourseProgress` has **`learner`**, not `user`: filter `learner__user__email=...`.
- `CourseProgress` has **no `status` field** (use `progress_percentage` / `completed_time`).
- The custom `User` has **no `date_joined`**.
- `_base_manager` everywhere: site-aware managers don't filter outside a request, but
  `_base_manager` also skips any default filtering and is the honest "show me every row" read.

## Verification to report back

Re-run the locating queries and print: total `CourseInterest` count, `exists()` per deleted user
(plus `EmailAddress`/`LegalConsent` by email, which proves the cascade actually fired), remaining
registrations for the seed learner, and untouched-fixture assertions (course `visibility`, the
seed user still `is_active`, `Course._base_manager.count()`).

## 4. Secondary `EmailAddress` rows on a KEPT user (Sep 2026, error-pages)

Variant ask: delete the extra unverified addresses a QA run added at `/accounts/email/`, but keep
the user and the primary verified row. Nothing cascades - the delete is exactly
`(2, {'account.EmailAddress': 2})`, and `EmailConfirmation` is **0 rows** (confirmed again: there
is no `ACCOUNT_EMAIL_CONFIRMATION_HMAC` override in settings, so allauth's HMAC default holds and
confirmations are stateless). Don't hunt for confirmation rows to clean up; just show the count is
0 and say so.

Delete by **explicit pk list** plus assertions that each row has `user_id == <kept user>`,
`primary is False`, `verified is False`, and an email in the target set. An `email__in=[...]`
delete would also take a matching row belonging to some other user; the pk list plus guards cannot.

The best verification for this shape is the rendered page, not just a row count:

```python
client = Client(SERVER_NAME="127.0.0.1"); client.force_login(user)
html = client.get(reverse("account_email")).content.decode()
```

`force_login` is a false positive for *proving login works*
([[reference_proving_allauth_login_works]]) but is fine here - the claim under test is page
content, not authentication. If you regex the page for email-like strings, note it also picks up
npm package specifiers from the asset tags (htmx and csp versions); ignore those.

## The security-guard hook fails with an EMPTY error message

`claude_plugins/django-stack/scripts/hooks/security-guard.sh` scans the *entire* Bash command
string against a denylist and exits non-zero with **no stderr**, so it reads as an infrastructure
fault rather than a policy block. Read the hook the first time a shell call fails with an empty
error - the denylist is short and plainly listed at the top of the file.

Two consequences worth remembering:

1. It matches a substring anywhere in the command, including inside a heredoc. Writing *prose*
   that quotes a denylisted string trips it, which is confusing because the command itself is
   harmless. Paraphrase instead of quoting.
2. One entry is a regex for private-key/certificate file suffixes. Allauth's `EmailConfirmation`
   has a token attribute whose dotted access matches that regex, so printing it from a shell
   one-liner is blocked. Print `created` / `sent` / `email_address_id` instead - for this cleanup
   the token was never needed anyway.

Do not try to smuggle a denylisted literal past the hook by splitting it into concatenated
fragments; that is hook evasion and the permission classifier correctly refuses it.
