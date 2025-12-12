from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone
from django.utils.text import slugify

from content_engine.models import Activity
from site_aware_models.models import SiteAwareModel
from student_progress.models import FormProgress


class Child(SiteAwareModel):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="children"
    )
    name = models.CharField(max_length=255)
    date_of_birth = models.DateField()
    gender = models.CharField(
        max_length=20,
        choices=[
            ("male", "Male"),
            ("female", "Female"),
            ("other", "Other"),
            ("prefer_not_to_say", "Prefer not to say"),
        ],
    )
    slug = models.SlugField(max_length=255, unique=True, blank=True)

    class Meta:
        verbose_name_plural = "Children"


    def clean(self):
        super().clean()
        if self.date_of_birth and self.date_of_birth >= timezone.now().date():
            raise ValidationError(
                {"date_of_birth": "Date of birth must be in the past."}
            )

    def save(self, *args, **kwargs):
        # self.full_clean()
        if not self.slug:
            base_slug = slugify(self.name)
            slug = base_slug
            counter = 1
            while Child.objects.filter(slug=slug).exists():
                slug = f"{base_slug}-{counter}"
                counter += 1
            self.slug = slug
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.name} ({self.date_of_birth}) - {self.user}"

    def age(self):
        """Calculate and return the age in years and months."""
        today = timezone.now().date()

        years = today.year - self.date_of_birth.year
        months = today.month - self.date_of_birth.month

        if months < 0:
            years -= 1
            months += 12

        if today.day < self.date_of_birth.day:
            months -= 1
            if months < 0:
                years -= 1
                months += 12

        year_str = "year" if years == 1 else "years"
        month_str = "month" if months == 1 else "months"

        return f"{years} {year_str}, {months} {month_str}"


class ChildFormProgress(SiteAwareModel):
    form_progress = models.ForeignKey(FormProgress, on_delete=models.CASCADE)
    child = models.ForeignKey(Child, on_delete=models.CASCADE)

    def __str__(self):
        return f"{self.child.name} - {self.form_progress.form.title}"

    @classmethod
    def get_latest_incomplete(cls, child, form):
        """Get the latest incomplete form progress for a specific child and form."""
        child_form_progress = cls.objects.filter(
            child=child,
            form_progress__form=form,
            form_progress__completed_time__isnull=True,
        ).first()

        if child_form_progress:
            return child_form_progress.form_progress
        return None

    @classmethod
    def get_latest_complete(cls, child, form):
        """Get the latest completed form progress for a specific child and form."""
        child_form_progress = (
            cls.objects.filter(
                child=child,
                form_progress__form=form,
                form_progress__completed_time__isnull=False,
            )
            .order_by("-form_progress__completed_time")
            .first()
        )

        if child_form_progress:
            return child_form_progress.form_progress
        return None


class RecommendedActivity(SiteAwareModel):
    """
    Activity recommendations for children.
    Created when a parent fills out a form for their child.
    """

    child = models.ForeignKey(
        Child, on_delete=models.CASCADE, related_name="recommended_activities"
    )
    activity = models.ForeignKey(
        Activity, on_delete=models.CASCADE, related_name="recommendations"
    )
    form_progress = models.ForeignKey(
        FormProgress, on_delete=models.CASCADE, null=True, blank=True
    )
    created_at = models.DateTimeField(auto_now_add=True)
    active = models.BooleanField(default=True)
    deactivated_at = models.DateTimeField(null=True, blank=True)
    deactivation_reason = models.CharField(
        max_length=20,
        null=True,
        blank=True,
        choices=[
            ("completed", "Completed"),
            ("too_hard", "Too Hard"),
            ("too_easy", "Too Easy"),
        ],
    )

    class Meta:
        ordering = ["-created_at"]
        verbose_name_plural = "Recommended activities"

    def __str__(self):
        return f"Activity recommendation for {self.child.name}: {self.activity.title}"

    def mark_complete(self):
        """Mark this recommendation as completed successfully."""
        from django.utils import timezone

        self.active = False
        self.deactivated_at = timezone.now()
        self.deactivation_reason = "completed"
        self.save()

    def mark_too_hard(self):
        """Mark this recommendation as too hard for the child."""
        from django.utils import timezone

        self.active = False
        self.deactivated_at = timezone.now()
        self.deactivation_reason = "too_hard"
        self.save()

    def mark_too_easy(self):
        """Mark this recommendation as too easy for the child."""
        from django.utils import timezone

        self.active = False
        self.deactivated_at = timezone.now()
        self.deactivation_reason = "too_easy"
        self.save()


class CommittedActivity(SiteAwareModel):
    child = models.ForeignKey(
        Child, on_delete=models.CASCADE, related_name="activities"
    )
    activity = models.ForeignKey(
        Activity,
        on_delete=models.CASCADE,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    stopped_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name_plural = "Committed activities"

    def __str__(self):
        status = "Active" if not self.stopped_at else f"Stopped {self.stopped_at.date()}"
        return f"{self.child.name} - {self.activity.title} ({status})"


class ActivityLog(SiteAwareModel):
    """
    Log of activities performed by a child on a specific date.
    Tracks whether the activity was completed (done=True), not done (done=False), or not yet marked (done=None).
    """

    child = models.ForeignKey(
        Child, on_delete=models.CASCADE, related_name="activity_logs"
    )
    activity = models.ForeignKey(
        Activity, on_delete=models.CASCADE, related_name="logs"
    )
    date = models.DateField()
    done = models.BooleanField(null=True, blank=True, default=None)

    notes = models.TextField(null=True, blank=True)
    sentiment = models.CharField(
        max_length=20,
        null=True,
        blank=True,
        choices=[
            ("good", "Good"),
            ("bad", "Bad"),
            ("neutral", "Neutral"),
        ],
    )

    class Meta:
        ordering = ["-date"]
        unique_together = ["child", "activity", "date"]
        verbose_name_plural = "Activity logs"

    def __str__(self):
        status = (
            "Done"
            if self.done is True
            else "Not done"
            if self.done is False
            else "Not marked"
        )
        return f"{self.child.name} - {self.activity.title} on {self.date} ({status})"
