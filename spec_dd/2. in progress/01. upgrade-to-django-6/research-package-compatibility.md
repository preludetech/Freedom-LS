# Django 6.0 Package Compatibility Research

**Research date:** 2026-03-10
**Django 6.0 released:** 2025-12-03
**Django 6.0 latest patch:** 6.0.3 (2026-03-03)
**Python support:** 3.12, 3.13, 3.14

---

## 1. django-allauth (headless mode)

- **Current constraint:** `>=65.13.0`
- **Latest version:** 65.14.1 (2026-02-07)
- **Django 6 support:** Yes, since v65.13.1 (2025-11-20)
- **Status:** Fully compatible. No migration steps required beyond updating the package version.
- **Action:** Update constraint to `>=65.14.0` when upgrading to Django 6.
- **References:**
  - [PyPI](https://pypi.org/project/django-allauth/)
  - [Requirements docs](https://docs.allauth.org/en/latest/installation/requirements.html)
  - [Release notes](https://docs.allauth.org/en/dev/release-notes/recent.html)

---

## 2. django-cotton

- **Current constraint:** `>=2.1.3,<2.5`
- **Latest version:** 2.6.1
- **Django 6 support:** Yes. Supports Django >4.2, <7.0.
- **Status:** Fully compatible. The upper bound constraint `<2.5` will need to be relaxed to pick up the latest version.
- **Migration steps:** Update constraint to `>=2.5,<3` or similar. Review changelog for any breaking changes in 2.5+.
- **References:**
  - [PyPI](https://pypi.org/project/django-cotton/)
  - [GitHub](https://github.com/wrabit/django-cotton)
  - [Releases](https://github.com/wrabit/django-cotton/releases)

---

## 3. django-guardian

- **Current constraint:** `>=3.2.0`
- **Latest version:** 3.3.0 (2026-02-24)
- **Django 6 support:** Likely yes. Supports Django 4.2+ and Python 3.9+. Version 3.3.0 was released after Django 6.0 and likely includes compatibility.
- **Status:** Should work. Verify by checking classifiers on the 3.3.0 release.
- **Action:** Update to `>=3.3.0` when upgrading.
- **References:**
  - [PyPI](https://pypi.org/project/django-guardian/)
  - [GitHub](https://github.com/django-guardian/django-guardian)
  - [Releases](https://github.com/django-guardian/django-guardian/releases)
  - [Docs](https://django-guardian.readthedocs.io/)

---

## 4. django-ninja

- **Current constraint:** `>=1.4.3`
- **Latest version:** 1.5.3 (2026-01-10)
- **Django 6 support:** Yes. PyPI classifiers list Django 3.1 through 6.0.
- **Status:** Fully compatible. No known issues.
- **Action:** Update constraint to `>=1.5.0` when upgrading.
- **References:**
  - [PyPI](https://pypi.org/project/django-ninja/)
  - [GitHub](https://github.com/vitalik/django-ninja)
  - [Docs](https://django-ninja.dev/)

---

## 5. django-unfold

- **Current constraint:** `>=0.67.0`
- **Latest version:** 0.83.1 (2026-03-05)
- **Django 6 support:** Yes. Supports Django 4.2, 5.0, 5.1, 5.2, and 6.0. Requires Python 3.11+.
- **Status:** Fully compatible. Actively maintained with frequent releases.
- **Action:** Update constraint to `>=0.83.0` when upgrading.
- **References:**
  - [PyPI](https://pypi.org/project/django-unfold/)
  - [GitHub releases](https://github.com/unfoldadmin/django-unfold/releases)
  - [Docs](https://unfoldadmin.com/)

---

## 6. django-template-partials

- **Current constraint:** `>=25.2`
- **Latest version:** 25.2 (or later)
- **Django 6 support:** Yes, but **Django 6.0 includes template partials natively in core**.
- **Status:** MAJOR CHANGE. Template partials are now built into Django 6.0. The third-party package is no longer needed.
- **Migration steps:**
  1. Remove `"template_partials"` (or `"template_partials.apps.SimpleAppConfig"`) from `INSTALLED_APPS`
  2. Remove any manual loader configuration for template partials
  3. Remove `{% load partials %}` from all templates (partials are now built-in)
  4. The internal storage key changed from `extra_data["template-partials"]` to `extra_data["partials"]` in Django 5.1+ for forward compatibility
  5. Uninstall the `django-template-partials` package
  6. Follow the official [Migration Guide](https://github.com/carltongibson/django-template-partials/blob/main/Migration.md)
- **Action:** Remove dependency entirely and migrate to Django's native partials support.
- **References:**
  - [PyPI](https://pypi.org/project/django-template-partials/)
  - [GitHub](https://github.com/carltongibson/django-template-partials)
  - [Migration Guide](https://github.com/carltongibson/django-template-partials/blob/main/Migration.md)
  - [Changelog](https://github.com/carltongibson/django-template-partials/blob/main/CHANGELOG.md)
  - [Django 6.0 release notes](https://docs.djangoproject.com/en/6.0/releases/6.0/)

---

## 7. django-storages[s3]

- **Current constraint:** `>=1.14.6`
- **Latest version:** 1.14.6 (latest stable as of research date)
- **Django 6 support:** Not explicitly confirmed in classifiers. The package generally supports "currently supported versions of Django" per its docs. Likely works but not formally declared.
- **Status:** Probably compatible but needs verification. The package is actively maintained and has historically tracked Django releases. Test thoroughly.
- **Risk:** Low-to-medium. The storage backend API has been stable across Django versions.
- **Action:** Test with Django 6. Check for a newer release closer to upgrade time.
- **References:**
  - [PyPI](https://pypi.org/project/django-storages/)
  - [GitHub](https://github.com/jschneier/django-storages)
  - [Changelog](https://github.com/jschneier/django-storages/blob/master/CHANGELOG.rst)
  - [Docs](https://django-storages.readthedocs.io/)

---

## 8. heroicons[django]

- **Current constraint:** `>=2.13.0,<3`
- **Latest version:** 2.13.0
- **Django 6 support:** Yes. Supports Django 4.2 to 6.0 and Python 3.9 to 3.14.
- **Status:** Fully compatible. No migration steps required.
- **Action:** No constraint changes needed. Current constraint already covers the latest version.
- **References:**
  - [PyPI](https://pypi.org/project/heroicons/)
  - [GitHub](https://github.com/adamchainz/heroicons)
  - [Changelog](https://github.com/adamchainz/heroicons/blob/main/CHANGELOG.rst)

---

## 9. django-premailer

- **Current constraint:** `>=0.2.0`
- **Latest version:** 0.2.0 (last release: 2016-06-20)
- **Django 6 support:** No. Officially supports Django 1.6-1.9 only. Package is unmaintained (no updates since 2016).
- **Status:** HIGH RISK. The package has not been updated in nearly 10 years. It relies on the `premailer` library underneath, which is still maintained. However, `django-premailer` itself is a thin wrapper (template tag) that may still work despite outdated classifiers.
- **Migration options:**
  1. Test if `django-premailer` 0.2.0 works with Django 6 despite lack of official support (it is a simple wrapper)
  2. Use the `premailer` library directly without the Django wrapper
  3. Consider `django-inlinecss` as an alternative
  4. Fork and maintain `django-premailer` if the template tag is essential
- **Action:** Test with Django 6. If it breaks, switch to using `premailer` directly or fork the package.
- **References:**
  - [PyPI](https://pypi.org/project/django-premailer/)
  - [GitHub](https://github.com/alexhayes/django-premailer)
  - [premailer (underlying library)](https://pypi.org/project/premailer/)

---

## 10. django-debug-toolbar (dev)

- **Current constraint:** `>=6.1.0`
- **Latest version:** 6.2.0 (2026-01-20)
- **Django 6 support:** Yes. Requires Django >= 4.2.0. Django 6.0 is in the testing matrix.
- **Status:** Fully compatible. Has experimental async view support.
- **Action:** Update constraint to `>=6.2.0` when upgrading.
- **References:**
  - [PyPI](https://pypi.org/project/django-debug-toolbar/)
  - [GitHub](https://github.com/django-commons/django-debug-toolbar)
  - [Changelog](https://django-debug-toolbar.readthedocs.io/en/latest/changes.html)
  - [Docs](https://django-debug-toolbar.readthedocs.io/)

---

## 11. django-browser-reload (dev)

- **Current constraint:** `>=1.21.0`
- **Latest version:** 1.21.0+ (supports Django 4.2 to 6.0)
- **Django 6 support:** Yes. Includes Django 6-specific enhancements: on Django 6.0+ with `ContentSecurityPolicyMiddleware`, the script tag automatically includes the CSP nonce.
- **Status:** Fully compatible with Django 6-specific improvements.
- **Action:** No constraint changes likely needed.
- **References:**
  - [PyPI](https://pypi.org/project/django-browser-reload/)
  - [GitHub](https://github.com/adamchainz/django-browser-reload)

---

## 12. django-stubs (dev)

- **Current constraint:** `>=5.2.9`
- **Latest version:** 5.2.9 (2026-01-20)
- **Django 6 support:** Partial. Django 6.0 stubs are unreleased and have incomplete coverage. Many new Django 6.0 APIs are missing stubs. Changes to existing APIs are not yet fully covered.
- **Status:** MEDIUM RISK. The stubs will work but won't provide type coverage for new Django 6 features. The project is actively working on Django 6 support.
- **Migration steps:**
  1. Watch for a django-stubs 6.x release that provides full Django 6 stubs
  2. In the interim, some Django 6 APIs will lack type information
  3. May need to use `type: ignore` comments temporarily for new Django 6 APIs (conflicts with project convention of no `type: ignore`)
- **Action:** Wait for django-stubs 6.0 release before upgrading, or accept partial type coverage initially.
- **References:**
  - [PyPI](https://pypi.org/project/django-stubs/)
  - [GitHub](https://github.com/typeddjango/django-stubs)
  - [Releases](https://github.com/typeddjango/django-stubs/releases)

---

## 13. django-watchfiles (dev)

- **Current constraint:** `>=1.4.0`
- **Latest version:** 1.4.0 (supports Django 4.2 to 6.0)
- **Django 6 support:** Yes. Fully compatible.
- **Status:** No issues. Actively maintained with sustainable release cadence.
- **Action:** No constraint changes needed.
- **References:**
  - [PyPI](https://pypi.org/project/django-watchfiles/)
  - [GitHub](https://github.com/adamchainz/django-watchfiles)

---

## Summary

| Package | Django 6 Ready | Risk | Action Required |
|---|---|---|---|
| django-allauth | Yes | Low | Update version constraint |
| django-cotton | Yes | Low | Relax upper bound constraint |
| django-guardian | Likely | Low | Verify 3.3.0 classifiers |
| django-ninja | Yes | Low | Update version constraint |
| django-unfold | Yes | Low | Update version constraint |
| django-template-partials | N/A | Medium | **Remove package, migrate to Django core partials** |
| django-storages[s3] | Unconfirmed | Low-Medium | Test, check for newer release |
| heroicons[django] | Yes | Low | No changes needed |
| django-premailer | No | **High** | Test or replace with `premailer` directly |
| django-debug-toolbar | Yes | Low | Update version constraint |
| django-browser-reload | Yes | Low | No changes needed |
| django-stubs | Partial | Medium | Wait for 6.0 stubs release |
| django-watchfiles | Yes | Low | No changes needed |

### Key Concerns

1. **django-template-partials** - Must be removed and migrated to Django 6 native partials. This is the most involved migration step but is well-documented.
2. **django-premailer** - Unmaintained since 2016. Needs testing or replacement.
3. **django-stubs** - Incomplete Django 6 type coverage. May delay full upgrade or require temporary workarounds.
4. **django-storages** - Likely works but lacks formal Django 6 declaration. Low risk given stable storage API.
