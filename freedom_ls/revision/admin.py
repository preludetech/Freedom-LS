from django.contrib import admin
from django.http import HttpRequest

from freedom_ls.revision.models import RevisionReview, RevisionSchedule
from freedom_ls.site_aware_models.admin import SiteAwareModelAdmin


class _ReadOnlyAdmin(SiteAwareModelAdmin):
    """Browse only: both models are written by the revision page."""

    list_select_related = ("user", "question")

    def has_add_permission(self, request: HttpRequest) -> bool:
        return False

    def has_change_permission(
        self, request: HttpRequest, obj: RevisionSchedule | RevisionReview | None = None
    ) -> bool:
        return False

    def has_delete_permission(
        self, request: HttpRequest, obj: RevisionSchedule | RevisionReview | None = None
    ) -> bool:
        return False


@admin.register(RevisionSchedule)
class RevisionScheduleAdmin(_ReadOnlyAdmin):
    list_display = ["user", "question", "state", "due", "reps", "lapses"]
    search_fields = ["user__email"]


@admin.register(RevisionReview)
class RevisionReviewAdmin(_ReadOnlyAdmin):
    list_display = ["user", "question", "reviewed_at", "was_correct", "guessed"]
    list_filter = ["was_correct", "guessed"]
    search_fields = ["user__email"]
