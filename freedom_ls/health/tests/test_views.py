from concurrent.futures import ThreadPoolExecutor

import pytest

from django.urls import reverse

from freedom_ls.health.views import ReadinessView


@pytest.mark.urls("freedom_ls.health.tests.root_urls")
def test_liveness_returns_alive_status_without_touching_db(client):
    response = client.get(reverse("health:liveness"))

    assert response.status_code == 200
    assert response.json() == {"status": "alive"}


@pytest.mark.django_db
@pytest.mark.urls("freedom_ls.health.tests.root_urls")
def test_readiness_returns_200_when_db_is_healthy(client):
    url = reverse("health:readiness")

    # ReadinessView (HealthCheckView) is an async view; the sync test client runs
    # it through AsyncToSync, which refuses to run when the calling thread already
    # has a running event loop. Drive the request from a fresh worker thread so the
    # probe is not coupled to event-loop state other tests may leave in the main
    # thread — production WSGI workers likewise serve it from a loop-free thread.
    # Request JSON so the response skips the HTML template/context processors, which
    # are orthogonal to a probe. The Database check opens its own connection
    # (SELECT 1) independent of the test transaction, so the worker thread is fine.
    with ThreadPoolExecutor(max_workers=1) as pool:
        response = pool.submit(client.get, url, HTTP_ACCEPT="application/json").result()

    assert response.status_code == 200


def test_readiness_default_check_set_includes_database():
    check_names = [type(check).__name__ for check in ReadinessView().get_checks()]

    assert "Database" in check_names
