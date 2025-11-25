from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse_lazy
from django.views.generic import CreateView, UpdateView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.decorators import login_required
from django.urls import reverse
from django.utils import timezone
from django.db.models import Prefetch

from content_engine.models import Form, Activity
from student_progress.models import FormProgress
from student_management.models import Student
from .models import (
    Child,
    ChildFormProgress,
    RecommendedCourse,
    CommittedActivity,
    ActivityLog,
)

from .recommender import make_recommendations


def home(request):
    """Home page with list of available courses."""
    children = []
    recommended_courses = []
    registered_courses = []
    activity_logs_today = {}

    if request.user.is_authenticated:
        children = Child.objects.filter(user=request.user).prefetch_related(
            "activities__activity"
        )
        recommended_courses = RecommendedCourse.objects.filter(
            user=request.user
        ).select_related("collection")

        # Get registered courses if user has a Student record
        try:
            student = Student.objects.get(user=request.user)
            registered_courses = student.get_course_registrations()
        except Student.DoesNotExist:
            pass

        # Get today's activity logs for all children
        today = timezone.now().date()
        logs = ActivityLog.objects.filter(
            child__user=request.user, date=today
        ).select_related("child", "activity")

        activity_logs_today = {}
        for log in logs:
            child_id = log.child_id
            activity_id = log.activity_id
            activity_logs_today[child_id] = activity_logs_today.get(child_id, {})
            activity_logs_today[child_id][activity_id] = log.done

    return render(
        request,
        "student_interface/home.html",
        {
            "children": children,
            "recommended_courses": recommended_courses,
            "registered_courses": registered_courses,
            "activity_logs_today": activity_logs_today,
        },
    )


class ChildCreateView(LoginRequiredMixin, CreateView):
    """Create a new child."""

    model = Child
    template_name = "bloom_student_interface/child_form.html"
    fields = ["name", "age"]
    success_url = reverse_lazy("bloom_student_interface:home")

    def form_valid(self, form):
        form.instance.user = self.request.user
        return super().form_valid(form)


class ChildUpdateView(LoginRequiredMixin, UpdateView):
    """Edit an existing child."""

    model = Child
    template_name = "bloom_student_interface/child_form.html"
    fields = ["name", "age"]
    success_url = reverse_lazy("bloom_student_interface:home")

    def get_queryset(self):
        return Child.objects.filter(user=self.request.user)


@login_required
def child_delete(request, pk):
    """Delete a child."""
    child = get_object_or_404(Child, pk=pk, user=request.user)

    if request.method == "POST":
        child.delete()
        return redirect("bloom_student_interface:home")

    return redirect("bloom_student_interface:home")


@login_required
def child_assessment(request, slug):
    """Picky eating assessment for a specific child."""
    child = get_object_or_404(Child, slug=slug, user=request.user)
    FORM_SLUG = "picky-eating"

    form = Form.objects.get(slug=FORM_SLUG)

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

        make_recommendations(child)

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


@login_required
def child_activities(request, slug):
    """Activities page for a specific child."""
    child = get_object_or_404(Child, slug=slug, user=request.user)

    recommended_activities = child.recommended_activities.select_related(
        "activity"
    ).all()

    committed_activities = child.activities.select_related("activity").all()

    return render(
        request,
        "bloom_student_interface/child_activities.html",
        {
            "child": child,
            "recommended_activities": recommended_activities,
            "committed_activities": committed_activities,
        },
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


@login_required
def child_activity_commit(request, child_slug, activity_slug):
    """Commit a child to an activity."""
    if request.method != "POST":
        return redirect(
            "bloom_student_interface:child_activity",
            child_slug=child_slug,
            activity_slug=activity_slug,
        )

    child = get_object_or_404(Child, slug=child_slug, user=request.user)
    activity = get_object_or_404(Activity, slug=activity_slug)

    # Create the commitment if it doesn't already exist
    CommittedActivity.objects.get_or_create(child=child, activity=activity)

    return redirect(
        "bloom_student_interface:child_activity",
        child_slug=child_slug,
        activity_slug=activity_slug,
    )
