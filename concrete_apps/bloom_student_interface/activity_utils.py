from content_engine.models import Form, Activity
from bloom_student_interface.models import (
    ChildFormProgress,
    ActivityLog,
    RecommendedActivity,
)

from django.conf import settings


def _get_sorted_categories(scores):
    mid_level_category_scores = []
    for category, details in scores.items():
        sub_scores = [
            (
                sub_details["score"] / sub_details["max_score"],
                f"{category} | {sub_cat}",
            )
            for sub_cat, sub_details in details["sub_categories"].items()
        ]
        mid_level_category_scores.extend(sub_scores)
    return sorted(mid_level_category_scores)


def _get_category_activities(category, score):
    mid_level = int(score * 5)  # maximum level is 5, the score is a percentage
    # Efficient queries to get exactly what we need: 1 easy, 2 medium, 1 hard
    easy = Activity.objects.filter(category=category, level=mid_level - 1).order_by(
        "pk"
    )[:1]
    medium = Activity.objects.filter(category=category, level=mid_level).order_by("pk")[
        :2
    ]
    hard = Activity.objects.filter(category=category, level=mid_level + 1).order_by(
        "pk"
    )[:1]
    # Combine results efficiently
    return list(easy) + list(medium) + list(hard)


def make_activity_recommendations(child):
    # get the latest picky-eating scores
    picky_eating_form = Form.objects.get(slug=settings.PICKY_EATING_FORM_SLUG)
    complete_form_progress = ChildFormProgress.get_latest_complete(
        child, picky_eating_form
    )

    scores = complete_form_progress.scores

    sorted_categories = _get_sorted_categories(scores)

    recommendation_count = 0

    for score, category in sorted_categories:
        activities = _get_category_activities(category, score)

        for activity in activities:
            if recommendation_count > settings.MAXIMUM_RECOMMENDED_ACTIVITIES:
                break

            recommendation, created = RecommendedActivity.objects.get_or_create(
                child=child,
                activity=activity,
                # site_id=3,
                defaults={"form_progress": complete_form_progress},
            )
            recommendation_count += 1


def _adjust_activity_recommendations(
    child, activity, levels_to_check, deactivate_filter, deactivate_method
):
    """
    Helper function to adjust activity recommendations based on sentiment.

    Args:
        child: Child instance
        activity: Activity instance that was completed
        levels_to_check: Tuple of levels to check for new recommendations (in priority order)
        deactivate_filter: Q filter kwargs for activities to deactivate
        deactivate_method: Method to call on recommendations to deactivate them

    Returns:
        list: RecommendedActivity instances (both newly created and existing active ones)
    """
    # Mark the completed activity as done
    try:
        recommendation = RecommendedActivity.objects.get(
            child=child, activity=activity, active=True
        )
        recommendation.mark_complete()
    except RecommendedActivity.DoesNotExist:
        pass

    # Deactivate inappropriate level recommendations
    recs_to_deactivate = RecommendedActivity.objects.filter(
        child=child,
        activity__category=activity.category,
        active=True,
        **deactivate_filter,
    )
    for rec in recs_to_deactivate:
        deactivate_method(rec)

    final_recommendations = []

    # Find and create recommendations at appropriate levels
    for new_level in levels_to_check:
        if len(final_recommendations) >= settings.MAXIMUM_CHANGE_LEVEL_RECOMMENDATIONS:
            break

        next_level_activities = (
            Activity.objects.filter(category=activity.category)
            .filter(level=new_level)
            .exclude(id=activity.id)
            .prefetch_related("recommendations")
        )

        for next_activity in next_level_activities:
            if (
                len(final_recommendations)
                >= settings.MAXIMUM_CHANGE_LEVEL_RECOMMENDATIONS
            ):
                break

            # TODO: update this logic.
            #  - there can be multiple recommendations over time
            #  - if a recommendation was set as inactive a long time ago, then it can be recommended again

            # Check for existing recommendation
            existing_rec = RecommendedActivity.objects.filter(
                child=child, activity=next_activity
            ).first()

            # If activity is already recommended and active, add it to the list
            if existing_rec and existing_rec.active:
                final_recommendations.append(existing_rec)
            # If activity has already been marked complete, skip it
            elif existing_rec and not existing_rec.active:
                continue
            # Otherwise, create a new recommendation
            else:
                new_rec = RecommendedActivity.objects.create(
                    child=child, activity=next_activity
                )
                final_recommendations.append(new_rec)

    return final_recommendations


def adjust_activity_recommendations_positive(child, activity):
    """
    Adjust activity recommendations after a child completes an activity with positive sentiment.

    When a child successfully completes an activity, this function:
    1. Marks the existing recommendation for the completed activity as complete (if one exists)
    2. Deactivates any active recommendations of the same category with a lower level (marked as too easy)
    3. Creates new recommendations from the same category at the same level and one level higher
    4. Reuses existing active recommendations if they match the criteria
    5. Ensures total recommendations don't exceed MAXIMUM_CHANGE_LEVEL_RECOMMENDATIONS

    Args:
        child: Child instance who completed the activity
        activity: Activity instance that was completed with positive sentiment

    Returns:
        list: RecommendedActivity instances (both newly created and existing active ones)

    Note:
        - Filters out activities that have already been marked complete
        - Includes existing active recommendations in the returned list
        - Stops adding recommendations once MAXIMUM_CHANGE_LEVEL_RECOMMENDATIONS is reached
        - Lower-level activities in the same category are marked as too easy to focus on appropriate challenges
    """
    return _adjust_activity_recommendations(
        child=child,
        activity=activity,
        levels_to_check=(activity.level + 1, activity.level),
        deactivate_filter={"activity__level__lt": activity.level},
        deactivate_method=lambda rec: rec.mark_too_easy(),
    )


def adjust_activity_recommendations_negative(child, activity):
    """
    Adjust activity recommendations after a child completes an activity with negative sentiment.

    When a child has a negative experience with an activity, this function:
    1. Marks the existing recommendation for the activity as complete (if one exists)
    2. Deactivates any active recommendations of the same category with a higher level (marked as too hard)
    3. Creates new recommendations from the same category at the same level and one level lower
    4. Reuses existing active recommendations if they match the criteria
    5. Ensures total recommendations don't exceed MAXIMUM_CHANGE_LEVEL_RECOMMENDATIONS

    Args:
        child: Child instance who completed the activity with negative sentiment
        activity: Activity instance that was completed with negative sentiment

    Returns:
        list: RecommendedActivity instances (both newly created and existing active ones)

    Note:
        - Filters out activities that have already been marked complete
        - Includes existing active recommendations in the returned list
        - Stops adding recommendations once MAXIMUM_CHANGE_LEVEL_RECOMMENDATIONS is reached
        - Recommends easier (lower level) activities to reduce difficulty after negative experience
        - Higher-level activities in the same category are marked as too hard to avoid frustration
    """
    return _adjust_activity_recommendations(
        child=child,
        activity=activity,
        levels_to_check=(activity.level - 1, activity.level),
        deactivate_filter={"activity__level__gt": activity.level},
        deactivate_method=lambda rec: rec.mark_too_hard(),
    )


def get_activity_good_streak(child, activity):
    """
    Calculate the current "good streak" for a child's activity.

    A good streak counts consecutive activity log entries with positive sentiment,
    allowing for a configurable number of neutral entries, missed days, or skips
    before the streak is broken. The streak ends immediately upon encountering a
    negative (bad) sentiment entry.

    Args:
        child: Child instance to check activity streak for
        activity: Activity instance to evaluate

    Returns:
        int: Count of activity log entries with "good" sentiment in the current streak

    Streak Break Conditions:
        - Encountering an entry with "bad" sentiment (immediate)
        - Accumulating more than MAXIMUM_SKIPS_IN_GOOD_ACTIVITY_STREAK total skips

    Skips Include:
        - Days between log entries (calculated as delta.days - 1)
        - Entries with neutral sentiment (+1 skip each)
        - Entries marked as not done (+1 skip each)

    Example:
        If MAXIMUM_SKIPS_IN_GOOD_ACTIVITY_STREAK = 3 and activity logs show:
        Day 1: Good, Day 2: Good, Day 4: Good (1 skip), Day 5: Neutral (1 skip) = 3 good streak
        Day 6: Good would continue, but Day 6: Bad would return the count at that point
    """
    from datetime import date as date_class

    maximum_skips = settings.MAXIMUM_SKIPS_IN_GOOD_ACTIVITY_STREAK

    good_count = 0
    skip_count = 0
    previous_date_seen = date_class.today()

    latest_log_entries = ActivityLog.objects.filter(
        child=child, activity=activity
    ).order_by("-date")

    for log_entry in latest_log_entries:
        if log_entry.sentiment == "bad":
            return good_count

        # Calculate skips from date gap (only for days with no log entries)
        delta = previous_date_seen - log_entry.date
        skips_from_gap = max(
            0, delta.days - 1
        )  # Consecutive days have delta=1, which gives 0 skips

        # Calculate skips from this entry itself
        skips_from_entry = 0
        if log_entry.sentiment == "neutral":
            skips_from_entry = 1
        elif log_entry.done is False:
            skips_from_entry = 1

        # Check if adding these skips would exceed the maximum
        total_if_added = skip_count + skips_from_gap + skips_from_entry
        if total_if_added > maximum_skips:
            return good_count

        # We're within the skip limit, so add the skips
        skip_count += skips_from_gap + skips_from_entry

        # Count good entries
        if log_entry.sentiment == "good":
            good_count += 1

        previous_date_seen = log_entry.date
    return good_count


def get_activity_bad_streak(child, activity):
    """
    Calculate the current "bad streak" for a child's activity.

    A bad streak counts consecutive activity log entries with negative sentiment,
    allowing for a configurable number of neutral entries, missed days, or skips
    before the streak is broken. The streak ends immediately upon encountering a
    positive (good) sentiment entry.

    Args:
        child: Child instance to check activity streak for
        activity: Activity instance to evaluate

    Returns:
        int: Count of activity log entries with "bad" sentiment in the current streak

    Streak Break Conditions:
        - Encountering an entry with "good" sentiment (immediate)
        - Accumulating more than MAXIMUM_SKIPS_IN_BAD_ACTIVITY_STREAK total skips

    Skips Include:
        - Days between log entries (calculated as delta.days - 1)
        - Entries with neutral sentiment (+1 skip each)
        - Entries marked as not done (+1 skip each)

    Example:
        If MAXIMUM_SKIPS_IN_BAD_ACTIVITY_STREAK = 3 and activity logs show:
        Day 1: Bad, Day 2: Bad, Day 4: Bad (1 skip), Day 5: Neutral (1 skip) = 3 bad streak
        Day 6: Bad would continue, but Day 6: Good would return the count at that point
    """
    from datetime import date as date_class

    maximum_skips = settings.MAXIMUM_SKIPS_IN_BAD_ACTIVITY_STREAK

    bad_count = 0
    skip_count = 0
    previous_date_seen = date_class.today()

    latest_log_entries = ActivityLog.objects.filter(
        child=child, activity=activity
    ).order_by("-date")

    for log_entry in latest_log_entries:
        if log_entry.sentiment == "good":
            return bad_count

        # Calculate skips from date gap (only for days with no log entries)
        delta = previous_date_seen - log_entry.date
        skips_from_gap = max(
            0, delta.days - 1
        )  # Consecutive days have delta=1, which gives 0 skips

        # Calculate skips from this entry itself
        skips_from_entry = 0
        if log_entry.sentiment == "neutral":
            skips_from_entry = 1
        elif log_entry.done is False:
            skips_from_entry = 1

        # Check if adding these skips would exceed the maximum
        total_if_added = skip_count + skips_from_gap + skips_from_entry
        if total_if_added > maximum_skips:
            return bad_count

        # We're within the skip limit, so add the skips
        skip_count += skips_from_gap + skips_from_entry

        # Count bad entries
        if log_entry.sentiment == "bad":
            bad_count += 1

        previous_date_seen = log_entry.date
    return bad_count
