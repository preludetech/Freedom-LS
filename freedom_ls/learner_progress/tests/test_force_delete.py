"""Force delete: what a plan collects, what blocks it, and the delete itself."""

from __future__ import annotations

from dataclasses import dataclass
from typing import cast

import pytest

from django.contrib import admin
from django.contrib.contenttypes.models import ContentType
from django.core.files.base import ContentFile
from django.db.models import Model
from django.db.models.signals import pre_delete
from django.http import HttpRequest
from django.test import RequestFactory

from freedom_ls.accounts import admin as accounts_admin
from freedom_ls.accounts.factories import LegalConsentFactory, UserFactory
from freedom_ls.accounts.models import LegalConsent, User
from freedom_ls.audit_log.models import AuditLogEntry
from freedom_ls.form_engine.factories import (
    FormProgressFactory,
    QuestionAnswerFactory,
    QuestionAnswerFileFactory,
)
from freedom_ls.form_engine.models import FormProgress, QuestionAnswerFile
from freedom_ls.learner_management.factories import (
    CohortFactory,
    CohortMembershipFactory,
    LearnerFactory,
)
from freedom_ls.learner_management.models import (
    CohortMembership,
    Learner,
    LearnerCourseRegistration,
)
from freedom_ls.learner_progress.factories import (
    CourseFormAttemptFactory,
    CourseProgressFactory,
    TopicProgressFactory,
)
from freedom_ls.learner_progress.force_delete import (
    ForceDeleteBlockedError,
    build_plan,
    force_delete_users,
    user_progress_roots,
)
from freedom_ls.learner_progress.models import (
    CourseFormAttempt,
    CourseProgress,
    TopicProgress,
)

pytestmark = pytest.mark.django_db


@pytest.fixture
def actor() -> User:
    user: User = UserFactory(superuser=True)
    return user


@pytest.fixture
def request_for(actor: User) -> HttpRequest:
    request = RequestFactory().post("/")
    request.user = actor
    return request


def _plan(user: User, request: HttpRequest):
    return build_plan(
        targets=[user], progress_roots=[], request=request, admin_site=admin.site
    )


def test_plan_counts_each_model_once(mock_site_context, request_for) -> None:
    user: User = UserFactory()
    LegalConsentFactory(user=user)
    LegalConsentFactory(user=user, document_type="privacy")

    plan = _plan(user, request_for)

    assert plan.counts()["users"] == 1
    assert plan.counts()["legal consents"] == 2


def test_plan_can_run_for_a_user_whose_rows_are_all_allowed(
    mock_site_context, request_for
) -> None:
    user: User = UserFactory()
    LegalConsentFactory(user=user)

    plan = _plan(user, request_for)

    assert plan.can_run is True
    assert plan.blocking_models == ()


def test_plan_names_a_model_whose_admin_refuses_delete_and_is_not_allowed(
    mock_site_context, request_for, monkeypatch
) -> None:
    user: User = UserFactory()
    LegalConsentFactory(user=user)
    monkeypatch.setattr(accounts_admin, "USER_ERASURE_CASCADE_MODELS", set())

    plan = _plan(user, request_for)

    assert plan.can_run is False
    assert plan.blocking_models == ("legal consent",)


def test_force_delete_removes_the_user_and_their_rows(
    mock_site_context, request_for, actor
) -> None:
    user: User = UserFactory()
    LegalConsentFactory(user=user)

    count = force_delete_users(
        [user],
        actor=actor,
        reason="Erasure requested",
        request=request_for,
        admin_site=admin.site,
    )

    assert count == 1
    assert not User._base_manager.filter(pk=user.pk).exists()
    assert not LegalConsent._base_manager.filter(user_id=user.pk).exists()


def test_force_delete_writes_one_entry_that_outlives_the_user(
    mock_site_context, request_for, actor
) -> None:
    user: User = UserFactory(first_name="Ada", last_name="Lovelace")
    user_pk = user.pk

    force_delete_users(
        [user],
        actor=actor,
        reason="Erasure requested",
        request=request_for,
        admin_site=admin.site,
    )

    entry = AuditLogEntry.unscoped.get()
    assert entry.action == "user.deleted"
    assert entry.actor == actor
    assert entry.target_label == "Ada Lovelace"
    assert entry.target_object_id == str(user_pk)
    assert entry.target_content_type == ContentType.objects.get_for_model(User)
    assert entry.organisation is None
    assert entry.reason == "Erasure requested"
    assert entry.details["counts"]["users"] == 1


def test_force_delete_of_a_blocked_user_raises_and_deletes_nothing(
    mock_site_context, request_for, actor, monkeypatch
) -> None:
    user: User = UserFactory()
    LegalConsentFactory(user=user)
    monkeypatch.setattr(accounts_admin, "USER_ERASURE_CASCADE_MODELS", set())

    with pytest.raises(ForceDeleteBlockedError) as blocked:
        force_delete_users(
            [user],
            actor=actor,
            reason="Erasure requested",
            request=request_for,
            admin_site=admin.site,
        )

    assert blocked.value.blocking_models == ("legal consent",)
    assert User._base_manager.filter(pk=user.pk).exists()
    assert not AuditLogEntry.unscoped.exists()


@dataclass
class LoadedUser:
    user: User
    learners: list[Learner]
    answer_file: QuestionAnswerFile
    standalone_form_progress: FormProgress
    profile_picture_name: str


@pytest.fixture
def loaded_user(mock_site_context) -> LoadedUser:
    """A user with a learner in each of two organisations, each holding a
    cohort membership, course progress and topic progress; the first learner
    also sat a form whose answer has a file. The user holds a form progress
    record no course points at, a legal consent and a profile picture."""
    user: User = UserFactory()
    learners = [LearnerFactory(user=user), LearnerFactory(user=user)]
    for learner in learners:
        CohortMembershipFactory(
            learner=learner, cohort=CohortFactory(organisation=learner.organisation)
        )
        TopicProgressFactory(course_progress=CourseProgressFactory(learner=learner))
    attempt = CourseFormAttemptFactory(
        course_progress=CourseProgress._base_manager.get(learner=learners[0])
    )
    answer_file = QuestionAnswerFileFactory(
        answer=QuestionAnswerFactory(form_progress=attempt.form_progress)
    )
    LegalConsentFactory(user=user)
    user.profile_picture.save("me.jpg", ContentFile(b"picture"), save=True)
    return LoadedUser(
        user=user,
        learners=learners,
        answer_file=answer_file,
        standalone_form_progress=FormProgressFactory(user=user),
        profile_picture_name=user.profile_picture.name,
    )


def _models_still_referencing(user_pk: int) -> list[str]:
    """Every model that still has a row pointing at the user."""
    offenders = []
    for relation in User._meta.related_objects:
        model = cast(type[Model], relation.related_model)
        if model._base_manager.filter(**{relation.field.name: user_pk}).exists():
            offenders.append(model._meta.label)
    return offenders


def _delete(loaded: LoadedUser, request: HttpRequest, actor: User) -> int:
    return force_delete_users(
        [loaded.user],
        actor=actor,
        reason="Erasure requested",
        request=request,
        admin_site=admin.site,
    )


def test_plan_counts_each_object_once_across_both_collections(
    loaded_user, request_for
) -> None:
    plan = build_plan(
        targets=[loaded_user.user],
        progress_roots=user_progress_roots([loaded_user.user]),
        request=request_for,
        admin_site=admin.site,
    )

    counts = plan.counts()
    assert counts[str(Learner._meta.verbose_name_plural)] == 2
    assert counts[str(CohortMembership._meta.verbose_name_plural)] == 2
    assert counts[str(CourseProgress._meta.verbose_name_plural)] == 2
    assert counts[str(TopicProgress._meta.verbose_name_plural)] == 2
    assert counts[str(CourseFormAttempt._meta.verbose_name_plural)] == 1
    assert counts[str(FormProgress._meta.verbose_name_plural)] == 2
    assert counts[str(QuestionAnswerFile._meta.verbose_name_plural)] == 1
    assert plan.can_run is True


def test_a_protected_row_outside_the_progress_collection_blocks(
    loaded_user, request_for
) -> None:
    plan = build_plan(
        targets=[loaded_user.user],
        progress_roots=[],
        request=request_for,
        admin_site=admin.site,
    )

    assert plan.can_run is False
    assert plan.blocking_models == (str(CourseProgress._meta.verbose_name),)


def test_force_delete_leaves_no_row_pointing_at_the_user(
    loaded_user, request_for, actor
) -> None:
    user_pk = loaded_user.user.pk

    _delete(loaded_user, request_for, actor)

    assert _models_still_referencing(user_pk) == []
    assert not Learner._base_manager.filter(user_id=user_pk).exists()
    assert not LearnerCourseRegistration._base_manager.filter(
        learner__in=loaded_user.learners
    ).exists()
    assert not FormProgress._base_manager.filter(
        pk=loaded_user.standalone_form_progress.pk
    ).exists()


def test_force_delete_removes_the_answer_file_and_profile_picture_on_commit(
    loaded_user, request_for, actor, django_capture_on_commit_callbacks
) -> None:
    answer_storage = loaded_user.answer_file.file.storage
    answer_name = loaded_user.answer_file.file.name
    picture_storage = loaded_user.user.profile_picture.storage

    with django_capture_on_commit_callbacks(execute=True):
        _delete(loaded_user, request_for, actor)

    assert answer_storage.exists(answer_name) is False
    assert picture_storage.exists(loaded_user.profile_picture_name) is False


def test_force_delete_writes_a_user_entry_and_a_learner_entry_per_organisation(
    loaded_user, request_for, actor
) -> None:
    _delete(loaded_user, request_for, actor)

    user_entry = AuditLogEntry.unscoped.get(action="user.deleted")
    learner_entries = AuditLogEntry.unscoped.filter(action="learner.removed")
    assert user_entry.organisation is None
    assert user_entry.reason == "Erasure requested"
    assert user_entry.details["organisations"] == sorted(
        learner.organisation.name for learner in loaded_user.learners
    )
    assert {e.organisation for e in learner_entries} == {
        learner.organisation for learner in loaded_user.learners
    }
    assert {e.reason for e in learner_entries} == {"Erasure requested"}
    assert all(e.details["counts"]["learners"] == 1 for e in learner_entries)
    assert AuditLogEntry.unscoped.count() == 3


class _SecondDeleteFailedError(Exception):
    pass


def test_a_failure_part_way_rolls_back_every_row_and_entry(
    mock_site_context, request_for, actor
) -> None:
    first: User = UserFactory()
    second: User = UserFactory()
    LegalConsentFactory(user=first)
    LearnerFactory(user=first)

    def fail_for_second(sender: type[User], instance: User, **kwargs: object) -> None:
        if instance.pk == second.pk:
            raise _SecondDeleteFailedError

    pre_delete.connect(fail_for_second, sender=User, dispatch_uid="fail_for_second")
    try:
        with pytest.raises(_SecondDeleteFailedError):
            force_delete_users(
                [first, second],
                actor=actor,
                reason="Erasure requested",
                request=request_for,
                admin_site=admin.site,
            )
    finally:
        pre_delete.disconnect(sender=User, dispatch_uid="fail_for_second")

    assert User._base_manager.filter(pk__in=[first.pk, second.pk]).count() == 2
    assert LegalConsent._base_manager.filter(user=first).exists()
    assert Learner._base_manager.filter(user=first).exists()
    assert not AuditLogEntry.unscoped.exists()
