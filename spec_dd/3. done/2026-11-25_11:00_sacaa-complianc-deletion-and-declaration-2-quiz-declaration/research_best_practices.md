# Best practices: quiz declaration as audit evidence

Scope: per `answers.md`, a learner signs on every attempt, in an own append-only model one-to-one with `FormProgress`, mirroring `LegalConsent` (read-only admin, `save()` refuses updates). No export, no skipping. Sources are marked: [web-known] means cited from established public sources and general knowledge, not fetched in this run; verify section numbers before quoting them in the spec.

## 1. Legal weight: what the declaration needs to be

- South Africa, ECTA 25 of 2002 [web-known]: s11 data messages are not denied legal effect merely for being electronic. s13 covers signatures: an "electronic signature" (data attached to or logically associated with other data, used as a method of signing) is valid where the law only requires a signature. An "advanced electronic signature" (accredited provider, s37-38) is needed only where a law specifically demands one. s15 makes data messages admissible as evidence and says weight depends on the reliability of how the message was generated, stored and communicated, how its integrity was kept, how the originator was identified, and other relevant factors.
- A quiz honour declaration is not a legally mandated signed document. A plain electronic signature (tick plus typed name, tied to an authenticated session) is enough in kind. An advanced electronic signature is not required and would be over-engineering. What the auditor and any tribunal care about is s15 weight: reliable generation, integrity of storage, and identification of the signer. That is the argument for append-only storage, a server-side timestamp and the authenticated user link.
- US analogue (ESIGN 2000, UETA) [web-known]: a signature is valid if there is intent to sign, consent to do business electronically, association of the signature with the record, and record retention in a reproducible form. Intent is shown by an explicit act (the tick plus typed name) after clearly displayed text.
- Clickwrap evidence practice (US case law, e.g. Specht v. Netscape, Meyer v. Uber, Nguyen v. Barnes & Noble) [web-known]: courts accept affirmative-action clickwrap when the text is shown conspicuously before the action, the action is explicit, and the operator can reproduce exactly what that user saw and when. Browsewrap fails. Evidence that wins cases is: the exact text version, user identity, timestamp, and the UI flow showing the text was unavoidable.

Implication: the credible record = exact text shown + authenticated user + typed name + server timestamp + IP. The design in `idea.md` already covers this.

## 2. Fields that make the record credible

| Field | Practice | Recommendation |
|---|---|---|
| Declaration text | Store verbatim text as shown. A version id or hash alone is only evidence if the source is also preserved immutably. Front matter text can be edited later, so a pointer would silently change history. | Store verbatim (already decided). Optionally add a SHA-256 of the text (cheap integrity check that the stored text was not later edited). Not required. |
| Typed name | Stored as typed, trimmed. | Keep as typed; store trimmed value (decided). Do not normalise case. |
| Timestamp | Server clock, never client-supplied. UTC, timezone-aware. | `DateTimeField(default=timezone.now, editable=False)` set server-side at submit. Name it so it is the signing time, not the attempt start time. |
| User identity | Link to the authenticated account. | Via `FormProgress.user`. Consider a denormalised `user` FK for query convenience only if the model allows it; do not duplicate email. |
| IP address | Standard evidence element. | `get_client_ip` (decided). Use `GenericIPAddressField(null=True)`; the existing `LegalConsent` pattern is the precedent. |
| User agent | Commonly stored in clickwrap audit trails and helps tie a signing to a device. Not required for ECTA. | Flag as a scope decision: it is an additional personal-data-adjacent field. Recommendation: do not store unless the auditor asks; the idea lists only four fields and CLAUDE.md says not to build unrequested functionality. |
| Form/quiz identity | Evidence should say which quiz. | Reachable via `FormProgress.form`, but if the form is renamed or deleted the context is lost. Consider no extra column; `FormProgress` already pins it. |
| Site | Multi-site. | The model should be site-aware like `LegalConsent` (`SiteAwareFactory` is used there). |

## 3. Tamper-evidence and immutability in Django

Layers, weakest to strongest. The accepted answer is layer 1 plus the admin lock, which matches `LegalConsent`. Know the limits.

1. Application guard: override `save()` to raise if `self.pk` exists and `_state.adding` is false (`force_insert` only). Also override `delete()`? Careful: the idea requires force deleting a learner to cascade-remove declarations, so do not block `delete()` on the model; block only updates. Cascade deletes via the collector do not call `Model.delete()` anyway, but raw `QuerySet.delete()` is also not blocked by a `delete()` override, which is what you want here.
2. Queryset gap: `QuerySet.update()` and `bulk_update()` bypass `save()`. Mitigate with a custom manager/queryset whose `update`/`bulk_update` raise `NotImplementedError` (keep `delete` allowed for the cascade). Test it. Note site-aware manager already exists in this project, so the queryset needs to compose with it.
3. Admin: `has_add_permission`, `has_change_permission` False, `has_delete_permission` False (precedent in `accounts/admin.py`). Caution: Django admin's cascading delete from `User` or `FormProgress` still removes the rows, which is the desired outcome. If has_delete_permission is False on the declaration admin but the parent admin deletes, the related-object permission check will block the parent delete in the admin UI ("would require deleting protected/unpermitted objects"). Verify how `LegalConsent` behaves and whether this spec's force-delete path uses the admin or a service function; flag as a test.
4. DB-level: a PostgreSQL `BEFORE UPDATE` trigger raising an exception (via `migrations.RunSQL`) gives enforcement that holds against `.update()`, raw SQL and shell use. Alternatively revoke `UPDATE` on the table from the app DB role (not workable when the app role owns the table and runs migrations). Trade-off: triggers are invisible to Django, add migration complexity, and CLAUDE.md says no raw SQL without security review. Recommendation: a trigger is optional hardening; state explicitly in the spec whether it is in or out. Application-level is the project precedent. Mention honestly that a database superuser can still alter rows; no in-DB measure stops that.
5. Hash chaining / HMAC: store an HMAC (server secret key) over `(user_id, form_progress_id, text, name, timestamp, ip)` to detect later out-of-band edits. This gives tamper evidence rather than prevention, and is the only measure that detects a direct DB edit. It adds key-management burden (rotation) and is beyond the answers given. Flag as a "would change what we store" option (an extra `integrity_hash` column), default out.
6. Off-DB: periodic export to WORM storage or log shipping. Out of scope.

Tests to expect: second `save()` raises; `.update()` raises; creating a second declaration for the same `FormProgress` fails (OneToOne unique); the admin has no add/change/delete.

## 4. Form-flow practice for a credible signature

- Show text and the tick box and name field on the same screen, text fully visible, before the first page; no pre-ticked box.
- Server-side enforce the gate on every route into the attempt (decided), and make the POST idempotent: a double submit must not create two rows or raise a 500. With a OneToOne the second insert fails; handle with `get_or_create` semantics or catch `IntegrityError` specifically and treat it as already signed. The `START_REUSE_WINDOW` reuse case in `idea.md` is the same concern.
- Store the text the learner actually saw: take it from the form at render time and carry it in the POST only as a hidden field if you must, but better to re-read it server-side at submit. If the author edits the text between render and submit, the stored text could differ from what was shown. Mitigation: carry a hash of the shown text in a hidden field, compare on submit, and re-prompt on mismatch. Flag as an edge case; low probability, cheap to handle or to accept and document.
- Only authenticated users sign; the record is tied to the logged-in session, which is what identifies the signer under ECTA s15 reasoning.
- Wording should be a first-person attestation ("I confirm that I completed this assessment myself, without assistance..."). The default text in the app setting should be written this way and state consequences of a false declaration.

## 5. POPIA and the IP address

[web-known] POPIA (Act 4 of 2013): the Information Regulator treats an IP address as capable of identifying a person when combined with other data, so assume it is personal information. Relevant conditions:

- Lawful basis and purpose specification (s9-13, s13 purpose; s11 justification): processing is justified where necessary to perform a contract, to comply with a legal obligation, or for the legitimate interests of the responsible party. Aviation training audit evidence fits legal obligation or legitimate interest. State the purpose ("evidence that the learner attested to completing the quiz themselves for regulator audit") in the privacy policy.
- Minimality (s10): store only IP, not full header sets. This is a reason to leave out the user agent unless needed.
- Retention (s14): records may be kept as long as required by law or for the purpose. The roadmap's SACAA retention work (spec 1) should set the retention period; the declaration inherits it. Do not keep forever without a stated period. The cascade delete on learner removal is consistent with POPIA deletion duties, but SACAA retention may require keeping records; that tension is precisely what spec 1 of this effort (deletion) addresses. Flag: if force deletion is blocked or anonymised under SACAA retention elsewhere in the effort, the cascade here must follow the same rule.
- Security safeguards (s19): append-only plus read-only admin and limited staff access satisfy "appropriate, reasonable technical measures". Restrict who can view the admin model.
- Data subject access (s23): the declaration, including IP, must be included in a subject access response. Keep it reachable via the user.
- Proxy awareness: `get_client_ip` must only trust `X-Forwarded-For` from known proxies; a spoofable header makes the IP evidence worthless and can be challenged. Confirm the helper's trust model in the spec. IPv6 and NAT: IP is corroborating evidence, not identification; the weight comes from combination with the authenticated session.

## 6. Exam-integrity honour-code practice

- Research (McCabe and Trevino; Mazar, Amir and Ariely; Shu et al. 2012 PNAS) [web-known] shows that signing an honesty statement before the task reduces cheating more than signing after (sign-at-top). The Shu 2012 result was affected by a failed replication and data concerns (2021), so treat the "sign first" effect as weakly supported but harmless. The decided placement (before the first page) agrees with the best-practice position and with proctoring-vendor and awarding-body practice (e.g. candidate declarations before assessment).
- Awarding bodies (Ofqual/JCQ style declarations; professional bodies' "authenticity statements") require a signed or ticked declaration per assessment, not once per course, because each assessment is a separate attestation. This supports the decision to ask every attempt and drop "once per learner".
- Deterrence works best with a stated consequence and a clear, short text. Keep the default under ~100 words.
- A declaration is an integrity control, not proof of identity. Do not claim it proves who sat the quiz; the audit claim is only "the learner attested".

## 7. Items that could change what we store

1. User agent: not in `idea.md`; recommend excluding (POPIA minimality) unless the auditor requires it.
2. Text hash and/or HMAC column: optional integrity evidence; recommend a plain SHA-256 of the text only if the spec wants a cheap integrity check; HMAC if tamper-detection of DB edits matters.
3. Mismatch between shown and stored text when the author edits mid-flow: if handled, a hidden hash field is needed (not stored).
4. DB trigger: affects migrations, not stored fields.
5. Retention and deletion interaction with SACAA retention (spec 1): may require the declaration to survive learner deletion by keeping identity fields on the record; this would change what is stored (e.g. denormalised learner identifier). The idea currently says cascade delete, so follow that.
6. Site FK: store via the site-aware base, consistent with `LegalConsent`.
7. Timestamp name: record signing time, separate from `FormProgress` start time.

## 8. References

- ECTA 2002 (Act 25 of 2002), sections 11, 13, 15, 37-38: https://www.gov.za/documents/electronic-communications-and-transactions-act (and https://www.saflii.org for consolidated text)
- POPIA (Act 4 of 2013), conditions 1-8: https://popia.co.za/ and https://inforegulator.org.za/
- ESIGN Act, 15 U.S.C. 7001 and UETA: https://www.law.cornell.edu/uscode/text/15/7001
- Django model docs on `save()`, `QuerySet.update`, and `force_insert`: https://docs.djangoproject.com/en/stable/ref/models/instances/
- PostgreSQL trigger docs: https://www.postgresql.org/docs/current/plpgsql-trigger.html
- Shu et al. 2012 (PNAS) on sign-at-top honesty and the 2021 data-integrity retraction: https://www.pnas.org/doi/10.1073/pnas.1209746109
- Project precedent: `freedom_ls/accounts/admin.py` (`LegalConsentAdmin`, `LegalConsentInline`) read-only admin pattern.

status: ok · reason: written from established knowledge plus project precedent; web sources cited but not fetched, verify statute section numbers before quoting
