"""Test UUID handling in content_save.py"""

import tempfile
import yaml
import pytest
from pathlib import Path
from django.contrib.sites.models import Site

from content_engine.models import Form, FormPage
from content_engine.management.commands.content_save import (
    save_form_page,
    save_form_text,
    save_form_question,
)
from content_engine.validate import parse_single_file


@pytest.fixture
def site():
    """Create a test site."""
    site, _ = Site.objects.get_or_create(
        name="TestSite", defaults={"domain": "testsite"}
    )
    return site


@pytest.fixture
def form(site):
    """Create a test form."""
    return Form.objects.create(
        site_id=site, title="Test Form", strategy="CATEGORY_VALUE_SUM"
    )


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


@pytest.mark.django_db
def test_form_page_with_uuid_no_duplicates_on_multiple_saves(
    site, form, make_temp_file
):
    """Test that saving a FormPage with same UUID multiple times doesn't create duplicates."""

    # Create a temporary yaml file for a FormPage without UUID
    yaml_content = {
        "content_type": "FORM_PAGE",
        "title": "Test Form Page",
        "subtitle": "Test Subtitle",
    }
    file_content = "---\n" + yaml.dump(yaml_content)
    temp_file = make_temp_file(suffix=".yaml", content=file_content)

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
    with open(temp_file, "r") as f:
        updated_content = yaml.safe_load(f.read().split("---")[1])
        assert "uuid" in updated_content
        assert updated_content["uuid"] == str(created_uuid)

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
    with open(temp_file, "r") as f:
        final_content = yaml.safe_load(f.read().split("---")[1])
        assert final_content["uuid"] == str(created_uuid)


@pytest.mark.django_db
def test_saving_form_questions_and_text_adds_uuids_to_file(site, form, make_temp_file):
    """Test that saving form questions and text adds UUIDs to the file."""

    # Create YAML with form page, question, and text
    original_yaml = """---
content_type: FORM_PAGE
title: Test Page
---
content_type: FORM_QUESTION
question: What is your favorite color?
type: multiple_choice
required: true
options:
  - text: Red
    value: 1
  - text: Blue
    value: 2
---
content_type: FORM_TEXT
text: This is some instructional text
"""

    temp_file = make_temp_file(suffix=".yaml", content=original_yaml)

    # Parse and save
    parsed = parse_single_file(temp_file)
    assert len(parsed) == 3

    # Verify no UUIDs initially
    assert parsed[0].uuid is None
    assert parsed[1].uuid is None
    assert parsed[2].uuid is None

    # Save to database

    page = save_form_page(parsed[0], form, site, order=0)
    question = save_form_question(parsed[1], page, site, order=0)
    text = save_form_text(parsed[2], page, site, order=1)

    # Read file back
    with open(temp_file, "r") as f:
        result = f.read()

    # Parse sections
    sections = result.split("---")[1:]  # Skip empty first element
    page_data = yaml.safe_load(sections[0])
    question_data = yaml.safe_load(sections[1])
    text_data = yaml.safe_load(sections[2])

    # Verify UUIDs were added
    assert "uuid" in page_data
    assert page_data["uuid"] == str(page.id)

    assert "uuid" in question_data
    assert question_data["uuid"] == str(question.id)

    assert "uuid" in text_data
    assert text_data["uuid"] == str(text.id)

    # Verify original content is preserved
    assert page_data["title"] == "Test Page"
    assert question_data["question"] == "What is your favorite color?"
    assert question_data["type"] == "multiple_choice"
    assert len(question_data["options"]) == 2
    assert text_data["text"] == "This is some instructional text"


@pytest.mark.django_db
def test_saving_form_question_options_saves_uuids_to_file(site, form, make_temp_file):
    """Test that saving a form question with options preserves the options correctly and adds UUID."""

    # Create YAML with form page and question with options
    original_yaml = """---
content_type: FORM_PAGE
title: Test Page
---
content_type: FORM_QUESTION
question: What is your favorite programming language?
type: multiple_choice
required: true
category: Programming
options:
  - text: Python
    value: 1
  - text: JavaScript
    value: 2
  - text: Rust
    value: 3
"""

    temp_file = make_temp_file(suffix=".yaml", content=original_yaml)

    # Parse and save
    parsed = parse_single_file(temp_file)
    assert len(parsed) == 2

    # Verify no UUIDs initially
    assert parsed[0].uuid is None
    assert parsed[1].uuid is None

    # Save to database
    page = save_form_page(parsed[0], form, site, order=0)
    question = save_form_question(parsed[1], page, site, order=0)

    # Read file back
    with open(temp_file, "r") as f:
        result = f.read()

    # Parse sections
    sections = result.split("---")[1:]  # Skip empty first element
    # page_data = yaml.safe_load(sections[0])
    question_data = yaml.safe_load(sections[1])

    # Verify UUIDs were added
    # OPTIONS DO HAVE UUIDS
    # Get the options from the database
    from content_engine.models import QuestionOption
    db_options = list(QuestionOption.objects.filter(question=question).order_by('order'))

    # Assert each option has the correct UUID matching the database
    assert len(question_data["options"]) == len(db_options)
    for idx, option in enumerate(question_data["options"]):
        assert "uuid" in option
        assert option["uuid"] == str(db_options[idx].id)


@pytest.mark.django_db
def test_yaml_dump_does_not_add_excessive_whitespace(site, form, make_temp_file):
    """Test that yaml.dump doesn't add blank lines when updating multi-document file with UUIDs."""

    # Create original multi-document YAML with specific compact format
    original_yaml = "---\ncontent_type: FORM_PAGE\ntitle: Test Page\n---\ncontent_type: FORM_TEXT\ntext: Some text\n"
    temp_file = make_temp_file(suffix=".yaml", content=original_yaml)

    # Save to add UUIDs
    parsed = parse_single_file(temp_file)
    page = save_form_page(parsed[0], form, site, order=0)
    save_form_text(parsed[1], page, site, order=0)

    # Read back
    with open(temp_file, "r") as f:
        result = f.read()

    # Parse to get UUIDs
    sections = result.split("---")[1:]  # Skip empty first element
    section1_data = yaml.safe_load(sections[0])
    section2_data = yaml.safe_load(sections[1])

    # Expected: compact YAML with no blank lines
    expected_result = f"---\ncontent_type: FORM_PAGE\ntitle: Test Page\nuuid: {section1_data['uuid']}\n---\ncontent_type: FORM_TEXT\ntext: Some text\nuuid: {section2_data['uuid']}\n"

    assert result == expected_result, (
        f"YAML formatting incorrect.\nExpected:\n{repr(expected_result)}\nGot:\n{repr(result)}"
    )


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
    with open(temp_file, "r") as f:
        result = f.read()

    # Parse to get UUIDs
    sections = result.split("---")[1:]
    section1_data = yaml.safe_load(sections[0])
    section2_data = yaml.safe_load(sections[1])

    # Verify multi-line text is preserved (using literal block style, not quoted)
    # Accept both | and |- as valid literal block styles
    assert "text: |" in result, (
        f"Multi-line text should use literal block style (|), got:\n{repr(result)}"
    )

    # Verify the parsed content is correct (multi-line text preserved)
    # Note: |- style strips trailing newline, which is acceptable
    assert (
        section2_data["text"]
        in [
            "hello there\nthis is a multi-line\nstring\n",  # | style (keeps trailing newline)
            "hello there\nthis is a multi-line\nstring",  # |- style (strips trailing newline)
        ]
    ), f"Multi-line text content incorrect: {repr(section2_data['text'])}"

    # Verify no extra blank lines were added (should have exactly 2 sections)
    assert len([s for s in sections if s.strip()]) == 2, (
        "Should have exactly 2 YAML sections"
    )
