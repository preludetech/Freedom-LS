"""Shared pytest fixtures for all tests."""

import base64
import tempfile
from collections.abc import Callable, Iterable, Mapping, Sequence
from pathlib import Path
from typing import TYPE_CHECKING, cast
from urllib.parse import urlparse

import pytest

from django.test import Client, RequestFactory
from django.urls import reverse

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.tests.factories import SiteFactory

# Playwright tests in every app's tests/playwright/ directory, and downstream projects
# that star-import this module, reach these fixtures through the root conftest. Naming
# them keeps the module's own imports (User, expect, Page, ...) from travelling too.
from freedom_ls.tests.playwright_fixtures import (
    logged_in_page,
    logged_in_user,
    playwright,
    reset_local_storage,
)
from freedom_ls.tests.site_context import site_context
from freedom_ls.tests.storages import (
    PathlessFileSystemStorage,
    bind_pathless_logo_storage,
)

_ONE_PIXEL_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg=="
)

if TYPE_CHECKING:
    from pytest_django.live_server_helper import LiveServer

    from freedom_ls.accounts.models import User
    from freedom_ls.content_engine.models import Course


@pytest.fixture(autouse=True)
def _disable_force_site_name(settings):
    """Ensure FORCE_SITE_NAME is always None during tests."""
    settings.FORCE_SITE_NAME = None


@pytest.fixture(autouse=True)
def _isolate_media_root(settings, tmp_path):
    """Redirect MEDIA_ROOT to a per-test tmp dir.

    Without this, every test that saves a file (an organisation logo, for
    example) writes into the real working-tree media/ directory. upload_to
    keys on a fresh UUID pk, so those files are never overwritten and never
    cleaned up — media/ is gitignored, so the growth is invisible until the
    disk fills up.
    """
    settings.MEDIA_ROOT = tmp_path


@pytest.fixture
def pathless_logo_storage(tmp_path, monkeypatch) -> PathlessFileSystemStorage:
    """Put a storage double whose `.path()` raises behind the logo fields.

    Not autouse: most tests want the ordinary storage. This one exists to
    prove that a specific code path never calls `.path()`, whatever backend
    is configured -- so it is opted into only by the tests making that claim.
    """
    return bind_pathless_logo_storage(monkeypatch, tmp_path)


@pytest.fixture(autouse=True)
def _disable_preview_overrides(settings):
    """Force both course-access preview overrides off by default.

    settings_dev turns OVERRIDE_COURSE_VISIBILITY_TO_VISIBLE and
    OVERRIDE_COURSE_ACCESS_TO_FREE on for manual QA of the preview modes. Tests run
    under settings_dev, so without this the whole suite would inherit the previews
    and exercise the wrong branch. Pinning them off makes the default contract
    deterministic; tests that need a preview on opt in via override_settings(...).
    """
    settings.OVERRIDE_COURSE_VISIBILITY_TO_VISIBLE = False
    settings.OVERRIDE_COURSE_ACCESS_TO_FREE = False


@pytest.fixture(autouse=True)
def _clear_course_access_backend_cache():
    """Reset the cached course-access backend before and after each test.

    get_course_access_backend() is @functools.cache'd for the process lifetime.
    Without this fixture, tests using override_settings(COURSE_ACCESS_BACKEND=...)
    can leave a stale cached instance that bleeds into subsequent tests, making
    order-dependent failures. Clearing before+after each test ensures every test
    resolves the backend from settings.COURSE_ACCESS_BACKEND fresh.

    Tests that use override_settings must also call cache_clear() themselves if
    they need the override active for the duration of their own body — see loader.py
    for details.
    """
    from freedom_ls.course_access.loader import get_course_access_backend

    get_course_access_backend.cache_clear()
    yield
    get_course_access_backend.cache_clear()


@pytest.fixture(autouse=True)
def _clear_rule_kind_cache():
    """Reset the cached rule kinds before and after each test.

    get_rule_kind() is @functools.cache'd for the process lifetime; a test that
    overrides REGISTRATION_RULE_KINDS would otherwise leak its kind. Imported
    only when the app is installed, so the suite still runs without it.
    """
    from django.apps import apps

    if not apps.is_installed("freedom_ls.registration_rules"):
        yield
        return
    from freedom_ls.registration_rules.loader import get_rule_kind

    get_rule_kind.cache_clear()
    yield
    get_rule_kind.cache_clear()


@pytest.fixture(autouse=True)
def _clear_messaging_policy_cache():
    """Reset the cached messaging policy before and after each test.

    get_messaging_policy() is @functools.cache'd for the process lifetime, so a
    test that overrides MESSAGING_POLICY would otherwise leak its instance.
    """
    from freedom_ls.comms.messaging_loader import get_messaging_policy

    get_messaging_policy.cache_clear()
    yield
    get_messaging_policy.cache_clear()


@pytest.fixture(autouse=True)
def _clear_deadline_policy_cache():
    """Reset the cached deadline policy before and after each test.

    get_deadline_policy() is @functools.cache'd for the process lifetime, so a
    test that overrides DEADLINE_POLICY would otherwise leak its instance.
    """
    from freedom_ls.deadlines.loader import get_deadline_policy

    get_deadline_policy.cache_clear()
    yield
    get_deadline_policy.cache_clear()


def reverse_url(
    live_server: "LiveServer",
    viewname: str,
    urlconf: str | None = None,
    args: Sequence[object] | None = None,
    kwargs: Mapping[str, object] | None = None,
    current_app: str | None = None,
) -> str:
    """Absolute URL of `viewname` on the live server.

    A plain function, not a fixture: several apps' tests import it by hand.
    """
    end = reverse(viewname, urlconf, args, kwargs, current_app)
    return f"{live_server.url}{end}"


@pytest.fixture
def site(request):
    """Create a test site. Can be parametrized with a name."""
    # Check if parametrized with a name
    if hasattr(request, "param"):
        name = request.param
        domain = name.lower()
    else:
        name = "TestSite"
        domain = "testsite"

    return SiteFactory(name=name, domain=domain)


@pytest.fixture
def make_temp_file():
    """Create a temporary YAML file and clean it up after test."""
    temp_file = None

    def _create_file(suffix, content):
        nonlocal temp_file
        with tempfile.NamedTemporaryFile(mode="w", suffix=suffix, delete=False) as f:
            f.write(content)
            temp_file = Path(f.name)
        return temp_file

    yield _create_file

    # Cleanup
    if temp_file and temp_file.exists():
        temp_file.unlink()


@pytest.fixture
def mock_site_context(site):
    """Make `site` the ambient site for SiteAwareModel, templates and the role registry."""
    with site_context(site):
        yield site


@pytest.fixture
def logged_in_client():
    """Factory: a Django test client logged in as the given user."""

    def _make(user: "User") -> Client:
        client = Client()
        client.force_login(user)
        return client

    return _make


@pytest.fixture
def staff_client(mock_site_context, logged_in_client):
    """The Django admin as a superuser -- admin classes under test here carry
    no role-based narrowing of their own."""
    return logged_in_client(UserFactory(superuser=True))


@pytest.fixture
def course_with_topic(mock_site_context):
    """Factory: a course (default free) with one topic item — the minimum viewable course."""
    from freedom_ls.content_engine.factories import CourseFactory, TopicFactory

    def _make(*, access_type: str = "free", **kwargs) -> "Course":
        course = cast(
            "Course",
            CourseFactory(access_config={"access_type": access_type}, **kwargs),
        )
        course.items.create(child=TopicFactory(), order=0)
        return course

    return _make


@pytest.fixture
def article_with_image(mock_site_context):
    """A published article whose `image` resolves to a one-pixel PNG File."""
    from django.core.files.base import ContentFile

    from freedom_ls.content_engine.factories import ArticleFactory, FileFactory

    FileFactory(
        file_path="articles/photo.png",
        file=ContentFile(_ONE_PIXEL_PNG, "photo.png"),
    )
    return ArticleFactory(
        file_path="articles/with-image.md",
        image="photo.png",
        image_alt="A grey square",
    )


@pytest.fixture
def site_aware_request(mock_site_context):
    return RequestFactory()


@pytest.fixture
def live_server_site(live_server, site):
    # Update site domain to match the live_server
    parsed_url = urlparse(live_server.url)
    site.domain = parsed_url.netloc
    site.save()
    return site


@pytest.fixture
def mock_legal_blobs(monkeypatch, tmp_path: Path, settings):
    """Replace `read_blob_at_head` with an in-memory blob store.

    Avoids spinning up a real git repo for tests that only care about
    higher-level legal-doc behaviour. Returns a function the test calls to
    register `(rel_path, content)` pairs; SHA is auto-derived from the path.

    Behaviour mirrors the real loader: missing rel_paths raise
    ``FileNotFoundError`` so the production code path is exercised.
    """
    blobs: dict[str, tuple[str, str]] = {}

    def fake_read_blob_at_head(rel_path: str) -> tuple[str, str]:
        if rel_path not in blobs:
            raise FileNotFoundError(f"no blob for {rel_path}")
        return blobs[rel_path]

    monkeypatch.setattr(
        "freedom_ls.accounts.legal_docs.read_blob_at_head",
        fake_read_blob_at_head,
    )

    # The icon loader reads BASE_DIR too, and pages rendered under this stub
    # (the 404 page among them) carry icons. Link the real node_modules into
    # the stub root so they resolve whether or not the loader's cache is warm.
    node_modules = Path(settings.BASE_DIR) / "node_modules"
    if node_modules.is_dir():
        (tmp_path / "node_modules").symlink_to(node_modules, target_is_directory=True)

    settings.BASE_DIR = tmp_path
    settings.LEGAL_DOCS_MANIFEST_PATH = None

    def add(rel_path: str, content: str, sha: str | None = None) -> None:
        # Synthesise a deterministic 40-char hex SHA from the path so tests
        # can still assert on `git_hash` length / uniqueness.
        derived = sha or (f"{abs(hash(rel_path)):040x}"[:40])
        blobs[rel_path] = (derived, content)

    return add


def _seed_default_legal_docs(
    add: Callable[..., None],
    docs: Iterable[tuple[str, str]] = (),
) -> None:
    """Helper: register the standard `_default/<type>.md` blobs."""
    for doc_type, content in docs:
        add(f"legal_docs/_default/{doc_type}.md", content)


@pytest.fixture
def legal_repo_mock(mock_legal_blobs):
    """Pre-seed `_default/{terms,privacy}.md` with minimal frontmatter.

    Drop-in replacement for the previous on-disk `legal_repo` fixture, but
    without ``subprocess`` calls. Returns the same ``add`` function so tests
    can layer site-specific overrides.
    """
    terms = (
        '---\nversion: "1.5"\ntitle: "Terms"\ntype: "terms"\n'
        'effective_date: "2026-04-27"\n---\n\nBody.\n'
    )
    privacy = (
        '---\nversion: "1.5"\ntitle: "Privacy"\ntype: "privacy"\n'
        'effective_date: "2026-04-27"\n---\n\nBody.\n'
    )
    _seed_default_legal_docs(
        mock_legal_blobs,
        docs=(("terms", terms), ("privacy", privacy)),
    )
    return mock_legal_blobs
