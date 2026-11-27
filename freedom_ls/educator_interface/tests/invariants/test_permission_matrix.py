"""The permission matrix: can() answers exactly what the permission table allows.

Most tests here are walks. A walk builds the world once, checks every cell it
covers against that world, and reports every mismatch in one failure.

MATRIX is a hand-written transcription of that table, reviewed against it and
never parsed from it. MATRIX and CAPABILITY_SCOPE_KINDS cover every row,
including download_cohort_report, which the cohort Report tab's generate
action asks about.

The world: site A has organisation O1 (cohorts C1 granted and C2, learners L1
in C1 and L2 in C2) and O2 (C3, L3). Site B has O3 (C4, L4). Grants:
site_admin on site A, organisation_admin, organisation_staff_viewer and
organisation_staff_roles_viewer and question_bank_viewer on O1, cohort_admin and cohort_viewer on C1.
"""

from __future__ import annotations

import operator
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from functools import partial
from typing import NamedTuple, cast

import pytest
from guardian.shortcuts import get_perms
from panel_framework.context import PanelContext

from django.contrib.auth.models import AbstractBaseUser
from django.contrib.sites.models import Site
from django.db.models import Model
from django.http import Http404
from django.test import RequestFactory

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.accounts.models import User
from freedom_ls.content_engine.factories import CourseFactory
from freedom_ls.content_engine.models import Course
from freedom_ls.educator_interface.learner_import import check_import_gate
from freedom_ls.educator_interface.panels.common.request import (
    OrganisationScopedRequest,
)
from freedom_ls.educator_interface.panels.course.actions import (
    DeactivateCourseCohortRegistrationAction,
    DeactivateCourseLearnerRegistrationAction,
    ReactivateCourseLearnerRegistrationAction,
    RegisterCohortOnCourseAction,
    RegisterLearnerOnCourseAction,
)
from freedom_ls.educator_interface.panels.course.config import CourseConfig
from freedom_ls.educator_interface.tests.interface_walk import (
    WalkedAction,
    WalkedBulkAction,
    walk_interface,
)
from freedom_ls.learner_management.capabilities import can
from freedom_ls.learner_management.factories import (
    CohortCourseRegistrationFactory,
    CohortFactory,
    CohortMembershipFactory,
    LearnerCourseRegistrationFactory,
    LearnerFactory,
)
from freedom_ls.learner_management.models import (
    Cohort,
    CohortCourseRegistration,
    Learner,
    LearnerCourseRegistration,
    StaffMember,
)
from freedom_ls.learner_management.queries import (
    cohorts_visible_to,
    learners_visible_to,
)
from freedom_ls.organisations.factories import OrganisationFactory
from freedom_ls.organisations.models import Organisation
from freedom_ls.role_based_permissions.models import ObjectRoleAssignment
from freedom_ls.role_based_permissions.roles import BASE_ROLES
from freedom_ls.role_based_permissions.utils import assign_object_role, assign_site_role
from freedom_ls.tests.factories import SiteFactory

#: Roles whose grants are gated on an active StaffMember. site_admin's
#: grant is a SiteRoleAssignment, which _site_grants never gates.
GATED_ROLES = (
    "organisation_admin",
    "organisation_staff_viewer",
    "organisation_staff_roles_viewer",
    "question_bank_viewer",
    "cohort_admin",
    "cohort_viewer",
)

ROLES = (
    "site_admin",
    "organisation_admin",
    "organisation_staff_viewer",
    "organisation_staff_roles_viewer",
    "question_bank_viewer",
    "cohort_admin",
    "cohort_viewer",
)

OWN = "own"
OTHER_COHORT = "other_cohort"
OTHER_ORGANISATION = "other_organisation"
OTHER_SITE = "other_site"

#: Which relations make sense for a scope object of this kind -- an
#: organisation has no "other cohort" position to test, and a site has
#: neither an "other cohort" nor an "other organisation" position.
RELATIONS_FOR_KIND: dict[str, tuple[str, ...]] = {
    "site": (OWN, OTHER_SITE),
    "organisation": (OWN, OTHER_ORGANISATION, OTHER_SITE),
    "cohort": (OWN, OTHER_COHORT, OTHER_ORGANISATION, OTHER_SITE),
    "learner": (OWN, OTHER_COHORT, OTHER_ORGANISATION, OTHER_SITE),
}

VIEW_ORGANISATION = "freedom_ls_organisations.view_organisation"
VIEW_AUDITLOGENTRY = "freedom_ls_audit_log.view_auditlogentry"
VIEW_COHORT = "freedom_ls_learner_management.view_cohort"
VIEW_LEARNER = "freedom_ls_learner_management.view_learner"
VIEW_CONVERSATION = "freedom_ls_comms.view_conversation"
ADD_COHORT = "freedom_ls_learner_management.add_cohort"
CHANGE_COHORT = "freedom_ls_learner_management.change_cohort"
DELETE_COHORT = "freedom_ls_learner_management.delete_cohort"
ADD_LEARNER = "freedom_ls_learner_management.add_learner"
CHANGE_LEARNER = "freedom_ls_learner_management.change_learner"
CHANGE_USER = "freedom_ls_accounts.change_user"
ADD_COHORTMEMBERSHIP = "freedom_ls_learner_management.add_cohortmembership"
DELETE_COHORTMEMBERSHIP = "freedom_ls_learner_management.delete_cohortmembership"
ADD_COHORTCOURSEREGISTRATION = (
    "freedom_ls_learner_management.add_cohortcourseregistration"
)
CHANGE_COHORTCOURSEREGISTRATION = (
    "freedom_ls_learner_management.change_cohortcourseregistration"
)
ADD_LEARNERCOURSEREGISTRATION = (
    "freedom_ls_learner_management.add_learnercourseregistration"
)
CHANGE_LEARNERCOURSEREGISTRATION = (
    "freedom_ls_learner_management.change_learnercourseregistration"
)
BULK_MANAGE_LEARNERS = "freedom_ls_learner_management.bulk_manage_learners"
ASSIGN_COHORT_ADMIN = "freedom_ls_role_based_permissions.assign_cohort_admin"
ASSIGN_COHORT_VIEWER = "freedom_ls_role_based_permissions.assign_cohort_viewer"
VIEW_STAFFMEMBER = "freedom_ls_learner_management.view_staffmember"
ADD_STAFFMEMBER = "freedom_ls_learner_management.add_staffmember"
CHANGE_STAFFMEMBER = "freedom_ls_learner_management.change_staffmember"
ASSIGN_ORGANISATION_ADMIN = (
    "freedom_ls_role_based_permissions.assign_organisation_admin"
)
ASSIGN_SITE_ADMIN = "freedom_ls_role_based_permissions.assign_site_admin"
DOWNLOAD_COHORT_REPORT = "freedom_ls_learner_management.download_cohort_report"
VIEW_ORGANISATION_STAFF = "freedom_ls_learner_management.view_organisation_staff"
VIEW_ORGANISATION_STAFF_ROLES = (
    "freedom_ls_learner_management.view_organisation_staff_roles"
)
ASSIGN_ORGANISATION_STAFF_VIEWER = (
    "freedom_ls_role_based_permissions.assign_organisation_staff_viewer"
)
ASSIGN_ORGANISATION_STAFF_ROLES_VIEWER = (
    "freedom_ls_role_based_permissions.assign_organisation_staff_roles_viewer"
)
VIEW_COURSE_QUESTIONS = "freedom_ls_content_engine.view_course_questions"
ASSIGN_QUESTION_BANK_VIEWER = (
    "freedom_ls_role_based_permissions.assign_question_bank_viewer"
)

# capability -> role -> the (scope kind, relation) pairs where can() is True.
MATRIX: dict[str, dict[str, set[tuple[str, str]]]] = {
    VIEW_ORGANISATION: {
        "site_admin": {("organisation", OWN), ("organisation", OTHER_ORGANISATION)},
        "organisation_admin": {("organisation", OWN)},
        "organisation_staff_viewer": set(),
        "organisation_staff_roles_viewer": set(),
        "question_bank_viewer": set(),
        "cohort_admin": set(),
        "cohort_viewer": set(),
    },
    VIEW_COHORT: {
        "site_admin": {
            ("cohort", OWN),
            ("cohort", OTHER_COHORT),
            ("cohort", OTHER_ORGANISATION),
        },
        "organisation_admin": {("cohort", OWN), ("cohort", OTHER_COHORT)},
        "organisation_staff_viewer": set(),
        "organisation_staff_roles_viewer": set(),
        "question_bank_viewer": set(),
        "cohort_admin": {("cohort", OWN)},
        "cohort_viewer": {("cohort", OWN)},
    },
    VIEW_LEARNER: {
        "site_admin": {
            ("learner", OWN),
            ("learner", OTHER_COHORT),
            ("learner", OTHER_ORGANISATION),
        },
        "organisation_admin": {("learner", OWN), ("learner", OTHER_COHORT)},
        "organisation_staff_viewer": set(),
        "organisation_staff_roles_viewer": set(),
        "question_bank_viewer": set(),
        "cohort_admin": {("learner", OWN)},
        "cohort_viewer": {("learner", OWN)},
    },
    VIEW_CONVERSATION: {
        "site_admin": {
            ("learner", OWN),
            ("learner", OTHER_COHORT),
            ("learner", OTHER_ORGANISATION),
        },
        "organisation_admin": {("learner", OWN), ("learner", OTHER_COHORT)},
        "organisation_staff_viewer": set(),
        "organisation_staff_roles_viewer": set(),
        "question_bank_viewer": set(),
        "cohort_admin": set(),
        "cohort_viewer": set(),
    },
    VIEW_AUDITLOGENTRY: {
        "site_admin": {
            ("organisation", OWN),
            ("organisation", OTHER_ORGANISATION),
            ("cohort", OWN),
            ("cohort", OTHER_COHORT),
            ("cohort", OTHER_ORGANISATION),
            ("learner", OWN),
            ("learner", OTHER_COHORT),
            ("learner", OTHER_ORGANISATION),
        },
        "organisation_admin": {
            ("organisation", OWN),
            ("cohort", OWN),
            ("cohort", OTHER_COHORT),
            ("learner", OWN),
            ("learner", OTHER_COHORT),
        },
        "organisation_staff_viewer": set(),
        "organisation_staff_roles_viewer": set(),
        "question_bank_viewer": set(),
        # A cohort grant covers the cohort and, as every cohort grant does,
        # the learners in it. The learner page's History panel asks for the
        # organisation instead, so a cohort admin opens cohort History only.
        "cohort_admin": {("cohort", OWN), ("learner", OWN)},
        "cohort_viewer": set(),
    },
    ADD_COHORT: {
        "site_admin": {("organisation", OWN), ("organisation", OTHER_ORGANISATION)},
        "organisation_admin": {("organisation", OWN)},
        "organisation_staff_viewer": set(),
        "organisation_staff_roles_viewer": set(),
        "question_bank_viewer": set(),
        "cohort_admin": set(),
        "cohort_viewer": set(),
    },
    CHANGE_COHORT: {
        "site_admin": {
            ("cohort", OWN),
            ("cohort", OTHER_COHORT),
            ("cohort", OTHER_ORGANISATION),
        },
        "organisation_admin": {("cohort", OWN), ("cohort", OTHER_COHORT)},
        "organisation_staff_viewer": set(),
        "organisation_staff_roles_viewer": set(),
        "question_bank_viewer": set(),
        "cohort_admin": set(),
        "cohort_viewer": set(),
    },
    DELETE_COHORT: {
        "site_admin": {
            ("cohort", OWN),
            ("cohort", OTHER_COHORT),
            ("cohort", OTHER_ORGANISATION),
        },
        "organisation_admin": {("cohort", OWN), ("cohort", OTHER_COHORT)},
        "organisation_staff_viewer": set(),
        "organisation_staff_roles_viewer": set(),
        "question_bank_viewer": set(),
        "cohort_admin": set(),
        "cohort_viewer": set(),
    },
    ADD_LEARNER: {
        "site_admin": {("organisation", OWN), ("organisation", OTHER_ORGANISATION)},
        "organisation_admin": {("organisation", OWN)},
        "organisation_staff_viewer": set(),
        "organisation_staff_roles_viewer": set(),
        "question_bank_viewer": set(),
        "cohort_admin": set(),
        "cohort_viewer": set(),
    },
    CHANGE_LEARNER: {
        "site_admin": {
            ("learner", OWN),
            ("learner", OTHER_COHORT),
            ("learner", OTHER_ORGANISATION),
        },
        "organisation_admin": {("learner", OWN), ("learner", OTHER_COHORT)},
        "organisation_staff_viewer": set(),
        "organisation_staff_roles_viewer": set(),
        "question_bank_viewer": set(),
        "cohort_admin": set(),
        "cohort_viewer": set(),
    },
    CHANGE_USER: {
        "site_admin": {
            ("learner", OWN),
            ("learner", OTHER_COHORT),
            ("learner", OTHER_ORGANISATION),
        },
        "organisation_admin": set(),
        "organisation_staff_viewer": set(),
        "organisation_staff_roles_viewer": set(),
        "question_bank_viewer": set(),
        "cohort_admin": set(),
        "cohort_viewer": set(),
    },
    ADD_COHORTMEMBERSHIP: {
        "site_admin": {
            ("cohort", OWN),
            ("cohort", OTHER_COHORT),
            ("cohort", OTHER_ORGANISATION),
        },
        "organisation_admin": {("cohort", OWN), ("cohort", OTHER_COHORT)},
        "organisation_staff_viewer": set(),
        "organisation_staff_roles_viewer": set(),
        "question_bank_viewer": set(),
        "cohort_admin": {("cohort", OWN)},
        "cohort_viewer": set(),
    },
    DELETE_COHORTMEMBERSHIP: {
        "site_admin": {
            ("cohort", OWN),
            ("cohort", OTHER_COHORT),
            ("cohort", OTHER_ORGANISATION),
        },
        "organisation_admin": {("cohort", OWN), ("cohort", OTHER_COHORT)},
        "organisation_staff_viewer": set(),
        "organisation_staff_roles_viewer": set(),
        "question_bank_viewer": set(),
        "cohort_admin": {("cohort", OWN)},
        "cohort_viewer": set(),
    },
    ADD_COHORTCOURSEREGISTRATION: {
        "site_admin": {
            ("cohort", OWN),
            ("cohort", OTHER_COHORT),
            ("cohort", OTHER_ORGANISATION),
        },
        "organisation_admin": {("cohort", OWN), ("cohort", OTHER_COHORT)},
        "organisation_staff_viewer": set(),
        "organisation_staff_roles_viewer": set(),
        "question_bank_viewer": set(),
        "cohort_admin": {("cohort", OWN)},
        "cohort_viewer": set(),
    },
    CHANGE_COHORTCOURSEREGISTRATION: {
        "site_admin": {
            ("cohort", OWN),
            ("cohort", OTHER_COHORT),
            ("cohort", OTHER_ORGANISATION),
        },
        "organisation_admin": {("cohort", OWN), ("cohort", OTHER_COHORT)},
        "organisation_staff_viewer": set(),
        "organisation_staff_roles_viewer": set(),
        "question_bank_viewer": set(),
        "cohort_admin": {("cohort", OWN)},
        "cohort_viewer": set(),
    },
    ADD_LEARNERCOURSEREGISTRATION: {
        "site_admin": {
            ("learner", OWN),
            ("learner", OTHER_COHORT),
            ("learner", OTHER_ORGANISATION),
        },
        "organisation_admin": {("learner", OWN), ("learner", OTHER_COHORT)},
        "organisation_staff_viewer": set(),
        "organisation_staff_roles_viewer": set(),
        "question_bank_viewer": set(),
        "cohort_admin": {("learner", OWN)},
        "cohort_viewer": set(),
    },
    CHANGE_LEARNERCOURSEREGISTRATION: {
        "site_admin": {
            ("learner", OWN),
            ("learner", OTHER_COHORT),
            ("learner", OTHER_ORGANISATION),
        },
        "organisation_admin": {("learner", OWN), ("learner", OTHER_COHORT)},
        "organisation_staff_viewer": set(),
        "organisation_staff_roles_viewer": set(),
        "question_bank_viewer": set(),
        "cohort_admin": {("learner", OWN)},
        "cohort_viewer": set(),
    },
    BULK_MANAGE_LEARNERS: {
        "site_admin": {("organisation", OWN), ("organisation", OTHER_ORGANISATION)},
        "organisation_admin": {("organisation", OWN)},
        "organisation_staff_viewer": set(),
        "organisation_staff_roles_viewer": set(),
        "question_bank_viewer": set(),
        "cohort_admin": set(),
        "cohort_viewer": set(),
    },
    ASSIGN_COHORT_ADMIN: {
        "site_admin": {
            ("cohort", OWN),
            ("cohort", OTHER_COHORT),
            ("cohort", OTHER_ORGANISATION),
        },
        "organisation_admin": {("cohort", OWN), ("cohort", OTHER_COHORT)},
        "organisation_staff_viewer": set(),
        "organisation_staff_roles_viewer": set(),
        "question_bank_viewer": set(),
        "cohort_admin": {("cohort", OWN)},
        "cohort_viewer": set(),
    },
    ASSIGN_COHORT_VIEWER: {
        "site_admin": {
            ("cohort", OWN),
            ("cohort", OTHER_COHORT),
            ("cohort", OTHER_ORGANISATION),
        },
        "organisation_admin": {("cohort", OWN), ("cohort", OTHER_COHORT)},
        "organisation_staff_viewer": set(),
        "organisation_staff_roles_viewer": set(),
        "question_bank_viewer": set(),
        "cohort_admin": {("cohort", OWN)},
        "cohort_viewer": set(),
    },
    VIEW_STAFFMEMBER: {
        "site_admin": {("organisation", OWN), ("organisation", OTHER_ORGANISATION)},
        "organisation_admin": {("organisation", OWN)},
        "organisation_staff_viewer": set(),
        "organisation_staff_roles_viewer": set(),
        "question_bank_viewer": set(),
        "cohort_admin": set(),
        "cohort_viewer": set(),
    },
    ADD_STAFFMEMBER: {
        "site_admin": {("organisation", OWN), ("organisation", OTHER_ORGANISATION)},
        "organisation_admin": {("organisation", OWN)},
        "organisation_staff_viewer": set(),
        "organisation_staff_roles_viewer": set(),
        "question_bank_viewer": set(),
        "cohort_admin": set(),
        "cohort_viewer": set(),
    },
    CHANGE_STAFFMEMBER: {
        "site_admin": {("organisation", OWN), ("organisation", OTHER_ORGANISATION)},
        "organisation_admin": {("organisation", OWN)},
        "organisation_staff_viewer": set(),
        "organisation_staff_roles_viewer": set(),
        "question_bank_viewer": set(),
        "cohort_admin": set(),
        "cohort_viewer": set(),
    },
    ASSIGN_ORGANISATION_ADMIN: {
        "site_admin": {("organisation", OWN), ("organisation", OTHER_ORGANISATION)},
        "organisation_admin": {("organisation", OWN)},
        "organisation_staff_viewer": set(),
        "organisation_staff_roles_viewer": set(),
        "question_bank_viewer": set(),
        "cohort_admin": set(),
        "cohort_viewer": set(),
    },
    ASSIGN_SITE_ADMIN: {
        "site_admin": {("site", OWN)},
        "organisation_admin": set(),
        "organisation_staff_viewer": set(),
        "organisation_staff_roles_viewer": set(),
        "question_bank_viewer": set(),
        "cohort_admin": set(),
        "cohort_viewer": set(),
    },
    DOWNLOAD_COHORT_REPORT: {
        "site_admin": {
            ("cohort", OWN),
            ("cohort", OTHER_COHORT),
            ("cohort", OTHER_ORGANISATION),
            ("organisation", OWN),
            ("organisation", OTHER_ORGANISATION),
        },
        "organisation_admin": {
            ("cohort", OWN),
            ("cohort", OTHER_COHORT),
            ("organisation", OWN),
        },
        "organisation_staff_viewer": set(),
        "organisation_staff_roles_viewer": set(),
        "question_bank_viewer": set(),
        "cohort_admin": {("cohort", OWN)},
        "cohort_viewer": {("cohort", OWN)},
    },
    VIEW_ORGANISATION_STAFF: {
        "site_admin": {("organisation", OWN), ("organisation", OTHER_ORGANISATION)},
        "organisation_admin": {("organisation", OWN)},
        "organisation_staff_viewer": {("organisation", OWN)},
        "organisation_staff_roles_viewer": {("organisation", OWN)},
        "question_bank_viewer": set(),
        "cohort_admin": set(),
        "cohort_viewer": set(),
    },
    VIEW_ORGANISATION_STAFF_ROLES: {
        "site_admin": {("organisation", OWN), ("organisation", OTHER_ORGANISATION)},
        "organisation_admin": {("organisation", OWN)},
        "organisation_staff_viewer": set(),
        "organisation_staff_roles_viewer": {("organisation", OWN)},
        "question_bank_viewer": set(),
        "cohort_admin": set(),
        "cohort_viewer": set(),
    },
    ASSIGN_ORGANISATION_STAFF_VIEWER: {
        "site_admin": {("organisation", OWN), ("organisation", OTHER_ORGANISATION)},
        "organisation_admin": {("organisation", OWN)},
        "organisation_staff_viewer": set(),
        "organisation_staff_roles_viewer": set(),
        "question_bank_viewer": set(),
        "cohort_admin": set(),
        "cohort_viewer": set(),
    },
    ASSIGN_ORGANISATION_STAFF_ROLES_VIEWER: {
        "site_admin": {("organisation", OWN), ("organisation", OTHER_ORGANISATION)},
        "organisation_admin": {("organisation", OWN)},
        "organisation_staff_viewer": set(),
        "organisation_staff_roles_viewer": set(),
        "question_bank_viewer": set(),
        "cohort_admin": set(),
        "cohort_viewer": set(),
    },
    VIEW_COURSE_QUESTIONS: {
        "site_admin": set(),
        "organisation_admin": set(),
        "organisation_staff_viewer": set(),
        "organisation_staff_roles_viewer": set(),
        "question_bank_viewer": {("organisation", OWN)},
        "cohort_admin": set(),
        "cohort_viewer": set(),
    },
    ASSIGN_QUESTION_BANK_VIEWER: {
        "site_admin": {("organisation", OWN), ("organisation", OTHER_ORGANISATION)},
        "organisation_admin": {("organisation", OWN)},
        "organisation_staff_viewer": set(),
        "organisation_staff_roles_viewer": set(),
        "question_bank_viewer": set(),
        "cohort_admin": set(),
        "cohort_viewer": set(),
    },
}

#: Which scope kinds each capability is asked of.
CAPABILITY_SCOPE_KINDS: dict[str, tuple[str, ...]] = {
    VIEW_ORGANISATION: ("organisation",),
    VIEW_COHORT: ("cohort",),
    VIEW_LEARNER: ("learner",),
    VIEW_CONVERSATION: ("learner",),
    VIEW_AUDITLOGENTRY: ("organisation", "cohort", "learner"),
    ADD_COHORT: ("organisation",),
    CHANGE_COHORT: ("cohort",),
    DELETE_COHORT: ("cohort",),
    ADD_LEARNER: ("organisation",),
    CHANGE_LEARNER: ("learner",),
    CHANGE_USER: ("learner",),
    ADD_COHORTMEMBERSHIP: ("cohort",),
    DELETE_COHORTMEMBERSHIP: ("cohort",),
    ADD_COHORTCOURSEREGISTRATION: ("cohort",),
    CHANGE_COHORTCOURSEREGISTRATION: ("cohort",),
    ADD_LEARNERCOURSEREGISTRATION: ("learner",),
    CHANGE_LEARNERCOURSEREGISTRATION: ("learner",),
    BULK_MANAGE_LEARNERS: ("organisation",),
    ASSIGN_COHORT_ADMIN: ("cohort",),
    ASSIGN_COHORT_VIEWER: ("cohort",),
    VIEW_STAFFMEMBER: ("organisation",),
    ADD_STAFFMEMBER: ("organisation",),
    CHANGE_STAFFMEMBER: ("organisation",),
    ASSIGN_ORGANISATION_ADMIN: ("organisation",),
    ASSIGN_SITE_ADMIN: ("site",),
    DOWNLOAD_COHORT_REPORT: ("cohort", "organisation"),
    VIEW_ORGANISATION_STAFF: ("organisation",),
    VIEW_ORGANISATION_STAFF_ROLES: ("organisation",),
    ASSIGN_ORGANISATION_STAFF_VIEWER: ("organisation",),
    ASSIGN_ORGANISATION_STAFF_ROLES_VIEWER: ("organisation",),
    VIEW_COURSE_QUESTIONS: ("organisation",),
    ASSIGN_QUESTION_BANK_VIEWER: ("organisation",),
}


class World(NamedTuple):
    """One grant holder per role, and one scope object per (kind, relation)."""

    users: dict[str, AbstractBaseUser]
    scopes: dict[tuple[str, str], Model]


def _build_world(site_a: Site) -> World:
    site_b = SiteFactory()

    o1 = OrganisationFactory()
    o2 = OrganisationFactory()
    o3 = OrganisationFactory(site=site_b)

    c1 = CohortFactory(organisation=o1)
    c2 = CohortFactory(organisation=o1)
    c3 = CohortFactory(organisation=o2)
    c4 = CohortFactory(organisation=o3, site=site_b)

    l1 = LearnerFactory(organisation=o1)
    l2 = LearnerFactory(organisation=o1)
    l3 = LearnerFactory(organisation=o2)
    l4 = LearnerFactory(organisation=o3)

    CohortMembershipFactory(cohort=c1, learner=l1)
    CohortMembershipFactory(cohort=c2, learner=l2)
    CohortMembershipFactory(cohort=c3, learner=l3)
    CohortMembershipFactory(cohort=c4, learner=l4, site=site_b)

    site_admin_user = UserFactory()
    assign_site_role(site_admin_user, "site_admin", site=site_a)

    organisation_admin_user = UserFactory()
    assign_object_role(organisation_admin_user, o1, "organisation_admin")

    organisation_staff_viewer_user = UserFactory()
    assign_object_role(organisation_staff_viewer_user, o1, "organisation_staff_viewer")

    organisation_staff_roles_viewer_user = UserFactory()
    assign_object_role(
        organisation_staff_roles_viewer_user, o1, "organisation_staff_roles_viewer"
    )

    question_bank_viewer_user = UserFactory()
    assign_object_role(question_bank_viewer_user, o1, "question_bank_viewer")

    cohort_admin_user = UserFactory()
    assign_object_role(cohort_admin_user, c1, "cohort_admin")

    cohort_viewer_user = UserFactory()
    assign_object_role(cohort_viewer_user, c1, "cohort_viewer")

    # factory_boy's metaclass makes mypy see these factories as returning the
    # factory class rather than the model, per pyproject's mypy override --
    # cast() back to the real return types at the one point they leave this
    # function.
    return World(
        users={
            "site_admin": cast(AbstractBaseUser, site_admin_user),
            "organisation_admin": cast(AbstractBaseUser, organisation_admin_user),
            "organisation_staff_viewer": cast(
                AbstractBaseUser, organisation_staff_viewer_user
            ),
            "organisation_staff_roles_viewer": cast(
                AbstractBaseUser, organisation_staff_roles_viewer_user
            ),
            "question_bank_viewer": cast(AbstractBaseUser, question_bank_viewer_user),
            "cohort_admin": cast(AbstractBaseUser, cohort_admin_user),
            "cohort_viewer": cast(AbstractBaseUser, cohort_viewer_user),
        },
        scopes={
            ("site", OWN): cast(Model, site_a),
            ("site", OTHER_SITE): cast(Model, site_b),
            ("organisation", OWN): cast(Model, o1),
            ("organisation", OTHER_ORGANISATION): cast(Model, o2),
            ("organisation", OTHER_SITE): cast(Model, o3),
            ("cohort", OWN): cast(Model, c1),
            ("cohort", OTHER_COHORT): cast(Model, c2),
            ("cohort", OTHER_ORGANISATION): cast(Model, c3),
            ("cohort", OTHER_SITE): cast(Model, c4),
            ("learner", OWN): cast(Model, l1),
            ("learner", OTHER_COHORT): cast(Model, l2),
            ("learner", OTHER_ORGANISATION): cast(Model, l3),
            ("learner", OTHER_SITE): cast(Model, l4),
        },
    )


def _cases() -> list[tuple[str, str, str, str]]:
    """(capability, role, kind, relation) for every combination MATRIX and
    CAPABILITY_SCOPE_KINDS cover."""
    return [
        (capability, role, kind, relation)
        for capability, kinds in CAPABILITY_SCOPE_KINDS.items()
        for kind in kinds
        for relation in RELATIONS_FOR_KIND[kind]
        for role in ROLES
    ]


class _Walk:
    """Every disagreement a walk finds, kept so one failing cell does not hide the rest.

    A walk checks many cells against one world because building the world costs far more than
    any one check.
    """

    def __init__(self, subject: str) -> None:
        self.subject = subject
        self.checked = 0
        self.mismatches: list[str] = []

    def check(
        self,
        expected: Callable[[], object],
        actual: Callable[[], object],
        *,
        same: Callable[[object, object], bool] = operator.is_,
        **coordinates: str,
    ) -> None:
        """Check one cell and keep any disagreement.

        Both sides are computed under the cell's name, so an error from either one
        names the cell and carries the mismatches found before it. `same` defaults to
        identity, which makes a truthy non-bool answer fail where True is expected.
        """
        with _naming_the_cell(self._earlier_mismatches(), **coordinates):
            expected_value = expected()
            actual_value = actual()
        self.checked += 1
        if not same(actual_value, expected_value):
            self.mismatches.append(
                _cell_line(
                    **coordinates,
                    expected=str(expected_value),
                    actual=str(actual_value),
                )
            )

    def _earlier_mismatches(self) -> list[str]:
        if not self.mismatches:
            return []
        header = f"{len(self.mismatches)} earlier mismatches for {self.subject}:"
        return [header, *sorted(self.mismatches)]

    def report(self) -> None:
        """Fail with every mismatch, sorted so the same failure always prints the same report.

        A walk that checked no cell fails too: it would otherwise pass while testing nothing.
        """
        if not self.checked:
            pytest.fail(f"no cells checked for {self.subject}", pytrace=False)
        if not self.mismatches:
            return
        lines = sorted(self.mismatches)
        header = f"{len(lines)} of {self.checked} cells disagree for {self.subject}"
        pytest.fail("\n".join([header, *lines]), pytrace=False)


def _cell_line(**pairs: str) -> str:
    return " ".join(f"{key}={value}" for key, value in pairs.items())


@contextmanager
def _naming_the_cell(earlier: list[str], **coordinates: str) -> Iterator[None]:
    """An error raised while checking a cell still fails the test, now naming the cell
    and listing the mismatches the walk had already found, so the error hides none of them."""
    try:
        yield
    # Broad on purpose, and approved as an exception to the catch-specific-exceptions rule:
    # this only adds notes to whatever was raised and re-raises it, so nothing is swallowed,
    # and naming types here would leave any other error without its cell. It is the only
    # broad catch in this file.
    except Exception as error:
        error.add_note(_cell_line(**coordinates))
        for line in earlier:
            error.add_note(line)
        raise


def _always(value: object) -> Callable[[], object]:
    """A side of a check that is already known, such as a step's expected answer."""
    return lambda: value


def _matrix_allows(capability: str, role: str, kind: str, relation: str) -> bool:
    return (kind, relation) in MATRIX[capability][role]


def _walk_matrix(world: World, capability: str) -> _Walk:
    """Every cell of one capability, against one world.

    It loops instead of parametrizing because building the world is the cost of a cell,
    not the check. `can()` keeps no cache between calls, so one world answers every cell.
    """
    walk = _Walk(capability)
    for cell_capability, role, kind, relation in _cases():
        if cell_capability != capability:
            continue
        walk.check(
            partial(_matrix_allows, capability, role, kind, relation),
            partial(can, world.users[role], capability, world.scopes[(kind, relation)]),
            capability=capability,
            role=role,
            kind=kind,
            relation=relation,
        )
    return walk


def _codename(capability: str) -> str:
    return capability.split(".", 1)[1]


@pytest.mark.django_db
@pytest.mark.parametrize("capability", CAPABILITY_SCOPE_KINDS, ids=_codename)
def test_can_matches_the_matrix(mock_site_context: Site, capability: str) -> None:
    world = _build_world(mock_site_context)

    walk = _walk_matrix(world, capability)

    walk.report()


def test_every_capability_a_role_holds_has_a_matrix_entry() -> None:
    held_capabilities = {
        capability for role in ROLES for capability in BASE_ROLES[role].permissions
    }

    for capability in held_capabilities:
        assert capability in MATRIX, f"{capability!r} has no MATRIX entry"


def test_every_matrix_entry_names_every_role() -> None:
    for capability, by_role in MATRIX.items():
        assert set(by_role) == set(ROLES), (
            f"{capability!r}'s MATRIX entry does not cover every role"
        )


@pytest.mark.parametrize("role", ROLES)
def test_a_roles_permissions_equal_the_capabilities_its_matrix_column_allows(
    role: str,
) -> None:
    from_matrix = {
        capability for capability, by_role in MATRIX.items() if by_role[role]
    }

    assert BASE_ROLES[role].permissions == from_matrix


def _cohort_is_listed(user: AbstractBaseUser, scope: Model) -> bool:
    cohort = cast(Cohort, scope)
    return cohorts_visible_to(user, cohort.organisation).filter(pk=cohort.pk).exists()


def _learner_is_listed(user: AbstractBaseUser, scope: Model) -> bool:
    learner = cast(Learner, scope)
    return (
        learners_visible_to(user, learner.organisation, include_inactive=True)
        .filter(pk=learner.pk)
        .exists()
    )


def _walk_visibility(
    world: World,
    kind: str,
    capability: str,
    visible: Callable[[AbstractBaseUser, Model], bool],
) -> _Walk:
    """The queryset a list renders and the per-object check gating a row agree, for every
    role on every scope object of this kind.

    It walks instead of parametrizing because every role pays for building a world, and
    one world answers them all.
    """
    walk = _Walk(f"{kind} visibility")
    for role in ROLES:
        user = world.users[role]
        for (scope_kind, relation), scope in world.scopes.items():
            if scope_kind != kind:
                continue
            walk.check(
                partial(can, user, capability, scope),
                partial(visible, user, scope),
                role=role,
                kind=kind,
                relation=relation,
            )
    return walk


@pytest.mark.django_db
def test_cohorts_visible_to_agrees_with_can_on_every_cohort(
    mock_site_context: Site,
) -> None:
    """The queryset a list renders and the per-object check gating a row must
    never disagree about which cohorts any role can see."""
    world = _build_world(mock_site_context)

    walk = _walk_visibility(world, "cohort", VIEW_COHORT, _cohort_is_listed)

    walk.report()


@pytest.mark.django_db
def test_learners_visible_to_agrees_with_can_on_every_learner(
    mock_site_context: Site,
) -> None:
    """Same agreement, on the learner side."""
    world = _build_world(mock_site_context)

    walk = _walk_visibility(world, "learner", VIEW_LEARNER, _learner_is_listed)

    walk.report()


def _gated_true_cases() -> list[tuple[str, str, str, str]]:
    """Every (capability, role, kind, relation) case _cases() covers where
    the role is one whose grant only counts through an active
    StaffMember, and the matrix says the answer is True."""
    return [
        (capability, role, kind, relation)
        for capability, role, kind, relation in _cases()
        if role in GATED_ROLES and (kind, relation) in MATRIX[capability][role]
    ]


def _walk_deactivation(world: World, role: str) -> _Walk:
    """The StaffMember gate, one role at a time.

    Every gated cell of a role hangs off that role's single StaffMember row, so one
    deactivate and reactivate checks all of them both ways.

    All three steps share one world on purpose: the row each step reads is the
    one the step before changed.
    """
    walk = _Walk(f"role {role}")
    user = world.users[role]
    cells = [
        (capability, kind, relation)
        for capability, cell_role, kind, relation in _gated_true_cases()
        if cell_role == role
    ]
    scopes = {
        (kind, relation): world.scopes[(kind, relation)] for _, kind, relation in cells
    }
    member = StaffMember.objects.get(user=user)

    _check_gated_cells(walk, "active", True, user, role, cells, world)
    before = _Snapshots.take(user, scopes)

    member.is_active = False
    member.save(update_fields=["is_active"])
    try:
        _check_gated_cells(walk, "deactivated", False, user, role, cells, world)
        _check_snapshots(
            walk, "deactivated", role, before, _Snapshots.take(user, scopes)
        )
    finally:
        member.is_active = True
        member.save(update_fields=["is_active"])
    _check_gated_cells(walk, "reactivated", True, user, role, cells, world)
    _check_snapshots(walk, "reactivated", role, before, _Snapshots.take(user, scopes))
    return walk


class _Snapshots(NamedTuple):
    """What deactivating a StaffMember row must never touch."""

    assignments: list[tuple[int, int, int, str, str, bool]]
    guardian: dict[tuple[str, str], list[str]]

    @classmethod
    def take(
        cls, user: AbstractBaseUser, scopes: dict[tuple[str, str], Model]
    ) -> _Snapshots:
        return cls(
            assignments=sorted(
                (
                    a.user_id,
                    a.site_id,
                    a.content_type_id,
                    a.object_id,
                    a.role,
                    a.is_active,
                )
                for a in ObjectRoleAssignment.objects.filter(user=user)
            ),
            guardian={
                key: sorted(get_perms(user, scope)) for key, scope in scopes.items()
            },
        )


def _check_gated_cells(
    walk: _Walk,
    step: str,
    expected: bool,
    user: AbstractBaseUser,
    role: str,
    cells: list[tuple[str, str, str]],
    world: World,
) -> None:
    for capability, kind, relation in cells:
        walk.check(
            _always(expected),
            partial(can, user, capability, world.scopes[(kind, relation)]),
            step=step,
            capability=capability,
            role=role,
            kind=kind,
            relation=relation,
        )


def _check_snapshots(
    walk: _Walk, step: str, role: str, before: _Snapshots, now: _Snapshots
) -> None:
    walk.check(
        _always(before.assignments),
        _always(now.assignments),
        same=operator.eq,
        step=step,
        role=role,
        snapshot="assignments",
    )
    for (kind, relation), perms in before.guardian.items():
        walk.check(
            _always(perms),
            _always(now.guardian[(kind, relation)]),
            same=operator.eq,
            step=step,
            role=role,
            snapshot="guardian",
            kind=kind,
            relation=relation,
        )


@pytest.mark.django_db
@pytest.mark.parametrize("role", GATED_ROLES)
def test_deactivating_the_staff_member_row_withdraws_the_grant(
    mock_site_context: Site, role: str
) -> None:
    """The StaffMember gate: an organisation or cohort grant counts
    only while the grant holder's StaffMember row for that
    organisation is active. Deactivating it must withdraw every gated
    answer the role holds, and reactivating it must restore every one,
    with the role assignment and guardian rows never touched."""
    world = _build_world(mock_site_context)

    walk = _walk_deactivation(world, role)

    walk.report()


@pytest.mark.django_db
def test_every_capability_reachable_from_the_interface_is_in_matrix(
    mock_site_context: Site,
) -> None:
    organisation = OrganisationFactory()
    capabilities = _walked_capabilities(organisation)
    capabilities.discard(None)

    assert capabilities <= set(MATRIX)


def _walked_capabilities(organisation: Organisation) -> set[str | None]:
    """Every capability the interface's actions and bulk actions declare."""
    capabilities: set[str | None] = set()
    for item in walk_interface(organisation):
        if isinstance(item, WalkedAction):
            capabilities.add(item.action.get_capability(item.ctx))
        elif isinstance(item, WalkedBulkAction):
            capabilities.add(item.action.capability)
    return capabilities


@pytest.mark.django_db
def test_assign_cohort_viewer_is_reachable_from_the_interface(
    mock_site_context: Site,
) -> None:
    organisation = OrganisationFactory()
    capabilities = _walked_capabilities(organisation)

    assert ASSIGN_COHORT_VIEWER in capabilities


@pytest.mark.django_db
def test_download_cohort_report_is_reachable_from_the_interface(
    mock_site_context: Site,
) -> None:
    organisation = OrganisationFactory()
    capabilities = {
        item.action.get_capability(item.ctx)
        for item in walk_interface(organisation)
        if isinstance(item, WalkedAction)
    }

    assert DOWNLOAD_COHORT_REPORT in capabilities


def test_assign_cohort_viewer_is_in_the_matrix() -> None:
    assert ASSIGN_COHORT_VIEWER in MATRIX


@pytest.mark.django_db
def test_cohort_admin_holds_delete_cohortmembership_on_its_own_cohort(
    mock_site_context: Site,
) -> None:
    world = _build_world(mock_site_context)
    user = world.users["cohort_admin"]
    own_cohort = world.scopes[("cohort", OWN)]

    assert can(user, DELETE_COHORTMEMBERSHIP, own_cohort) is True


@pytest.mark.django_db
def test_cohort_admin_holds_add_cohortmembership_on_another_cohort_only_with_a_grant_there(
    mock_site_context: Site,
) -> None:
    """A membership move needs delete_ on the source cohort and add_ on the
    destination. cohort_admin already holds both on its own cohort; on a
    cohort it holds no grant on, add_cohortmembership counts only once it is
    granted there too -- can() never reads one cohort's grant for another."""
    world = _build_world(mock_site_context)
    user = world.users["cohort_admin"]
    other_cohort = cast(Cohort, world.scopes[("cohort", OTHER_COHORT)])

    assert can(user, ADD_COHORTMEMBERSHIP, other_cohort) is False

    assign_object_role(user, other_cohort, "cohort_admin")

    assert can(user, ADD_COHORTMEMBERSHIP, other_cohort) is True


def _course_deactivation_offered(
    world: World, user: User, registration: CohortCourseRegistration
) -> bool:
    """Whether the course page's Deactivate action reaches `registration` for
    `user`: the permission check passes and the row resolves in its scope."""
    organisation = cast(Organisation, world.scopes[("organisation", OWN)])
    request = cast(
        OrganisationScopedRequest,
        RequestFactory().get("/x", {"registration": str(registration.pk)}),
    )
    request.user = user
    request.organisation = organisation
    ctx = PanelContext(
        request=request,
        instance=registration.course,
        base_url="/x",
        name="cohorts",
        config=CourseConfig,
    )
    action = DeactivateCourseCohortRegistrationAction()
    try:
        return action.has_permission(ctx)
    except Http404:
        return False


@pytest.mark.django_db
def test_the_course_page_deactivation_follows_the_registrations_own_cohort(
    mock_site_context: Site,
) -> None:
    world = _build_world(mock_site_context)
    course = CourseFactory()
    walk = _Walk("the course page's Deactivate action")
    for relation in (OWN, OTHER_COHORT):
        cohort = cast(Cohort, world.scopes[("cohort", relation)])
        registration = CohortCourseRegistrationFactory(cohort=cohort, course=course)
        for role in ROLES:
            allowed = ("cohort", relation) in MATRIX[CHANGE_COHORTCOURSEREGISTRATION][
                role
            ]
            walk.check(
                lambda allowed=allowed: allowed,
                partial(
                    _course_deactivation_offered,
                    world,
                    cast(User, world.users[role]),
                    registration,
                ),
                role=role,
                relation=relation,
            )

    walk.report()


def _course_register_context(world: World, user: User, course: Course) -> PanelContext:
    request = cast(OrganisationScopedRequest, RequestFactory().get("/x"))
    request.user = user
    request.organisation = cast(Organisation, world.scopes[("organisation", OWN)])
    return PanelContext(
        request=request,
        instance=course,
        base_url="/x",
        name="cohorts",
        config=CourseConfig,
    )


def _course_register_cohorts(world: World, user: User, course: Course) -> set[str]:
    """The relations (own, other_cohort) of the world's cohorts that the
    course page's Register picker offers `user`; empty when the action is
    not permitted."""
    action = RegisterCohortOnCourseAction()
    ctx = _course_register_context(world, user, course)
    if not action.has_permission(ctx):
        return set()
    offered = set(action._cohorts(ctx).values_list("pk", flat=True))
    return {
        relation
        for relation in (OWN, OTHER_COHORT)
        if world.scopes[("cohort", relation)].pk in offered
    }


@pytest.mark.django_db
def test_the_course_page_register_picker_offers_the_cohorts_the_role_may_register(
    mock_site_context: Site,
) -> None:
    world = _build_world(mock_site_context)
    course = CourseFactory()
    walk = _Walk("the course page's Register action")
    for role in ROLES:
        walk.check(
            lambda role=role: {
                relation
                for (kind, relation) in MATRIX[ADD_COHORTCOURSEREGISTRATION][role]
                if kind == "cohort" and relation in (OWN, OTHER_COHORT)
            },
            partial(
                _course_register_cohorts, world, cast(User, world.users[role]), course
            ),
            same=operator.eq,
            role=role,
        )

    walk.report()


def _course_learner_registration_offered(
    world: World,
    user: User,
    registration: LearnerCourseRegistration,
    action: DeactivateCourseLearnerRegistrationAction
    | ReactivateCourseLearnerRegistrationAction,
) -> bool:
    """Whether the course page's Deactivate or Reactivate action reaches
    `registration` for `user`: the permission check passes and the row
    resolves in its scope."""
    request = cast(
        OrganisationScopedRequest,
        RequestFactory().get("/x", {"registration": str(registration.pk)}),
    )
    request.user = user
    request.organisation = cast(Organisation, world.scopes[("organisation", OWN)])
    ctx = PanelContext(
        request=request,
        instance=registration.course,
        base_url="/x",
        name="learners",
        config=CourseConfig,
    )
    try:
        return action.has_permission(ctx)
    except Http404:
        return False


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("action_class", "is_active"),
    [
        (DeactivateCourseLearnerRegistrationAction, True),
        (ReactivateCourseLearnerRegistrationAction, False),
    ],
)
def test_the_course_page_direct_registration_actions_follow_the_learners_grant(
    mock_site_context: Site,
    action_class: type[
        DeactivateCourseLearnerRegistrationAction
        | ReactivateCourseLearnerRegistrationAction
    ],
    is_active: bool,
) -> None:
    world = _build_world(mock_site_context)
    course = CourseFactory()
    walk = _Walk(f"the course page's {action_class.__name__}")
    for relation in (OWN, OTHER_COHORT):
        learner = cast(Learner, world.scopes[("learner", relation)])
        registration = LearnerCourseRegistrationFactory(
            learner=learner, course=course, is_active=is_active
        )
        for role in ROLES:
            allowed = ("learner", relation) in MATRIX[CHANGE_LEARNERCOURSEREGISTRATION][
                role
            ]
            walk.check(
                lambda allowed=allowed: allowed,
                partial(
                    _course_learner_registration_offered,
                    world,
                    cast(User, world.users[role]),
                    registration,
                    action_class(),
                ),
                role=role,
                relation=relation,
            )

    walk.report()


def _course_register_learners(world: World, user: User, course: Course) -> set[str]:
    """The relations (own, other_cohort) of the world's learners that the
    course page's learner Register picker offers `user`; empty when the
    action is not permitted."""
    action = RegisterLearnerOnCourseAction()
    ctx = _course_register_context(world, user, course)
    if not action.has_permission(ctx):
        return set()
    offered = set(action._learners(ctx).values_list("pk", flat=True))
    return {
        relation
        for relation in (OWN, OTHER_COHORT)
        if world.scopes[("learner", relation)].pk in offered
    }


@pytest.mark.django_db
def test_the_course_page_learner_register_picker_offers_the_learners_the_role_may_register(
    mock_site_context: Site,
) -> None:
    world = _build_world(mock_site_context)
    course = CourseFactory()
    walk = _Walk("the course page's learner Register action")
    for role in ROLES:
        walk.check(
            lambda role=role: {
                relation
                for (kind, relation) in MATRIX[ADD_LEARNERCOURSEREGISTRATION][role]
                if kind == "learner" and relation in (OWN, OTHER_COHORT)
            },
            partial(
                _course_register_learners, world, cast(User, world.users[role]), course
            ),
            same=operator.eq,
            role=role,
        )

    walk.report()


def _organisation_gate_expected(role: str) -> bool:
    return all(
        ("organisation", OWN) in MATRIX[capability][role]
        for capability in (BULK_MANAGE_LEARNERS, ADD_LEARNER)
    )


def _cohort_gate_expected(role: str) -> bool:
    return ("organisation", OWN) in MATRIX[ADD_LEARNER][role] and (
        "cohort",
        OWN,
    ) in MATRIX[ADD_COHORTMEMBERSHIP][role]


def _walk_import_gate(
    world: World, cohort: Cohort | None, expected_for: Callable[[str], bool]
) -> _Walk:
    """check_import_gate for every role, against what MATRIX allows.

    It walks instead of parametrizing because every role pays for building a world, and
    one world answers them all.
    """
    organisation = cast(Organisation, world.scopes[("organisation", OWN)])
    walk = _Walk(
        "the organisation import gate" if cohort is None else "the cohort import gate"
    )
    for role in ROLES:
        walk.check(
            partial(expected_for, role),
            partial(
                check_import_gate, cast(User, world.users[role]), organisation, cohort
            ),
            role=role,
        )
    return walk


@pytest.mark.django_db
def test_the_organisation_import_gate_needs_bulk_manage_learners_and_add_learner(
    mock_site_context: Site,
) -> None:
    world = _build_world(mock_site_context)

    walk = _walk_import_gate(world, None, _organisation_gate_expected)

    walk.report()


@pytest.mark.django_db
def test_the_cohort_import_gate_needs_add_learner_and_add_cohortmembership(
    mock_site_context: Site,
) -> None:
    world = _build_world(mock_site_context)
    cohort = cast(Cohort, world.scopes[("cohort", OWN)])

    walk = _walk_import_gate(world, cohort, _cohort_gate_expected)

    walk.report()


@pytest.mark.django_db
def test_the_cohort_import_gate_refuses_an_inactive_cohort(
    mock_site_context: Site,
) -> None:
    world = _build_world(mock_site_context)
    user = cast(User, world.users["organisation_admin"])
    organisation = cast(Organisation, world.scopes[("organisation", OWN)])
    cohort = cast(Cohort, world.scopes[("cohort", OWN)])
    cohort.is_active = False
    cohort.save(update_fields=["is_active"])

    assert check_import_gate(user, organisation, cohort) is False
