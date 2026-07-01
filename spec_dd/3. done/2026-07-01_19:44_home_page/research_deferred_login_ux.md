# Research: Deferred-Login / "Login Wall on Action" UX

Research topic: the moment of asking an anonymous user to authenticate when they take a
committing action, and how to preserve their intent across the login/signup flow.

Context: Freedom Learning System allows anonymous users to browse the platform, view course
listings and course detail pages. Authentication is only required when the user takes a
committing action (e.g. "Enrol in this free course" or "Apply to this course").

---

## 1. Intent Preservation Across Login/Signup

### The core pattern: `?next=`

Django's built-in `LoginView` uses a `next` query parameter that contains the URL the user
should land on after successfully authenticating. This is the conventional approach across
the web. The flow is:

1. Anonymous user clicks "Enrol" on the course detail page.
2. System detects the user is not authenticated.
3. Redirect to `/login/?next=/courses/python-101/enrol/` (or equivalent).
4. After login or signup, redirect to the `next` URL.
5. The enrol view completes the enrolment action.

The key distinction for LMS platforms is step 5: the user should not just land on the
course detail page again; they should actually complete the action they intended (enrolment).
This requires the enrol view to be idempotent and to perform the enrolment when reached by
an authenticated user, not just display a confirmation.

### Signup vs login: the extra hop problem

When a new user signs up rather than logging in, the intent preservation is harder: the
signup form does not natively chain to a `next` URL in the same way as Django's login view
unless explicitly coded. The `next` value must be threaded through the signup form as a
hidden field or session value, and then honoured in the signup success handler.

Patterns observed in LMS platforms (LearnDash, Tutor LMS):
- Store the intended course slug/action in the session before redirecting to login.
- On post-login and post-registration success hooks, check the session for a pending action
  and execute it (auto-enrol), then redirect to the course content.

Reference: LearnDash auto-enrol on registration:
https://docs.wpuserregistration.com/docs/user-registration-learndash/

Reference: Redirect Tutor LMS users after login based on course:
https://loginwp.com/redirect-tutor-lms-users-after-login/

### What leading platforms do

**Coursera** lets anonymous users browse the full course catalogue and course detail pages.
Clicking "Enrol for Free" surfaces a login/signup screen (modal overlay on desktop). After
authentication, the platform returns the user to the course and completes enrolment. The
`next` destination is embedded as a URL parameter in the auth flow.
Reference: https://learner.coursera.help/hc/en-us/articles/209818603-Enroll-in-a-course

**Udemy** follows the same pattern: full public browsing, login/signup modal on "Buy" or
"Enrol Free", then redirect back to the course.

**GitHub** allows anonymous browsing of all public repositories. "Star", "Fork", and "Watch"
actions trigger a login prompt. GitHub passes the intended action as a parameter so that
after login, the action completes automatically without the user having to click again.

**E-commerce checkouts (Amazon, Shopify stores)**: Guest checkout avoids the login wall
entirely, but for platforms that require accounts, the standard is to pass a `returnUrl`
through the auth flow. Baymard Institute research consistently shows that 24% of users cite
"site wanted me to create an account" as the reason for abandoning checkout — underlining
that the moment and framing of the auth prompt is critical.
Reference: https://www.corbado.com/blog/guest-checkout-vs-forced-login

### Two patterns for action completion after login

**Pattern A — Redirect-to-action-URL**: The enrol URL is the `next` destination. The view
checks authentication, performs the enrolment, and redirects to the course content. Simple
and stateless.

**Pattern B — Session-stored pending action**: Before redirecting to login, store a
structured pending action in the session (e.g. `{'action': 'enrol', 'course_slug':
'python-101'}`). After login/signup, a post-auth hook checks for the pending action,
executes it, and clears it. More flexible for cases where the action URL alone does not
carry enough context (e.g. multi-step application forms).

For this LMS (free enrolment and gated course applications), Pattern A is simpler and
sufficient for enrolment. Pattern B may be needed for application forms where the user
might have filled in data before being asked to log in.

---

## 2. Login vs Signup vs Guest: What to Present at the Action Moment

### Combined or separate?

At the moment of the committing action, the user may be a new visitor (needs to sign up) or
a returning user (needs to log in). Best practice is to present both paths clearly on the
same screen. A combined email-first flow — where entering an email detects whether the
account exists and routes to login or signup — is used by Amazon and Nike and reduces the
cognitive choice, but adds a round-trip. Tabs ("Log in / Sign up") on a single modal or
page are a simpler and well-understood alternative.

Research indicates that the "sign in" vs "sign up" label similarity causes accidental wrong
clicks. Prefer visually distinct labels: "Log in" + "Create account" or "Log in" +
"Join free".
Reference: https://www.authgear.com/post/login-signup-ux-guide/

### Modal vs full-page redirect

**Modal (inline overlay)**
- Pros: preserves context (user can still see the course detail behind the modal), fewer
  page transitions, can feel lighter.
- Cons: focus trap required for accessibility, scroll position/state may be lost on close,
  harder to deep-link to for testing, URL does not update so back button behaviour can
  be confusing.

**Full-page redirect**
- Pros: simpler implementation, URL updates naturally, back button works predictably,
  server-side rendering is straightforward, easier to handle signup/login flows that span
  multiple steps.
- Cons: user loses visual context of what they were doing; the `next` parameter must be
  handled correctly or the user lands on a generic dashboard.

**Consensus from research**: For action-triggered auth prompts (not proactive prompts), a
full-page redirect with a clear heading ("Create a free account to enrol") that restates
what the user was trying to do is acceptable and often preferable for accessibility and
reliability. Modals are higher-effort to get right and can surprise users. Coursera uses a
modal on desktop; edX uses a full-page approach. Both work when intent preservation is solid.

The Nielsen Norman Group finding on login walls is that users are "utterly vexed" when
they encounter auth before seeing any value. Since FLS already allows browsing before the
wall, this concern does not apply — the wall only appears at the committing action, which
is the appropriate moment.
Reference: https://www.nngroup.com/articles/login-walls/

---

## 3. CTA Wording and Framing for Anonymous Users

### Should the button reveal the login requirement upfront?

Two philosophies:

**Transparent upfront**: "Sign up to enrol" or "Create account to apply". The user knows
before clicking that they will need to authenticate. Reduces surprise but increases the
perception of friction before the user has decided to commit.

**Action-forward**: "Enrol for free" or "Apply now" — the auth requirement appears only
after click. The CTA sells the outcome, not the process. This is what Coursera, edX, and
Udemy do. Evidence suggests this is higher-converting because the user commits to the
outcome first, then accepts the auth step as part of completing it.

**Best practice recommendation**: Use action-forward CTAs on the course detail page.
After click, the login/signup screen should clearly restate the goal: "Create a free
account to enrol in Python 101" — so the user understands their intent is preserved, not
abandoned.

Supporting evidence: Reducing frictional language ("No credit card required", "Free forever")
and specificity of outcome language consistently improves conversion 10–30% on high-friction
CTAs.
Reference: https://www.authgear.com/post/login-signup-ux-guide/

### Wording for different action types

| Action | Recommended CTA (anonymous) | Login/signup screen heading |
|---|---|---|
| Enrol in free course | "Enrol for free" | "Create a free account to enrol in [Course Name]" |
| Apply to gated course | "Apply now" | "Create a free account to submit your application" |
| Start course (enrolled) | "Start learning" (only shown when enrolled) | — |

### Microcopy considerations

- Below or near the CTA, a line such as "Free account required — takes 30 seconds" sets
  accurate expectations without making it feel burdensome.
- Avoid "Register" as the button verb (feels bureaucratic). "Join" or "Create account"
  test better.
- "Already have an account? Log in" should be a secondary link on the signup screen,
  not competing with the primary CTA.

---

## 4. Common Pitfalls and User Complaints

### 4a. Landing on a generic dashboard after login

The most cited frustration: user clicks "Enrol", logs in, and lands on their course
dashboard — not on the course or enrolment confirmation. The `next` parameter was either
missing, ignored, or pointed to the wrong place. Result: the user has to search for the
course they were already looking at, and may not realize they are not yet enrolled.

**Fix**: Always ensure the `next` URL is the enrolment confirmation or the course content
page, not the homepage or dashboard.

### 4b. Losing the pending action after signup (new users only)

Signing up as a new user often means the `next` URL is not passed from the registration
form. The user ends up on a generic "Welcome, complete your profile" page without the
enrolment happening.

**Fix**: Pass `next` through the signup form as a hidden field; honour it in the signup
success redirect.

### 4c. Redirect loops

Misconfigured auth views can send unauthenticated requests for the login page itself to the
login page (infinite redirect). This typically happens when `LOGIN_URL` is not excluded from
login-required middleware, or when the `next` parameter itself points back to the login page.

**Fix**: Django's `@login_required` decorator and `LoginRequiredMixin` are already safe
against this for the login URL itself, but custom middleware or view-level auth checks must
explicitly exclude the login and signup views.

### 4d. Form data lost after login (application forms)

If an anonymous user partially fills an application form and is then prompted to log in,
all form data is lost on redirect. This is a real user frustration.

**Fix**: Do not show gated application forms to anonymous users. Instead, show a preview of
the form fields (to demonstrate what is needed) and prompt login before the form is rendered.
Alternatively, use Pattern B (session-stored pending action) to preserve submitted data.

### 4e. Confusing free-vs-paid gating

Users who cannot tell whether a course is free (enrol immediately) or paid/gated (apply and
wait for approval) may be confused when the CTA triggers different auth flows.

**Fix**: Make the course type explicit on the course detail page before the CTA (e.g. a
badge: "Free" / "By application"). The CTA wording differs accordingly ("Enrol for free" vs
"Apply now") so the user understands what happens after login.

### 4f. Forced signup before seeing value

NN/G research identifies this as the top cause of abandonment from login walls: requiring
registration before users can evaluate whether the product meets their needs.
Reference: https://www.nngroup.com/articles/login-walls/

Since the FLS feature allows full browsing before the auth prompt, this pitfall is avoided
by design. The auth wall only appears at the moment of commitment.

### 4g. SaaS evidence: early login walls destroy activation

Research on SaaS onboarding shows that requiring account creation before delivering value
reduces trial starts by 30–70%. Conversely, enabling anonymous exploration before prompting
auth is one of the highest-leverage conversion improvements available.
Reference: https://www.letsgroto.com/blog/saas-signup-flow-ux

---

## 5. Security: Open Redirect Risks with `next=`

### The risk

The `?next=` parameter is user-controlled. An attacker can craft a URL like:
`/login/?next=https://evil.com/phishing` to redirect users to an external site after login,
enabling phishing attacks. This is a well-known vulnerability (CWE-601, Open Redirect).
Reference: https://www.stackhawk.com/blog/django-open-redirect-guide-examples-and-prevention/

### Django's built-in protection

Django's `LoginView` already validates the `next` parameter using internal logic. However,
the utility function `url_has_allowed_host_and_scheme` (formerly `is_safe_url`) is
documented as handling only part of what is needed for safety — it checks the host and
scheme but does not address all escaping issues.

The Django forum discussion (https://forum.djangoproject.com/t/why-is-the-use-of-url_has_allowed_host_and_scheme-discouraged/35314)
clarifies: Carlton Gibson (Django maintainer) recommends "knowing the allowed targets ahead
of time" rather than accepting arbitrary user input. Django's own auth views do use
`url_has_allowed_host_and_scheme` internally, but custom views that accept `next` must
validate too.

### Practical guidance for this project

For the enrol and apply actions, the `next` destination is always a known internal URL
constructed by the server (e.g. the course enrol view URL generated from a course slug).
The user cannot inject a `next` value from the course detail page — the server constructs
it.

However, if the `next` parameter is ever read from `request.GET` and passed through to a
redirect, always validate it:

```python
from django.utils.http import url_has_allowed_host_and_scheme

def safe_next_url(request) -> str:
    next_url = request.GET.get("next", "")
    if next_url and url_has_allowed_host_and_scheme(
        url=next_url,
        allowed_hosts=request.get_host(),
        require_https=request.is_secure(),
    ):
        return next_url
    return settings.LOGIN_REDIRECT_URL
```

Additionally, use `django.utils.encoding.iri_to_uri()` on the path component of
untrusted URLs before passing to `HttpResponseRedirect`.

Django's `LoginView.success_url_allowed_hosts` attribute can be used to extend allowed
hosts for multi-domain setups without opening up arbitrary redirects:
Reference: https://docs.djangoproject.com/en/6.0/topics/auth/default/

CVE-2017-7233 is the historical Django open redirect vulnerability affecting the `next`
parameter — fixed since Django 1.11.2, but illustrates why validation is not optional.
Reference: https://www.acunetix.com/vulnerabilities/web/django-url-redirection-to-untrusted-site-open-redirect-vulnerability-cve-2017-7233/

---

## 6. Accessibility for Auth Prompts

### Modal login dialog requirements (if modal is chosen)

W3C WAI-ARIA authoring practices for dialogs (https://www.w3.org/WAI/ARIA/apg/patterns/dialog-modal/examples/dialog/)
specify:

- `role="dialog"` on the container element.
- `aria-modal="true"` so screen readers treat background content as inert.
- `aria-labelledby` pointing to the dialog's heading (e.g. "Create a free account to enrol").
- `aria-describedby` pointing to supplementary content if needed.
- On open: move focus to the first interactive element (usually the email field) or the
  dialog heading if the first element is low in the content.
- Focus trap: Tab and Shift+Tab must cycle only within the dialog while it is open.
- Escape key closes the dialog and returns focus to the element that triggered it (the
  "Enrol for free" button).

Native HTML `<dialog>` element (opened with `.showModal()`) provides built-in focus
trapping, Escape handling, and correct ARIA semantics and is recommended for new
implementations.
Reference: https://testparty.ai/blog/modal-dialog-accessibility

### Screen reader announcement of the auth requirement

Whether using a modal or full-page redirect, the heading of the auth screen must clearly
state why the user is here. "Log in" alone is insufficient — add the context: "Log in or
create a free account to enrol in [Course Name]". This heading is announced by screen
readers on page load (full-page) or focus move (modal).

### Full-page redirect accessibility considerations

A full-page redirect is generally more accessible than a modal for login flows because:
- The page title and `<h1>` communicate context unambiguously on load.
- No focus trap management required.
- Back button behaviour is standard and predictable.
- Screen reader virtual cursor does not need to be constrained.

If the auth is triggered by a button that submits a form (e.g. the enrol button is a POST
form), use `aria-busy="true"` on the button after click to indicate processing, then let
the redirect happen naturally.

### Keyboard focus on return

After successful login (full-page redirect back to the course detail or enrol confirmation),
the page loads normally and focus lands at the top of the document. This is acceptable; no
special focus management is needed for the post-login page.

---

## Summary: Key Actionable Recommendations for FLS

1. **Use action-forward CTAs**: "Enrol for free" and "Apply now" on course detail pages.
   Do not mention the login requirement in the button label itself.

2. **Full-page redirect for auth**: Redirect to a login/signup page (not a modal) with a
   heading that restates the user's intent. Lower implementation risk, more accessible.

3. **Thread `next` through signup AND login**: The `next` URL must be preserved as a
   hidden field in both the login and signup forms, and honoured in both success handlers.
   Django's `LoginView` handles login; the signup view must be coded explicitly.

4. **Make the enrol view idempotent and action-completing**: When an authenticated user
   hits the enrol URL (after being redirected there via `next`), the view should perform
   the enrolment and redirect to course content — not display a "you need to enrol" page
   that requires a second click.

5. **Show course type before the CTA**: Free vs application-gated should be visually
   distinct (badge or label) so the user knows what happens after they click the CTA.

6. **Validate `next` URLs**: Any view that accepts a `next` parameter from `request.GET`
   must validate it with `url_has_allowed_host_and_scheme` and restrict to same-host paths.

7. **Do not show partially-filled application forms to anonymous users**: Show a preview
   or summary of what the form requires, prompt login, then render the form for the
   authenticated user.

8. **Test the new-user signup path explicitly**: The lost-intent problem is most common
   for new users. Confirm that after registration, a new user lands on the enrolment
   confirmation (or course content), not a generic welcome page.

---

## Reference URLs

- Django auth documentation (LoginView, next param, success_url_allowed_hosts):
  https://docs.djangoproject.com/en/6.0/topics/auth/default/
- NN/G on login walls: https://www.nngroup.com/articles/login-walls/
- NN/G on optional registration: https://www.nngroup.com/articles/optional-registration/
- Authgear login/signup UX guide 2025: https://www.authgear.com/post/login-signup-ux-guide/
- Corbado: guest checkout vs forced login (conversion stats):
  https://www.corbado.com/blog/guest-checkout-vs-forced-login
- SaaS signup flow UX (30-70% drop from early login walls):
  https://www.letsgroto.com/blog/saas-signup-flow-ux
- W3C WAI-ARIA modal dialog pattern:
  https://www.w3.org/WAI/ARIA/apg/patterns/dialog-modal/examples/dialog/
- TestParty: accessible modal dialogs:
  https://testparty.ai/blog/modal-dialog-accessibility
- StackHawk: Django open redirect guide:
  https://www.stackhawk.com/blog/django-open-redirect-guide-examples-and-prevention/
- Django open redirect CVE-2017-7233:
  https://www.acunetix.com/vulnerabilities/web/django-url-redirection-to-untrusted-site-open-redirect-vulnerability-cve-2017-7233/
- Django forum: url_has_allowed_host_and_scheme discouraged:
  https://forum.djangoproject.com/t/why-is-the-use-of-url_has_allowed_host_and_scheme-discouraged/35314
- Coursera enrol help: https://learner.coursera.help/hc/en-us/articles/209818603-Enroll-in-a-course
- LearnDash auto-enrol on registration:
  https://docs.wpuserregistration.com/docs/user-registration-learndash/
- Eleken: effective sign-up flows: https://www.eleken.co/blog-posts/sign-up-flow

status: ok
