"""The data migration that turns a sitting's furthest page number into the page itself."""

from __future__ import annotations

import pytest

from django.db import connection
from django.db.migrations.executor import MigrationExecutor

from freedom_ls.form_engine.factories import (
    FormFactory,
    FormPageFactory,
    FormProgressFactory,
)

APP = "freedom_ls_form_engine"
BEFORE = "0011_shuffle"


# transaction=True: the test migrates the schema backwards and forwards.
@pytest.mark.django_db(transaction=True)
def test_each_stored_number_becomes_the_page_it_names(mock_site_context):
    form = FormFactory()
    first, second, third = (FormPageFactory(form=form, order=order) for order in range(3))
    other_form = FormFactory()
    other_first = FormPageFactory(form=other_form, order=0)
    FormPageFactory(form=other_form, order=1)
    not_started = FormProgressFactory(form=form).pk
    on_first = FormProgressFactory(form=form).pk
    on_second = FormProgressFactory(form=form).pk
    past_the_end = FormProgressFactory(form=form).pk
    on_other_form = FormProgressFactory(form=other_form).pk

    executor = MigrationExecutor(connection)
    # Every app's leaf: migrating back also unapplies apps that depend on this one.
    leaf = executor.loader.graph.leaf_nodes()
    executor.migrate([(APP, BEFORE)])
    Historical = executor.loader.project_state([(APP, BEFORE)]).apps.get_model(
        APP, "FormProgress"
    )
    Historical.objects.filter(pk=on_first).update(furthest_page_reached=1)
    Historical.objects.filter(pk=on_second).update(furthest_page_reached=2)
    Historical.objects.filter(pk=past_the_end).update(furthest_page_reached=9)
    Historical.objects.filter(pk=on_other_form).update(furthest_page_reached=1)

    executor = MigrationExecutor(connection)
    executor.loader.build_graph()
    executor.migrate(leaf)
    Current = executor.loader.project_state(
        executor.loader.graph.leaf_nodes(APP)
    ).apps.get_model(APP, "FormProgress")

    assert dict(Current.objects.values_list("pk", "furthest_page_id")) == {
        not_started: None,
        on_first: first.pk,
        on_second: second.pk,
        past_the_end: third.pk,
        on_other_form: other_first.pk,
    }
