"""Loading COURSE_CATEGORIES declarations and course category/dashboard_category references."""

import tempfile
from pathlib import Path

import pytest
import yaml

from django.db import IntegrityError

from freedom_ls.accounts.factories import SiteFactory
from freedom_ls.content_engine.management.commands.content_save import (
    save_content_to_db,
)
from freedom_ls.content_engine.models import (
    ContentCollectionItem,
    Course,
    CourseCategory,
)


def _read_yaml_document(file_path: Path) -> dict:
    with open(file_path, encoding="utf-8") as f:
        content = f.read()
    sections = [s.strip() for s in content.split("---") if s.strip()]
    data = yaml.safe_load(sections[0])
    assert isinstance(data, dict)
    return data


@pytest.mark.django_db
def test_uuid_write_back_touches_only_entries_lacking_one(site, mock_site_context):
    """A first load writes a uuid into every entry that lacked one; an untouched second load is byte-identical."""
    with tempfile.TemporaryDirectory() as tmpdir:
        repo_dir = Path(tmpdir)
        existing_uuid = "10000000-0000-0000-0000-000000000001"
        (repo_dir / "course_categories.yaml").write_text(f"""---
content_type: COURSE_CATEGORIES
categories:
  - slug: start-here
    title: Start here
    uuid: {existing_uuid}
  - slug: technical
    title: Technical
""")

        save_content_to_db(repo_dir, site.name)

        first_load_data = _read_yaml_document(repo_dir / "course_categories.yaml")
        entries = first_load_data["categories"]
        assert entries[0]["uuid"] == existing_uuid
        assert entries[0]["slug"] == "start-here"
        assert entries[1]["uuid"] is not None
        assert entries[1]["slug"] == "technical"

        first_load_bytes = (repo_dir / "course_categories.yaml").read_bytes()

        save_content_to_db(repo_dir, site.name)

        second_load_bytes = (repo_dir / "course_categories.yaml").read_bytes()
        assert second_load_bytes == first_load_bytes
        assert CourseCategory.objects.filter(site=site).count() == 2


@pytest.mark.django_db
def test_authored_slug_survives_a_title_edit(site, mock_site_context):
    """A category's authored slug is not re-derived from its title, unlike every other content type."""
    category_uuid = "20000000-0000-0000-0000-000000000001"
    with tempfile.TemporaryDirectory() as tmpdir:
        repo_dir = Path(tmpdir)
        categories_file = repo_dir / "course_categories.yaml"
        categories_file.write_text(f"""---
content_type: COURSE_CATEGORIES
categories:
  - slug: technical
    title: Technical Skills
    uuid: {category_uuid}
""")
        save_content_to_db(repo_dir, site.name)

        categories_file.write_text(f"""---
content_type: COURSE_CATEGORIES
categories:
  - slug: technical
    title: Technical Skills, Revised
    uuid: {category_uuid}
""")
        save_content_to_db(repo_dir, site.name)

        category = CourseCategory.objects.get(site=site, id=category_uuid)
        assert category.slug == "technical"
        assert category.title == "Technical Skills, Revised"
        assert CourseCategory.objects.filter(site=site).count() == 1


@pytest.mark.django_db
def test_slug_rename_on_a_fixed_uuid_renames_the_row(site, mock_site_context):
    """Renaming an entry's slug while its uuid stays put renames the existing row rather than creating a second."""
    category_uuid = "30000000-0000-0000-0000-000000000001"
    with tempfile.TemporaryDirectory() as tmpdir:
        repo_dir = Path(tmpdir)
        categories_file = repo_dir / "course_categories.yaml"
        categories_file.write_text(f"""---
content_type: COURSE_CATEGORIES
categories:
  - slug: technical
    title: Technical
    uuid: {category_uuid}
""")
        save_content_to_db(repo_dir, site.name)

        categories_file.write_text(f"""---
content_type: COURSE_CATEGORIES
categories:
  - slug: engineering
    title: Technical
    uuid: {category_uuid}
""")
        save_content_to_db(repo_dir, site.name)

        assert CourseCategory.objects.filter(site=site).count() == 1
        category = CourseCategory.objects.get(site=site, id=category_uuid)
        assert category.slug == "engineering"


@pytest.mark.django_db
def test_order_follows_list_position_and_changes_on_reorder(site, mock_site_context):
    first_uuid = "40000000-0000-0000-0000-000000000001"
    second_uuid = "40000000-0000-0000-0000-000000000002"
    with tempfile.TemporaryDirectory() as tmpdir:
        repo_dir = Path(tmpdir)
        categories_file = repo_dir / "course_categories.yaml"
        categories_file.write_text(f"""---
content_type: COURSE_CATEGORIES
categories:
  - slug: alpha
    title: Alpha
    uuid: {first_uuid}
  - slug: beta
    title: Beta
    uuid: {second_uuid}
""")
        save_content_to_db(repo_dir, site.name)

        alpha = CourseCategory.objects.get(site=site, id=first_uuid)
        beta = CourseCategory.objects.get(site=site, id=second_uuid)
        assert alpha.order == 0
        assert beta.order == 1

        categories_file.write_text(f"""---
content_type: COURSE_CATEGORIES
categories:
  - slug: beta
    title: Beta
    uuid: {second_uuid}
  - slug: alpha
    title: Alpha
    uuid: {first_uuid}
""")
        save_content_to_db(repo_dir, site.name)

        alpha.refresh_from_db()
        beta.refresh_from_db()
        assert beta.order == 0
        assert alpha.order == 1


@pytest.mark.django_db
def test_single_category_shorthand_loads_both_fields(site, mock_site_context):
    """A course declaring one category and no dashboard_category loads with both set."""
    with tempfile.TemporaryDirectory() as tmpdir:
        repo_dir = Path(tmpdir)
        (repo_dir / "course_categories.yaml").write_text("""---
content_type: COURSE_CATEGORIES
categories:
  - slug: technical
    title: Technical
""")
        course_dir = repo_dir / "demo_course"
        course_dir.mkdir()
        (course_dir / "course.md").write_text("""---
content_type: COURSE
title: Demo Course
categories:
  - technical
uuid: 50000000-0000-0000-0000-000000000001
---
""")

        save_content_to_db(repo_dir, site.name)

        course = Course.objects.get(site=site, title="Demo Course")
        assert [c.slug for c in course.categories.all()] == ["technical"]
        assert course.dashboard_category.slug == "technical"


@pytest.mark.django_db
def test_dropping_a_category_slug_and_reloading_removes_that_membership(
    site, mock_site_context
):
    """A course's category set is replaced by a reload, not merged into."""
    with tempfile.TemporaryDirectory() as tmpdir:
        repo_dir = Path(tmpdir)
        (repo_dir / "course_categories.yaml").write_text("""---
content_type: COURSE_CATEGORIES
categories:
  - slug: technical
    title: Technical
  - slug: start-here
    title: Start here
""")
        course_dir = repo_dir / "demo_course"
        course_dir.mkdir()
        (course_dir / "course.md").write_text("""---
content_type: COURSE
title: Demo Course
categories:
  - technical
  - start-here
dashboard_category: technical
uuid: 60000000-0000-0000-0000-000000000001
---
""")
        save_content_to_db(repo_dir, site.name)
        course = Course.objects.get(site=site, title="Demo Course")
        assert {c.slug for c in course.categories.all()} == {"technical", "start-here"}

        (course_dir / "course.md").write_text("""---
content_type: COURSE
title: Demo Course
categories:
  - technical
dashboard_category: technical
uuid: 60000000-0000-0000-0000-000000000001
---
""")
        save_content_to_db(repo_dir, site.name)
        course.refresh_from_db()
        assert {c.slug for c in course.categories.all()} == {"technical"}


@pytest.mark.django_db
def test_loose_category_file_in_a_course_directory_is_not_adopted_as_a_child(
    site, mock_site_context
):
    """save_content_to_db called directly does not adopt a stray category file as a course child."""
    with tempfile.TemporaryDirectory() as tmpdir:
        course_dir = Path(tmpdir) / "demo_course"
        course_dir.mkdir()
        (course_dir / "course.md").write_text("""---
content_type: COURSE
title: Demo Course
uuid: 70000000-0000-0000-0000-000000000001
---
""")
        (course_dir / "1. topic.md").write_text("""---
content_type: TOPIC
title: Topic One
uuid: 70000000-0000-0000-0000-000000000002
---

Topic content
""")
        # A loose declaration file, inside the course directory rather than
        # the repo root -- content_validate rejects this location (step 4),
        # but save_content_to_db is also called directly and must not treat
        # it as a child of the course it happens to sit beside.
        (course_dir / "course_categories.yaml").write_text("""---
content_type: COURSE_CATEGORIES
categories:
  - slug: technical
    title: Technical
""")

        save_content_to_db(course_dir, site.name)

        course = Course.objects.get(site=site, title="Demo Course")
        children_titles = [item.child.title for item in course.items.all()]
        assert children_titles == ["Topic One"]
        # The category row is still saved -- only child adoption is skipped.
        assert CourseCategory.objects.filter(site=site, slug="technical").exists()


@pytest.mark.django_db
def test_a_failure_later_in_the_load_leaves_no_course_with_a_partial_category_set(
    site, mock_site_context, mocker
):
    """save_content_to_db is atomic: a failure anywhere rolls back every category assignment too."""
    mocker.patch.object(
        ContentCollectionItem.objects,
        "update_or_create",
        side_effect=RuntimeError("forced failure for the atomicity test"),
    )
    with tempfile.TemporaryDirectory() as tmpdir:
        repo_dir = Path(tmpdir)
        (repo_dir / "course_categories.yaml").write_text("""---
content_type: COURSE_CATEGORIES
categories:
  - slug: technical
    title: Technical
""")
        course_dir = repo_dir / "demo_course"
        course_dir.mkdir()
        (course_dir / "course.md").write_text("""---
content_type: COURSE
title: Demo Course
categories:
  - technical
uuid: 80000000-0000-0000-0000-000000000001
---
""")
        (course_dir / "1. topic.md").write_text("""---
content_type: TOPIC
title: Topic One
uuid: 80000000-0000-0000-0000-000000000002
---

Topic content
""")

        with pytest.raises(RuntimeError):
            save_content_to_db(repo_dir, site.name)

        assert not Course.objects.filter(site=site).exists()
        assert not CourseCategory.objects.filter(site=site).exists()


@pytest.mark.django_db
def test_two_sites_get_their_own_rows_reusing_slugs_and_titles():
    """Two sites with their own declarations, reusing each other's slugs, get their own rows."""
    site_a = SiteFactory()
    site_b = SiteFactory()

    with tempfile.TemporaryDirectory() as tmpdir_a:
        repo_a = Path(tmpdir_a)
        (repo_a / "course_categories.yaml").write_text("""---
content_type: COURSE_CATEGORIES
categories:
  - slug: technical
    title: Technical (Site A)
""")
        save_content_to_db(repo_a, site_a.name)

    with tempfile.TemporaryDirectory() as tmpdir_b:
        repo_b = Path(tmpdir_b)
        (repo_b / "course_categories.yaml").write_text("""---
content_type: COURSE_CATEGORIES
categories:
  - slug: technical
    title: Technical (Site B)
""")
        save_content_to_db(repo_b, site_b.name)

    category_a = CourseCategory._base_manager.get(site=site_a, slug="technical")
    category_b = CourseCategory._base_manager.get(site=site_b, slug="technical")
    assert category_a.id != category_b.id
    assert category_a.title == "Technical (Site A)"
    assert category_b.title == "Technical (Site B)"
    assert CourseCategory._base_manager.filter(site=site_b).count() == 1


@pytest.mark.django_db
def test_loading_one_declaration_into_two_sites_fails_on_duplicate_primary_key():
    """Pinning a pre-existing limit of the content loader: a shared uuid cannot serve two sites in one database."""
    site_a = SiteFactory()
    site_b = SiteFactory()
    category_uuid = "90000000-0000-0000-0000-000000000001"

    with tempfile.TemporaryDirectory() as tmpdir:
        repo_dir = Path(tmpdir)
        (repo_dir / "course_categories.yaml").write_text(f"""---
content_type: COURSE_CATEGORIES
categories:
  - slug: technical
    title: Technical
    uuid: {category_uuid}
""")
        save_content_to_db(repo_dir, site_a.name)

        with pytest.raises(IntegrityError):
            save_content_to_db(repo_dir, site_b.name)
