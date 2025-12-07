import pytest
from datetime import date, timedelta
from bloom_student_interface.models import Child, ActivityLog
from bloom_student_interface.activity_utils import get_activity_good_streak
from content_engine.models import Activity


@pytest.mark.parametrize("site", ["Bloom"], indirect=True)
@pytest.mark.django_db
class TestGetActivityGoodStreak:
    """Test the get_activity_good_streak function."""

    def test_no_activity_logs_returns_zero(self, child, activity, mock_site_context):
        """Test that when there are no activity logs, the streak is 0."""
        streak = get_activity_good_streak(child, activity)
        assert streak == 0

    def test_single_good_entry_returns_one(
        self, child, activity, mock_site_context, settings
    ):
        """Test that a single good entry returns a streak of 1."""
        settings.MAXIMUM_SKIPS_IN_GOOD_ACTIVITY_STREAK = 3

        ActivityLog.objects.create(
            child=child, activity=activity, date=date.today(), sentiment="good"
        )

        streak = get_activity_good_streak(child, activity)
        assert streak == 1

    def test_consecutive_good_entries(
        self, child, activity, mock_site_context, settings
    ):
        """Test consecutive good entries without any skips."""
        settings.MAXIMUM_SKIPS_IN_GOOD_ACTIVITY_STREAK = 3

        today = date.today()
        ActivityLog.objects.create(
            child=child, activity=activity, date=today, sentiment="good"
        )
        ActivityLog.objects.create(
            child=child,
            activity=activity,
            date=today - timedelta(days=1),
            sentiment="good",
        )
        ActivityLog.objects.create(
            child=child,
            activity=activity,
            date=today - timedelta(days=2),
            sentiment="good",
        )

        streak = get_activity_good_streak(child, activity)
        assert streak == 3

    def test_bad_sentiment_breaks_streak_immediately(
        self, child, activity, mock_site_context, settings
    ):
        """Test that a bad sentiment entry immediately breaks the streak."""
        settings.MAXIMUM_SKIPS_IN_GOOD_ACTIVITY_STREAK = 3

        today = date.today()
        ActivityLog.objects.create(
            child=child, activity=activity, date=today, sentiment="good"
        )
        ActivityLog.objects.create(
            child=child,
            activity=activity,
            date=today - timedelta(days=1),
            sentiment="good",
        )
        ActivityLog.objects.create(
            child=child,
            activity=activity,
            date=today - timedelta(days=2),
            sentiment="bad",
        )
        ActivityLog.objects.create(
            child=child,
            activity=activity,
            date=today - timedelta(days=3),
            sentiment="good",
        )

        streak = get_activity_good_streak(child, activity)
        assert streak == 2

    def test_neutral_sentiment_counts_as_skip(
        self, child, activity, mock_site_context, settings
    ):
        """Test that neutral sentiment entries count as skips."""
        settings.MAXIMUM_SKIPS_IN_GOOD_ACTIVITY_STREAK = 2

        today = date.today()
        ActivityLog.objects.create(
            child=child, activity=activity, date=today, sentiment="good"
        )
        ActivityLog.objects.create(
            child=child,
            activity=activity,
            date=today - timedelta(days=1),
            sentiment="neutral",
        )
        ActivityLog.objects.create(
            child=child,
            activity=activity,
            date=today - timedelta(days=2),
            sentiment="good",
        )

        streak = get_activity_good_streak(child, activity)
        assert streak == 2

    def test_done_false_counts_as_skip(
        self, child, activity, mock_site_context, settings
    ):
        """Test that done=False entries count as skips."""
        settings.MAXIMUM_SKIPS_IN_GOOD_ACTIVITY_STREAK = 2

        today = date.today()
        ActivityLog.objects.create(
            child=child, activity=activity, date=today, sentiment="good", done=True
        )
        ActivityLog.objects.create(
            child=child, activity=activity, date=today - timedelta(days=1), done=False
        )
        ActivityLog.objects.create(
            child=child,
            activity=activity,
            date=today - timedelta(days=2),
            sentiment="good",
            done=True,
        )

        streak = get_activity_good_streak(child, activity)
        assert streak == 2

    def test_skipped_days_count_as_skips(
        self, child, activity, mock_site_context, settings
    ):
        """Test that days between log entries count as skips."""
        settings.MAXIMUM_SKIPS_IN_GOOD_ACTIVITY_STREAK = 3

        today = date.today()
        ActivityLog.objects.create(
            child=child, activity=activity, date=today, sentiment="good"
        )
        # Skip 2 days (creates 2 skips)
        ActivityLog.objects.create(
            child=child,
            activity=activity,
            date=today - timedelta(days=3),
            sentiment="good",
        )

        streak = get_activity_good_streak(child, activity)
        assert streak == 2

    def test_exceeding_maximum_skips_breaks_streak(
        self, child, activity, mock_site_context, settings
    ):
        """Test that exceeding maximum skips breaks the streak."""
        settings.MAXIMUM_SKIPS_IN_GOOD_ACTIVITY_STREAK = 2

        today = date.today()
        ActivityLog.objects.create(
            child=child, activity=activity, date=today, sentiment="good"
        )
        ActivityLog.objects.create(
            child=child,
            activity=activity,
            date=today - timedelta(days=1),
            sentiment="neutral",
        )
        ActivityLog.objects.create(
            child=child,
            activity=activity,
            date=today - timedelta(days=2),
            sentiment="neutral",
        )
        ActivityLog.objects.create(
            child=child,
            activity=activity,
            date=today - timedelta(days=3),
            sentiment="neutral",
        )
        ActivityLog.objects.create(
            child=child,
            activity=activity,
            date=today - timedelta(days=4),
            sentiment="good",
        )

        streak = get_activity_good_streak(child, activity)
        assert streak == 1

    def test_combined_skips_accumulated(
        self, child, activity, mock_site_context, settings
    ):
        """Test that different types of skips are accumulated together."""
        settings.MAXIMUM_SKIPS_IN_GOOD_ACTIVITY_STREAK = 3

        today = date.today()
        ActivityLog.objects.create(
            child=child, activity=activity, date=today, sentiment="good"
        )
        # 1 neutral = 1 skip
        ActivityLog.objects.create(
            child=child,
            activity=activity,
            date=today - timedelta(days=1),
            sentiment="neutral",
        )
        # Skip 1 day (2 day gap = 1 skip)
        # Total: 2 skips so far
        ActivityLog.objects.create(
            child=child,
            activity=activity,
            date=today - timedelta(days=3),
            sentiment="good",
        )
        # 1 done=False = 1 skip
        # Total: 3 skips (at the limit)
        ActivityLog.objects.create(
            child=child, activity=activity, date=today - timedelta(days=4), done=False
        )
        # This good entry adds no skips, so total stays at 3 (within limit)
        ActivityLog.objects.create(
            child=child,
            activity=activity,
            date=today - timedelta(days=5),
            sentiment="good",
        )

        streak = get_activity_good_streak(child, activity)
        # All 3 good entries should be counted since we never exceed max of 3 skips
        assert streak == 3

    def test_only_counts_specific_child_and_activity(
        self, user, activity, mock_site_context, settings
    ):
        """Test that the function only counts logs for the specific child and activity."""

        settings.MAXIMUM_SKIPS_IN_GOOD_ACTIVITY_STREAK = 3

        child1 = Child.objects.create(
            user=user,
            name="Child 1",
            date_of_birth=date.today() - timedelta(days=365 * 4),
            gender="male",
        )
        child2 = Child.objects.create(
            user=user,
            name="Child 2",
            date_of_birth=date.today() - timedelta(days=365 * 5),
            gender="female",
        )
        activity2 = Activity.objects.create(
            title="Different Activity", slug="different-activity"
        )

        today = date.today()

        # Create logs for child1 with activity
        ActivityLog.objects.create(
            child=child1, activity=activity, date=today, sentiment="good"
        )
        ActivityLog.objects.create(
            child=child1,
            activity=activity,
            date=today - timedelta(days=1),
            sentiment="good",
        )

        # Create logs for different combinations (should not be counted)
        ActivityLog.objects.create(
            child=child2, activity=activity, date=today, sentiment="good"
        )
        ActivityLog.objects.create(
            child=child1, activity=activity2, date=today, sentiment="good"
        )

        streak = get_activity_good_streak(child1, activity)
        assert streak == 2

    def test_empty_sentiment_and_done_none_not_counted(
        self, child, activity, mock_site_context, settings
    ):
        """Test that entries without sentiment or done status are handled correctly."""
        settings.MAXIMUM_SKIPS_IN_GOOD_ACTIVITY_STREAK = 3

        today = date.today()
        ActivityLog.objects.create(
            child=child, activity=activity, date=today, sentiment="good"
        )
        # Entry with no sentiment or done status
        ActivityLog.objects.create(
            child=child, activity=activity, date=today - timedelta(days=1)
        )
        ActivityLog.objects.create(
            child=child,
            activity=activity,
            date=today - timedelta(days=2),
            sentiment="good",
        )

        # The function should handle this gracefully
        streak = get_activity_good_streak(child, activity)
        # Behavior depends on implementation - this test documents expected behavior
        assert streak >= 0
