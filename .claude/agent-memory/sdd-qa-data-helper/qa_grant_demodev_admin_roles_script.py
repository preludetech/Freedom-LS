# ruff: noqa: T201 -- a manage.py shell script whose output is printed for the QA operator

from django.contrib.sites.models import Site

from freedom_ls.accounts.models import User
from freedom_ls.content_engine.models import Course
from freedom_ls.learner_management.models import (
    CohortMembership,
    Learner,
    OrganisationMember,
)
from freedom_ls.learner_management.utils import ensure_organisation_member
from freedom_ls.organisations.models import Organisation
from freedom_ls.organisations.utils import get_default_organisation
from freedom_ls.qa_helpers.management.commands.qa_create_organisation_scenarios import (
    _pin_current_site,
    _site_context,
)
from freedom_ls.role_based_permissions.models import (
    ObjectRoleAssignment,
    SiteRoleAssignment,
)
from freedom_ls.role_based_permissions.utils import assign_object_role, assign_site_role

site = Site.objects.get(name="DemoDev")
_pin_current_site(site)
u = User._base_manager.get(email="demodev@email.com")
org = get_default_organisation(site)
with _site_context(site):
    assign_site_role(u, "site_admin", assigned_by=u, site=site)
    assign_object_role(u, org, "organisation_admin", assigned_by=u)
    ensure_organisation_member(u, org)
print("site", site.pk, site.name, site.domain)
print(
    "user",
    u.pk,
    u.email,
    "superuser",
    u.is_superuser,
    "staff",
    u.is_staff,
    "site",
    u.site.name,
    "pw ok",
    u.check_password("demodev@email.com"),
)
print(
    "site roles",
    list(
        SiteRoleAssignment._base_manager.filter(user=u).values_list(
            "role", "site__name", "is_active"
        )
    ),
)
print(
    "obj roles",
    list(
        ObjectRoleAssignment._base_manager.filter(user=u).values_list(
            "role", "object_id", "is_active"
        )
    ),
)
print(
    "org members",
    list(
        OrganisationMember._base_manager.filter(user=u).values_list(
            "organisation__slug", "is_active"
        )
    ),
)
for o in Organisation._base_manager.filter(site=site):
    print(
        "org",
        o.pk,
        o.name,
        o.slug,
        "default",
        o.is_default,
        "learners",
        Learner._base_manager.filter(organisation=o).count(),
    )
for learner in (
    Learner._base_manager.filter(organisation=org)
    .select_related("user")
    .order_by("user__email")[:3]
):
    print(
        "learner",
        learner.pk,
        learner.user.email,
        learner.is_active,
        list(
            CohortMembership._base_manager.filter(learner=learner).values_list(
                "cohort__name", flat=True
            )
        ),
    )

print("courses on DemoDev", Course._base_manager.filter(site=site).count())
