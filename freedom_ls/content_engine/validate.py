"""
validate that a bunch of markdown files matches the given schema

from the command line run: python validate.py /path/to/content/directory_or_item

The path can either be a file or a directory. if it is a directory then recurse over all files and validate each one.
"""

import functools
import logging
import os.path
import re
from collections.abc import Sequence
from pathlib import Path

import frontmatter
import yaml
from pydantic import ValidationError

from freedom_ls.content_base.schema import SCHEMAS, BaseBaseContentModel, ContentType
from freedom_ls.content_engine.schema import Child, Course, CoursePart
from freedom_ls.form_engine.schema import (
    Condition,
    Form,
    FormContent,
    FormPage,
    FormQuestion,
    FormStrategy,
    QuestionType,
)

logger = logging.getLogger(__name__)

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".svg", ".webp"}


def is_skipped_path(path: Path) -> bool:
    """Whether a file or directory is ignored when scanning for content.

    Names starting with `_` or `.` are ignored, along with everything inside such
    directories.
    """
    return path.name.startswith("_") or path.name.startswith(".")


def content_key(file_path: Path | str) -> Path:
    """The normalised key every content_by_path entry and lookup uses.

    A path written by an author and a path produced by the directory scan reach
    the same file by different routes, so both have to be resolved before either
    is used as a key.
    """
    return Path(file_path).resolve()


def resolve_author_path(declaring_file: Path | str, author_path: Path | str) -> Path:
    """An author-written path, relative to the file that declares it."""
    return content_key(Path(declaring_file).parent / author_path)


def auto_discovered_children(collection_file: Path) -> list[Path]:
    """The children a collection without a children: list gets: every content file and
    content directory beside it, in name order, skipping what the directory walk skips,
    course_categories.yaml and articles. Resolved keys, as the loader stores them."""
    found: list[Path] = []
    # Anything starting with _ or . is skipped, the same rule as get_all_files.
    for item in sorted(
        entry
        for entry in collection_file.parent.iterdir()
        if not is_skipped_path(entry)
    ):
        if item.is_file() and item.suffix in [".md", ".yaml", ".yml"]:
            if item != collection_file:
                # A loose course_categories.yaml in a course directory belongs at the
                # repo root, so it is never adopted as a child. An article is loaded in
                # its own pass and is never a collection child.
                parsed = parse_single_file(item)
                if parsed and parsed[0].content_type in (
                    ContentType.COURSE_CATEGORIES,
                    ContentType.ARTICLE,
                ):
                    continue
                found.append(content_key(item))
        elif item.is_dir():
            # A subdirectory is either a child collection/form (form.md/course.md/
            # part.yaml) or a topic directory (content.md). Collection and form roles
            # take priority because a COURSE_PART directory also contains topic files.
            collection_child: Path | None = None
            topic_file: Path | None = None
            for f in sorted(item.iterdir()):
                if is_skipped_path(f):
                    continue
                if not (f.is_file() and f.suffix in [".md", ".yaml", ".yml"]):
                    continue
                parsed = parse_single_file(f)
                if not parsed:
                    continue
                content_type = parsed[0].content_type
                if content_type in (ContentType.COURSE_CATEGORIES, ContentType.ARTICLE):
                    continue
                if content_type in (
                    ContentType.FORM,
                    ContentType.COURSE,
                    ContentType.COURSE_PART,
                ):
                    collection_child = f
                    break
                if (
                    content_type in (ContentType.TOPIC, ContentType.ACTIVITY)
                    and topic_file is None
                ):
                    topic_file = f
            main_file = collection_child or topic_file
            if main_file:
                found.append(content_key(main_file))
    return found


def get_all_files(path):
    """
    if path points to a regular file, then return it

    if path is a directory, then recursively find all the files inside it, and return a list of paths

    don't include any files that:
    - are named README.md
    - have names starting with an _ or .
    - are included in directories with names starting with an _ or . (recursive)
    """

    def should_skip(file_path, base_path):
        """Check if a file should be skipped based on filtering rules."""
        # Skip README.md
        if file_path.name == "README.md":
            return True

        if file_path.name == "CLAUDE.md":
            return True

        if file_path.name.endswith("~"):
            return True

        # Skip files starting with _ or .
        if is_skipped_path(file_path):
            return True

        # Skip files in directories starting with _ or . (only check parents within base_path)
        try:
            relative_path = file_path.relative_to(base_path)
            for parent in relative_path.parents:
                # Skip the root parent (which would be '.')
                if parent.name and parent.name != "." and is_skipped_path(parent):
                    return True
        except ValueError:
            # file_path is not relative to base_path
            pass

        return False

    if path.is_file():
        return [path]
    elif path.is_dir():
        # Recursively find all files, excluding those that match skip criteria
        return sorted(
            [f for f in path.rglob("*") if f.is_file() and not should_skip(f, path)]
        )
    else:
        return []


def split_yaml_documents(content: str) -> list[str]:
    """Split a multi-document YAML string on its `---` separator lines.

    Only a `---` on a line of its own separates documents; the same three
    characters inside a value (an em dash typed as `---` in a description)
    are prose and stay put. A bare `content.split("---")` cut those values in
    half on both read and write, which is why the reader and every uuid
    writer in content_save share this.

    Returns each document stripped, with empty documents dropped.
    """
    return [
        section.strip()
        for section in re.split(r"^---[ \t]*$", content, flags=re.MULTILINE)
        if section.strip()
    ]


def validate_yaml_section(data, path, section_num=None):
    """
    Validate a single YAML section/document.

    Args:
        data: The parsed YAML data (dict)
        path: The file path being validated
        section_num: Optional section number for error messages

    Returns:
        The validated model instance
    """
    section_label = f"section {section_num} of " if section_num else ""

    if not isinstance(data, dict):
        raise ValueError(f"YAML {section_label}{path} is not a valid object")

    # Get the content_type field, and figure out which model to use
    content_type = data.get("content_type")

    if content_type is None:
        raise ValueError(f"No content_type field found in {section_label}{path}")

    model = SCHEMAS.get(content_type)
    if model is None:
        raise ValueError(
            f"Unknown content_type '{content_type}' in {section_label}{path}"
        )

    # Inject the file path into the data
    data["file_path"] = path

    # Use pydantic to validate the data structure and return the instance
    try:
        return model.model_validate(data)
    except ValidationError as e:
        # Build a user-friendly error message
        location = f"{section_label}{path}"
        error_lines = [f"\n❌ Validation failed in {location}"]
        error_lines.append(f"Content type: {content_type}")
        error_lines.append("\nErrors found:")

        for error in e.errors():
            field_path = " -> ".join(str(loc) for loc in error["loc"])
            message = error["msg"]

            # Format the error in a user-friendly way
            error_lines.append(f"  • Field: {field_path}")
            error_lines.append(f"    Problem: {message}")

            # Show the actual value if available
            if "input" in error:
                error_lines.append(f"    Given value: {error['input']}")

            error_lines.append("")  # Blank line between errors

        raise ValueError("\n".join(error_lines)) from e


def parse_yaml_file(path):
    """
    Parse and validate a .yaml or .yml file.
    Each file can contain multiple YAML documents separated by ---

    Returns:
        list: List of validated pydantic model instances
    """
    try:
        with open(path, encoding="utf-8") as f:
            content = f.read()
    except FileNotFoundError as e:
        raise ValueError(f"\n❌ File not found: {path}") from e
    except PermissionError as e:
        raise ValueError(f"\n❌ Permission denied when reading: {path}") from e
    except UnicodeDecodeError as e:
        raise ValueError(
            f"\n❌ File encoding error in {path}\n"
            f"The file is not valid UTF-8. Please ensure it's saved with UTF-8 encoding."
        ) from e
    except Exception as e:
        raise ValueError(f"\n❌ Error reading file {path}: {e!s}") from e

    # Split content by --- to get individual YAML documents
    sections = split_yaml_documents(content)

    if not sections:
        raise ValueError(f"\n❌ No YAML content found in {path}")

    results = []
    first_model = None

    # Validate each YAML document
    for idx, section in enumerate(sections, start=1):
        try:
            data = yaml.safe_load(section)
        except yaml.YAMLError as e:
            # Build a user-friendly error message for YAML parsing errors
            section_label = f"section {idx} of " if len(sections) > 1 else ""
            error_lines = [f"\n❌ YAML parsing failed in {section_label}{path}"]
            error_lines.append(f"\nYAML Error: {e!s}")

            # Show a preview of the problematic section (first 5 lines)
            section_preview = "\n".join(section.split("\n")[:5])
            error_lines.append("\nSection preview:")
            error_lines.append(section_preview)
            if len(section.split("\n")) > 5:
                error_lines.append("...")

            raise ValueError("\n".join(error_lines)) from e

        if first_model:
            data["content_type"] = data.get(
                "content_type", first_model.derive_content_type(data)
            )

        current_model = validate_yaml_section(
            data, path, section_num=idx if len(sections) > 1 else None
        )
        results.append(current_model)
        first_model = first_model or current_model

    return results


def parse_markdown_file(path):
    """
    Parse and validate a markdown file's YAML frontmatter.

    Returns:
        list: List containing a single validated pydantic model instance
    """
    # Load the yaml frontmatter
    try:
        post = frontmatter.load(path)
    except FileNotFoundError as e:
        raise ValueError(f"\n❌ File not found: {path}") from e
    except PermissionError as e:
        raise ValueError(f"\n❌ Permission denied when reading: {path}") from e
    except yaml.YAMLError as e:
        raise ValueError(
            f"\n❌ YAML frontmatter parsing failed in {path}\n"
            f"\nYAML Error: {e!s}\n"
            f"\nPlease check the frontmatter section at the top of your markdown file."
        ) from e
    except UnicodeDecodeError as e:
        raise ValueError(
            f"\n❌ File encoding error in {path}\n"
            f"The file is not valid UTF-8. Please ensure it's saved with UTF-8 encoding."
        ) from e
    except Exception as e:
        raise ValueError(
            f"\n❌ Error reading markdown file {path}\nError: {e!s}"
        ) from e

    data = post.metadata

    # Include the markdown content
    data["content"] = post.content

    # Validate the frontmatter
    model = validate_yaml_section(data, path)
    return [model]


def parse_single_file(path):
    """
    Parse and validate a single file based on its extension.
    - .yaml/.yml files: parse each YAML document (separated by ---)
    - .md files: parse the frontmatter

    Returns:
        list: List of validated pydantic model instances
    """
    if path.suffix in [".yaml", ".yml"]:
        return parse_yaml_file(path)
    else:
        return parse_markdown_file(path)


def validate_yaml_file(path):
    """
    Validate a .yaml or .yml file.
    Each file can contain multiple YAML documents separated by ---
    """
    try:
        results = parse_yaml_file(path)
        logger.info(
            f"✓ {path} validated successfully ({len(results)} section{'s' if len(results) > 1 else ''})"
        )
    except ValueError:
        # Re-raise ValueError as-is (already has user-friendly message)
        raise
    except Exception as e:
        logger.error(f"Unexpected error while validating {path}: {e!s}")
        raise


def validate_markdown_file(path):
    """
    Validate a markdown file's YAML frontmatter.
    """
    try:
        parse_markdown_file(path)
        logger.info(f"✓ {path} validated successfully")
    except ValueError:
        # Re-raise ValueError as-is (already has user-friendly message)
        raise
    except Exception as e:
        logger.error(f"Unexpected error while validating {path}: {e!s}")
        raise


def validate_single_file(path):
    """
    Validate a single file based on its extension.
    - .yaml/.yml files: validate each YAML document (separated by ---)
    - .md files: validate the frontmatter
    """
    if path.suffix in [".yaml", ".yml"]:
        validate_yaml_file(path)
    else:
        validate_markdown_file(path)


def _category_reference_error(
    file_path: Path,
    header: str,
    field: str,
    problem: str,
    given_value: str,
    declared: dict[str, Path],
    fix: str,
    list_label: str = "Categories declared in this repo",
) -> str:
    """Build the course-side category error block.

    Shared by the four checks in `validate_category_references` that report a
    course's `categories`/`dashboard_category` against the declared set:
    unknown slug in `categories`, unknown `dashboard_category`,
    `dashboard_category` outside the course's own `categories`, and a missing
    `dashboard_category` with two or more `categories`.
    """
    lines = [f"\n❌ {header} in {file_path}", "Content type: COURSE", ""]
    lines.append(f"  • Field: {field}")
    lines.append(f"    Problem: {problem}")
    lines.append(f"    Given value: {given_value!r}")
    lines.append("")

    if declared:
        declaring_files = sorted(
            {str(declaring_path) for declaring_path in declared.values()}
        )
        lines.append(f"    {list_label} ({', '.join(declaring_files)}):")
        for slug in sorted(declared):
            lines.append(f"      {slug}")
    else:
        lines.append(f"    {list_label}: none")

    lines.append("")
    lines.append(f"    {fix}")
    return "\n".join(lines)


def validate_category_references(all_parsed: list) -> list[str]:
    """Resolve every course's category references against the declared set.

    `validate()`'s per-file pass validates each file in isolation and can't
    see whether a slug a course names is actually declared anywhere -- a
    `course_categories.yaml` appearing later in the sorted file walk than the
    courses that reference it still has to satisfy them. This pass runs once
    every file's parsed items are available, so file order doesn't matter.

    Returns every error found, never just the first, so an author with five
    typos gets five lines rather than five runs.
    """
    errors: list[str] = []

    declarations = [
        item
        for item in all_parsed
        if item.content_type == ContentType.COURSE_CATEGORIES
    ]

    if len(declarations) > 1:
        declaring_files = ", ".join(str(d.file_path) for d in declarations)
        errors.append(
            f"\n❌ Multiple COURSE_CATEGORIES declarations found: {declaring_files}. "
            "A content repo may declare its categories only once."
        )

    declared: dict[str, Path] = {}
    for declaration in declarations:
        for entry in declaration.categories:
            declared.setdefault(entry.slug, declaration.file_path)

    collection_dirs = {
        item.file_path.parent
        for item in all_parsed
        if item.content_type in (ContentType.COURSE, ContentType.COURSE_PART)
    }
    for declaration in declarations:
        if set(declaration.file_path.parents) & collection_dirs:
            errors.append(
                f"\n❌ COURSE_CATEGORIES declaration inside a course directory: "
                f"{declaration.file_path}. Move it to the repo root."
            )

    unknown_fix = (
        "Fix the slug, or add an entry declaring it in course_categories.yaml."
    )

    for item in all_parsed:
        if item.content_type != ContentType.COURSE:
            continue

        for index, slug in enumerate(item.categories):
            if slug not in declared:
                errors.append(
                    _category_reference_error(
                        item.file_path,
                        header="Unknown category",
                        field=f"categories[{index}]",
                        problem="no category is declared with this slug in this content repo",
                        given_value=slug,
                        declared=declared,
                        fix=unknown_fix,
                    )
                )

        dashboard_category = item.dashboard_category
        if dashboard_category:
            if dashboard_category not in declared:
                errors.append(
                    _category_reference_error(
                        item.file_path,
                        header="Unknown category",
                        field="dashboard_category",
                        problem="no category is declared with this slug in this content repo",
                        given_value=dashboard_category,
                        declared=declared,
                        fix=unknown_fix,
                    )
                )
            elif dashboard_category not in item.categories:
                errors.append(
                    _category_reference_error(
                        item.file_path,
                        header="dashboard_category not in categories",
                        field="dashboard_category",
                        problem=(
                            f"'{dashboard_category}' is not one of this course's "
                            f"categories {sorted(item.categories)}: the dashboard "
                            "category has to be one the course belongs to"
                        ),
                        given_value=dashboard_category,
                        declared=declared,
                        fix="Add it to categories, or change dashboard_category to one already listed there.",
                    )
                )
        elif len(item.categories) >= 2:
            candidates = {
                slug: declared.get(slug, item.file_path) for slug in item.categories
            }
            errors.append(
                _category_reference_error(
                    item.file_path,
                    header="dashboard_category is required",
                    field="dashboard_category",
                    problem=(
                        "this course belongs to two or more categories, so "
                        "dashboard_category must name which one the dashboard uses"
                    ),
                    given_value="(not set)",
                    declared=candidates,
                    fix="Set dashboard_category to one of the candidates listed above.",
                    list_label="Candidates",
                )
            )

    return errors


_WIDGET_TAG_PATTERN = re.compile(
    r'<c-(article-link|article-card|course-card)\b[^>]*?\bpath="([^"]*)"'
)

_ARTICLE_WIDGETS = {"article-link", "article-card"}


def _reference_error(
    file_path: Path,
    content_type: ContentType,
    field: str,
    path: str,
    problem: str,
    fix: str,
    header: str = "Broken widget reference",
) -> str:
    """Build the error block for a path that does not resolve.

    Same header/field/problem/given-value/fix layout as
    `_category_reference_error`, without its declared-list section.
    """
    lines = [
        f"\n❌ {header} in {file_path}",
        f"Content type: {content_type}",
        "",
        f"  • Field: {field}",
        f"    Problem: {problem}",
        f"    Given value: {path!r}",
        "",
        f"    {fix}",
    ]
    return "\n".join(lines)


def validate_widget_references(all_parsed: list) -> list[str]:
    """Check every widget `path` in a body against the parsed content files.

    Paths resolve relative to the file holding the widget. Also reports two
    article files that resolve to the same slug, since both would claim one URL.
    """
    errors: list[str] = []
    by_path = {os.path.normpath(item.file_path): item for item in all_parsed}

    for item in all_parsed:
        body = getattr(item, "content", None)
        if not body:
            continue
        for widget, path in _WIDGET_TAG_PATTERN.findall(body):
            field = f"c-{widget} path"
            target = by_path.get(os.path.normpath(item.file_path.parent / path))
            if target is None:
                errors.append(
                    _reference_error(
                        item.file_path,
                        item.content_type,
                        field,
                        path,
                        problem="no content file at this path",
                        fix="Fix the path. It is relative to this file and must end in the target's file name.",
                    )
                )
            elif (
                widget in _ARTICLE_WIDGETS
                and target.content_type != ContentType.ARTICLE
            ):
                errors.append(
                    _reference_error(
                        item.file_path,
                        item.content_type,
                        field,
                        path,
                        problem=f"this file is a {target.content_type}, not an ARTICLE",
                        fix="Point the widget at an ARTICLE file.",
                    )
                )
            elif widget == "course-card" and target.content_type != ContentType.COURSE:
                errors.append(
                    _reference_error(
                        item.file_path,
                        item.content_type,
                        field,
                        path,
                        problem=f"this file is a {target.content_type}, not a COURSE",
                        fix="Point the widget at a COURSE file.",
                    )
                )

    files_by_slug: dict[str, list[Path]] = {}
    for item in all_parsed:
        if item.content_type == ContentType.ARTICLE:
            files_by_slug.setdefault(item.slug, []).append(item.file_path)
    for slug, files in sorted(files_by_slug.items()):
        if len(files) > 1:
            errors.append(
                f"\n❌ Duplicate article slug '{slug}': "
                f"{', '.join(str(f) for f in files)}. "
                "Give one of them a different slug."
            )

    return errors


_DUE_DATE_CHILD_TYPES = frozenset({ContentType.TOPIC, ContentType.FORM})
_placement_error = functools.partial(
    _reference_error, header="Invalid due date placement"
)


def _direct_entry_errors(
    item: Course | CoursePart, index: int, entry: Child, target: BaseBaseContentModel
) -> list[str]:
    """A due date belongs to a topic or form placement."""
    if entry.holds_due_value() and target.content_type not in _DUE_DATE_CHILD_TYPES:
        return [
            _placement_error(
                item.file_path,
                item.content_type,
                f"children[{index}]",
                str(entry.path),
                problem=f"a due date on a {target.content_type} placement",
                fix="Only a TOPIC or FORM placement takes due keys or no_due_date.",
            )
        ]
    return []


def collection_children(
    collection: Course | CoursePart,
) -> list[tuple[Path, Child | None]]:
    """The collection's children as (resolved key, entry) pairs: the listed entries, else
    the auto-discovered files, which have no entry. The one rule for what a collection
    holds, shared by the validator and the loader so the two never disagree."""
    if collection.children:
        return [
            (resolve_author_path(collection.file_path, child.path), child)
            for child in collection.children
        ]
    return [(path, None) for path in auto_discovered_children(collection.file_path)]


def _shown_relative_to(path: Path, directory: Path) -> str:
    """A resolved key as an author would write it under the part's directory."""
    base = content_key(directory)
    return str(path.relative_to(base)) if path.is_relative_to(base) else str(path)


class _ParsedByPath:
    """The parsed items by resolved key, reaching outside the validated path when an entry
    does. A course may place a part from a sibling directory; validating the course's
    directory alone must still check the part's nested list, so a key not parsed in this
    run is parsed from disk on first use. A file that does not exist, or does not parse,
    gives None: the unknown-child check and the file's own validation own those."""

    def __init__(self, all_parsed: Sequence[BaseBaseContentModel]) -> None:
        self._items = {content_key(item.file_path): item for item in all_parsed}
        self._read: set[Path] = set()
        self._children: dict[Path, list[Path]] = {}

    def get(self, key: Path) -> BaseBaseContentModel | None:
        if key not in self._items and key not in self._read:
            self._read.add(key)
            if key.is_file():
                try:
                    parsed = parse_single_file(key)
                except ValueError:
                    parsed = []
                # The last document wins, as it does in __init__ and in the loader.
                for item in parsed:
                    self._items[content_key(item.file_path)] = item
        return self._items.get(key)

    def children_of(self, part: CoursePart) -> list[Path]:
        """The part's children as resolved keys, listed or auto-discovered. Auto-discovery
        parses every file beside the part, so the walk happens once per part however many
        courses place it. Raises ValueError when a file beside the part does not parse."""
        key = content_key(part.file_path)
        if key not in self._children:
            self._children[key] = [path for path, _ in collection_children(part)]
        return self._children[key]


def _nested_list_errors(
    item: Course | CoursePart,
    index: int,
    entry: Child,
    target: BaseBaseContentModel,
    by_path: _ParsedByPath,
) -> list[str]:
    """A nested children: list belongs on a course's placement of a part and names the
    part's topics and forms, each once."""
    field = f"children[{index}].children"
    error = functools.partial(_placement_error, item.file_path, item.content_type)
    if isinstance(item, CoursePart):
        return [
            error(
                field,
                str(entry.path),
                problem="a nested children: list in a part.yaml entry",
                fix="Set the part's child dates in part.yaml's own children: list.",
            )
        ]
    if not isinstance(target, CoursePart):
        return [
            error(
                field,
                str(entry.path),
                problem=f"a nested children: list on a {target.content_type} placement",
                fix="Only a placed part takes a nested children: list.",
            )
        ]
    # The part may sit outside the validated path, where the per-file pass never saw its
    # siblings, so a file that does not parse is reported here rather than lost.
    try:
        part_children = by_path.children_of(target)
    except ValueError as e:
        return [
            error(
                field,
                str(entry.path),
                problem=f"a file beside the part does not parse: {e}",
                fix="Fix that file first.",
            )
        ]
    known = set(part_children)
    listed = ", ".join(
        _shown_relative_to(p, target.file_path.parent) for p in part_children
    )
    errors: list[str] = []
    seen: set[Path] = set()
    for nested_index, nested in enumerate(entry.children or []):
        nested_field = f"{field}[{nested_index}]"
        resolved = resolve_author_path(target.file_path, nested.path)
        child = by_path.get(resolved)
        if resolved not in known:
            errors.append(
                error(
                    nested_field,
                    str(nested.path),
                    problem="the part has no child at this path",
                    fix=(
                        f"The part's children are: {listed}. "
                        "Paths are relative to the part's directory."
                    ),
                )
            )
        elif child is not None and child.content_type not in _DUE_DATE_CHILD_TYPES:
            errors.append(
                error(
                    nested_field,
                    str(nested.path),
                    problem=f"this child is a {child.content_type}",
                    fix="Name the part's topics and forms.",
                )
            )
        elif resolved in seen:
            errors.append(
                error(
                    nested_field,
                    str(nested.path),
                    problem="this child is named twice",
                    fix="Name each child once.",
                )
            )
        seen.add(resolved)
    return errors


def validate_children_lists(all_parsed: Sequence[BaseBaseContentModel]) -> list[str]:
    """Check that no course or part names the same child twice in its children: list.

    The loader keeps one row per child of a collection, so a second entry would silently
    replace the first's order and dates. Paths are resolved the way the loader resolves
    them, so two spellings of one file count as one child.
    """
    errors: list[str] = []
    for item in all_parsed:
        if not isinstance(item, (Course, CoursePart)):
            continue
        seen: set[Path] = set()
        for index, entry in enumerate(item.children or []):
            resolved = resolve_author_path(item.file_path, entry.path)
            if resolved in seen:
                errors.append(
                    _reference_error(
                        item.file_path,
                        item.content_type,
                        f"children[{index}]",
                        str(entry.path),
                        problem="this child is named twice",
                        fix="Name each child once.",
                        header="Invalid children list",
                    )
                )
            seen.add(resolved)
    return errors


def validate_due_date_placements(
    all_parsed: Sequence[BaseBaseContentModel],
) -> list[str]:
    """Check every children: entry that sets a due date against the file it names.

    An entry whose path names nothing is left to the unknown-child check.
    """
    errors: list[str] = []
    # Keyed by content_key, not normpath: an entry's path is resolved the way the loader
    # resolves it, so the two agree on every file.
    by_path = _ParsedByPath(all_parsed)
    for item in all_parsed:
        if not isinstance(item, (Course, CoursePart)):
            continue
        for index, entry in enumerate(item.children or []):
            target = by_path.get(resolve_author_path(item.file_path, entry.path))
            if target is None:
                continue
            errors.extend(_direct_entry_errors(item, index, entry, target))
            if entry.children is not None:
                errors.extend(_nested_list_errors(item, index, entry, target, by_path))
    return errors


_CONDITION_SOURCE_TYPES = {
    QuestionType.MULTIPLE_CHOICE,
    QuestionType.DROPDOWN,
    QuestionType.CHECKBOXES,
}

_FormSection = FormPage | FormContent | FormQuestion


def _condition_error(
    file_path: Path, target: str, problem: str, fix: str, field: str = "when"
) -> str:
    """Build the error block for an invalid `when` or a duplicated `slug`.

    Same header/field/problem/fix layout as `_reference_error`.
    """
    return "\n".join(
        [
            f"\n❌ Invalid condition in {file_path}",
            "",
            f"  • Field: {target} → {field}",
            f"    Problem: {problem}",
            "",
            f"    {fix}",
        ]
    )


def _target_label(item: _FormSection, block_number: int) -> str:
    if isinstance(item, FormPage):
        return f'page "{item.title}"'
    if isinstance(item, FormQuestion):
        return f'question "{item.question}"'
    return f"content block {block_number}"


def _slug_owners(
    page_files: list[Path], sections_by_file: dict[Path, list[_FormSection]]
) -> tuple[dict[str, tuple[int, FormQuestion]], list[str]]:
    """Map each declared slug to its first question and page index, plus an
    error for every later question that reuses a slug."""
    owners: dict[str, tuple[int, FormQuestion]] = {}
    errors: list[str] = []
    for page_index, page_file in enumerate(page_files):
        for item in sections_by_file[page_file]:
            if not isinstance(item, FormQuestion) or item.slug is None:
                continue
            if item.slug in owners:
                first_file = owners[item.slug][1].file_path
                errors.append(
                    _condition_error(
                        item.file_path,
                        _target_label(item, 0),
                        f'slug "{item.slug}" is declared twice: in {first_file} '
                        f"and {item.file_path}.",
                        "Give each question its own slug.",
                        field="slug",
                    )
                )
            else:
                owners[item.slug] = (page_index, item)
    return owners, errors


def _condition_problem(
    condition: Condition,
    page_index: int,
    slug_owner: dict[str, tuple[int, FormQuestion]],
) -> tuple[str, str] | None:
    """The problem and fix for the first rule the condition breaks, or None."""
    source_slug = condition.question
    if source_slug not in slug_owner:
        declared = ", ".join(sorted(slug_owner)) or "none"
        return (
            f'when.question names "{source_slug}", which no question in this '
            "form has as its slug.",
            f"Declared slugs: {declared}.",
        )
    source_index, source = slug_owner[source_slug]
    if source_index >= page_index:
        return (
            f'when.question names "{source_slug}", which is on this page or a '
            "later one.",
            "A condition's source has to be on an earlier page.",
        )
    if source.type not in _CONDITION_SOURCE_TYPES:
        return (
            f'when.question names "{source_slug}", a {source.type} question.',
            "A source has to be a multiple_choice, dropdown or checkboxes question.",
        )
    is_checkboxes = source.type == QuestionType.CHECKBOXES
    if condition.equals is not None and is_checkboxes:
        return (
            f'when.equals cannot test "{source_slug}", a checkboxes question.',
            "Use includes.",
        )
    if condition.includes is not None and not is_checkboxes:
        return (
            f'when.includes cannot test "{source_slug}", a {source.type} question.',
            "Use equals.",
        )
    values = [str(option.value) for option in source.options or []]
    if condition.literal not in values:
        key = "equals" if condition.equals is not None else "includes"
        return (
            f'when.{key} names "{condition.literal}", which is not a value of '
            f'"{source_slug}".',
            f"Its values: {', '.join(values)}.",
        )
    return None


def validate_form_conditions(all_parsed: Sequence[BaseBaseContentModel]) -> list[str]:
    """Check every `when` against the questions the same form declares earlier.

    Page order is the one content_save assigns: the page files sorted as
    paths, so `10. x.yaml` comes before `2. y.yaml`. Every error is reported,
    never just the first.
    """
    errors: list[str] = []
    forms = {
        item.file_path.parent: item for item in all_parsed if isinstance(item, Form)
    }
    sections_by_file: dict[Path, list[_FormSection]] = {}
    for item in all_parsed:
        if isinstance(item, (FormPage, FormContent, FormQuestion)):
            sections_by_file.setdefault(item.file_path, []).append(item)

    for form_dir, form in forms.items():
        page_files = sorted(f for f in sections_by_file if f.parent == form_dir)
        gated: list[tuple[int, _FormSection, Condition, str]] = []
        for page_index, page_file in enumerate(page_files):
            block_number = 0
            for item in sections_by_file[page_file]:
                if isinstance(item, FormContent):
                    block_number += 1
                if item.when is not None:
                    label = _target_label(item, block_number)
                    gated.append((page_index, item, item.when, label))
        if form.strategy == FormStrategy.QUIZ:
            if gated:
                _, first, _, target = gated[0]
                errors.append(
                    _condition_error(
                        first.file_path,
                        target,
                        "when is not allowed in a QUIZ form.",
                        "Remove it, or change the form's strategy.",
                    )
                )
            continue
        slug_owner, duplicate_errors = _slug_owners(page_files, sections_by_file)
        errors.extend(duplicate_errors)
        for page_index, item, condition, target in gated:
            problem = _condition_problem(condition, page_index, slug_owner)
            if problem is not None:
                errors.append(_condition_error(item.file_path, target, *problem))
    return errors


def validate_article_images(all_parsed: list, all_file_paths: list[Path]) -> list[str]:
    """Check every article's `image` against the files the loader would save.

    The path is relative to the article file. Files under `_` and `.` directories
    are never loaded, so an image there is reported rather than found on disk.
    A path without an image extension is reported too: the loader would not save
    it as an image, so the article would show none.
    """
    errors: list[str] = []
    saved = {os.path.normpath(path) for path in all_file_paths}
    for item in all_parsed:
        if item.content_type != ContentType.ARTICLE or not item.image:
            continue
        if Path(item.image).suffix.lower() not in IMAGE_EXTENSIONS:
            problem = "this file is not an image"
            fix = "Point it at an image file (.jpg, .png, .webp, ...)."
        elif os.path.normpath(item.file_path.parent / item.image) not in saved:
            problem = "no file at this path"
            fix = "Fix the path. It is relative to this article's file."
        else:
            continue
        errors.append(
            _reference_error(
                item.file_path,
                item.content_type,
                field="image",
                path=item.image,
                problem=problem,
                fix=fix,
                header="Broken image reference",
            )
        )
    return errors


def validate(path):
    """
    Validate all content files in a directory or a single file.

    Args:
        path: Path to a file or directory to validate

    Raises:
        ValueError: If validation fails with detailed error messages
    """
    path = Path(path)

    # 1. Make sure the path exists
    if not path.exists():
        raise ValueError(f"\n❌ Path does not exist: {path}")

    # 2. get a list of all the file paths
    try:
        all_file_paths = get_all_files(path)
    except Exception as e:
        raise ValueError(f"\n❌ Error scanning directory {path}\nError: {e!s}") from e

    # Check if we found any content files
    content_files = [f for f in all_file_paths if f.suffix in [".md", ".yaml", ".yml"]]
    if not content_files:
        logger.warning(f"No content files (.md, .yaml, .yml) found in {path}")
        return

    # 3. validate each file path (only .md and .yaml files), keeping every
    # parsed item so validate_category_references can resolve references
    # across files regardless of the order the walk visited them in.
    failed_files = []
    all_parsed = []
    for file_path in all_file_paths:
        if file_path.suffix in [".md", ".yaml", ".yml"]:
            try:
                items = parse_single_file(file_path)
            except ValueError as e:
                # Collect errors but continue validating other files
                failed_files.append((file_path, str(e)))
                continue

            all_parsed.extend(items)
            if file_path.suffix in [".yaml", ".yml"]:
                logger.info(
                    f"✓ {file_path} validated successfully "
                    f"({len(items)} section{'s' if len(items) > 1 else ''})"
                )
            else:
                logger.info(f"✓ {file_path} validated successfully")

    # 4. cross-file pass: resolve every course's category references now
    # that every file's parsed items are available
    for message in validate_category_references(all_parsed):
        failed_files.append((path, message))
    for message in validate_widget_references(all_parsed):
        failed_files.append((path, message))
    for message in validate_children_lists(all_parsed):
        failed_files.append((path, message))
    for message in validate_due_date_placements(all_parsed):
        failed_files.append((path, message))
    for message in validate_form_conditions(all_parsed):
        failed_files.append((path, message))
    # A single-file run has no sibling files to resolve an image against.
    if path.is_dir():
        for message in validate_article_images(all_parsed, all_file_paths):
            failed_files.append((path, message))

    # Report all failures at the end
    if failed_files:
        error_report = ["\n" + "=" * 80]
        error_report.append(f"❌ Validation failed for {len(failed_files)} file(s):")
        error_report.append("=" * 80)

        for _file_path, error_msg in failed_files:
            error_report.append(error_msg)
            error_report.append("-" * 80)

        raise ValueError("\n".join(error_report))
