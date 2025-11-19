from django.conf import settings
from django.db import models
from django.utils.text import slugify


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
        child_form_progress = cls.objects.filter(
            child=child,
            form_progress__form=form,
            form_progress__completed_time__isnull=False,
        ).order_by('-form_progress__completed_time').first()

        if child_form_progress:
            return child_form_progress.form_progress
        return None
