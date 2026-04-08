from django.contrib.auth.decorators import login_required
from django.contrib.contenttypes.models import ContentType
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_GET, require_POST

from freedom_ls.feedback.models import FeedbackDismissal, FeedbackForm, FeedbackResponse


@login_required
@require_GET
def feedback_form_view(request: HttpRequest, form_id: str) -> HttpResponse:
    """Return the rendered feedback form partial (for HTMX lazy-load)."""
    feedback_form = get_object_or_404(FeedbackForm, id=form_id)
    content_type_id = request.GET.get("content_type_id")
    object_id = request.GET.get("object_id")

    # Clear pending_feedback from session
    request.session.pop("pending_feedback", None)
    request.session["feedback_shown_this_session"] = True

    context = {
        "feedback_form": feedback_form,
        "content_type_id": content_type_id,
        "object_id": object_id,
    }
    return render(request, "partials/feedback_form.html", context)


@login_required
@require_POST
def feedback_submit_view(request: HttpRequest, form_id: str) -> HttpResponse:
    """Validate rating (1-5), save FeedbackResponse, return thank-you partial."""
    feedback_form = get_object_or_404(FeedbackForm, id=form_id)

    try:
        rating = int(request.POST.get("rating", 0))
    except (ValueError, TypeError):
        return HttpResponse("Invalid rating", status=422)
    if rating < 1 or rating > 5:
        return HttpResponse("Invalid rating", status=422)

    comment = request.POST.get("comment", "")
    content_type_id = request.POST.get("content_type_id")
    object_id = request.POST.get("object_id")
    content_type = get_object_or_404(ContentType, id=content_type_id)

    FeedbackResponse.objects.create(
        form=feedback_form,
        user=request.user,
        content_type=content_type,
        object_id=object_id,
        rating=rating,
        comment=comment,
    )

    request.session["feedback_shown_this_session"] = True
    request.session.pop("pending_feedback", None)

    return render(request, "partials/thank_you.html", {"feedback_form": feedback_form})


@login_required
@require_POST
def feedback_dismiss_view(request: HttpRequest, form_id: str) -> HttpResponse:
    """Create FeedbackDismissal record and return 204."""
    feedback_form = get_object_or_404(FeedbackForm, id=form_id)
    content_type_id = request.POST.get("content_type_id")
    object_id = request.POST.get("object_id")
    content_type = get_object_or_404(ContentType, id=content_type_id)

    FeedbackDismissal.objects.create(
        form=feedback_form,
        user=request.user,
        content_type=content_type,
        object_id=object_id,
    )

    request.session["feedback_shown_this_session"] = True
    request.session.pop("pending_feedback", None)

    return HttpResponse(status=204)
