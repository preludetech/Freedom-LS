# Idea: the header's Login and Sign up links forget the page the visitor was on

## The bug

Source: this downstream project's mega QA run on 2026-10-28 (ACCT-5).

1. As an anonymous visitor open `/courses/rpc-fixed-wing-aeroplane/detail/`.
2. Click the header's "Sign up". Sign up and verify the email.

Expected: back on the course detail page.

Actual: the learner lands on `/`. The header links are a bare `/accounts/signup/` and
`/accounts/login/` on the home page, `/courses/`, every course detail page and articles. Only on
the login and signup pages themselves, where the URL already has `?next=`, do they carry it.

## Cause

`partials/login_prompt.html` (`freedom_ls/base/templates/partials/login_prompt.html:2,7`) builds
both links with `url_with_next`. That tag (`accounts/templatetags/accounts_tags.py:17-35`) only
passes through a `next` the request already has, via allauth's `passthrough_next_redirect_url`.
It never uses the current page.

## Suggested fix

In the header, fall back to the current path when the request has no `next`. Leave the link bare
on the home page and on `/accounts/` pages, where coming back is either the default or a loop.
That could be a new tag, or a flag on `url_with_next`. The signup page's in-form links rely on
the pass-through behaviour, so don't change it for them.

## Downstream workaround

The project's `templates/partials/login_prompt.html` uses `url_back_here`, a tag in
`apps/project_setup/templatetags/auth_link_tags.py` that does the fallback above and otherwise
delegates to `url_with_next`.
