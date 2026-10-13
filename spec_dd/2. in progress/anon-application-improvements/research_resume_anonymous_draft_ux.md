# Research: surfacing a session-held draft application to an anonymous visitor

## Fit with FLS today (code look)

- Signed-in block: `freedom_ls/course_applications/templates/course_applications/partials/dashboard_applications.html`, a "Your applications" section. One row per application: course title (link to `course_applications:status`), an "Incomplete" warning chip, "Finish your application to have it reviewed.", and a "Continue application for <course>" button. A submitted application shows "Pending review" instead.
- The dashboard view (`freedom_ls/learner_interface/views.py`, ~L631-645) only asks the backend for `get_dashboard_contributions(user=...)` when `inputs.is_auth`. An anonymous visitor therefore gets no panels. This is the gap.
- Session access (`freedom_ls/form_engine/session_access.py`): `owned_form_progress(request)` for anonymous requests returns only sittings with `user` null, `completed_time` null and pk in the session list. Completed sittings drop out on purpose ("a visitor's answers are theirs to write, not to read back later from the same shared computer"). A submitted draft will therefore never be resolvable for an anonymous visitor. This is already the right privacy stance.
- The panel template carries no PII beyond the course title, so it can be reused for anonymous visitors as is.

## Findings from the web

1. Guest resume works only from the same device or browser, and it is built to be privacy-safe.
   - HCL Commerce persistent guest sessions: a guest can recover a pending cart only from the same computer. On return it can create a fresh guest and strip sensitive data (address, card) because of public-computer ordering. https://help.hcl-software.com/commerce/9.1.0/admin/concepts/csepersist_session.html
   - Adobe Commerce persistent cart: the cart survives browser close, but no sensitive account information is exposed. https://experienceleague.adobe.com/docs/commerce-admin/stores-sales/point-of-purchase/cart/cart-persistent.html
   - A NopCommerce thread shows the failure mode: a guest on a public computer left their details visible to the next person. https://www.nopcommerce.com/en/boards/topic/15225/security-risk-current-customer-persists-after-closing-browser
2. GOV.UK pattern (save-and-return).
   - The pattern puts "Save and complete later" under the primary button. After saving it shows a confirmation and sends an email that says how to resume.
   - A "What do you want to do?" screen offers "start new" or "resume a saved one". Resuming requires sign-in, then the user lands back where they stopped. https://sign-in.service.gov.uk/documentation/design-recommendations/save-progress
   - The page says nothing about shared devices or retention. It is not an authority on either.
   - The Ministry of Justice patterns say to respond helpfully to a bookmarked link the user can no longer use, and to offer a new application or a way to track the old one. https://design-patterns.service.justice.gov.uk/service-patterns/apply
3. Session lifetime.
   - OWASP guidance (via secondary summaries) is that every session needs an absolute timeout and a server-enforced idle timeout. Idle timeouts of 15-30 minutes suit low-risk apps, and the Periodic Table suggests 20 minutes idle and 8 hours absolute as framework defaults. These figures are for authenticated sessions. https://owasp.org/www-project-web-security-testing-guide/v42/4-Web_Application_Security_Testing/06-Session_Management_Testing/07-Testing_Session_Timeout and https://wiki.owasp.org/index.php/OWASP_Periodic_Table_of_Vulnerabilities_-_Insufficient_Session_Expiration
   - An idle timeout does not stop someone who already holds the session cookie. It only limits the window.
   - A draft application is much lower risk than an authenticated session, so a longer window is defensible. That is a judgement call, not something the sources set.
4. Not found. Searches turned up no primary Typeform, Jotform or Baymard source for the guest-banner copy or retention numbers, so those are not cited. The recommendations below that depend on them are judgement.

## What the banner should show

- Show: course title, an "Incomplete" chip, and "Continue application". This is what the signed-in block already does.
- Optionally show "Last saved <relative time>" and a small step indicator ("Page 2 of 4"). Both are useful and carry no PII. FLS has `answered_counts` and `resume_page_number` in `form_engine.paging`.
- Do not show the email address, name, or any answers on the anonymous dashboard. On a shared browser the dashboard is visible to the next person.
- At most show a masked email ("s•••@gmail.com") only on the verification-pending state. Even that is optional.
- Secondary action: "Not you? Discard this application". It needs a POST with CSRF and a confirm step, and it removes the sitting from the session. Say whether it also deletes the row, or only forgets it in the session (the draft keeps its email, so deleting is cleaner for privacy). Without a discard control, a second person on the same browser has no way to clear someone else's draft.

## Edge cases

- Multiple drafts in one session: list one row per draft (the session list holds several pks), newest first. Reuse the same list markup.
- Course no longer accepting applications: show the row, but replace "Continue" with "Applications for this course are closed" and keep Discard. Do not leave a Continue button that dead-ends. This follows the MoJ advice to respond helpfully instead of failing.
- Already submitted: `owned_form_progress` already excludes completed sittings, so the anonymous dashboard shows nothing for them. Do not widen it to show "Pending review" for anonymous visitors. That would reverse the stance in the module docstring. The visitor has the confirmation email and, once they verify, the signed-in panel.
- Session expired or a different browser: the block is simply absent. The idea does not need an extra message on the dashboard. The apply page for a course can say "Already started an application? Check your email for the link we sent you", and this is only worth it if the verification email is sent after the first page (the other half of this idea).

## After email verification

- Verification signs the session in. The current code calls `forget_all_anonymous_form_progress` at that moment, and the sitting gains a user, so it drops out of the anonymous branch.
- The signed-in `get_dashboard_contributions(user=...)` panel then lists the same application, so the block carries over with no extra work.
- Make sure the verification landing page sends the visitor to the application, or to the dashboard where it appears. Avoid a dead end.
- If the visitor verifies in a different browser than the one that holds the draft, the original browser keeps a stale session entry. This is harmless because the sitting has a user and drops out of the anonymous branch.

## Retention

- The session cookie lifetime governs how long the draft is resumable from the browser. The row itself can outlive the session, since the email link is the way back.
- Django's default session age is two weeks, with no idle timeout. That is reasonable for an application draft, but it is longer than a shared-computer user would expect. Keep it as is, unless FLS wants a shorter lifetime for the anonymous case, and let the Discard link cover the shared-computer risk.
- Draft rows with no user and no verified email should be purged after a period set by the project's retention policy. This is outside this idea.

## Recommendations for this idea

1. Extend the dashboard so anonymous visitors get panel contributions. Today `if inputs.is_auth:` blocks it. The least invasive change is a backend method such as `get_dashboard_contributions(request=...)`, or a separate anonymous variant, that reads `owned_form_progress(request)` for user-less drafts. Keep the "learner_interface never imports course_applications" rule.
2. Reuse `dashboard_applications.html` for the anonymous rows. Its links point to `course_applications:status` by pk, so confirm the status and resume views accept a session-owned sitting.
3. Add a Discard action for anonymous drafts (POST, CSRF, confirm), with a note about whether it deletes the row.
4. Show only course title, Incomplete chip and Continue. No email, no answers. Add "last saved" and page progress only if cheap.
5. For a closed course, show a disabled state with Discard in place of Continue.
6. Do not show submitted applications to anonymous visitors. The existing `owned_form_progress` already excludes them.
7. Handle several drafts as a list. Put the block at the top of the dashboard, above the course sections, to match the signed-in layout.
8. Tests: anonymous dashboard shows the draft and does not show another session's draft, nor a completed one. Discard removes it. After verification the signed-in panel shows it once.

## Sources

- https://sign-in.service.gov.uk/documentation/design-recommendations/save-progress
- https://design-patterns.service.justice.gov.uk/service-patterns/apply
- https://help.hcl-software.com/commerce/9.1.0/admin/concepts/csepersist_session.html
- https://experienceleague.adobe.com/docs/commerce-admin/stores-sales/point-of-purchase/cart/cart-persistent.html
- https://www.nopcommerce.com/en/boards/topic/15225/security-risk-current-customer-persists-after-closing-browser
- https://owasp.org/www-project-web-security-testing-guide/v42/4-Web_Application_Security_Testing/06-Session_Management_Testing/07-Testing_Session_Timeout
- https://wiki.owasp.org/index.php/OWASP_Periodic_Table_of_Vulnerabilities_-_Insufficient_Session_Expiration

status: ok
