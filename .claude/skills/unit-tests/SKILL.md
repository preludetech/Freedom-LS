---
name: unit-tests
description: Write pytest unit tests for Django models, views, APIs, and utilities. Use when writing tests, adding test coverage, or when the user mentions testing, pytest, or test files. Follows project-specific patterns including site-aware models, mock_site_context fixture, and pytest-django conventions.
allowed-tools: Read, Grep, Glob, Write, Edit, Bash
---

# Unit Test Writer

This Skill helps write comprehensive pytest unit tests for the Django LMS project, following established patterns and conventions.

## Project-Specific Testing Patterns

### Site-Aware Models Testing
All models in this project are site-aware. When testing models that require site context, always use the `mock_site_context` fixture:

```python
def test_student_creation(mock_site_context):
    student = Student.objects.create(
        first_name="John",
        last_name="Doe",
        email="john@example.com"
    )
    assert student.site is not None
```

### Common Fixtures
Available in `conftest.py` at project root:
- `site`: Creates a test Site
- `user`: Creates a test User
- `form`: Creates a test Form
- `make_temp_file`: Helper for creating temporary files
- `mock_site_context`: Mocks site context for SiteAwareModel

### Import Pattern
Apps are inside the `apps/` directory but it's on the PATH. Leave out the `apps` part:

```python
# CORRECT
from content_engine.models import Course

# INCORRECT
from apps.content_engine.models import Course
```

## Instructions for Writing Tests

### 1. Analyze the Code to Test
Before writing tests:
- Read the target file to understand its functionality
- Identify model fields, methods, views, or API endpoints to test
- Check for existing tests to understand the pattern
- Look for dependencies and related models

### 2. Create Test File
- Location: `apps/<app_name>/tests/test_<module_name>.py`
- Naming: `test_<what_is_being_tested>.py`
- Make **one test at a time** (project convention)

### 3. Test Structure

#### Model Tests
```python
import pytest
from <app_name>.models import ModelName

@pytest.mark.django_db
def test_model_method(mock_site_context):
    """Test a specific model method."""
    instance = ModelName.objects.create(field1="value")
    result = instance.some_method()
    assert result == expected_value
```

#### View/API Tests
```python
import pytest
from django.test import Client
from django.urls import reverse

@pytest.mark.django_db
def test_api_endpoint(client, user, mock_site_context):
    """Test API endpoint returns expected response."""
    client.force_login(user)
    response = client.get(reverse('endpoint-name'))
    assert response.status_code == 200
    result = response.json()
    assert result == ??? # Always be explicit. What exactly do we expect to see
```

#### Utility Function Tests
```python
import pytest
from <app_name>.utils import utility_function

def test_utility_function():
    """Test utility function with various inputs."""
    result = utility_function(input_value)
    assert result == expected_output
```

### 4. Test Coverage Checklist
For each component, ensure tests cover:
- **Happy path**: Normal expected usage
- **Edge cases**: Empty values, None, boundary conditions
- **Error cases**: Invalid inputs, missing required fields
- **Business logic**: Custom methods, calculated properties
- **Relationships**: Foreign keys, M2M relationships (for site-aware models)
- **Permissions**: Access control if applicable

### 5. Running Tests
Run specific test:
```bash
pytest path/to/test_file.py::test_name
```

Run all tests except Bloom app:
```bash
pytest
```

Run the Bloom tests:

```bash
pytest  concrete_apps/bloom_student_interface --ds concrete_apps.bloom_student_interface.config.settings_dev
```

### 6. Test Best Practices
- Use descriptive test names that explain what is being tested
- Include docstrings explaining the test's purpose
- Use `@pytest.mark.django_db` for tests that touch the database
- Use fixtures from `conftest.py` when available
- If new fixtures need to be created, consider putting them in `conftest.py`
- Always use `mock_site_context` for site-aware models
- Keep tests focused - one assertion concept per test
- Clean up test data (pytest handles this automatically)
- DO NOT use if statements in tests. The code under test is deterministic. If statements in tests hide errors
- be explicit when making assertions. Eg: `assert result == []`. NOT `assert type(result) is list`. We should know exactly what is being returned at all times

## Example: Complete Test File

```python
"""Tests for Student model."""
import pytest
from student_management.models import Student, Cohort


@pytest.mark.django_db
class TestStudentModel:
    """Test suite for Student model."""

    def test_student_creation(self, mock_site_context):
        """Test that students can be created with required fields."""
        student = Student.objects.create(
            first_name="Jane",
            last_name="Smith",
            email="jane@example.com"
        )
        assert student.first_name == "Jane"
        assert student.last_name == "Smith"
        assert student.email == "jane@example.com"
        assert student.site is not None

    def test_student_str_method(self, mock_site_context):
        """Test string representation of Student."""
        student = Student.objects.create(
            first_name="Jane",
            last_name="Smith",
            email="jane@example.com"
        )
        assert str(student) == "Jane Smith"

    def test_student_cohort_relationship(self, mock_site_context):
        """Test that students can be added to cohorts."""
        cohort = Cohort.objects.create(name="2024 Cohort")
        student = Student.objects.create(
            first_name="Jane",
            last_name="Smith",
            email="jane@example.com"
        )
        student.cohorts.add(cohort)
        assert student.cohorts.count() == 1
        assert cohort in student.cohorts.all()
```

## When to Use This Skill

Use this Skill when:
- User asks to write tests for a specific module, model, view, or API
- User mentions "test coverage", "unit tests", or "pytest"
- Adding new functionality that needs test coverage
- Fixing bugs and need regression tests
- User provides a path to a file and asks for tests

## Workflow for testing existing code

1. **Read the code** to understand what needs testing
2. **Check existing tests** to follow established patterns
3. **Create test file** in the appropriate location if it doesn't exist
4. **Write tests one at a time** following the project convention
5. **Run the test** to verify it works
6. **Iterate** based on test results

## Workflow for solving bugs (Test Driven Development)

1. **Read the code** to understand what needs testing
2. **Check existing tests** to follow established patterns
3. **Create test file** in the appropriate location if it doesn't exist
4. **Write a test that fails because of the bug**. This test verifies the existence of the bug. Do not continue with the next step until there is a failing test.
5. **Fix the bug**, the test should now pass