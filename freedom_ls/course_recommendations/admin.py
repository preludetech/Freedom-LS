from django.contrib import admin

from freedom_ls.course_recommendations.models import RecommendedCourse
from freedom_ls.site_aware_models.admin import SiteAwareModelAdmin


@admin.register(RecommendedCourse)
class RecommendedCourseAdmin(SiteAwareModelAdmin):
    list_display = ["user", "course", "created_at"]
    search_fields = ["user__email", "course__title"]
    list_filter = ["created_at"]
    readonly_fields = ["created_at"]
    exclude = ["site"]
