from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from content_engine.models import Topic, Form
from .models import FormProgress


@login_required
def topic_detail(request, pk):
    """View to display a topic for students."""
    topic = get_object_or_404(Topic, pk=pk)
    return render(request, "content_engine/topic_detail.html", {"topic": topic})


@login_required
def form_detail(request, pk):
    """View to display a form for students."""
    form = get_object_or_404(Form, pk=pk)

    # Try to get existing incomplete form progress (don't create if it doesn't exist)
    form_progress = (
        FormProgress.objects.filter(
            user=request.user, form=form, completed_time__isnull=True
        )
        .order_by("-start_time")
        .first()
    )

    page_number = None
    if form_progress:
        page_number = form_progress.get_current_page_number()

    return render(
        request,
        "content_engine/form_detail.html",
        {
            "form": form,
            "page_number": page_number,
            "form_progress": form_progress,
        },
    )


@login_required
def form_start(request, pk):
    """Start or resume a form for the current user."""
    form = get_object_or_404(Form, pk=pk)

    # Create a FormProgress instance if it doesn't yet exist
    form_progress = FormProgress.get_or_create_incomplete(request.user, form)

    # Figure out what page of the form the user is on
    page_number = form_progress.get_current_page_number()

    # Redirect the user to form_fill_page
    return redirect(
        "student_interface:form_fill_page", pk=form_progress.pk, page_number=page_number
    )


@login_required
def form_fill_page(request, pk, page_number):
    """View to display a specific page of a form for the user to fill."""
    # Get the FormProgress instance
    form_progress = get_object_or_404(FormProgress, pk=pk)

    # Ensure the form_progress belongs to the current user
    if form_progress.user != request.user:
        return redirect("student_interface:form_start", pk=form_progress.form.pk)

    if request.method == "POST":
        TODO

    # Get the form and all its pages
    form = form_progress.form
    all_pages = list(form.pages.all())
    total_pages = len(all_pages)

    # Get the specific page (page_number is 1-indexed)
    if page_number < 1 or page_number > total_pages:
        # Invalid page number, redirect to form start
        return redirect("student_interface:form_start", pk=form.pk)

    form_page = all_pages[page_number - 1]

    # Calculate navigation
    previous_page = all_pages[page_number - 2] if page_number > 1 else None
    next_page = all_pages[page_number] if page_number < total_pages else None
    pages_left = total_pages - page_number

    context = {
        "form": form,
        "form_page": form_page,
        "form_progress": form_progress,
        "current_page_num": page_number,
        "total_pages": total_pages,
        "pages_left": pages_left,
        "previous_page": previous_page,
        "next_page": next_page,
    }

    return render(request, "content_engine/form_page_detail.html", context)
