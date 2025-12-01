from django.urls import path
from . import views

app_name = "bloom_student_interface"

urlpatterns = [
    path("", views.home, name="home"),
    path("child/create/", views.ChildCreateView.as_view(), name="child_create"),
    path("child/<uuid:pk>/edit/", views.ChildUpdateView.as_view(), name="child_edit"),
    path("child/<uuid:pk>/delete/", views.child_delete, name="child_delete"),
    path(
        "child/<slug:slug>/activities/child_activities_configure",
        views.child_activities_configure,
        name="child_activities_configure",
    ),
    path(
        "child/<slug:slug>/activities/current",
        views.child_current_activities,
        name="child_current_activities",
    ),
    path(
        "child/<slug:child_slug>/activity/<slug:activity_slug>/",
        views.child_activity,
        name="child_activity",
    ),
    path(
        "child/<slug:child_slug>/activity/<slug:activity_slug>/commit/",
        views.child_activity_commit,
        name="child_activity_commit",
    ),
    path(
        "child/<slug:child_slug>/activity/<slug:activity_slug>/toggle/<str:date>/",
        views.action_child_activity_toggle,
        name="action_child_activity_toggle",
    ),
    ###### Experimenting with better layout
    # path("children/activities", views.children_activities, name="children_activities"),
    # path("children/assessment", views.children_assessment, name="children_assessment"),
    path("learn", views.learn, name="learn"),
    path("children", views.children, name="children"),
    path("children/create/", views.create_child, name="children_create"),
    ## Assessment
    path(
        "child/<slug:slug>/assessment/", views.child_assessment, name="child_assessment"
    ),
    path(
        "child/<slug:child_slug>/assessment/<slug:form_slug>/start/",
        views.child_assessment_start,
        name="child_assessment_start",
    ),
    path(
        "child/<slug:child_slug>/assessment/<slug:form_slug>/page/<int:page_number>/",
        views.child_assessment_fill_page,
        name="child_assessment_fill_page",
    ),
    path(
        "child/<slug:child_slug>/assessment/<slug:form_slug>/complete/",
        views.child_assessment_complete,
        name="child_assessment_complete",
    ),
]
