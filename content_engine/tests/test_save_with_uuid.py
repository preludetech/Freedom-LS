"""Test UUID handling in content_save.py"""

import tempfile
import yaml
import pytest
from pathlib import Path
from django.contrib.sites.models import Site

from content_engine.models import Form, FormPage
from content_engine.management.commands.content_save import save_form_page, save_form_text
from content_engine.validate import parse_single_file


@pytest.fixture
def site():
    """Create a test site."""
    site, _ = Site.objects.get_or_create(
        name="TestSite",
        defaults={'domain': 'testsite'}
    )
    return site


@pytest.fixture
def form(site):
    """Create a test form."""
    return Form.objects.create(
        site_id=site,
        title="Test Form",
        strategy="CATEGORY_VALUE_SUM"
    )


@pytest.fixture
def make_temp_file():
    """Create a temporary YAML file and clean it up after test."""
    temp_file = None

    def _create_file(suffix,content):
        nonlocal temp_file
        with tempfile.NamedTemporaryFile(mode='w', suffix=suffix, delete=False) as f:
            f.write(content)
            temp_file = Path(f.name)
        return temp_file

    yield _create_file

    # Cleanup
    if temp_file and temp_file.exists():
        temp_file.unlink()


@pytest.mark.django_db
def test_form_page_with_uuid_no_duplicates_on_multiple_saves(site, form, make_temp_file):
    """Test that saving a FormPage with same UUID multiple times doesn't create duplicates."""

    # Create a temporary yaml file for a FormPage without UUID
    yaml_content = {
        'content_type': 'FORM_PAGE',
        'title': 'Test Form Page',
        'subtitle': 'Test Subtitle'
    }
    file_content = '---\n' + yaml.dump(yaml_content)
    temp_file = make_temp_file(suffix=".yaml",content=file_content)

    # Parse and save the first time
    parsed_items = parse_single_file(temp_file)
    assert len(parsed_items) == 1
    item1 = parsed_items[0]

    # Verify no UUID initially
    assert item1.uuid is None

    # Save to database (should create UUID and update file)
    initial_count = FormPage.objects.count()
    page1 = save_form_page(item1, form, site, order=0)

    assert FormPage.objects.count() == initial_count + 1
    created_uuid = page1.id

    # Verify file was updated with UUID
    with open(temp_file, 'r') as f:
        updated_content = yaml.safe_load(f.read().split('---')[1])
        assert 'uuid' in updated_content
        assert updated_content['uuid'] == str(created_uuid)

    # Parse the file again (should now have UUID)
    parsed_items2 = parse_single_file(temp_file)
    assert len(parsed_items2) == 1
    item2 = parsed_items2[0]

    # Verify UUID is now present
    assert item2.uuid is not None
    assert item2.uuid == str(created_uuid)

    # Save again (should update, not create new)
    page2 = save_form_page(item2, form, site, order=0)

    # Assert UUID unchanged and no duplicates
    assert FormPage.objects.count() == initial_count + 1
    assert page2.id == created_uuid

    # Verify file UUID hasn't changed
    with open(temp_file, 'r') as f:
        final_content = yaml.safe_load(f.read().split('---')[1])
        assert final_content['uuid'] == str(created_uuid)





@pytest.mark.django_db
def test_yaml_dump_does_not_add_excessive_whitespace(site, form, make_temp_file):
    """Test that yaml.dump doesn't add blank lines when updating multi-document file with UUIDs."""

    # Create original multi-document YAML with specific compact format
    original_yaml = "---\ncontent_type: FORM_PAGE\ntitle: Test Page\n---\ncontent_type: FORM_TEXT\ntext: Some text\n"
    temp_file = make_temp_file(suffix=".yaml",content=original_yaml)

    # Save to add UUIDs
    parsed = parse_single_file(temp_file)
    page = save_form_page(parsed[0], form, site, order=0)
    save_form_text(parsed[1], page, site, order=0)

    # Read back
    with open(temp_file, 'r') as f:
        result = f.read()

    # Parse to get UUIDs
    sections = result.split('---')[1:]  # Skip empty first element
    section1_data = yaml.safe_load(sections[0])
    section2_data = yaml.safe_load(sections[1])

    # Expected: compact YAML with no blank lines
    expected_result = f"---\ncontent_type: FORM_PAGE\ntitle: Test Page\nuuid: {section1_data['uuid']}\n---\ncontent_type: FORM_TEXT\ntext: Some text\nuuid: {section2_data['uuid']}\n"

    assert result == expected_result, f"YAML formatting incorrect.\nExpected:\n{repr(expected_result)}\nGot:\n{repr(result)}"


@pytest.mark.django_db
def test_yaml_dump_doesnt_reformat_multi_line_text_fields(site, form, make_temp_file):
    """Test that yaml.dump preserves multi-line text formatting."""

    # Create YAML with multi-line text field
    original_yaml = """---
content_type: FORM_PAGE
title: Test Page
---
content_type: FORM_TEXT
text: |
  hello there
  this is a multi-line
  string
"""

    temp_file = make_temp_file(suffix=".yaml", content=original_yaml)

    # Save the content
    parsed = parse_single_file(temp_file)
    page = save_form_page(parsed[0], form, site, order=0)
    save_form_text(parsed[1], page, site, order=0)

    # Read back
    with open(temp_file, 'r') as f:
        result = f.read()

    # Parse to get UUIDs
    sections = result.split('---')[1:]
    section1_data = yaml.safe_load(sections[0])
    section2_data = yaml.safe_load(sections[1])

    # Verify multi-line text is preserved (using literal block style, not quoted)
    # Accept both | and |- as valid literal block styles
    assert 'text: |' in result, f"Multi-line text should use literal block style (|), got:\n{repr(result)}"

    # Verify the parsed content is correct (multi-line text preserved)
    # Note: |- style strips trailing newline, which is acceptable
    assert section2_data['text'] in [
        "hello there\nthis is a multi-line\nstring\n",  # | style (keeps trailing newline)
        "hello there\nthis is a multi-line\nstring"     # |- style (strips trailing newline)
    ], f"Multi-line text content incorrect: {repr(section2_data['text'])}"

    # Verify no extra blank lines were added (should have exactly 2 sections)
    assert len([s for s in sections if s.strip()]) == 2, "Should have exactly 2 YAML sections"