import pytest
from datetime import date, timedelta
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.utils import timezone
from playwright.sync_api import Page
from urllib.parse import urlparse
from allauth.account.models import EmailAddress
from content_engine.models import Form

from bloom_student_interface.models import (
    Child,
    CommittedActivity,
    ActivityLog,
    ChildFormProgress,
)
from content_engine.models import Activity
from student_progress.models import FormProgress

User = get_user_model()


def reverse_url(
    live_server, viewname, urlconf=None, args=None, kwargs=None, current_app=None
):
    end = reverse(viewname, urlconf, args, kwargs, current_app)
    return f"{live_server.url}{end}"


@pytest.fixture
def live_server_site(live_server, site):
    # Update site domain to match the live_server
    parsed_url = urlparse(live_server.url)
    site.domain = parsed_url.netloc
    site.save()
    return site


@pytest.fixture
def picky_eating_form(live_server_site):
    # Create the picky eating form that the children view expects
    form, created = Form.objects.get_or_create(
        slug="picky-eating",
        defaults={
            "title": "Picky Eating Assessment",
            "strategy": "CATEGORY_VALUE_SUM",
            "site": live_server_site,
        },
    )
    return form


@pytest.fixture
def logged_in_page(
    page: Page, live_server, user, db, live_server_site, picky_eating_form
):
    """Create a logged in page with a verified email address."""

    # Set the user's email as verified (required for allauth)
    # Use get_or_create to avoid duplicate email addresses
    EmailAddress.objects.get_or_create(
        user=user, email=user.email, defaults={"verified": True, "primary": True}
    )

    # Navigate to login page
    login_url = reverse_url(live_server, "account_login")
    page.goto(login_url)

    # Fill in login form
    page.fill('input[name="login"]', user.email)
    page.fill('input[name="password"]', "testpass")

    # Submit the form
    page.click('button[type="submit"]')

    # Wait for navigation to complete
    page.wait_for_load_state("networkidle")

    yield page


@pytest.mark.django_db
def test_committed_activity_displays_correctly(
    live_server, logged_in_page: Page, user, mock_site_context, picky_eating_form
):
    """Test that committed activities and activity logs display correctly on the frontend."""

    # Create a child for the logged in user
    child = Child.objects.create(
        user=user, name="Test Child", date_of_birth=date(2020, 1, 1), gender="female"
    )

    form_progress = FormProgress.objects.create(
        user=user, form=picky_eating_form, completed_time=timezone.now()
    )
    ChildFormProgress.objects.create(child=child, form_progress=form_progress)

    # Create an activity
    activity = Activity.objects.create(
        title="Test Activity",
        slug="test-activity",
        description="A test activity for the child",
    )

    # Create a committed activity
    committed_activity = CommittedActivity.objects.create(
        child=child, activity=activity
    )

    # Create activity logs
    today = timezone.now().date()
    yesterday = today - timedelta(days=1)
    day_before_yesterday = today - timedelta(days=2)
    three_days_ago = today - timedelta(days=3)

    # Yesterday: good with notes
    ActivityLog.objects.create(
        child=child,
        activity=activity,
        date=yesterday,
        done=True,
        sentiment="good",
        notes="Had a great time!",
    )

    # Day before yesterday: bad with no notes
    ActivityLog.objects.create(
        child=child,
        activity=activity,
        date=day_before_yesterday,
        done=True,
        sentiment="bad",
        notes="",
    )

    # Three days ago: neutral with notes
    ActivityLog.objects.create(
        child=child,
        activity=activity,
        date=three_days_ago,
        done=True,
        sentiment="neutral",
        notes="It was okay",
    )

    # Navigate to the child's activities page
    activities_url = reverse_url(
        live_server,
        "bloom_student_interface:child_activities_configure",
        kwargs={"slug": child.slug},
    )
    logged_in_page.goto(activities_url)

    # Wait for the page to load
    logged_in_page.wait_for_load_state("networkidle")

    # Assert that the activity is visible
    activity_title = logged_in_page.get_by_test_id(
        f"committed-activity-title-{activity.slug}"
    )
    assert activity_title.is_visible()

    # Yesterday: good with notes
    # => yesterday should show a thumbs up icon

    # Day before yesterday: bad with no notes
    # => show a thumbs down icon

    # Three days ago: neutral with notes
    # => show a check
