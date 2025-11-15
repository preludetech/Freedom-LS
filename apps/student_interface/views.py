from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.urls import reverse
from django.utils import timezone
from content_engine.models import Topic, Form, ContentCollection
from student_progress.models import FormProgress, TopicProgress, QuestionAnswer
from student_management.models import Student
from student_management.models import Student, StudentCourseRegistration


# def get_navigation_items(collection, current_item):
#     """Get previous and next items in a collection relative to current item."""
#     children = collection.children()
#     current_index = None

#     for i, child in enumerate(children):
#         if child.pk == current_item.pk and type(child) is type(current_item):
#             current_index = i
#             break

#     if current_index is None:
#         return None, None

#     previous_item = children[current_index - 1] if current_index > 0 else None
#     next_item = (
#         children[current_index + 1] if current_index < len(children) - 1 else None
#     )

#     return previous_item, next_item


# def get_item_url(item, collection_slug=None):
#     """Get the URL for a content item (Topic, Form, or Collection)."""
#     if isinstance(item, Topic):
#         if collection_slug:
#             return reverse(
#                 "student_interface:topic_detail_in_collection",
#                 kwargs={"collection_slug": collection_slug, "topic_slug": item.slug},
#             )
#         return reverse(
#             "student_interface:topic_detail", kwargs={"topic_slug": item.slug}
#         )
#     elif isinstance(item, Form):
#         if collection_slug:
#             return reverse(
#                 "student_interface:form_detail_in_collection",
#                 kwargs={"collection_slug": collection_slug, "form_slug": item.slug},
#             )
#         return reverse("student_interface:form_detail", kwargs={"form_slug": item.slug})
#     elif isinstance(item, ContentCollection):
#         return reverse(
#             "student_interface:course_home", kwargs={"collection_slug": item.slug}
#         )
#     return None


# @login_required
# def topic_detail(request, topic_slug, collection_slug=None):
#     """View to display a topic for students."""
#     topic = get_object_or_404(Topic, slug=topic_slug)

#     # Track progress


#     # Handle "mark complete" POST request
#     if request.method == "POST" and "mark_complete" in request.POST:
#         topic_progress.complete_time = timezone.now()
#         topic_progress.save()

#         if collection_slug:
#             collection = get_object_or_404(ContentCollection, slug=collection_slug)
#             _, next_item = get_navigation_items(collection, topic)
#             if next_item:
#                 return redirect(get_item_url(next_item, collection.slug))
#             return redirect(
#                 "student_interface:course_home", collection_slug=collection.slug
#             )

#         return redirect("student_interface:topic_detail", topic_slug=topic.slug)

#     # Get navigation items
#     collection = None
#     previous_url = None
#     next_url = None

#     if collection_slug:
#         collection = get_object_or_404(ContentCollection, slug=collection_slug)
#         previous_item, next_item = get_navigation_items(collection, topic)

#         if previous_item:
#             previous_url = get_item_url(previous_item, collection.slug)
#         if next_item:
#             next_url = get_item_url(next_item, collection.slug)

#     return render(
#         request,
#         "content_engine/topic_detail.html",
#         {
#             "topic": topic,
#             "collection": collection,
#             "previous_url": previous_url,
#             "next_url": next_url,
#             "is_complete": topic_progress.complete_time is not None,
#         },
#     )


# @login_required
# def form_detail(request, form_slug, collection_slug=None):
#     """View to display a form for students."""
#     form = get_object_or_404(Form, slug=form_slug)

#     # Try to get existing incomplete form progress (don't create if it doesn't exist)
#     form_progress = (
#         FormProgress.objects.filter(
#             user=request.user, form=form, completed_time__isnull=True
#         )
#         .order_by("-start_time")
#         .first()
#     )

#     page_number = None
#     if form_progress:
#         page_number = form_progress.get_current_page_number()

#     collection = None
#     if collection_slug:
#         collection = get_object_or_404(ContentCollection, slug=collection_slug)

#     return render(
#         request,
#         "content_engine/form_detail.html",
#         {
#             "form": form,
#             "page_number": page_number,
#             "form_progress": form_progress,
#             "collection": collection,
#         },
#     )


# @login_required
# def form_start(request, form_slug):
#     """Start or resume a form for the current user."""
#     form = get_object_or_404(Form, slug=form_slug)

#     # Create a FormProgress instance if it doesn't yet exist
#     form_progress = FormProgress.get_or_create_incomplete(request.user, form)

#     # Figure out what page of the form the user is on
#     page_number = form_progress.get_current_page_number()

#     # Redirect the user to form_fill_page
#     return redirect(
#         "student_interface:form_fill_page", pk=form_progress.pk, page_number=page_number
#     )


# @login_required
# def form_fill_page(request, pk, page_number):
#     """View to display a specific page of a form for the user to fill."""
#     # Get the FormProgress instance
#     form_progress = get_object_or_404(FormProgress, pk=pk)

#     # Ensure the form_progress belongs to the current user
#     if form_progress.user != request.user:
#         return redirect(
#             "student_interface:form_start", form_slug=form_progress.form.slug
#         )

#     if request.method == "POST":
#         # Get the form and current page
#         form = form_progress.form
#         all_pages = list(form.pages.all())
#         total_pages = len(all_pages)

#         if page_number < 1 or page_number > total_pages:
#             return redirect("student_interface:form_start", form_slug=form.slug)

#         form_page = all_pages[page_number - 1]

#         # Get all questions on this page
#         questions = [
#             child
#             for child in form_page.children()
#             if hasattr(child, "question")  # It's a FormQuestion
#         ]

#         # Process each question's answer
#         for question in questions:
#             field_name = f"question_{question.id}"

#             # Get or create the answer
#             answer, created = QuestionAnswer.objects.get_or_create(
#                 form_progress=form_progress, question=question
#             )

#             # Handle different question types
#             if question.type == "multiple_choice":
#                 # Get the selected option ID from POST
#                 option_id = request.POST.get(field_name)
#                 if option_id:
#                     # Clear existing selections and set the new one
#                     answer.selected_options.clear()
#                     answer.selected_options.add(option_id)
#                     answer.save()

#             elif question.type == "checkboxes":
#                 # Get all selected option IDs (can be multiple)
#                 option_ids = request.POST.getlist(field_name)
#                 if option_ids:
#                     answer.selected_options.clear()
#                     answer.selected_options.add(*option_ids)
#                     answer.save()

#             elif question.type in ["short_text", "long_text"]:
#                 # Get text answer
#                 text_answer = request.POST.get(field_name, "")
#                 answer.text_answer = text_answer
#                 answer.save()

#         # Determine where to redirect
#         if page_number < total_pages:
#             # Redirect to next page
#             return redirect(
#                 "student_interface:form_fill_page",
#                 pk=form_progress.pk,
#                 page_number=page_number + 1,
#             )
#         else:
#             # This was the last page, mark as complete, calculate score, and redirect to complete page
#             form_progress.completed_time = timezone.now()
#             form_progress.save()

#             # Calculate scores based on the form's strategy
#             form_progress.score()

#             return redirect("student_interface:form_complete", pk=form_progress.pk)

#     # Get the form and all its pages
#     form = form_progress.form
#     all_pages = list(form.pages.all())
#     total_pages = len(all_pages)

#     # Get the specific page (page_number is 1-indexed)
#     if page_number < 1 or page_number > total_pages:
#         # Invalid page number, redirect to form start
#         return redirect("student_interface:form_start", pk=form.pk)

#     form_page = all_pages[page_number - 1]

#     # Get existing answers for questions on this page
#     questions = [
#         child
#         for child in form_page.children()
#         if hasattr(child, "question")  # It's a FormQuestion
#     ]

#     # Build a dictionary of existing answers keyed by question ID
#     existing_answers = {}
#     for question in questions:
#         try:
#             answer = QuestionAnswer.objects.get(
#                 form_progress=form_progress, question=question
#             )
#             existing_answers[question.id] = answer
#         except QuestionAnswer.DoesNotExist:
#             pass

#     # Calculate navigation
#     previous_page = all_pages[page_number - 2] if page_number > 1 else None
#     next_page = all_pages[page_number] if page_number < total_pages else None
#     pages_left = total_pages - page_number

#     context = {
#         "form": form,
#         "form_page": form_page,
#         "form_progress": form_progress,
#         "current_page_num": page_number,
#         "total_pages": total_pages,
#         "pages_left": pages_left,
#         "previous_page": previous_page,
#         "next_page": next_page,
#         "existing_answers": existing_answers,
#     }

#     return render(request, "content_engine/form_page_detail.html", context)


# @login_required
# def form_complete(request, pk):
#     """View displayed when a user completes a form."""
#     form_progress = get_object_or_404(FormProgress, pk=pk)

#     # Ensure the form_progress belongs to the current user
#     if form_progress.user != request.user:
#         return redirect(
#             "student_interface:form_start", form_slug=form_progress.form.slug
#         )

#     # Ensure the form is actually complete
#     if not form_progress.completed_time:
#         return redirect(
#             "student_interface:form_fill_page",
#             pk=form_progress.pk,
#             page_number=form_progress.get_current_page_number(),
#         )

#     # Check if we should display category scores
#     from content_engine.models import FormStrategy

#     show_scores = form_progress.form.strategy == FormStrategy.CATEGORY_VALUE_SUM

#     context = {
#         "form": form_progress.form,
#         "form_progress": form_progress,
#         "show_scores": show_scores,
#         "scores": form_progress.scores if show_scores else None,
#     }

#     return render(request, "student_interface/form_complete.html", context)


# def course_home(request, collection_slug):
#     # TODO: check that the student is registered for the course

#     BLOCKED = "BLOCKED"
#     READY = "READY"
#     IN_PROGRESS = "IN_PROGRESS"
#     COMPLETE = "COMPLETE"

#     collection = get_object_or_404(ContentCollection, slug=collection_slug)

#     children = [
#         # {title, status, url}
#     ]

#     next_status = READY  # First item starts as READY
#     for _i, child in enumerate(collection.children()):
#         # create a list of children dicts
#         # status is either blocked, ready, in progress or complete
#         # users need to complete things in order, an item is blocked if the previous item has not been completed yet

#         status = None
#         url = None
#         title = None

#         if isinstance(child, Topic):
#             title = child.title
#             url = reverse(
#                 "student_interface:topic_detail_in_collection",
#                 kwargs={"collection_slug": collection.slug, "topic_slug": child.slug},
#             )

#             # Check progress
#             topic_progress = TopicProgress.objects.filter(
#                 user=request.user, topic=child
#             ).first()

#             if topic_progress and topic_progress.complete_time:
#                 status = COMPLETE
#             elif topic_progress:
#                 status = IN_PROGRESS
#             elif next_status == READY:
#                 status = READY
#             else:
#                 status = BLOCKED

#         elif isinstance(child, Form):
#             title = child.title
#             url = reverse(
#                 "student_interface:form_detail_in_collection",
#                 kwargs={"collection_slug": collection.slug, "form_slug": child.slug},
#             )

#             # Check progress
#             form_progress = (
#                 FormProgress.objects.filter(user=request.user, form=child)
#                 .order_by("-start_time")
#                 .first()
#             )

#             if form_progress and form_progress.completed_time:
#                 status = COMPLETE
#             elif form_progress:
#                 status = IN_PROGRESS
#             elif next_status == READY:
#                 status = READY
#             else:
#                 status = BLOCKED

#         elif isinstance(child, ContentCollection):
#             title = child.title
#             url = reverse(
#                 "student_interface:course_home", kwargs={"collection_slug": child.slug}
#             )

#             # For collections, check if all direct children are complete
#             # TODO: implement proper recursive collection completion checking
#             if next_status == READY:
#                 status = READY
#             else:
#                 status = BLOCKED

#         children.append({"title": title, "status": status, "url": url})

#         # Update next_status for the next iteration
#         if status == COMPLETE:
#             next_status = READY
#         else:
#             next_status = BLOCKED

#     return render(
#         request,
#         "student_interface/course_home.html",
#         {"collection": collection, "children": children},
#     )


def course_home(request, collection_slug):
    course = get_object_or_404(ContentCollection, slug=collection_slug)

    children = get_course_index(course=course, request=request)
    is_registered = get_is_registered(request, course)

    return render(
        request,
        "student_interface/course_home.html",
        {"course": course, "children": children, "is_registered": is_registered},
    )


def partial_course_toc(request, collection_slug):
    course = get_object_or_404(ContentCollection, slug=collection_slug)

    children = get_course_index(course=course, request=request)
    is_registered = get_is_registered(request, course)

    return render(
        request,
        "student_interface/partials/course_minimal_toc.html",
        {"course": course, "children": children, "is_registered": is_registered},
    )


def get_is_registered(request, course):
    # Check if user is registered for the course
    is_registered = False
    if request.user.is_authenticated:
        try:
            student = Student.objects.get(user=request.user)
            registered_courses = student.get_course_registrations()
            is_registered = course in registered_courses
        except Student.DoesNotExist:
            is_registered = False
    return is_registered


def get_course_index(request, course):
    BLOCKED = "BLOCKED"
    READY = "READY"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETE = "COMPLETE"

    is_registered = get_is_registered(request, course)

    # Get the children of this course
    children = [
        # {title, status, url}
    ]

    if is_registered:
        next_status = READY  # First item starts as READY
        for index, child in enumerate(course.children()):
            # create a list of children dicts
            # status is either blocked, ready, in progress or complete
            # users need to complete things in order, an item is blocked if the previous item has not been completed yet

            status = None
            url = reverse(
                "student_interface:view_course_item",
                kwargs={"collection_slug": course.slug, "index": index + 1},
            )
            title = None

            if isinstance(child, Topic):
                title = child.title

                # Check progress
                topic_progress = TopicProgress.objects.filter(
                    user=request.user, topic=child
                ).first()

                if topic_progress and topic_progress.complete_time:
                    status = COMPLETE
                elif topic_progress:
                    status = IN_PROGRESS
                elif next_status == READY:
                    status = READY
                else:
                    status = BLOCKED

            elif isinstance(child, Form):
                title = child.title

                # Check progress
                form_progress = (
                    FormProgress.objects.filter(user=request.user, form=child)
                    .order_by("-start_time")
                    .first()
                )

                if form_progress and form_progress.completed_time:
                    status = COMPLETE
                elif form_progress:
                    status = IN_PROGRESS
                elif next_status == READY:
                    status = READY
                else:
                    status = BLOCKED

            elif isinstance(child, ContentCollection):
                NotImplemented
                title = child.title
                # url = reverse(
                #     "student_interface:course_home",
                #     kwargs={"collection_slug": child.slug},
                # )
                url = "todo"

                # For collections, check if all direct children are complete
                # TODO: implement proper recursive collection completion checking
                if next_status == READY:
                    status = READY
                else:
                    status = BLOCKED

            children.append({"title": title, "status": status, "url": url})

            # Update next_status for the next iteration
            if status == COMPLETE:
                next_status = READY
            else:
                next_status = BLOCKED

    else:
        children = [
            {"title": child.title, "status": BLOCKED, "url": ""}
            for child in course.children()
        ]
    return children


def home(request):
    """Home page with list of available courses."""
    return render(request, "student_interface/home.html")


def partial_list_courses(request):
    """Return a partial HTML section listing all available courses."""
    from student_management.models import Student

    all_courses = ContentCollection.objects.all()
    registered_courses = []

    if request.user.is_authenticated:
        try:
            student = Student.objects.get(user=request.user)
            registered_courses = student.get_course_registrations()
        except Student.DoesNotExist:
            registered_courses = []

    context = {
        "all_courses": all_courses,
        "registered_courses": registered_courses,
    }

    return render(request, "student_interface/partials/course_list.html", context)


@login_required
def register_for_course(request, collection_slug):
    """Register the current user for a course."""

    course = get_object_or_404(ContentCollection, slug=collection_slug)

    # Get or create Student instance for this user
    student, _ = Student.objects.get_or_create(user=request.user)

    # Create the course registration
    StudentCourseRegistration.objects.get_or_create(
        student=student,
        collection=course,
        defaults={"is_active": True},
    )

    # Redirect back to the course home page
    return redirect("student_interface:course_home", collection_slug=collection_slug)


def view_course_item(request, collection_slug, index):
    course = get_object_or_404(ContentCollection, slug=collection_slug)

    children = course.children()
    current_item = children[index - 1]

    total_children = len(children)

    # Calculate navigation URLs
    next_url = None
    if index < total_children:
        next_url = reverse(
            "student_interface:view_course_item",
            kwargs={"collection_slug": collection_slug, "index": index + 1},
        )

    previous_url = None
    if index > 1:
        previous_url = reverse(
            "student_interface:view_course_item",
            kwargs={"collection_slug": collection_slug, "index": index - 1},
        )

    if isinstance(current_item, Topic):
        return view_topic(
            request,
            topic=current_item,
            course=course,
            next_url=next_url,
            previous_url=previous_url,
        )

    if isinstance(current_item, Form):
        return view_form(request, form=current_item, course=course)


def view_topic(request, topic, course, next_url, previous_url):
    topic_progress, created = TopicProgress.objects.get_or_create(
        user=request.user, topic=topic
    )
    if not created:
        topic_progress.save()

    if request.method == "POST" and "mark_complete" in request.POST:
        topic_progress.complete_time = timezone.now()
        topic_progress.save()

        if next_url:
            return redirect(next_url)

    context = {
        "course": course,
        "topic": topic,
        "is_complete": topic_progress.complete_time is not None,
        "next_url": next_url,
        "previous_url": previous_url,
    }
    return render(request, "student_interface/course_topic.html", context)
