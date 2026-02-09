"""Tests for UUID validation in validate.py."""

import pytest
from pathlib import Path
from freedom_ls.content_engine.validate import validate, check_uuids


@pytest.mark.django_db
class TestUUIDValidation:
    """Test suite for UUID uniqueness validation."""

    def test_check_uuids_with_no_duplicates(self, make_temp_file):
        """Test that validation passes when all UUIDs are unique."""
        # Create two files with different UUIDs
        file1 = make_temp_file(
            suffix=".md",
            content="""---
content_type: TOPIC
title: First Topic
uuid: 11111111-1111-1111-1111-111111111111
---
Content here
""",
        )

        file2 = make_temp_file(
            suffix=".md",
            content="""---
content_type: TOPIC
title: Second Topic
uuid: 22222222-2222-2222-2222-222222222222
---
Content here
""",
        )

        # Should not raise any errors
        validate(file1.parent)

    def test_check_uuids_detects_duplicate_in_different_files(self, make_temp_file):
        """Test that validation fails when same UUID appears in different files."""
        # Create two files with the SAME UUID
        file1 = make_temp_file(
            suffix=".md",
            content="""---
content_type: TOPIC
title: First Topic
uuid: 11111111-1111-1111-1111-111111111111
---
Content here
""",
        )

        file2 = make_temp_file(
            suffix=".md",
            name="another.md",
            content="""---
content_type: TOPIC
title: Second Topic
uuid: 11111111-1111-1111-1111-111111111111
---
Different content
""",
        )

        # Should raise ValueError with duplicate UUID message
        with pytest.raises(ValueError) as exc_info:
            validate(file1.parent)

        error_msg = str(exc_info.value)
        assert "Duplicate UUID" in error_msg
        assert "11111111-1111-1111-1111-111111111111" in error_msg

    def test_check_uuids_in_yaml_files(self, make_temp_file):
        """Test that UUID validation works with YAML files."""
        file1 = make_temp_file(
            suffix=".yaml",
            content="""content_type: COURSE
title: First Course
uuid: 33333333-3333-3333-3333-333333333333
""",
        )

        file2 = make_temp_file(
            suffix=".yaml",
            name="second.yaml",
            content="""content_type: COURSE
title: Second Course
uuid: 33333333-3333-3333-3333-333333333333
""",
        )

        with pytest.raises(ValueError) as exc_info:
            validate(file1.parent)

        error_msg = str(exc_info.value)
        assert "Duplicate UUID" in error_msg
        assert "33333333-3333-3333-3333-333333333333" in error_msg

    def test_check_uuids_in_question_options(self, make_temp_file):
        """Test that UUID validation detects duplicates in question options."""
        file1 = make_temp_file(
            suffix=".yaml",
            content="""content_type: FORM_PAGE
title: Form Page
---
content_type: FORM_QUESTION
question: What is your answer?
type: multiple_choice
required: true
options:
  - text: Option A
    value: 1
    uuid: 44444444-4444-4444-4444-444444444444
  - text: Option B
    value: 2
    uuid: 55555555-5555-5555-5555-555555555555
""",
        )

        file2 = make_temp_file(
            suffix=".yaml",
            name="second_form.yaml",
            content="""content_type: FORM_PAGE
title: Another Form Page
---
content_type: FORM_QUESTION
question: Another question?
type: multiple_choice
required: true
options:
  - text: Option C
    value: 1
    uuid: 44444444-4444-4444-4444-444444444444
  - text: Option D
    value: 2
    uuid: 66666666-6666-6666-6666-666666666666
""",
        )

        with pytest.raises(ValueError) as exc_info:
            validate(file1.parent)

        error_msg = str(exc_info.value)
        assert "Duplicate UUID" in error_msg
        assert "44444444-4444-4444-4444-444444444444" in error_msg

    def test_check_uuids_allows_missing_uuids(self, make_temp_file):
        """Test that validation passes when UUIDs are not specified (optional field)."""
        file1 = make_temp_file(
            suffix=".md",
            content="""---
content_type: TOPIC
title: Topic Without UUID
---
Content here
""",
        )

        file2 = make_temp_file(
            suffix=".md",
            name="another.md",
            content="""---
content_type: TOPIC
title: Another Topic Without UUID
---
Different content
""",
        )

        # Should not raise any errors
        validate(file1.parent)

    def test_check_uuids_mixed_with_and_without_uuids(self, make_temp_file):
        """Test validation with mix of files with and without UUIDs."""
        file1 = make_temp_file(
            suffix=".md",
            content="""---
content_type: TOPIC
title: Topic With UUID
uuid: 77777777-7777-7777-7777-777777777777
---
Content here
""",
        )

        file2 = make_temp_file(
            suffix=".md",
            name="no_uuid.md",
            content="""---
content_type: TOPIC
title: Topic Without UUID
---
Different content
""",
        )

        file3 = make_temp_file(
            suffix=".md",
            name="another_uuid.md",
            content="""---
content_type: TOPIC
title: Another Topic With UUID
uuid: 88888888-8888-8888-8888-888888888888
---
More content
""",
        )

        # Should not raise any errors
        validate(file1.parent)
