# Research: Theming Patterns in Pluggable Django Packages

Context: FLS is a Django 6 + Tailwind v4 + HTMX + django-cotton LMS distributed as a dependency. Downstream projects ("Bloom", "FirstClass") need to rebrand without forking. Below are the patterns that mature Django libraries use, ranked by relevance to FLS.

## 1. django-allauth — settings-pointed class swapping + template path override

**Mechanism.** Two layers stacked:
- `ACCOUNT_FORMS = {"login": "myapp.forms.MyLoginForm", ...}` swaps form classes by dotted path. The same idea is used for adapters (`ACCOUNT_ADAPTER`) and signup views.
- Templates are overridden by Django's standard template loader: a downstream `templates/account/login.html` wins over `allauth/templates/account/login.html` because `APP_DIRS` searches project dirs first.

**Downstream cost.** Cheap for class swaps (one settings key, subclass the original). Template overrides require copying the upstream template and editing — the standard "override one, own it forever" tax.

**Brittleness.** Form-class swaps are fairly stable across versions because the contract is explicit. Template overrides are brittle: when allauth restructures `base.html` or adds new context, copies drift silently. Allauth mitigates this by keeping templates small and using lots of `{% block %}`s and partial includes (e.g. `account/password_reset_help_text.html`) — extension points rather than override points.

**Theme directory?** No. There is no allauth concept of "a theme is a folder you select".

## 2. Wagtail — hooks + template block extension, no theme dirs

**Mechanism.** `wagtail.admin.hooks` is a pub/sub registry. Branding is done through specific hook names: `insert_global_admin_css`, `insert_global_admin_js`, `get_avatar_url`, plus template overrides for `wagtailadmin/admin_base.html`, `wagtailadmin/login.html`, branding partials (`branding_logo.html`, `branding_login.html`, `branding_favicon.html`).

**Downstream cost.** Add a small app, register hooks in `wagtail_hooks.py`, drop replacement partials in `templates/wagtailadmin/`. No "switch theme" toggle — branding is additive.

**Brittleness.** Hooks are versioned API and survive upgrades well. Template partials are deliberately tiny (logo, favicon) so overriding them rarely breaks. Wagtail explicitly does *not* expose deep CSS variables or theme bundles — projects inject CSS files via the hook.

**Theme directory?** No.

## 3. django-oscar — fork-the-app + dynamic class loading

**Mechanism.** `oscar_fork_app` copies an app into the project; Oscar's `get_class()` loader resolves classes by walking `INSTALLED_APPS` and picking the first match. This means a forked `myproject.catalogue` shadows `oscar.apps.catalogue` for *every* class lookup (views, forms, strategies, models).

**Downstream cost.** High. You take ownership of an app even if you only wanted to change one template. Migrations, models, and admin all become yours.

**Brittleness.** Famously high — Oscar upgrades require diffing your fork against upstream. The pattern is powerful for deep customisation but inappropriate for *just* theming.

**Theme directory?** No, the opposite — code-level forking.

## 4. Mezzanine — closest thing to drop-in theme directories

**Mechanism.** A theme is a regular Django app containing only `templates/` and `static/`, listed at the top of `INSTALLED_APPS`. Django's `app_directories` template loader resolves the theme's templates first. Switching themes is "swap the entry in INSTALLED_APPS". Themes can chain (a child theme inheriting from a parent by listing both).

**Downstream cost.** Low if a suitable theme exists; theme is just files.

**Brittleness.** Same drift problem as any template override — themes pin to a Mezzanine version.

**Theme directory?** Yes — this is the prior art FLS should study most closely.

## 5. Saleor / django-CMS — out of scope but worth a note

Saleor is now headless: theming happens in the Next.js storefront via Tailwind CSS custom properties (design tokens) — irrelevant to a server-rendered Django package. django-CMS uses `CMS_TEMPLATES` to register selectable page templates, plus plugin-level template overrides; it's a content-author choice, not a brand-rebranding mechanism.

## Patterns that survive Tailwind + django-cotton

Tailwind v4 changes the cost model. Compiled CSS means a downstream theme cannot just "drop in classes" — the build needs to see the markup. Two patterns survive:

1. **CSS custom properties as the theme contract.** Ship FLS components using semantic Tailwind classes bound to CSS variables (`bg-[--color-surface]`, `rounded-[--radius-card]`). A theme is then a single CSS file setting variables — no Tailwind rebuild needed downstream. This is the Saleor design-token pattern, and is the most robust against upstream evolution.

2. **Cotton component overrides via template loader order.** Because `django-cotton` resolves `<c-button>` from `templates/cotton/button.html`, a theme app placed first in `INSTALLED_APPS` can replace any FLS cotton component wholesale (Mezzanine pattern, applied to components). `<c-vars>` defaults give a lighter touch: components ship with overridable defaults (`<c-vars theme="bg-surface rounded-card" />`) consumers can pass per-call.

3. **Allauth-style class swapping for non-visual extension** (form classes, adapters, scoring strategies) — orthogonal to theming but the same architectural idea.

**Recommendation outline for FLS.** Combine (a) Mezzanine-style theme-app dirs that win the template loader race, (b) CSS-variable-driven Tailwind tokens so non-structural rebrands need zero template copying, and (c) keep cotton components small and block-rich (allauth lesson) so partial overrides stay viable. Avoid the Oscar fork-the-app path entirely — it's the wrong cost shape for branding.

## References

- django-allauth forms: https://docs.allauth.org/en/latest/account/forms.html
- django-allauth templates: https://docs.allauth.org/en/dev/common/templates.html
- django-allauth source `templates/account/`: https://github.com/pennersr/django-allauth/tree/main/allauth/templates/account
- django-oscar customisation: https://django-oscar.readthedocs.io/en/latest/topics/customisation.html
- Wagtail hooks reference: https://docs.wagtail.org/en/stable/reference/hooks.html
- Wagtail admin templates: https://docs.wagtail.org/en/stable/extending/admin_templates.html
- Mezzanine themes (community): https://github.com/renyi/mezzanine-themes
- Mezzanine FAQ on themes: https://mezzanine.readthedocs.io/en/latest/frequently-asked-questions.html
- Mezzanine theming walkthrough: https://bitofpixels.com/blog/mezzatheming-creating-mezzanine-themes-part-1-basehtml/
- Saleor storefront (design tokens via CSS variables): https://github.com/saleor/storefront
- django-cotton components & `<c-vars>`: https://django-cotton.com/docs/components
- django-cotton usage patterns (COTTON_DIR, loader order): https://django-cotton.com/docs/usage-patterns
- Django template loader resolution order: https://docs.djangoproject.com/en/5.2/ref/templates/api/#django.template.loaders.app_directories.Loader
