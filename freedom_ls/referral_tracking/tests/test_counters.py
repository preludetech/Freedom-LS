"""Tests for the daily first-touch tally."""

from __future__ import annotations

import pytest

from freedom_ls.referral_tracking.counters import (
    attribution_key_hash,
    create_or_increment_first_touch,
    increment_first_touch,
)
from freedom_ls.referral_tracking.factories import FirstTouchCountFactory
from freedom_ls.referral_tracking.models import FirstTouchCount


def _key_fields(**overrides: str) -> dict[str, str]:
    fields = {
        "advert_code": "",
        "utm_source": "spring",
        "utm_medium": "email",
        "utm_campaign": "",
        "utm_content": "",
        "utm_term": "",
    }
    fields.update(overrides)
    return fields


def _key_hash(**overrides: str) -> str:
    fields = _key_fields(**overrides)
    return attribution_key_hash(
        fields["advert_code"],
        fields["utm_source"],
        fields["utm_medium"],
        fields["utm_campaign"],
        fields["utm_content"],
        fields["utm_term"],
    )


@pytest.mark.django_db
def test_a_mint_creates_the_row_with_count_one(mock_site_context, site) -> None:
    key_fields = _key_fields()

    increment_first_touch(
        site=site, day="2026-01-01", key_hash=_key_hash(), **key_fields
    )

    row = FirstTouchCount.objects.get(site=site, day="2026-01-01", key_hash=_key_hash())
    assert row.count == 1


@pytest.mark.django_db
def test_a_second_call_for_the_same_key_increments_it_to_two(
    mock_site_context, site
) -> None:
    key_fields = _key_fields()
    key_hash = _key_hash()
    increment_first_touch(site=site, day="2026-01-01", key_hash=key_hash, **key_fields)

    increment_first_touch(site=site, day="2026-01-01", key_hash=key_hash, **key_fields)

    row = FirstTouchCount.objects.get(site=site, day="2026-01-01", key_hash=key_hash)
    assert row.count == 2


@pytest.mark.django_db
def test_a_second_call_for_the_same_key_creates_no_second_row(
    mock_site_context, site
) -> None:
    key_fields = _key_fields()
    key_hash = _key_hash()
    increment_first_touch(site=site, day="2026-01-01", key_hash=key_hash, **key_fields)

    increment_first_touch(site=site, day="2026-01-01", key_hash=key_hash, **key_fields)

    assert (
        FirstTouchCount.objects.filter(
            site=site, day="2026-01-01", key_hash=key_hash
        ).count()
        == 1
    )


@pytest.mark.django_db
def test_a_distinct_key_creates_a_distinct_row(mock_site_context, site) -> None:
    increment_first_touch(
        site=site, day="2026-01-01", key_hash=_key_hash(), **_key_fields()
    )

    increment_first_touch(
        site=site,
        day="2026-01-01",
        key_hash=_key_hash(utm_source="autumn"),
        **_key_fields(utm_source="autumn"),
    )

    assert FirstTouchCount.objects.filter(site=site, day="2026-01-01").count() == 2


@pytest.mark.django_db
def test_keys_differing_only_in_utm_content_are_distinct_rows(
    mock_site_context, site
) -> None:
    increment_first_touch(
        site=site,
        day="2026-01-01",
        key_hash=_key_hash(utm_content="banner"),
        **_key_fields(utm_content="banner"),
    )

    increment_first_touch(
        site=site,
        day="2026-01-01",
        key_hash=_key_hash(utm_content="video"),
        **_key_fields(utm_content="video"),
    )

    assert FirstTouchCount.objects.filter(site=site, day="2026-01-01").count() == 2


@pytest.mark.django_db
def test_third_novel_key_past_the_cap_increments_the_overflow_row(
    mock_site_context, site, settings
) -> None:
    settings.REFERRAL_TRACKING_FIRST_TOUCH_KEY_CAP = 2
    increment_first_touch(
        site=site,
        day="2026-01-01",
        key_hash=_key_hash(utm_source="one"),
        **_key_fields(utm_source="one"),
    )
    increment_first_touch(
        site=site,
        day="2026-01-01",
        key_hash=_key_hash(utm_source="two"),
        **_key_fields(utm_source="two"),
    )

    increment_first_touch(
        site=site,
        day="2026-01-01",
        key_hash=_key_hash(utm_source="three"),
        **_key_fields(utm_source="three"),
    )

    overflow_hash = attribution_key_hash("\x00overflow")
    overflow_row = FirstTouchCount.objects.get(
        site=site, day="2026-01-01", key_hash=overflow_hash
    )
    assert overflow_row.is_overflow is True
    assert overflow_row.count == 1
    assert overflow_row.advert_code == ""
    assert overflow_row.utm_source == ""


@pytest.mark.django_db
def test_third_novel_key_past_the_cap_creates_no_key_row_for_it(
    mock_site_context, site, settings
) -> None:
    settings.REFERRAL_TRACKING_FIRST_TOUCH_KEY_CAP = 2
    increment_first_touch(
        site=site,
        day="2026-01-01",
        key_hash=_key_hash(utm_source="one"),
        **_key_fields(utm_source="one"),
    )
    increment_first_touch(
        site=site,
        day="2026-01-01",
        key_hash=_key_hash(utm_source="two"),
        **_key_fields(utm_source="two"),
    )

    increment_first_touch(
        site=site,
        day="2026-01-01",
        key_hash=_key_hash(utm_source="three"),
        **_key_fields(utm_source="three"),
    )

    assert not FirstTouchCount.objects.filter(
        site=site, day="2026-01-01", key_hash=_key_hash(utm_source="three")
    ).exists()


@pytest.mark.django_db
def test_an_existing_key_past_the_cap_still_increments_its_own_row(
    mock_site_context, site, settings
) -> None:
    settings.REFERRAL_TRACKING_FIRST_TOUCH_KEY_CAP = 1
    key_fields = _key_fields()
    key_hash = _key_hash()
    increment_first_touch(site=site, day="2026-01-01", key_hash=key_hash, **key_fields)

    increment_first_touch(site=site, day="2026-01-01", key_hash=key_hash, **key_fields)

    row = FirstTouchCount.objects.get(site=site, day="2026-01-01", key_hash=key_hash)
    assert row.count == 2


@pytest.mark.django_db
def test_the_overflow_row_is_not_counted_against_the_cap(
    mock_site_context, site, settings
) -> None:
    settings.REFERRAL_TRACKING_FIRST_TOUCH_KEY_CAP = 1
    increment_first_touch(
        site=site,
        day="2026-01-01",
        key_hash=_key_hash(utm_source="one"),
        **_key_fields(utm_source="one"),
    )
    # The cap is already met, so this mints the overflow row rather than its own.
    increment_first_touch(
        site=site,
        day="2026-01-01",
        key_hash=_key_hash(utm_source="two"),
        **_key_fields(utm_source="two"),
    )

    # A third novel key still finds the overflow row rather than being blocked
    # by a cap that would otherwise count the overflow row itself.
    increment_first_touch(
        site=site,
        day="2026-01-01",
        key_hash=_key_hash(utm_source="three"),
        **_key_fields(utm_source="three"),
    )

    overflow_hash = attribution_key_hash("\x00overflow")
    overflow_row = FirstTouchCount.objects.get(
        site=site, day="2026-01-01", key_hash=overflow_hash
    )
    assert overflow_row.count == 2


@pytest.mark.django_db
def test_concurrent_insert_of_the_same_key_recovers_without_raising(
    mock_site_context, site
) -> None:
    row = FirstTouchCountFactory(count=1)

    create_or_increment_first_touch(
        site=site,
        day=row.day,
        key_hash=row.key_hash,
        is_overflow=False,
        advert_code=row.advert_code,
        utm_source=row.utm_source,
        utm_medium=row.utm_medium,
        utm_campaign=row.utm_campaign,
        utm_content=row.utm_content,
        utm_term=row.utm_term,
    )

    row.refresh_from_db()
    assert row.count == 2
