# Research: Terms & Conditions Acceptance During Registration

Research to inform the better-registration feature. Focused on practical patterns.

---

## 1. Legal Requirements — What to Store

When a user accepts T&Cs, the following must be recorded to satisfy GDPR (Art. 7) and POPIA requirements:

| Field | Why |
|---|---|
| **User identifier** | Link consent to the specific account (email, user ID) |
| **Timestamp** | When consent was given (UTC). Required by GDPR Art. 7(1) to "demonstrate that the data subject consented" |
| **T&C version** | Which exact version they agreed to. Critical when terms change |
| **IP address** | Supporting evidence of consent origin. Optional but recommended |
| **Consent method** | How consent was obtained (e.g. "signup_checkbox", "re-consent_banner") |

### GDPR specifics
- Consent must be "freely given, specific, informed and unambiguous" (Art. 4(11))
- Controller must be able to *demonstrate* consent was obtained (Art. 7(1))
- Pre-ticked boxes do NOT constitute valid consent
- Consent for T&Cs must be separate from consent for data processing / marketing
- Users must be able to withdraw consent as easily as they gave it
- Fines: up to 4% of annual global revenue

### POPIA specifics (South Africa)
- Similar "informed, voluntary, specific" consent requirements
- Must be able to produce consent records on request
- Fines up to ZAR 10 million
- POPIA and GDPR are broadly aligned; a system compliant with GDPR will largely satisfy POPIA

### References
- [GDPR Consent Requirements — gdpr.eu](https://gdpr.eu/gdpr-consent-requirements/)
- [7 Criteria for GDPR-Compliant Consent — Usercentrics](https://usercentrics.com/knowledge-hub/7-criteria-for-a-gdpr-compliant-consent/)
- [GDPR vs POPIA — Michalsons](https://www.michalsons.com/blog/gdpr-mean-popi-act/19959)
- [Records of Consent — Complianz](https://complianz.io/records-of-consent/)

---

## 2. UX Patterns

### Checkbox (clickwrap) vs click-through (browsewrap)

| Approach | Enforceability | UX friction |
|---|---|---|
| **Clickwrap** (unchecked checkbox + "I agree") | Strong — clear affirmative action | Higher — extra click |
| **Sign-in wrap** ("By signing up you agree to...") | Moderate — accepted by some courts | Lower — no extra action |
| **Browsewrap** (link in footer, no action required) | Weak — often unenforceable | None |

**Recommendation: Use clickwrap (checkbox).** It is the most legally defensible and required under GDPR.

### Practical UX guidelines

- Checkbox must be **unchecked by default** (GDPR requirement)
- T&C text should be a **hyperlink** that opens in a new tab or modal — do not force users to scroll through the full text inline
- Keep the label short: `I agree to the [Terms and Conditions]` with a link
- **Separate checkboxes** for T&Cs vs privacy policy vs marketing consent — do not bundle
- Place the checkbox **directly above the submit button** on the signup form
- Show a clear validation error if the user tries to submit without checking
- Common complaint: walls of legal text at signup. Solve with a link, not inline text

### References
- [The "I Agree" Checkbox — WebsitePolicies](https://www.websitepolicies.com/blog/i-agree-terms-and-conditions)
- [Clickwrap Best Practices — TermsFeed](https://www.termsfeed.com/blog/clickwrap-best-practices/)
- ["Agree to Terms" Checkbox Examples — Termly](https://termly.io/resources/articles/agree-to-terms-and-conditions-checkbox/)
- [10 Tips for T&C UX — IxDF](https://www.interaction-design.org/literature/article/10-tips-for-improving-the-ux-of-your-terms-and-conditions)

---

## 3. Versioning & Re-consent

### How versioning works in practice

1. Each T&C document has a **slug** (identifier) and a **version number**
2. When terms are updated, a new version is created (old versions are preserved)
3. User acceptance is recorded against a specific version
4. When a new version becomes active, users who accepted an older version are flagged for re-consent

### Re-consent flow options

| Approach | Description | When to use |
|---|---|---|
| **Blocking banner/modal** | User must accept new terms before continuing to use the app | Major term changes, legally required |
| **Non-blocking notification** | Banner informing users of changes, with a grace period | Minor updates, courtesy changes |
| **Next-login prompt** | Show acceptance form on next login | Good middle ground |

### Grace periods
- Common practice: give users 30 days to accept updated terms
- After the grace period, block access until acceptance
- Always email users when terms change, linking to a diff or summary of changes

### Data model sketch (informed by django-termsandconditions)

```
TermsAndConditions:
    slug            (e.g. "site-terms", "privacy-policy")
    version_number  (decimal)
    name            (display name)
    text            (full content, or URL to content)
    date_active     (when this version becomes the current one)
    date_created

UserTermsAndConditions:
    user            (FK to User)
    terms           (FK to TermsAndConditions)
    date_accepted   (timestamp)
    ip_address      (optional, configurable)
```

### References
- [django-termsandconditions — GitHub](https://github.com/cyface/django-termsandconditions)
- [django-termsandconditions — ReadTheDocs](https://django-termsandconditions.readthedocs.io/)

---

## 4. Django/allauth Integration Patterns

### Adding a T&C checkbox to allauth signup

The standard pattern for adding custom fields to allauth signup:

**1. Create a custom form:**

```python
from django import forms
from allauth.account.forms import SignupForm

class CustomSignupForm(SignupForm):
    terms_accepted = forms.BooleanField(
        required=True,
        label='I agree to the <a href="/terms/">Terms and Conditions</a>',
    )

    def custom_signup(self, request, user):
        # Record the acceptance in UserTermsAndConditions
        # Access: self.cleaned_data["terms_accepted"]
        # Also capture: request.META.get("REMOTE_ADDR") for IP
        pass
```

**2. Register in settings:**

```python
ACCOUNT_FORMS = {
    "signup": "yourapp.forms.CustomSignupForm",
}
```

**3. Override the signup template** to render the new field.

### Key considerations
- The `custom_signup()` method is called by allauth after the user is created — this is where you save the acceptance record
- The `BooleanField(required=True)` ensures Django validates the checkbox is checked before form submission
- The IP address can be captured from `request.META.get("REMOTE_ADDR")` or `request.META.get("HTTP_X_FORWARDED_FOR")`
- For FLS: the signup form customization should be done at the FLS level, not in consuming projects, but should be extensible

### References
- [Customizing Django Allauth Signup Forms — DEV Community](https://dev.to/danielfeldroy/customizing-django-allauth-signup-forms-2o1m)
- [django-allauth forms.py source — GitHub](https://github.com/pennersr/django-allauth/blob/main/allauth/account/forms.py)

---

## 5. Multi-tenant Considerations

FLS uses Django's Sites framework for multi-tenancy. Different sites will likely have different T&Cs.

### Requirements
- Each `TermsAndConditions` record should be **site-aware** (linked to a Site, or applicable to all sites)
- User acceptance should also be site-aware — a user accepting terms on Site A does not imply acceptance on Site B
- The signup form must dynamically load the correct T&C version for the current site
- Admin interface should allow managing T&Cs per site

### Suggested approach for FLS
- Make `TermsAndConditions` extend `SiteAwareModel` so it is automatically filtered by the current site
- `UserTermsAndConditions` should also be site-aware (or inherit site context from the linked terms)
- The allauth custom signup form should query `TermsAndConditions.objects.get_active()` which will automatically filter by site due to the site-aware manager
- Middleware for re-consent checks should respect site context

### Fallback pattern
- Allow a "default" T&C that applies when no site-specific version exists
- This lets FLS work out of the box without requiring every site to configure its own T&Cs

---

## Summary of Recommendations for FLS

1. **Use clickwrap** (unchecked checkbox) — it is the most legally defensible
2. **Store**: user, T&C version, timestamp, IP address, consent method
3. **Separate consents** for T&Cs vs privacy policy
4. **Version T&Cs** with a slug + version number model, linked to Sites
5. **Extend allauth signup** via `ACCOUNT_FORMS` + `custom_signup()` method
6. **Re-consent on version change** via middleware that checks accepted version against active version
7. **Make models site-aware** using FLS's existing `SiteAwareModel` pattern
