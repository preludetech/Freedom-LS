from __future__ import annotations

from django.contrib import admin

from freedom_ls.messaging_policy.forms import SiteMessagingConfigForm
from freedom_ls.messaging_policy.models import (
    FLAG_NAMES,
    CohortCourseRegistrationMessagingConfig,
    CohortMessagingConfig,
    LearnerCourseRegistrationMessagingConfig,
    LearnerMessagingConfig,
    OrganisationMessagingConfig,
    SiteMessagingConfig,
)
from freedom_ls.site_aware_models.admin import SiteAwareModelAdmin


@admin.register(SiteMessagingConfig)
class SiteMessagingConfigAdmin(SiteAwareModelAdmin):
    form = SiteMessagingConfigForm
    list_display = ["__str__", *FLAG_NAMES]
    list_filter = list(FLAG_NAMES)


@admin.register(OrganisationMessagingConfig)
class OrganisationMessagingConfigAdmin(SiteAwareModelAdmin):
    list_display = ["__str__", *FLAG_NAMES]
    list_filter = list(FLAG_NAMES)
    autocomplete_fields = ["organisation"]
    search_fields = ["organisation__name"]


@admin.register(CohortMessagingConfig)
class CohortMessagingConfigAdmin(SiteAwareModelAdmin):
    list_display = ["__str__", *FLAG_NAMES]
    list_filter = list(FLAG_NAMES)
    autocomplete_fields = ["cohort"]
    search_fields = ["cohort__name"]


@admin.register(LearnerMessagingConfig)
class LearnerMessagingConfigAdmin(SiteAwareModelAdmin):
    list_display = ["__str__", *FLAG_NAMES]
    list_filter = list(FLAG_NAMES)
    autocomplete_fields = ["learner"]
    search_fields = ["learner__user__email"]


@admin.register(LearnerCourseRegistrationMessagingConfig)
class LearnerCourseRegistrationMessagingConfigAdmin(SiteAwareModelAdmin):
    list_display = ["__str__", "learner_to_course_peer"]
    list_filter = ["learner_to_course_peer"]
    autocomplete_fields = ["registration"]
    search_fields = ["registration__learner__user__email"]


@admin.register(CohortCourseRegistrationMessagingConfig)
class CohortCourseRegistrationMessagingConfigAdmin(SiteAwareModelAdmin):
    list_display = ["__str__", "learner_to_course_peer"]
    list_filter = ["learner_to_course_peer"]
    autocomplete_fields = ["registration"]
    search_fields = ["registration__cohort__name"]
