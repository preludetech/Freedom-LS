"""
example usage:
python manage.py content_save  ../bloom_content Bloom
"""

import logging
import uuid
import frontmatter
import yaml
from pathlib import Path
from collections import defaultdict

from django.contrib.sites.models import Site
from django.db import transaction

import djclick as click

from content_engine.validate import validate, get_all_files, parse_single_file
from content_engine.schema import ContentType as SchemaContentType
from content_engine.models import (
    Topic,
    Form,
    FormPage,
    FormText,
    FormQuestion,
    QuestionOption,
)

logger = logging.getLogger(__name__)


def represent_str(dumper, data):
    """Custom string representer that uses literal style for multi-line strings."""
    if "\n" in data:
        return dumper.represent_scalar("tag:yaml.org,2002:str", data, style="|")
    return dumper.represent_scalar("tag:yaml.org,2002:str", data)


# Create custom YAML dumper
class PreservingDumper(yaml.SafeDumper):
    pass


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


def save_with_uuid(model_class, item, site, update_file=True, **fields):
    """Generic save function that handles UUID logic."""
    if item.uuid:
        instance, created = model_class.objects.update_or_create(
            id=uuid.UUID(item.uuid), site=site, defaults=fields
        )
    else:
        instance = model_class.objects.create(site=site, **fields)
        if update_file:
            update_file_with_uuid(item.file_path, instance.id)
    return instance


def save_topic(item, site):
    """Save a Topic to the database."""
    return save_with_uuid(
        Topic,
        item,
        site,
        title=item.title,
        subtitle=item.subtitle,
        content=item.content,
        meta=item.meta,
        tags=item.tags,
    )


def save_form(item, site):
    """Save a Form to the database."""
    return save_with_uuid(
        Form,
        item,
        site,
        title=item.title,
        subtitle=item.subtitle,
        content=item.content,
        strategy=item.strategy,
        meta=item.meta,
        tags=item.tags,
    )


def save_form_page(item, form, site, order=0):
    """Save a FormPage to the database."""
    return save_with_uuid(
        FormPage,
        item,
        site,
        form=form,
        title=item.title,
        subtitle=item.subtitle,
        order=order,
        meta=item.meta,
        tags=item.tags,
    )


def save_form_text(item, form_page, site, order=0):
    """Save FormText to the database."""
    return save_with_uuid(
        FormText,
        item,
        site,
        form_page=form_page,
        text=item.text,
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

    # Group by content type
    grouped = defaultdict(list)
    for item in all_parsed:
        grouped[item.content_type].append(item)

    # Save Topics
    for item in grouped.get(SchemaContentType.TOPIC, []):
        topic = save_topic(item, site)
        logger.info(f"Saved Topic: {topic.title}")

    # Save Forms and track them by directory
    forms_by_dir = {}
    for item in grouped.get(SchemaContentType.FORM, []):
        form = save_form(item, site)
        forms_by_dir[item.file_path.parent] = form
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
                    page_item, parent_form, site, order=page_order
                )
                logger.info(f"Saved FormPage: {form_page.title} (order={page_order})")

                # Get all content items from this file in the order they appear in the YAML
                file_content_items = [
                    item
                    for item in all_parsed
                    if item.file_path == file_path
                    and item.content_type
                    in (SchemaContentType.FORM_TEXT, SchemaContentType.FORM_QUESTION)
                ]

                # Save texts and questions in the order they appear in the file
                for content_order, item in enumerate(file_content_items):
                    if item.content_type == SchemaContentType.FORM_TEXT:
                        save_form_text(item, form_page, site, order=content_order)
                        logger.info(
                            f"Saved FormText in {form_page.title} (order={content_order})"
                        )
                    elif item.content_type == SchemaContentType.FORM_QUESTION:
                        save_form_question(item, form_page, site, order=content_order)
                        logger.info(
                            f"Saved FormQuestion in {form_page.title} (order={content_order})"
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
