"""Create QA data for the "Override course access & details page" feature.

Seeds (idempotently, on a single site — default: DemoDev) the course-detail-page
variants that exercise the ``table_of_contents_in_development`` flag, the
"This course includes" assessments panel, and the visibility lifecycle states.

Courses created / ensured:

1. ``qa-toc-in-development`` — visibility=coming_soon, table_of_contents_in_development=TRUE,
   free access, lesson (Topic) children only and NO Form children, so the
   "This course includes" assessments panel is empty while a TOC still exists.

2. ``qa-toc-in-development-with-assessment`` — visibility=coming_soon,
   table_of_contents_in_development=TRUE, free access, some lesson (Topic)
   children PLUS at least one Form (assessment) child.

3. ``qa-hidden-course`` — visibility=hidden, free access, one lesson.

4. ``qa-free-course-access-types`` — topped up to 3 lesson (Topic) children so the
   "3 lessons" stat renders. This course is normally created by
   ``qa_create_course_access_types``; this command creates it (published, free)
   if absent and guarantees it has >= 3 lessons either way.

IMPORTANT spec constraint (see ``content_engine.schema.Course._validate_toc_in_development``
and the Django-side clean): a PUBLISHED course may not have
``table_of_contents_in_development=True``. The two TOC-in-development courses are
therefore ``coming_soon`` (not published).

All objects are created with the site-aware factories and an explicit ``site=``
override (the factories' thread-local site default is None outside a request).
"""

from typing import cast

import djclick as click

from django.contrib.contenttypes.models import ContentType as DjangoContentType
from django.contrib.sites.models import Site

from freedom_ls.content_engine.factories import (
    ContentCollectionItemFactory,
    CourseFactory,
    FormFactory,
    FormPageFactory,
    TopicFactory,
)
from freedom_ls.content_engine.models import (
    ContentCollectionItem,
    Course,
    CourseVisibility,
    Form,
    Topic,
)

TOC_NO_ASSESSMENT_SLUG = "qa-toc-in-development"
TOC_WITH_ASSESSMENT_SLUG = "qa-toc-in-development-with-assessment"
HIDDEN_SLUG = "qa-hidden-course"
FREE_ACCESS_TYPES_SLUG = "qa-free-course-access-types"


def _get_or_create_course(
    site: Site,
    *,
    title: str,
    slug: str,
    visibility: str,
    toc_in_development: bool,
    access_config: dict,
) -> Course:
    """Create/refresh a Course keyed on (slug, site). Idempotent."""
    course: Course | None = Course.objects.filter(slug=slug, site=site).first()
    if course is None:
        return cast(
            Course,
            CourseFactory(
                title=title,
                slug=slug,
                visibility=visibility,
                table_of_contents_in_development=toc_in_development,
                access_config=access_config,
                site=site,
            ),
        )
    course.title = title
    course.visibility = visibility
    course.table_of_contents_in_development = toc_in_development
    course.access_config = access_config
    course.save(
        update_fields=[
            "title",
            "visibility",
            "table_of_contents_in_development",
            "access_config",
        ]
    )
    return course


def _ensure_link(site: Site, course: Course, child: Topic | Form, order: int) -> None:
    """Ensure a ContentCollectionItem links ``child`` into ``course``. Idempotent."""
    collection_ct = DjangoContentType.objects.get_for_model(Course)
    child_ct = DjangoContentType.objects.get_for_model(type(child))
    exists = ContentCollectionItem.objects.filter(
        collection_type=collection_ct,
        collection_id=course.pk,
        child_type=child_ct,
        child_id=child.pk,
    ).exists()
    if not exists:
        ContentCollectionItemFactory(
            collection_object=course,
            child_object=child,
            site=site,
            order=order,
        )


def _ensure_topic_child(
    site: Site, course: Course, *, slug: str, title: str, order: int
) -> Topic:
    """Ensure a Topic (by slug) exists and is linked into ``course``. Idempotent."""
    topic: Topic | None = Topic.objects.filter(slug=slug, site=site).first()
    if topic is None:
        topic = cast(
            Topic,
            TopicFactory(
                title=title,
                slug=slug,
                content=f"# {title}\n\nQA lesson content so the course player resolves.",
                site=site,
            ),
        )
    _ensure_link(site, course, topic, order)
    return topic


def _ensure_form_child(
    site: Site, course: Course, *, slug: str, title: str, order: int
) -> Form:
    """Ensure a Form (by slug) with one page exists and is linked. Idempotent."""
    form: Form | None = Form.objects.filter(slug=slug, site=site).first()
    if form is None:
        form = cast(
            Form,
            FormFactory(
                title=title,
                slug=slug,
                site=site,
            ),
        )
        # A minimal page so the assessment is not hollow if a tester opens it.
        FormPageFactory(form=form, title=f"{title} - Page 1", site=site)
    _ensure_link(site, course, form, order)
    return form


def _count_lessons_and_forms(site: Site, slug: str) -> tuple[int, int]:
    """Re-query a FRESH Course instance and count lessons vs Form children.

    ``Course.viewable_items()`` is memoized per instance, so counts must be read
    from an instance fetched AFTER the links were created.
    """
    course = Course.objects.get(slug=slug, site=site)
    viewable = course.viewable_items()
    forms = sum(1 for c in viewable if isinstance(c, Form))
    lessons = len(viewable) - forms
    return lessons, forms


@click.command()
@click.argument("site_name", default="DemoDev")
def command(site_name: str) -> None:
    """Create course-detail-page variant QA data.

    SITE_NAME is the site to create data on (default: DemoDev).
    """
    try:
        site = Site.objects.get(name=site_name)
    except Site.DoesNotExist as e:
        available = list(Site.objects.values_list("name", flat=True))
        raise click.ClickException(
            f"Site '{site_name}' not found. Available: {available}"
        ) from e

    # 1. TOC-in-development, NO assessments (lessons only).
    toc_no_assess = _get_or_create_course(
        site,
        title="QA TOC In Development (No Assessment)",
        slug=TOC_NO_ASSESSMENT_SLUG,
        visibility=CourseVisibility.COMING_SOON,
        toc_in_development=True,
        access_config={"access_type": "free"},
    )
    for i in range(1, 4):
        _ensure_topic_child(
            site,
            toc_no_assess,
            slug=f"{TOC_NO_ASSESSMENT_SLUG}-lesson-{i}",
            title=f"TOC In Dev - Lesson {i}",
            order=i,
        )

    # 2. TOC-in-development, WITH at least one assessment.
    toc_with_assess = _get_or_create_course(
        site,
        title="QA TOC In Development (With Assessment)",
        slug=TOC_WITH_ASSESSMENT_SLUG,
        visibility=CourseVisibility.COMING_SOON,
        toc_in_development=True,
        access_config={"access_type": "free"},
    )
    _ensure_topic_child(
        site,
        toc_with_assess,
        slug=f"{TOC_WITH_ASSESSMENT_SLUG}-lesson-1",
        title="TOC In Dev (Assessed) - Lesson 1",
        order=1,
    )
    _ensure_topic_child(
        site,
        toc_with_assess,
        slug=f"{TOC_WITH_ASSESSMENT_SLUG}-lesson-2",
        title="TOC In Dev (Assessed) - Lesson 2",
        order=2,
    )
    _ensure_form_child(
        site,
        toc_with_assess,
        slug=f"{TOC_WITH_ASSESSMENT_SLUG}-assessment-1",
        title="TOC In Dev - Quiz",
        order=3,
    )

    # 3. Hidden course (free, one lesson).
    hidden = _get_or_create_course(
        site,
        title="QA Hidden Course",
        slug=HIDDEN_SLUG,
        visibility=CourseVisibility.HIDDEN,
        toc_in_development=False,
        access_config={"access_type": "free"},
    )
    _ensure_topic_child(
        site,
        hidden,
        slug=f"{HIDDEN_SLUG}-lesson-1",
        title="Hidden Course - Lesson 1",
        order=1,
    )

    # 4. Free access-types course: guarantee 3 lessons for the "3 lessons" stat.
    #    Normally created by qa_create_course_access_types; create if absent.
    free_course = _get_or_create_course(
        site,
        title="QA Free Course (Access Types)",
        slug=FREE_ACCESS_TYPES_SLUG,
        visibility=CourseVisibility.PUBLISHED,
        toc_in_development=False,
        access_config={"access_type": "free"},
    )
    existing_lessons, _ = _count_lessons_and_forms(site, FREE_ACCESS_TYPES_SLUG)
    # Top up to 3 lessons without disturbing any existing (e.g. intro) topic.
    for i in range(existing_lessons + 1, 4):
        _ensure_topic_child(
            site,
            free_course,
            slug=f"{FREE_ACCESS_TYPES_SLUG}-lesson-{i}",
            title=f"Free Course - Lesson {i}",
            order=i,
        )

    click.secho("\n--- Course Detail Page Variants QA data ---", fg="cyan", bold=True)
    click.secho(f"Site: {site.name} (domain: {site.domain})", fg="cyan")
    for slug in (
        TOC_NO_ASSESSMENT_SLUG,
        TOC_WITH_ASSESSMENT_SLUG,
        HIDDEN_SLUG,
        FREE_ACCESS_TYPES_SLUG,
    ):
        course = Course.objects.get(slug=slug, site=site)
        lessons, forms = _count_lessons_and_forms(site, slug)
        click.secho(
            f"{slug:45} vis={course.visibility:12} "
            f"toc_dev={course.table_of_contents_in_development!s:5} "
            f"lessons={lessons} assessments={forms} "
            f"access={course.access_config}",
            fg="green",
        )
