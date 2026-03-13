from django import forms
from django.core.files.uploadedfile import UploadedFile
from django.http import HttpRequest
from django.utils.datastructures import MultiValueDict

from freedom_ls.site_aware_models.models import _thread_locals, get_cached_site
from freedom_ls.student_management.models import Cohort


class CohortForm(forms.ModelForm):
    class Meta:
        model = Cohort
        fields = ["name"]

    def __init__(
        self,
        data: dict[str, str] | None = None,
        files: MultiValueDict[str, UploadedFile] | None = None,
        instance: Cohort | None = None,
        request: HttpRequest | None = None,
    ) -> None:
        self._form_request = request
        super().__init__(data, files, instance=instance)

    def clean(self) -> dict[str, object] | None:
        """Set site before unique validation so (site, name) constraint is checked.

        This runs before _post_clean which calls instance.validate_unique().
        """
        cleaned_data = super().clean()
        instance = self.instance
        if not instance.site_id:
            request = getattr(_thread_locals, "request", None) or self._form_request
            if request:
                instance.site = get_cached_site(request)
        return cleaned_data
