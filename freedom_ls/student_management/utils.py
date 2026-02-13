from uuid import UUID


def calculate_course_progress_percentage(
    course,
    completed_topic_ids: set[UUID],
    completed_form_ids: set[UUID],
) -> int:
    """
    Calculate the percentage of completion for a course.

    This function counts all completable items in a course, including:
    - Direct child items (Topics and Forms)
    - Items nested inside CourseParts

    Args:
        course: The Course object
        completed_topic_ids: Set of UUIDs for completed topics
        completed_form_ids: Set of UUIDs for completed forms

    Returns:
        Integer percentage (0-100) of course completion, rounded
    """
    # Get all completable items (recursively for CourseParts)
    total_items = 0
    completed_items = 0

    def count_items(children):
        """Recursively count items, expanding CourseParts."""
        nonlocal total_items, completed_items

        for child in children:
            if child.content_type == "COURSE_PART":
                # Recurse into CoursePart children
                count_items(child.children())
            elif child.content_type == "TOPIC":
                total_items += 1
                if child.id in completed_topic_ids:
                    completed_items += 1
            elif child.content_type == "FORM":
                total_items += 1
                if child.id in completed_form_ids:
                    completed_items += 1

    # Start counting from course children
    children = course.children()
    count_items(children)

    # Calculate percentage
    if total_items > 0:
        return round((completed_items / total_items) * 100)
    else:
        return 0
