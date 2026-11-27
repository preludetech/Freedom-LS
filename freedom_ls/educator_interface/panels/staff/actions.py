"""Staff role helpers, refusals and the actions on staff members and their roles."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import replace
from typing import NamedTuple, cast

from panel_framework.actions import (
    ConfirmAction,
    ModalPanelAction,
    PanelAction,
    changed_response,
    denied_response,
    field_error_count,
    join_prose,
    refusal_response,
)
from panel_framework.context import PanelContext

from django import forms
from django.db import transaction
from django.db.models import Model, QuerySet
from django.http import (
    Http404,
    HttpRequest,
    HttpResponse,
    QueryDict,
)
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.utils import timezone

from freedom_ls.accounts.account_setup import (
    EmailInUseOnAnotherSite,
    lookup_user,
    match_or_create_user,
    send_account_setup_email,
)
from freedom_ls.accounts.models import User
from freedom_ls.accounts.search import MIN_TERM_LENGTH, term_condition
from freedom_ls.educator_interface.events import (
    STAFF_CHANGED,
)
from freedom_ls.educator_interface.forms import (
    AddStaffMemberForm,
    ChangeRoleForm,
    CohortSetForm,
    StaffEmailForm,
)
from freedom_ls.educator_interface.panels.common.actions import (
    EducatorReasonMixin,
    _action_params,
)
from freedom_ls.educator_interface.panels.common.request import (
    OrganisationScopedRequest,
)
from freedom_ls.educator_interface.panels.staff.filters import may_see_staff_roles
from freedom_ls.educator_interface.staff import (
    ORGANISATION_SCOPE,
    RoleEntry,
    current_role_entries,
)
from freedom_ls.educator_interface.user_display import email_below_name
from freedom_ls.learner_management.capabilities import _active_role_assignments, can
from freedom_ls.learner_management.models import (
    Cohort,
    Learner,
    StaffMember,
)
from freedom_ls.learner_management.queries import (
    ADD_STAFF_MEMBER,
    ASSIGN_COHORT_VIEWER,
    ORGANISATION_ROLES,
    STAFF_ROLES,
    cohorts_visible_to,
    has_staff_assignments,
    pickable_staff,
    role_target,
    staff_assignments,
    staff_of,
)
from freedom_ls.learner_management.role_assignment import (
    ASSIGN,
    CHANGE_STAFF_MEMBER,
    GrantableRole,
    add_staff_member,
    assign_role,
    deactivate_role,
    grantable_roles,
    is_last_organisation_admin,
    is_site_level_admin,
    set_staff_member_active,
)
from freedom_ls.learner_management.utils import (
    ensure_staff_member,
)
from freedom_ls.organisations.models import Organisation
from freedom_ls.role_based_permissions.exceptions import (
    RefusalReason,
    RoleChangeRefused,
)
from freedom_ls.role_based_permissions.loader import get_role_config
from freedom_ls.role_based_permissions.models import ObjectRoleAssignment

__all__ = [
    "OTHER_SITE_MESSAGE",
    "REFUSAL_MESSAGES",
    "SEARCH_LISTBOX_ID",
    "AddRoleAction",
    "AddStaffMemberAction",
    "AddStaffMemberToCohortAction",
    "ChangeCohortsAction",
    "ChangeRoleAction",
    "CohortChange",
    "CohortRoleAction",
    "DeactivateRoleAction",
    "DeactivateStaffMemberAction",
    "ReactivateStaffMemberAction",
    "RemoveStaffFromCohortAction",
    "StaffMemberStateAction",
    "StaffRoleAction",
    "StaffRowMixin",
    "_entries_after",
    "_organisation",
    "_refused",
    "_staff_member_name",
    "actionable_roles",
    "grantable_roles_for",
    "has_grantable_roles",
    "role_entries_shown_to",
    "role_reach",
    "role_refusal_response",
    "roles_grantable_on",
    "staff_member_changed_response",
    "staff_member_state",
]


def grantable_roles_for(request: HttpRequest) -> list[GrantableRole]:
    """The grantor's grantable roles in the request's organisation, computed
    once and kept on the request, so every cell and action on a page reads
    the same list."""
    scoped = cast("OrganisationScopedRequest", request)
    cached = getattr(scoped, "grantable_roles", None)
    if cached is None:
        cached = grantable_roles(cast("User", scoped.user), scoped.organisation)
        scoped.grantable_roles = cached
    return cached


def roles_grantable_on(request: HttpRequest, cohort: Cohort) -> set[str]:
    """The role keys the grantor may give or take on this cohort."""
    return {
        grantable.role
        for grantable in grantable_roles_for(request)
        if grantable.cohorts is not None and cohort in grantable.cohorts
    }


def role_reach(request: HttpRequest, role: str) -> set[Cohort]:
    """The cohorts the grantor may give or take `role` on, inactive ones
    included, computed once per role and kept on the request."""
    scoped = cast("OrganisationScopedRequest", request)
    cached: dict[str, set[Cohort]] | None = getattr(scoped, "role_reach", None)
    if cached is None:
        cached = {}
        scoped.role_reach = cached
    if role not in cached:
        cached[role] = set(
            cohorts_visible_to(
                cast("User", scoped.user),
                scoped.organisation,
                capability=ASSIGN.format(role=role),
            )
        )
    return cached[role]


def actionable_roles(request: HttpRequest, entries: list[RoleEntry]) -> set[str]:
    """The roles among `entries` the grantor may deactivate or change: an
    organisation role they may give, and a cohort role held on at least one
    cohort within their reach."""
    grantable = {g.role for g in grantable_roles_for(request)}
    return {
        entry.role
        for entry in entries
        if entry.role in grantable
        and (
            entry.target == "organisation"
            or any(
                cohort in role_reach(request, entry.role) for cohort in entry.cohorts
            )
        )
    }


def role_entries_shown_to(
    request: HttpRequest, entries: list[RoleEntry]
) -> list[RoleEntry]:
    """The part of a person's roles the viewer may read. A viewer who may see
    staff roles reads them all. Anyone else reads a cohort role on the cohorts
    they may give it on, which that cohort's own Staff list already shows
    them, and no organisation role."""
    if may_see_staff_roles(request):
        return entries
    reach = {
        grantable.role: set(grantable.cohorts)
        for grantable in grantable_roles_for(request)
        if grantable.cohorts is not None
    }
    trimmed = (
        replace(
            entry,
            cohorts=tuple(c for c in entry.cohorts if c in reach.get(entry.role, ())),
        )
        for entry in entries
    )
    return [entry for entry in trimmed if entry.cohorts]


def has_grantable_roles(ctx: PanelContext) -> bool:
    """Whether the viewer may give any staff role here. The organisation-level
    can() is false for a cohort admin, so the per-entry actions ask this
    instead and assign_role / deactivate_role re-check each target."""
    return bool(grantable_roles_for(ctx.request))


#: The in-dialog message for each refusal the interface can show. NOT_PERMITTED is
#: the 403 denied fragment instead, and LAST_SITE_ADMIN cannot arise, because
#: site_admin is never granted or removed from here, so a KeyError on it is a bug.
REFUSAL_MESSAGES: dict[RefusalReason, str] = {
    RefusalReason.INACTIVE_USER: (
        "This person's account is turned off, so they can't be given a role."
    ),
    RefusalReason.SELF: (
        "You can't change your own roles. Ask another organisation admin."
    ),
    RefusalReason.LAST_ORGANISATION_ADMIN: (
        "{name} is this organisation's only organisation admin. "
        "Add another organisation admin first."
    ),
    RefusalReason.ALREADY_STAFF: "{name} is already on the staff here.",
    RefusalReason.INACTIVE_STAFF_MEMBER: (
        "{name} is an inactive staff member here. Use Reactivate staff member instead."
    ),
    RefusalReason.NOT_VISIBLE: (
        "No staff member you can add has this email. "
        "Ask an organisation admin to add them."
    ),
}

SEARCH_LISTBOX_ID = "staff-search-listbox"
OTHER_SITE_MESSAGE = (
    "This address belongs to an account on another site. Use a different address."
)


def _organisation(ctx: PanelContext) -> Organisation:
    return cast("OrganisationScopedRequest", ctx.request).organisation


def _refused(ctx: PanelContext, message: str) -> HttpResponse:
    """The 422 message a staff dialog shows in place of its body."""
    return refusal_response(ctx, title="This change wasn't made", message=message)


def role_refusal_response(
    ctx: PanelContext, action: PanelAction, refused: RoleChangeRefused, name: str
) -> HttpResponse:
    """What a refused role change answers with: the 403 denied fragment for
    a missing capability, else a 422 message inside the dialog."""
    if refused.reason == RefusalReason.NOT_PERMITTED:
        return denied_response(ctx, action)
    return _refused(ctx, REFUSAL_MESSAGES[refused.reason].format(name=name))


def _staff_member_name(user: User | None, email: str) -> str:
    """What the dialog calls the person: their name, or the address of an
    account not yet created."""
    return email if user is None else user.display_name


def staff_member_changed_response(user: User, ctx: PanelContext) -> HttpResponse:
    """The changed response. When the change took away the actor's own access
    to the section the action was posted from (they removed their own
    Organisation admin on Staff), it also sends them to the first section
    they can still see, or the educator root when none shows, so they are
    not left on a page that now 404s."""
    from panel_framework.views import first_visible_section

    from freedom_ls.educator_interface.views import interface_config

    response = changed_response({STAFF_CHANGED: [str(user.pk)]})
    request = ctx.request
    # Visibility answers cached earlier in this request predate the change.
    for cached in ("works_with_cohorts", "may_see_staff_roles"):
        vars(request).pop(cached, None)
    if ctx.config.is_visible(request) and ctx.config.is_available(request):
        return response
    landing = first_visible_section(interface_config, request)
    if landing is None:
        response["HX-Redirect"] = reverse("educator_interface:root")
    else:
        response["HX-Redirect"] = reverse(
            "educator_interface:interface",
            kwargs={
                "organisation_slug": cast(
                    "OrganisationScopedRequest", request
                ).organisation.slug,
                "path_string": landing.url_name,
            },
        )
    return response


def staff_member_state(user: User | None, organisation: Organisation) -> str:
    """Where a role given now would land: "new" for an account not yet
    created, "missing" for one with no StaffMember row here,
    "inactive" for an inactive row, else "active"."""
    if user is None:
        return "new"
    staff_member = StaffMember.objects.filter(
        organisation=organisation, user=user
    ).first()
    if staff_member is None:
        return "missing"
    if not staff_member.is_active:
        return "inactive"
    return "active"


def _entries_after(
    before: list[RoleEntry],
    grantor: User,
    role: str,
    display_name: str,
    cohorts: list[Cohort],
) -> list[RoleEntry]:
    """`before` with `role` on `cohorts` merged in, in STAFF_ROLES order."""
    held = {entry.role: entry for entry in before}
    existing = held.get(role)
    merged = {*(existing.cohorts if existing else ()), *cohorts}
    held[role] = RoleEntry(
        role=role,
        display_name=display_name,
        cohorts=tuple(sorted(merged, key=lambda c: c.name)),
        assigned_by=grantor,
        assigned_at=timezone.now(),
    )
    return [held[key] for key in STAFF_ROLES if key in held]


class AddStaffMemberAction(ModalPanelAction):
    """Gives an existing account a staff role, in a dialog of steps: look up
    the address, choose the role, confirm. Nothing is written until the
    confirmation is submitted."""

    label = "Add staff member"
    action_name = "add_staff_member"
    capability = ADD_STAFF_MEMBER
    template_name = "educator_interface/modal/add_staff_member.html"
    #: Every role this dialog could offer. A role missing from the grantor's
    #: grantable roles counts as withheld only when it is in here.
    offerable_roles: tuple[str, ...] = STAFF_ROLES
    #: Whether the dialog may add someone to the staff with no role.
    offers_no_role: bool = True
    SEARCH_RESULT_LIMIT = 8

    def permission_object(self, ctx: PanelContext) -> Model | None:
        return _organisation(ctx)

    def _may_add_anyone(self, ctx: PanelContext) -> bool:
        """Whether this viewer may add any email address to the staff, not
        only the people they may pick."""
        return can(cast("User", ctx.request.user), ADD_STAFF_MEMBER, _organisation(ctx))

    def _adds_staff(self, ctx: PanelContext) -> bool:
        """Whether this viewer is offered "No roles yet"."""
        return self.offers_no_role and self._may_add_anyone(ctx)

    def is_offered(self, ctx: PanelContext) -> bool:
        return bool(self._grantable(ctx))

    def _grantable(self, ctx: PanelContext) -> list[GrantableRole]:
        return grantable_roles_for(ctx.request)

    def _preset(self, ctx: PanelContext) -> Cohort | None:
        return None

    def _dialog_title(self, ctx: PanelContext) -> str:
        preset = self._preset(ctx)
        return f"Add a staff member to {preset}" if preset else "Add a staff member"

    def _email_context(
        self, ctx: PanelContext, form: StaffEmailForm
    ) -> dict[str, object]:
        return {
            "step": "email",
            "dialog_title": self._dialog_title(ctx),
            "form": form,
            "field_error_count": field_error_count(form),
            "action_url": self.get_action_url(ctx),
            "search_url": self.get_action_url(ctx),
            "listbox_id": SEARCH_LISTBOX_ID,
            "searches_pickable_only": not self._may_add_anyone(ctx),
            "results": [],
            "needs_term": True,
            "term": "",
        }

    def _email_step(
        self, ctx: PanelContext, form: StaffEmailForm, status: int = 200
    ) -> HttpResponse:
        return render(
            ctx.request,
            self.template_name,
            self._email_context(ctx, form),
            status=status,
        )

    def _search_context(self, ctx: PanelContext) -> dict[str, object]:
        """The as-you-type matches for the typed term: up to
        ``SEARCH_RESULT_LIMIT`` of the people this viewer may pick."""
        term = ctx.request.GET["q"].strip()
        context: dict[str, object] = {
            "step": "search",
            "term": term,
            "listbox_id": SEARCH_LISTBOX_ID,
            "searches_pickable_only": not self._may_add_anyone(ctx),
            "needs_term": len(term) < MIN_TERM_LENGTH,
            "results": [],
            "truncated": False,
        }
        if context["needs_term"]:
            return context
        fetched = list(
            pickable_staff(cast("User", ctx.request.user), _organisation(ctx)).filter(
                term_condition(term, include_email=True)
            )[: self.SEARCH_RESULT_LIMIT + 1]
        )
        context["results"] = [
            {
                "pk": user.pk,
                "display_name": user.display_name,
                "email": user.email,
                "email_below_name": email_below_name(user),
            }
            for user in fetched[: self.SEARCH_RESULT_LIMIT]
        ]
        context["truncated"] = len(fetched) > self.SEARCH_RESULT_LIMIT
        return context

    def get_context_data(self, ctx: PanelContext) -> dict[str, object]:
        if "q" in ctx.request.GET:
            return self._search_context(ctx)
        return self._email_context(ctx, StaffEmailForm())

    def handle_submit(self, ctx: PanelContext) -> HttpResponse:
        if not self._grantable(ctx):
            return denied_response(ctx, self)
        if ctx.request.POST.get("step") == "lookup":
            return self._lookup(ctx)
        return self._submit(ctx)

    def _other_site_response(self, ctx: PanelContext) -> HttpResponse:
        form = StaffEmailForm(ctx.request.POST)
        form.is_valid()
        form.add_error("email", OTHER_SITE_MESSAGE)
        return self._email_step(ctx, form, status=422)

    def _match(self, ctx: PanelContext, email: str) -> User | HttpResponse | None:
        """The account for `email`, None when there is none yet, or the
        response that says why the address cannot be used. Someone who may
        add staff looks up any address; anyone else matches only the people
        they may pick, with one message for every miss so the answer never
        reveals whether an account exists."""
        organisation = _organisation(ctx)
        actor = cast("User", ctx.request.user)
        if not self._may_add_anyone(ctx):
            user = (
                pickable_staff(actor, organisation).filter(email__iexact=email).first()
            )
            if user is None:
                return _refused(ctx, REFUSAL_MESSAGES[RefusalReason.NOT_VISIBLE])
            return user
        try:
            user = lookup_user(organisation.site, email)
        except EmailInUseOnAnotherSite:
            return self._other_site_response(ctx)
        return user

    def _fixed_person(self, ctx: PanelContext) -> User | None:
        """The staff member the page fixes, or None when the dialog looks the
        person up by address."""
        return None

    def _posted(self, ctx: PanelContext) -> QueryDict:
        """The submitted fields."""
        return ctx.request.POST

    @staticmethod
    def _unavailable_reason(grantable: GrantableRole, entries: list[RoleEntry]) -> str:
        """Why the role cannot be given again, or "" when it can: the person
        already holds it on the organisation or on every cohort offered."""
        held = next((e for e in entries if e.role == grantable.role), None)
        if held is None:
            return ""
        if grantable.cohorts is None:
            return "Already held"
        if grantable.cohorts and set(grantable.cohorts) <= set(held.cohorts):
            return "Already held on every cohort you can give"
        return ""

    def _role_cards(
        self, ctx: PanelContext, entries: list[RoleEntry]
    ) -> list[dict[str, str | bool]]:
        config = get_role_config(_organisation(ctx).site.name)
        return [
            {
                "key": grantable.role,
                "display_name": config[grantable.role].display_name,
                "description": config[grantable.role].description,
                "needs_cohorts": grantable.cohorts is not None,
                "unavailable_reason": self._unavailable_reason(grantable, entries),
            }
            for grantable in self._grantable(ctx)
        ]

    def _cohort_rows(
        self, ctx: PanelContext, chosen: list[str]
    ) -> list[dict[str, object]]:
        """One checklist row per cohort the grantor may give any cohort role
        on, each naming the roles it is offered for."""
        roles_by_cohort: dict[Cohort, list[str]] = {}
        for grantable in self._grantable(ctx):
            for cohort in grantable.cohorts or ():
                roles_by_cohort.setdefault(cohort, []).append(grantable.role)
        return [
            {
                "pk": str(cohort.pk),
                "name": cohort.name,
                "roles": " ".join(roles),
                "checked": str(cohort.pk) in chosen,
            }
            for cohort, roles in sorted(
                roles_by_cohort.items(), key=lambda item: item[0].name
            )
        ]

    def _role_note(self, ctx: PanelContext) -> str:
        if not Cohort.objects.filter(
            organisation=_organisation(ctx), is_active=True
        ).exists():
            return "This organisation has no active cohorts yet."
        offered = {grantable.role for grantable in self._grantable(ctx)}
        if any(role not in offered for role in self.offerable_roles):
            return "You can only give roles at or below your own."
        return ""

    def _role_step_context(
        self, ctx: PanelContext, user: User | None, form: AddStaffMemberForm
    ) -> dict[str, object]:
        chosen = [str(pk) for pk in form["cohorts"].value() or []]
        person = self._fixed_person(ctx)
        entries = (
            [] if person is None else current_role_entries(person, _organisation(ctx))
        )
        return {
            "step": "role",
            "dialog_title": self._dialog_title(ctx),
            "match": user,
            "new_account": user is None,
            "person": person,
            "current_entries": role_entries_shown_to(ctx.request, entries),
            "form": form,
            "field_error_count": field_error_count(form),
            "action_url": self.get_action_url(ctx),
            "role_cards": self._role_cards(ctx, entries),
            "preset_cohort": self._preset(ctx),
            "cohort_rows": self._cohort_rows(ctx, chosen),
            "selected_role": form["role"].value() or "",
            "offers_no_role": self._adds_staff(ctx),
            "role_note": self._role_note(ctx),
        }

    def _role_step(
        self,
        ctx: PanelContext,
        user: User | None,
        form: AddStaffMemberForm,
        status: int = 200,
    ) -> HttpResponse:
        return render(
            ctx.request,
            self.template_name,
            self._role_step_context(ctx, user, form),
            status=status,
        )

    def _lookup(self, ctx: PanelContext) -> HttpResponse:
        email_form = StaffEmailForm(ctx.request.POST)
        if not email_form.is_valid():
            return self._email_step(ctx, email_form, status=422)
        matched = self._match(ctx, email_form.cleaned_data["email"])
        if isinstance(matched, HttpResponse):
            return matched
        form = AddStaffMemberForm(
            None,
            roles=[
                (grantable.role, grantable.role) for grantable in self._grantable(ctx)
            ],
            cohorts=self._cohort_choices(ctx),
            preset=self._preset(ctx),
            new_account=matched is None,
            allow_no_role=self._adds_staff(ctx),
        )
        form.fields["email"].initial = email_form.cleaned_data["email"]
        return self._role_step(ctx, matched, form)

    def _cohort_choices(self, ctx: PanelContext) -> QuerySet[Cohort]:
        return Cohort.objects.filter(organisation=_organisation(ctx))

    def _targets(
        self, ctx: PanelContext, role: str, cohorts: list[Cohort]
    ) -> list[Organisation | Cohort] | None:
        """What the role is given on, or None when the grantor may not give
        this role there. The cohorts must be among that role's own grantable
        cohorts, not those of another role."""
        grantable = {g.role: g for g in self._grantable(ctx)}.get(role)
        if grantable is None:
            return None
        if grantable.cohorts is None:
            return [_organisation(ctx)]
        allowed = set(grantable.cohorts)
        if not all(cohort in allowed for cohort in cohorts):
            return None
        return list(cohorts)

    def _submit(self, ctx: PanelContext) -> HttpResponse:
        posted = self._posted(ctx)
        matched = self._match(ctx, posted.get("email", ""))
        if isinstance(matched, HttpResponse):
            return matched
        form = AddStaffMemberForm(
            posted,
            roles=[(role, role) for role in STAFF_ROLES],
            cohorts=self._cohort_choices(ctx),
            preset=self._preset(ctx),
            new_account=matched is None,
            allow_no_role=self._adds_staff(ctx),
        )
        if not form.is_valid():
            return self._role_step(ctx, matched, form, status=422)
        role = cast(str, form.cleaned_data["role"])
        cohorts = sorted(form.cleaned_data["cohorts"], key=lambda c: c.name)
        targets = [] if not role else self._targets(ctx, role, cohorts)
        if targets is None:
            return denied_response(ctx, self)
        email = cast(str, form.cleaned_data["email"])
        if not role:
            return self._submit_without_role(ctx, matched, email, form)
        before = (
            [] if matched is None else current_role_entries(matched, _organisation(ctx))
        )
        if role in ORGANISATION_ROLES and any(e.role == role for e in before):
            held_name = get_role_config(_organisation(ctx).site.name)[role].display_name
            return _refused(
                ctx,
                f"{_staff_member_name(matched, email)} is already {held_name} here.",
            )
        held = self._already_held(ctx, matched, role, cohorts)
        names = (
            (
                cast(str, form.cleaned_data["first_name"]),
                cast(str, form.cleaned_data["last_name"]),
            )
            if matched is None
            else ("", "")
        )
        new_cohorts = [cohort for cohort in cohorts if cohort not in held]
        if cohorts and not new_cohorts:
            return _refused(
                ctx,
                f"{_staff_member_name(matched, email)} already holds this role on "
                "these cohorts.",
            )
        new_targets: list[Organisation | Cohort] = [*new_cohorts] or targets
        if ctx.request.POST.get("confirmed") != "1":
            return self._confirmation(
                ctx, email, matched, role, new_cohorts, held, cohorts, names, before
            )
        return self._perform(ctx, matched, email, role, new_targets, names)

    def _submit_without_role(
        self,
        ctx: PanelContext,
        user: User | None,
        email: str,
        form: AddStaffMemberForm,
    ) -> HttpResponse:
        """Add `email` to the staff with no role: refused up front for
        someone already on the staff, so the person sees why before a
        confirm step. Someone who holds roles here with no StaffMember row
        is listed as inactive, and is refused as inactive: a new active row
        would switch those roles on without naming them."""
        organisation = _organisation(ctx)
        names = (
            (
                cast(str, form.cleaned_data["first_name"]),
                cast(str, form.cleaned_data["last_name"]),
            )
            if user is None
            else ("", "")
        )
        state = staff_member_state(user, organisation)
        existing = {
            "active": RefusalReason.ALREADY_STAFF,
            "inactive": RefusalReason.INACTIVE_STAFF_MEMBER,
        }.get(state)
        if (
            user is not None
            and state == "missing"
            and has_staff_assignments(user, organisation)
        ):
            existing = RefusalReason.INACTIVE_STAFF_MEMBER
        if existing is not None:
            return _refused(
                ctx,
                REFUSAL_MESSAGES[existing].format(name=_staff_member_name(user, email)),
            )
        if ctx.request.POST.get("confirmed") != "1":
            return render(
                ctx.request,
                self.template_name,
                {
                    "step": "confirmation",
                    "no_role": True,
                    "match": user,
                    "staff_member_name": _staff_member_name(user, email),
                    "creates_account": user is None,
                    "first_name": names[0],
                    "last_name": names[1],
                    "action_url": self.get_action_url(ctx),
                    "email": email,
                    "role": "",
                    "cohort_ids": [],
                },
            )
        return self._perform(ctx, user, email, "", [], names)

    def _already_held(
        self, ctx: PanelContext, user: User | None, role: str, cohorts: list[Cohort]
    ) -> list[Cohort]:
        """The cohorts among `cohorts` that `user` already holds `role` on."""
        if user is None or not cohorts:
            return []
        held_keys = set(
            staff_assignments(_organisation(ctx))
            .filter(user=user, role=role)
            .values_list("object_id", flat=True)
        )
        return [cohort for cohort in cohorts if str(cohort.pk) in held_keys]

    def _confirmation(
        self,
        ctx: PanelContext,
        email: str,
        user: User | None,
        role: str,
        cohorts: list[Cohort],
        already_held: list[Cohort],
        chosen: list[Cohort],
        names: tuple[str, str],
        before: list[RoleEntry],
    ) -> HttpResponse:
        organisation = _organisation(ctx)
        site = organisation.site
        role_config = get_role_config(site.name)[role]
        name = _staff_member_name(user, email)
        before = role_entries_shown_to(ctx.request, before)
        after = (
            _entries_after(
                before,
                cast("User", ctx.request.user),
                role,
                role_config.display_name,
                cohorts,
            )
            if before
            else []
        )
        return render(
            ctx.request,
            self.template_name,
            {
                "step": "confirmation",
                "match": user,
                "staff_member_name": name,
                "creates_account": user is None,
                "first_name": names[0],
                "last_name": names[1],
                "action_url": self.get_action_url(ctx),
                "person": self._fixed_person(ctx),
                "email": email,
                "role": role,
                "cohort_ids": [str(cohort.pk) for cohort in chosen],
                "already_held": join_prose([cohort.name for cohort in already_held]),
                "display_name": role_config.display_name,
                "description": role_config.description,
                "scope": (
                    ORGANISATION_SCOPE
                    if role in ORGANISATION_ROLES
                    else join_prose([cohort.name for cohort in cohorts])
                ),
                "current_entries": before,
                "after_entries": after,
                "staff_member_state": staff_member_state(user, organisation),
            },
        )

    def _perform(
        self,
        ctx: PanelContext,
        user: User | None,
        email: str,
        role: str,
        targets: list[Organisation | Cohort],
        names: tuple[str, str],
    ) -> HttpResponse:
        organisation = _organisation(ctx)
        name = _staff_member_name(user, email)
        try:
            with transaction.atomic():
                user, created = match_or_create_user(organisation.site, email, *names)
                if role:
                    for target in targets:
                        assign_role(cast("User", ctx.request.user), user, role, target)
                else:
                    add_staff_member(cast("User", ctx.request.user), user, organisation)
                if created:
                    send_account_setup_email(user, organisation.name)
        except RoleChangeRefused as refused:
            return role_refusal_response(ctx, self, refused, name)
        except EmailInUseOnAnotherSite:
            return self._other_site_response(ctx)
        return staff_member_changed_response(user, ctx)


class StaffRowMixin(PanelAction):
    """An action on one staff member, named by the `user` parameter and read
    through staff_of, so a missing, malformed or non-staff value is a 404."""

    row_param = "user"

    def get_row_queryset(self, ctx: PanelContext) -> QuerySet[User]:
        return staff_of(_organisation(ctx))

    def _staff_member(self, ctx: PanelContext) -> User:
        return cast(User, self.get_row_object(ctx))


class AddRoleAction(StaffRowMixin, AddStaffMemberAction):
    """Gives one staff member another role, from their row. The person is
    fixed by the `user` parameter, so the dialog opens at the role step and
    the posted email is never read."""

    label = "Add role"
    action_name = "add_role"
    variant = "secondary"
    renders_in_footer = False
    offers_no_role = False

    def has_permission(self, ctx: PanelContext) -> bool:
        return has_grantable_roles(ctx)

    def _dialog_title(self, ctx: PanelContext) -> str:
        return f"Add a role for {self._staff_member(ctx).display_name}"

    def _fixed_person(self, ctx: PanelContext) -> User | None:
        return self._staff_member(ctx)

    def _posted(self, ctx: PanelContext) -> QueryDict:
        posted = ctx.request.POST.copy()
        posted["email"] = self._staff_member(ctx).email
        return posted

    def _match(self, ctx: PanelContext, email: str) -> User:
        return self._staff_member(ctx)

    def get_context_data(self, ctx: PanelContext) -> dict[str, object]:
        person = self._staff_member(ctx)
        form = AddStaffMemberForm(
            None,
            roles=[(g.role, g.role) for g in self._grantable(ctx)],
            cohorts=self._cohort_choices(ctx),
        )
        form.fields["email"].initial = person.email
        return self._role_step_context(ctx, person, form)

    def handle_submit(self, ctx: PanelContext) -> HttpResponse:
        if not self._grantable(ctx):
            return denied_response(ctx, self)
        return self._submit(ctx)


class AddStaffMemberToCohortAction(AddStaffMemberAction):
    """Add a staff member on a cohort's page, with the cohort fixed. Rendered by
    the Settings panel beside its Staff heading, not in the footer."""

    capability = ASSIGN_COHORT_VIEWER
    renders_in_footer = False
    offerable_roles = ("cohort_admin", "cohort_viewer")
    offers_no_role = False

    def permission_object(self, ctx: PanelContext) -> Model | None:
        return ctx.instance

    def is_offered(self, ctx: PanelContext) -> bool:
        # Someone who may add anyone needs nobody to pick from: they can type
        # an email address.
        return super().is_offered(ctx) and (
            self._may_add_anyone(ctx)
            or pickable_staff(
                cast("User", ctx.request.user), _organisation(ctx)
            ).exists()
        )

    def _grantable(self, ctx: PanelContext) -> list[GrantableRole]:
        cohort = cast(Cohort, ctx.instance)
        return [
            grantable
            for grantable in grantable_roles_for(ctx.request)
            if grantable.cohorts is not None and cohort in grantable.cohorts
        ]

    def _preset(self, ctx: PanelContext) -> Cohort | None:
        return cast(Cohort, ctx.instance)


class CohortRoleAction(StaffRowMixin, ModalPanelAction):
    """An action on one person's one cohort role on this cohort, named by the
    `user` and `role` parameters. The assignment is re-read on every request;
    one that is gone or inactive is a 404 that the action route answers with
    its unavailable fragment."""

    variant = "secondary"
    renders_in_footer = False

    def permission_object(self, ctx: PanelContext) -> Model | None:
        return ctx.instance

    def has_permission(self, ctx: PanelContext) -> bool:
        return ctx.instance is not None and bool(self._grantable(ctx))

    def _grantable(self, ctx: PanelContext) -> set[str]:
        return roles_grantable_on(ctx.request, cast(Cohort, ctx.instance))

    def _assignment(self, ctx: PanelContext) -> ObjectRoleAssignment:
        cohort = cast(Cohort, ctx.instance)
        user = self._staff_member(ctx)
        role = _action_params(ctx.request).get("role", "")
        if role_target(role) != "cohort" or role not in STAFF_ROLES:
            raise Http404("Not a cohort role")
        return get_object_or_404(
            _active_role_assignments(Cohort, frozenset({role})).select_related("user"),
            user=user,
            object_id=str(cohort.pk),
        )


class ChangeRoleAction(CohortRoleAction):
    """Swaps one cohort role of a staff member on this cohort for another,
    after a confirm step. Both roles are checked before anything is written,
    so a refusal leaves the original role active."""

    label = "Change role"
    action_name = "change_role"
    template_name = "educator_interface/modal/change_role.html"

    def _cohort_roles(self, ctx: PanelContext) -> list[str]:
        """The cohort roles among the staff roles, in display order."""
        return [role for role in STAFF_ROLES if role_target(role) == "cohort"]

    def _role_cards(self, ctx: PanelContext, held: str) -> list[dict[str, object]]:
        config = get_role_config(cast(Cohort, ctx.instance).site.name)
        grantable = self._grantable(ctx)
        return [
            {
                "value": role,
                "display_name": config[role].display_name,
                "description": config[role].description,
                "checked": role == held,
            }
            for role in self._cohort_roles(ctx)
            if role in grantable
        ]

    def _form(
        self, ctx: PanelContext, data: Mapping[str, str] | None
    ) -> ChangeRoleForm:
        config = get_role_config(cast(Cohort, ctx.instance).site.name)
        return ChangeRoleForm(
            data,
            roles=[
                (role, config[role].display_name) for role in self._cohort_roles(ctx)
            ],
        )

    def _dialog_context(
        self, ctx: PanelContext, assignment: ObjectRoleAssignment
    ) -> dict[str, object]:
        context = super().get_context_data(ctx)
        context.update(
            {
                "step": "form",
                "staff_member": assignment.user,
                "role": assignment.role,
                "cohort": ctx.instance,
                "role_cards": self._role_cards(ctx, assignment.role),
                "action_url": self.get_action_url(ctx),
            }
        )
        return context

    def get_context_data(self, ctx: PanelContext) -> dict[str, object]:
        return self._dialog_context(ctx, self._assignment(ctx))

    def handle_submit(self, ctx: PanelContext) -> HttpResponse:
        assignment = self._assignment(ctx)
        cohort = cast(Cohort, ctx.instance)
        user = assignment.user
        form = self._form(ctx, ctx.request.POST)
        if not form.is_valid():
            return render(
                ctx.request,
                self.template_name,
                {**self._dialog_context(ctx, assignment), "form": form},
                status=422,
            )
        new_role = str(form.cleaned_data["new_role"])
        config = get_role_config(cohort.site.name)
        if new_role == assignment.role:
            return _refused(
                ctx,
                f"{user.display_name} already holds "
                f"{config[new_role].display_name} on {cohort}.",
            )
        grantable = self._grantable(ctx)
        if assignment.role not in grantable or new_role not in grantable:
            return denied_response(ctx, self)
        if ctx.request.POST.get("confirmed") != "1":
            return render(
                ctx.request,
                self.template_name,
                {
                    **self._dialog_context(ctx, assignment),
                    "step": "confirmation",
                    "new_role": new_role,
                    "new_role_display_name": config[new_role].display_name,
                },
            )
        grantor = cast("User", ctx.request.user)
        try:
            # The new role first: a grantor changing their own role still
            # holds the old one while the new one is checked.
            with transaction.atomic():
                assign_role(grantor, user, new_role, cohort)
                deactivate_role(grantor, user, assignment.role, cohort)
        except RoleChangeRefused as refused:
            return role_refusal_response(ctx, self, refused, user.display_name)
        return staff_member_changed_response(user, ctx)


class RemoveStaffFromCohortAction(EducatorReasonMixin, CohortRoleAction):
    """Takes one cohort role off a staff member on this cohort alone."""

    label = "Remove from cohort"
    action_name = "remove_staff_from_cohort"
    template_name = (
        "educator_interface/modal/remove_staff_from_cohort_confirmation.html"
    )

    def get_context_data(self, ctx: PanelContext) -> dict[str, object]:
        assignment = self._assignment(ctx)
        cohort = cast(Cohort, ctx.instance)
        context = super().get_context_data(ctx)
        context.update(
            {
                "staff_member": assignment.user,
                "role": assignment.role,
                "role_display_name": get_role_config(cohort.site.name)[
                    assignment.role
                ].display_name,
                "cohort": cohort,
                "confirm_url": self.get_action_url(ctx),
            }
        )
        return context

    def handle_confirmed_submit(self, ctx: PanelContext) -> HttpResponse:
        assignment = self._assignment(ctx)
        if assignment.role not in self._grantable(ctx):
            return denied_response(ctx, self)
        user = assignment.user
        try:
            with transaction.atomic():
                deactivate_role(
                    cast("User", ctx.request.user),
                    user,
                    assignment.role,
                    cast(Cohort, ctx.instance),
                    reason=ctx.reason,
                )
        except RoleChangeRefused as refused:
            return role_refusal_response(ctx, self, refused, user.display_name)
        return staff_member_changed_response(user, ctx)


class StaffRoleAction(StaffRowMixin, ModalPanelAction):
    """An action on one role entry of one staff member, named by the `user` and
    `role` parameters. Renders per entry, never in the header. The target
    is re-read on every request through staff_of, so a staff member who has
    since lost every role, or a role no longer held, is a 404 that the
    action route answers with its unavailable fragment."""

    variant = "secondary"
    renders_in_footer = False

    def has_permission(self, ctx: PanelContext) -> bool:
        return has_grantable_roles(ctx)

    def get_capability(self, ctx: PanelContext) -> str | None:
        role = _action_params(ctx.request).get("role", "")
        if role in STAFF_ROLES:
            return ASSIGN.format(role=role)
        return ASSIGN.format(role="cohort_viewer")

    def permission_object(self, ctx: PanelContext) -> Model | None:
        return _organisation(ctx)

    def _entries(self, ctx: PanelContext, user: User) -> list[RoleEntry]:
        """Every role `user` holds here, loaded once per request."""
        return current_role_entries(user, _organisation(ctx))

    def _reach(self, ctx: PanelContext, role: str) -> set[Cohort]:
        return role_reach(ctx.request, role)

    def _entry(self, ctx: PanelContext, entries: list[RoleEntry]) -> RoleEntry:
        """The entry the `role` parameter names, from `entries`."""
        role = _action_params(ctx.request).get("role", "")
        for entry in entries:
            if entry.role == role:
                return entry
        raise Http404("The staff member does not hold this role")

    def _readable(self, ctx: PanelContext, entry: RoleEntry) -> list[Cohort]:
        """The entry's cohorts the viewer may read: all of them for someone
        who may see staff roles, else the ones within their reach, which
        that cohort's own Staff list already shows them."""
        if may_see_staff_roles(ctx.request):
            return list(entry.cohorts)
        reach = self._reach(ctx, entry.role)
        return [cohort for cohort in entry.cohorts if cohort in reach]


class DeactivateRoleAction(EducatorReasonMixin, ConfirmAction, StaffRoleAction):
    """Takes one role entry off a staff member: on the organisation, or on every
    cohort of the entry the grantor can act on. A cohort outside the
    grantor's reach keeps the role, and the dialog says so. An entry with no
    cohort in reach has no trigger, and is a 404 dialog and a 403 submit."""

    label = "Deactivate role"
    action_name = "deactivate_role"
    confirm_label = "Deactivate"
    loading_text = "Deactivating…"
    template_name = "educator_interface/modal/deactivate_role_confirmation.html"

    def _split(
        self, ctx: PanelContext, entry: RoleEntry
    ) -> tuple[list[Cohort], list[Cohort]]:
        """The entry's cohorts the grantor may act on, then the ones that stay."""
        reach = self._reach(ctx, entry.role)
        return (
            [cohort for cohort in entry.cohorts if cohort in reach],
            [cohort for cohort in entry.cohorts if cohort not in reach],
        )

    def _kept(
        self,
        ctx: PanelContext,
        user: User,
        removed: RoleEntry,
        entries: list[RoleEntry],
        possessive: str,
    ) -> str:
        """What the person keeps, in prose; `possessive` is "their", or "your"
        when the viewer is removing their own role."""
        organisation = _organisation(ctx)
        kept = [
            f"{entry.display_name} on {entry.scope}"
            for entry in entries
            if entry.role != removed.role
        ]
        has_learner = Learner.objects.filter(
            organisation=organisation, user=user, is_active=True
        ).exists()
        parts = [f"{possessive} account", *kept]
        if has_learner:
            parts.append(f"{possessive} learner access in this organisation")
        return join_prose(parts)

    def get_hidden_fields(self, ctx: PanelContext) -> dict[str, str]:
        params = _action_params(ctx.request)
        return {"user": params.get("user", ""), "role": params.get("role", "")}

    def get_confirm_context(self, ctx: PanelContext) -> dict[str, object]:
        organisation = _organisation(ctx)
        site = organisation.site
        grantor = cast("User", ctx.request.user)
        user = self._staff_member(ctx)
        entries = self._entries(ctx, user)
        entry = self._entry(ctx, entries)
        # A role the viewer cannot act on answers as one the person does not
        # hold, so the response never confirms who holds it.
        if entry.role not in actionable_roles(ctx.request, [entry]):
            raise Http404("This role is not the grantor's to deactivate")
        removed, staying = self._split(ctx, entry)
        shows_roles = may_see_staff_roles(ctx.request)
        is_self = user.pk == grantor.pk
        shown_entries = role_entries_shown_to(ctx.request, entries)
        description = get_role_config(site.name)[entry.role].description.rstrip(".")
        return {
            "staff_member": user,
            "entry": entry,
            "description": description,
            "full_scope": (
                "the whole organisation"
                if entry.target == "organisation"
                else join_prose([cohort.name for cohort in removed])
            ),
            "stays": (
                join_prose([cohort.name for cohort in staying]) if shows_roles else ""
            ),
            "keeps": self._kept(
                ctx, user, entry, shown_entries, "your" if is_self else "their"
            ),
            "is_self": is_self,
            # Nothing else left here: the person stays on the staff list
            # with no roles, which a site-level admin's dialog says.
            "last_role": not staying
            and all(other.role == entry.role for other in shown_entries),
            "last_organisation_admin": entry.role == "organisation_admin"
            and is_last_organisation_admin(organisation, user),
            "grantor_is_site_level": is_site_level_admin(grantor, site),
            "target_is_site_level": shows_roles and is_site_level_admin(user, site),
        }

    def handle_confirmed_submit(self, ctx: PanelContext) -> HttpResponse:
        organisation = _organisation(ctx)
        user = self._staff_member(ctx)
        entry = self._entry(ctx, self._entries(ctx, user))
        removed, _ = self._split(ctx, entry)
        targets: list[Organisation | Cohort] = (
            [organisation] if entry.target == "organisation" else [*removed]
        )
        if not targets:
            return denied_response(ctx, self)
        try:
            with transaction.atomic():
                for target in targets:
                    deactivate_role(
                        cast("User", ctx.request.user),
                        user,
                        entry.role,
                        target,
                        reason=ctx.reason,
                    )
        except RoleChangeRefused as refused:
            return role_refusal_response(ctx, self, refused, user.display_name)
        return staff_member_changed_response(user, ctx)


class CohortChange(NamedTuple):
    added: list[Cohort]
    removed: list[Cohort]
    untouched: list[Cohort]


class ChangeCohortsAction(StaffRoleAction):
    """Adds and removes the cohorts of one cohort-role entry in a single
    transaction, after a confirmation that names what is gained and lost. An
    entry with no cohort in the grantor's reach has no trigger and is a 404:
    giving that role on another cohort is Add role's job."""

    label = "Change cohorts"
    action_name = "change_cohorts"
    template_name = "educator_interface/modal/change_cohorts.html"

    def is_offered(self, ctx: PanelContext) -> bool:
        return any(g.cohorts for g in grantable_roles_for(ctx.request))

    def _offered(self, ctx: PanelContext, role: str) -> tuple[Cohort, ...]:
        for grantable in grantable_roles_for(ctx.request):
            if grantable.role == role and grantable.cohorts is not None:
                return grantable.cohorts
        raise Http404("This role is not given on cohorts here")

    def _entry(self, ctx: PanelContext, entries: list[RoleEntry]) -> RoleEntry:
        entry = super()._entry(ctx, entries)
        reach = self._reach(ctx, entry.role)
        if not any(cohort in reach for cohort in entry.cohorts):
            raise Http404("No cohort of this role is within the grantor's reach")
        return entry

    def _plan(
        self, ctx: PanelContext, entry: RoleEntry, chosen: list[Cohort]
    ) -> CohortChange:
        """Cohorts the person holds outside the offered set, and inactive
        ones they hold, are untouched."""
        offered = self._offered(ctx, entry.role)
        held = list(entry.cohorts)
        return CohortChange(
            added=[cohort for cohort in chosen if cohort not in held],
            removed=[
                cohort for cohort in held if cohort in offered and cohort not in chosen
            ],
            untouched=[cohort for cohort in held if cohort not in offered],
        )

    def _dialog(
        self, ctx: PanelContext, user: User, entry: RoleEntry
    ) -> dict[str, object]:
        offered = self._offered(ctx, entry.role)
        held = set(entry.cohorts)
        return {
            "staff_member": user,
            "entry": entry,
            "action_url": self.get_action_url(ctx),
            "cohort_rows": [
                {
                    "pk": str(cohort.pk),
                    "name": cohort.name,
                    "checked": cohort in held,
                }
                for cohort in offered
            ],
            "read_only": [
                f"{cohort.name} (inactive)"
                if not cohort.is_active
                else f"{cohort.name} (outside the cohorts you can give)"
                for cohort in self._readable(ctx, entry)
                if cohort not in offered
            ],
        }

    def get_context_data(self, ctx: PanelContext) -> dict[str, object]:
        user = self._staff_member(ctx)
        entry = self._entry(ctx, self._entries(ctx, user))
        return {"step": "form", **self._dialog(ctx, user, entry)}

    def _chosen(self, ctx: PanelContext, entry: RoleEntry) -> list[Cohort]:
        form = CohortSetForm(ctx.request.POST)
        cohorts = cast(forms.ModelMultipleChoiceField, form.fields["cohorts"])
        cohorts.queryset = Cohort.objects.filter(organisation=_organisation(ctx))
        if not form.is_valid():
            raise Http404("No such cohort")
        chosen = sorted(form.cleaned_data["cohorts"], key=lambda c: c.name)
        offered = self._offered(ctx, entry.role)
        if not all(cohort in offered for cohort in chosen):
            raise Http404("This cohort is no longer offered")
        return chosen

    def handle_submit(self, ctx: PanelContext) -> HttpResponse:
        user = self._staff_member(ctx)
        grantor = cast("User", ctx.request.user)
        entry = self._entry(ctx, self._entries(ctx, user))
        chosen = self._chosen(ctx, entry)
        plan = self._plan(ctx, entry, chosen)
        if not plan.added and not plan.removed:
            return _refused(ctx, "Nothing changed. Tick or untick a cohort first.")
        if ctx.request.POST.get("confirmed") != "1":
            return self._confirmation(ctx, user, entry, chosen, plan)
        try:
            with transaction.atomic():
                for cohort in plan.added:
                    assign_role(grantor, user, entry.role, cohort)
                for cohort in plan.removed:
                    deactivate_role(grantor, user, entry.role, cohort)
        except RoleChangeRefused as refused:
            return role_refusal_response(ctx, self, refused, user.display_name)
        return staff_member_changed_response(user, ctx)

    def _confirmation(
        self,
        ctx: PanelContext,
        user: User,
        entry: RoleEntry,
        chosen: list[Cohort],
        plan: CohortChange,
    ) -> HttpResponse:
        organisation = _organisation(ctx)
        return render(
            ctx.request,
            self.template_name,
            {
                "step": "confirmation",
                "staff_member": user,
                "entry": entry,
                "action_url": self.get_action_url(ctx),
                "cohort_ids": [str(cohort.pk) for cohort in chosen],
                "added": join_prose([cohort.name for cohort in plan.added]),
                "removed": join_prose([cohort.name for cohort in plan.removed]),
                "removes_role": not plan.added
                and len(plan.removed) == len(self._readable(ctx, entry)),
                "staff_member_state": staff_member_state(user, organisation),
            },
        )


class StaffMemberStateAction(StaffRowMixin, ConfirmAction):
    """Flips one staff member's StaffMember row, named by the `user`
    parameter, after confirmation. Renders per row, never in the header."""

    renders_in_footer = False
    capability = CHANGE_STAFF_MEMBER

    def permission_object(self, ctx: PanelContext) -> Model | None:
        return _organisation(ctx)

    def _row(self, user: User, organisation: Organisation) -> StaffMember | None:
        return StaffMember.objects.filter(user=user, organisation=organisation).first()


class DeactivateStaffMemberAction(EducatorReasonMixin, StaffMemberStateAction):
    label = "Deactivate staff member"
    action_name = "deactivate"
    confirm_label = "Deactivate"
    loading_text = "Deactivating…"
    template_name = "educator_interface/modal/deactivate_staff_member_confirmation.html"

    def get_confirm_context(self, ctx: PanelContext) -> dict[str, object]:
        organisation = _organisation(ctx)
        user = self._staff_member(ctx)
        return {
            "staff_member": user,
            "organisation": organisation,
            "last_organisation_admin": is_last_organisation_admin(organisation, user),
            "grantor_is_site_level": is_site_level_admin(
                cast("User", ctx.request.user), organisation.site
            ),
        }

    def handle_confirmed_submit(self, ctx: PanelContext) -> HttpResponse:
        organisation = _organisation(ctx)
        user = self._staff_member(ctx)
        row = self._row(user, organisation)
        if row is None or not row.is_active:
            raise Http404("The staff member is already inactive")
        try:
            set_staff_member_active(
                cast("User", ctx.request.user),
                row,
                False,
                reason=ctx.reason,
            )
        except RoleChangeRefused as refused:
            return role_refusal_response(ctx, self, refused, user.display_name)
        return staff_member_changed_response(user, ctx)


class ReactivateStaffMemberAction(StaffMemberStateAction):
    label = "Reactivate staff member"
    action_name = "reactivate"
    confirm_label = "Reactivate"
    loading_text = "Reactivating…"
    template_name = "educator_interface/modal/reactivate_staff_member_confirmation.html"

    def get_confirm_context(self, ctx: PanelContext) -> dict[str, object]:
        user = self._staff_member(ctx)
        entries = current_role_entries(user, _organisation(ctx))
        return {
            "staff_member": user,
            "roles": join_prose(
                [f"{entry.display_name} on {entry.scope}" for entry in entries]
            ),
        }

    def handle_submit(self, ctx: PanelContext) -> HttpResponse:
        organisation = _organisation(ctx)
        user = self._staff_member(ctx)
        row = self._row(user, organisation)
        if row is not None and row.is_active:
            raise Http404("The staff member is already active")
        try:
            with transaction.atomic():
                # A staff member with no row has no access, so the row is created
                # inactive and reactivated below rather than created active:
                # set_staff_member_active is the one path that checks
                # the actor's capability, locks the row and writes the entry,
                # and it only writes for a real change.
                row = row or ensure_staff_member(user, organisation, is_active=False)
                set_staff_member_active(cast("User", ctx.request.user), row, True)
        except RoleChangeRefused as refused:
            return role_refusal_response(ctx, self, refused, user.display_name)
        return staff_member_changed_response(user, ctx)
