"""The actions on the Personal details page, each saving part of the signed-in
user's own account."""

from __future__ import annotations

from typing import cast

from allauth.account import app_settings as allauth_account_settings
from allauth.account.forms import AddEmailForm, ChangePasswordForm, SetPasswordForm
from allauth.account.internal import flows
from allauth.account.internal.flows.email_verification import (
    send_verification_email_to_address,
)
from allauth.account.models import EmailAddress
from allauth.core import ratelimit
from allauth.utils import get_form_class

from django import forms
from django.contrib import messages
from django.db.models import QuerySet
from django.http import HttpResponse
from django.template.loader import render_to_string

from freedom_ls.accounts.forms import (
    ProfilePictureForm,
    UserForm,
    remove_profile_picture,
)
from freedom_ls.accounts.models import User
from freedom_ls.accounts.utils import get_own_user
from freedom_ls.panel_framework.actions import (
    ConfirmAction,
    EditAction,
    FormPanelAction,
    PanelAction,
)
from freedom_ls.panel_framework.context import PanelContext
from freedom_ls.panel_framework.events import build_hx_trigger

ACCOUNT_CHANGED = "accountChanged"
EMAIL_ADDRESSES_CHANGED = "accountEmailAddressesChanged"
PASSWORD_CHANGED = "accountPasswordChanged"  # noqa: S105  # pragma: allowlist secret (an event name)

# Names the section config grants on the user's own row. They are not Django
# permissions: a learner holds none of those on their own user.
CHANGE_OWN_NAME = "change_own_name"
CHANGE_OWN_PROFILE_PICTURE = "change_own_profile_picture"
REMOVE_OWN_PROFILE_PICTURE = "remove_own_profile_picture"
CHANGE_OWN_EMAIL_ADDRESSES = "change_own_email_addresses"
CHANGE_OWN_PASSWORD = "change_own_password"  # noqa: S105  # pragma: allowlist secret (a capability name)
ACCOUNT_CAPABILITIES: frozenset[str] = frozenset(
    {
        CHANGE_OWN_NAME,
        CHANGE_OWN_PROFILE_PICTURE,
        REMOVE_OWN_PROFILE_PICTURE,
        CHANGE_OWN_EMAIL_ADDRESSES,
        CHANGE_OWN_PASSWORD,
    }
)


def account_saved_response(
    ctx: PanelContext,
    action: PanelAction,
    html: str,
    message: str | None,
    *,
    close_modal: bool = False,
    swap_picture_preview: bool = False,
    swap_nothing: bool = False,
) -> HttpResponse:
    """200, not EditAction's 204: htmx drops a 204's body, and this body
    carries the re-rendered form. The queued message becomes the toast
    through HtmxMessagesMiddleware. The header avatar rides along out of band,
    read afresh because the removal clears the picture with .update(), which
    leaves ctx.instance holding the old one. `swap_picture_preview` sends the
    Profile picture panel's preview the same way, for a save that changes it
    without refreshing that panel. `message` is None when the allauth flow
    the action called has queued its own. `swap_nothing` is for a response
    with no fragment to swap: the dialog closes on the closeModal event, but
    any swap that targets its body reopens it, and a 204 would drop the
    toast, so a swap of nothing is retargeted at the body and only the
    out-of-band content lands."""
    if message is not None:
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
    if swap_nothing:
        response["HX-Retarget"] = "body"
        response["HX-Reswap"] = "none"
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
        return account_saved_response(
            ctx,
            self,
            "",
            "Profile picture removed",
            close_modal=True,
            swap_nothing=True,
        )


def sentence_case_labels(form: forms.BaseForm) -> None:
    """allauth titles its labels and placeholders ("New Password (again)");
    the account area writes them in sentence case."""
    for field in form.fields.values():
        if field.label:
            field.label = sentence_case(str(field.label))
        placeholder = field.widget.attrs.get("placeholder")
        if placeholder:
            field.widget.attrs["placeholder"] = sentence_case(str(placeholder))


def sentence_case(text: str) -> str:
    return text[:1].upper() + text[1:].lower()


def own_email_addresses(ctx: PanelContext) -> QuerySet[EmailAddress]:
    """The signed-in user's own addresses, the only rows the email actions
    may act on."""
    user = cast(User, ctx.instance)
    addresses: QuerySet[EmailAddress] = EmailAddress.objects.filter(
        user_id=user.pk
    ).order_by("email")
    return addresses


class OwnEmailAddressAction(PanelAction):
    """An action on one of the user's own email addresses, named by its pk in
    the `email` parameter and rendered on that address's row. allauth's
    manage_email rate limit applies to every submit, as on its own page, and
    the toast is the message allauth's flow queues."""

    renders_in_footer = False
    capability = CHANGE_OWN_EMAIL_ADDRESSES
    success_events = (EMAIL_ADDRESSES_CHANGED,)
    row_param = "email"

    def get_row_queryset(self, ctx: PanelContext) -> QuerySet[EmailAddress]:
        return own_email_addresses(ctx)

    def email_address(self, ctx: PanelContext) -> EmailAddress:
        return cast(EmailAddress, self.get_row_object(ctx))

    def handle_submit(self, ctx: PanelContext) -> HttpResponse:
        email_address = self.email_address(ctx)
        limited: HttpResponse | None = ratelimit.consume_or_429(
            ctx.request, action="manage_email"
        )
        if limited is not None:
            return limited
        self.run(ctx, email_address)
        return account_saved_response(
            ctx, self, "", None, close_modal=True, swap_nothing=True
        )

    def run(self, ctx: PanelContext, email_address: EmailAddress) -> None:
        raise NotImplementedError


class MakePrimaryEmailAction(OwnEmailAddressAction):
    label = "Make primary"
    action_name = "make_primary_email"

    def run(self, ctx: PanelContext, email_address: EmailAddress) -> None:
        # Refused (an unverified address while a verified one exists) with
        # allauth's own error message.
        flows.manage_email.mark_as_primary(ctx.request, email_address)


class ResendVerificationAction(OwnEmailAddressAction):
    label = "Resend verification"
    action_name = "resend_email_verification"

    def run(self, ctx: PanelContext, email_address: EmailAddress) -> None:
        if email_address.verified:
            messages.info(ctx.request, f"{email_address.email} is already verified.")
            return
        if not send_verification_email_to_address(ctx.request, email_address):
            messages.error(
                ctx.request,
                "A verification email was sent recently. "
                "Wait a few minutes before asking for another.",
            )


class RemoveEmailAction(OwnEmailAddressAction, ConfirmAction):
    label = "Remove"
    action_name = "remove_email"
    confirm_label = "Remove"
    confirm_variant = "error"
    loading_text = "Removing…"
    template_name = "accounts/modal/remove_email_confirmation.html"

    def get_title(self, ctx: PanelContext) -> str:
        return f"Remove {self.email_address(ctx).email}?"

    def get_confirm_context(self, ctx: PanelContext) -> dict[str, object]:
        return {"email_address": self.email_address(ctx)}

    def run(self, ctx: PanelContext, email_address: EmailAddress) -> None:
        # The primary address is refused, with allauth's own error message.
        flows.manage_email.delete_email(ctx.request, email_address)


class AddEmailAction(FormPanelAction):
    """Adds an address to the user's account through allauth's form and
    flow, which sends the verification email and queues the toast."""

    label = "Add email"
    action_name = "add_email"
    variant = "primary"
    capability = CHANGE_OWN_EMAIL_ADDRESSES
    success_events = (EMAIL_ADDRESSES_CHANGED,)
    form_title = "Add an email address"
    submit_buttons = [{"label": "Add email", "variant": "primary"}]

    def __init__(self) -> None:
        self.form_class = get_form_class(
            allauth_account_settings.FORMS, "add_email", AddEmailForm
        )

    def is_offered(self, ctx: PanelContext) -> bool:
        return bool(EmailAddress.objects.can_add_email(ctx.instance))

    def get_form_kwargs(self, ctx: PanelContext) -> dict[str, object]:
        return {**super().get_form_kwargs(ctx), "user": ctx.request.user}

    def get_form(self, ctx: PanelContext) -> forms.BaseForm:
        form = super().get_form(ctx)
        sentence_case_labels(form)
        return form

    def handle_submit(self, ctx: PanelContext) -> HttpResponse:
        limited: HttpResponse | None = ratelimit.consume_or_429(
            ctx.request, action="manage_email"
        )
        if limited is not None:
            return limited
        return super().handle_submit(ctx)

    def form_valid(self, ctx: PanelContext, form: forms.BaseForm) -> HttpResponse:
        flows.manage_email.add_email(ctx.request, form)
        return account_saved_response(
            ctx, self, "", None, close_modal=True, swap_nothing=True
        )


class ChangePasswordAction(FormPanelAction):
    """Changes the user's password through allauth's form and flow, inline on
    the Password panel, or sets one for a user who has none. allauth's
    change_password rate limit applies, its flow keeps the session signed in
    and queues the toast, and the panel's refresh shows an empty form."""

    action_name = "change_password"
    renders_in_footer = False
    autofocus_first_field = False
    capability = CHANGE_OWN_PASSWORD
    success_events = (PASSWORD_CHANGED,)
    template_name = "accounts/partials/password_form.html"

    def __init__(self, user: User) -> None:
        self.has_password = user.has_usable_password()
        if self.has_password:
            self.label = "Change password"
            self.form_class = get_form_class(
                allauth_account_settings.FORMS, "change_password", ChangePasswordForm
            )
        else:
            self.label = "Set password"
            self.form_class = get_form_class(
                allauth_account_settings.FORMS, "set_password", SetPasswordForm
            )
        self.form_title = self.label

    def get_form_kwargs(self, ctx: PanelContext) -> dict[str, object]:
        return {**super().get_form_kwargs(ctx), "user": ctx.request.user}

    def get_form(self, ctx: PanelContext) -> forms.BaseForm:
        form = super().get_form(ctx)
        sentence_case_labels(form)
        return form

    def get_unbound_form(self, ctx: PanelContext) -> forms.BaseForm:
        form = super().get_unbound_form(ctx)
        sentence_case_labels(form)
        return form

    def handle_submit(self, ctx: PanelContext) -> HttpResponse:
        limited: HttpResponse | None = ratelimit.consume_or_429(
            ctx.request, action="change_password"
        )
        if limited is not None:
            return limited
        return super().handle_submit(ctx)

    def form_valid(self, ctx: PanelContext, form: forms.BaseForm) -> HttpResponse:
        user = cast(User, ctx.request.user)
        cast(ChangePasswordForm, form).save()
        if self.has_password:
            flows.password_change.finalize_password_change(ctx.request, user)
        else:
            flows.password_change.finalize_password_set(ctx.request, user)
        return account_saved_response(ctx, self, "", None, swap_nothing=True)
