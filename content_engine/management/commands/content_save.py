"""
example usage:
python manage.py content_save  ../bloom_content Bloom
"""

import logging
from pathlib import Path
from collections import defaultdict

from django.contrib.sites.models import Site
from django.db import transaction

import djclick as click

from content_engine.validate import validate, _get_all_files, parse_single_file
from content_engine.schema import ContentType as SchemaContentType
from content_engine.models import (
    Topic, ContentCollection, Form, FormPage,
    FormText, FormQuestion, QuestionOption
)

logger = logging.getLogger(__name__)


def save_topic(item, site):
    """Save a Topic to the database."""
    return Topic.objects.create(
        site_id=site,
        title=item.title,
        subtitle=item.subtitle,
        meta=item.meta,
        tags=item.tags,
    )


def save_collection(item, site):
    """Save a ContentCollection to the database."""
    return ContentCollection.objects.create(
        site_id=site,
        title=item.title,
        subtitle=item.subtitle,
        children=item.children if isinstance(item.children, list) else [item.children],
        meta=item.meta,
        tags=item.tags,
    )


def save_form(item, site):
    """Save a Form to the database."""
    return Form.objects.create(
        site_id=site,
        title=item.title,
        subtitle=item.subtitle,
        strategy=item.strategy,
        meta=item.meta,
        tags=item.tags,
    )


def save_form_page(item, form, site, order=0):
    """Save a FormPage to the database."""
    return FormPage.objects.create(
        site_id=site,
        form=form,
        title=item.title,
        subtitle=item.subtitle,
        order=order,
        meta=item.meta,
        tags=item.tags,
    )


def save_form_text(item, form_page, site, order=0):
    """Save FormText to the database."""
    return FormText.objects.create(
        site_id=site,
        form_page=form_page,
        text=item.text,
        order=order,
        meta=item.meta,
        tags=item.tags,
    )


def save_form_question(item, form_page, site, order=0):
    """Save FormQuestion and its options to the database."""
    question = FormQuestion.objects.create(
        site_id=site,
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
        for idx, option in enumerate(item.options):
            QuestionOption.objects.create(
                site_id=site,
                question=question,
                text=option.text,
                value=str(option.value),
                order=idx,
            )

    return question


@transaction.atomic
def save_content_to_db(path, site_name):
    """Scan through all validated files and save them to the database."""
    path = Path(path)

    # Get or create the site
    site, created = Site.objects.get_or_create(
        name=site_name,
        defaults={'domain': site_name.lower().replace(' ', '')}
    )
    if created:
        logger.info(f"Created new site: {site_name}")

    # Clear existing content for this site
    logger.info(f"Clearing existing content for site: {site_name}")
    Topic.objects.filter(site_id=site).delete()
    ContentCollection.objects.filter(site_id=site).delete()
    Form.objects.filter(site_id=site).delete()

    # Parse all files using existing validation code
    all_files = _get_all_files(path)
    all_parsed = []

    for file_path in all_files:
        if file_path.suffix in ['.md', '.yaml', '.yml']:
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

    # Save Collections
    for item in grouped.get(SchemaContentType.COLLECTION, []):
        collection = save_collection(item, site)
        logger.info(f"Saved ContentCollection: {collection.title}")

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

    # Save form pages and their content
    for file_path, page_items in pages_by_file.items():
        parent_form = forms_by_dir.get(file_path.parent)

        if not parent_form:
            logger.warning(f"No parent form found for page: {file_path}")
            continue

        if page_items:
            page_item = page_items[0]
            form_page = save_form_page(page_item, parent_form, site, order=len(parent_form.pages.all()))
            logger.info(f"Saved FormPage: {form_page.title}")

            # Save texts and questions from this file
            texts = [item for item in grouped.get(SchemaContentType.FORM_TEXT, [])
                     if item.file_path == file_path]
            questions = [item for item in grouped.get(SchemaContentType.FORM_QUESTION, [])
                        if item.file_path == file_path]

            content_order = 0
            for item in texts:
                save_form_text(item, form_page, site, order=content_order)
                content_order += 1
                logger.info(f"Saved FormText in {form_page.title}")

            for item in questions:
                save_form_question(item, form_page, site, order=content_order)
                content_order += 1
                logger.info(f"Saved FormQuestion in {form_page.title}")

    logger.info(f"✓ Successfully saved all content for site: {site_name}")


@click.command()
@click.argument('path')
@click.argument('site_name')
def command(path, site_name):
    """Validate and save content to database."""
    logger.info("Validating content...")
    validate(path)
    logger.info("Validation complete!")

    logger.info("Saving to database...")
    save_content_to_db(path, site_name)
    