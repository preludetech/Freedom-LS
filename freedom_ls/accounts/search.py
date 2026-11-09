from django.db.models import Q

MIN_TERM_LENGTH = 2


def term_condition(term: str, *, include_email: bool) -> Q:
    """Every word of `term` must match a first name, last name or, when
    asked, the email, so "Jane Smith" finds Jane Smith. No words means
    no narrowing."""
    condition = Q()
    for word in term.split():
        word_condition = Q(first_name__icontains=word) | Q(last_name__icontains=word)
        if include_email:
            word_condition |= Q(email__icontains=word)
        condition &= word_condition
    return condition
