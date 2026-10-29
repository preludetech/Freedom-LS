# Idea: the profile form lets a learner blank the first name that signup requires

## The bug

Source: this downstream project's mega QA run on 2026-10-28 (ACCT-2).

1. Log in as a learner on a site that requires a name at signup (the default).
2. Open `/accounts/profile/`. Clear First name, or set it to spaces. Save.

Expected: "This field is required." on First name.

Actual: "Profile saved". `first_name` is stored as `''`. The dashboard then reads "Welcome back,
qa-acct-5@email.com", the avatar initials become "QA", and the user menu's label uses the email.
Certificates and educator views read the same name.

A second, smaller problem: `edit_profile` re-renders the page on a successful POST instead of
redirecting, so a refresh resubmits the form.

## Cause

`UserForm` (`freedom_ls/accounts/forms.py:30-35`) is a plain `ModelForm` on
`["first_name", "last_name"]`. The model field allows blanks
(`accounts/models.py:75`, `blank=True`), so the form does too. Signup declares
`first_name = forms.CharField(max_length=200, required=True)` (`forms.py:199`) and then applies
`apply_signup_name_policy` (`forms.py:113-121`). The profile form does neither.

`edit_profile` (`accounts/views.py:30-41`) calls `render` after `form.save()`.

## Suggested fix

- Declare `first_name` on `UserForm` the way signup does and call `apply_signup_name_policy` with
  the request's policy, so the two forms agree. Django's `CharField` strips whitespace, so
  spaces-only fails too.
- Redirect to the profile page after a successful save (the message survives the redirect).

## Downstream workaround

None.
