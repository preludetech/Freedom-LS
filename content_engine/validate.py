"""
validate that a bunch of markdown files matches the given schema

from the command line run: python validate.py /path/to/content/directory_or_item

The path can either be a file or a directory. if it is a directory then recurse over all files and validate each one.
"""

import frontmatter
import logging
import yaml
from pathlib import Path
from .schema import SCHEMAS

logger = logging.getLogger(__name__)


def _get_all_files(path):
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

        # Skip files starting with _ or .
        if file_path.name.startswith("_") or file_path.name.startswith("."):
            return True

        # Skip files in directories starting with _ or . (only check parents within base_path)
        try:
            relative_path = file_path.relative_to(base_path)
            for parent in relative_path.parents:
                # Skip the root parent (which would be '.')
                if parent.name and parent.name != "." and (parent.name.startswith("_") or parent.name.startswith(".")):
                    return True
        except ValueError:
            # file_path is not relative to base_path
            pass

        return False

    if path.is_file():
        return [path]
    elif path.is_dir():
        # Recursively find all files, excluding those that match skip criteria
        return [f for f in path.rglob("*") if f.is_file() and not should_skip(f, path)]
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
    content_type = data.get('content_type')

    if content_type is None:
        raise ValueError(f"No content_type field found in {section_label}{path}")

    model = SCHEMAS.get(content_type)
    if model is None:
        raise ValueError(f"Unknown content_type '{content_type}' in {section_label}{path}")

    # Inject the file path into the data
    data['file_path'] = path

    # Use pydantic to validate the data structure and return the instance
    return model.model_validate(data)


def parse_yaml_file(path):
    """
    Parse and validate a .yaml or .yml file.
    Each file can contain multiple YAML documents separated by ---

    Returns:
        list: List of validated pydantic model instances
    """
    with open(path, 'r', encoding='utf-8') as f:
        content = f.read()

    # Split content by --- to get individual YAML documents
    sections = [s.strip() for s in content.split('---') if s.strip()]

    if not sections:
        raise ValueError(f"No YAML content found in {path}")

    results = []
    first_model = None

    # Validate each YAML document
    for idx, section in enumerate(sections, start=1):
        data = yaml.safe_load(section)
        if first_model:
            data['content_type'] = data.get('content_type', first_model.derive_content_type(data))
        current_model = validate_yaml_section(data, path, section_num=idx if len(sections) > 1 else None)
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
    post = frontmatter.load(path)
    data = post.metadata

    # Include the markdown content
    data['content'] = post.content

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
    if path.suffix in ['.yaml', '.yml']:
        return parse_yaml_file(path)
    else:
        return parse_markdown_file(path)


def validate_yaml_file(path):
    """
    Validate a .yaml or .yml file.
    Each file can contain multiple YAML documents separated by ---
    """
    results = parse_yaml_file(path)
    logger.info(f"✓ {path} validated successfully ({len(results)} section{'s' if len(results) > 1 else ''})")


def validate_markdown_file(path):
    """
    Validate a markdown file's YAML frontmatter.
    """
    parse_markdown_file(path)
    logger.info(f"✓ {path} validated successfully")


def validate_single_file(path):
    """
    Validate a single file based on its extension.
    - .yaml/.yml files: validate each YAML document (separated by ---)
    - .md files: validate the frontmatter
    """
    if path.suffix in ['.yaml', '.yml']:
        validate_yaml_file(path)
    else:
        validate_markdown_file(path)

    

def validate(path):
    path = Path(path)

    # 1. Make sure the path exists
    if not path.exists():
        raise FileNotFoundError(f"Path does not exist: {path}")

    # 2. get a list of all the file paths
    all_file_paths = _get_all_files(path)

   

    # 3. validate each file path (only .md and .yaml files)
    for file_path in all_file_paths:
        if file_path.suffix in ['.md', '.yaml', '.yml']:
            validate_single_file(file_path)
            
            

