from django.conf import settings
from django.db import models
from django.utils.text import slugify

from content_engine.models import Activity, ContentCollection
from site_aware_models.models import SiteAwareModel
from student_progress.models import FormProgress


class Child(SiteAwareModel):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="children"
    )
    name = models.CharField(max_length=255)
    age = models.IntegerField()
    slug = models.SlugField(max_length=255, unique=True, blank=True)

    def save(self, *args, **kwargs):
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
        return f"{self.name} ({self.age}) - {self.user}"


class ChildFormProgress(SiteAwareModel):
    form_progress = models.ForeignKey(FormProgress, on_delete=models.CASCADE)
    child = models.ForeignKey(Child, on_delete=models.CASCADE)

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

    class Meta:
        ordering = ["-created_at"]
        verbose_name_plural = "Recommended activities"

    def __str__(self):
        return f"Activity recommendation for {self.child.name}: {self.activity.title}"


class CommittedActivity(SiteAwareModel):
    child = models.ForeignKey(
        Child, on_delete=models.CASCADE, related_name="activities"
    )
    activity = models.ForeignKey(
        Activity,
        on_delete=models.CASCADE,
    )
    created_at = models.DateTimeField(auto_now_add=True)


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
