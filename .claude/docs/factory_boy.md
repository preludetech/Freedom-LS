# Factory Boy

## Convention

Every Django app that has models should have a `factories.py` file at `freedom_ls/<app>/factories.py`. Always check existing factories before creating new ones.

## SiteAwareFactory Base Class

All site-aware models must use `SiteAwareFactory` from `freedom_ls/site_aware_models/factories.py`. It automatically sets the `site` field from the thread-local request context (provided by the `mock_site_context` fixture) and bypasses custom site-aware managers during creation.

```python
from freedom_ls.site_aware_models.factories import SiteAwareFactory

class MyModelFactory(SiteAwareFactory):
    class Meta:
        model = MyModel

    name = factory.Sequence(lambda n: f"Item {n}")
```

## Creating a New Factory

1. Check if a factory already exists in the app's `factories.py`
2. Import `SiteAwareFactory` from `freedom_ls.site_aware_models.factories`
3. Subclass `SiteAwareFactory` (not `factory.django.DjangoModelFactory` directly)
4. Set `Meta.model` to the model class
5. Provide sensible defaults for all required fields

## Common Patterns

### Sequence

Generate unique values:

```python
email = factory.Sequence(lambda n: f"user{n}@example.com")
title = factory.Sequence(lambda n: f"Topic {n}")
```

### SubFactory

Create related objects automatically:

```python
student = factory.SubFactory(StudentFactory)
course = factory.SubFactory(CourseFactory)
```

### LazyAttribute

Derive a field from other fields:

```python
slug = factory.LazyAttribute(lambda obj: slugify(obj.title))
```

### LazyFunction

Call a function with no arguments:

```python
deadline = factory.LazyFunction(lambda: timezone.now() + timedelta(days=30))
```

### Traits

Define reusable field combinations in `Params`:

```python
class Params:
    staff = factory.Trait(is_staff=True)
    superuser = factory.Trait(is_staff=True, is_superuser=True)

# Usage:
UserFactory(staff=True)
UserFactory(superuser=True)
```

### post_generation

Run logic after the object is created (e.g., setting passwords):

```python
class Meta:
    skip_postgeneration_save = True

@factory.post_generation
def password(obj, create, extracted, **kwargs):
    obj.set_password(extracted or obj.email)
    if create:
        obj.save(update_fields=["password"])
```

### GenericForeignKey Handling

Use `Meta.exclude` and `Params` to accept a convenience parameter, then derive `content_type` and `object_id` via `LazyAttribute`:

```python
class CohortDeadlineFactory(SiteAwareFactory):
    class Meta:
        model = CohortDeadline
        exclude = ["content_item"]

    class Params:
        content_item = None

    content_type = factory.LazyAttribute(
        lambda obj: ContentType.objects.get_for_model(obj.content_item)
        if obj.content_item else None
    )
    object_id = factory.LazyAttribute(
        lambda obj: obj.content_item.pk if obj.content_item else None
    )

# Usage:
topic = TopicFactory()
CohortDeadlineFactory(content_item=topic)
```

### ContentCollectionItem (dual GenericFK)

```python
course = CourseFactory()
topic = TopicFactory()
ContentCollectionItemFactory(collection_object=course, child_object=topic)
```

## Usage in Tests

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
```

Override only the fields relevant to your test:

```python
@pytest.mark.django_db
def test_cohort_membership(mock_site_context):
    cohort = CohortFactory(name="Test Cohort")
    membership = CohortMembershipFactory(cohort=cohort)
    assert membership.cohort == cohort
    # membership.student was auto-created by SubFactory
```
