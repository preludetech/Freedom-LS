from datetime import datetime
from typing import cast

from django.db.models import Model
from django.utils import timezone


def retire[RowT: Model](row: RowT, at: datetime | None = None) -> RowT:
    """Retire a row the way a content save does: one queryset update that stamps
    `retired_at` and `updated_at` together, with no save()."""
    stamp = at or timezone.now()
    type(row)._base_manager.filter(pk=row.pk).update(retired_at=stamp, updated_at=stamp)
    row.refresh_from_db()
    return row


def retired[RowT](row: RowT) -> RowT:
    """`retire` for a factory-built row, which the type checker sees as the factory
    rather than the model. Returns the same object, typed as what the caller built."""
    retire(cast(Model, row))
    return row
