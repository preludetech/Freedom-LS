"""Tests for students_list view."""

import pytest
from django.test import Client
from django.urls import reverse
from guardian.shortcuts import assign_perm

from freedom_ls.student_management.models import (
    Student,
    Cohort,
    CohortMembership,
    StudentCourseRegistration,
    CohortCourseRegistration
)
from freedom_ls.content_engine.models import Course


@pytest.mark.django_db
def test_user_with_no_permissions_sees_no_students(mock_site_context, user):
    """User without view permissions sees no students."""
    # Create students but don't assign permissions
    user1 = user.__class__.objects.create_user(
        email="student1@example.com",
        password="testpass123"
    )
    user1.first_name = "Alice"
    user1.last_name = "Johnson"
    user1.save()

    user2 = user.__class__.objects.create_user(
        email="student2@example.com",
        password="testpass123"
    )
    user2.first_name = "Bob"
    user2.last_name = "Smith"
    user2.save()

    Student.objects.create(user=user1)
    Student.objects.create(user=user2)

    # Create client and login
    client = Client()
    client.force_login(user)

    # Call view
    url = reverse("educator_interface:students_list")
    response = client.get(url)

    # Check response
    assert response.status_code == 200
    students_list_result = list(response.context["students"])
    assert len(students_list_result) == 0


@pytest.mark.django_db
def test_user_sees_students_with_direct_view_permission(mock_site_context, user):
    """User with direct view permissions sees only assigned students."""
    # Create students
    user1 = user.__class__.objects.create_user(
        email="student1@example.com",
        password="testpass123"
    )
    user1.first_name = "Alice"
    user1.last_name = "Johnson"
    user1.save()

    user2 = user.__class__.objects.create_user(
        email="student2@example.com",
        password="testpass123"
    )
    user2.first_name = "Bob"
    user2.last_name = "Smith"
    user2.save()

    user3 = user.__class__.objects.create_user(
        email="student3@example.com",
        password="testpass123"
    )
    user3.first_name = "Charlie"
    user3.last_name = "Brown"
    user3.save()

    student1 = Student.objects.create(user=user1)
    student2 = Student.objects.create(user=user2)
    student3 = Student.objects.create(user=user3)

    # Assign direct view permissions only for student1 and student3
    assign_perm("view_student", user, student1)
    assign_perm("view_student", user, student3)

    # Create client and login
    client = Client()
    client.force_login(user)

    # Call view
    url = reverse("educator_interface:students_list")
    response = client.get(url)

    # Check response
    assert response.status_code == 200
    students = list(response.context["students"])
    assert students == [student1, student3]


@pytest.mark.django_db
def test_user_sees_students_through_cohort_permissions(mock_site_context, user):
    """User sees students from cohorts they have view permission for."""
    # Create students
    user1 = user.__class__.objects.create_user(
        email="student1@example.com",
        password="testpass123"
    )
    user1.first_name = "Alice"
    user1.last_name = "Johnson"
    user1.save()

    user2 = user.__class__.objects.create_user(
        email="student2@example.com",
        password="testpass123"
    )
    user2.first_name = "Bob"
    user2.last_name = "Smith"
    user2.save()

    user3 = user.__class__.objects.create_user(
        email="student3@example.com",
        password="testpass123"
    )
    user3.first_name = "Charlie"
    user3.last_name = "Brown"
    user3.save()

    student1 = Student.objects.create(user=user1)
    student2 = Student.objects.create(user=user2)
    student3 = Student.objects.create(user=user3)

    # Create cohorts
    cohort_a = Cohort.objects.create(name="Cohort A")
    cohort_b = Cohort.objects.create(name="Cohort B")

    # Add students to cohorts
    CohortMembership.objects.create(student=student1, cohort=cohort_a)
    CohortMembership.objects.create(student=student2, cohort=cohort_a)
    CohortMembership.objects.create(student=student3, cohort=cohort_b)

    # Assign cohort view permission only for cohort_a
    assign_perm("view_cohort", user, cohort_a)

    # Create client and login
    client = Client()
    client.force_login(user)

    # Call view
    url = reverse("educator_interface:students_list")
    response = client.get(url)

    # Check response - should see student1 and student2 from cohort_a, but not student3
    assert response.status_code == 200
    students = list(response.context["students"])
    assert set(students) == {student1, student2}


@pytest.mark.django_db
def test_user_sees_combined_students_from_both_access_methods(mock_site_context, user):
    """User sees students from both direct permissions and cohort permissions, without duplicates."""
    # Create students
    user1 = user.__class__.objects.create_user(
        email="student1@example.com",
        password="testpass123"
    )
    user1.first_name = "Alice"
    user1.last_name = "Johnson"
    user1.save()

    user2 = user.__class__.objects.create_user(
        email="student2@example.com",
        password="testpass123"
    )
    user2.first_name = "Bob"
    user2.last_name = "Smith"
    user2.save()

    user3 = user.__class__.objects.create_user(
        email="student3@example.com",
        password="testpass123"
    )
    user3.first_name = "Charlie"
    user3.last_name = "Brown"
    user3.save()

    student1 = Student.objects.create(user=user1)
    student2 = Student.objects.create(user=user2)
    student3 = Student.objects.create(user=user3)

    # Create cohort
    cohort = Cohort.objects.create(name="Cohort A")

    # Add student1 and student2 to cohort
    CohortMembership.objects.create(student=student1, cohort=cohort)
    CohortMembership.objects.create(student=student2, cohort=cohort)

    # Give cohort view permission (gives access to student1 and student2)
    assign_perm("view_cohort", user, cohort)

    # Also give direct view permission to student1 (duplicate access) and student3
    assign_perm("view_student", user, student1)
    assign_perm("view_student", user, student3)

    # Create client and login
    client = Client()
    client.force_login(user)

    # Call view
    url = reverse("educator_interface:students_list")
    response = client.get(url)

    # Check response - should see all 3 students without duplicates
    # student1 via both direct and cohort (no duplicate)
    # student2 via cohort
    # student3 via direct
    assert response.status_code == 200
    students = list(response.context["students"])
    assert set(students) == {student1, student2, student3}


@pytest.mark.django_db
def test_view_displays_correct_student_information(mock_site_context, user):
    """Verify that the students list displays name, email, cohorts, and courses correctly."""
    # Create student
    user1 = user.__class__.objects.create_user(
        email="alice@example.com",
        password="testpass123"
    )
    user1.first_name = "Alice"
    user1.last_name = "Johnson"
    user1.save()

    student = Student.objects.create(user=user1)

    # Create cohorts and add student
    cohort1 = Cohort.objects.create(name="Math Cohort 2024")
    cohort2 = Cohort.objects.create(name="Science Cohort 2024")
    CohortMembership.objects.create(student=student, cohort=cohort1)
    CohortMembership.objects.create(student=student, cohort=cohort2)

    # Create courses
    course1 = Course.objects.create(
        title="Introduction to Python",
        slug="intro-python",
        file_path="courses/python-intro.md"
    )
    course2 = Course.objects.create(
        title="Advanced Mathematics",
        slug="advanced-math",
        file_path="courses/advanced-math.md"
    )

    # Register student for course1 directly
    StudentCourseRegistration.objects.create(student=student, collection=course1)

    # Register cohort1 for course2 (student gets access through cohort)
    CohortCourseRegistration.objects.create(cohort=cohort1, collection=course2)

    # Give user permission to view the student
    assign_perm("view_student", user, student)

    # Create client and login
    client = Client()
    client.force_login(user)

    # Call view
    url = reverse("educator_interface:students_list")
    response = client.get(url)

    # Check response
    assert response.status_code == 200
    content = response.content.decode()

    # Verify student information is in the response
    assert "Alice Johnson" in content
    assert "alice@example.com" in content
    assert "Math Cohort 2024" in content
    assert "Science Cohort 2024" in content
    assert "Introduction to Python" in content
    assert "Advanced Mathematics" in content
