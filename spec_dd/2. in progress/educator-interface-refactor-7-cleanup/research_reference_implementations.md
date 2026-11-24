# Research: reference implementations (module moves, old import paths, upgrade notes)

Scope: how mature Django projects handle moving code to new modules, the old import path, and the release note. Findings come from search-result summaries and release-note titles. I did not open the full pages, so verify specifics before quoting them in the spec.

## What the projects did

| Project | Move | Old path | Where it was documented |
|---|---|---|---|
| Wagtail 2.0 | Module paths shortened across the codebase | Removed. A `wagtail updatemodulepaths` command rewrote downstream imports. | Wagtail 2.0 release notes: "import lines ... will need to be updated" |
| Wagtail 3.0 | `wagtail.core.models` to `wagtail.models` | Kept temporarily so upgrades did not break at once. | 3.0 release notes and an "Upgrade considerations" section |
| Wagtail 8.0 (in development) | `wagtail.admin.signals.init_new_page` to `wagtail.signals`, `wagtail.telepath` to `wagtail.admin.telepath` | Removed, with the earlier deprecations from 6.4 to 7.3 | 8.0 release notes, a list of removed deprecated features |
| django-oscar 1.5 | Dashboard catalogue formsets to `dashboard.catalogue.formsets` | Not stated in the results. | Backwards-incompatible changes list, one named class per entry |
| django-oscar 2.0 | App config modules renamed from `config` to `apps` | Rename, no shim | 2.0 release notes |
| django-oscar 2.1 to 3.0 | Models moved from the customer app to the communication app | Old paths worked in 2.1. 3.0 removed dynamic loading from them. | 3.0 release notes |
| django-oscar 3.1 | `dashboard.catalogue.views.filter_products` function removed | Removed. The note points to `PartnerProductFilterMixin` methods. | 3.1 release notes |
| Django 1.7 | `django.views.defaults.shortcut` moved to `django.contrib.contenttypes.views.shortcut` | Deprecated first, then removed | Deprecation timeline |
| Django 2.0 | `django.conf.urls.url()` is now `django.urls.re_path()` | Kept, no removal date | 2.0 release notes |
| Django 2.1 | `contrib.auth.views.login()` and similar function views | Removed after the deprecation period | 2.2 deprecation timeline |

## Patterns

1. **Two policies, chosen by who imports the path.** Libraries and frameworks with many downstream subclassers (Wagtail, Oscar, Django) usually deprecate first, or keep the old path for a release, and remove it later. A project with a few known callers can remove outright. Wagtail 2.0 and Oscar 2.0 did this, and Wagtail 2.0 added a rewrite command.
2. **The release note lists the exact new dotted path per moved name.** Oscar's 1.5 entry names each class and the new module. Wagtail's 8.0 entry gives old and new path pairs. This matches the idea's plan to list the new `panels.<area>.<module>` path for every public class.
3. **A "backwards incompatible" or "upgrade considerations" section holds the moves.** Wagtail also keeps a general upgrade guide that says to fix deprecation warnings before upgrading. FLS's "Breaking changes" and "Manual steps" headings play the same two roles.
4. **Where a shim exists, removal is a separate later note.** For example, the 2.1 to 3.0 Oscar move and the Wagtail 3.0 and 8.0 pair. With no shim there is one note and no follow-up. That is the idea's choice.
5. **A mechanical migration aid is optional.** Only Wagtail 2.0 shipped one, because the move touched most downstream code. Here the idea already tells projects to grep for old module paths. A shipped command is not warranted for one `educator_interface` package. First-Class-LMS only includes the URLconf.

## Implications for this spec

- No re-export shim is consistent with Wagtail 2.0 and Oscar 2.0, and with Django's removal of the 2.1 auth function views. The one-note-no-follow-up outcome is a known, accepted shape.
- Because there is no shim, the sweep and the note carry the full migration burden. The note should be a complete old-to-new table, since there is no deprecation warning to tell a downstream project what to change.
- State in the note that URL names, URL paths and template paths are unchanged. Oscar's and Wagtail's notes separate import-path changes from behaviour, and downstream readers look for that.
- The one-line grep recipe in "Manual steps" is the lightweight equivalent of Wagtail's `updatemodulepaths`.

## Sources

- https://docs.djangoproject.com/en/2.2/internals/deprecation/
- https://docs.djangoproject.com/en/1.11/internals/deprecation
- https://docs.djangoproject.com/en/dev/releases/2.0
- https://github.com/wagtail/wagtail/blob/v2.8/docs/releases/2.0.rst
- https://docs.wagtail.org/en/v7.4/releases/3.0.html.md
- https://thibaudcolas-wagtail.readthedocs.io/en/latest/releases/8.0.html.md
- https://docs.wagtail.org/en/v7.4/releases/upgrading.html.md
- https://django-oscar.readthedocs.io/en/3.1/releases/v1.5.html
- https://django-oscar.readthedocs.io/en/3.2/releases/v2.0.html
- https://django-oscar.readthedocs.io/en/3.2/releases/v3.0.html
- https://django-oscar.readthedocs.io/en/3.1/releases/v3.1.html

status: ok
