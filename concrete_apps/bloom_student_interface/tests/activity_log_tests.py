import pytest
from django.urls import reverse
from datetime import date, timedelta
from bloom_student_interface.models import Child, ActivityLog


@pytest.fixture
def child(user, mock_site_context):
    """Create a test child."""
    dob = date.today() - timedelta(days=365 * 4)
    return Child.objects.create(
        user=user, name="Test Child", date_of_birth=dob, gender="female"
    )


@pytest.fixture
def bloom_urlconf(settings, site):
    """Configure URLconf and SITE_ID for Bloom site."""
    from django.urls import include, path
    from config.urls import urlpatterns as base_urlpatterns

    # Set SITE_ID to the Bloom site so Django uses it
    settings.SITE_ID = site.id

    # Create URLconf similar to what SiteURLConfMiddleware does for Bloom site
    test_urlpatterns = base_urlpatterns + [
        path("", include("bloom_student_interface.urls")),
    ]

    # Temporarily set ROOT_URLCONF to use our test patterns
    from types import ModuleType
    import sys

    module = ModuleType("_test_bloom_urlconf")
    module.urlpatterns = test_urlpatterns
    sys.modules["_test_bloom_urlconf"] = module

    settings.ROOT_URLCONF = "_test_bloom_urlconf"

    yield

    # Cleanup
    if "_test_bloom_urlconf" in sys.modules:
        del sys.modules["_test_bloom_urlconf"]


@pytest.mark.parametrize("site", ["Bloom"], indirect=True)
@pytest.mark.django_db
@pytest.mark.usefixtures("bloom_urlconf")
class TestActionChildActivityToggle:
    """Test the action_child_activity_toggle view."""

    def test_full_toggle_cycle(self, client, user, child, activity, mock_site_context):
        """Test complete toggle cycle: None -> True -> False -> None -> True."""
        client.force_login(user)
        test_date = "2025-11-25"

        url = reverse(
            "bloom_student_interface:action_child_activity_toggle",
            kwargs={
                "child_slug": child.slug,
                "activity_slug": activity.slug,
                "date": test_date,
            },
        )

        # First toggle: None -> True
        response = client.post(url)
        log = ActivityLog.objects.get(
            child=child, activity=activity, date=date(2025, 11, 25)
        )
        assert log.done is True

        # Second toggle: True -> False
        response = client.post(url)
        log.refresh_from_db()
        assert log.done is False

        # Third toggle: False -> None
        response = client.post(url)
        log.refresh_from_db()
        assert log.done is None

        # Fourth toggle: None -> True (back to start)
        response = client.post(url)
        log.refresh_from_db()
        assert log.done is True

    def test_only_allows_own_children(
        self, client, user, child, activity, mock_site_context
    ):
        """Test that users can only toggle activity logs for their own children."""
        from django.contrib.auth import get_user_model

        User = get_user_model()

        # Create another user
        other_user = User.objects.create(
            email="other@example.com",
            site=mock_site_context,
            is_active=True,
        )
        other_user.set_password("testpass")
        other_user.save()

        # Login as other user
        client.force_login(other_user)

        test_date = "2025-11-25"
        url = reverse(
            "bloom_student_interface:action_child_activity_toggle",
            kwargs={
                "child_slug": child.slug,
                "activity_slug": activity.slug,
                "date": test_date,
            },
        )

        response = client.post(url)

        # Should return 404 because child doesn't belong to other_user
        assert response.status_code == 404
