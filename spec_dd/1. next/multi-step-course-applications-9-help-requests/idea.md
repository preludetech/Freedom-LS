# Applicant help requests

Spec 9 of 10 in the Multi-step course applications effort. Read the "Multi-step course applications" section of
`spec_dd/1. next/roadmap.md` first: it holds the build order, what this spec depends on and may
run beside, the decisions already taken and the assumptions every idea in the effort makes.

## What

An applicant who is stuck asks for a person to call them, from any page of an application form and from the application's status page. They give their name, a phone number, a good time to call and their question. Reviewers of the application's organisation are notified in the app and see the request on the review screen, where they mark it done. A webhook event carries the request to the deployment's CRM.

## Why

Applicants stall mid-form on things only a person can answer: which documents count, whether they qualify. Today they leave. A callback request keeps them, and gets the question to the people who can answer it without the applicant having to hunt for a contact address.

## What is settled

- **Who and where.** A signed-in applicant or an anonymous applicant can ask, from every page of an application form and from the status page. The request records the form page the applicant was on.
- **Data model.** The request hangs off the `CourseApplication`, which covers both kinds of applicant. It does not use `comms` messaging, because an anonymous applicant has no `User` and nobody replies in FLS: a person phones the number.
- **Requirement anchor.** If `multi-step-course-applications-5-requirements-and-resolver` has landed first, the request also anchors to a requirement. Otherwise that spec adds the requirement anchor and the link from requirement pages.
- **Name.** The word is "help request". It is distinct from the help desk's "help ticket", and this spec adds it to the glossary. The request shares nothing with `user-communication-help-desk`: different askers, anchors and reply channel.
- **Phone field.** The phone number is validated and stored as E.164 using `form_engine/phone_numbers.py`. The spec extracts a small reusable form field and widget from the form_engine phone input, so there is no copied template and later plain Django forms can use it.
- **Reviewer notification.** Every holder of the review capability in the application's organisation gets an in-app notification in a new category, linking to the review screen. The applicant is never notified of their own request, so a reviewer who is also the applicant is skipped. The spec answers the notifications skill's five checklist questions; email is out of scope until notification email lands.
- **No reviewers.** When nobody holds the role, the request is still stored and the webhook still fires.
- **Review screen.** Reviewers see the application's help requests on the review screen from `multi-step-course-applications-2-reviewers-and-inbox` and can mark one done. A request is open or done; there is no reply thread.
- **Webhook.** A new event `application.help_requested`, with a sample payload alongside the other event samples. The payload holds ids, course, organisation, applicant name and email, E.164 phone, good time, question and anchor. It carries personal data, and the webhook docs say so.
- **Abuse protection.** Anonymous posts are protected by the honeypot and a rate limit.

## Open until the spec

- Whether help requests also appear as their own list in the inbox, beside the per-application view on the review screen.
- Whether several requests from one applicant roll up into one notification.

## Out of scope

- Email to reviewers or applicants.
- Replying to the applicant inside FLS.
- Any shared model, queue or screen with `user-communication-help-desk`.

## Resources

- `spec_dd/1. next/multi-step-course-applications/research_help_and_recommendations.md`, sections 1 to 4 and 6
- `spec_dd/1. next/multi-step-course-applications/idea.md`, "Asking for help"
- `claude_plugins/fls-dev/skills/notifications/SKILL.md`
- `freedom_ls/form_engine/phone_numbers.py`
- `freedom_ls/base/webhook_event_types.py`, `freedom_ls/webhooks/events.py`
- `freedom_ls/accounts/forms.py` (`honeypot_field`, `reject_honeypot`)
