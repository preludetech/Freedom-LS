"""
validate that a bunch of markdown files matches the given schema

from the command line run: python validate.py /path/to/content/directory_or_item

The path can either be a file or a directory. if it is a directory then recurse over all files and validate each one.
"""

import logging
from pathlib import Path

import frontmatter
import yaml
from pydantic import ValidationError

from freedom_ls.content_base.schema import SCHEMAS, ContentType

logger = logging.getLogger(__name__)


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
        if file_path.name.startswith("_") or file_path.name.startswith("."):
            return True

        # Skip files in directories starting with _ or . (only check parents within base_path)
        try:
            relative_path = file_path.relative_to(base_path)
            for parent in relative_path.parents:
                # Skip the root parent (which would be '.')
                if (
                    parent.name
                    and parent.name != "."
                    and (parent.name.startswith("_") or parent.name.startswith("."))
                ):
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
    sections = [s.strip() for s in content.split("---") if s.strip()]

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
    """Build the course-side category error block shown in the spec.

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

    # Report all failures at the end
    if failed_files:
        error_report = ["\n" + "=" * 80]
        error_report.append(f"❌ Validation failed for {len(failed_files)} file(s):")
        error_report.append("=" * 80)

        for _file_path, error_msg in failed_files:
            error_report.append(error_msg)
            error_report.append("-" * 80)

        raise ValueError("\n".join(error_report))
