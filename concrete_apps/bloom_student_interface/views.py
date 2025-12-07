from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse_lazy, reverse
from django.views.generic import CreateView, UpdateView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from django import forms
from datetime import datetime, timedelta
from content_engine.models import Form, Activity
from student_progress.models import FormProgress
from student_management.models import Student, RecommendedCourse
from .models import (
    Child,
    ChildFormProgress,
    CommittedActivity,
    ActivityLog,
)

from .activity_utils import (
    make_activity_recommendations,
    get_activity_good_streak,
    get_activity_bad_streak,
    adjust_activity_recommendations_positive,
    adjust_activity_recommendations_negative,
)
from django.conf import settings
from django.template.loader import render_to_string
from django.http import HttpResponse


@login_required
def home(request):
    """Home page with list of available courses."""

    # children = []
    # recommended_courses = []
    # registered_courses = []
    # activity_logs_today = {}

    if request.user.is_authenticated:
        return redirect("bloom_student_interface:children")

    #     children = Child.objects.filter(user=request.user).prefetch_related(
    #         "activities__activity"
    #     )
    #     recommended_courses = RecommendedCourse.objects.filter(
    #         user=request.user
    #     ).select_related("collection")

    #     # Get registered courses if user has a Student record
    #     try:
    #         student = Student.objects.get(user=request.user)
    #         registered_courses = student.get_course_registrations()
    #     except Student.DoesNotExist:
    #         pass

    #     # Get today's activity logs for all children
    #     today = timezone.now().date()
    #     logs = ActivityLog.objects.filter(
    #         child__user=request.user, date=today
    #     ).select_related("child", "activity")

    #     activity_logs_today = {}
    #     for log in logs:
    #         child_id = log.child_id
    #         activity_id = log.activity_id
    #         activity_logs_today[child_id] = activity_logs_today.get(child_id, {})
    #         activity_logs_today[child_id][activity_id] = log.done

    # # Format date as string for URL
    # today_str = (
    #     timezone.now().date().strftime("%Y-%m-%d")
    #     if request.user.is_authenticated
    #     else ""
    # )

    # return render(
    #     request,
    #     "student_interface/home.html",
    #     {
    #         "children": children,
    #         "recommended_courses": recommended_courses,
    #         "registered_courses": registered_courses,
    #         "activity_logs_today": activity_logs_today,
    #         "date": today_str,
    #     },
    # )


# class ChildCreateView(LoginRequiredMixin, CreateView):
#     """Create a new child."""

#     model = Child
#     template_name = "bloom_student_interface/child_form.html"
#     fields = ["name", "age"]
#     success_url = reverse_lazy("bloom_student_interface:home")

#     def form_valid(self, form):
#         form.instance.user = self.request.user
#         return super().form_valid(form)


# class ChildUpdateView(LoginRequiredMixin, UpdateView):
#     """Edit an existing child."""

#     model = Child
#     template_name = "bloom_student_interface/child_form.html"
#     fields = ["name", "age"]
#     success_url = reverse_lazy("bloom_student_interface:home")

#     def get_queryset(self):
#         return Child.objects.filter(user=self.request.user)


# @login_required
# def child_delete(request, pk):
#     """Delete a child."""
#     child = get_object_or_404(Child, pk=pk, user=request.user)

#     if request.method == "POST":
#         child.delete()
#         return redirect("bloom_student_interface:home")

#     return redirect("bloom_student_interface:home")


@login_required
def child_assessment(request, slug):
    """Picky eating assessment for a specific child."""
    child = get_object_or_404(Child, slug=slug, user=request.user)

    form = Form.objects.get(slug=settings.PICKY_EATING_FORM_SLUG)

    incomplete_form_progress = ChildFormProgress.get_latest_incomplete(child, form)
    page_number = (
        incomplete_form_progress.get_current_page_number()
        if incomplete_form_progress
        else None
    )

    complete_form_progress = ChildFormProgress.get_latest_complete(child, form)

    return render(
        request,
        "bloom_student_interface/child_assessment.html",
        {
            "child": child,
            "form": form,
            "incomplete_form_progress": incomplete_form_progress,
            "complete_form_progress": complete_form_progress,
            "page_number": page_number,
        },
    )


@login_required
def child_assessment_start(request, child_slug, form_slug):
    """Start a new assessment form for a child."""
    child = get_object_or_404(Child, slug=child_slug, user=request.user)
    form = get_object_or_404(Form, slug=form_slug)

    # Check if there's an incomplete form progress for this specific child
    form_progress = ChildFormProgress.get_latest_incomplete(child, form)

    if not form_progress:
        # Create a new FormProgress for this child
        form_progress = FormProgress.objects.create(user=request.user, form=form)
        ChildFormProgress.objects.create(form_progress=form_progress, child=child)

    page_number = form_progress.get_current_page_number()

    # Redirect the user to form_fill_page
    return redirect(
        "bloom_student_interface:child_assessment_fill_page",
        child_slug=child.slug,
        form_slug=form.slug,
        page_number=page_number,
    )


@login_required
def child_assessment_fill_page(request, child_slug, form_slug, page_number):
    """Fill in a specific page of the assessment form."""
    child = get_object_or_404(Child, slug=child_slug, user=request.user)
    form = get_object_or_404(Form, slug=form_slug)
    all_pages = list(form.pages.all())
    total_pages = len(all_pages)
    form_page = all_pages[page_number - 1]

    form_progress = ChildFormProgress.get_latest_incomplete(child, form)

    questions = [
        child
        for child in form_page.children()
        if hasattr(child, "question")  # It's a FormQuestion
    ]

    # Determine the furthest page the user has progressed to
    furthest_page = form_progress.get_current_page_number()

    # Build list of all page objects with their URLs for navigation
    page_links = []
    for i in range(1, total_pages + 1):
        page_links.append(
            {
                "number": i,
                "title": all_pages[i - 1].title,
                "url": reverse(
                    "bloom_student_interface:child_assessment_fill_page",
                    kwargs={
                        "child_slug": child_slug,
                        "form_slug": form_slug,
                        "page_number": i,
                    },
                ),
                "is_current": i == page_number,
                "is_accessible": i
                <= furthest_page,  # Can access all pages up to furthest progress
            }
        )
    existing_answers = form_progress.existing_answers_dict(questions)

    previous_page_url = (
        reverse(
            "bloom_student_interface:child_assessment_fill_page",
            kwargs={
                "child_slug": child_slug,
                "form_slug": form_slug,
                "page_number": page_number - 1,
            },
        )
        if page_number > 1
        else None
    )

    next_page_url = (
        reverse(
            "bloom_student_interface:child_assessment_fill_page",
            kwargs={
                "child_slug": child_slug,
                "form_slug": form_slug,
                "page_number": page_number + 1,
            },
        )
        if page_number < total_pages
        else None
    )

    if request.method == "POST":
        # Process each question's answer
        form_progress.save_answers(questions, request.POST)

        if next_page_url:
            return redirect(next_page_url)

        # Mark form as completed and calculate scores
        form_progress.complete()

        make_activity_recommendations(child)

        return redirect(
            "bloom_student_interface:child_assessment_complete",
            child_slug=child_slug,
            form_slug=form_slug,
        )

    context = {
        "child": child,
        "form": form,
        "form_page": form_page,
        "form_progress": form_progress,
        "current_page_num": page_number,
        "total_pages": total_pages,
        "previous_page_url": previous_page_url,
        "has_next_page": next_page_url,
        "existing_answers": existing_answers,
        "page_links": page_links,
    }

    return render(
        request,
        "bloom_student_interface/child_assessment_fill_page.html",
        context,
    )


@login_required
def child_assessment_complete(request, child_slug, form_slug):
    """Show the completion page for a child's assessment."""
    child = get_object_or_404(Child, slug=child_slug, user=request.user)
    form = get_object_or_404(Form, slug=form_slug)

    # Get the most recent completed form progress for this child
    child_form_progress = (
        ChildFormProgress.objects.filter(
            child=child,
            form_progress__form=form,
            form_progress__completed_time__isnull=False,
        )
        .order_by("-form_progress__completed_time")
        .first()
    )

    form_progress = child_form_progress.form_progress if child_form_progress else None

    context = {
        "child": child,
        "form": form,
        "form_progress": form_progress,
        "show_scores": True,
        "scores": form_progress.scores if form_progress else None,
    }

    return render(
        request,
        "bloom_student_interface/child_assessment_complete.html",
        context,
    )


def get_activity_log_entries(child, day_range):
    # Get the last 7 days of activity logs for this child
    today = timezone.now().date()
    dates = [today - timedelta(days=i) for i in range(day_range)]
    min_date = min(dates)

    # Structure: activity_logs[date][activity_id] = done
    logs = ActivityLog.objects.filter(
        child=child, date__gte=min_date, date__lte=today
    ).select_related("activity")

    activity_logs = {}
    for date in dates:
        activity_logs[date] = {}

    for log in logs:
        if log.date not in activity_logs:
            activity_logs[log.date] = {}
        activity_logs[log.date][log.activity_id] = log

    return activity_logs


@login_required
def child_activities_configure(request, slug):
    """Activities page for a specific child."""

    child = get_object_or_404(Child, slug=slug, user=request.user)

    context = get_activities_context(child)

    return render(
        request, "bloom_student_interface/child_activities_configure.html", context
    )


@login_required
def child_activity(request, child_slug, activity_slug):
    """Detail page for a specific activity for a child."""
    child = get_object_or_404(Child, slug=child_slug, user=request.user)

    activity = get_object_or_404(Activity, slug=activity_slug)

    committed = CommittedActivity.objects.filter(
        child=child, activity=activity
    ).exists()

    return render(
        request,
        "bloom_student_interface/child_activity.html",
        {
            "child": child,
            "activity": activity,
            "committed": committed,
        },
    )


# @login_required
# def child_activity_commit(request, child_slug, activity_slug):
#     """Commit a child to an activity."""
#     if request.method != "POST":
#         return redirect(
#             "bloom_student_interface:child_activity",
#             child_slug=child_slug,
#             activity_slug=activity_slug,
#         )

#     child = get_object_or_404(Child, slug=child_slug, user=request.user)
#     activity = get_object_or_404(Activity, slug=activity_slug)

#     # Create the commitment if it doesn't already exist
#     CommittedActivity.objects.get_or_create(child=child, activity=activity)

#     # if there is an existing recommendation, delete it
#     # RecommendedActivity.objects.filter(child=child, activity=activity)

#     return redirect(
#         "bloom_student_interface:child_activity",
#         child_slug=child_slug,
#         activity_slug=activity_slug,
#     )


@login_required
def action_child_activity_toggle(request, child_slug, activity_slug, date):
    """Toggle activity log status for a child on a specific date."""
    child = get_object_or_404(Child, slug=child_slug, user=request.user)
    activity = get_object_or_404(Activity, slug=activity_slug)

    # Parse date string to date object

    date_obj = datetime.strptime(date, "%Y-%m-%d").date()

    # Get or create the activity log
    log, created = ActivityLog.objects.get_or_create(
        child=child, activity=activity, date=date_obj
    )

    log.notes = request.POST["notes"]

    if "good" in request.POST:
        log.done = True
        log.sentiment = "good"

    elif "neutral" in request.POST:
        log.done = True
        log.sentiment = "neutral"

    elif "bad" in request.POST:
        log.done = True
        log.sentiment = "bad"

    elif "didnt-do" in request.POST:
        log.done = False
        log.sentiment = None

    else:
        raise Exception(f"{request.POST}")

    log.save()

    context = {"log": log, "date": date, "child": child, "activity": activity}

    response_string = render_to_string(
        "bloom_student_interface/partials/activity_tracking.html#activity_radio",
        context,
        request=request,
    )

    if log.sentiment == "good":
        streak = get_activity_good_streak(child, activity)

        if streak >= settings.NUMBER_OF_GOOD_ACTIVITIES_BEFORE_LEVEL_UP:
            activity_options = adjust_activity_recommendations_positive(child, activity)
            # context["activity_options"] = activity_options
            level_up_modal = render_to_string(
                "bloom_student_interface/partials/activity_tracking.html#activity_level_up_modal",
                context,
                request=request,
            )
            response_string = response_string + level_up_modal
    elif log.sentiment == "bad":
        streak = get_activity_bad_streak(child, activity)
        if streak >= settings.NUMBER_OF_BAD_ACTIVITIES_BEFORE_LEVEL_DOWN:
            activity_options = adjust_activity_recommendations_negative(child, activity)
            # context["activity_options"] = activity_options
            level_down_modal = render_to_string(
                "bloom_student_interface/partials/activity_tracking.html#activity_level_down_modal",
                context,
                request=request,
            )
            response_string = response_string + level_down_modal

    return HttpResponse(response_string)

    # return render(
    #     request,
    #     "bloom_student_interface/partials/activity_tracking.html#activity_radio",
    #     context,
    # )


# @login_required
# def action_child_activity_stop(request, child_slug, activity_slug):
#     """Stop (decommit) a child's activity by setting stopped_at timestamp."""

#     # Return updated activities table
#     DAY_RANGE = 7
#     committed_activities = (
#         child.activities.filter(stopped_at__isnull=True)
#         .select_related("activity")
#         .all()
#     )
#     activity_logs = get_activity_log_entries(child=child, day_range=DAY_RANGE)

#     return render(
#         request,
#         "bloom_student_interface/partials/activity_tracking.html#current_activities_table",
#         {
#             "child": child,
#             "committed_activities": committed_activities,
#             "activity_logs": activity_logs,
#         },
#     )


def get_activities_context(child):
    DAY_RANGE = 7
    committed_activities = (
        child.activities.filter(stopped_at__isnull=True)
        .select_related("activity")
        .all()
    )
    activity_logs = get_activity_log_entries(child=child, day_range=DAY_RANGE)
    committed_activity_ids = committed_activities.values_list("activity_id", flat=True)
    recommended_activities = (
        child.recommended_activities.filter(active=True)
        .select_related("activity")
        .exclude(activity_id__in=committed_activity_ids)
        .order_by("activity__level")
    )

    recommended_activities_organised = {}
    for recommendation in recommended_activities:
        activity = recommendation.activity
        cat, sub_cat = (s.strip() for s in activity.category.split("|"))
        level = activity.level

        recommended_activities_organised[cat] = recommended_activities_organised.get(
            cat, {}
        )
        recommended_activities_organised[cat][sub_cat] = (
            recommended_activities_organised[cat].get(sub_cat, {})
        )
        recommended_activities_organised[cat][sub_cat][level] = (
            recommended_activities_organised[cat][sub_cat].get(level, [])
        )
        recommended_activities_organised[cat][sub_cat][level].append(activity)

    # Get set of recommended activity IDs (including those that are committed)
    recommended_activity_ids = set(
        child.recommended_activities.filter(active=True).values_list(
            "activity_id", flat=True
        )
    )

    # Get stopped activities (previously committed but now stopped)
    # Only get the latest stopped commitment for each activity
    stopped_activities = (
        child.activities.filter(stopped_at__isnull=False)
        .select_related("activity")
        .order_by("activity_id", "-stopped_at")
        .distinct("activity_id")
        .exclude(activity_id__in=committed_activity_ids)
    )

    return {
        "child": child,
        "recommended_activities": recommended_activities,
        "recommended_activities_organised": recommended_activities_organised,
        "committed_activities": committed_activities,
        "activity_logs": activity_logs,
        "recommended_activity_ids": recommended_activity_ids,
        "stopped_activities": stopped_activities,
    }


@login_required
def action_child_activity_start_stop(request, child_slug, activity_slug, action):
    """Start (commit to) a child's activity by creating a CommittedActivity."""
    if request.method != "POST":
        return redirect("bloom_student_interface:children")

    child = get_object_or_404(Child, slug=child_slug, user=request.user)
    activity = get_object_or_404(Activity, slug=activity_slug)

    if action == "start":
        # Create the commitment if it doesn't already exist (or reactivate stopped activity)
        committed_activity, created = CommittedActivity.objects.get_or_create(
            child=child, activity=activity, stopped_at__isnull=True
        )
    elif action == "stop":
        # Find the committed activity and set stopped_at
        committed_activity = get_object_or_404(
            CommittedActivity, child=child, activity=activity, stopped_at__isnull=True
        )
        committed_activity.stopped_at = timezone.now()
        committed_activity.save()
    else:
        raise Exception(f"unknown action: {action}")

    context = get_activities_context(child)

    return render(
        request,
        "bloom_student_interface/partials/activity_tracking.html#activity_start_stop_response",
        context,
    )


###########################
# New navigation

# children_view_names = [
#     "bloom_student_interface:children_activities"
#     "bloom_student_interface:children_assessment"
# ]


# def children_activities(request):
#     template_name = "bloom_student_interface/experiment/children/activities.html"
#     children = Child.objects.filter(user=request.user)
#     context = {"children": children}

#     if request.headers.get("Hx-Request"):
#         current_url = request.headers.get("Hx-Current-Url")
#         url_path = urlparse(current_url).path
#         current_view_name = resolve(url_path).view_name
#         if current_view_name in children_view_names:
#             return render(request, f"{template_name}#child_content")

#     return render(request, template_name, context)


# def children_assessment(request):
#     template_name = "bloom_student_interface/experiment/children/assessment.html"
#     children = Child.objects.filter(user=request.user)
#     context = {"children": children}

#     if request.headers.get("Hx-Request"):
#         current_url = request.headers.get("Hx-Current-Url")
#         url_path = urlparse(current_url).path
#         current_view_name = resolve(url_path).view_name
#         if current_view_name in children_view_names:
#             return render(request, f"{template_name}#child_content")

#     return render(request, template_name, context)


@login_required
def learn(request):
    recommended_courses = RecommendedCourse.objects.filter(
        user=request.user
    ).select_related("collection")

    # Get registered courses if user has a Student record
    try:
        student = Student.objects.get(user=request.user)
        registered_courses = student.get_course_registrations()
    except Student.DoesNotExist:
        registered_courses = []

    context = {
        "recommended_courses": recommended_courses,
        "registered_courses": registered_courses,
    }

    if request.headers.get("Hx-Request"):
        return render(request, "bloom_student_interface/learn.html#content", context)

    return render(request, "bloom_student_interface/learn.html", context)


@login_required
def children(request):
    children = Child.objects.filter(user=request.user).prefetch_related(
        "activities__activity"
    )

    # Get the picky eating form
    picky_eating_form = Form.objects.get(slug=settings.PICKY_EATING_FORM_SLUG)

    # Add assessment status to each child
    for child in children:
        child.has_incomplete_assessment = (
            ChildFormProgress.get_latest_incomplete(child, picky_eating_form)
            is not None
        )
        complete_form_progress = ChildFormProgress.get_latest_complete(
            child, picky_eating_form
        )
        # child.has_complete_assessment = complete_form_progress is not None
        # child.last_assessment_date = (
        #     complete_form_progress.completed_time if complete_form_progress else None
        # )
        child.complete_assessment = complete_form_progress

    context = {
        "children": children,
    }

    if request.headers.get("Hx-Request"):
        return render(
            request,
            "bloom_student_interface/children.html#content",
            context=context,
        )

    return render(request, "bloom_student_interface/children.html", context=context)


class ChildForm(forms.ModelForm):
    """Form for creating and editing children."""

    class Meta:
        model = Child
        fields = ["name", "date_of_birth", "gender"]
        widgets = {
            "name": forms.TextInput(attrs={"placeholder": "Enter child's name"}),
            "date_of_birth": forms.DateInput(
                attrs={"type": "date", "placeholder": "YYYY-MM-DD"}
            ),
            "gender": forms.Select(),
        }


@login_required
def create_child(request):
    """Create a new child for the current user."""
    if request.method == "POST":
        form = ChildForm(request.POST)
        if form.is_valid():
            child = form.save(commit=False)
            child.user = request.user
            child.save()

            return redirect("bloom_student_interface:children")
    else:
        form = ChildForm()

    return render(request, "partials/form.html", context={"form": form})


@login_required
def child_current_activities(request, slug):
    child = get_object_or_404(Child, slug=slug, user=request.user)
    context = get_activities_context(child)
    return render(
        request,
        "bloom_student_interface/partials/activity_tracking.html#current_activities_table",
        context,
    )
