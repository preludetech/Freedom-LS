from allauth.account.models import EmailAddress

from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import make_password
from django.contrib.sites.models import Site
from django.db import transaction

from freedom_ls.learner_management.models import Learner
from freedom_ls.learner_management.utils import ensure_learner
from freedom_ls.organisations.models import Organisation

User = get_user_model()
site = Site.objects.get(name="DemoDev")
org = Organisation._base_manager.get(site=site, slug="demodev")
pw_hash = make_password("testpass123")
created = 0
with transaction.atomic():
    for i in range(1, 211):
        email = f"qa_bulk_{i:03d}@email.com"
        user, was_created = User.objects.get_or_create(
            email=email,
            site=site,
            defaults={
                "first_name": f"qa_bulk_{i:03d}",
                "last_name": "",
                "is_active": True,
                "password": pw_hash,
            },
        )
        created += was_created
        EmailAddress.objects.update_or_create(
            user=user, email=email, defaults={"verified": True, "primary": True}
        )
        ensure_learner(user, org)
qs = Learner._base_manager.filter(site=site, organisation=org)
print("users created this run:", created)  # noqa: T201
print(  # noqa: T201
    "qa_bulk learners:",
    qs.filter(user__email__startswith="qa_bulk_", is_active=True).count(),
)
print(  # noqa: T201
    "org learners total / active:", qs.count(), qs.filter(is_active=True).count()
)
print(  # noqa: T201
    "qa_bulk cohort memberships:",
    qs.filter(
        user__email__startswith="qa_bulk_", cohortmembership__isnull=False
    ).count(),
)
