"""The actions on the Personal details page, each saving part of the signed-in
user's own account."""

from __future__ import annotations

from typing import cast

from django import forms
from django.contrib import messages
from django.http import HttpResponse
from django.template.loader import render_to_string

from freedom_ls.accounts.forms import (
    ProfilePictureForm,
    UserForm,
    remove_profile_picture,
)
from freedom_ls.accounts.models import User
from freedom_ls.accounts.utils import get_own_user
from freedom_ls.panel_framework.actions import ConfirmAction, EditAction, PanelAction
from freedom_ls.panel_framework.context import PanelContext
from freedom_ls.panel_framework.events import build_hx_trigger

ACCOUNT_CHANGED = "accountChanged"

# Names the section config grants on the user's own row. They are not Django
# permissions: a learner holds none of those on their own user.
CHANGE_OWN_NAME = "change_own_name"
CHANGE_OWN_PROFILE_PICTURE = "change_own_profile_picture"
REMOVE_OWN_PROFILE_PICTURE = "remove_own_profile_picture"
ACCOUNT_CAPABILITIES: frozenset[str] = frozenset(
    {CHANGE_OWN_NAME, CHANGE_OWN_PROFILE_PICTURE, REMOVE_OWN_PROFILE_PICTURE}
)


def account_saved_response(
    ctx: PanelContext,
    action: PanelAction,
    html: str,
    message: str,
    *,
    close_modal: bool = False,
    swap_picture_preview: bool = False,
) -> HttpResponse:
    """200, not EditAction's 204: htmx drops a 204's body, and this body
    carries the re-rendered form. The queued message becomes the toast
    through HtmxMessagesMiddleware. The header avatar rides along out of band,
    read afresh because the removal clears the picture with .update(), which
    leaves ctx.instance holding the old one. `swap_picture_preview` sends the
    Profile picture panel's preview the same way, for a save that changes it
    without refreshing that panel."""
    messages.success(ctx.request, message)
    user = get_own_user(ctx.request)
    out_of_band = render_to_string(
        "partials/header_avatar.html", {"avatar_user": user, "oob": True}
    )
    if swap_picture_preview:
        out_of_band += render_to_string(
            "accounts/partials/profile_picture_preview.html",
            {"stored_user": user, "oob": True},
        )
    response = HttpResponse(html + out_of_band)
    response["HX-Trigger"] = build_hx_trigger(
        action.get_success_events(ctx.instance), close_modal=close_modal
    )
    return response


class AccountEditAction(EditAction):
    """Saves part of the signed-in user's own account from a form in a panel."""

    renders_in_footer = False
    autofocus_first_field = False
    success_message: str
    #: On for a save that changes the picture preview without firing the
    #: Profile picture panel's refresh event.
    swaps_picture_preview: bool = False

    def __init__(
        self,
        user: User,
        form_class: type[forms.ModelForm],
        form_title: str,
        success_events: tuple[str, ...],
    ) -> None:
        super().__init__(
            form_class=form_class,
            form_title=form_title,
            instance=user,
            success_events=success_events,
        )

    def get_capability(self, ctx: PanelContext) -> str | None:
        # Named explicitly: EditAction falls back to the model's change
        # permission, which a learner does not hold.
        return self.capability

    def form_valid(self, ctx: PanelContext, form: forms.BaseForm) -> HttpResponse:
        cast(forms.ModelForm, form).save()
        html = render_to_string(
            self.get_fragment_template_name(),
            self.get_fragment_context(ctx, self.get_unbound_form(ctx)),
            request=ctx.request,
        )
        return account_saved_response(
            ctx,
            self,
            html,
            self.success_message,
            swap_picture_preview=self.swaps_picture_preview,
        )


class EditNameAction(AccountEditAction):
    label = "Edit name"
    action_name = "edit_name"
    capability = CHANGE_OWN_NAME
    template_name = "accounts/partials/name_form.html"
    success_message = "Name saved"
    # The preview shows the name's initials, but the panel's refresh event
    # would re-render its upload form and drop a file the user has chosen.
    swaps_picture_preview = True

    def __init__(self, user: User) -> None:
        super().__init__(
            user, form_class=UserForm, form_title="Name", success_events=()
        )


class UploadProfilePictureAction(AccountEditAction):
    label = "Upload picture"
    action_name = "upload_profile_picture"
    capability = CHANGE_OWN_PROFILE_PICTURE
    template_name = "accounts/partials/profile_picture_form.html"
    success_message = "Profile picture saved"

    def __init__(self, user: User) -> None:
        super().__init__(
            user,
            form_class=ProfilePictureForm,
            form_title="Profile picture",
            success_events=(ACCOUNT_CHANGED,),
        )


class RemoveProfilePictureAction(ConfirmAction):
    label = "Remove picture"
    action_name = "remove_profile_picture"
    capability = REMOVE_OWN_PROFILE_PICTURE
    success_events = (ACCOUNT_CHANGED,)
    confirm_label = "Remove"
    confirm_variant = "error"
    loading_text = "Removing…"
    template_name = "accounts/modal/remove_profile_picture_confirmation.html"

    def get_title(self, ctx: PanelContext) -> str:
        return "Remove your profile picture?"

    def is_offered(self, ctx: PanelContext) -> bool:
        return bool(cast(User, ctx.instance).profile_picture)

    def handle_submit(self, ctx: PanelContext) -> HttpResponse:
        remove_profile_picture(cast(User, ctx.instance))
        response = account_saved_response(
            ctx, self, "", "Profile picture removed", close_modal=True
        )
        # The dialog closes on the closeModal event, but any swap that targets
        # its body reopens it, and a 204 would drop the toast. Retargeting a
        # swap of nothing at the body lets only the out-of-band toast land.
        response["HX-Retarget"] = "body"
        response["HX-Reswap"] = "none"
        return response
