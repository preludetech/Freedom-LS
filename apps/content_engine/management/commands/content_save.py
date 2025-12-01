"""
example usage:
python manage.py content_save  ../bloom_content Bloom
"""

import logging
import uuid
import mimetypes
import frontmatter
import yaml
from pathlib import Path
from collections import defaultdict

from django.contrib.sites.models import Site
from django.core.files import File as DjangoFile
from django.db import transaction
from django.utils.text import slugify

import djclick as click

from content_engine.validate import validate, get_all_files, parse_single_file
from content_engine.schema import ContentType as SchemaContentType
from content_engine.models import (
    Topic,
    Activity,
    ContentCollection,
    ContentCollectionItem,
    Form,
    FormPage,
    FormContent,
    FormQuestion,
    QuestionOption,
    File,
)
from django.contrib.contenttypes.models import ContentType as DjangoContentType

logger = logging.getLogger(__name__)


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
        if self.event.style == '|':
            return '|'

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
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()

        sections = content.split("---")
        # Account for leading --- (sections[0] might be empty)
        if sections and not sections[0].strip():
            sections = sections[1:]

        # Strip all sections to normalize formatting
        sections = [s.strip() for s in sections]

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

    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()

    sections = content.split("---")
    if sections and not sections[0].strip():
        sections = sections[1:]

    sections = [s.strip() for s in sections]

    # Find the question section with matching UUID
    for idx, section in enumerate(sections):
        section_data = yaml.safe_load(section)
        if section_data and section_data.get("uuid") == str(question_uuid):
            # Update options with UUIDs
            if "options" in section_data and section_data["options"]:
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


def get_unique_slug(model_class, site, base_slug, existing_uuid=None):
    """
    Generate a unique slug by appending -2, -3, etc. if needed.

    Args:
        model_class: The model class (Topic, Form, ContentCollection)
        site: The site object
        base_slug: The base slug to make unique
        existing_uuid: Optional UUID of existing object (to exclude from uniqueness check)

    Returns:
        A unique slug for the given site and model
    """
    slug = base_slug
    counter = 2

    while True:
        # Check if this slug exists
        queryset = model_class.objects.filter(site=site, slug=slug)

        # If we're updating an existing object, exclude it from the check
        if existing_uuid:
            try:
                queryset = queryset.exclude(id=uuid.UUID(existing_uuid))
            except (ValueError, AttributeError):
                pass  # Invalid UUID or None, continue without exclusion

        if not queryset.exists():
            return slug

        # Slug exists, try next number
        slug = f"{base_slug}-{counter}"
        counter += 1


def save_with_uuid(model_class, item, site, base_path, update_file=True, **fields):
    """Generic save function that handles UUID logic."""
    # Calculate relative path if base_path is provided
    if base_path:
        relative_path = str(item.file_path.relative_to(base_path))
        fields["file_path"] = relative_path

    # Ensure slug uniqueness if a slug field is provided
    if "slug" in fields:
        base_slug = fields["slug"]
        fields["slug"] = get_unique_slug(model_class, site, base_slug, item.uuid)

    if item.uuid:
        instance, created = model_class.objects.update_or_create(
            id=uuid.UUID(item.uuid), site=site, defaults=fields
        )
    else:
        instance = model_class.objects.create(site=site, **fields)
        if update_file:
            update_file_with_uuid(item.file_path, instance.id)
    return instance


def save_topic(item, site, base_path):
    """Save a Topic to the database."""
    return save_with_uuid(
        Topic,
        item,
        site,
        base_path,
        title=item.title,
        subtitle=item.subtitle,
        description=item.description,
        slug=slugify(item.title),
        content=item.content,
        meta=item.meta,
        tags=item.tags,
    )


def save_activity(item, site, base_path):
    """Save an Activity to the database."""
    return save_with_uuid(
        Activity,
        item,
        site,
        base_path,
        title=item.title,
        subtitle=item.subtitle,
        description=item.description,
        slug=slugify(item.title),
        content=item.content,
        category=item.category,
        meta=item.meta,
        tags=item.tags,
    )


def save_collection(item, site, base_path):
    """Save a ContentCollection to the database."""
    return save_with_uuid(
        ContentCollection,
        item,
        site,
        base_path,
        title=item.title,
        subtitle=item.subtitle,
        description=item.description,
        slug=slugify(item.title),
        meta=item.meta,
        tags=item.tags,
    )


def save_form(item, site, base_path):
    """Save a Form to the database."""
    return save_with_uuid(
        Form,
        item,
        site,
        base_path,
        title=item.title,
        subtitle=item.subtitle,
        description=item.description,
        slug=slugify(item.title),
        content=item.content,
        strategy=item.strategy,
        meta=item.meta,
        tags=item.tags,
    )


def save_form_page(item, form, site, base_path, order=0):
    """Save a FormPage to the database."""
    return save_with_uuid(
        FormPage,
        item,
        site,
        base_path,
        form=form,
        title=item.title,
        subtitle=item.subtitle,
        description=item.description,
        category=item.category,
        order=order,
        meta=item.meta,
        tags=item.tags,
    )


def save_form_content(item, form_page, site, order=0):
    """Save FormContent to the database."""
    return save_with_uuid(
        FormContent,
        item,
        site,
        None,  # No base_path for inline content
        form_page=form_page,
        content=item.content,
        order=order,
        meta=item.meta,
        tags=item.tags,
    )


def save_form_question(item, form_page, site, order=0):
    """Save FormQuestion and its options to the database."""
    question = save_with_uuid(
        FormQuestion,
        item,
        site,
        None,  # No base_path for inline content
        form_page=form_page,
        question=item.question,
        type=item.type,
        required=item.required,
        category=item.category,
        order=order,
        meta=item.meta,
        tags=item.tags,
    )

    if item.options:
        option_uuids = []
        for idx, option in enumerate(item.options):
            option_obj = save_with_uuid(
                QuestionOption,
                option,
                site,
                None,  # No base_path for inline content
                update_file=False,
                question=question,
                text=option.text,
                value=str(option.value),
                order=idx,
            )
            option_uuids.append((idx, option_obj.id))

        # Update file with option UUIDs if any options didn't have UUIDs
        if any(opt.uuid is None for opt in item.options):
            update_file_with_option_uuids(item.file_path, question.id, option_uuids)

    return question


def get_file_type_from_extension(file_path):
    """Determine file type based on file extension."""
    extension = file_path.suffix.lower()

    image_extensions = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".svg", ".webp"}
    document_extensions = {".pdf", ".doc", ".docx", ".txt", ".rtf", ".odt"}
    video_extensions = {".mp4", ".avi", ".mov", ".wmv", ".flv", ".webm", ".mkv"}
    audio_extensions = {".mp3", ".wav", ".ogg", ".m4a", ".flac", ".aac"}

    if extension in image_extensions:
        return File.FileType.IMAGE
    elif extension in document_extensions:
        return File.FileType.DOCUMENT
    elif extension in video_extensions:
        return File.FileType.VIDEO
    elif extension in audio_extensions:
        return File.FileType.AUDIO
    else:
        return File.FileType.OTHER


def save_file_to_db(file_path, site, base_path):
    """Save a single file to the database."""
    # Calculate relative path
    relative_path = str(file_path.relative_to(base_path))

    # Determine file type
    file_type = get_file_type_from_extension(file_path)

    # Get mime type
    mime_type, _ = mimetypes.guess_type(str(file_path))

    # Get or create the File record (without the file field)
    file_obj, created = File.objects.get_or_create(
        site=site,
        file_path=relative_path,
        defaults={
            "file_type": file_type,
            "original_filename": file_path.name,
            "mime_type": mime_type or "",
        },
    )

    # Update metadata if it's an existing record
    if not created:
        file_obj.file_type = file_type
        file_obj.original_filename = file_path.name
        file_obj.mime_type = mime_type or ""

    # Always update the actual file
    with open(file_path, "rb") as f:
        # Delete old file if it exists to avoid orphaned files
        if file_obj.file:
            file_obj.file.delete(save=False)

        # Save new file to proper upload_to location
        file_obj.file.save(file_path.name, DjangoFile(f), save=True)

    action = "Created" if created else "Updated"
    logger.info(f"{action} {file_type} file: {relative_path}")


@transaction.atomic
def save_content_to_db(path, site_name):
    """Scan through all validated files and save them to the database."""
    path = Path(path)
    # Get the site
    site = Site.objects.get(
        name=site_name,
    )

    # Parse all files using existing validation code
    all_files = get_all_files(path)
    all_parsed = []

    for file_path in all_files:
        if file_path.suffix in [".md", ".yaml", ".yml"]:
            parsed_items = parse_single_file(file_path)
            all_parsed.extend(parsed_items)
        else:
            # Save non-content files (images, documents, etc.) to the database
            save_file_to_db(file_path, site, path)

    # Group by content type
    grouped = defaultdict(list)
    for item in all_parsed:
        grouped[item.content_type].append(item)

    # Mapping of file paths to saved content objects for collection children resolution
    content_by_path = {}

    # Save Topics
    for item in grouped.get(SchemaContentType.TOPIC, []):
        topic = save_topic(item, site, path)
        content_by_path[item.file_path] = topic
        logger.info(f"Saved Topic: {topic.title}")

    # Save Activities
    for item in grouped.get(SchemaContentType.ACTIVITY, []):
        activity = save_activity(item, site, path)
        content_by_path[item.file_path] = activity
        logger.info(f"Saved Activity: {activity.title}")

    # Save Collections
    collections_data = []  # Store (collection_obj, schema_item) for later children processing
    for item in grouped.get(SchemaContentType.COLLECTION, []):
        collection = save_collection(item, site, path)
        content_by_path[item.file_path] = collection
        collections_data.append((collection, item))
        logger.info(f"Saved ContentCollection: {collection.title}")

    # Save Forms and track them by directory
    forms_by_dir = {}
    for item in grouped.get(SchemaContentType.FORM, []):
        form = save_form(item, site, path)
        forms_by_dir[item.file_path.parent] = form
        content_by_path[item.file_path] = form
        logger.info(f"Saved Form: {form.title}")

    # Group form pages by file
    pages_by_file = defaultdict(list)
    for item in grouped.get(SchemaContentType.FORM_PAGE, []):
        pages_by_file[item.file_path].append(item)

    # Group pages by parent form directory
    pages_by_form = defaultdict(list)
    for file_path, page_items in pages_by_file.items():
        parent_form = forms_by_dir.get(file_path.parent)
        if parent_form:
            pages_by_form[parent_form].append((file_path, page_items))

    # Save form pages and their content in alphabetical order per form
    for parent_form, form_pages in pages_by_form.items():
        # Sort pages by file path alphabetically
        for page_order, (file_path, page_items) in enumerate(sorted(form_pages)):
            if page_items:
                page_item = page_items[0]
                # Pages are processed in alphabetical order by filename
                # First page gets order=0, second gets order=1, etc.
                form_page = save_form_page(
                    page_item, parent_form, site, path, order=page_order
                )
                logger.info(f"Saved FormPage: {form_page.title} (order={page_order})")

                # Get all content items from this file in the order they appear in the YAML
                file_content_items = [
                    item
                    for item in all_parsed
                    if item.file_path == file_path
                    and item.content_type
                    in (SchemaContentType.FORM_CONTENT, SchemaContentType.FORM_QUESTION)
                ]

                # Save texts and questions in the order they appear in the file
                for content_order, item in enumerate(file_content_items):
                    if item.content_type == SchemaContentType.FORM_CONTENT:
                        save_form_content(item, form_page, site, order=content_order)
                        logger.info(
                            f"Saved FormContent in {form_page.title} (order={content_order})"
                        )
                    elif item.content_type == SchemaContentType.FORM_QUESTION:
                        save_form_question(item, form_page, site, order=content_order)
                        logger.info(
                            f"Saved FormQuestion in {form_page.title} (order={content_order})"
                        )

    # Process collection children
    for collection, schema_item in collections_data:
        children_list = schema_item.children if schema_item.children else []

        # If no children specified, scan the directory for all content files
        if not children_list:
            collection_dir = schema_item.file_path.parent
            # Get all content files in the collection directory (not subdirectories)
            dir_files = [
                f
                for f in collection_dir.iterdir()
                if f.is_file() and f.suffix in [".md", ".yaml", ".yml"]
            ]
            # Also include subdirectories as they might contain collections or forms
            dir_subdirs = [d for d in collection_dir.iterdir() if d.is_dir()]

            # Create Child-like objects for directory scanning
            for f in sorted(dir_files):
                if (
                    f != schema_item.file_path
                ):  # Don't include the collection file itself
                    children_list.append(
                        type("Child", (), {"path": f, "overrides": None})()
                    )

            # For subdirectories, look for main content files (forms or collections)
            for subdir in sorted(dir_subdirs):
                # Look for a main file in the subdirectory (form or collection)
                main_files = []
                for f in subdir.iterdir():
                    if f.is_file() and f.suffix in [".md", ".yaml", ".yml"]:
                        # Parse to check if it's a Form or Collection (top-level content)
                        parsed = parse_single_file(f)
                        if parsed and parsed[0].content_type in (
                            SchemaContentType.FORM,
                            SchemaContentType.COLLECTION,
                        ):
                            main_files.append(f)
                            break  # Found the main file

                if main_files:
                    children_list.append(
                        type("Child", (), {"path": main_files[0], "overrides": None})()
                    )

        # Create ContentCollectionItem entries for each child
        for order, child in enumerate(children_list):
            child_content = content_by_path.get(child.path)
            if child_content:
                # Get the Django ContentType for the child
                child_content_type = DjangoContentType.objects.get_for_model(
                    child_content
                )

                # Create or update the ContentCollectionItem
                ContentCollectionItem.objects.update_or_create(
                    site=site,
                    collection=collection,
                    child_type=child_content_type,
                    child_id=child_content.id,
                    defaults={
                        "order": order,
                        "overrides": child.overrides,
                    },
                )
                logger.info(
                    f"Added {child_content.__class__.__name__} '{child_content.title}' "
                    f"to collection '{collection.title}' (order={order})"
                )
            else:
                logger.warning(
                    f"Could not find content for path {child.path} "
                    f"in collection '{collection.title}'"
                )

    logger.info(f"✓ Successfully saved all content for site: {site_name}")


@click.command()
@click.argument("path")
@click.argument("site_name")
def command(path, site_name):
    """Validate and save content to database."""
    logger.info("Validating content...")
    validate(path)
    logger.info("Validation complete!")

    logger.info("Saving to database...")
    save_content_to_db(path, site_name)
