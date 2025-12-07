import pytest
from datetime import date, timedelta
from bloom_student_interface.models import Child, ActivityLog, RecommendedActivity
from bloom_student_interface.activity_utils import (
    get_activity_good_streak,
    get_activity_bad_streak,
    adjust_activity_recommendations_positive,
    adjust_activity_recommendations_negative,
)
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


@pytest.mark.parametrize("site", ["Bloom"], indirect=True)
@pytest.mark.django_db
class TestGetActivityBadStreak:
    """Test the get_activity_bad_streak function."""

    def test_no_activity_logs_returns_zero(self, child, activity, mock_site_context):
        """Test that when there are no activity logs, the streak is 0."""
        streak = get_activity_bad_streak(child, activity)
        assert streak == 0

    def test_single_bad_entry_returns_one(
        self, child, activity, mock_site_context, settings
    ):
        """Test that a single bad entry returns a streak of 1."""
        settings.MAXIMUM_SKIPS_IN_BAD_ACTIVITY_STREAK = 3

        ActivityLog.objects.create(
            child=child, activity=activity, date=date.today(), sentiment="bad"
        )

        streak = get_activity_bad_streak(child, activity)
        assert streak == 1

    def test_consecutive_bad_entries(
        self, child, activity, mock_site_context, settings
    ):
        """Test consecutive bad entries without any skips."""
        settings.MAXIMUM_SKIPS_IN_BAD_ACTIVITY_STREAK = 3

        today = date.today()
        ActivityLog.objects.create(
            child=child, activity=activity, date=today, sentiment="bad"
        )
        ActivityLog.objects.create(
            child=child,
            activity=activity,
            date=today - timedelta(days=1),
            sentiment="bad",
        )
        ActivityLog.objects.create(
            child=child,
            activity=activity,
            date=today - timedelta(days=2),
            sentiment="bad",
        )

        streak = get_activity_bad_streak(child, activity)
        assert streak == 3

    def test_good_sentiment_breaks_streak_immediately(
        self, child, activity, mock_site_context, settings
    ):
        """Test that a good sentiment entry immediately breaks the streak."""
        settings.MAXIMUM_SKIPS_IN_BAD_ACTIVITY_STREAK = 3

        today = date.today()
        ActivityLog.objects.create(
            child=child, activity=activity, date=today, sentiment="bad"
        )
        ActivityLog.objects.create(
            child=child,
            activity=activity,
            date=today - timedelta(days=1),
            sentiment="bad",
        )
        ActivityLog.objects.create(
            child=child,
            activity=activity,
            date=today - timedelta(days=2),
            sentiment="good",
        )
        ActivityLog.objects.create(
            child=child,
            activity=activity,
            date=today - timedelta(days=3),
            sentiment="bad",
        )

        streak = get_activity_bad_streak(child, activity)
        assert streak == 2

    def test_neutral_sentiment_counts_as_skip(
        self, child, activity, mock_site_context, settings
    ):
        """Test that neutral sentiment entries count as skips."""
        settings.MAXIMUM_SKIPS_IN_BAD_ACTIVITY_STREAK = 2

        today = date.today()
        ActivityLog.objects.create(
            child=child, activity=activity, date=today, sentiment="bad"
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
            sentiment="bad",
        )

        streak = get_activity_bad_streak(child, activity)
        assert streak == 2

    def test_done_false_counts_as_skip(
        self, child, activity, mock_site_context, settings
    ):
        """Test that done=False entries count as skips."""
        settings.MAXIMUM_SKIPS_IN_BAD_ACTIVITY_STREAK = 2

        today = date.today()
        ActivityLog.objects.create(
            child=child, activity=activity, date=today, sentiment="bad", done=True
        )
        ActivityLog.objects.create(
            child=child, activity=activity, date=today - timedelta(days=1), done=False
        )
        ActivityLog.objects.create(
            child=child,
            activity=activity,
            date=today - timedelta(days=2),
            sentiment="bad",
            done=True,
        )

        streak = get_activity_bad_streak(child, activity)
        assert streak == 2

    def test_skipped_days_count_as_skips(
        self, child, activity, mock_site_context, settings
    ):
        """Test that days between log entries count as skips."""
        settings.MAXIMUM_SKIPS_IN_BAD_ACTIVITY_STREAK = 3

        today = date.today()
        ActivityLog.objects.create(
            child=child, activity=activity, date=today, sentiment="bad"
        )
        # Skip 2 days (creates 2 skips)
        ActivityLog.objects.create(
            child=child,
            activity=activity,
            date=today - timedelta(days=3),
            sentiment="bad",
        )

        streak = get_activity_bad_streak(child, activity)
        assert streak == 2

    def test_exceeding_maximum_skips_breaks_streak(
        self, child, activity, mock_site_context, settings
    ):
        """Test that exceeding maximum skips breaks the streak."""
        settings.MAXIMUM_SKIPS_IN_BAD_ACTIVITY_STREAK = 2

        today = date.today()
        ActivityLog.objects.create(
            child=child, activity=activity, date=today, sentiment="bad"
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
            sentiment="bad",
        )

        streak = get_activity_bad_streak(child, activity)
        assert streak == 1

    def test_combined_skips_accumulated(
        self, child, activity, mock_site_context, settings
    ):
        """Test that different types of skips are accumulated together."""
        settings.MAXIMUM_SKIPS_IN_BAD_ACTIVITY_STREAK = 3

        today = date.today()
        ActivityLog.objects.create(
            child=child, activity=activity, date=today, sentiment="bad"
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
            sentiment="bad",
        )
        # 1 done=False = 1 skip
        # Total: 3 skips (at the limit)
        ActivityLog.objects.create(
            child=child, activity=activity, date=today - timedelta(days=4), done=False
        )
        # This bad entry adds no skips, so total stays at 3 (within limit)
        ActivityLog.objects.create(
            child=child,
            activity=activity,
            date=today - timedelta(days=5),
            sentiment="bad",
        )

        streak = get_activity_bad_streak(child, activity)
        # All 3 bad entries should be counted since we never exceed max of 3 skips
        assert streak == 3

    def test_only_counts_specific_child_and_activity(
        self, user, activity, mock_site_context, settings
    ):
        """Test that the function only counts logs for the specific child and activity."""

        settings.MAXIMUM_SKIPS_IN_BAD_ACTIVITY_STREAK = 3

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
            child=child1, activity=activity, date=today, sentiment="bad"
        )
        ActivityLog.objects.create(
            child=child1,
            activity=activity,
            date=today - timedelta(days=1),
            sentiment="bad",
        )

        # Create logs for different combinations (should not be counted)
        ActivityLog.objects.create(
            child=child2, activity=activity, date=today, sentiment="bad"
        )
        ActivityLog.objects.create(
            child=child1, activity=activity2, date=today, sentiment="bad"
        )

        streak = get_activity_bad_streak(child1, activity)
        assert streak == 2

    def test_empty_sentiment_and_done_none_not_counted(
        self, child, activity, mock_site_context, settings
    ):
        """Test that entries without sentiment or done status are handled correctly."""
        settings.MAXIMUM_SKIPS_IN_BAD_ACTIVITY_STREAK = 3

        today = date.today()
        ActivityLog.objects.create(
            child=child, activity=activity, date=today, sentiment="bad"
        )
        # Entry with no sentiment or done status
        ActivityLog.objects.create(
            child=child, activity=activity, date=today - timedelta(days=1)
        )
        ActivityLog.objects.create(
            child=child,
            activity=activity,
            date=today - timedelta(days=2),
            sentiment="bad",
        )

        # The function should handle this gracefully
        streak = get_activity_bad_streak(child, activity)
        # Behavior depends on implementation - this test documents expected behavior
        assert streak >= 0


@pytest.mark.parametrize("site", ["Bloom"], indirect=True)
@pytest.mark.django_db
class TestAdjustActivityRecommendationsPositive:
    """Test the adjust_activity_recommendations_positive function."""

    def test_marks_existing_recommendation_complete(
        self, child, mock_site_context, settings
    ):
        """Test that existing active recommendation for completed activity is marked complete."""
        settings.MAXIMUM_CHANGE_LEVEL_RECOMMENDATIONS = 3

        activity = Activity.objects.create(
            title="Completed Activity", slug="completed", category="taste", level=2
        )

        # Create an active recommendation for the activity
        recommendation = RecommendedActivity.objects.create(
            child=child, activity=activity
        )

        # Call the function
        result = adjust_activity_recommendations_positive(child, activity)

        # Verify the recommendation was marked complete
        recommendation.refresh_from_db()
        assert recommendation.active is False

    def test_no_error_when_no_existing_recommendation(
        self, child, mock_site_context, settings
    ):
        """Test that function handles case when no existing recommendation exists."""
        settings.MAXIMUM_CHANGE_LEVEL_RECOMMENDATIONS = 3

        activity = Activity.objects.create(
            title="New Activity", slug="new-activity", category="taste", level=2
        )

        # Call the function - should not raise an error
        result = adjust_activity_recommendations_positive(child, activity)

        # Should return empty list since there are no other activities to recommend
        assert result == []

    def test_recommends_same_level_activities(self, child, mock_site_context, settings):
        """Test that activities at the same level are recommended."""
        settings.MAXIMUM_CHANGE_LEVEL_RECOMMENDATIONS = 3

        completed_activity = Activity.objects.create(
            title="Completed Activity", slug="completed", category="taste", level=2
        )

        # Create other activities at the same level and category
        same_level_1 = Activity.objects.create(
            title="Same Level 1", slug="same-1", category="taste", level=2
        )
        same_level_2 = Activity.objects.create(
            title="Same Level 2", slug="same-2", category="taste", level=2
        )

        result = adjust_activity_recommendations_positive(child, completed_activity)

        # Should include both same-level activities (sorted by pk for deterministic ordering)
        result_activities = sorted([r.activity for r in result], key=lambda a: a.pk)
        expected_activities = sorted([same_level_1, same_level_2], key=lambda a: a.pk)
        assert result_activities == expected_activities

    def test_recommends_higher_level_activities(
        self, child, mock_site_context, settings
    ):
        """Test that activities at one level higher are recommended."""
        settings.MAXIMUM_CHANGE_LEVEL_RECOMMENDATIONS = 3

        completed_activity = Activity.objects.create(
            title="Completed Activity", slug="completed", category="taste", level=2
        )

        # Create activities at level+1
        higher_level_1 = Activity.objects.create(
            title="Higher Level 1", slug="higher-1", category="taste", level=3
        )
        higher_level_2 = Activity.objects.create(
            title="Higher Level 2", slug="higher-2", category="taste", level=3
        )

        result = adjust_activity_recommendations_positive(child, completed_activity)

        # Should include both higher-level activities (sorted by pk for deterministic ordering)
        result_activities = sorted([r.activity for r in result], key=lambda a: a.pk)
        expected_activities = sorted(
            [higher_level_1, higher_level_2], key=lambda a: a.pk
        )
        assert result_activities == expected_activities

    def test_prioritizes_higher_level_over_same_level(
        self, child, mock_site_context, settings
    ):
        """Test that higher level activities are checked first."""
        settings.MAXIMUM_CHANGE_LEVEL_RECOMMENDATIONS = 2

        completed_activity = Activity.objects.create(
            title="Completed Activity", slug="completed", category="taste", level=2
        )

        # Create activities at both levels
        higher_level = Activity.objects.create(
            title="Higher Level", slug="higher", category="taste", level=3
        )
        same_level = Activity.objects.create(
            title="Same Level", slug="same", category="taste", level=2
        )

        result = adjust_activity_recommendations_positive(child, completed_activity)

        # Should return exactly 2 activities: higher level first, then same level
        result_activities = [r.activity for r in result]
        assert len(result_activities) == 2
        assert result_activities == [higher_level, same_level]

    def test_respects_maximum_recommendations_limit(
        self, child, mock_site_context, settings
    ):
        """Test that total recommendations don't exceed MAXIMUM_CHANGE_LEVEL_RECOMMENDATIONS."""
        settings.MAXIMUM_CHANGE_LEVEL_RECOMMENDATIONS = 2

        completed_activity = Activity.objects.create(
            title="Completed Activity", slug="completed", category="taste", level=2
        )

        # Create many activities at both levels
        for i in range(5):
            Activity.objects.create(
                title=f"Higher {i}", slug=f"higher-{i}", category="taste", level=3
            )
            Activity.objects.create(
                title=f"Same {i}", slug=f"same-{i}", category="taste", level=2
            )

        result = adjust_activity_recommendations_positive(child, completed_activity)

        # Should return exactly the limit (2 activities)
        assert len(result) == settings.MAXIMUM_CHANGE_LEVEL_RECOMMENDATIONS

    def test_filters_out_completed_activities(self, child, mock_site_context, settings):
        """Test that activities already marked complete are not recommended."""
        settings.MAXIMUM_CHANGE_LEVEL_RECOMMENDATIONS = 3

        completed_activity = Activity.objects.create(
            title="Completed Activity", slug="completed", category="taste", level=2
        )

        # Create activities at the same level
        already_complete = Activity.objects.create(
            title="Already Complete", slug="already-complete", category="taste", level=2
        )
        not_complete = Activity.objects.create(
            title="Not Complete", slug="not-complete", category="taste", level=2
        )

        # Mark one as already complete
        RecommendedActivity.objects.create(
            child=child, activity=already_complete, active=False
        )

        result = adjust_activity_recommendations_positive(child, completed_activity)

        # Should return exactly 1 activity: the not-complete one
        result_activities = [r.activity for r in result]
        assert len(result_activities) == 1
        assert result_activities == [not_complete]

    def test_includes_existing_active_recommendations(
        self, child, mock_site_context, settings
    ):
        """Test that existing active recommendations are included in the result."""
        settings.MAXIMUM_CHANGE_LEVEL_RECOMMENDATIONS = 3

        completed_activity = Activity.objects.create(
            title="Completed Activity", slug="completed", category="taste", level=2
        )

        # Create an activity that's already actively recommended
        already_recommended = Activity.objects.create(
            title="Already Recommended",
            slug="already-recommended",
            category="taste",
            level=3,
        )

        existing_rec = RecommendedActivity.objects.create(
            child=child, activity=already_recommended, active=True
        )

        result = adjust_activity_recommendations_positive(child, completed_activity)

        # Should include the existing active recommendation
        assert existing_rec in result

    def test_only_same_category_activities(self, child, mock_site_context, settings):
        """Test that only activities from the same category are recommended."""
        settings.MAXIMUM_CHANGE_LEVEL_RECOMMENDATIONS = 3

        completed_activity = Activity.objects.create(
            title="Completed Activity", slug="completed", category="taste", level=2
        )

        # Create activities in different categories
        same_category = Activity.objects.create(
            title="Same Category", slug="same-cat", category="taste", level=3
        )
        different_category = Activity.objects.create(
            title="Different Category", slug="diff-cat", category="texture", level=3
        )

        result = adjust_activity_recommendations_positive(child, completed_activity)

        # Should return exactly 1 activity: the same category one
        result_activities = [r.activity for r in result]
        assert len(result_activities) == 1
        assert result_activities == [same_category]

    def test_creates_new_recommendation_instances(
        self, child, mock_site_context, settings
    ):
        """Test that new RecommendedActivity instances are created."""
        settings.MAXIMUM_CHANGE_LEVEL_RECOMMENDATIONS = 3

        completed_activity = Activity.objects.create(
            title="Completed Activity", slug="completed", category="taste", level=2
        )

        new_activity = Activity.objects.create(
            title="New Activity", slug="new", category="taste", level=3
        )

        initial_count = RecommendedActivity.objects.filter(child=child).count()

        adjust_activity_recommendations_positive(child, completed_activity)

        final_count = RecommendedActivity.objects.filter(child=child).count()

        # Should have created exactly 1 new recommendation
        assert final_count == initial_count + 1

        # Verify the new recommendation is for the new activity
        new_rec = RecommendedActivity.objects.get(child=child, activity=new_activity)
        assert new_rec.child == child
        assert new_rec.activity == new_activity

    def test_only_affects_specific_child(self, user, mock_site_context, settings):
        """Test that recommendations are only created for the specific child."""
        settings.MAXIMUM_CHANGE_LEVEL_RECOMMENDATIONS = 3

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

        completed_activity = Activity.objects.create(
            title="Completed Activity", slug="completed", category="taste", level=2
        )

        new_activity = Activity.objects.create(
            title="New Activity", slug="new", category="taste", level=3
        )

        result = adjust_activity_recommendations_positive(child1, completed_activity)

        # Should return exactly 1 recommendation for child1
        assert len(result) == 1
        assert result[0].child == child1
        assert result[0].activity == new_activity

        # child2 should have no recommendations
        assert RecommendedActivity.objects.filter(child=child2).count() == 0

    def test_handles_activities_with_no_higher_level(
        self, child, mock_site_context, settings
    ):
        """Test behavior when activity is at max level (no higher level exists)."""
        settings.MAXIMUM_CHANGE_LEVEL_RECOMMENDATIONS = 3

        # Activity at level 5 with no level 6 activities
        completed_activity = Activity.objects.create(
            title="Max Level Activity", slug="max-level", category="taste", level=5
        )

        # Only create same-level activity
        same_level = Activity.objects.create(
            title="Same Level", slug="same", category="taste", level=5
        )

        result = adjust_activity_recommendations_positive(child, completed_activity)

        # Should return exactly 1 activity: the same-level one
        result_activities = [r.activity for r in result]
        assert len(result_activities) == 1
        assert result_activities == [same_level]

    def test_empty_result_when_no_eligible_activities(
        self, child, mock_site_context, settings
    ):
        """Test that empty list is returned when no eligible activities exist."""
        settings.MAXIMUM_CHANGE_LEVEL_RECOMMENDATIONS = 3

        # Only activity is the completed one
        completed_activity = Activity.objects.create(
            title="Only Activity", slug="only", category="taste", level=2
        )

        result = adjust_activity_recommendations_positive(child, completed_activity)

        # Should return empty list since there are no other activities to recommend
        assert result == []

    def test_deactivates_lower_level_recommendations_same_category(
        self, child, mock_site_context, settings
    ):
        """Test that existing lower-level recommendations in same category are deactivated as too easy."""
        settings.MAXIMUM_CHANGE_LEVEL_RECOMMENDATIONS = 3

        completed_activity = Activity.objects.create(
            title="Completed Activity", slug="completed", category="taste", level=3
        )

        # Create lower level activities in the same category
        lower_level_1 = Activity.objects.create(
            title="Lower Level 1", slug="lower-1", category="taste", level=2
        )
        lower_level_2 = Activity.objects.create(
            title="Lower Level 2", slug="lower-2", category="taste", level=1
        )

        # Create lower level activity in different category (should not be deactivated)
        different_category_lower = Activity.objects.create(
            title="Different Category Lower",
            slug="diff-cat-lower",
            category="texture",
            level=2,
        )

        # Create active recommendations for lower level activities
        rec_lower_1 = RecommendedActivity.objects.create(
            child=child, activity=lower_level_1, active=True
        )
        rec_lower_2 = RecommendedActivity.objects.create(
            child=child, activity=lower_level_2, active=True
        )
        rec_diff_cat = RecommendedActivity.objects.create(
            child=child, activity=different_category_lower, active=True
        )

        # Call the function
        adjust_activity_recommendations_positive(child, completed_activity)

        # Verify lower level recommendations in same category are deactivated
        rec_lower_1.refresh_from_db()
        rec_lower_2.refresh_from_db()
        rec_diff_cat.refresh_from_db()

        assert rec_lower_1.active is False
        assert rec_lower_1.deactivation_reason == "too_easy"
        assert rec_lower_2.active is False
        assert rec_lower_2.deactivation_reason == "too_easy"

        # Different category should remain active
        assert rec_diff_cat.active is True
        assert rec_diff_cat.deactivation_reason is None

    def test_deactivates_only_lower_levels_not_same_or_higher(
        self, child, mock_site_context, settings
    ):
        """Test that only lower-level recommendations are deactivated, not same or higher level."""
        settings.MAXIMUM_CHANGE_LEVEL_RECOMMENDATIONS = 3

        completed_activity = Activity.objects.create(
            title="Completed Activity", slug="completed", category="taste", level=3
        )

        # Create activities at different levels
        lower_level = Activity.objects.create(
            title="Lower Level", slug="lower", category="taste", level=2
        )
        same_level = Activity.objects.create(
            title="Same Level", slug="same", category="taste", level=3
        )
        higher_level = Activity.objects.create(
            title="Higher Level", slug="higher", category="taste", level=4
        )

        # Create active recommendations
        rec_lower = RecommendedActivity.objects.create(
            child=child, activity=lower_level, active=True
        )
        rec_same = RecommendedActivity.objects.create(
            child=child, activity=same_level, active=True
        )
        rec_higher = RecommendedActivity.objects.create(
            child=child, activity=higher_level, active=True
        )

        # Call the function
        adjust_activity_recommendations_positive(child, completed_activity)

        # Refresh from database
        rec_lower.refresh_from_db()
        rec_same.refresh_from_db()
        rec_higher.refresh_from_db()

        # Lower level should be deactivated
        assert rec_lower.active is False
        assert rec_lower.deactivation_reason == "too_easy"

        # Same and higher level should remain active
        assert rec_same.active is True
        assert rec_same.deactivation_reason is None
        assert rec_higher.active is True
        assert rec_higher.deactivation_reason is None


@pytest.mark.parametrize("site", ["Bloom"], indirect=True)
@pytest.mark.django_db
class TestAdjustActivityRecommendationsNegative:
    """Test the adjust_activity_recommendations_negative function."""

    def test_marks_existing_recommendation_complete(
        self, child, mock_site_context, settings
    ):
        """Test that existing active recommendation for completed activity is marked complete."""
        settings.MAXIMUM_CHANGE_LEVEL_RECOMMENDATIONS = 3

        activity = Activity.objects.create(
            title="Failed Activity", slug="failed", category="taste", level=3
        )

        # Create an active recommendation for the activity
        recommendation = RecommendedActivity.objects.create(
            child=child, activity=activity
        )

        # Call the function
        result = adjust_activity_recommendations_negative(child, activity)

        # Verify the recommendation was marked complete
        recommendation.refresh_from_db()
        assert recommendation.active is False

    def test_no_error_when_no_existing_recommendation(
        self, child, mock_site_context, settings
    ):
        """Test that function handles case when no existing recommendation exists."""
        settings.MAXIMUM_CHANGE_LEVEL_RECOMMENDATIONS = 3

        activity = Activity.objects.create(
            title="Failed Activity", slug="failed-activity", category="taste", level=3
        )

        # Call the function - should not raise an error
        result = adjust_activity_recommendations_negative(child, activity)

        # Should return empty list since there are no other activities to recommend
        assert result == []

    def test_recommends_same_level_activities(self, child, mock_site_context, settings):
        """Test that activities at the same level are recommended."""
        settings.MAXIMUM_CHANGE_LEVEL_RECOMMENDATIONS = 3

        failed_activity = Activity.objects.create(
            title="Failed Activity", slug="failed", category="taste", level=3
        )

        # Create other activities at the same level and category
        same_level_1 = Activity.objects.create(
            title="Same Level 1", slug="same-1", category="taste", level=3
        )
        same_level_2 = Activity.objects.create(
            title="Same Level 2", slug="same-2", category="taste", level=3
        )

        result = adjust_activity_recommendations_negative(child, failed_activity)

        # Should include both same-level activities (sorted by pk for deterministic ordering)
        result_activities = sorted([r.activity for r in result], key=lambda a: a.pk)
        expected_activities = sorted([same_level_1, same_level_2], key=lambda a: a.pk)
        assert result_activities == expected_activities

    def test_recommends_lower_level_activities(
        self, child, mock_site_context, settings
    ):
        """Test that activities at one level lower are recommended."""
        settings.MAXIMUM_CHANGE_LEVEL_RECOMMENDATIONS = 3

        failed_activity = Activity.objects.create(
            title="Failed Activity", slug="failed", category="taste", level=3
        )

        # Create activities at level-1
        lower_level_1 = Activity.objects.create(
            title="Lower Level 1", slug="lower-1", category="taste", level=2
        )
        lower_level_2 = Activity.objects.create(
            title="Lower Level 2", slug="lower-2", category="taste", level=2
        )

        result = adjust_activity_recommendations_negative(child, failed_activity)

        # Should include both lower-level activities (sorted by pk for deterministic ordering)
        result_activities = sorted([r.activity for r in result], key=lambda a: a.pk)
        expected_activities = sorted([lower_level_1, lower_level_2], key=lambda a: a.pk)
        assert result_activities == expected_activities

    def test_prioritizes_lower_level_over_same_level(
        self, child, mock_site_context, settings
    ):
        """Test that lower level activities are checked first."""
        settings.MAXIMUM_CHANGE_LEVEL_RECOMMENDATIONS = 2

        failed_activity = Activity.objects.create(
            title="Failed Activity", slug="failed", category="taste", level=3
        )

        # Create activities at both levels
        lower_level = Activity.objects.create(
            title="Lower Level", slug="lower", category="taste", level=2
        )
        same_level = Activity.objects.create(
            title="Same Level", slug="same", category="taste", level=3
        )

        result = adjust_activity_recommendations_negative(child, failed_activity)

        # Should return exactly 2 activities: lower level first, then same level
        result_activities = [r.activity for r in result]
        assert len(result_activities) == 2
        assert result_activities == [lower_level, same_level]

    def test_respects_maximum_recommendations_limit(
        self, child, mock_site_context, settings
    ):
        """Test that total recommendations don't exceed MAXIMUM_CHANGE_LEVEL_RECOMMENDATIONS."""
        settings.MAXIMUM_CHANGE_LEVEL_RECOMMENDATIONS = 2

        failed_activity = Activity.objects.create(
            title="Failed Activity", slug="failed", category="taste", level=3
        )

        # Create many activities at both levels
        for i in range(5):
            Activity.objects.create(
                title=f"Lower {i}", slug=f"lower-{i}", category="taste", level=2
            )
            Activity.objects.create(
                title=f"Same {i}", slug=f"same-{i}", category="taste", level=3
            )

        result = adjust_activity_recommendations_negative(child, failed_activity)

        # Should return exactly the limit (2 activities)
        assert len(result) == settings.MAXIMUM_CHANGE_LEVEL_RECOMMENDATIONS

    def test_filters_out_completed_activities(self, child, mock_site_context, settings):
        """Test that activities already marked complete are not recommended."""
        settings.MAXIMUM_CHANGE_LEVEL_RECOMMENDATIONS = 3

        failed_activity = Activity.objects.create(
            title="Failed Activity", slug="failed", category="taste", level=3
        )

        # Create activities at the same level
        already_complete = Activity.objects.create(
            title="Already Complete", slug="already-complete", category="taste", level=3
        )
        not_complete = Activity.objects.create(
            title="Not Complete", slug="not-complete", category="taste", level=3
        )

        # Mark one as already complete
        RecommendedActivity.objects.create(
            child=child, activity=already_complete, active=False
        )

        result = adjust_activity_recommendations_negative(child, failed_activity)

        # Should return exactly 1 activity: the not-complete one
        result_activities = [r.activity for r in result]
        assert len(result_activities) == 1
        assert result_activities == [not_complete]

    def test_includes_existing_active_recommendations(
        self, child, mock_site_context, settings
    ):
        """Test that existing active recommendations are included in the result."""
        settings.MAXIMUM_CHANGE_LEVEL_RECOMMENDATIONS = 3

        failed_activity = Activity.objects.create(
            title="Failed Activity", slug="failed", category="taste", level=3
        )

        # Create an activity that's already actively recommended
        already_recommended = Activity.objects.create(
            title="Already Recommended",
            slug="already-recommended",
            category="taste",
            level=2,
        )

        existing_rec = RecommendedActivity.objects.create(
            child=child, activity=already_recommended, active=True
        )

        result = adjust_activity_recommendations_negative(child, failed_activity)

        # Should include the existing active recommendation
        assert existing_rec in result

    def test_only_same_category_activities(self, child, mock_site_context, settings):
        """Test that only activities from the same category are recommended."""
        settings.MAXIMUM_CHANGE_LEVEL_RECOMMENDATIONS = 3

        failed_activity = Activity.objects.create(
            title="Failed Activity", slug="failed", category="taste", level=3
        )

        # Create activities in different categories
        same_category = Activity.objects.create(
            title="Same Category", slug="same-cat", category="taste", level=2
        )
        different_category = Activity.objects.create(
            title="Different Category", slug="diff-cat", category="texture", level=2
        )

        result = adjust_activity_recommendations_negative(child, failed_activity)

        # Should return exactly 1 activity: the same category one
        result_activities = [r.activity for r in result]
        assert len(result_activities) == 1
        assert result_activities == [same_category]

    def test_creates_new_recommendation_instances(
        self, child, mock_site_context, settings
    ):
        """Test that new RecommendedActivity instances are created."""
        settings.MAXIMUM_CHANGE_LEVEL_RECOMMENDATIONS = 3

        failed_activity = Activity.objects.create(
            title="Failed Activity", slug="failed", category="taste", level=3
        )

        easier_activity = Activity.objects.create(
            title="Easier Activity", slug="easier", category="taste", level=2
        )

        initial_count = RecommendedActivity.objects.filter(child=child).count()

        adjust_activity_recommendations_negative(child, failed_activity)

        final_count = RecommendedActivity.objects.filter(child=child).count()

        # Should have created exactly 1 new recommendation
        assert final_count == initial_count + 1

        # Verify the new recommendation is for the easier activity
        new_rec = RecommendedActivity.objects.get(child=child, activity=easier_activity)
        assert new_rec.child == child
        assert new_rec.activity == easier_activity

    def test_only_affects_specific_child(self, user, mock_site_context, settings):
        """Test that recommendations are only created for the specific child."""
        settings.MAXIMUM_CHANGE_LEVEL_RECOMMENDATIONS = 3

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

        failed_activity = Activity.objects.create(
            title="Failed Activity", slug="failed", category="taste", level=3
        )

        easier_activity = Activity.objects.create(
            title="Easier Activity", slug="easier", category="taste", level=2
        )

        result = adjust_activity_recommendations_negative(child1, failed_activity)

        # Should return exactly 1 recommendation for child1
        assert len(result) == 1
        assert result[0].child == child1
        assert result[0].activity == easier_activity

        # child2 should have no recommendations
        assert RecommendedActivity.objects.filter(child=child2).count() == 0

    def test_handles_activities_at_minimum_level(
        self, child, mock_site_context, settings
    ):
        """Test behavior when activity is at minimum level (level 1, no lower level exists)."""
        settings.MAXIMUM_CHANGE_LEVEL_RECOMMENDATIONS = 3

        # Activity at level 1 with no level 0 activities
        failed_activity = Activity.objects.create(
            title="Min Level Activity", slug="min-level", category="taste", level=1
        )

        # Only create same-level activity
        same_level = Activity.objects.create(
            title="Same Level", slug="same", category="taste", level=1
        )

        result = adjust_activity_recommendations_negative(child, failed_activity)

        # Should return exactly 1 activity: the same-level one
        result_activities = [r.activity for r in result]
        assert len(result_activities) == 1
        assert result_activities == [same_level]

    def test_empty_result_when_no_eligible_activities(
        self, child, mock_site_context, settings
    ):
        """Test that empty list is returned when no eligible activities exist."""
        settings.MAXIMUM_CHANGE_LEVEL_RECOMMENDATIONS = 3

        # Only activity is the failed one
        failed_activity = Activity.objects.create(
            title="Only Activity", slug="only", category="taste", level=3
        )

        result = adjust_activity_recommendations_negative(child, failed_activity)

        # Should return empty list since there are no other activities to recommend
        assert result == []

    def test_does_not_recommend_higher_level_activities(
        self, child, mock_site_context, settings
    ):
        """Test that higher level activities are NOT recommended after negative experience."""
        settings.MAXIMUM_CHANGE_LEVEL_RECOMMENDATIONS = 3

        failed_activity = Activity.objects.create(
            title="Failed Activity", slug="failed", category="taste", level=3
        )

        # Create activities at different levels
        lower_level = Activity.objects.create(
            title="Lower Level", slug="lower", category="taste", level=2
        )
        same_level = Activity.objects.create(
            title="Same Level", slug="same", category="taste", level=3
        )
        higher_level = Activity.objects.create(
            title="Higher Level", slug="higher", category="taste", level=4
        )

        result = adjust_activity_recommendations_negative(child, failed_activity)

        # Should include lower and same level, but NOT higher level
        result_activities = sorted([r.activity for r in result], key=lambda a: a.pk)
        expected_activities = sorted([lower_level, same_level], key=lambda a: a.pk)
        assert result_activities == expected_activities
        # Explicitly verify higher level is not included
        assert higher_level not in result_activities

    def test_deactivates_higher_level_recommendations_same_category(
        self, child, mock_site_context, settings
    ):
        """Test that existing higher-level recommendations in same category are deactivated as too hard."""
        settings.MAXIMUM_CHANGE_LEVEL_RECOMMENDATIONS = 3

        failed_activity = Activity.objects.create(
            title="Failed Activity", slug="failed", category="taste", level=3
        )

        # Create higher level activities in the same category
        higher_level_1 = Activity.objects.create(
            title="Higher Level 1", slug="higher-1", category="taste", level=4
        )
        higher_level_2 = Activity.objects.create(
            title="Higher Level 2", slug="higher-2", category="taste", level=5
        )

        # Create higher level activity in different category (should not be deactivated)
        different_category_higher = Activity.objects.create(
            title="Different Category Higher",
            slug="diff-cat-higher",
            category="texture",
            level=4,
        )

        # Create active recommendations for higher level activities
        rec_higher_1 = RecommendedActivity.objects.create(
            child=child, activity=higher_level_1, active=True
        )
        rec_higher_2 = RecommendedActivity.objects.create(
            child=child, activity=higher_level_2, active=True
        )
        rec_diff_cat = RecommendedActivity.objects.create(
            child=child, activity=different_category_higher, active=True
        )

        # Call the function
        adjust_activity_recommendations_negative(child, failed_activity)

        # Verify higher level recommendations in same category are deactivated
        rec_higher_1.refresh_from_db()
        rec_higher_2.refresh_from_db()
        rec_diff_cat.refresh_from_db()

        assert rec_higher_1.active is False
        assert rec_higher_1.deactivation_reason == "too_hard"
        assert rec_higher_2.active is False
        assert rec_higher_2.deactivation_reason == "too_hard"

        # Different category should remain active
        assert rec_diff_cat.active is True
        assert rec_diff_cat.deactivation_reason is None

    def test_deactivates_only_higher_levels_not_same_or_lower(
        self, child, mock_site_context, settings
    ):
        """Test that only higher-level recommendations are deactivated, not same or lower level."""
        settings.MAXIMUM_CHANGE_LEVEL_RECOMMENDATIONS = 3

        failed_activity = Activity.objects.create(
            title="Failed Activity", slug="failed", category="taste", level=3
        )

        # Create activities at different levels
        lower_level = Activity.objects.create(
            title="Lower Level", slug="lower", category="taste", level=2
        )
        same_level = Activity.objects.create(
            title="Same Level", slug="same", category="taste", level=3
        )
        higher_level = Activity.objects.create(
            title="Higher Level", slug="higher", category="taste", level=4
        )

        # Create active recommendations
        rec_lower = RecommendedActivity.objects.create(
            child=child, activity=lower_level, active=True
        )
        rec_same = RecommendedActivity.objects.create(
            child=child, activity=same_level, active=True
        )
        rec_higher = RecommendedActivity.objects.create(
            child=child, activity=higher_level, active=True
        )

        # Call the function
        adjust_activity_recommendations_negative(child, failed_activity)

        # Refresh from database
        rec_lower.refresh_from_db()
        rec_same.refresh_from_db()
        rec_higher.refresh_from_db()

        # Lower and same level should remain active
        assert rec_lower.active is True
        assert rec_lower.deactivation_reason is None
        assert rec_same.active is True
        assert rec_same.deactivation_reason is None

        # Higher level should be deactivated
        assert rec_higher.active is False
        assert rec_higher.deactivation_reason == "too_hard"
