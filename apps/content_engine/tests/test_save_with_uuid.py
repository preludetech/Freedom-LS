"""Test UUID handling in content_save.py"""

import yaml
import pytest
from content_engine.models import FormPage
from content_engine.management.commands.content_save import (
    save_form_page,
    save_form_content,
    save_form_question,
    PreservingDumper,
)
from content_engine.validate import parse_single_file


def test_preserving_dumper_uses_literal_style_for_html_content():
    """Test that PreservingDumper correctly uses literal block style for multi-line strings with HTML.

    This tests whether the custom YAML dumper properly handles strings containing:
    - Newlines
    - HTML/XML tags with angle brackets
    - Quoted attributes

    The dumper should output these using literal block style (|) not quoted strings.
    """
    # Create content similar to what's in the demo file
    content_with_html = (
        "Considering blah blah, answer the following:\n"
        "<c-picture  \n"
        '   src="../images/graph1.drawio.svg"\n'
        '   alt="Graph example"\n'
        '   caption="Example of a graph"\n'
        "   />\n"
        "  Blah blah"
    )

    data = {
        "content_type": "FORM_CONTENT",
        "content": content_with_html,
        "uuid": "9c4265c5-9178-47b8-9a9d-074e69e34a40",
    }

    # Dump using PreservingDumper
    result = yaml.dump(
        data, Dumper=PreservingDumper, default_flow_style=False, allow_unicode=True
    )

    # THE BUG: PreservingDumper should use literal block style (|) for multi-line strings,
    # but it's actually outputting quoted strings with \n escapes instead!
    assert "content: |" in result, (
        f"PreservingDumper should use literal block style (|) for multi-line strings.\n"
        f"Instead it's using quoted strings with \\n escapes.\n"
        f"Got:\n{result}"
    )

    # Should NOT use quoted string format
    assert 'content: "' not in result, (
        f"Content should not use quoted string format.\nGot:\n{result}"
    )

    # HTML tags should appear literally, not escaped
    assert "<c-picture" in result
    assert 'src="../images/graph1.drawio.svg"' in result


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
    page1 = save_form_page(item1, form, site, temp_file.parent, order=0)

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
    page2 = save_form_page(item2, form, site, temp_file.parent, order=0)

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
content_type: FORM_CONTENT
content: This is some instructional text
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

    page = save_form_page(parsed[0], form, site, temp_file.parent, order=0)
    question = save_form_question(parsed[1], page, site, order=0)
    text = save_form_content(parsed[2], page, site, order=1)

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
    assert text_data["content"] == "This is some instructional text"


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
    page = save_form_page(parsed[0], form, site, temp_file.parent, order=0)
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

    db_options = list(
        QuestionOption.objects.filter(question=question).order_by("order")
    )

    # Assert each option has the correct UUID matching the database
    assert len(question_data["options"]) == len(db_options)
    for idx, option in enumerate(question_data["options"]):
        assert "uuid" in option
        assert option["uuid"] == str(db_options[idx].id)


@pytest.mark.django_db
def test_yaml_dump_does_not_add_excessive_whitespace(site, form, make_temp_file):
    """Test that yaml.dump doesn't add blank lines when updating multi-document file with UUIDs."""

    # Create original multi-document YAML with specific compact format
    original_yaml = "---\ncontent_type: FORM_PAGE\ntitle: Test Page\n---\ncontent_type: FORM_CONTENT\ncontent: Some text\n"
    temp_file = make_temp_file(suffix=".yaml", content=original_yaml)

    # Save to add UUIDs
    parsed = parse_single_file(temp_file)
    page = save_form_page(parsed[0], form, site, temp_file.parent, order=0)
    save_form_content(parsed[1], page, site, order=0)

    # Read back
    with open(temp_file, "r") as f:
        result = f.read()

    # Parse to get UUIDs
    sections = result.split("---")[1:]  # Skip empty first element
    section1_data = yaml.safe_load(sections[0])
    section2_data = yaml.safe_load(sections[1])

    # Expected: compact YAML with no blank lines
    expected_result = f"---\ncontent_type: FORM_PAGE\ntitle: Test Page\nuuid: {section1_data['uuid']}\n---\ncontent: Some text\ncontent_type: FORM_CONTENT\nuuid: {section2_data['uuid']}\n"

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
content_type: FORM_CONTENT
content: |
  hello there
  this is a multi-line
  string
"""

    temp_file = make_temp_file(suffix=".yaml", content=original_yaml)

    # Save the content
    parsed = parse_single_file(temp_file)
    page = save_form_page(parsed[0], form, site, temp_file.parent, order=0)
    save_form_content(parsed[1], page, site, order=0)

    # Read back
    with open(temp_file, "r") as f:
        result = f.read()

    # Parse to get UUIDs
    sections = result.split("---")[1:]
    section2_data = yaml.safe_load(sections[1])

    # Verify multi-line text is preserved (using literal block style, not quoted)
    # Accept both | and |- as valid literal block styles
    assert "content: |" in result, (
        f"Multi-line text should use literal block style (|), got:\n{repr(result)}"
    )

    # Verify the parsed content is correct (multi-line text preserved)
    # Note: |- style strips trailing newline, which is acceptable
    assert (
        section2_data["content"]
        in [
            "hello there\nthis is a multi-line\nstring\n",  # | style (keeps trailing newline)
            "hello there\nthis is a multi-line\nstring",  # |- style (strips trailing newline)
        ]
    ), f"Multi-line text content incorrect: {repr(section2_data['content'])}"

    # Verify no extra blank lines were added (should have exactly 2 sections)
    assert len([s for s in sections if s.strip()]) == 2, (
        "Should have exactly 2 YAML sections"
    )


@pytest.mark.django_db
def test_yaml_dump_preserves_multi_line_content_with_html_tags(
    site, form, make_temp_file
):
    """Test that yaml.dump preserves multi-line text with HTML/XML tags using literal block style.

    This tests the bug where content with HTML tags gets converted from:
        content: |
          Text here
          <c-picture src="..." />
          More text

    To the incorrect format:
        content: "Text here\\n<c-picture src=\\"...\\" />\\nMore text"
    """
    # Create YAML with multi-line content containing HTML-like tags
    original_yaml = """---
content_type: FORM_PAGE
title: Test Page
---
content_type: FORM_CONTENT
content: |
  Considering blah blah, answer the following:
  <c-picture
     src="../images/graph1.drawio.svg"
     alt="Graph example"
     caption="Example of a graph"
     />
  Blah blah
"""

    temp_file = make_temp_file(suffix=".yaml", content=original_yaml)

    # Save the content
    parsed = parse_single_file(temp_file)
    page = save_form_page(parsed[0], form, site, temp_file.parent, order=0)
    save_form_content(parsed[1], page, site, order=0)

    # Read back
    with open(temp_file, "r") as f:
        result = f.read()

    # Parse to get UUIDs
    sections = result.split("---")[1:]
    section2_data = yaml.safe_load(sections[1])

    # The key assertion: multi-line content with HTML tags should NOT be quoted
    # It should use the literal block style (|)
    assert "content: |" in result, (
        f"Multi-line text with HTML tags should use literal block style (|), "
        f"not quoted strings with \\n escapes.\nGot:\n{repr(result)}"
    )

    # Verify it does NOT use the incorrect quoted format with \n escapes
    assert 'content: "' not in result, (
        f"Content should not use quoted string format with \\n escapes.\nGot:\n{repr(result)}"
    )

    # Verify the actual HTML tag is preserved on its own lines, not escaped
    assert "<c-picture" in result, (
        f"HTML tag should be preserved literally, not escaped.\nGot:\n{repr(result)}"
    )
    assert 'src="../images/graph1.drawio.svg"' in result, (
        f"HTML attributes should be preserved literally.\nGot:\n{repr(result)}"
    )

    # Verify the parsed content is correct (newlines preserved, not escaped)
    # The content should contain the HTML tag and newlines should be actual newlines, not \n escapes
    assert "Considering blah blah, answer the following:" in section2_data["content"]
    assert "<c-picture" in section2_data["content"]
    assert 'src="../images/graph1.drawio.svg"' in section2_data["content"]
    assert "Blah blah" in section2_data["content"]

    # Most importantly, verify that newlines in the content are real newlines
    # If they were escaped as \n, the parsed content wouldn't have real newlines
    assert "\n" in section2_data["content"], (
        f"Content should contain actual newlines, not escaped \\n sequences.\n"
        f"Got:\n{repr(section2_data['content'])}"
    )


@pytest.mark.django_db
def test_updating_question_options_preserves_other_sections_multi_line_format(
    site, form, make_temp_file
):
    """Test that adding UUIDs to question options preserves multi-line formatting in other sections.

    This exposes the REAL bug! When update_file_with_option_uuids is called:
    1. It reads the entire file and splits all sections
    2. It strips all sections: `sections = [s.strip() for s in sections]`
    3. It finds the question section and re-dumps it with option UUIDs
    4. It reconstructs the ENTIRE file from the sections list

    The problem: Other sections that have `content: |` multi-line formatting
    are NOT re-dumped, they're just the stripped original text. But when the
    file is reconstructed, those sections are embedded in a fresh yaml.dump()
    of the ENTIRE sections list... NO WAIT, that's not right.

    Actually looking at the code more carefully - it joins the sections as strings,
    not as yaml objects. So the sections that weren't touched should retain their
    format. Unless...

    The bug must be that PreservingDumper is NOT properly preserving multi-line
    strings with special characters like < and >.
    """
    # Create YAML where question has UUID but options don't, and there's
    # multi-line content in another section
    original_yaml = """---
content_type: FORM_PAGE
title: Test Page
uuid: d5f43271-9465-496d-925d-61118963ad9e
---
content_type: FORM_CONTENT
content: |
  Considering blah blah, answer the following:
  <c-picture
     src="../images/graph1.drawio.svg"
     alt="Graph example"
     caption="Example of a graph"
     />
  Blah blah
uuid: 9c4265c5-9178-47b8-9a9d-074e69e34a40
---
content_type: FORM_QUESTION
question: What is your answer?
type: multiple_choice
required: true
uuid: 5e8405d4-2333-49cb-b4fd-9406d3f64b9c
options:
  - text: Option A
    value: a
  - text: Option B
    value: b
"""

    temp_file = make_temp_file(suffix=".yaml", content=original_yaml)

    # Parse
    parsed = parse_single_file(temp_file)
    assert len(parsed) == 3

    # All have UUIDs except the options
    assert parsed[0].uuid == "d5f43271-9465-496d-925d-61118963ad9e"
    assert parsed[1].uuid == "9c4265c5-9178-47b8-9a9d-074e69e34a40"
    assert parsed[2].uuid == "5e8405d4-2333-49cb-b4fd-9406d3f64b9c"
    assert all(opt.uuid is None for opt in parsed[2].options)

    # Save to database - the question has UUID but options don't,
    # so update_file_with_option_uuids will be called
    page = save_form_page(parsed[0], form, site, temp_file.parent, order=0)
    save_form_content(parsed[1], page, site, order=0)
    save_form_question(parsed[2], page, site, order=1)

    # Read the file back
    with open(temp_file, "r") as f:
        result = f.read()

    # THE BUG: The FormContent section should STILL have literal block style
    assert "content: |" in result, (
        f"Multi-line text with HTML tags should use literal block style (|), "
        f"but got quoted strings with \\n escapes instead.\nGot:\n{repr(result)}"
    )

    # Verify it does NOT use the incorrect quoted format with \n escapes
    assert 'content: "' not in result, (
        f"Content should not use quoted string format with \\n escapes.\nGot:\n{repr(result)}"
    )

    # Verify the actual HTML tag is preserved on its own lines, not escaped
    assert "<c-picture" in result, (
        f"HTML tag should be preserved literally, not escaped.\nGot:\n{repr(result)}"
    )
    assert 'src="../images/graph1.drawio.svg"' in result, (
        f"HTML attributes should be preserved literally.\nGot:\n{repr(result)}"
    )
