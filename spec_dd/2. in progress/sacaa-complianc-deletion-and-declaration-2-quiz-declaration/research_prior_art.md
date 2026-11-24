# Research: prior art for the quiz declaration

Topic: what has been tried before, here and elsewhere, and what happened. Repo parts read from the worktree; web parts cited. Nothing in `spec_dd/` has built a quiz declaration before.

## 1. Here: earlier attempts at this feature

- No earlier build. The only earlier mention is "Learner declaration on submit (F8)" in `spec_dd/1. next/sacaa-compliance/idea.md:19`. It asked for a tick plus typed full name before submitting, stored on the form progress record, immutable, shown to educators. This effort moved it to before the first page and into its own spec.
- `spec_dd/1. next/sacaa-compliance/research_sacaa_requirements.md` has no text on declarations or attestation. It says SACAA integrity expectations for ATO internal tests come from the ATO's own approved manual, so FLS must be configurable and not hardcode a policy. It says SACAA-run exams use certified invigilators and candidate ID. The declaration is therefore audit evidence for the ATO, not a SACAA mandate. No regulation text for its wording or frequency was found.
- `spec_dd/1. next/roadmap.md` (SACAA record retention section, lines 76-97) records the decisions and collisions. Two of its lines are now superseded by `answers.md`: "each quiz sets whether its declaration is signed on every attempt or once per learner" (every attempt now), and the assumption that whichever of this spec and `sacaa-compliance-4-attempt-review` lands second shows the declaration on the educator view (still holds; `answers.md` limits this spec to Django admin). The roadmap and `idea.md` should be updated to match.
- `answers.md` outcomes: own append-only model, one-to-one with `FormProgress`; no skipping or reuse (every attempt signs, no frequency setting); no export columns here.

## 2. Here: precedents to follow

### LegalConsent (accounts/models.py:232, built in `better-registration`, May 2026)
- Append-only by a `save()` guard that raises `ValueError` on update. It uses `_state.adding` because the PK is a UUID. The admin is fully read-only: `has_add_permission`, `has_change_permission` and `has_delete_permission` all False, with a read-only inline on User.
- The code comment admits that `QuerySet.update()` and `bulk_update()` bypass the `save()` guard. The audit-log spec (`audit-log-coverage-gaps/idea.md:36`) accepts this: "append-only against application code only", not tamper-proof against direct DB access.
- The better-registration threat model (`spec_dd/3. done/2026-05-05_08:18_better-registration/threat_model.md`) set the controls to repeat:
  - V1.1: cross-tenant read or write of consent, so the model is site-aware and no view takes a user id.
  - V4.2: fabrication, so limit the code paths that create rows (no admin "give consent" action).
  - V5.3: IP extraction behind a proxy needs a vetted helper, which became `accounts.utils.get_client_ip`.
  - V2.2: IP is PII, so the privacy policy must mention IP capture and retention. QA confirmed the privacy doc mentions IP capture and 7-year retention. A declaration IP is the same PII and may need the same policy mention.
  - V9.1: the consent log is the audit trail.
- It stores a document version and git hash, not the text. This spec must store the text verbatim, since the author can edit the declaration afterwards.
- `LegalConsent` is in `USER_ERASURE_CASCADE_MODELS` (accounts/admin.py:26). Force delete (sibling spec 1) removes it with the user, so a declaration that cascades from `FormProgress` fits the same stance. The sibling research notes that other admins deny delete and that only `LegalConsentInline` sits on User.

### served_paper (`sacaa-compliance-1-served-paper-record`, done 2026-11-20)
- Chosen: a lazy write at the first page-serving request (`ensure_served_paper`), because two production sites and QA seeders create `FormProgress` by hand. Write-once is a conditional `update(... served_paper__isnull=True)` plus a re-read, so two racing tabs agree.
- Lesson for the declaration: a flag on a mutable `FormProgress` row is not truly immutable. The answer chosen (own append-only model) is stronger. A gate must also cover sittings that already exist (in flight at deploy, QA seeders, anonymous sittings, course applications that reuse the page flow without the start screen). Old rows get no backfill.
- Landed spec set a convention: references are string uuids, no backfill for old rows, quizzes only, and the in-code decisions are named in a "Decisions" section.
- `form_start` already calls `ensure_served_paper` (views.py around 1927-1943). Declaration check should sit in the same place and guard `form_fill_page` and `form_submit_and_exit` (views.py:2024, 2390).

### Other precedents
- `FormProgress.user` is `on_delete=CASCADE`, `form` is `PROTECT` ("audit record of a sitting"). A one-to-one declaration with CASCADE follows this.
- The audit-log app's append-only guards (`freedom_ls/audit_log/README.md`) are another in-repo template.
- Collision list (research_quiz_declaration.md section 6, roadmap): `sacaa-compliance-3-question-pools` landed 2026-11-24 and already changed schema, `Form`, `content_save` and the `form_engine` migrations. Rebase onto it, and check the migration numbers after `0011_shuffle`.

## 3. Elsewhere: honesty statements in online assessment

- Evidence that they deter cheating is mixed.
  - Mazar, Amir and Ariely found that signing a code before a self-graded test reduced cheating in lab settings (reported in the summary below; not read directly).
  - A randomised trial of 409 students in an online course (Corrigan-Gibbs et al., "Measuring and Maximizing the Effectiveness of Honor Codes in Online Courses", L@S 2015) found a pre-task warning about consequences significantly reduced cheating, while an honor code had a smaller, non-significant effect. They suggest a specific warning may work better than a generic code. https://people.csail.mit.edu/henrycg/files/academic/papers/las15measuring.pdf
  - Other work found no effect of honor codes in online psychology and exam studies. A Kennesaw State 2025 working paper tests an integrity statement at the start of online accounting exams; I did not retrieve its result. https://www.kennesaw.edu/coles/research/docs/fall-2025/fall-25-06.pdf
  - Rutgers: honor code as a moral reminder (Weiner): https://newbrunswick.rutgers.edu/sites/default/files/2022-01/Using%20an%20Honor%20Code%20as%20a%20Moral%20Reminder%2C%20Weiner%2C%2012-13-20-2_v2.pdf
- Implication for this spec: the main value is evidence (a record to match against the learner in an audit), not deterrence. Do not claim it reduces cheating. An author can include consequences wording in the declaration text; the default text could name them (a suggestion from the trial, not a requirement).
- Audit acceptance: I found no documented case of a regulator accepting or rejecting a typed-name-plus-tick declaration in an LMS. SACAA material (see section 1) gives no declaration rule. Typed-name click-wrap is generally a weak signature (no identity proof), which is why the stored time and IP matter. Say in the spec that it is attestation evidence, not identity verification.
- Web search was one standard query; no LMS vendor documentation (Moodle, Canvas, Blackboard honour-pledge plugins) was reviewed, so no claim is made about their implementations or their audit track record.

## 4. Points for the spec

1. Follow the `LegalConsent` pattern: `save()` guard, fully read-only admin (add, change and delete denied), site-aware, one creation path only, IP from `get_client_ip`. Note the `QuerySet.update()` bypass and accept it in the same words.
2. Store the declaration text verbatim, plus the typed name as typed, time and IP. Decide the null-IP case, as `LegalConsent` uses `ip_address=ip or None`.
3. Gate every route to pages, including existing and resumed sittings, and decide what happens to in-flight sittings at deploy. A rule that a sitting without a declaration cannot be shown pages needs a policy for old rows (no backfill, as with served_paper).
4. Handle the double start within `START_REUSE_WINDOW` with a one-to-one constraint and a get-or-create that tolerates the race (`IntegrityError`), like served_paper's conditional update.
5. Mention IP capture in the privacy text (V2.2) if that policy file is project-level.
6. Update roadmap line 92 and `idea.md` for the dropped frequency setting.
7. Do not promise a deterrent effect; frame it as audit evidence.

Sources:
- https://people.csail.mit.edu/henrycg/files/academic/papers/las15measuring.pdf
- https://www.kennesaw.edu/coles/research/docs/fall-2025/fall-25-06.pdf
- https://newbrunswick.rutgers.edu/sites/default/files/2022-01/Using%20an%20Honor%20Code%20as%20a%20Moral%20Reminder%2C%20Weiner%2C%2012-13-20-2_v2.pdf

status: ok
