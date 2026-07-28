# Factory Boy

## Convention

Every Django app that has models should have a `factories.py` file at `<app>/factories.py`. Always check existing factories before creating new ones.

## Base Class

Subclass `factory.django.DjangoModelFactory` (not `factory.Factory`) for Django models.

```python
import factory

class MyModelFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = MyModel

    name = factory.Sequence(lambda n: f"Item {n}")
```

## Creating a New Factory

1. Check if a factory already exists in the app's `factories.py`
2. Subclass `factory.django.DjangoModelFactory`
3. Set `Meta.model` to the model class
4. Provide sensible defaults for all required fields

## Common Patterns

### Sequence

Generate unique values:

```python
email = factory.Sequence(lambda n: f"user{n}@example.com")
title = factory.Sequence(lambda n: f"Article {n}")
```

### SubFactory

Create related objects automatically:

```python
author = factory.SubFactory(UserFactory)
category = factory.SubFactory(CategoryFactory)
```

### RelatedFactory

Use `RelatedFactory` when a related object must be created **after** the parent has been saved — e.g. reverse-FK rows, m2m through-models, or any side object that needs the parent's PK. `SubFactory` runs before save and won't work for these cases.

**Default to opt-in via traits.** A bare `RelatedFactory` runs on every call to the parent factory, so tests that just need an empty parent silently get an extra row. Tests that don't know about it can fail in confusing ways (off-by-one counts, unintended cascade behaviour). Wrap related rows in a trait so callers opt in explicitly:

```python
class TeamFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Team

    name = factory.Sequence(lambda n: f"Team {n}")

    class Params:
        with_initial_member = factory.Trait(
            initial_member=factory.RelatedFactory(
                "myapp.teams.factories.MembershipFactory",
                factory_related_name="team",
            )
        )

# Bare team, no membership row:
TeamFactory()
# Team plus one membership:
TeamFactory(with_initial_member=True)
```

Only put `RelatedFactory` directly on the factory (no trait) when **every** test that creates the parent genuinely needs the related row — i.e. the model is unusable without it. That's rare; reach for the trait first.

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
class TagFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Tag
        exclude = ["tagged_item"]

    class Params:
        tagged_item = None

    content_type = factory.LazyAttribute(
        lambda obj: ContentType.objects.get_for_model(obj.tagged_item)
        if obj.tagged_item else None
    )
    object_id = factory.LazyAttribute(
        lambda obj: obj.tagged_item.pk if obj.tagged_item else None
    )

# Usage:
article = ArticleFactory()
TagFactory(tagged_item=article)
```

## Usage in Tests

```python
@pytest.mark.django_db
def test_member_creation():
    member = MemberFactory(name="Alice")
    assert member.name == "Alice"

@pytest.mark.django_db
def test_article_with_custom_title():
    article = ArticleFactory(title="My Article")
    assert article.title == "My Article"
    assert article.slug == "my-article"
```

Override only the fields relevant to your test:

```python
@pytest.mark.django_db
def test_membership():
    team = TeamFactory(name="Test Team")
    membership = MembershipFactory(team=team)
    assert membership.team == team
    # membership.member was auto-created by SubFactory
```
