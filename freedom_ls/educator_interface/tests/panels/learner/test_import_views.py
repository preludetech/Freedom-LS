"""The learner import pages and the oversight thread paging view."""

from __future__ import annotations

import csv
import io
from collections.abc import Callable, Iterator
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import TYPE_CHECKING, cast
from urllib.parse import parse_qsl, urlsplit
from uuid import uuid4

import lxml.html
import pytest
import time_machine

from django.contrib.sites.models import Site
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.accounts.models import User
from freedom_ls.comms.factories import (
    MessageFactory,
)
from freedom_ls.comms.messaging import (
    encode_cursor,
)
from freedom_ls.comms.models import Message
from freedom_ls.educator_interface.learner_import import (
    PREVIEW_LABEL_TONES,
    create_learner_import,
    run_learner_import,
)
from freedom_ls.educator_interface.tests.helpers import (
    _get_document,
    _grant,
    _interface_url,
    _msg_conversation,
    _msg_educator,
    _msg_learner,
    _older_url,
    _open_conversation,
    _oversight_scene,
    _viewed_entries,
    messages_section,
)
from freedom_ls.learner_management.factories import (
    CohortFactory,
    CohortMembershipFactory,
    LearnerFactory,
)
from freedom_ls.learner_management.models import (
    Cohort,
    ImportLabel,
    ImportStatus,
    Learner,
    LearnerImport,
)
from freedom_ls.learner_management.queries import (
    ADD_COHORTMEMBERSHIP,
    ADD_LEARNER,
    VIEW_COHORT,
    VIEW_LEARNER,
    VIEW_ORGANISATION,
)
from freedom_ls.learner_management.role_assignment import assign_role
from freedom_ls.learner_management.tests.scenario_world import custom_role_config
from freedom_ls.organisations.factories import OrganisationFactory
from freedom_ls.organisations.models import Organisation
from freedom_ls.panel_framework.models import RunStatus
from freedom_ls.role_based_permissions.types import SCOPE_OBJECT, Role
from freedom_ls.role_based_permissions.utils import assign_object_role

if TYPE_CHECKING:
    pass


@pytest.mark.django_db
@messages_section
class TestOversight:
    @pytest.fixture
    def scene(self):
        return _oversight_scene()

    @pytest.fixture
    def long_scene(self, scene, settings):
        settings.MESSAGE_PAGE_SIZE = 3
        _, educator, _, conversation = scene
        base = timezone.now() - timedelta(days=3)
        messages = []
        for i in range(7):
            message = MessageFactory(
                conversation=conversation, sender=educator, body=f"m{i}"
            )
            Message.objects.filter(pk=message.pk).update(
                created_at=base + timedelta(minutes=i)
            )
            messages.append(Message.objects.get(pk=message.pk))
        return scene, messages

    def test_the_modal_control_points_at_the_oversight_endpoint(
        self, msg_client_for, long_scene
    ):
        (organisation, _, learner, conversation), _ = long_scene

        response = _open_conversation(
            msg_client_for(_msg_educator(organisation)), learner, conversation.pk
        )

        page = lxml.html.fromstring(response.content.decode())
        (button,) = page.xpath("//div[@id='read-only-thread-older']//button")
        assert button.get("hx-get").startswith(_older_url(learner, conversation.pk, ""))

    def test_the_modal_thread_ids_differ_from_the_own_threads(
        self, msg_client_for, long_scene
    ):
        (organisation, _, learner, conversation), _ = long_scene

        response = _open_conversation(
            msg_client_for(_msg_educator(organisation)), learner, conversation.pk
        )

        page = lxml.html.fromstring(response.content.decode())
        assert page.xpath("//ol[@id='read-only-thread-log']")
        assert not page.xpath("//*[@id='thread-log' or @id='thread-older']")
        (button,) = page.xpath("//div[@id='read-only-thread-older']//button")
        assert button.get("hx-target") == "#read-only-thread-log"

    def test_the_older_endpoint_pages_back_and_writes_no_entry(
        self, msg_client_for, long_scene
    ):
        (organisation, _, learner, conversation), messages = long_scene
        client = msg_client_for(_msg_educator(organisation))

        response = client.get(
            _older_url(learner, conversation.pk, encode_cursor(messages[4])),
            HTTP_HX_REQUEST="true",
        )

        assert response.status_code == 200
        tree = lxml.html.fromstring(f"<div>{response.content.decode()}</div>")
        ids = [li.get("id") for li in tree.xpath("./li[not(@hx-swap-oob)]")]
        assert ids == [f"msg-{m.pk}" for m in messages[1:4]]
        button = tree.xpath("./div[@id='read-only-thread-older']//button")[0]
        assert button.get("hx-get").startswith(_older_url(learner, conversation.pk, ""))
        assert button.get("hx-target") == "#read-only-thread-log"
        assert _viewed_entries() == []

    def test_the_older_endpoint_is_404_for_a_cohort_admin(
        self, msg_client_for, long_scene
    ):
        (organisation, _, learner, conversation), messages = long_scene
        cohort = CohortFactory(organisation=organisation)
        CohortMembershipFactory(cohort=cohort, learner=learner)
        cohort_admin = cast(User, UserFactory(staff=True))
        _grant(cohort_admin, "cohort_admin", cohort)

        response = msg_client_for(cohort_admin).get(
            _older_url(learner, conversation.pk, encode_cursor(messages[4])),
            HTTP_HX_REQUEST="true",
        )

        assert response.status_code == 404

    def test_the_older_endpoint_is_404_outside_the_oversight_set(
        self, msg_client_for, long_scene
    ):
        (organisation, _, learner, _), messages = long_scene
        client = msg_client_for(_msg_educator(organisation))
        peer = _msg_learner(organisation, first_name="Peer")
        peer_conversation = _msg_conversation(peer.user, learner.user)
        cursor = encode_cursor(messages[4])

        for target in (peer_conversation.pk, uuid4(), "-" * 36):
            response = client.get(
                _older_url(learner, target, cursor), HTTP_HX_REQUEST="true"
            )
            assert response.status_code == 404, target

    def test_the_older_endpoint_is_404_for_another_organisations_learner(
        self, msg_client_for, long_scene
    ):
        (organisation, _, _, conversation), messages = long_scene
        stranger = _msg_learner(OrganisationFactory())

        response = msg_client_for(_msg_educator(organisation)).get(
            _older_url(
                stranger, conversation.pk, encode_cursor(messages[4]), organisation
            ),
            HTTP_HX_REQUEST="true",
        )

        assert response.status_code == 404

    def test_the_older_endpoint_is_404_when_messaging_is_off(
        self, msg_client_for, long_scene, settings
    ):
        (organisation, _, learner, conversation), messages = long_scene
        client = msg_client_for(_msg_educator(organisation))
        settings.MESSAGING_ENABLED = False

        response = client.get(
            _older_url(learner, conversation.pk, encode_cursor(messages[4])),
            HTTP_HX_REQUEST="true",
        )

        assert response.status_code == 404

    @pytest.mark.parametrize("cursor", ["", "junk"])
    def test_a_missing_or_malformed_cursor_is_a_400(
        self, msg_client_for, long_scene, cursor
    ):
        (organisation, _, learner, conversation), _ = long_scene

        response = msg_client_for(_msg_educator(organisation)).get(
            _older_url(learner, conversation.pk, cursor), HTTP_HX_REQUEST="true"
        )

        assert response.status_code == 400


# learner import pages


def _import_url(organisation: Organisation, name: str, learner_import=None) -> str:
    kwargs: dict[str, object] = {"organisation_slug": organisation.slug}
    if learner_import is not None:
        kwargs["import_id"] = learner_import.pk
    return reverse(f"educator_interface:{name}", kwargs=kwargs)


def _csv_upload(*lines: str) -> SimpleUploadedFile:
    body = "email,first_name,last_name,cohort\n" + "\n".join(lines)
    return SimpleUploadedFile("learners.csv", body.encode(), "text/csv")


def _import_for(user: User, organisation: Organisation, *lines: str) -> LearnerImport:
    return create_learner_import(user, organisation, None, _csv_upload(*lines))


@pytest.fixture
def import_world(logged_in_client: Callable[[User], Client], mock_site_context: Site):
    organisation = OrganisationFactory()
    grantor = cast(User, UserFactory(superuser=True))
    admin = cast(User, LearnerFactory(user__staff=True, organisation=organisation).user)
    assign_role(grantor, admin, "organisation_admin", organisation)
    cohort = cast(Cohort, CohortFactory(organisation=organisation))
    cohort_admin = cast(
        User, LearnerFactory(user__staff=True, organisation=organisation).user
    )
    assign_role(grantor, cohort_admin, "cohort_admin", cohort)
    return SimpleNamespace(
        organisation=organisation,
        admin=admin,
        client=logged_in_client(admin),
        cohort=cohort,
        cohort_admin_client=logged_in_client(cohort_admin),
        logged_in_client=logged_in_client,
    )


@pytest.mark.django_db
def test_the_upload_page_shows_the_headers_the_stepper_and_the_file_input(
    import_world: SimpleNamespace,
):
    page = _get_document(
        import_world.client, _import_url(import_world.organisation, "learner_import")
    )

    assert page.cssselect("input[type=file]")
    assert [code.text for code in page.cssselect("[data-format-table] code")] == [
        "email",
        "first_name",
        "last_name",
        "cohort",
    ]
    assert page.cssselect("ol li[aria-current='step']")
    assert "Step 1 of 3" in page.text_content()


@pytest.mark.django_db
def test_the_format_table_has_one_row_per_header_with_only_email_required(
    import_world: SimpleNamespace,
):
    page = _get_document(
        import_world.client, _import_url(import_world.organisation, "learner_import")
    )

    rows = [
        (row.cssselect("td")[0].text_content().strip(), row.cssselect("td")[1].text)
        for row in page.cssselect("[data-format-table] tbody tr")
    ]
    assert rows == [
        ("email", "Required"),
        ("first_name", "Optional"),
        ("last_name", "Optional"),
        ("cohort", "Optional"),
    ]


@pytest.mark.django_db
def test_the_upload_page_states_the_row_and_file_size_limits(
    import_world: SimpleNamespace, settings, monkeypatch: pytest.MonkeyPatch
):
    settings.LEARNER_IMPORT_MAX_ROWS = 1500
    monkeypatch.setattr(
        "freedom_ls.educator_interface.panels.learner.import_views.MAX_UPLOAD_BYTES",
        2 * 1024 * 1024,
    )

    page = _get_document(
        import_world.client, _import_url(import_world.organisation, "learner_import")
    )

    text = page.text_content().replace("\xa0", " ")
    assert "Add up to 1,500 learners at once, 2.0 MB per file" in " ".join(text.split())


@pytest.mark.django_db
def test_the_cohort_upload_page_describes_the_cohort_column_as_ignored(
    import_world: SimpleNamespace,
):
    cohort = CohortFactory(organisation=import_world.organisation, name="Accra Jan")

    page = _get_document(
        import_world.client, _cohort_import_url(import_world.organisation, cohort)
    )

    cohort_row = page.cssselect("[data-format-table] tbody tr")[3]
    assert "Ignored: everyone goes into Accra Jan." in " ".join(
        cohort_row.text_content().split()
    )


@pytest.mark.django_db
def test_an_import_page_offers_a_back_link_to_the_learners_list(
    import_world: SimpleNamespace,
):
    organisation = import_world.organisation

    page = _get_document(
        import_world.client, _import_url(organisation, "learner_import")
    )

    (back,) = page.cssselect("#breadcrumbs a")
    assert back.get("href") == _interface_url(organisation.slug, "learners")
    assert back.text_content().strip() == "Learners"


@pytest.mark.django_db
def test_the_stepper_numbers_each_step_in_its_own_label(
    import_world: SimpleNamespace,
):
    page = _get_document(
        import_world.client, _import_url(import_world.organisation, "learner_import")
    )

    steps = page.cssselect("nav[aria-label='Import steps'] [data-step-label]")
    assert [" ".join(step.text_content().split()) for step in steps] == [
        "1. Upload",
        "2. Preview",
        "3. Result",
    ]


@pytest.mark.django_db
def test_the_stepper_line_names_the_current_step_for_narrow_screens(
    import_world: SimpleNamespace,
):
    learner_import = _import_for(
        import_world.admin, import_world.organisation, "a@example.com,,,"
    )

    page = _get_document(
        import_world.client,
        _import_url(
            import_world.organisation, "learner_import_preview", learner_import
        ),
    )

    (stepper,) = page.cssselect("nav[aria-label='Import steps']")
    assert "Step 2 of 3: Preview" in " ".join(stepper.text_content().split())


@pytest.mark.django_db
def test_an_organisation_admin_passes_the_import_gate_and_a_cohort_admin_gets_the_403_page(
    import_world: SimpleNamespace,
):
    url = _import_url(import_world.organisation, "learner_import")

    allowed = import_world.client.get(url)
    denied = import_world.cohort_admin_client.get(url)

    assert allowed.status_code == 200
    assert denied.status_code == 403
    assert (
        "can't import learners here"
        in lxml.html.fromstring(denied.content.decode()).text_content()
    )


@pytest.mark.django_db
def test_a_bad_file_is_a_422_with_a_focused_alert_and_stores_nothing(
    import_world: SimpleNamespace,
):
    response = import_world.client.post(
        _import_url(import_world.organisation, "learner_import"),
        {"file": SimpleUploadedFile("learners.csv", b"name\nAda\n")},
    )

    page = lxml.html.fromstring(response.content.decode())
    (alert,) = page.cssselect("#main-content [role=alert]")
    assert response.status_code == 422
    assert alert.get("autofocus") is not None
    assert "Unknown column(s): name" in alert.text_content()
    assert not LearnerImport.objects.exists()


@pytest.mark.django_db
def test_the_file_input_only_offers_csv_files(import_world: SimpleNamespace):
    page = _get_document(
        import_world.client, _import_url(import_world.organisation, "learner_import")
    )

    (file_input,) = page.cssselect("input[type=file]")
    assert file_input.get("accept") == ".csv,text/csv"


@pytest.mark.django_db
def test_the_file_input_is_described_by_the_limits_line(
    import_world: SimpleNamespace,
):
    page = _get_document(
        import_world.client, _import_url(import_world.organisation, "learner_import")
    )

    (file_input,) = page.cssselect("input[type=file]")
    (limits,) = page.cssselect(f"#{file_input.get('aria-describedby')}")
    assert "rows" in limits.text_content()


@pytest.mark.django_db
def test_a_bad_file_page_still_wraps_the_input_in_the_drop_zone(
    import_world: SimpleNamespace,
):
    response = import_world.client.post(
        _import_url(import_world.organisation, "learner_import"),
        {"file": SimpleUploadedFile("learners.csv", b"name\nAda\n")},
    )

    page = lxml.html.fromstring(response.content.decode())
    (file_input,) = page.cssselect("input[type=file]")
    assert page.cssselect(f"label[for={file_input.get('id')}][data-drop-zone]")


@pytest.mark.django_db
def test_a_good_file_redirects_with_a_303_to_its_preview(
    import_world: SimpleNamespace,
):
    response = import_world.client.post(
        _import_url(import_world.organisation, "learner_import"),
        {"file": _csv_upload("a@example.com,Ada,Lovelace,")},
    )

    learner_import = LearnerImport.objects.get()
    assert response.status_code == 303
    assert response["Location"] == _import_url(
        import_world.organisation, "learner_import_preview", learner_import
    )


@pytest.mark.django_db
def test_the_preview_counts_each_label_and_offers_to_add_the_rows_that_can_be_added(
    import_world: SimpleNamespace,
):
    existing = LearnerFactory(organisation=import_world.organisation)
    learner_import = _import_for(
        import_world.admin,
        import_world.organisation,
        "a@example.com,,,",
        "b@example.com,,,",
        f"{existing.user.email},,,",
        "nonsense,,,",
    )

    page = _get_document(
        import_world.client,
        _import_url(
            import_world.organisation, "learner_import_preview", learner_import
        ),
    )

    text = " ".join(page.text_content().split())
    tile_labels = [
        link.get("aria-label") for link in page.cssselect("a[data-label-filter]")
    ]
    assert "New account: 2" in tile_labels
    assert "Already a member: 1" in tile_labels
    assert "Error: 1" in tile_labels
    assert "1 row with errors will not be added." in text
    assert "2 new accounts will get a setup email." in text
    assert [
        button.text_content().strip()
        for button in page.cssselect("#main-content button[type=submit]")
    ] == ["Add 2 learners"]
    assert len(page.cssselect("[data-import-rows] tbody tr")) == 3


@pytest.mark.django_db
def test_a_preview_with_nothing_to_add_has_no_confirm_button_and_says_why(
    import_world: SimpleNamespace,
):
    learner_import = _import_for(
        import_world.admin, import_world.organisation, "nonsense,,,"
    )

    page = _get_document(
        import_world.client,
        _import_url(
            import_world.organisation, "learner_import_preview", learner_import
        ),
    )

    assert not page.cssselect("#main-content form button[type=submit]")
    assert "Nothing can be added" in page.text_content()


@pytest.mark.django_db
def test_a_preview_with_no_new_accounts_omits_the_setup_email_line(
    import_world: SimpleNamespace,
):
    existing = LearnerFactory(organisation=import_world.organisation)
    learner_import = _import_for(
        import_world.admin, import_world.organisation, f"{existing.user.email},,,"
    )

    page = _get_document(
        import_world.client,
        _import_url(
            import_world.organisation, "learner_import_preview", learner_import
        ),
    )

    assert "setup email" not in page.text_content()


@pytest.mark.django_db
def test_a_result_with_nothing_not_added_omits_the_not_added_line(
    import_world: SimpleNamespace,
):
    learner_import = _import_for(
        import_world.admin, import_world.organisation, "a@example.com,,,"
    )
    import_world.client.post(
        _import_url(import_world.organisation, "learner_import_preview", learner_import)
    )

    page = _get_document(
        import_world.client,
        _import_url(import_world.organisation, "learner_import_result", learner_import),
    )

    text = " ".join(page.text_content().split())
    assert "Added 1 learner." in text
    assert "not added" not in text


@pytest.mark.django_db
def test_a_result_with_no_new_accounts_omits_the_setup_email_line(
    import_world: SimpleNamespace,
):
    existing = LearnerFactory(organisation=import_world.organisation)
    learner_import = _import_for(
        import_world.admin, import_world.organisation, f"{existing.user.email},,,"
    )
    import_world.client.post(
        _import_url(import_world.organisation, "learner_import_preview", learner_import)
    )

    page = _get_document(
        import_world.client,
        _import_url(import_world.organisation, "learner_import_result", learner_import),
    )

    assert "setup email" not in page.text_content()


@pytest.mark.django_db
def test_confirming_runs_the_import_and_the_result_page_reports_it(
    import_world: SimpleNamespace,
):
    learner_import = _import_for(
        import_world.admin,
        import_world.organisation,
        "a@example.com,,,",
        "b@example.com,,,",
        "nonsense,,,",
    )

    confirmed = import_world.client.post(
        _import_url(import_world.organisation, "learner_import_preview", learner_import)
    )
    result_url = _import_url(
        import_world.organisation, "learner_import_result", learner_import
    )
    page = _get_document(import_world.client, result_url)

    text = " ".join(page.text_content().split())
    assert (confirmed.status_code, confirmed["Location"]) == (303, result_url)
    assert "Added 2 learners. 1 row was not added." in text
    assert "2 setup emails were sent." in text
    assert "Step 3 of 3" in text


@pytest.mark.django_db
def test_the_result_shows_its_completed_time_in_site_time_not_the_browsers(
    import_world: SimpleNamespace,
):
    """The completed time used to be a `<time x-data="localTime">` the browser
    rewrote into its own zone, so it disagreed with the tables beside it."""
    learner_import = _import_for(
        import_world.admin, import_world.organisation, "a@example.com,,,"
    )
    import_world.client.post(
        _import_url(import_world.organisation, "learner_import_preview", learner_import)
    )

    page = _get_document(
        import_world.client,
        _import_url(import_world.organisation, "learner_import_result", learner_import),
    )

    assert page.cssselect('time[x-data="localTime"]') == []
    assert len(page.cssselect("time[datetime]")) == 1


@pytest.mark.django_db
def test_a_second_confirmation_does_not_run_the_import_again(
    import_world: SimpleNamespace,
):
    learner_import = _import_for(
        import_world.admin, import_world.organisation, "a@example.com,,,"
    )
    url = _import_url(
        import_world.organisation, "learner_import_preview", learner_import
    )

    import_world.client.post(url)
    second = import_world.client.post(url)

    assert second.status_code == 303
    assert second["Location"] == _import_url(
        import_world.organisation, "learner_import_result", learner_import
    )
    assert Learner.objects.filter(organisation=import_world.organisation).count() == 3


@pytest.mark.django_db
def test_a_finished_import_redirects_from_its_preview_to_its_result(
    import_world: SimpleNamespace,
):
    learner_import = _import_for(
        import_world.admin, import_world.organisation, "a@example.com,,,"
    )
    LearnerImport.objects.filter(pk=learner_import.pk).update(status=RunStatus.DONE)

    response = import_world.client.get(
        _import_url(import_world.organisation, "learner_import_preview", learner_import)
    )

    assert response.status_code == 303


@pytest.mark.django_db
@pytest.mark.parametrize("name", ["learner_import_preview", "learner_import_result"])
def test_an_import_is_a_404_for_another_user_of_the_organisation(
    import_world: SimpleNamespace, name: str
):
    learner_import = _import_for(
        import_world.admin, import_world.organisation, "a@example.com,,,"
    )
    other = cast(User, UserFactory(superuser=True))

    response = import_world.logged_in_client(other).get(
        _import_url(import_world.organisation, name, learner_import)
    )

    assert response.status_code == 404


@pytest.mark.django_db
@pytest.mark.parametrize("name", ["learner_import_preview", "learner_import_result"])
def test_an_import_is_a_404_through_another_organisations_slug(
    import_world: SimpleNamespace, name: str
):
    learner_import = _import_for(
        import_world.admin, import_world.organisation, "a@example.com,,,"
    )
    elsewhere = OrganisationFactory()

    response = import_world.client.get(_import_url(elsewhere, name, learner_import))

    assert response.status_code == 404


@pytest.mark.django_db
def test_the_learners_list_offers_the_import_link_to_an_admin_and_not_to_a_cohort_admin(
    import_world: SimpleNamespace,
):
    url = _interface_url(import_world.organisation.slug, "learners")
    import_url = _import_url(import_world.organisation, "learner_import")

    admin_page = import_world.client.get(url).content.decode()
    cohort_admin_page = import_world.cohort_admin_client.get(url).content.decode()

    assert f'href="{import_url}"' in admin_page
    assert import_url not in cohort_admin_page


# learner import preview, template and error file


def _numbered_lines(good: int, bad: int) -> list[str]:
    return [f"person{n}@example.com,,," for n in range(good)] + [
        f"bad{n},,," for n in range(bad)
    ]


@pytest.mark.django_db
def test_the_preview_filters_its_rows_to_the_label_in_the_query_string(
    import_world: SimpleNamespace,
):
    learner_import = _import_for(
        import_world.admin,
        import_world.organisation,
        "good@example.com,,,",
        "bad,,,",
    )

    page = _get_document(
        import_world.client,
        _import_url(import_world.organisation, "learner_import_preview", learner_import)
        + "?label=error",
    )

    emails = [
        cell.text
        for cell in page.cssselect("[data-import-rows] tbody tr td:nth-child(2)")
    ]
    assert emails == ["bad"]


@pytest.mark.django_db
def test_each_label_count_links_to_the_preview_filtered_by_that_label(
    import_world: SimpleNamespace,
):
    learner_import = _import_for(
        import_world.admin, import_world.organisation, "good@example.com,,,", "bad,,,"
    )
    preview_url = _import_url(
        import_world.organisation, "learner_import_preview", learner_import
    )

    page = _get_document(import_world.client, preview_url)

    hrefs = [link.get("href") for link in page.cssselect("a[data-label-filter]")]
    assert sorted(hrefs) == [
        f"{preview_url}?label=error",
        f"{preview_url}?label=new_account",
    ]


@pytest.mark.django_db
def test_each_summary_tile_names_its_label_and_count_in_its_aria_label(
    import_world: SimpleNamespace,
):
    learner_import = _import_for(
        import_world.admin, import_world.organisation, "good@example.com,,,", "bad,,,"
    )

    page = _get_document(
        import_world.client,
        _import_url(
            import_world.organisation, "learner_import_preview", learner_import
        ),
    )

    labels = sorted(
        link.get("aria-label") for link in page.cssselect("a[data-label-filter]")
    )
    assert labels == ["Error: 1", "New account: 1"]


@pytest.mark.django_db
def test_only_the_tile_of_the_active_filter_is_marked_current(
    import_world: SimpleNamespace,
):
    learner_import = _import_for(
        import_world.admin, import_world.organisation, "good@example.com,,,", "bad,,,"
    )

    page = _get_document(
        import_world.client,
        _import_url(import_world.organisation, "learner_import_preview", learner_import)
        + "?label=error",
    )

    current = {
        link.get("aria-label"): link.get("aria-current")
        for link in page.cssselect("a[data-label-filter]")
    }
    assert current == {"Error: 1": "true", "New account: 1": None}


@pytest.mark.django_db
def test_clear_filter_shows_only_under_a_filter_and_links_to_the_preview(
    import_world: SimpleNamespace,
):
    learner_import = _import_for(
        import_world.admin, import_world.organisation, "good@example.com,,,", "bad,,,"
    )
    preview_url = _import_url(
        import_world.organisation, "learner_import_preview", learner_import
    )

    unfiltered = _get_document(import_world.client, preview_url)
    filtered = _get_document(import_world.client, preview_url + "?label=error")

    clear = "//a[normalize-space()='Clear filter']"
    assert unfiltered.xpath(clear) == []
    assert [link.get("href") for link in filtered.xpath(clear)] == [preview_url]


@pytest.mark.django_db
def test_each_label_cell_carries_the_tone_of_its_label(import_world: SimpleNamespace):
    existing = LearnerFactory(organisation=import_world.organisation)
    learner_import = _import_for(
        import_world.admin,
        import_world.organisation,
        "new@example.com,,,",
        f"{existing.user.email},,,",
    )

    page = _get_document(
        import_world.client,
        _import_url(
            import_world.organisation, "learner_import_preview", learner_import
        ),
    )

    tones = {
        row.xpath("string(td[2])").strip(): row.xpath("td[6]")[0].get("data-tone")
        for row in page.cssselect("[data-import-rows] tbody tr")
    }
    assert tones == {
        "new@example.com": PREVIEW_LABEL_TONES[ImportLabel.NEW_ACCOUNT],
        existing.user.email: PREVIEW_LABEL_TONES[ImportLabel.ALREADY_MEMBER],
    }


@pytest.mark.django_db
def test_the_preview_pages_fifty_rows_at_a_time_and_keeps_the_label_filter(
    import_world: SimpleNamespace,
):
    learner_import = _import_for(
        import_world.admin, import_world.organisation, *_numbered_lines(2, 51)
    )
    preview_url = _import_url(
        import_world.organisation, "learner_import_preview", learner_import
    )

    first = _get_document(import_world.client, f"{preview_url}?label=error")
    second = _get_document(import_world.client, f"{preview_url}?label=error&page=2")

    next_link = next(
        link for link in first.cssselect("a") if link.text_content().strip() == "Next"
    )
    assert (
        len(first.cssselect("[data-import-rows] tbody tr")),
        len(second.cssselect("[data-import-rows] tbody tr")),
        sorted(parse_qsl(urlsplit(next_link.get("href")).query)),
    ) == (50, 1, [("label", "error"), ("page", "2")])


@pytest.mark.django_db
def test_an_htmx_page_request_for_the_preview_returns_only_the_rows_card(
    import_world: SimpleNamespace,
):
    learner_import = _import_for(
        import_world.admin, import_world.organisation, *_numbered_lines(2, 51)
    )
    preview_url = _import_url(
        import_world.organisation, "learner_import_preview", learner_import
    )

    response = import_world.client.get(
        f"{preview_url}?label=error&page=2",
        headers={"HX-Request": "true", "HX-Target": "import-rows"},
    )

    page = lxml.html.fromstring(response.content.decode())
    assert len(page.cssselect("[data-import-rows] tbody tr")) == 1
    assert not page.cssselect("[data-label-filter]")


def _rows_footer_count(page: lxml.html.HtmlElement) -> str:
    (count,) = page.cssselect("#import-rows [data-entry-count]")
    return str(count.text_content()).strip()


@pytest.mark.django_db
def test_a_one_page_preview_states_how_many_rows_it_shows_in_its_footer(
    import_world: SimpleNamespace,
):
    """The Rows table used to have no footer at all on a single page."""
    learner_import = _import_for(
        import_world.admin, import_world.organisation, *_numbered_lines(28, 0)
    )

    page = _get_document(
        import_world.client,
        _import_url(
            import_world.organisation, "learner_import_preview", learner_import
        ),
    )

    assert _rows_footer_count(page) == "28 rows"
    assert not page.cssselect("#import-rows a[hx-get]")


@pytest.mark.django_db
def test_a_two_page_preview_footer_shows_the_range_and_the_pager(
    import_world: SimpleNamespace,
):
    """The footer used to read only "Page 1 of 2", with no entry count."""
    learner_import = _import_for(
        import_world.admin, import_world.organisation, *_numbered_lines(60, 0)
    )

    page = _get_document(
        import_world.client,
        _import_url(
            import_world.organisation, "learner_import_preview", learner_import
        ),
    )

    assert _rows_footer_count(page) == "Showing 1\u201350 of 60 rows"
    assert any(
        link.text_content().strip() == "Next"
        for link in page.cssselect("#import-rows a")
    )


@pytest.mark.django_db
def test_a_filtered_preview_footer_counts_the_filtered_rows(
    import_world: SimpleNamespace,
):
    learner_import = _import_for(
        import_world.admin, import_world.organisation, *_numbered_lines(5, 3)
    )

    page = _get_document(
        import_world.client,
        _import_url(import_world.organisation, "learner_import_preview", learner_import)
        + "?label=error",
    )

    assert _rows_footer_count(page) == "3 rows"


@pytest.mark.django_db
def test_the_preview_rows_table_scrolls_inside_a_capped_region(
    import_world: SimpleNamespace,
):
    """The Rows table used to grow the page by up to fifty rows."""
    learner_import = _import_for(
        import_world.admin, import_world.organisation, *_numbered_lines(3, 0)
    )

    page = _get_document(
        import_world.client,
        _import_url(
            import_world.organisation, "learner_import_preview", learner_import
        ),
    )

    assert page.cssselect("#import-rows [data-capped]")


@pytest.mark.django_db
def test_an_htmx_request_for_the_preview_from_elsewhere_returns_the_whole_preview(
    import_world: SimpleNamespace,
):
    """htmx following a redirect here, or a navigation link, swaps the main
    content, so it needs the tiles and the confirm form as well as the rows."""
    learner_import = _import_for(
        import_world.admin, import_world.organisation, *_numbered_lines(2, 3)
    )
    preview_url = _import_url(
        import_world.organisation, "learner_import_preview", learner_import
    )

    response = import_world.client.get(
        preview_url, headers={"HX-Request": "true", "HX-Target": "main-content"}
    )

    page = lxml.html.fromstring(response.content.decode())
    assert page.cssselect("[data-label-filter]")


@pytest.mark.django_db
def test_the_preview_shows_the_file_chip_and_a_link_to_upload_a_different_file(
    import_world: SimpleNamespace,
):
    learner_import = _import_for(
        import_world.admin, import_world.organisation, "a@example.com,,,"
    )

    page = _get_document(
        import_world.client,
        _import_url(
            import_world.organisation, "learner_import_preview", learner_import
        ),
    )

    chip = " ".join(page.cssselect(".chip")[0].text_content().split())
    upload_link = page.xpath("//a[normalize-space()='Upload a different file']")[0]
    assert (chip, upload_link.get("href")) == (
        "learners.csv \u00b7 1 row",
        _import_url(import_world.organisation, "learner_import"),
    )


@pytest.mark.django_db
def test_the_preview_offers_each_row_as_a_card_for_narrow_screens(
    import_world: SimpleNamespace,
):
    learner_import = _import_for(
        import_world.admin, import_world.organisation, "a@example.com,Ada,,"
    )

    page = _get_document(
        import_world.client,
        _import_url(
            import_world.organisation, "learner_import_preview", learner_import
        ),
    )

    card = page.cssselect("ul[data-row-cards] > li")[0]
    assert "a@example.com" in card.text_content()
    assert "New account" in card.text_content()


@pytest.mark.django_db
def test_the_preview_links_to_the_error_rows_download_only_when_there_are_errors(
    import_world: SimpleNamespace,
):
    with_errors = _import_for(
        import_world.admin, import_world.organisation, "a@example.com,,,", "bad,,,"
    )
    without_errors = _import_for(
        import_world.admin, import_world.organisation, "b@example.com,,,"
    )

    def download_links(learner_import: LearnerImport) -> list[str]:
        page = _get_document(
            import_world.client,
            _import_url(
                import_world.organisation, "learner_import_preview", learner_import
            ),
        )
        return [
            " ".join(a.text_content().split())
            for a in page.cssselect("a[data-error-download]")
        ]

    assert (download_links(with_errors), download_links(without_errors)) == (
        ["Download errors"],
        [],
    )


def _preview_page(
    import_world: SimpleNamespace, learner_import: LearnerImport, query: str = ""
):
    return _get_document(
        import_world.client,
        _import_url(import_world.organisation, "learner_import_preview", learner_import)
        + query,
    )


@pytest.mark.django_db
def test_the_unfiltered_preview_rows_table_holds_no_error_rows(
    import_world: SimpleNamespace,
):
    learner_import = _import_for(
        import_world.admin, import_world.organisation, "good@example.com,,,", "bad,,,"
    )

    page = _preview_page(import_world, learner_import)

    emails = [
        c.text for c in page.cssselect("[data-import-rows] tbody tr td:nth-child(2)")
    ]
    assert emails == ["good@example.com"]


@pytest.mark.django_db
def test_the_preview_filtered_to_errors_lists_only_error_rows_in_the_rows_table(
    import_world: SimpleNamespace,
):
    learner_import = _import_for(
        import_world.admin, import_world.organisation, "good@example.com,,,", "bad,,,"
    )

    page = _preview_page(import_world, learner_import, "?label=error")

    emails = [
        c.text for c in page.cssselect("[data-import-rows] tbody tr td:nth-child(2)")
    ]
    assert emails == ["bad"]


@pytest.mark.django_db
def test_the_error_block_lists_the_line_email_and_reason_of_each_error_row(
    import_world: SimpleNamespace,
):
    learner_import = _import_for(
        import_world.admin, import_world.organisation, "good@example.com,,,", "bad,,,"
    )

    page = _preview_page(import_world, learner_import)

    cells = [
        c.text for c in page.cssselect("[data-error-block] table[data-error-rows] td")
    ]
    assert cells == ["3", "bad", "This isn't a valid email address."]


@pytest.mark.django_db
def test_the_error_block_links_to_the_download_and_the_corrected_file_upload(
    import_world: SimpleNamespace,
):
    learner_import = _import_for(
        import_world.admin, import_world.organisation, "good@example.com,,,", "bad,,,"
    )

    page = _preview_page(import_world, learner_import)

    download = page.cssselect("[data-error-block] a[data-error-download]")[0]
    reupload = page.cssselect("[data-error-block] a[data-error-reupload]")[0]
    assert (download.get("href"), reupload.get("href")) == (
        _import_url(import_world.organisation, "learner_import_errors", learner_import),
        _import_url(import_world.organisation, "learner_import"),
    )


@pytest.mark.django_db
def test_the_error_block_buttons_are_the_small_size(import_world: SimpleNamespace):
    """The download and corrected-file links used to render at the default button size."""
    learner_import = _import_for(
        import_world.admin, import_world.organisation, "good@example.com,,,", "bad,,,"
    )

    page = _preview_page(import_world, learner_import)

    buttons = page.cssselect(
        "[data-error-block] a[data-error-download], [data-error-block] a[data-error-reupload]"
    )
    assert [("btn-sm" in b.get("class").split()) for b in buttons] == [True, True]


@pytest.mark.django_db
def test_the_error_block_shows_fifty_error_rows_and_says_how_many_there_are(
    import_world: SimpleNamespace,
):
    learner_import = _import_for(
        import_world.admin, import_world.organisation, *_numbered_lines(1, 51)
    )

    page = _preview_page(import_world, learner_import)

    block = page.cssselect("[data-error-block]")[0]
    assert len(block.cssselect("table[data-error-rows] tbody tr")) == 50
    assert "Showing the first 50 of 51." in " ".join(block.text_content().split())


@pytest.mark.django_db
def test_a_preview_without_errors_has_no_error_block(import_world: SimpleNamespace):
    learner_import = _import_for(
        import_world.admin, import_world.organisation, "good@example.com,,,"
    )

    page = _preview_page(import_world, learner_import)

    assert not page.cssselect("[data-error-block]")


@pytest.mark.django_db
def test_the_setup_email_line_is_absent_when_no_new_accounts_will_be_made(
    import_world: SimpleNamespace,
):
    existing = LearnerFactory(organisation=import_world.organisation)
    learner_import = _import_for(
        import_world.admin,
        import_world.organisation,
        f"{existing.user.email},,,",
        "bad,,,",
    )

    page = _preview_page(import_world, learner_import)

    assert "will get a setup email" not in page.text_content()


@pytest.mark.django_db
def test_an_all_errors_preview_has_no_rows_card_and_offers_a_different_file_button(
    import_world: SimpleNamespace,
):
    learner_import = _import_for(
        import_world.admin, import_world.organisation, "bad,,,"
    )

    page = _preview_page(import_world, learner_import)

    buttons = page.cssselect("#main-content a.btn")
    different = [
        b
        for b in buttons
        if " ".join(b.text_content().split()) == "Upload a different file"
    ]
    assert not page.cssselect("[data-import-rows]")
    assert "Nothing can be added" in page.text_content()
    upload_url = _import_url(import_world.organisation, "learner_import")
    assert [b.get("href") for b in different] == [upload_url, upload_url]
    assert different[-1].xpath("ancestor::*[@data-error-block]") == []


@pytest.mark.django_db
def test_the_template_download_is_a_bom_prefixed_csv_with_the_headers_and_two_examples(
    import_world: SimpleNamespace,
):
    response = import_world.client.get(
        _import_url(import_world.organisation, "learner_import_template")
    )

    body = b"".join(response.streaming_content).decode("utf-8")
    rows = list(csv.reader(io.StringIO(body.lstrip("﻿"))))
    assert (
        body.startswith("﻿"),
        response["Content-Disposition"],
        rows[0],
        len(rows),
    ) == (
        True,
        'attachment; filename="learner-import-template.csv"',
        ["email", "first_name", "last_name", "cohort"],
        3,
    )


@pytest.mark.django_db
def test_the_template_download_is_refused_to_a_user_who_fails_the_import_gate(
    import_world: SimpleNamespace,
):
    response = import_world.cohort_admin_client.get(
        _import_url(import_world.organisation, "learner_import_template")
    )

    assert response.status_code == 403


@pytest.fixture
def cohort_importer_client(
    import_world: SimpleNamespace, mock_site_context: Site, settings
) -> Iterator[Client]:
    """A client whose user passes the cohort import gate but not the
    organisation-wide one, which no shipped role does."""
    role = Role(
        display_name="Cohort importer",
        permissions=frozenset(
            {
                VIEW_ORGANISATION,
                VIEW_COHORT,
                VIEW_LEARNER,
                ADD_LEARNER,
                ADD_COHORTMEMBERSHIP,
            }
        ),
        assignment_scope=SCOPE_OBJECT,
    )
    with custom_role_config(
        mock_site_context, settings, extra_roles={"cohort_importer": role}
    ):
        importer = cast(
            User,
            LearnerFactory(
                user__staff=True, organisation=import_world.organisation
            ).user,
        )
        assign_object_role(importer, import_world.organisation, "cohort_importer")
        yield import_world.logged_in_client(importer)


@pytest.mark.django_db
def test_a_cohort_page_importer_can_download_the_template(
    import_world: SimpleNamespace, cohort_importer_client: Client
):
    """The template was gated on the organisation-wide import, so the cohort
    upload page offered a link that answered 403 to an importer who may only
    import into the cohort."""
    upload_url = (
        f"{_import_url(import_world.organisation, 'learner_import')}"
        f"?cohort={import_world.cohort.pk}"
    )
    page = _get_document(cohort_importer_client, upload_url)
    template_url = _import_url(import_world.organisation, "learner_import_template")
    (href,) = [
        a.get("href") for a in page.cssselect("a") if template_url in a.get("href")
    ]

    organisation_wide = cohort_importer_client.get(template_url)
    response = cohort_importer_client.get(href)

    assert href == f"{template_url}?cohort={import_world.cohort.pk}"
    assert organisation_wide.status_code == 403
    assert response.status_code == 200
    assert response["Content-Type"].startswith("text/csv")


@pytest.mark.django_db
def test_the_upload_page_links_to_the_template(import_world: SimpleNamespace):
    page = _get_document(
        import_world.client, _import_url(import_world.organisation, "learner_import")
    )

    hrefs = [a.get("href") for a in page.cssselect("a")]
    assert _import_url(import_world.organisation, "learner_import_template") in hrefs


def _error_csv_rows(response) -> tuple[str, list[list[str]]]:
    body = b"".join(response.streaming_content).decode("utf-8")
    return body, list(csv.reader(io.StringIO(body.lstrip("﻿"))))


@pytest.mark.django_db
def test_the_error_csv_of_a_preview_holds_exactly_the_error_rows_with_reasons(
    import_world: SimpleNamespace,
):
    learner_import = _import_for(
        import_world.admin,
        import_world.organisation,
        "good@example.com,Ada,Lovelace,",
        "=bad,Eve,Hacker,",
    )

    response = import_world.client.get(
        _import_url(import_world.organisation, "learner_import_errors", learner_import)
    )

    body, rows = _error_csv_rows(response)
    assert (body.startswith("﻿"), rows) == (
        True,
        [
            ["email", "first_name", "last_name", "cohort", "reason"],
            ["'=bad", "Eve", "Hacker", "", "This isn't a valid email address."],
        ],
    )


@pytest.mark.django_db
def test_the_error_csv_is_named_for_the_day(import_world: SimpleNamespace):
    learner_import = _import_for(
        import_world.admin, import_world.organisation, "bad,,,"
    )

    with time_machine.travel(datetime(2026, 3, 4, 12, tzinfo=UTC)):
        response = import_world.client.get(
            _import_url(
                import_world.organisation, "learner_import_errors", learner_import
            )
        )

    assert (
        response["Content-Disposition"]
        == 'attachment; filename="learner-import-errors-2026-03-04.csv"'
    )


@pytest.mark.django_db
def test_the_error_csv_of_a_finished_import_holds_the_final_error_rows(
    import_world: SimpleNamespace,
):
    learner_import = _import_for(
        import_world.admin, import_world.organisation, "good@example.com,,,", "bad,,,"
    )
    import_world.client.post(
        _import_url(import_world.organisation, "learner_import_preview", learner_import)
    )

    response = import_world.client.get(
        _import_url(import_world.organisation, "learner_import_errors", learner_import)
    )

    _body, rows = _error_csv_rows(response)
    assert [row[0] for row in rows[1:]] == ["bad"]


@pytest.mark.django_db
def test_the_error_csv_is_a_404_for_another_user_of_the_organisation(
    import_world: SimpleNamespace,
):
    learner_import = _import_for(
        import_world.admin, import_world.organisation, "bad,,,"
    )
    other = cast(User, UserFactory(superuser=True))

    response = import_world.logged_in_client(other).get(
        _import_url(import_world.organisation, "learner_import_errors", learner_import)
    )

    assert response.status_code == 404


@pytest.mark.django_db
def test_the_result_lists_its_error_rows_the_download_and_the_reupload_line(
    import_world: SimpleNamespace,
):
    learner_import = _import_for(
        import_world.admin, import_world.organisation, "good@example.com,,,", "bad,,,"
    )
    import_world.client.post(
        _import_url(import_world.organisation, "learner_import_preview", learner_import)
    )

    page = _get_document(
        import_world.client,
        _import_url(import_world.organisation, "learner_import_result", learner_import),
    )

    text = " ".join(page.text_content().split())
    error_cells = [cell.text for cell in page.cssselect("table[data-error-rows] td")]
    download = page.cssselect("a[data-error-download]")[0].get("href")
    assert (error_cells, download) == (
        ["3", "bad", "This isn't a valid email address."],
        _import_url(import_world.organisation, "learner_import_errors", learner_import),
    )
    assert (
        "Uploading the whole file again is safe: rows already added show as "
        "'already a member'." in text
    )


@pytest.mark.django_db
def test_the_result_shows_only_the_first_fifty_error_rows(
    import_world: SimpleNamespace,
):
    learner_import = _import_for(
        import_world.admin, import_world.organisation, *_numbered_lines(0, 51)
    )
    import_world.client.post(
        _import_url(import_world.organisation, "learner_import_preview", learner_import)
    )

    page = _get_document(
        import_world.client,
        _import_url(import_world.organisation, "learner_import_result", learner_import),
    )

    assert len(page.cssselect("table[data-error-rows] tbody tr")) == 50
    assert "Showing the first 50 of 51." in " ".join(page.text_content().split())


@pytest.mark.django_db
def test_the_result_error_block_has_no_corrected_file_link(
    import_world: SimpleNamespace,
):
    learner_import = _import_for(
        import_world.admin, import_world.organisation, "good@example.com,,,", "bad,,,"
    )
    import_world.client.post(
        _import_url(import_world.organisation, "learner_import_preview", learner_import)
    )

    page = _get_document(
        import_world.client,
        _import_url(import_world.organisation, "learner_import_result", learner_import),
    )

    assert page.cssselect("[data-error-block]")
    assert not page.cssselect("a[data-error-reupload]")


@pytest.mark.django_db
def test_a_failed_import_shows_the_reupload_line(import_world: SimpleNamespace):
    learner_import = _import_for(
        import_world.admin, import_world.organisation, "a@example.com,,,"
    )
    LearnerImport.objects.filter(pk=learner_import.pk).update(
        status=RunStatus.FAILED, error_message="Something broke."
    )

    page = _get_document(
        import_world.client,
        _import_url(import_world.organisation, "learner_import_result", learner_import),
    )

    assert "Uploading the whole file again is safe" in page.text_content()


def _import_task_rows():
    from django_tasks_db.models import DBTaskResult

    return DBTaskResult.objects.filter(task_path__endswith="_run_learner_import_task")


def _ten_row_import(import_world: SimpleNamespace) -> LearnerImport:
    return _import_for(
        import_world.admin,
        import_world.organisation,
        *(f"learner{index}@example.com,,," for index in range(10)),
    )


@pytest.mark.django_db
def test_the_preview_names_the_background_only_above_the_threshold(
    import_world: SimpleNamespace, settings
):
    learner_import = _ten_row_import(import_world)
    url = _import_url(
        import_world.organisation, "learner_import_preview", learner_import
    )

    settings.BULK_BACKGROUND_THRESHOLD = 10
    at_threshold = " ".join(
        _get_document(import_world.client, url).text_content().split()
    )
    settings.BULK_BACKGROUND_THRESHOLD = 9
    above_threshold = " ".join(
        _get_document(import_world.client, url).text_content().split()
    )

    assert "runs in the background" not in at_threshold
    assert (
        "This import runs in the background. The result page will show progress."
        in above_threshold
    )


@pytest.mark.django_db(transaction=True)
def test_confirming_above_the_threshold_queues_one_task_and_the_result_page_polls(
    import_world: SimpleNamespace, settings, database_task_backend: None
):
    settings.BULK_BACKGROUND_THRESHOLD = 5
    learner_import = _ten_row_import(import_world)
    preview_url = _import_url(
        import_world.organisation, "learner_import_preview", learner_import
    )
    result_url = _import_url(
        import_world.organisation, "learner_import_result", learner_import
    )

    confirmed = import_world.client.post(preview_url)
    page = _get_document(import_world.client, result_url)

    learner_import.refresh_from_db()
    (status,) = page.cssselect("#run-status")
    assert (confirmed.status_code, confirmed["Location"]) == (303, result_url)
    assert learner_import.status == RunStatus.QUEUED
    assert _import_task_rows().count() == 1
    assert Learner.objects.filter(organisation=import_world.organisation).count() == 2
    assert status.get("role") == "status"
    assert status.get("hx-trigger") == "every 2s"
    assert status.get("hx-get") == _import_url(
        import_world.organisation, "learner_import_status", learner_import
    )
    assert "Waiting to start." in status.text_content()
    assert status.cssselect("progress, [role=progressbar]")


@pytest.mark.django_db(transaction=True)
def test_a_second_confirmation_of_a_queued_import_does_not_enqueue_again(
    import_world: SimpleNamespace, settings, database_task_backend: None
):
    settings.BULK_BACKGROUND_THRESHOLD = 5
    learner_import = _ten_row_import(import_world)
    url = _import_url(
        import_world.organisation, "learner_import_preview", learner_import
    )

    import_world.client.post(url)
    second = import_world.client.post(url)

    assert second.status_code == 303
    assert second["Location"] == _import_url(
        import_world.organisation, "learner_import_result", learner_import
    )
    assert _import_task_rows().count() == 1


@pytest.mark.django_db(transaction=True)
def test_the_status_partial_drops_the_trigger_and_holds_the_result_once_done(
    import_world: SimpleNamespace, settings, database_task_backend: None
):
    settings.BULK_BACKGROUND_THRESHOLD = 5
    learner_import = _ten_row_import(import_world)
    import_world.client.post(
        _import_url(import_world.organisation, "learner_import_preview", learner_import)
    )
    status_url = _import_url(
        import_world.organisation, "learner_import_status", learner_import
    )

    queued = import_world.client.get(status_url)
    run_learner_import(str(learner_import.pk), import_world.organisation.site_id)
    done = import_world.client.get(status_url)

    queued_status = lxml.html.fromstring(queued.content.decode())
    done_status = lxml.html.fromstring(done.content.decode())
    assert queued_status.get("hx-trigger") == "every 2s"
    assert done_status.get("id") == "run-status"
    assert done_status.get("hx-trigger") is None
    assert done_status.get("hx-get") is None
    assert "Added 10 learners." in " ".join(done_status.text_content().split())


@pytest.mark.django_db
def test_the_status_partial_of_a_failed_import_stops_polling_and_shows_the_reason(
    import_world: SimpleNamespace,
):
    learner_import = _import_for(
        import_world.admin, import_world.organisation, "a@example.com,,,"
    )
    LearnerImport.objects.filter(pk=learner_import.pk).update(
        status=RunStatus.FAILED, error_message="Something broke.", processed_count=0
    )

    response = import_world.client.get(
        _import_url(import_world.organisation, "learner_import_status", learner_import)
    )

    status = lxml.html.fromstring(response.content.decode())
    text = " ".join(status.text_content().split())
    assert status.get("hx-trigger") is None
    assert "Stopped after 0 of 1 rows" in text
    assert "Something broke." in text
    assert "Uploading the whole file again is safe" in text


def _finished_result_page(
    import_world: SimpleNamespace, *lines: str
) -> lxml.html.HtmlElement:
    learner_import = _import_for(import_world.admin, import_world.organisation, *lines)
    import_world.client.post(
        _import_url(import_world.organisation, "learner_import_preview", learner_import)
    )
    return _get_document(
        import_world.client,
        _import_url(import_world.organisation, "learner_import_result", learner_import),
    )


@pytest.mark.django_db
def test_a_result_with_no_rows_lost_does_not_mention_rows_not_added(
    import_world: SimpleNamespace,
):
    page = _finished_result_page(import_world, "a@example.com,,,", "b@example.com,,,")

    text = " ".join(page.text_content().split())
    assert "Added 2 learners." in text
    assert "was not added" not in text
    assert "were not added" not in text


@pytest.mark.django_db
def test_a_result_with_no_new_accounts_has_no_setup_email_text(
    import_world: SimpleNamespace,
):
    page = _finished_result_page(import_world, "nonsense,,,")

    assert "setup email" not in page.text_content()


@pytest.mark.django_db
def test_a_result_shows_the_summary_and_the_error_rows_in_separate_panels(
    import_world: SimpleNamespace,
):
    page = _finished_result_page(import_world, "a@example.com,,,", "nonsense,,,")

    (summary,) = page.cssselect("#run-status .panel-surface")
    (error_block,) = page.cssselect("#run-status [data-error-block]")
    assert "Added 1 learner." in summary.text_content()
    assert not summary.cssselect("[data-error-block]")
    assert not [a for a in error_block.iterancestors() if "panel-surface" in a.classes]


@pytest.mark.django_db
def test_a_finished_result_has_no_importing_heading_and_focuses_its_heading(
    import_world: SimpleNamespace,
):
    page = _finished_result_page(import_world, "a@example.com,,,")

    (heading,) = page.cssselect("#run-status h2")
    assert "Importing learners" not in page.text_content()
    assert heading.get("autofocus") is not None
    assert heading.get("tabindex") == "-1"


@pytest.mark.django_db(transaction=True)
def test_a_running_result_is_headed_importing_learners_and_keeps_its_poll(
    import_world: SimpleNamespace, settings, database_task_backend: None
):
    settings.BULK_BACKGROUND_THRESHOLD = 5
    learner_import = _ten_row_import(import_world)
    import_world.client.post(
        _import_url(import_world.organisation, "learner_import_preview", learner_import)
    )

    page = _get_document(
        import_world.client,
        _import_url(import_world.organisation, "learner_import_result", learner_import),
    )

    (status,) = page.cssselect("#run-status")
    headings = [h.text_content().strip() for h in page.cssselect("#main-content h2")]
    assert "Importing learners" in headings
    assert status.get("role") == "status"
    assert status.get("hx-trigger") == "every 2s"
    assert "Waiting to start." in status.text_content()
    assert status.cssselect("progress, [role=progressbar]")


@pytest.mark.django_db(transaction=True)
def test_the_status_fragment_has_no_refresh_header_while_queued(
    import_world: SimpleNamespace, settings, database_task_backend: None
):
    settings.BULK_BACKGROUND_THRESHOLD = 5
    learner_import = _ten_row_import(import_world)
    import_world.client.post(
        _import_url(import_world.organisation, "learner_import_preview", learner_import)
    )

    response = import_world.client.get(
        _import_url(import_world.organisation, "learner_import_status", learner_import)
    )

    assert "HX-Refresh" not in response


@pytest.mark.django_db(transaction=True)
def test_the_status_fragment_asks_for_a_page_refresh_once_done(
    import_world: SimpleNamespace, settings, database_task_backend: None
):
    settings.BULK_BACKGROUND_THRESHOLD = 5
    learner_import = _ten_row_import(import_world)
    import_world.client.post(
        _import_url(import_world.organisation, "learner_import_preview", learner_import)
    )
    run_learner_import(str(learner_import.pk), import_world.organisation.site_id)

    response = import_world.client.get(
        _import_url(import_world.organisation, "learner_import_status", learner_import)
    )

    assert response["HX-Refresh"] == "true"


@pytest.mark.django_db
def test_the_status_fragment_asks_for_a_page_refresh_once_failed(
    import_world: SimpleNamespace,
):
    learner_import = _import_for(
        import_world.admin, import_world.organisation, "a@example.com,,,"
    )
    LearnerImport.objects.filter(pk=learner_import.pk).update(
        status=RunStatus.FAILED, error_message="Something broke."
    )

    response = import_world.client.get(
        _import_url(import_world.organisation, "learner_import_status", learner_import)
    )

    assert response["HX-Refresh"] == "true"


@pytest.mark.django_db
def test_the_import_status_is_a_404_for_another_user_and_another_organisation(
    import_world: SimpleNamespace,
):
    learner_import = _import_for(
        import_world.admin, import_world.organisation, "a@example.com,,,"
    )
    LearnerImport.objects.filter(pk=learner_import.pk).update(status=RunStatus.QUEUED)
    other = cast(User, UserFactory(superuser=True))

    by_other_user = import_world.logged_in_client(other).get(
        _import_url(import_world.organisation, "learner_import_status", learner_import)
    )
    through_other_slug = import_world.client.get(
        _import_url(OrganisationFactory(), "learner_import_status", learner_import)
    )

    assert by_other_user.status_code == 404
    assert through_other_slug.status_code == 404


# learner import from a cohort


def _cohort_import_url(organisation: Organisation, cohort: Cohort) -> str:
    return f"{_import_url(organisation, 'learner_import')}?cohort={cohort.pk}"


def _learners_tab_url(organisation: Organisation, cohort: Cohort) -> str:
    return _interface_url(organisation.slug, f"cohorts/{cohort.pk}/__tabs/learners")


@pytest.mark.django_db
def test_the_cohort_upload_page_names_the_cohort_and_says_the_cohort_column_is_ignored(
    import_world: SimpleNamespace,
):
    cohort = CohortFactory(organisation=import_world.organisation, name="Accra Jan")

    page = _get_document(
        import_world.client, _cohort_import_url(import_world.organisation, cohort)
    )

    text = " ".join(page.text_content().split())
    assert "Accra Jan" in text
    assert "The cohort column is ignored" in text
    assert "is matched by name" not in text


@pytest.mark.django_db
def test_a_cohort_admin_gets_the_403_page_from_the_cohort_upload_page(
    import_world: SimpleNamespace,
):
    response = import_world.cohort_admin_client.get(
        _cohort_import_url(import_world.organisation, import_world.cohort)
    )

    assert response.status_code == 403


@pytest.mark.django_db
def test_an_inactive_cohort_is_refused_by_the_cohort_upload_page(
    import_world: SimpleNamespace,
):
    cohort = CohortFactory(organisation=import_world.organisation, is_active=False)

    response = import_world.client.get(
        _cohort_import_url(import_world.organisation, cohort)
    )

    assert response.status_code == 403


@pytest.mark.django_db
@pytest.mark.parametrize(
    "cohort_param", ["not-a-uuid", "00000000-0000-0000-0000-000000000000"]
)
def test_an_unknown_cohort_is_a_404_on_the_upload_page(
    import_world: SimpleNamespace, cohort_param: str
):
    response = import_world.client.get(
        f"{_import_url(import_world.organisation, 'learner_import')}?cohort={cohort_param}"
    )

    assert response.status_code == 404


@pytest.mark.django_db
def test_a_cohort_in_another_organisation_is_a_404_on_the_upload_page(
    import_world: SimpleNamespace,
):
    foreign = CohortFactory(organisation=OrganisationFactory())

    response = import_world.client.get(
        _cohort_import_url(import_world.organisation, foreign)
    )

    assert response.status_code == 404


@pytest.mark.django_db
def test_uploading_from_the_cohort_page_stores_the_cohort_on_the_import(
    import_world: SimpleNamespace,
):
    cohort = CohortFactory(organisation=import_world.organisation)

    response = import_world.client.post(
        _cohort_import_url(import_world.organisation, cohort),
        {"file": _csv_upload("a@example.com,Ada,Lovelace,Other cohort")},
    )

    learner_import = LearnerImport.objects.get()
    assert response.status_code == 303
    assert learner_import.cohort == cohort


@pytest.mark.django_db
def test_the_preview_of_a_cohort_import_shows_the_target_cohort_on_every_row(
    import_world: SimpleNamespace,
):
    """The preview echoed the file's ignored cohort cell, so a row naming
    another cohort, or none, looked like it would join somewhere else."""
    cohort = CohortFactory(organisation=import_world.organisation, name="Target A")
    CohortFactory(organisation=import_world.organisation, name="Other C")
    learner_import = create_learner_import(
        import_world.admin,
        import_world.organisation,
        cohort,
        _csv_upload("a@example.com,Co,Imp,Other C", "b@example.com,,,"),
    )

    page = _get_document(
        import_world.client,
        _import_url(
            import_world.organisation, "learner_import_preview", learner_import
        ),
    )

    table_cells = [
        " ".join(row.cssselect("td")[4].text_content().split())
        for row in page.cssselect("[data-import-rows] tbody tr")
    ]
    card_values = [
        " ".join(dd.text_content().split())
        for dd in page.cssselect("[data-row-cards] dt:contains('Cohort') + dd")
    ]
    assert table_cells == ["Target A", "Target A"]
    assert card_values == ["Target A", "Target A"]


@pytest.mark.django_db
def test_a_failed_cohort_upload_keeps_the_cohort_for_the_next_attempt(
    import_world: SimpleNamespace,
):
    cohort = CohortFactory(organisation=import_world.organisation, name="Accra Jan")

    response = import_world.client.post(
        _cohort_import_url(import_world.organisation, cohort),
        {"file": SimpleUploadedFile("learners.csv", b"name\nAda\n")},
    )

    assert response.status_code == 422
    assert "Accra Jan" in response.content.decode()


@pytest.mark.django_db
def test_the_result_of_a_cohort_import_links_to_the_cohorts_learners_tab(
    import_world: SimpleNamespace,
):
    cohort = CohortFactory(organisation=import_world.organisation)
    learner_import = create_learner_import(
        import_world.admin,
        import_world.organisation,
        cohort,
        _csv_upload("a@example.com,,,"),
    )
    LearnerImport.objects.filter(pk=learner_import.pk).update(
        status=ImportStatus.QUEUED
    )
    run_learner_import(str(learner_import.pk), import_world.organisation.site_id)

    page = _get_document(
        import_world.client,
        _import_url(import_world.organisation, "learner_import_result", learner_import),
    )

    hrefs = [link.get("href") for link in page.cssselect("#main-content a")]
    assert _learners_tab_url(import_world.organisation, cohort) in hrefs


@pytest.mark.django_db
def test_the_cohort_learners_tab_offers_the_import_link_to_an_organisation_admin(
    import_world: SimpleNamespace,
):
    cohort = CohortFactory(organisation=import_world.organisation)

    page = _get_document(
        import_world.client, _learners_tab_url(import_world.organisation, cohort)
    )

    hrefs = [link.get("href") for link in page.cssselect("a[href]")]
    assert _cohort_import_url(import_world.organisation, cohort) in hrefs


@pytest.mark.django_db
def test_the_cohort_learners_tab_hides_the_import_link_from_a_cohort_admin(
    import_world: SimpleNamespace,
):
    page = _get_document(
        import_world.cohort_admin_client,
        _learners_tab_url(import_world.organisation, import_world.cohort),
    )

    hrefs = [link.get("href") or "" for link in page.cssselect("a[href]")]
    assert not [href for href in hrefs if "/learners/import" in href]
