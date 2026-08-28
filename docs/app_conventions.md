# App conventions

Rules every `freedom_ls/<app>` follows, and the exemptions that apply to a specific,
named set of apps rather than to the codebase in general. Where a rule has an
enforcement test, this file names it — treat the test as the definition and this
file as the summary.

---

## App labels: `freedom_ls_<app>`

Every FLS app sets `label = "freedom_ls_<app>"` on its `AppConfig`. This is what keeps
FLS's tables, and its system-check ids, distinct from a downstream project's own apps
once FLS is installed alongside them. `webhooks`, for instance, carries
`label = "freedom_ls_webhooks"`, so its tables are `freedom_ls_webhooks_*` rather than
the `webhooks_*` a plain Django app of that name would produce.

`freedom_ls/contrib/conformance/tests/test_app_labels.py` enforces this across every
installed FLS app. An app that has a genuine reason to skip the prefix is added to
`UNPREFIXED_LABEL_ALLOWLIST` in that file, not silently left unlabelled.

### The extractable-app exemption

An app is **extractable** when a spec has committed it to leaving `freedom_ls/` as its
own installable package, independent of FLS. Extractable apps may skip the label
prefix and the `SiteAwareModel` base described below. Both are permitted, not
required, and an extractable app is exempt from nothing else: it still may not import
from a host FLS app, since after extraction that import would no longer resolve.
Dependency direction always points from the host into the app, never back.

Today's extractable apps: `icons` (on its way to becoming the standalone
`django_semantic_iconify` package), `markdown_rendering`, and the planned
`referral-link-tracker`. `markdown_rendering` already carries
`freedom_ls_markdown_rendering` and keeps it, since renaming it twice buys nothing.
`icons` is the only app actually taking the bare-label exemption today, which is why
it's the only entry in `UNPREFIXED_LABEL_ALLOWLIST`.

Neither `icons` nor `markdown_rendering` defines a model yet, so the `SiteAwareModel`
half of the exemption is untested in practice: it exists so that when
`referral-link-tracker` (or either of the other two) does add a model, that model can
stay a plain `django.db.models.Model` instead of pulling in FLS's own
`site_aware_models` app, which an extracted package cannot depend on.

## System-check ids match the app's own label

A system check's id is `<label>.<severity><number>` where `<label>` is whatever that
app's `AppConfig.label` actually is, not the `freedom_ls_<app>` form other apps use.
`icons` registers checks as `icons.E001`, `icons.E002`, and so on, because `icons`'
own label is bare `icons`; `deployment` registers `freedom_ls_deployment.E001` because
that's its label. Get this wrong and Django's `SILENCED_SYSTEM_CHECKS` can't target the
check by id, since the id it's silencing doesn't match the id the check actually
raises.

## The `"site"` constraint spelling

A `UniqueConstraint` scoped by tenant names the field `"site"`, not `"site_id"`. Both
work with Django's ORM, but only one of them survives contact with
`ConstraintValidationFormMixin` for free.

`SiteAwareModelAdmin` excludes `site` from every admin form, and
`UniqueConstraint.validate()` drops a constraint entirely as soon as one of its own
fields sits in that exclusion set. A constraint spelled `fields=["site", ...]` matches
the excluded `"site"` and needs `ConstraintValidationFormMixin` to reach form
validation at all; `fields=["site_id", ...]` happens not to match that string and
would validate without it, but it's also the wrong spelling for the codebase's own
convention. Spell it `"site"`, and any model with a live admin form takes
`ConstraintValidationFormMixin` (`freedom_ls/site_aware_models/forms.py`) so the
constraint's errors land on the form instead of surfacing as an `IntegrityError` 500
at the database. `freedom_ls/organisations/forms.py` and
`freedom_ls/learner_management/forms.py` are worked examples.

## `default_auto_field` on every model-defining app

Every FLS app that defines models sets `default_auto_field` on its `AppConfig`, so a
downstream project's own `DEFAULT_AUTO_FIELD` setting can't retroactively change what
FLS's `makemigrations` generates for FLS's own models. In practice this only changes
behaviour for the two models that don't extend `SiteAwareModel` and so don't already
declare their own primary key: `accounts.User` and
`role_based_permissions.SystemRoleAssignment`. Every other concrete model extends
`SiteAwareModel`, which declares its own UUID primary key directly and so is
unaffected either way. Set it anyway, on every app that defines models, rather than
reasoning case by case about which ones need it.

## Generic foreign key `object_id` type

A generic foreign key's `object_id` field is a `UUIDField` when the set of models it
can point at is closed and every one of them uses a UUID primary key, which is the
case for every content and deadline GFK in the codebase. It's `CharField(max_length=255)`
in exactly one place, `ObjectRoleAssignment.object_id`
(`freedom_ls/role_based_permissions/models.py`), because the set of models a role can
be scoped to is deliberately open and can't be pinned to one pk type in advance.

Match whichever of those two situations a new GFK is actually in. Don't default to
`CharField` because it accepts anything; that trades a real constraint for a
theoretical one, on a field where the codebase already has a closed-set answer almost
everywhere it appears.
