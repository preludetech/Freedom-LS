# ruff: noqa: T201
from django.contrib.contenttypes.models import ContentType

from freedom_ls.accounts.models import User
from freedom_ls.learner_management.models import Cohort, StaffMember
from freedom_ls.organisations.models import Organisation
from freedom_ls.role_based_permissions.models import ObjectRoleAssignment

org_ct = ContentType.objects.get_for_model(Organisation)
coh_ct = ContentType.objects.get_for_model(Cohort)
for slug in ("northside", "westside"):
    org = Organisation._base_manager.filter(slug=slug).first()
    if org is None:
        print("NO ORG", slug)
        continue
    print("ORG", slug, org.pk, "site", org.site_id)
    cohorts = {str(c.pk): c.name for c in Cohort._base_manager.filter(organisation=org)}
    print(" cohorts", cohorts)
    for g in (
        ObjectRoleAssignment._base_manager.filter(
            content_type=org_ct, object_id=str(org.pk)
        )
        .select_related("user", "assigned_by")
        .order_by("user__email")
    ):
        print(
            "  ORG-GRANT",
            g.pk,
            g.user.email,
            g.role,
            "active" if g.is_active else "INACTIVE",
            "by",
            g.assigned_by.email if g.assigned_by else None,
        )
    for g in (
        ObjectRoleAssignment._base_manager.filter(
            content_type=coh_ct, object_id__in=list(cohorts)
        )
        .select_related("user", "assigned_by")
        .order_by("user__email")
    ):
        print(
            "  COH-GRANT",
            g.pk,
            g.user.email,
            cohorts[g.object_id],
            g.role,
            "active" if g.is_active else "INACTIVE",
            "by",
            g.assigned_by.email if g.assigned_by else None,
        )
    for s in (
        StaffMember._base_manager.filter(organisation=org)
        .select_related("user")
        .order_by("user__email")
    ):
        print("  STAFF", s.pk, s.user.email, s.is_active)
for e in (
    "existing2@qa.test",
    "brand.new@qa.test",
    "w.admin@qa.test",
    "w.cohortadmin@qa.test",
    "lone.admin@qa.test",
):
    print(
        "USER", e, list(User._base_manager.filter(email=e).values_list("pk", "site_id"))
    )
