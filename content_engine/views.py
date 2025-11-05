from django.shortcuts import render, get_object_or_404
from .models import Topic, ContentCollection, Form, FormPage


def topic_detail(request, pk):
    """Simple view to display a topic."""
    topic = get_object_or_404(Topic, pk=pk)
    return render(
        request, "content_engine/topic_detail.html", {"topic": topic, "preview": True}
    )


def collection_detail(request, pk):
    """Simple view to display a collection."""
    collection = get_object_or_404(ContentCollection, pk=pk)
    children = collection.children()
    return render(
        request,
        "content_engine/collection_detail.html",
        {"collection": collection, "children": children, "preview": True},
    )


def form_detail(request, pk):
    """Simple view to display a form."""
    form = get_object_or_404(Form, pk=pk)
    first_page = form.pages.first()
    return render(
        request,
        "content_engine/form_detail.html",
        {"form": form, "first_page": first_page, "preview": True},
    )


def form_page_detail(request, pk):
    """Simple view to display a form page with navigation info."""
    form_page = get_object_or_404(FormPage, pk=pk)

    # Get all pages for this form to calculate position
    all_pages = list(form_page.form.pages.all())
    total_pages = len(all_pages)

    # Find current page index (0-indexed)
    current_index = next(
        (i for i, page in enumerate(all_pages) if page.pk == form_page.pk), 0
    )

    current_page_num = current_index + 1
    pages_left = total_pages - current_page_num

    # Calculate previous and next pages
    previous_page = all_pages[current_index - 1] if current_index > 0 else None
    next_page = (
        all_pages[current_index + 1] if current_index < total_pages - 1 else None
    )

    context = {
        "form_page": form_page,
        "form": form_page.form,
        "current_page_num": current_page_num,
        "total_pages": total_pages,
        "pages_left": pages_left,
        "previous_page": previous_page,
        "next_page": next_page,
        "preview": True,
    }

    return render(request, "content_engine/form_page_detail.html", context)
