from content_engine.models import Form, Activity
from bloom_student_interface.models import (
    Child,
    ChildFormProgress,
    CommittedActivity,
    ActivityLog,
    RecommendedActivity,
)

PICKY_EATING_FORM_SLUG = "picky-eating"

MAXIMUM_RECOMMENDED_ACTIVITIES = 10


def get_sorted_categories(scores):
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


def get_category_activities(category, score):
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


def make_recommendations(child):
    # get the latest picky-eating scores
    picky_eating_form = Form.objects.get(slug=PICKY_EATING_FORM_SLUG)
    complete_form_progress = ChildFormProgress.get_latest_complete(
        child, picky_eating_form
    )

    scores = complete_form_progress.scores

    sorted_categories = get_sorted_categories(scores)

    recommendation_count = 0

    for score, category in sorted_categories:
        activities = get_category_activities(category, score)

        for activity in activities:
            if recommendation_count > MAXIMUM_RECOMMENDED_ACTIVITIES:
                break

            recommendation, created = RecommendedActivity.objects.get_or_create(
                child=child,
                activity=activity,
                # site_id=3,
                defaults={"form_progress": complete_form_progress},
            )
            recommendation_count += 1
