# Bundled from freedom_ls/content_engine/validate.py — re-sync via /update_claude_plugin_fls_content
# Patches applied:
#   1. Import: `from .schema import SCHEMAS` → `from schema import SCHEMAS`
#      (same-directory import; Python puts the script's own dir on sys.path when run as a script
#      via `uv run python .../validate.py`).
#   2. Added `if __name__ == "__main__":` entry point: reads a path from sys.argv, calls
#      validate(path), prints human-readable failures on ValueError, exits non-zero on error.
#   3. Fixed stale docstring usage line to the real uv invocation (never bare python/python3).
#   4. _load_allowed_access_types(): resolve the valid Course access types from the repo's
#      .fls-content.yaml, which always lives at the repo root (the current working directory).
#      The file is required: a missing or malformed .fls-content.yaml is a hard error (run
#      /fls-content:init to create it). When the file is present and parses but declares no
#      `access_types` key, a documented shipped base set is used. The vocabulary is injected
#      into schema.ALLOWED_ACCESS_TYPES before validating; the schema module owns no vocabulary
#      of its own. This is the only code path that reads .fls-content.yaml.
#      Re-apply all patches on every D4 re-sync.
"""
validate that a bunch of markdown files matches the given schema

from the command line run:
    uv run --no-project --with pydantic --with pyyaml --with python-frontmatter python validate.py /path/to/content/directory_or_item

The path can either be a file or a directory. if it is a directory then recurse over all files and validate each one.
"""

import logging
import sys
from pathlib import Path

import frontmatter
import schema  # Patch 4: module imported so access_types override can rebind ALLOWED_ACCESS_TYPES
import yaml
from pydantic import ValidationError
from schema import (
    SCHEMAS,  # Patch 1: same-directory import (was `from .schema import SCHEMAS`)
)

logger = logging.getLogger(__name__)

# Patch 4: the repo config file declaring deployment-specific authoring vocabulary.
_CONFIG_FILENAME = ".fls-content.yaml"

# Patch 4: documented base access-type vocabulary, used ONLY when the repo's .fls-content.yaml
# is present and parses but declares no `access_types` key (a legacy config predating that
# block). This base set mirrors the FLS shipped COURSE_ACCESS_BACKEND (free + application_gated).
# It is a default for the missing-key case, not the universal allowed set — a deployment on a
# different backend declares its own access_types.
_SHIPPED_ACCESS_TYPES: frozenset[str] = frozenset({"free", "application_gated"})


def _load_allowed_access_types() -> None:
    """Inject the valid Course access_config access types into schema.ALLOWED_ACCESS_TYPES.

    The repo's `.fls-content.yaml` always lives at the repo root (the current working
    directory), so it is read directly — never searched for. The file is required: a missing
    or unreadable/malformed config is a hard error (the author must run /fls-content:init).
    When the file is present and parses, its `access_types` list is authoritative; when it
    declares no `access_types` key, the documented shipped base set is used.
    """
    config_path = Path.cwd() / _CONFIG_FILENAME
    if not config_path.is_file():
        raise ValueError(
            f"\n❌ No {_CONFIG_FILENAME} found at the repo root ({Path.cwd()}).\n"
            f"   Run /fls-content:init to create it."
        )
    try:
        with open(config_path, encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
    except (OSError, yaml.YAMLError) as e:
        raise ValueError(
            f"\n❌ Could not read {_CONFIG_FILENAME} at the repo root ({config_path}).\n"
            f"   Fix the file or re-run /fls-content:init.\nError: {e!s}"
        ) from e
    access_types = data.get("access_types") if isinstance(data, dict) else None
    if isinstance(access_types, list) and access_types:
        schema.ALLOWED_ACCESS_TYPES = frozenset(str(t) for t in access_types)
    else:
        schema.ALLOWED_ACCESS_TYPES = _SHIPPED_ACCESS_TYPES


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

    # Patch 4: pick up the repo's deployment-specific access-type vocabulary from the
    # repo-root .fls-content.yaml (required; hard-errors if missing or malformed).
    _load_allowed_access_types()

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

    # 3. validate each file path (only .md and .yaml files)
    failed_files = []
    for file_path in all_file_paths:
        if file_path.suffix in [".md", ".yaml", ".yml"]:
            try:
                validate_single_file(file_path)
            except ValueError as e:
                # Collect errors but continue validating other files
                failed_files.append((file_path, str(e)))
            # except Exception as e:
            # Catch any unexpected errors
            # failed_files.append((file_path, f"\n❌ Unexpected error: {str(e)}"))

    # Report all failures at the end
    if failed_files:
        error_report = ["\n" + "=" * 80]
        error_report.append(f"❌ Validation failed for {len(failed_files)} file(s):")
        error_report.append("=" * 80)

        for _file_path, error_msg in failed_files:
            error_report.append(error_msg)
            error_report.append("-" * 80)

        raise ValueError("\n".join(error_report))


# Patch 2: standalone CLI entry point.
# The original validate.py has no __main__ block (FLS invokes it via the
# content_validate management command). This shim lets the bundled copy run
# directly via uv: `uv run --no-project --with pydantic --with pyyaml --with python-frontmatter
# python validate.py <path>`. --no-project is required to run in a truly isolated
# env without the FLS project's Django dependency tree.
if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(
            "Usage: uv run --no-project --with pydantic --with pyyaml --with python-frontmatter "
            "python validate.py <path>",
            file=sys.stderr,
        )
        sys.exit(1)

    target = Path(sys.argv[1])
    try:
        validate(target)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        sys.exit(1)
    except Exception as exc:
        print(f"\n❌ Unexpected error: {exc!s}", file=sys.stderr)
        sys.exit(2)

    # validate() returns without raising when no content files match — otherwise
    # indistinguishable from a real pass. Surface it so a wrong/typo'd path can't
    # read as "validated".
    content_files = (
        [f for f in get_all_files(target) if f.suffix in [".md", ".yaml", ".yml"]]
        if target.exists()
        else []
    )
    if not content_files:
        print(
            f"\n⚠ No content files (.md, .yaml, .yml) found under {target}. "
            "Nothing was validated — check the path.",
            file=sys.stderr,
        )
        sys.exit(3)

    print(f"✓ Validation passed for {target}")
    sys.exit(0)
