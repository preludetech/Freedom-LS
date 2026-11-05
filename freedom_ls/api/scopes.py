from django.db import models


class ApiScope(models.TextChoices):
    USERS = "users", "Users"
    COURSE_APPLICATIONS = "course_applications", "Course applications"
    REFERRAL_DATA = "referral_data", "Referral data"
    REGISTRATIONS_AND_PROGRESS = (
        "registrations_and_progress",
        "Registrations and progress",
    )

    @property
    def description(self) -> str:
        """The model classes this API scope reads, for admin help text."""
        return _DESCRIPTIONS[self]


_DESCRIPTIONS: dict[ApiScope, str] = {
    ApiScope.USERS: "User",
    ApiScope.COURSE_APPLICATIONS: "CourseApplication and its answers",
    ApiScope.REFERRAL_DATA: "ReferralCode, ReferralCodeHit, SignupAttribution, FirstTouchCount",
    ApiScope.REGISTRATIONS_AND_PROGRESS: (
        "LearnerCourseRegistration, CohortCourseRegistration, CourseInterest, CourseProgress"
    ),
}
