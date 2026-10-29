# Idea: the honeypot field re-renders its submitted value, so a person who trips it can never get through

## The bug

Source: this downstream project's mega QA run on 2026-10-28 (ACCT-1).

1. Open `/accounts/signup/` and fill in every visible field correctly.
2. Put any value in the hidden `fax_number` input. This stands in for the autofill or password
   manager case the error message is written for.
3. Submit. The form says: "We couldn't process this sign-up. If you used autofill or a password
   manager, please try typing your details in by hand."
4. Do what it says. Type the details by hand and submit again.

Expected: the retry succeeds, because the honeypot comes back empty.

Actual: every retry is rejected. The error page re-renders the hidden input with its value:

```html
<input type="text" name="fax_number" value="Smith" tabindex="-1" autocomplete="off" aria-hidden="true" id="id_fax_number">
```

The person can't see the field, so they can't clear it. The advice in the message can't work.

The same thing happens on the anonymous application flow. `ApplicantDetailsForm` and
`ApplicantEmailForm` (`course_applications/forms.py:38` and `:124`) both use `honeypot_field()`,
and their templates render `form.hidden_fields`
(`course_applications/templates/course_applications/applicant_details.html:32`,
`partials/claim_link_notice.html:92`). Rendering a bound form built from `honeypot_field()` in a
shell gives the output above.

## Cause

`HoneypotInput` (`freedom_ls/accounts/forms.py:46`) subclasses `forms.TextInput` and doesn't
change how it renders, so it renders the bound value like any text input. `honeypot_field()`
(`accounts/forms.py:70`) is shared by the signup form and both application forms.

## Suggested fix

Make the widget never render a value:

```python
class HoneypotInput(forms.TextInput):
    def format_value(self, value):
        return None
```

Add a test that binds a form with `fax_number` filled, renders it, and asserts the input has no
`value` attribute. Cover the signup form and `ApplicantDetailsForm`.

## Downstream workaround

`apps/project_setup/forms.py` defines `BlankHoneypotInput` (the override above) and a
`SignupForm` that swaps it in. `ACCOUNT_FORMS` in `config/settings_base.py` points at that form.
This only fixes signup. The project can't reach the application forms, so anonymous applicants
who trip the honeypot are still stuck.
