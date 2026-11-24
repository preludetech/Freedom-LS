"""
example usage:
python manage.py content_save  ../bloom_content Bloom

The source path must be a clean, committed git tree: the command refuses
uncommitted, staged, deleted and untracked files so a save always matches
a commit.
"""

import logging
import mimetypes
import re
import uuid
from collections import Counter, defaultdict
from collections.abc import Callable, Collection, Hashable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from functools import partial
from pathlib import Path

import djclick as click
import frontmatter
import mutagen
import yaml

from django.conf import settings
from django.contrib.contenttypes.models import ContentType as DjangoContentType
from django.contrib.sites.models import Site
from django.core.files import File as DjangoFile
from django.core.files.base import ContentFile
from django.core.management.base import CommandError
from django.db import models, transaction
from django.db.models import Model
from django.utils import timezone
from django.utils.module_loading import import_string
from django.utils.text import slugify

from freedom_ls.base.git_utils import (
    UncommittedPath,
    find_repo_root,
    head_commit_of,
    submodule_paths,
    tracked_files,
    uncommitted_paths,
)
from freedom_ls.content_base.schema import (
    DUE_DATE_FIELD_NAMES,
    BaseBaseContentModel,
    BaseContentModel,
    DueDateFields,
)
from freedom_ls.content_base.schema import ContentType as SchemaContentType
from freedom_ls.content_engine.config import config
from freedom_ls.content_engine.ignore_list import ignore_list_for
from freedom_ls.content_engine.image_cache import CACHE_DIR_NAME, ImageCache
from freedom_ls.content_engine.images import (
    ImageEncodeDecision,
    ImageEncodeStatus,
)
from freedom_ls.content_engine.models import (
    Activity,
    Article,
    ContentCollectionItem,
    ContentSave,
    ContentSaveSource,
    Course,
    CourseCategory,
    CoursePart,
    CoursePartChildDueDate,
    CourseReferencePart,
    File,
    FormQuestionCoursePart,
    FormQuestionTopic,
    Topic,
)
from freedom_ls.content_engine.moved_children import (
    carry_placement_due_dates,
    moved_children,
)
from freedom_ls.content_engine.prices import KIND_FIELDS
from freedom_ls.content_engine.schema import Child, CourseCategories
from freedom_ls.content_engine.schema import Course as CourseSchema
from freedom_ls.content_engine.schema import CoursePart as CoursePartSchema
from freedom_ls.content_engine.signals import (
    collection_items_synced,
    part_placement_removed,
)
from freedom_ls.content_engine.validate import (
    CONFIG_FILE_NAME,
    IMAGE_EXTENSIONS,
    collection_children,
    content_key,
    effective_sections,
    form_section_label,
    get_all_files,
    is_ignored,
    parse_single_file,
    resolve_author_path,
    split_yaml_documents,
    validate,
    validate_children_lists,
    validate_due_date_placements,
    validate_form_section_placement,
    validate_question_sections,
    validate_reference_lists,
)
from freedom_ls.form_engine import schema as form_schema
from freedom_ls.form_engine.models import (
    Form,
    FormContent,
    FormPage,
    FormQuestion,
    QuestionOption,
)
from freedom_ls.form_engine.schema import Condition
from freedom_ls.form_engine.signals import form_questions_dropped
from freedom_ls.organisations.models import Organisation
from freedom_ls.site_aware_models.slugs import get_unique_slug

logger = logging.getLogger(__name__)

# Every model a save can retire, in the order the count line names them.
RETIRABLE_MODELS: tuple[type[Model], ...] = (
    Course,
    CoursePart,
    Topic,
    Activity,
    Article,
    Form,
    FormPage,
    FormContent,
    FormQuestion,
    QuestionOption,
    CourseCategory,
    File,
)


def _row_key(row: Model) -> Hashable:
    """What identifies a row to a save: a File's path, any other row's pk."""
    return row.file_path if isinstance(row, File) else row.pk


@dataclass
class _RunLedger:
    """What one save found in the source and what it did about retirement."""

    seen: dict[type[Model], set[Hashable]] = field(
        default_factory=lambda: defaultdict(set)
    )
    retired: dict[type[Model], set[uuid.UUID]] = field(
        default_factory=lambda: defaultdict(set)
    )

    retired_before: dict[type[Model], set[Hashable]] = field(
        default_factory=lambda: defaultdict(set)
    )

    def saw(self, row: Model) -> None:
        self.seen[type(row)].add(_row_key(row))

    def unretired(self, model: type[Model]) -> set[Hashable]:
        """Rows that were retired before the run and are in the source again."""
        return self.seen[model] & self.retired_before[model]


@dataclass(frozen=True)
class _SaveResult:
    """What a save transaction hands back for the command to report."""

    image_statuses: list[ImageEncodeStatus]
    removal_lines: list[str]
    ledger: _RunLedger


def _retire_count_line(ledger: _RunLedger) -> str:
    """`Retired: 3 (Topic 1, FormQuestion 2). Un-retired: 0.` Both totals are always
    printed. A model with a zero count is left out of the brackets, and a zero total
    has no brackets."""

    def describe(label: str, counts: dict[str, int]) -> str:
        total = sum(counts.values())
        if not total:
            return f"{label}: 0."
        detail = ", ".join(f"{name} {count}" for name, count in counts.items())
        return f"{label}: {total} ({detail})."

    retired = {
        model.__name__: len(ledger.retired[model])
        for model in RETIRABLE_MODELS
        if ledger.retired[model]
    }
    unretired = {
        model.__name__: len(ledger.unretired(model))
        for model in RETIRABLE_MODELS
        if ledger.unretired(model)
    }
    return f"{describe('Retired', retired)} {describe('Un-retired', unretired)}"


def represent_str(dumper, data):
    """Custom string representer that uses literal style for multi-line strings."""
    if "\n" in data:
        # Force literal block style for multi-line strings
        # The style parameter tells PyYAML which style to use:
        # '|' = literal block style (preserves newlines, no escaping)
        # Use the literal style to preserve readability of multi-line content
        return dumper.represent_scalar("tag:yaml.org,2002:str", data, style="|")
    return dumper.represent_scalar("tag:yaml.org,2002:str", data)


# Create custom YAML dumper
class PreservingDumper(yaml.SafeDumper):
    """Custom YAML dumper that preserves multi-line strings in literal block style."""

    def write_line_break(self, data=None):
        """Override to ensure proper line breaks in literal style."""
        super().write_line_break(data)

    def choose_scalar_style(self):
        """Override scalar style selection to prefer literal style for multi-line strings.

        This method is called by PyYAML to determine which style to use for a scalar.
        By default, PyYAML may choose double-quoted style for strings with special
        characters, even if we specified style='|'. This override ensures that
        our style preference is respected.
        """
        # Call parent's choose_scalar_style first
        style = super().choose_scalar_style()

        # If we explicitly set style to '|' (literal), keep it
        # even if the string has special characters
        if self.event and hasattr(self.event, "style") and self.event.style == "|":
            return "|"

        return style


PreservingDumper.add_representer(str, represent_str)


def update_file_with_uuid(file_path, item_uuid):
    """
    Update a file's frontmatter or YAML section with a UUID.
    For multi-document YAML files, finds the first section without a UUID and updates it.

    Args:
        file_path: Path to the file
        item_uuid: UUID to add
    """
    if file_path.suffix in [".yaml", ".yml"]:
        # Handle YAML file
        with open(file_path, encoding="utf-8") as f:
            content = f.read()

        sections = split_yaml_documents(content)

        # Find the first section without a UUID
        for idx, section in enumerate(sections):
            section_data = yaml.safe_load(section)
            if section_data and "uuid" not in section_data:
                section_data["uuid"] = str(item_uuid)
                # Re-serialize with literal style for multi-line strings
                sections[idx] = yaml.dump(
                    section_data,
                    Dumper=PreservingDumper,
                    default_flow_style=False,
                    allow_unicode=True,
                ).strip()
                break

        # Reconstruct file with leading --- and proper formatting
        new_content = "---\n" + "\n---\n".join(sections) + "\n"

        with open(file_path, "w", encoding="utf-8") as f:
            f.write(new_content)

        logger.info(f"Updated {file_path} with UUID: {item_uuid}")
    else:
        # Handle markdown file
        post = frontmatter.load(file_path)
        post.metadata["uuid"] = str(item_uuid)

        with open(file_path, "w", encoding="utf-8") as f:
            f.write(frontmatter.dumps(post))

        logger.info(f"Updated {file_path} with UUID: {item_uuid}")


def update_file_with_option_uuids(file_path, question_uuid, option_uuids):
    """
    Update options in a YAML file with their UUIDs.

    Args:
        file_path: Path to the file
        question_uuid: UUID of the question containing the options
        option_uuids: List of (option_index, option_uuid) tuples
    """
    if file_path.suffix not in [".yaml", ".yml"]:
        return

    with open(file_path, encoding="utf-8") as f:
        content = f.read()

    sections = split_yaml_documents(content)

    # Find the question section with matching UUID
    for idx, section in enumerate(sections):
        section_data = yaml.safe_load(section)
        if (
            section_data
            and section_data.get("uuid") == str(question_uuid)
            and section_data.get("options")
        ):
            for opt_idx, opt_uuid in option_uuids:
                if opt_idx < len(section_data["options"]):
                    section_data["options"][opt_idx]["uuid"] = str(opt_uuid)

            sections[idx] = yaml.dump(
                section_data,
                Dumper=PreservingDumper,
                default_flow_style=False,
                allow_unicode=True,
            ).strip()
            break

    new_content = "---\n" + "\n---\n".join(sections) + "\n"

    with open(file_path, "w", encoding="utf-8") as f:
        f.write(new_content)

    logger.info(f"Updated {file_path} with option UUIDs")


def update_file_with_category_uuids(file_path, written):
    """
    Update entries in the COURSE_CATEGORIES document of a YAML file with their UUIDs.

    Args:
        file_path: Path to the file
        written: List of (entry_index, category_uuid) tuples
    """
    with open(file_path, encoding="utf-8") as f:
        content = f.read()

    sections = split_yaml_documents(content)

    for idx, section in enumerate(sections):
        section_data = yaml.safe_load(section)
        if (
            section_data
            and section_data.get("content_type") == "COURSE_CATEGORIES"
            and section_data.get("categories")
        ):
            for entry_idx, entry_uuid in written:
                if entry_idx < len(section_data["categories"]):
                    section_data["categories"][entry_idx]["uuid"] = str(entry_uuid)

            sections[idx] = yaml.dump(
                section_data,
                Dumper=PreservingDumper,
                default_flow_style=False,
                allow_unicode=True,
            ).strip()
            break

    new_content = "---\n" + "\n---\n".join(sections) + "\n"

    with open(file_path, "w", encoding="utf-8") as f:
        f.write(new_content)

    logger.info(f"Updated {file_path} with category UUIDs")


def save_with_uuid(
    model_class,
    item,
    site,
    base_path,
    update_file=True,
    exclude_fields=None,
    derive_slug=True,
    **extra_fields,
):
    """Generic save function that handles UUID logic.

    Automatically extracts all fields from the Pydantic item and validates
    that they match the Django model schema.

    Args:
        model_class: Django model class to save to
        item: Pydantic model instance with frontmatter data
        site: Django Site instance
        base_path: Base path for calculating relative file paths
        update_file: Whether to update the file with UUID after creation
        exclude_fields: Additional fields to exclude from the Pydantic dump (e.g., 'options' for FormQuestion)
        derive_slug: Whether to overwrite 'slug' with slugify(title). True for every
            content type whose slug is derived and unreferenced by name. False for
            CourseCategory, whose slug is authored and named by every referencing course.
        **extra_fields: Additional fields not in the Pydantic model (e.g., foreign keys like 'form', 'form_page', 'order')
    """
    # Build exclusion set
    exclude = {"content_type", "file_path", "uuid"}
    if exclude_fields:
        exclude.update(exclude_fields)

    # Get all fields from the Pydantic item (excluding internal fields)
    fields = item.model_dump(
        exclude=exclude,
        exclude_none=True,  # Don't include None values
    )

    # A file with no `tags:` key says nothing about tags, exactly as an absent
    # `meta:` does -- leave whatever is stored alone. `tags: []` still clears
    # them. Without this, `tags` defaulting to [] rather than None would
    # survive exclude_none and wipe tags added through the admin.
    if "tags" not in item.model_fields_set:
        fields.pop("tags", None)

    # Add extra fields (like foreign keys that aren't in the Pydantic schema)
    fields.update(extra_fields)

    # A row found in the source is live. Written with the content so the update and
    # the un-retire are one statement.
    fields["retired_at"] = None

    # Calculate relative path if base_path is provided
    if base_path:
        relative_path = str(item.file_path.relative_to(base_path))
        fields["file_path"] = relative_path

    # Get all fields from the Django model
    model_field_names = {f.name for f in model_class._meta.get_fields()}

    # Validate: check for fields that don't exist on the model
    item_field_names = set(fields.keys())
    invalid_fields = item_field_names - model_field_names

    if invalid_fields:
        source_info = getattr(item, "file_path", "inline content")
        raise ValueError(
            f"Cannot save {model_class.__name__} from {source_info}: "
            f"Fields present in frontmatter but don't exist in Django model: {sorted(invalid_fields)}. "
            f"Either add these fields to the {model_class.__name__} model or remove from the Pydantic schema. "
            f"Valid model fields are: {sorted(model_field_names)}"
        )

    # Auto-generate slug if title exists and slug field exists on model
    if derive_slug and "title" in fields and "slug" in model_field_names:
        base_slug = slugify(fields["title"])
        fields["slug"] = get_unique_slug(model_class, site, base_slug, item.uuid)

    if item.uuid:
        instance, _ = model_class.objects.update_or_create(
            id=uuid.UUID(item.uuid), site=site, defaults=fields
        )
    else:
        instance = model_class.objects.create(site=site, **fields)
        if update_file:
            update_file_with_uuid(item.file_path, instance.id)
    try:
        if item.content:
            instance.content = markdown_translate(instance.content)
            instance.save()
    except AttributeError:
        pass  # nothing to do

    return instance


def markdown_translate(markdown_content):
    # look for markdown pictures
    # Eg with title: `![[Chewy tubes.jpg | Chewy Tubes]]`
    # Eg without title: `![[Chewy tubes.jpg]]`
    # replace them with c-picture cotton components

    # Pattern with title: ![[filename | title]]
    pattern_with_title = r"!\[\[([^|\]]+)\s*\|\s*([^\]]+)\]\]"
    markdown_content = re.sub(
        pattern_with_title,
        lambda m: (
            f'<c-picture src="{m.group(1).strip()}" title="{m.group(2).strip()}"></c-picture>'
        ),
        markdown_content,
    )

    # Pattern without title: ![[filename]]
    pattern_without_title = r"!\[\[([^\]]+)\]\]"
    markdown_content = re.sub(
        pattern_without_title,
        lambda m: f'<c-picture src="{m.group(1).strip()}"></c-picture>',
        markdown_content,
    )

    return markdown_content


def due_date_columns(
    schema: BaseBaseContentModel | DueDateFields | None,
) -> dict[str, object]:
    """The four due columns a child file or a children: entry sets, None for each due key it
    does not carry and no_due_date False when it has none. Writing the absent values on every
    sync is what lets an author remove a due date."""
    columns: dict[str, object] = {
        name: getattr(schema, name, None) for name in DUE_DATE_FIELD_NAMES
    }
    columns["no_due_date"] = getattr(schema, "no_due_date", False)
    return columns


def placement_due_columns(
    entry: Child | None, child_schema: BaseBaseContentModel | None
) -> dict[str, object]:
    """The due columns one placement row holds. An entry that sets a value supplies every
    column, so an entry's relative offset is never given the child file's time of day;
    otherwise the child file does."""
    if entry is not None and entry.holds_due_value():
        return due_date_columns(entry)
    return due_date_columns(child_schema)


def save_topic(item, site, base_path):
    """Save a Topic to the database."""
    return save_with_uuid(
        Topic, item, site, base_path, exclude_fields=DUE_DATE_FIELD_NAMES
    )


def save_activity(item, site, base_path):
    """Save an Activity to the database."""
    return save_with_uuid(Activity, item, site, base_path)


def _retired_prefix(owner: Article | CourseCategory) -> str:
    """`retired ` for a retired row, so a collision message says the slug is held by
    a row that is no longer in the source."""
    return "retired " if owner.is_retired else ""


def _refuse_category_slug_collisions(item, site, relative_path):
    """Refuse any entry whose slug already belongs to a different row on this site.

    Rows are identified by uuid, never by slug: an entry without a uuid is a
    new row, and an entry whose uuid differs from the slug's current owner is
    a different row. Either way, saving it would hit the (site, slug)
    constraint, so name the owning uuid instead so the author can adopt the
    row deliberately or pick another slug. Every collision is reported, not
    just the first.
    """
    owners = {
        category.slug: category
        for category in CourseCategory._base_manager.filter(
            site=site, slug__in=[entry.slug for entry in item.categories]
        )
    }
    errors = []
    for entry in item.categories:
        owner = owners.get(entry.slug)
        if owner is not None and str(owner.id) != entry.uuid:
            owner_id = owner.id
            errors.append(
                f"\n❌ Category slug '{entry.slug}' in {relative_path} already "
                f"belongs to another {_retired_prefix(owner)}CourseCategory "
                f"on site '{site.name}' (uuid {owner_id}). A category is identified by its uuid, so "
                "this entry would be a second row with the same slug. To edit "
                f"that category, give this entry `uuid: {owner_id}`; to add a "
                "new one, choose a different slug."
            )
    if errors:
        raise ValueError("\n".join(errors))


def _refuse_article_slug_collisions(item, site, relative_path):
    """Refuse an article whose slug already belongs to a different row on this site.

    The slug is the public URL, so it is never suffixed to make room.
    """
    owner = Article._base_manager.filter(site=site, slug=item.slug).first()
    if owner is not None and str(owner.id) != item.uuid:
        raise ValueError(
            f"\n❌ Article slug '{item.slug}' in {relative_path} already belongs "
            f"to another {_retired_prefix(owner)}Article on site '{site.name}' (uuid {owner.id}). To edit "
            f"that article, give this file `uuid: {owner.id}`; to add a new one, "
            "choose a different slug."
        )


def save_article(item, site, base_path):
    """Save an Article to the database.

    `author`, `show_date`, `show_author`, `image` and `image_alt` go in as extra fields because the
    dump drops None values, which would otherwise leave a stale stored value
    when a key is removed from the file.
    """
    relative_path = item.file_path.relative_to(base_path)
    _refuse_article_slug_collisions(item, site, relative_path)
    return save_with_uuid(
        Article,
        item,
        site,
        base_path,
        derive_slug=False,
        author=item.author or "",
        image=item.image or "",
        image_alt=item.image_alt or "",
        show_date=item.show_date,
        show_author=item.show_author,
    )


def save_course_categories(item, site, base_path):
    """Save every CourseCategory declared in one file, order from list position."""
    relative_path = str(item.file_path.relative_to(base_path))
    _refuse_category_slug_collisions(item, site, relative_path)
    categories = []
    written = []
    for index, entry in enumerate(item.categories):
        category = save_with_uuid(
            CourseCategory,
            entry,
            site,
            None,
            update_file=False,
            derive_slug=False,
            order=index,
            file_path=relative_path,
        )
        categories.append(category)
        written.append((index, category.id))

    if any(entry.uuid is None for entry in item.categories):
        update_file_with_category_uuids(item.file_path, written)

    return categories


# The eight price_* columns with no price at all -- the shape `price_columns`
# starts from and falls back to for a kind that doesn't use a given field.
EMPTY_PRICE_COLUMNS: dict[str, object] = {
    "price_kind": "",
    "price_amount": None,
    "price_sale_amount": None,
    "price_sale_ends_on": None,
    "price_low_amount": None,
    "price_high_amount": None,
    "price_currency": "",
    "price_tax_note": "",
}


def price_columns(item: CourseSchema) -> dict[str, object]:
    """The eight price_* columns for a course whose frontmatter has a `price:` key.

    A field the chosen kind doesn't use comes back at its empty value, so
    switching a course from one kind to another through content_save never
    leaves a stale column behind. `item.price` is `None` here only when the
    author wrote an explicit `price: null` -- the caller only calls this when
    `"price"` is in `item.model_fields_set` -- so this returns the all-empty
    shape for that case too, clearing whatever was stored.
    """
    columns = dict(EMPTY_PRICE_COLUMNS)
    if item.price is None:
        return columns
    columns.update(
        {
            f"price_{field}": value
            for field, value in item.price.model_dump(exclude_none=True).items()
        }
    )
    if "currency" in KIND_FIELDS[item.price.kind][1] and not columns["price_currency"]:
        if not config.DEFAULT_CURRENCY:
            raise ValueError(
                f"{item.file_path}: the price has no currency and "
                "DEFAULT_CURRENCY is not set."
            )
        columns["price_currency"] = config.DEFAULT_CURRENCY
    return columns


def save_course(item, site, base_path):
    """Save a Course to the database."""
    # Defence-in-depth: the pydantic model_validator already enforces these
    # rules during `validate.py`/`content_validate`, but the validation also
    # runs here so that any caller that bypasses `validate(...)` still gets
    # a clear ValidationError instead of a half-saved row.
    from freedom_ls.content_engine.icon_validation import (
        validate_course_icon_fields,
    )

    validate_course_icon_fields(item.icon or "", item.icon_fallback or "")

    # Load-time access_config validation via the settings hook.
    # content_engine never imports course_access directly — the dotted-path setting
    # is the only seam (resolved via import_string). This avoids a dependency cycle:
    # course_access already depends on content_engine, so a direct import here would
    # close the cycle. Degrades safely if COURSE_ACCESS_CONFIG_VALIDATOR is unset.
    validator_path = config.COURSE_ACCESS_CONFIG_VALIDATOR
    if validator_path:
        validate_access_config = import_string(validator_path)
        item.access_config = validate_access_config(
            item.access_config or {}, file_path=str(item.file_path)
        )

    dashboard_category_slug = item.resolve_dashboard_category()
    dashboard_category = None
    if dashboard_category_slug is not None:
        try:
            dashboard_category = CourseCategory._base_manager.get(
                site=site, slug=dashboard_category_slug
            )
        except CourseCategory.DoesNotExist as exc:
            # Defence-in-depth, as above: validate() already checks every
            # dashboard_category against the declared slugs, but a caller
            # that bypasses it still gets a clear error rather than a
            # half-saved course.
            raise ValueError(
                f"Unknown dashboard_category '{dashboard_category_slug}' in "
                f"{item.file_path}: no CourseCategory with this slug is declared."
            ) from exc

    # An absent `price:` key leaves whatever price is already stored alone,
    # mirroring how `save_with_uuid` already treats `tags` -- only when the
    # author wrote the key (including `price: null`) do these columns change.
    price_fields = price_columns(item) if "price" in item.model_fields_set else {}

    # The access_config written here still carries the author's raw
    # application_form path; the binding pass in save_content_to_db resolves it
    # into the Course.application_form foreign key once every Form is saved.
    organisations = _resolve_organisations(
        item.organisations, "organisations", item.file_path, site
    )
    shared_with = _resolve_organisations(
        item.shared_with, "shared_with", item.file_path, site
    )
    # Written on every load, None included, so that deleting `time_limit_days`
    # from the file removes the limit; a None in the dump would be dropped.
    course = save_with_uuid(
        Course,
        item,
        site,
        base_path,
        exclude_fields={
            "children",
            "reference",
            "categories",
            "dashboard_category",
            "price",
            "time_limit_days",
            "organisations",
            "shared_with",
        },
        dashboard_category=dashboard_category,
        time_limit_days=item.time_limit_days,
        **price_fields,
    )
    # A replace, like categories: an absent key clears the link, so the file
    # stays the single source of which organisations own a course and which it
    # is shared with.
    course.organisations.set(organisations)
    course.shared_with.set(shared_with)
    return course


def _organisation_name_from_slug(slug: str) -> str:
    """ "harbour-college" becomes "Harbour College".

    Only the first letter of each word is capitalised: `str.title()` would also
    capitalise after an apostrophe or a digit.
    """
    return " ".join(
        word[:1].upper() + word[1:] for word in re.split(r"[-_]", slug) if word
    )


def _resolve_organisations(
    slugs: list[str], field: str, file_path: Path, site: Site
) -> list[Organisation]:
    """Return the site's organisations named by `slugs`, or raise naming the bad ones."""
    if not slugs:
        return []
    found = list(Organisation._base_manager.filter(site=site, slug__in=slugs))
    unknown = sorted(set(slugs) - {o.slug for o in found})
    if unknown and settings.DEBUG:
        # Development only: a clean checkout's demo content names organisations
        # nobody has created yet. Looked up with an explicit site and the base
        # manager because the loader runs with no request. `ensure_organisation`
        # is not used: it may suffix the slug, and the course names this one.
        for slug in unknown:
            name = _organisation_name_from_slug(slug)
            holder = Organisation._base_manager.filter(site=site, name=name).first()
            if holder is not None:
                raise CommandError(
                    _refusal(
                        f'content_save cannot create organisation "{slug}" '
                        f"for {file_path}.",
                        [
                            (
                                f'Its name would be "{name}", which organisation '
                                f'"{holder.name}" (slug: {holder.slug}) already '
                                "has on this site.",
                                [],
                            )
                        ],
                        "Rename that organisation, or use its slug in the course file.",
                    )
                )
            organisation, _ = Organisation._base_manager.get_or_create(
                site=site, slug=slug, defaults={"name": name}
            )
            found.append(organisation)
        return found
    if unknown:
        valid = sorted(
            Organisation._base_manager.filter(site=site).values_list("slug", flat=True)
        )
        raise ValueError(
            f"Unknown organisations {unknown} in {field} of {file_path} on site "
            f"'{site.name}'. Valid organisation slugs: {valid}"
        )
    return found


def save_course_part(item, site, base_path):
    """Save a CoursePart to the database."""
    return save_with_uuid(
        CoursePart,
        item,
        site,
        base_path,
        exclude_fields={"children"},
    )


def save_form(item, site, base_path):
    """Save a Form to the database."""
    return save_with_uuid(
        Form,
        item,
        site,
        base_path,
        exclude_fields=DUE_DATE_FIELD_NAMES | {"sections"},
    )


def _resolve_condition(
    when: Condition | None,
    options_by_slug: Mapping[str, Mapping[str, QuestionOption]],
    file_path: Path,
) -> QuestionOption | None:
    """The option this run saved for the value `when` names, or None.

    Resolved from this run's saved objects rather than the database, where
    questions dropped from the YAML and options re-created without a uuid
    leave stale rows that a value lookup could hit.
    """
    if when is None:
        return None
    option = options_by_slug.get(when.question, {}).get(when.literal)
    if option is None:
        raise ValueError(
            f"{file_path}: when names {when.question} = {when.literal}, "
            "which no earlier question in this form saved."
        )
    return option


def save_form_page(
    item: form_schema.FormPage,
    form: Form,
    site: Site,
    base_path: Path,
    order: int = 0,
    condition_option: QuestionOption | None = None,
) -> FormPage:
    """Save a FormPage to the database."""
    # condition_option and draw are written even when None: save_with_uuid drops
    # None keys, so leaving them out would keep whatever the row had from an
    # earlier import.
    page: FormPage = save_with_uuid(
        FormPage,
        item,
        site,
        base_path,
        exclude_fields={"when"},
        form=form,
        order=order,
        condition_option=condition_option,
        draw=item.draw,
    )
    return page


def save_form_content(
    item: form_schema.FormContent,
    form_page: FormPage,
    site: Site,
    base_path: Path,
    order: int = 0,
    condition_option: QuestionOption | None = None,
) -> FormContent:
    """Save FormContent to the database."""
    content: FormContent = save_with_uuid(
        FormContent,
        item,
        site,
        base_path,
        exclude_fields={"when"},
        form_page=form_page,
        order=order,
        condition_option=condition_option,
        # Written even when the file has none: the dump drops None, so a
        # removed `group:` would otherwise leave the stored one.
        group=item.group or "",
    )
    return content


def save_form_question(
    item: form_schema.FormQuestion,
    form_page: FormPage,
    site: Site,
    base_path: Path,
    order: int = 0,
    condition_option: QuestionOption | None = None,
) -> tuple[FormQuestion, dict[str, QuestionOption]]:
    """Save FormQuestion and its options to the database.

    Returns the question and the options this call saved, keyed by value.
    """
    # Exclude 'options' since they're handled separately below. slug, group and
    # explanation are written even when the file has none: the dump drops None, so
    # removing one would otherwise leave the stored value.
    question = save_with_uuid(
        FormQuestion,
        item,
        site,
        base_path,
        exclude_fields={"options", "when", "sections"},
        form_page=form_page,
        order=order,
        condition_option=condition_option,
        slug=item.slug or "",
        group=item.group or "",
        explanation=item.explanation or "",
    )

    saved_options: dict[str, QuestionOption] = {}
    if item.options:
        option_uuids = []
        for idx, option in enumerate(item.options):
            # Convert value to string since the model field is CharField
            option_obj = save_with_uuid(
                QuestionOption,
                option,
                site,
                None,  # No base_path for inline content
                update_file=False,
                question=question,
                order=idx,
                value=str(option.value),  # Convert to string for CharField
            )
            option_uuids.append((idx, option_obj.id))
            saved_options[option_obj.value] = option_obj

        # Update file with option UUIDs if any options didn't have UUIDs
        if any(opt.uuid is None for opt in item.options):
            update_file_with_option_uuids(item.file_path, question.id, option_uuids)

    return question, saved_options


def mark_dropped_questions(
    site: Site, loaded_form_ids: set[uuid.UUID], seen_question_ids: set[uuid.UUID]
) -> None:
    """Mark the loaded forms' questions that their files no longer hold, and unmark the rest.

    Scoped to forms this run loaded, so a partial load never marks another
    form's questions. A question moved to another loaded form was saved onto
    its new page first, so it is seen and stays unmarked.
    """
    # The load runs with no request, so there is no current site to filter
    # by: the base manager with an explicit site, as the loader's other reads do.
    questions = FormQuestion._base_manager.filter(site=site)
    dropped = list(
        questions.filter(form_page__form_id__in=loaded_form_ids)
        .exclude(pk__in=seen_question_ids)
        .values_list("pk", flat=True)
    )
    questions.filter(pk__in=dropped, dropped_from_source_at__isnull=True).update(
        dropped_from_source_at=timezone.now()
    )
    questions.filter(
        pk__in=seen_question_ids, dropped_from_source_at__isnull=False
    ).update(dropped_from_source_at=None)
    if dropped:
        form_questions_dropped.send(sender=FormQuestion, question_ids=dropped)


def replace_question_sections(
    sections_by_question: Sequence[tuple[FormQuestion, list[models.Model]]],
) -> None:
    """Set each question's sections to exactly its list, in a fixed number of queries.

    Empty lists count too, so a path removed from the file drops that section.
    A row that is still wanted keeps its id. Targets are this run's saved rows,
    already checked by validate_question_sections, so they are always this
    site's topics and parts.
    """
    question_ids = [question.id for question, _ in sections_by_question]
    _sync_section_rows(
        FormQuestionTopic,
        "topic_id",
        _section_pairs(sections_by_question, Topic),
        question_ids,
        lambda question_id, topic_id: FormQuestionTopic(
            question_id=question_id, topic_id=topic_id
        ),
    )
    _sync_section_rows(
        FormQuestionCoursePart,
        "course_part_id",
        _section_pairs(sections_by_question, CoursePart),
        question_ids,
        lambda question_id, part_id: FormQuestionCoursePart(
            question_id=question_id, course_part_id=part_id
        ),
    )


def _section_pairs(
    sections_by_question: Sequence[tuple[FormQuestion, list[models.Model]]],
    target_type: type[Topic] | type[CoursePart],
) -> set[tuple[uuid.UUID, uuid.UUID]]:
    """The (question id, target id) pairs whose target is of target_type."""
    return {
        (question.id, target.pk)
        for question, targets in sections_by_question
        for target in targets
        if isinstance(target, target_type)
    }


def _sync_section_rows[Row: (FormQuestionTopic, FormQuestionCoursePart)](
    through: type[Row],
    target_field: str,
    wanted: set[tuple[uuid.UUID, uuid.UUID]],
    question_ids: list[uuid.UUID],
    make_row: Callable[[uuid.UUID, uuid.UUID], Row],
) -> None:
    """Delete the questions' rows not in wanted and create the missing ones."""
    existing = {
        (question_id, target_id): pk
        for pk, question_id, target_id in through._default_manager.filter(
            question_id__in=question_ids
        ).values_list("pk", "question_id", target_field)
    }
    stale = [pk for pair, pk in existing.items() if pair not in wanted]
    if stale:
        through._default_manager.filter(pk__in=stale).delete()
    through._default_manager.bulk_create(
        [make_row(*pair) for pair in wanted - existing.keys()]
    )


# What deleting a part placement takes with it, as Django's collector labels it, and how
# the report names it: the placement's own cascades plus what part_placement_removed
# receivers report. Labels, not imports: the deadline models live in an app that depends
# on this one.
_PLACEMENT_CASCADES = (
    ("freedom_ls_deadlines.CohortDeadlineOverride", "cohort deadline override(s)"),
    ("freedom_ls_deadlines.LearnerDeadlineOverride", "learner deadline override(s)"),
    ("freedom_ls_deadlines.DeadlineExtension", "deadline extension(s)"),
    ("freedom_ls_content_engine.CoursePartChildDueDate", "part child due date(s)"),
)


def remove_part_placement(site: Site, course: Course, part: CoursePart) -> str | None:
    """Delete this course's placement of a part it now lists as reference material, and
    say what went with it. None when the course did not place the part."""
    total, deleted = ContentCollectionItem.objects.filter(
        site=site,
        collection_type=DjangoContentType.objects.get_for_model(Course),
        collection_id=course.id,
        child_type=DjangoContentType.objects.get_for_model(CoursePart),
        child_id=part.id,
    ).delete()
    if not total:
        return None
    deleted_by_label = Counter(deleted)
    for _receiver, response in part_placement_removed.send(
        sender=ContentCollectionItem, site=site, course=course, part=part
    ):
        if response:
            deleted_by_label.update(response)
    counts = ", ".join(
        f"{deleted_by_label[label]} {noun}" for label, noun in _PLACEMENT_CASCADES
    )
    return (
        f"Removed part placement: {course.file_path} no longer places {part.file_path} "
        "in its learning path (it is listed under reference:).\n"
        f"  Deleted with it: {counts}."
    )


def sync_reference_parts(
    site: Site,
    collections_data: Sequence[tuple[Course | CoursePart, BaseBaseContentModel]],
    content_by_path: Mapping[Path, models.Model],
) -> list[str]:
    """Write each loaded course's reference parts from its reference: list. Returns the
    lines that report what was removed, for the caller to print once the load is safe."""
    removal_lines: list[str] = []
    for course, schema_item in collections_data:
        if not isinstance(course, Course) or not isinstance(schema_item, CourseSchema):
            continue
        part_ids: list[uuid.UUID] = []
        parts: list[CoursePart] = []
        for order, entry in enumerate(schema_item.reference):
            part_path = resolve_author_path(schema_item.file_path, entry.path)
            part = content_by_path.get(part_path)
            if part is None:
                # A silently dropped entry is a course missing reference material
                # nobody notices.
                raise ValueError(
                    f"Course '{course.title}' lists {part_path} under reference:, "
                    "but it was not loaded with the course; load a directory that "
                    "holds both the course and the part"
                )
            if not isinstance(part, CoursePart):
                raise ValueError(
                    f"Course '{course.title}' lists {part_path} under reference:, "
                    "which is not a COURSE_PART"
                )
            CourseReferencePart.objects.update_or_create(
                site=site, course=course, course_part=part, defaults={"order": order}
            )
            part_ids.append(part.id)
            parts.append(part)
        # The file is the single source of a course's reference parts, so a row the
        # list no longer names goes. Only courses in this load are touched.
        CourseReferencePart.objects.filter(site=site, course=course).exclude(
            course_part_id__in=part_ids
        ).delete()
        # Runs before the part child due date reconcile, which would delete the
        # placement's child due dates first and leave the report counting none.
        for part in parts:
            line = remove_part_placement(site, course, part)
            if line is not None:
                removal_lines.append(line)
    return removal_lines


def get_file_type_from_extension(file_path):
    """Determine file type based on file extension."""
    extension = file_path.suffix.lower()

    document_extensions = {".pdf", ".doc", ".docx", ".txt", ".rtf", ".odt"}
    video_extensions = {".mp4", ".avi", ".mov", ".wmv", ".flv", ".webm", ".mkv"}
    audio_extensions = {".mp3", ".wav", ".ogg", ".m4a", ".flac", ".aac"}

    if extension in IMAGE_EXTENSIONS:
        return File.FileType.IMAGE
    elif extension in document_extensions:
        return File.FileType.DOCUMENT
    elif extension in video_extensions:
        return File.FileType.VIDEO
    elif extension in audio_extensions:
        return File.FileType.AUDIO
    else:
        return File.FileType.OTHER


def _format_bytes(num_bytes: int) -> str:
    """Render a byte count for the author, e.g. `5.1 MB` or `118 KB`.

    One decimal place below 10 units, none above -- enough precision to show
    the reduction without implying an accuracy the encoder doesn't have.
    """
    value = float(num_bytes)
    unit = "B"
    for unit in ("B", "KB", "MB", "GB"):
        if value < 1024 or unit == "GB":
            break
        value /= 1024
    if unit == "B":
        return f"{int(value)} {unit}"
    return f"{value:.1f} {unit}" if value < 10 else f"{value:.0f} {unit}"


def _format_image_decision_line(decision: ImageEncodeDecision) -> str:
    """The source-and-outcome line for one image decision, from the decision alone.

    `OPTIMISED` is the only status with a source-to-target arrow; every other
    status names the source, when Pillow got far enough to know it, and ends
    in the status word so the four outcomes stay greppable.
    """
    # The ImageEncodeDecision contract sets source_size and stored_size
    # together with data, and never leaves either None for this status.
    if (
        decision.status is ImageEncodeStatus.OPTIMISED
        and decision.source_size is not None
        and decision.stored_size is not None
    ):
        source_width, source_height = decision.source_size
        stored_width, stored_height = decision.stored_size
        lossy_word = "lossless" if decision.lossless else "lossy"
        return (
            f"{decision.source_format} {source_width}x{source_height} -> "
            f"WebP {lossy_word} {stored_width}x{stored_height}"
        )

    if decision.source_format is None:
        return f"{decision.status}."

    if decision.source_size is None:
        return f"{decision.source_format}, {decision.status}."

    source_width, source_height = decision.source_size
    reason = (
        "re-encode not smaller, "
        if decision.status is ImageEncodeStatus.KEPT_SOURCE
        else ""
    )
    return f"{decision.source_format} {source_width}x{source_height}, {reason}{decision.status}."


def read_audio_duration(file_path: Path) -> float | None:
    """Seconds of audio in the local source file, or None when mutagen can't read it."""
    try:
        audio = mutagen.File(file_path)
    except (mutagen.MutagenError, OSError):
        return None
    if audio is None:
        return None
    length = float(audio.info.length)
    # A header-only file reports 0.0, which would give a seek bar with no range.
    return length if length > 0 else None


def save_file_to_db(
    file_path: Path, site: Site, base_path: Path, cache: ImageCache
) -> ImageEncodeDecision | None:
    """Save a single file to the database, optimising it first if it is an image."""
    relative_path = str(file_path.relative_to(base_path))
    file_type = get_file_type_from_extension(file_path)
    mime_type, _ = mimetypes.guess_type(str(file_path))

    decision: ImageEncodeDecision | None = None
    before_bytes: int | None = None
    if file_type == File.FileType.IMAGE:
        raw = file_path.read_bytes()
        decision = cache.decide(file_path, raw)
        before_bytes = len(raw)
        if decision.data is not None:
            mime_type = decision.mime_type

    duration_seconds = (
        read_audio_duration(file_path) if file_type == File.FileType.AUDIO else None
    )

    # Get or create the File record (without the file field)
    file_obj, created = File.objects.get_or_create(
        site=site,
        file_path=relative_path,
        defaults={
            "file_type": file_type,
            "original_filename": file_path.name,
            "mime_type": mime_type or "",
            "duration_seconds": duration_seconds,
        },
    )

    # Update metadata if it's an existing record
    if not created:
        file_obj.file_type = file_type
        file_obj.original_filename = file_path.name
        file_obj.mime_type = mime_type or ""
        # None for a non-audio file clears a value left from when it was audio.
        file_obj.duration_seconds = duration_seconds
        # A file found in the source is live; the save below persists the row.
        file_obj.retired_at = None

    if (
        decision is not None
        and decision.data is not None
        and decision.suffix is not None
    ):
        stored_name = file_path.with_suffix(decision.suffix).name
        encoded = ContentFile(decision.data)
    else:
        stored_name = file_path.name
        encoded = None

    # course_media never overwrites an existing key, so a superseded object
    # has to be dealt with explicitly, and when depends on whether the key
    # changes. file_upload_handler keys on the extension: a re-run at the
    # same extension writes back to the same key, which has to be cleared
    # first or the write is renamed and the key stops being stable across
    # runs. An extension change writes to a different key, where deleting the
    # old object inline would strand every File row still naming it if a
    # later step rolled this atomic run back, so that delete waits for the
    # commit instead.
    superseded_name = file_obj.file.name
    if superseded_name:
        storage = file_obj.file.storage
        if (
            file_obj.file.field.generate_filename(file_obj, stored_name)
            == superseded_name
        ):
            file_obj.file.delete(save=False)
        else:
            transaction.on_commit(partial(storage.delete, superseded_name))

    if encoded is not None:
        file_obj.file.save(stored_name, encoded, save=True)
    else:
        with open(file_path, "rb") as f:
            file_obj.file.save(stored_name, DjangoFile(f), save=True)

    action = "Created" if created else "Updated"
    lines = [f"{action} {file_type} file: {relative_path}"]
    if file_type == File.FileType.AUDIO and duration_seconds is None:
        lines.append(
            f"  Could not read the audio duration of {relative_path}; it stays empty."
        )
    if decision is not None:
        lines.append(f"  {_format_image_decision_line(decision)}")
        if decision.data is not None and before_bytes is not None:
            after_bytes = len(decision.data)
            percent = (after_bytes - before_bytes) / before_bytes * 100
            lines.append(
                f"  {_format_bytes(before_bytes)} -> {_format_bytes(after_bytes)} "
                f"({percent:.1f}%), {decision.status}."
            )
        elif decision.status is ImageEncodeStatus.UNDECODABLE:
            logger.warning(f"Could not decode {relative_path}: {decision.error}")
    click.echo("\n".join(lines))

    return decision


@dataclass
class _ParsedSource:
    """One source path with every file read and parsed, before anything is written."""

    path: Path
    all_files: list[Path]
    content_files: set[Path]
    all_parsed: list[BaseBaseContentModel]
    ignore: frozenset[Path]


CONTENT_SUFFIXES = frozenset({".md", ".yaml", ".yml"})


def _parse_source(path: Path) -> _ParsedSource:
    ignore = ignore_list_for(path)
    all_files = get_all_files(path, ignore=ignore)
    content_files = {f for f in all_files if f.suffix in CONTENT_SUFFIXES}
    all_parsed: list[BaseBaseContentModel] = []
    for file_path in all_files:
        if file_path in content_files:
            all_parsed.extend(parse_single_file(file_path))
    return _ParsedSource(path, all_files, content_files, all_parsed, ignore)


def _relative_to_source(source: Path, file_path: Path) -> str:
    base = source.parent if source.is_file() else source
    return file_path.relative_to(base).as_posix()


def _refuse_relative_path_collisions(sources: Sequence[_ParsedSource]) -> None:
    """Refuse two source paths that hold a file at the same relative path.

    Template tags look a file up by its relative path alone and a `File` row is
    overwritten silently, so no database constraint would catch the clash.
    """
    owners: dict[str, list[Path]] = defaultdict(list)
    for source in sources:
        for file_path in source.all_files:
            owners[_relative_to_source(source.path, file_path)].append(source.path)
    clashes = {rel: paths for rel, paths in owners.items() if len(paths) > 1}
    if not clashes:
        return
    count = len(clashes)
    raise CommandError(
        _refusal(
            f"content_save found {count} file{'s' if count != 1 else ''} at the "
            "same relative path in more than one source path.",
            [
                (relative, [f"Source path: {p}" for p in paths])
                for relative, paths in clashes.items()
            ],
            "Rename or remove one of each pair, then run again.",
        )
    )


def _course_retire_refusal(course_pks: Collection[uuid.UUID]) -> str:
    """The refusal for a run that would retire the given courses."""
    rows = Course._base_manager.filter(pk__in=course_pks).order_by("title")
    return _refusal(
        f"content_save would retire {rows.count()} "
        f"course{'s' if rows.count() != 1 else ''}, which closes "
        f"{'them' if rows.count() != 1 else 'it'} to every learner.",
        [("Courses no source path names:", [f"{c.title} ({c.pk})" for c in rows])],
        "Restore the course files, or run again with --allow-course-retire.",
    )


def _refuse_course_retire(site: Site, sources: Sequence[_ParsedSource]) -> None:
    """Refuse a run whose source paths lack a live course of the site."""
    source_uuids = {
        item.uuid
        for source in sources
        for item in _items_of(source.all_parsed, CourseSchema)
        if item.uuid
    }
    missing = (
        Course._base_manager.filter(site=site, retired_at__isnull=True)
        .exclude(pk__in=source_uuids)
        .values_list("pk", flat=True)
    )
    if missing:
        raise CommandError(_course_retire_refusal(list(missing)))


def _items_of[T: BaseBaseContentModel](
    items: Sequence[BaseBaseContentModel], schema: type[T]
) -> list[T]:
    """The parsed items of one schema class, in their original order."""
    return [item for item in items if isinstance(item, schema)]


def _write_source(
    source: _ParsedSource, site: Site, ledger: _RunLedger
) -> tuple[list[ImageEncodeStatus], list[str]]:
    """Write a `_ParsedSource`'s files and content rows. Returns its image statuses and
    the lines that report the part placements it removed."""
    # The statuses alone: an ImageEncodeDecision carries the encoded bytes,
    # and holding one per image would keep every encode of the run in memory
    # to produce a count.
    image_statuses: list[ImageEncodeStatus] = []
    cache = ImageCache(source.path)

    # Save non-content files (images, documents, etc.) to the database
    for file_path in source.all_files:
        if file_path not in source.content_files:
            ledger.seen[File].add(_relative_to_source(source.path, file_path))
            decision = save_file_to_db(file_path, site, source.path, cache)
            if decision is not None:
                image_statuses.append(decision.status)

    # After the manifests, not before: write_manifests() reads directories
    # this run never scanned, so an unreadable manifest it finds there raises
    # its notice last, and echoing first would swallow exactly the warning
    # that explains a cache it then cleared out.
    cache.write_manifests()
    for notice in cache.notices:
        click.echo(notice)
    if cache.written or cache.removed:
        click.echo(
            f"Wrote {len(cache.written)} and removed {len(cache.removed)} file(s) "
            f"under {CACHE_DIR_NAME}/. Commit them alongside the content change, or "
            "every other clone pays the full encode again."
        )

    # Group by content type
    grouped = defaultdict(list)
    for item in source.all_parsed:
        grouped[item.content_type].append(item)

    # Mapping of file paths to saved content objects for collection children resolution
    content_by_path = {}
    # The parsed file behind each child, for the due date columns on its collection items.
    schema_by_path: dict[Path, BaseBaseContentModel] = {}

    # Save CourseCategories, ahead of Courses so a course's categories/
    # dashboard_category resolve against rows that already exist.
    for item in grouped.get(SchemaContentType.COURSE_CATEGORIES, []):
        categories = save_course_categories(item, site, source.path)
        for category in categories:
            ledger.saw(category)
        logger.info(f"Saved {len(categories)} CourseCategory row(s)")

    # Save Topics
    for item in grouped.get(SchemaContentType.TOPIC, []):
        topic = save_topic(item, site, source.path)
        ledger.saw(topic)
        content_by_path[content_key(item.file_path)] = topic
        schema_by_path[content_key(item.file_path)] = item
        logger.info(f"Saved Topic: {topic.title}")

    # Save Activities
    for item in grouped.get(SchemaContentType.ACTIVITY, []):
        activity = save_activity(item, site, source.path)
        ledger.saw(activity)
        content_by_path[content_key(item.file_path)] = activity
        schema_by_path[content_key(item.file_path)] = item
        logger.info(f"Saved Activity: {activity.title}")

    # Save Articles. They are not added to content_by_path: an article is never
    # a collection child.
    for item in grouped.get(SchemaContentType.ARTICLE, []):
        article = save_article(item, site, source.path)
        ledger.saw(article)
        logger.info(f"Saved Article: {article.title}")

    # Save Courses and CourseParts
    # (collection_obj, schema_item), kept for the children processing below
    collections_data: list[
        tuple[Course | CoursePart, CourseSchema | CoursePartSchema]
    ] = []
    for item in _items_of(source.all_parsed, CourseSchema):
        collection = save_course(item, site, source.path)
        ledger.saw(collection)
        content_by_path[content_key(item.file_path)] = collection
        schema_by_path[content_key(item.file_path)] = item
        collections_data.append((collection, item))
        logger.info(f"Saved Course: {collection.title}")

    for item in _items_of(source.all_parsed, CoursePartSchema):
        collection = save_course_part(item, site, source.path)
        ledger.saw(collection)
        content_by_path[content_key(item.file_path)] = collection
        schema_by_path[content_key(item.file_path)] = item
        collections_data.append((collection, item))
        logger.info(f"Saved CoursePart: {collection.title}")

    # Save Forms and track them by directory
    forms_by_dir: dict[Path, tuple[Form, form_schema.Form]] = {}
    for item in _items_of(source.all_parsed, form_schema.Form):
        form = save_form(item, site, source.path)
        ledger.saw(form)
        forms_by_dir[item.file_path.parent] = (form, item)
        content_by_path[content_key(item.file_path)] = form
        schema_by_path[content_key(item.file_path)] = item
        logger.info(f"Saved Form: {form.title}")

    # Group form pages by file
    pages_by_file: defaultdict[Path, list[form_schema.FormPage]] = defaultdict(list)
    for item in _items_of(source.all_parsed, form_schema.FormPage):
        pages_by_file[item.file_path].append(item)

    # Group pages by parent form directory
    pages_by_form: defaultdict[Path, list[tuple[Path, list[form_schema.FormPage]]]] = (
        defaultdict(list)
    )
    for file_path, page_items in pages_by_file.items():
        form_entry = forms_by_dir.get(file_path.parent)
        if form_entry:
            pages_by_form[file_path.parent].append((file_path, page_items))

    sections_by_question: list[tuple[FormQuestion, list[models.Model]]] = []
    seen_question_ids: set[uuid.UUID] = set()
    # Save form pages and their content in alphabetical order per form
    for form_dir, form_pages in pages_by_form.items():
        parent_form, form_item = forms_by_dir[form_dir]
        options_by_slug: dict[str, dict[str, QuestionOption]] = {}
        # Sort pages by file path alphabetically
        for page_order, (file_path, page_items) in enumerate(sorted(form_pages)):
            if page_items:
                page_item = page_items[0]
                # Pages are processed in alphabetical order by filename
                # First page gets order=0, second gets order=1, etc.
                form_page = save_form_page(
                    page_item,
                    parent_form,
                    site,
                    source.path,
                    order=page_order,
                    condition_option=_resolve_condition(
                        page_item.when, options_by_slug, file_path
                    ),
                )
                ledger.saw(form_page)
                logger.info(f"Saved FormPage: {form_page.title} (order={page_order})")

                # Get all content items from this file in the order they appear in the YAML
                file_content_items = [
                    item
                    for item in source.all_parsed
                    if item.file_path == file_path
                    and isinstance(
                        item, (form_schema.FormContent, form_schema.FormQuestion)
                    )
                ]

                # Save texts and questions in the order they appear in the file
                for content_order, item in enumerate(file_content_items):
                    if isinstance(item, form_schema.FormContent):
                        form_content = save_form_content(
                            item,
                            form_page,
                            site,
                            source.path,
                            order=content_order,
                            condition_option=_resolve_condition(
                                item.when, options_by_slug, file_path
                            ),
                        )
                        ledger.saw(form_content)
                        logger.info(
                            f"Saved FormContent in {form_page.title} (order={content_order})"
                        )
                    else:
                        question, saved_options = save_form_question(
                            item,
                            form_page,
                            site,
                            source.path,
                            order=content_order,
                            condition_option=_resolve_condition(
                                item.when, options_by_slug, file_path
                            ),
                        )
                        seen_question_ids.add(question.pk)
                        ledger.saw(question)
                        for saved_option in saved_options.values():
                            ledger.saw(saved_option)
                        declarer, section_paths = effective_sections(item, form_item)
                        sections_by_question.append(
                            (
                                question,
                                [
                                    content_by_path[
                                        resolve_author_path(declarer.file_path, p)
                                    ]
                                    for p in section_paths
                                ],
                            )
                        )
                        if item.slug:
                            options_by_slug[item.slug] = saved_options
                        logger.info(
                            f"Saved FormQuestion in {form_page.title} (order={content_order})"
                        )

    replace_question_sections(sections_by_question)
    mark_dropped_questions(
        site,
        {form.pk for form, _ in forms_by_dir.values()},
        seen_question_ids,
    )

    # Bind each course to the application form its access_config names. Writing
    # None when the key is absent is what makes deleting the line unbind the
    # form: save_with_uuid's update_or_create would otherwise leave the old value.
    #
    # This binding and validate_application_form_declarations are the only places in
    # core that read an access_config key by name.
    # content_engine already owns the Course.application_form foreign key, and the
    # form has to be resolved against the file that declared it, which only the
    # loader can do — so the key is read here rather than by the access backend.
    for collection, schema_item in collections_data:
        if not isinstance(collection, Course) or not isinstance(
            schema_item, CourseSchema
        ):
            continue
        form = None
        author_path = (schema_item.access_config or {}).get("application_form")
        if author_path is not None:
            form_path = resolve_author_path(schema_item.file_path, author_path)
            form = content_by_path.get(form_path)
            if not isinstance(form, Form):
                raise ValueError(
                    f"Course '{collection.title}' names application_form {form_path}, "
                    f"which is not a loaded FORM"
                )
        if collection.application_form_id != (form.pk if form else None):
            collection.application_form = form
            collection.save(update_fields=["application_form"])

    # Process collection children
    written: list[ContentCollectionItem] = []
    created: list[ContentCollectionItem] = []
    row_by_placement: dict[tuple[uuid.UUID, Path], ContentCollectionItem] = {}
    for collection, schema_item in collections_data:
        if isinstance(collection, Course) and isinstance(schema_item, CourseSchema):
            # A replace, not a merge: a slug dropped from `categories` and
            # reloaded drops that membership, which is the one place a load
            # takes something away rather than only adding or updating.
            collection.categories.set(
                CourseCategory._base_manager.filter(
                    site=site, slug__in=schema_item.categories
                )
            )

        # Create ContentCollectionItem entries for each child. An auto-discovered
        # child has no entry.
        for order, (child_path, entry) in enumerate(
            collection_children(schema_item, ignore=source.ignore)
        ):
            child_content = content_by_path.get(child_path)
            if child_content:
                # Get the Django ContentType for both collection and child
                collection_content_type = DjangoContentType.objects.get_for_model(
                    collection
                )
                child_content_type = DjangoContentType.objects.get_for_model(
                    child_content
                )

                # Create or update the ContentCollectionItem
                row, was_created = ContentCollectionItem.objects.update_or_create(
                    site=site,
                    collection_type=collection_content_type,
                    collection_id=collection.id,
                    child_type=child_content_type,
                    child_id=child_content.id,
                    defaults={
                        "order": order,
                        **placement_due_columns(entry, schema_by_path.get(child_path)),
                    },
                )
                written.append(row)
                row_by_placement[(collection.id, child_path)] = row
                if was_created:
                    created.append(row)
                logger.info(
                    f"Added {child_content.__class__.__name__} '{child_content.title}' "
                    f"to {collection.__class__.__name__} '{collection.title}' (order={order})"
                )
            else:
                # A silently dropped child is a course missing content nobody
                # notices, so this fails the whole atomic load instead.
                raise ValueError(
                    f"Collection '{collection.title}' names a child at "
                    f"{child_path} that was not loaded"
                )

    # Before the reference sync: a child moved out of a part that becomes reference
    # material is only seen as moved while the course still places that part, and what
    # follows the child must reach its new row before the removal deletes what is left.
    loaded_collections = {
        (DjangoContentType.objects.get_for_model(collection).pk, collection.id)
        for collection, _ in collections_data
    }
    moved = moved_children(site, written, loaded_collections)
    carry_placement_due_dates(site, moved)
    collection_items_synced.send(
        sender=ContentCollectionItem,
        site=site,
        created=created,
        written=written,
        moved=moved,
    )
    removal_lines = sync_reference_parts(site, collections_data, content_by_path)

    # A course is written before the parts it places, so the part's own rows exist only
    # now. Every part placement of every course in this load is reconciled: one whose
    # entry no longer has a nested list, and one the course no longer names at all (a
    # sync keeps the row a dropped child left behind, so its values would otherwise
    # stay in force). The load runs with no request, so the site goes on every write
    # and delete by hand.
    kept: list[uuid.UUID] = []
    loaded_course_ids: list[uuid.UUID] = []
    for collection, schema_item in collections_data:
        if not isinstance(schema_item, CourseSchema):
            continue
        loaded_course_ids.append(collection.id)
        for entry in schema_item.children or []:
            if not entry.children:
                continue
            part_path = resolve_author_path(schema_item.file_path, entry.path)
            part_placement = row_by_placement[(collection.id, part_path)]
            part_schema = schema_by_path[part_path]
            for nested in entry.children:
                child_row = row_by_placement[
                    (
                        part_placement.child_id,
                        resolve_author_path(part_schema.file_path, nested.path),
                    )
                ]
                value, _ = CoursePartChildDueDate.objects.update_or_create(
                    site=site,
                    part_collection_item=part_placement,
                    collection_item=child_row,
                    defaults=due_date_columns(nested),
                )
                kept.append(value.pk)
    CoursePartChildDueDate.objects.filter(
        site=site,
        part_collection_item__collection_type=DjangoContentType.objects.get_for_model(
            Course
        ),
        part_collection_item__collection_id__in=loaded_course_ids,
    ).exclude(pk__in=kept).delete()

    return image_statuses, removal_lines


@dataclass(frozen=True)
class SourceCommit:
    """The commit one source path is loaded from."""

    path: Path
    repo_path: str  # the source path relative to its content repo root, "" for the root
    commit: str  # the HEAD commit read by the git check


def save_content_to_db(
    paths: Path | str | Sequence[Path | str],
    site_name: str,
    *,
    generate_uuids: bool = True,
    source_commits: Sequence[SourceCommit] | None = None,
    retire_missing: bool = False,
    allow_course_retire: bool = False,
) -> None:
    """Scan through all validated files of every source path and save them as one.

    Every source path is parsed and checked before the first write. With
    `generate_uuids=False` a file that lacks a uuid is refused instead of
    being given one, so a save never rewrites the content files. When
    `source_commits` is given, a `ContentSave` records the commit each source
    path was loaded from, in the same transaction as the content rows. With
    `retire_missing=True`, every row of the site that no source path names is
    retired in the same transaction; a row that returns to the source is live again.
    A run that would retire a course is refused unless `allow_course_retire=True`,
    because retiring a course closes it to every learner.
    """
    # Printed only once the load's transaction is over, so a load that rolls back,
    # at its commit included, has reported no removal and no success.
    result = _write_sources(
        paths,
        site_name,
        generate_uuids=generate_uuids,
        source_commits=source_commits,
        retire_missing=retire_missing,
        allow_course_retire=allow_course_retire,
    )
    for line in result.removal_lines:
        click.echo(line)
    if retire_missing:
        click.echo(_retire_count_line(result.ledger))
    click.echo(f"✓ Successfully saved all content for site: {site_name}")

    image_statuses = result.image_statuses
    counts = Counter(image_statuses)
    per_status = ", ".join(
        f"{counts[status]} {status}" for status in ImageEncodeStatus if status in counts
    )
    summary = f"Images: {len(image_statuses)} seen"
    click.echo(f"{summary} ({per_status})." if per_status else f"{summary}.")


def _retire_missing(site: Site, ledger: _RunLedger, run_time: datetime) -> None:
    """Retire every live row of the site that the run did not find in the source."""
    for model in RETIRABLE_MODELS:
        live = model._base_manager.filter(site=site, retired_at__isnull=True)
        key = "file_path__in" if model is File else "pk__in"
        pks = list(
            live.exclude(**{key: ledger.seen[model]}).values_list("pk", flat=True)
        )
        # update() skips auto_now, and readers find changed rows by updated_at.
        model._base_manager.filter(pk__in=pks).update(
            retired_at=run_time, updated_at=run_time
        )
        ledger.retired[model] = set(pks)


@transaction.atomic
def _write_sources(
    paths: Path | str | Sequence[Path | str],
    site_name: str,
    *,
    generate_uuids: bool,
    source_commits: Sequence[SourceCommit] | None,
    retire_missing: bool,
    allow_course_retire: bool = False,
) -> _SaveResult:
    """Write every source path in one transaction. Returns the image statuses, the
    lines that report what was removed and the ledger of what was retired."""
    site = Site.objects.get(
        name=site_name,
    )
    # A lone str is itself a Sequence, so it is told apart by type.
    path_list = [paths] if isinstance(paths, (str, Path)) else list(paths)
    sources = [_parse_source(Path(p)) for p in path_list]

    # Checked here as well as in the command's validate(), because fixtures and downstream
    # projects call this function directly. Every placement error of every source at
    # once, before anything is written: the rows roll back with the transaction, but a
    # file already sent to storage does not.
    placement_errors = [
        error
        for source in sources
        for error in (
            *validate_children_lists(source.all_parsed, ignore=source.ignore),
            *validate_reference_lists(
                source.all_parsed, ignore=source.ignore, loaded_root=source.path
            ),
            *validate_due_date_placements(source.all_parsed, ignore=source.ignore),
            *validate_form_section_placement(
                source.all_parsed, check_form_folder=source.path.is_dir()
            ),
            *validate_question_sections(
                source.all_parsed, loaded_root=source.path, ignore=source.ignore
            ),
        )
    ]
    if placement_errors:
        raise ValueError("\n".join(placement_errors))

    if not generate_uuids:
        _refuse_missing_uuids(sources)
    _refuse_relative_path_collisions(sources)
    refuse_course_retire = retire_missing and not allow_course_retire
    if refuse_course_retire:
        _refuse_course_retire(site, sources)

    run_time = timezone.now()
    ledger = _RunLedger()
    if retire_missing:
        # The upsert clears retired_at, so rows that come back must be read first.
        ledger.retired_before = {
            model: set(
                model._base_manager.filter(
                    site=site, retired_at__isnull=False
                ).values_list("file_path" if model is File else "pk", flat=True)
            )
            for model in RETIRABLE_MODELS
        }
    image_statuses: list[ImageEncodeStatus] = []
    removal_lines: list[str] = []
    for source in sources:
        source_statuses, source_removals = _write_source(source, site, ledger)
        image_statuses.extend(source_statuses)
        removal_lines.extend(source_removals)

    if retire_missing:
        _retire_missing(site, ledger, run_time)
        # The guard compares parsed uuids; this reads what the sweep did, so it also
        # catches a course whose file parsed but was never written.
        if refuse_course_retire and ledger.retired[Course]:
            raise CommandError(_course_retire_refusal(ledger.retired[Course]))

    if source_commits is not None:
        content_save = ContentSave.objects.create(
            site=site, generate_uuids=generate_uuids
        )
        ContentSaveSource.objects.bulk_create(
            ContentSaveSource(
                content_save=content_save,
                order=order,
                repo_path=source_commit.repo_path,
                commit=source_commit.commit,
            )
            for order, source_commit in enumerate(source_commits)
        )

    return _SaveResult(image_statuses, removal_lines, ledger)


def _refusal(
    headline: str,
    groups: Sequence[tuple[str, Sequence[str]]],
    fix: str,
    *,
    limit: int | None = None,
) -> str:
    """The text of every content_save refusal: headline, groups, then the fix last.

    `limit` caps the lines shown per group; the rest collapse to "... and N more".
    """
    blocks = [f"❌ {headline}"]
    for heading, lines in groups:
        shown = list(lines) if limit is None else list(lines[:limit])
        block = [heading, *(f"  {line}" for line in shown)]
        if len(shown) < len(lines):
            block.append(f"  ... and {len(lines) - len(shown)} more")
        blocks.append("\n".join(block))
    blocks.append(fix)
    return "\n\n".join(blocks)


def _label(item: BaseBaseContentModel, block_number: int) -> str:
    """How a refusal names a section: the validator's label for form sections."""
    if isinstance(
        item,
        (
            form_schema.FormPage,
            form_schema.FormContent,
            form_schema.FormQuestion,
        ),
    ):
        return form_section_label(item, block_number)
    if isinstance(item, BaseContentModel):
        return f'{item.content_type} "{item.title}"'
    return str(item.content_type)


def missing_uuids(
    all_parsed: Sequence[BaseBaseContentModel],
) -> list[tuple[Path, str]]:
    """(file, description) for every uuid the save would have to generate."""
    found: list[tuple[Path, str]] = []
    content_blocks: Counter[Path] = Counter()
    for item in all_parsed:
        if isinstance(item, CourseCategories):
            # The document has no uuid of its own: each entry has one.
            found += [
                (item.file_path, f'category {position} ("{entry.title}")')
                for position, entry in enumerate(item.categories, start=1)
                if not entry.uuid
            ]
            continue
        if item.content_type == SchemaContentType.FORM_CONTENT:
            content_blocks[item.file_path] += 1
        label = _label(item, content_blocks[item.file_path])
        if not item.uuid:
            found.append((item.file_path, label))
        found += [
            (item.file_path, f"option {position} of {label}")
            for position, option in enumerate(
                getattr(item, "options", None) or [], start=1
            )
            if not option.uuid
        ]
    return found


def _refuse_missing_uuids(sources: Sequence[_ParsedSource]) -> None:
    """Raise CommandError listing every uuid the save would have to generate.

    With several source paths each file is headed by its source path, so two
    paths that both hold `topic.md` stay distinguishable.
    """
    by_file: dict[str, list[str]] = {}
    count = 0
    for source in sources:
        for file_path, description in missing_uuids(source.all_parsed):
            heading = _relative_to_source(source.path, file_path)
            if len(sources) > 1:
                heading = f"{source.path}: {heading}"
            by_file.setdefault(heading, []).append(description)
            count += 1
    if not count:
        return
    raise CommandError(
        _refusal(
            f"content_save found {count} missing uuid{'s' if count != 1 else ''}.",
            list(by_file.items()),
            "Run again with --generate-uuids, then commit the changed files.",
        )
    )


# Lines shown per group in the uncommitted-files refusal before "... and N more".
UNCOMMITTED_LINES_SHOWN = 20


IGNORED_BUT_UNCOMMITTED = (
    "(in the .fls-content.yaml ignore list; it still has to be committed)"
)


def _uncommitted_lines(
    entries: Sequence[UncommittedPath],
    root: Path,
    ignore: frozenset[Path],
) -> list[str]:
    """One line per entry, marking those the ignore list covers: they stay refused."""
    width = max(len(entry.kind) for entry in entries)
    return [
        f"{entry.kind.ljust(width)}  {entry.path}"
        + (
            f"  {IGNORED_BUT_UNCOMMITTED}"
            if is_ignored(root / entry.path, ignore)
            else ""
        )
        for entry in entries
    ]


def _uncommitted_under(
    source: Path, root: Path, ignore: frozenset[Path]
) -> list[UncommittedPath]:
    """Every file under `source` the save would read that no commit holds.

    Adds the gitignored files the directory scan still reads: they are in no
    commit and git status does not report them.
    """
    entries = uncommitted_paths(source)
    listed = {entry.path for entry in entries}
    tracked = tracked_files(source)
    # The scan path, not the resolved one: a committed symlink is tracked as the
    # link itself, and its target may sit outside the repo.
    for file_path in get_all_files(source.resolve(), ignore=ignore):
        relative = file_path.relative_to(root).as_posix()
        if file_path not in tracked and relative not in listed:
            entries.append(
                UncommittedPath(path=relative, kind="untracked (gitignored)")
            )
    return sorted(entries, key=lambda entry: entry.path)


def _uncommitted_config_file(root: Path) -> UncommittedPath | None:
    """The repo's `.fls-content.yaml` when it exists but no commit holds its current text."""
    config_file = root / CONFIG_FILE_NAME
    if not config_file.exists():
        return None
    entries = uncommitted_paths(config_file)
    if entries:
        return entries[0]
    if config_file not in tracked_files(root):
        return UncommittedPath(path=CONFIG_FILE_NAME, kind="untracked (gitignored)")
    return None


def check_committed(
    paths: Sequence[str], ignores: Sequence[frozenset[Path]]
) -> list[SourceCommit]:
    """Refuse any source path that is not a clean, committed git tree.

    Uncommitted files from every path come back in one refusal. Each content
    repo root's `.fls-content.yaml` is listed once, under the root, before one
    group per path headed by the path as it was typed. Returns the HEAD commit
    each path will be loaded from, in the order the paths were given. `ignores`
    holds each path's ignore list, in the same order: it narrows which gitignored
    files count as read, and exempts nothing from the dirty-file list. With
    `settings.DEBUG` on, uncommitted files are not refused.
    """
    commits: list[SourceCommit] = []
    root_entries: dict[Path, UncommittedPath] = {}
    dirty: list[tuple[str, list[UncommittedPath], Path, frozenset[Path]]] = []
    for path, ignore in zip(paths, ignores, strict=True):
        source = Path(path)
        root = find_repo_root(source)
        if root is None:
            raise CommandError(
                _refusal(
                    "content_save loads only committed content: "
                    f"{path} is not inside a git repository.",
                    [],
                    "Put the content in a git repository and commit it, then run again.",
                )
            )
        try:
            commit = head_commit_of(source)
        except ValueError as error:
            raise CommandError(
                _refusal(
                    f"content_save loads only committed content: {error}",
                    [],
                    "Make a first commit, then run again.",
                )
            ) from error
        repo_path = source.resolve().relative_to(root).as_posix()
        commits.append(
            SourceCommit(
                path=source,
                repo_path="" if repo_path == "." else repo_path,
                commit=commit,
            )
        )
        if submodules := submodule_paths(source):
            raise CommandError(
                _refusal(
                    f"content_save does not load content from git submodules: {path} "
                    f"holds {len(submodules)} submodule"
                    f"{'s' if len(submodules) != 1 else ''}.",
                    [(f"Content repo root: {root}", submodules)],
                    "Copy the files into the content repo, or remove the submodule, "
                    "then run again.",
                )
            )
        if root not in root_entries and (entry := _uncommitted_config_file(root)):
            root_entries[root] = entry
        entries = _uncommitted_under(source, root, ignore)
        if source.resolve() == root:
            entries = [e for e in entries if e.path != CONFIG_FILE_NAME]
        if entries:
            dirty.append((f"Source path: {path}", entries, root, ignore))
    # Under DEBUG, uncommitted files load as they are on disk, so authors can
    # preview edits locally before committing them.
    if (root_entries or dirty) and not settings.DEBUG:
        groups = [
            (
                f"Content repo root: {root}",
                _uncommitted_lines([entry], root, frozenset()),
            )
            for root, entry in root_entries.items()
        ] + [
            (heading, _uncommitted_lines(entries, root, ignore))
            for heading, entries, root, ignore in dirty
        ]
        count = len(root_entries) + sum(len(entries) for _, entries, _, _ in dirty)
        raise CommandError(
            _refusal(
                "content_save loads only committed content: "
                f"{count} uncommitted file{'s' if count != 1 else ''}.",
                groups,
                "Commit or remove these files, then run again.",
                limit=UNCOMMITTED_LINES_SHOWN,
            )
        )
    return commits


def check_source_paths(paths: Sequence[str]) -> list[frozenset[Path]]:
    """Refuse a source path that does not exist, repeats, or sits inside another.

    Returns each path's ignore list, in the order the paths were given. A
    malformed `ignore:` entry in a `.fls-content.yaml` is refused here, naming
    the entry and the file.
    """
    resolved: list[tuple[str, Path]] = []
    for path in paths:
        if not Path(path).exists():
            raise CommandError(
                _refusal(
                    f"content_save cannot find the source path {path}: it does not exist.",
                    [],
                    "Check the path, then run again.",
                )
            )
        resolved.append((path, Path(path).resolve()))
    for index, (path, real) in enumerate(resolved):
        for other_path, other_real in resolved[index + 1 :]:
            if real == other_real:
                problem = f"{path} and {other_path} are the same source path."
            elif real in other_real.parents or other_real in real.parents:
                inner, outer = (
                    (other_path, path)
                    if real in other_real.parents
                    else (path, other_path)
                )
                problem = (
                    f"{inner} is inside another source path, {outer}, so its "
                    "files would be loaded more than once."
                )
            else:
                continue
            raise CommandError(
                _refusal(
                    f"content_save was given overlapping source paths: {problem}",
                    [],
                    "Give each directory once, then run again.",
                )
            )
    ignores: list[frozenset[Path]] = []
    for path in paths:
        try:
            ignore = ignore_list_for(Path(path))
        except ValueError as error:
            raise CommandError(str(error).strip()) from error
        if is_ignored(Path(path), ignore):
            raise CommandError(
                _refusal(
                    f"content_save was given {path}, which is in the "
                    f"{CONFIG_FILE_NAME} ignore list, so nothing in it would be saved.",
                    [],
                    f"Remove it from ignore: in {CONFIG_FILE_NAME}, or give another "
                    "source path, then run again.",
                )
            )
        ignores.append(ignore)
    return ignores


def check_has_content(paths: Sequence[str], ignores: Sequence[frozenset[Path]]) -> None:
    """Refuse a source path with no file to load, and a run with no content file.

    A path holding only images or documents is allowed: another path's content
    can use them.
    """
    found_content = False
    for path, ignore in zip(paths, ignores, strict=True):
        files = get_all_files(Path(path), ignore=ignore)
        if not files:
            raise CommandError(
                _refusal(
                    f"content_save found no files to load in {path}.",
                    [],
                    "Give a path that holds content, then run again.",
                )
            )
        found_content = found_content or any(
            f.suffix in CONTENT_SUFFIXES for f in files
        )
    if not found_content:
        raise CommandError(
            _refusal(
                "content_save found no content files in "
                f"{', '.join(paths)}: nothing would be saved.",
                [],
                "Give a path that holds .md or .yaml content files, then run again.",
            )
        )


@click.command()
@click.argument("paths", nargs=-1, required=True)
@click.argument("site_name")
@click.option(
    "--generate-uuids",
    is_flag=True,
    default=False,
    help="Write a new uuid into every content file that lacks one.",
)
def command(paths: tuple[str, ...], site_name: str, generate_uuids: bool) -> None:
    """Validate and save committed content to the database.

    Several source paths load as one save:

        python manage.py content_save ../bloom_content ../bloom_extra Bloom

    Every source path must be inside a git repository with no uncommitted,
    staged, deleted or untracked files. No path may be, or sit inside,
    another. A file without a uuid is refused unless --generate-uuids is given.
    """
    ignores = check_source_paths(paths)
    source_commits = check_committed(paths, ignores)
    check_has_content(paths, ignores)
    logger.info("Validating content...")
    reports: list[str] = []
    for path, ignore in zip(paths, ignores, strict=True):
        try:
            validate(path, ignore=ignore)
        except ValueError as error:
            reports.append(f"Source path: {path}\n{error}")
    if reports:
        raise ValueError("\n\n".join(reports))
    logger.info("Validation complete!")

    logger.info("Saving to database...")
    save_content_to_db(
        paths,
        site_name,
        generate_uuids=generate_uuids,
        source_commits=source_commits,
    )
