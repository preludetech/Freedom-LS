from uuid import UUID

from django.http import HttpRequest, HttpResponseRedirect
from django.shortcuts import get_object_or_404
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_safe

from freedom_ls.content_engine.models import File


@require_safe
@never_cache
def audio_file(request: HttpRequest, pk: UUID) -> HttpResponseRedirect:
    """Redirect to a freshly signed URL for an audio file.

    The page holds this URL rather than a signed one, so a page left open past
    the signature's lifetime still plays. It needs no login and never expires:
    the UUID lookup is site-scoped, limited to audio files and skips retired
    files, and checks no course access or publication state, so anyone holding
    the UUID can play the file for as long as the row is live.
    """
    file_obj = get_object_or_404(
        File.objects.not_retired(), pk=pk, file_type=File.FileType.AUDIO
    )
    return HttpResponseRedirect(file_obj.file.url)
