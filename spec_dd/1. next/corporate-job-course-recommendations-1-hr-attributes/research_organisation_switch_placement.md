# Research: where the organisation-level "registration rules" switch lives

## Recommendation (findings first)

Put the switch in a **one-to-one settings model in `learner_management`** (working name `OrganisationRegistrationSettings`: `organisation` one-to-one, `registration_rules_enabled` boolean default False, site-aware). **No row means off.** Show it as a single-row inline on the Organisation change page, using the seam `learner_management` already uses. Do not add a column to `Organisation`, and do not wait for the rules app.

Reasons rooted in app boundaries:

1. `organisations` is a low-level app: it depends only on `base` and `site_aware_models` at runtime (`docs/app_structure.md`, row `organisations`). Its admin says it "must stay installable without" the apps that own an organisation's objects (comment on `ORGANISATION_SUMMARIES` in `freedom_ls/organisations/admin.py`). A "registration rules" boolean on `Organisation` would bake a learner-management concept into that app. `Organisation` today holds only name, slug, two logos and `is_default` (`freedom_ls/organisations/models.py`). Nothing in it is feature-specific.
2. `learner_management` already depends on `organisations` (`learner_management --> organisations`). It owns the attributes and lists in spec 1, so the switch sits with the data it gates. No new cross-app edge is needed, and `docs/app_structure.md` needs no regeneration for the edge.
3. The rules app (spec 2) will need `learner_management` anyway, to create `LearnerCourseRegistration`. It can read the switch with no new edge. Spec 2 can be an optional app: with it removed, the settings row is harmless and inert, and `organisations` carries no dead column.
4. The rules app cannot own the switch. It does not exist until spec 2, and spec 1 must create the switch. It also may be omitted from INSTALLED_APPS, which would then remove the switch from the admin.
5. The admin seam already exists. `learner_management/admin.py` (~lines 663-674) does `OrganisationAdmin.inlines = [*OrganisationAdmin.inlines, ...]` and `ORGANISATION_SUMMARIES.append(...)`. A new inline follows the established path.

## Options compared

| Option | Pros | Cons / migration |
|---|---|---|
| A. Boolean on `Organisation` | Simplest read (`org.registration_rules_enabled`), one query less, trivially editable in the existing admin form. | Wrong direction of knowledge: `organisations` would know about a feature of a higher app. Migration lands in `organisations` (`0002`), shipped to every downstream even when it never uses rules. Each future per-org toggle repeats this. Needs a field added to `OrganisationAdminForm.Meta.fields` and the admin `fields` list. Dead column if the rules app is omitted. |
| B. Settings row in the rules app | Best cohesion with the rules. | Impossible for spec 1 (app is created in spec 2). If the app is optional, the switch and the admin vanish with it. |
| C. One-to-one settings model in `learner_management` (recommended) | Respects dependency direction. Migration is in `learner_management`, next to the HR attribute migrations spec 1 already adds there. Room for more per-organisation settings later (a natural home beside the lists). No-row-means-off matches the `SiteSignupPolicy` idiom. | One extra query to read it. Needs an explicit "no row" path. Needs a unique constraint and a site-consistency check. |
| D. Feature-flag library (django-waffle) | Admin-managed, cached lookups, rollout tooling. | FLS uses none today (research_fls_backends_and_toggles.md, section 2). Waffle has no native tenant notion; per-tenant use needs a custom flag model chosen before the first migration. A new dependency for downstream projects. Overkill for a stable per-organisation entitlement. |

## Codebase precedent

- `accounts.SiteSignupPolicy` (`freedom_ls/accounts/models.py:141`) is a `SiteAwareModel, TimestampedModel` one-to-one per site (`UniqueConstraint(fields=["site"], name="unique_signup_policy_per_site")`). Docstring: with no row, a global default applies. Its factory uses `django_get_or_create = ("site",)`. That is the template for C. The difference here is that the default is hard-coded off.
- No organisation-level toggle exists (research_fls_backends_and_toggles.md, section 2), so C sets the precedent. It extends the per-Site policy-row idiom down one level.
- `organisations` shows how FLS ships: apps are installable independently, and `blog` and `course_applications` are optional. Downstream projects take `migrate` for every installed FLS app, so a migration in `organisations` touches all of them, while one in `learner_management` only touches installs that already have it (every install).

## Implementation notes for the spec

- Model: `OrganisationRegistrationSettings(SiteAwareModel, TimestampedModel)`, `organisation = OneToOneField(Organisation, on_delete=CASCADE, related_name="registration_settings")`, `registration_rules_enabled = BooleanField(default=False)`. Follow `fls-dev:multi-tenant`: the row's `site` must match the organisation's site (inherit from the organisation on save, or validate).
- Read helper in `learner_management/utils.py`, e.g. `registration_rules_enabled(organisation) -> bool`, returning False when no row exists. Spec 2's evaluation task has no request, so it must read through `_base_manager` or filter explicitly by site, as `ensure_learner` does.
- Do not create rows in a `post_save` receiver on `Organisation`. The lazy row avoids backfilling existing organisations in a data migration, keeps off the default, and the existing `Site` receiver (`organisations/signals.py`) needs no change.
- Spec 1 must not make anything read the switch. Add a test that the default is off and that attributes save with it off.

## Where it shows in the admin

- On the Organisation change page (`OrganisationAdmin`), as a `StackedInline` of the settings model, `max_num=1`, `can_delete=False`, titled for example "Registration rules". Appended from `learner_management/admin.py` next to the existing inline, so it appears on the change page only (`get_inlines` already hides inlines on the add page).
- An inline with a boolean default False and an untouched form does not create a row, so no-row-means-off holds even after visiting the page.
- Optional: a read-only line in `ORGANISATION_SUMMARIES` showing "Registration rules: on/off". Not required.
- Not as a standalone ModelAdmin. A separate list page would only add a place to get lost.

## Web sources

- django-waffle flag docs, including the custom flag model for non-user targets and the note that the Flag model cannot be changed without breaking migrations: https://waffle.readthedocs.io/en/stable/types/flag.html
- Open edX Enterprise decision record on feature flags (cost of adding boolean fields to the customer model, move to waffle managed in the admin): https://open-edx-enterprise-service-documentation.readthedocs.io/en/stable/decisions/0012-enterprise-feature-flags-waffle.html
- django-feature-flags (flag groups on a tenant model, mapped to flags defined in settings): https://pypi.org/project/django-feature-flags
- Common rule of thumb drawn from these: a tenant field or plan row for stable per-tenant entitlements, a flag library for rollouts and short-lived toggles. The switch here is a stable per-organisation entitlement, so a library is not warranted. This is a synthesis from a search summary, not a quoted claim.

status: ok
