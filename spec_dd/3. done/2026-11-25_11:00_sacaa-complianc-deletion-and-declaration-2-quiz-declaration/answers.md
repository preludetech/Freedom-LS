# Answers: sacaa-complianc-deletion-and-declaration-2-quiz-declaration

Asked by `/sdd:start` before the spec was written.

- Q: Where is a learner's signed quiz declaration stored, which decides how "never updated" is enforced? → A: Its own append-only model, one-to-one with `FormProgress`, whose `save()` refuses updates and whose admin is read-only, like `LegalConsent` (asked up front)
- Q: With "once per learner", which earlier signature lets a later attempt skip the declaration (same form any course, or same form same course)? → A: No declaration skipping. If a form needs a declaration, the user must fill it in (asked up front)
- Q: With "once per learner", if the author changes the declaration text after a learner signed, does the next attempt ask again? → A: Every form attempt gets the declaration again. No reuse. This drops the "once per learner" frequency and the frequency setting from the idea: every attempt signs (asked up front)
- Q: Should the declaration (text, name, time, IP) be added to a form export in this spec? → A: No. Leave it to `sacaa-compliance-4-attempt-review`; this spec shows the declaration in the Django admin only (asked up front)
- Q: How hard is "never updated" enforced (QuerySet.update() and raw SQL bypass a save() guard)? → A: App level plus an update-blocking queryset: save() refuses updates, the model's queryset refuses update()/bulk_update(), the admin is read-only; no PostgreSQL trigger (asked while research ran)
- Q: If the author changes the declaration text between the learner opening the declaration page and submitting it, what happens? → A: The page carries a hash of the text it showed; on a mismatch nothing is stored and the page re-renders with the new text (asked while research ran)
