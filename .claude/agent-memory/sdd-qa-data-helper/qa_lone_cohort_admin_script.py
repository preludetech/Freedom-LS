# Run through manage.py shell; printing the state is the whole output.
# ruff: noqa: T201
from django.contrib.contenttypes.models import ContentType
from django.contrib.sites.models import Site

from freedom_ls.accounts.models import User
from freedom_ls.learner_management.models import Cohort, CohortMembership, StaffMember
from freedom_ls.organisations.models import Organisation
from freedom_ls.qa_helpers.management.commands.qa_create_cohort_administration_scenario import (
    _ensure_cohort,
)
from freedom_ls.qa_helpers.management.commands.qa_create_organisation_scenarios import (
    _pin_current_site,
    _site_context,
)
from freedom_ls.qa_helpers.management.commands.qa_create_staff_administration_scenario import (
    _ensure_user,
)
from freedom_ls.role_based_permissions.models import ObjectRoleAssignment
from freedom_ls.role_based_permissions.utils import assign_object_role

site = Site.objects.get(name="DemoDev")
_pin_current_site(site)
with _site_context(site):
    su = User._base_manager.get(site=site, email="demodev@email.com", is_superuser=True)
    west = Organisation._base_manager.get(site=site, slug="westside")
    cw = _ensure_cohort(site, west, "Cohort W")
    ca = _ensure_user(site, "w.admin@qa.test", "Wanda", "Wadmin")
    assign_object_role(ca, cw, "cohort_admin", assigned_by=su)

    cohort_ct = ContentType.objects.get_for_model(Cohort)
    print(
        "COHORT W",
        cw.pk,
        "active",
        cw.is_active,
        "org",
        cw.organisation.slug,
        "site",
        cw.site_id,
    )
    print(
        "CA",
        ca.pk,
        ca.email,
        ca.first_name,
        ca.last_name,
        "site",
        ca.site_id,
        "active",
        ca.is_active,
        "pw ok",
        ca.check_password(ca.email),
    )
    from allauth.account.models import EmailAddress

    print(
        "EMAIL",
        list(
            EmailAddress.objects.filter(user=ca).values_list(
                "email", "verified", "primary"
            )
        ),
    )
    print(
        "CA GRANTS (all, any site)",
        list(
            ObjectRoleAssignment._base_manager.filter(user=ca).values_list(
                "role", "content_type__model", "object_id", "is_active", "site_id"
            )
        ),
    )
    print(
        "CA STAFF ROWS",
        list(
            StaffMember._base_manager.filter(user=ca).values_list(
                "organisation__slug", "is_active"
            )
        ),
    )
    print(
        "COHORT W GRANTS",
        list(
            ObjectRoleAssignment._base_manager.filter(
                content_type=cohort_ct, object_id=str(cw.pk)
            ).values_list("user__email", "role", "is_active")
        ),
    )
    print("COHORT W LEARNERS", CohortMembership._base_manager.filter(cohort=cw).count())
    print(
        "WESTSIDE COHORTS",
        list(
            Cohort._base_manager.filter(organisation=west).values_list(
                "pk", "name", "is_active"
            )
        ),
    )
    print(
        "WESTSIDE STAFF",
        list(
            StaffMember._base_manager.filter(organisation=west).values_list(
                "user__email", "is_active"
            )
        ),
    )
