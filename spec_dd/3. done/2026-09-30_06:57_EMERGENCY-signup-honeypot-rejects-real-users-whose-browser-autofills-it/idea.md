# Idea: the signup honeypot rejects real people whose browser or password manager autofills it

## The bug

Source: this downstream project's production site. A real person (the site owner) could not
create an account. Every submit of the signup form came back with one error under the
"Last name" input and nothing else:

```
Submission could not be processed.
```

The message comes from the honeypot in `SiteAwareSignupForm`
(`freedom_ls/accounts/forms.py`):

```python
_hp = forms.CharField(
    required=False,
    widget=forms.TextInput(
        attrs={
            "style": "position:absolute; left:-9999px;",
            "tabindex": "-1",
            "autocomplete": "off",
            "aria-hidden": "true",
        }
    ),
    label="",
)

def clean__hp(self) -> str:
    value = self.cleaned_data.get("_hp", "")
    if value:
        # Generic message — do not reveal which field tripped.
        raise forms.ValidationError(_("Submission could not be processed."))
    return str(value)
```

Four things combine to lock people out:

1. **The field is off-screen, not hidden.** `position:absolute; left:-9999px` leaves it a
   focusable text input. Chrome's autofill and password managers (Bitwarden, 1Password, etc.)
   fill focusable fields whether or not they are on screen. Chrome ignores `autocomplete="off"`
   for address/name autofill.
2. **It has no label and comes straight after `last_name`.** Autofill works out what a field is
   from its name, label and nearby text. `_hp` has no label, so the nearest text is "Last name:",
   and the field gets classified as another last-name field and filled with the person's surname.
3. **The user can't recover.** The error names nothing they can act on, and the field they would
   need to clear can't be seen. Retrying autofills it again. The only way through is to turn
   autofill off, which nobody will guess.
4. **Nothing is logged.** `clean__hp` raises without logging, so production logs don't show real
   people being rejected. We found it only because the site owner tried to sign up.

The error shows under "Last name" because `account/signup.html` prints each field's first error
just before that field, looping over `form.visible_fields`. The `_hp` error is printed where the
off-screen `_hp` input sits, right after `last_name`.

CSP is not involved. The downstream project runs `SECURE_CSP_REPORT_ONLY` with `unsafe-inline`
for styles, so the inline style is applied. It works exactly as written.

### How to confirm

On the signup page, let the browser autofill the name/email fields, then in DevTools inspect
`input[name="_hp"]` before submitting. It holds a value, usually the surname.

## Impact

Any FLS site with the default signup form. The people it hits are exactly the ones who use
autofill or a password manager, and that is most people on a signup form. They see a meaningless
error and leave. Nothing in the logs shows it happened.

## Expected fix

### 1. Hide the honeypot so autofill skips it

Use `display:none` instead of moving the field off-screen. Chrome and the major password
managers don't fill inputs that can't be focused (`display:none` or `visibility:hidden`),
but scrapers and scripted bots that fill every `<input>` in the HTML still fill it.

- Keep `type="text"`. Many bots skip `type="hidden"`.
- Put the `display:none` on a wrapper element, not on the input's own inline style, so it
  doesn't depend on inline styles being allowed if FLS ever enforces a CSP without
  `unsafe-inline` for styles. A Tailwind `hidden` class or the HTML `hidden` attribute on the
  wrapper both work.
- Keep `tabindex="-1"`, `autocomplete="off"` and `aria-hidden="true"`.

### 2. Give the field a name that autofill won't match

Rename `_hp` to something autofill has no profile value for. It shouldn't match any name,
address, contact, company or URL field. This downstream project learned that the hard way on its
own lead forms (`apps/lead_forms/forms.py`): **`website`/`url` get autofilled by Safari from the
contact card**, so it uses `fax_number`. Something like `fax_number` or `extra_reference` works.
Give it a label that doesn't match an autofill field either (e.g. "Leave this field empty"). That
removes the "inherits the Last name label" failure even if the hiding in step 1 is ever undone.

### 3. Render it as a hidden field, outside the visible-field loop

`signup.html` loops over `form.visible_fields` and never prints `form.hidden_fields`. The
downstream lead form uses a widget that reports `is_hidden = True`, so the honeypot lands in
`form.hidden_fields`. The template prints it bare, inside a hidden wrapper, with no label and no
per-field error slot:

```python
class HoneypotInput(forms.TextInput):
    """A text input that people never see and bots fill in.

    Reports itself as hidden so it lands in `form.hidden_fields`. Still
    `type="text"`: bots skip `type="hidden"`.
    """

    @property
    def is_hidden(self) -> bool:
        return True
```

```django
<div hidden>
    {% for field in form.hidden_fields %}{{ field }}{% endfor %}
</div>
```

Check that nothing else allauth adds to the signup form is a hidden field that now renders in a
different place.

### 4. Raise the error at form level, and render form-level errors

Move the check from `clean__hp` to `clean()` and raise a non-field error, so the message doesn't
land under whichever visible field comes before the honeypot. `signup.html` doesn't print
`form.non_field_errors` at the moment, so add that at the top of the form body. Without it, any
non-field error from allauth or FLS is dropped silently and the page just re-renders. That's
worse than the current bug.

The wording should give a real person a way forward and still not say which check tripped.
For example: "We couldn't process this sign-up. If you used autofill or a password manager,
please try typing your details in by hand."

### 5. Log every trip

Log at `WARNING` when the honeypot trips, with the site domain and client IP, and without the
submitted email or field value (PII / log injection). Then false positives in production show up
in the logs, not as sign-ups that quietly stop coming in.

## Tests

- **Regression, rendering:** the rendered signup page's honeypot input sits inside an element
  that is `display:none` / `hidden`, not merely off-screen. Assert on the rendered HTML: the
  input is inside a `hidden` wrapper and has no `left:-9999px` style.
- **Regression, naming:** the honeypot's `name` isn't one browsers autofill. Keep an explicit
  denylist in the test (`name`, `first_name`, `last_name`, `email`, `website`, `url`,
  `homepage`, `company`, `organization`, `phone`, `tel`, `address`, anything starting with an
  underscore next to a name field, and so on) so a later rename can't bring the bug back.
- **Existing behaviour kept:** a filled honeypot still creates no user (update
  `test_honeypot_rejects_submission_when_filled` for the new field name), and now also puts the
  error in `form.non_field_errors()`, not on a field.
- **Logging:** a filled honeypot logs one `WARNING` that contains neither the email nor the
  honeypot value (`caplog`).
- **Template:** a form with a non-field error renders that error on the signup page.
- **Playwright (optional, `playwright` marker):** fill the visible fields as a person would and
  submit. The account is created. That covers the whole path the bug broke.

## Downstream workaround in place

None yet. Affected users can get through by typing their details by hand in a private window
with extensions turned off. Once the FLS fix lands, pull the submodule and check a real signup
on production with Chrome autofill and a password manager both turned on.
