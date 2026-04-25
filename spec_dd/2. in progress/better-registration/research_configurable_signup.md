# Research: Configurable Signup Forms in Multi-Tenant Django

Research to inform the better-registration feature. Focused on practical Django/allauth patterns.

---

## 1. django-allauth Customisation (v65.x+)

### Field control
- `ACCOUNT_SIGNUP_FIELDS` controls which fields appear on signup — but this is a **global setting**, not per-site
- `ACCOUNT_FORMS = {"signup": "yourapp.forms.CustomSignupForm"}` lets you swap in a custom form class
- The existing `AccountAdapter.save_user()` in FLS already handles `first_name`/`last_name` persistence

### Custom form approach
The standard pattern is to subclass `allauth.account.forms.SignupForm` and override `custom_signup()`. The form can read site-specific config at `__init__` time to decide which fields to show.

### References
- [allauth configuration docs](https://docs.allauth.org/en/latest/account/configuration.html)
- [allauth SignupForm source](https://github.com/pennersr/django-allauth/blob/main/allauth/account/forms.py)

---

## 2. Per-Tenant Configuration Approaches

### Option A: Settings-based (per-site Django settings)
- Use different settings files or environment variables per site
- **Pro**: Simple, no DB overhead
- **Con**: Requires deployment changes to update; doesn't scale for many tenants

### Option B: Database-driven (model-based) ✅ Recommended for FLS
- A `SiteRegistrationConfig` model with boolean toggles for each optional field
- **Pro**: Configurable at runtime via admin, fits FLS's existing `SiteAwareModel` pattern
- **Con**: Slightly more complex initial setup
- **Precedent**: FLS already has `SiteSignupPolicy` — this is the same pattern extended

### Option C: Hybrid
- Use settings for defaults, DB overrides per site
- **Pro**: Works out of the box, customisable where needed
- **Con**: Two places to look for config

**Recommendation**: Option B. FLS already uses `SiteAwareModel` everywhere and has `SiteSignupPolicy` as a direct precedent. Database-driven config is the natural fit.

---

## 3. Common Configurable Fields

| Field | Notes |
|---|---|
| **First name / Last name** | Already on User model. Toggle whether required at signup |
| **T&C acceptance** | Needs its own auditable record (not just a form field) |
| **Phone number** | allauth has built-in phone support. Would need new model field |
| **Organisation** | Would need new model field on User or a related model |

For FLS's immediate needs, only **name fields** and **T&C acceptance** are required. Phone and organisation are future possibilities.

---

## 4. Recommended Implementation Pattern

### Model: Extend SiteSignupPolicy or create SiteRegistrationConfig

```
SiteRegistrationConfig (extends SiteAwareModel):
    require_name          Boolean, default=False
    require_terms_acceptance  Boolean, default=False
    # Future: require_phone, require_organisation, custom_fields JSON
```

**Consider merging with `SiteSignupPolicy`** since that model already controls per-site signup behaviour. Adding fields to it avoids a second config model.

### Form: Dynamic field injection

```python
class CustomSignupForm(SignupForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        config = get_site_registration_config(self.request)
        if config.require_name:
            self.fields["first_name"] = CharField(required=True)
            self.fields["last_name"] = CharField(required=True)
        if config.require_terms_acceptance:
            self.fields["terms_accepted"] = BooleanField(required=True)
```

### Template: Conditional rendering
The template renders whatever fields the form contains — no conditional logic needed in the template itself if the form handles field injection.

---

## 5. Key Advice

- **Don't build a dynamic form builder.** Fixed toggleable fields cover the requirements without the complexity of arbitrary custom fields
- **Don't over-engineer.** Start with name + T&C toggles. Add more fields only when needed
- The existing `SiteAwareModel` + adapter patterns make this straightforward
- The allauth `ACCOUNT_FORMS` setting is the right hook — no need to override views

### References
- [django-allauth custom signup forms](https://docs.allauth.org/en/latest/account/forms.html)
- [Multi-tenant Django patterns — Lincoln Loop](https://lincolnloop.com/insights/multi-tenant-django/)
