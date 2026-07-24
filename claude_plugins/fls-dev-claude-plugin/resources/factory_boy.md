# factory_boy — FreedomLS addendum

This addendum extends the generic `ds` `factory_boy.md` resource (pulled in by `Skill(ds:testing)`). It adds the mandatory `SiteAwareFactory` base, FLS model examples, and `mock_site_context` usage. Read the `ds` resource first for the generic factory_boy technique.

## Convention path

Where the generic resource uses `<app>/factories.py`, FLS factories live at `freedom_ls/<app>/factories.py`.

## `SiteAwareFactory` base class

All site-aware models must use `SiteAwareFactory` from `freedom_ls/site_aware_models/factories.py`. It automatically sets the `site` field from the thread-local request context (provided by the `mock_site_context` fixture) and bypasses custom site-aware managers during creation.

```python
from freedom_ls.site_aware_models.factories import SiteAwareFactory

class MyModelFactory(SiteAwareFactory):
    class Meta:
        model = MyModel

    name = factory.Sequence(lambda n: f"Item {n}")
```

When creating a new factory for a site-aware model, import `SiteAwareFactory` from `freedom_ls.site_aware_models.factories` and subclass it (not `factory.django.DjangoModelFactory` directly).

## FLS model examples

- **SubFactory:** `StudentFactory` / `CourseFactory`.
- **RelatedFactory:** `CohortFactory(SiteAwareFactory)` with `"freedom_ls.student_management.factories.CohortMembershipFactory"`.
- **GenericFK:** `CohortDeadlineFactory(SiteAwareFactory)` with `CohortDeadline` / `content_item` / `TopicFactory`.
- **ContentCollectionItem (dual GenericFK):**

  ```python
  course = CourseFactory()
  topic = TopicFactory()
  ContentCollectionItemFactory(collection_object=course, child_object=topic)
  ```

## Usage in tests — `mock_site_context`

Always use `mock_site_context` when working with site-aware factories:

```python
@pytest.mark.django_db
def test_student_creation(mock_site_context):
    student = StudentFactory()
    assert student.user is not None
    assert student.site is not None


@pytest.mark.django_db
def test_course_with_custom_title(mock_site_context):
    course = CourseFactory(title="My Course")
    assert course.title == "My Course"
    assert course.slug == "my-course"


@pytest.mark.django_db
def test_cohort_membership(mock_site_context):
    cohort = CohortFactory(name="Test Cohort")
    membership = CohortMembershipFactory(cohort=cohort)
    assert membership.cohort == cohort
    # membership.student was auto-created by SubFactory
```
