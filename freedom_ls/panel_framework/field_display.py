"""Field label and value resolution, vendored from Django and adapted.

Adapted from `django/contrib/admin/utils.py`, Django 6.0.4.
Copyright (c) Django Software Foundation and individual contributors.
All rights reserved.

Redistribution and use in source and binary forms, with or without
modification, are permitted provided that the following conditions are met:

    1. Redistributions of source code must retain the above copyright
       notice, this list of conditions and the following disclaimer.

    2. Redistributions in binary form must reproduce the above copyright
       notice, this list of conditions and the following disclaimer in the
       documentation and/or other materials provided with the distribution.

    3. Neither the name of Django nor the names of its contributors may be
       used to endorse or promote products derived from this software
       without specific prior written permission.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT OWNER OR CONTRIBUTORS BE
LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
POSSIBILITY OF SUCH DAMAGE.

Adaptations from the Django original, recorded here so the parity test can
enumerate them:

- The `model_admin` and `form` parameters are dropped from `label_for_field`
  and `lookup_field`. The framework has no `ModelAdmin` or bound form to
  consult, so a property or method declared on the model itself carries the
  whole fallback path.
- `label_for_field` labels a `__` path from the leaf field's own
  `verbose_name`, not `pretty_name` of the whole joined path, so a
  multi-segment path doesn't read as one run-on label.
- `lookup_field` returns the leaf field for a `__` path (Django's own
  version discards it), so a related field's choices and booleans display
  exactly as a local field's would.
- `display_for_field` and `display_for_value` return a plain `bool` for a
  boolean value instead of admin's `<img>` icon HTML, so a template decides
  how to render it (this project uses `c-icon`).
- The `URLField`/`FileField` link branches and the `avoid_link` parameter
  are dropped; those values fall through to `display_for_value` and render
  as plain text.
- The `password` branch is dropped; nothing here treats a field named
  "password" specially.
"""

from __future__ import annotations

import datetime
import decimal
import json
from collections.abc import Callable
from typing import cast

from django.core.exceptions import FieldDoesNotExist
from django.core.validators import EMPTY_VALUES
from django.db import models
from django.db.models import Field, Model
from django.db.models.constants import LOOKUP_SEP
from django.db.models.options import Options
from django.forms.utils import pretty_name
from django.utils import formats, timezone
from django.utils.hashable import make_hashable

# django-stubs doesn't cover `template_localtime`, though it exists at runtime;
# this typed alias keeps the call sites below free of Any. getattr, not direct
# attribute access, so mypy doesn't check a name its stub doesn't declare.
_template_localtime: Callable[[datetime.datetime], datetime.datetime] = getattr(  # noqa: B009
    timezone, "template_localtime"
)


class FieldIsAForeignKeyColumnName(Exception):  # noqa: N818 - vendored name, kept verbatim
    """Raised for an `<fk>_id` attname, so it is never treated as the relation itself."""


class NotRelationField(Exception):  # noqa: N818 - vendored name, kept verbatim
    """Raised when a `__` path segment that should be a relation isn't one."""


def get_model_from_relation(field: Field) -> type[Model]:
    """Return the model a relation field points to, or raise NotRelationField."""
    if hasattr(field, "path_infos"):
        related_model: type[Model] = field.path_infos[-1].to_opts.model
        return related_model
    raise NotRelationField


def get_fields_from_path(model: type[Model], path: str) -> list[Field]:
    """Return the Field objects along a `__`-separated path from model."""
    pieces = path.split(LOOKUP_SEP)
    fields: list[Field] = []
    for piece in pieces:
        parent = get_model_from_relation(fields[-1]) if fields else model
        fields.append(cast(Field, parent._meta.get_field(piece)))
    return fields


def _get_non_gfk_field(opts: Options[Model], name: str) -> Field:
    """Return a concrete field for `name`, excluding GFKs and reverse relations.

    Those are excluded so a caller falls through to the property/method/
    `__`-path branch instead, and an `<fk>_id` attname raises
    FieldIsAForeignKeyColumnName so "user_id" is never treated the same as
    "user".
    """
    field = cast(Field, opts.get_field(name))
    if field.is_relation and (
        (field.many_to_one and not field.related_model) or field.one_to_many
    ):
        raise FieldDoesNotExist
    if (
        field.is_relation
        and not field.many_to_many
        and hasattr(field, "attname")
        and field.attname == name
    ):
        raise FieldIsAForeignKeyColumnName
    return field


def lookup_field(name: str, obj: Model) -> tuple[Field | None, object]:
    """Resolve `name` on `obj`: a field, a `__` path, a property, a method or an annotation.

    Returns `(field, value)`. `field` is `None` when `name` isn't a concrete
    field. A missing `__` segment returns `(None, None)` rather than raising.
    """
    try:
        field = _get_non_gfk_field(obj._meta, name)
    except (FieldDoesNotExist, FieldIsAForeignKeyColumnName):
        pass
    else:
        value: object = getattr(obj, name)
        return field, value

    sentinel = object()
    attr: object = getattr(obj, name, sentinel)
    if attr is not sentinel:
        resolved: object = attr() if callable(attr) else attr
        return None, resolved

    walked: object = obj
    for part in name.split(LOOKUP_SEP):
        walked = getattr(walked, part, sentinel)
        if walked is sentinel:
            return None, None

    try:
        leaf_field = get_fields_from_path(type(obj), name)[-1]
    except (FieldDoesNotExist, NotRelationField):
        return None, walked
    return leaf_field, walked


def label_for_field(name: str, model: type[Model]) -> str:
    """Return a display label for `name`: a field, a `__` path, a property or a method.

    Mirrors Django's own admin resolution order, minus the ModelAdmin/form
    fallbacks the admin offers (this framework has neither). Raises
    AttributeError naming the model when nothing resolves.
    """
    try:
        field = _get_non_gfk_field(model._meta, name)
    except FieldIsAForeignKeyColumnName:
        return pretty_name(name)
    except FieldDoesNotExist:
        field = None

    if field is not None:
        try:
            return str(field.verbose_name)
        except AttributeError:
            # A reverse relation (ForeignObjectRel) has no verbose_name of its own.
            related_model = cast("type[Model]", field.related_model)
            return str(related_model._meta.verbose_name)

    if name == "__str__":
        return str(model._meta.verbose_name)

    attr: object
    if callable(name):
        attr = name
    elif hasattr(model, name):
        attr = getattr(model, name)
    else:
        try:
            leaf_field = get_fields_from_path(model, name)[-1]
        except (FieldDoesNotExist, NotRelationField):
            raise AttributeError(
                f"Unable to lookup '{name}' on {model._meta.label}"
            ) from None
        return str(leaf_field.verbose_name)

    if hasattr(attr, "short_description"):
        return str(attr.short_description)
    if (
        isinstance(attr, property)
        and attr.fget is not None
        and hasattr(attr.fget, "short_description")
    ):
        return str(attr.fget.short_description)
    if callable(attr):
        name_attr = getattr(attr, "__name__", "")
        return "--" if name_attr == "<lambda>" else pretty_name(name_attr)
    return pretty_name(name)


def display_for_field(value: object, field: Field, empty_value_display: str) -> object:
    """Format `value` for display given the concrete model `field` it came from."""
    flatchoices = getattr(field, "flatchoices", None)
    if flatchoices:
        try:
            return dict(flatchoices).get(value, empty_value_display)
        except TypeError:
            hashable_choices = make_hashable(flatchoices)
            return dict(hashable_choices).get(make_hashable(value), empty_value_display)
    if isinstance(field, models.BooleanField):
        if value in field.empty_values:
            return empty_value_display
        return bool(value)
    if value in field.empty_values:
        return empty_value_display
    if isinstance(field, models.DateTimeField):
        return formats.localize(_template_localtime(cast(datetime.datetime, value)))
    if isinstance(field, (models.DateField, models.TimeField)):
        return formats.localize(value)
    if isinstance(field, models.DecimalField):
        return formats.number_format(cast(decimal.Decimal, value), field.decimal_places)
    if isinstance(field, (models.IntegerField, models.FloatField)):
        return formats.number_format(cast(float, value))
    if isinstance(field, models.JSONField) and value:
        try:
            return json.dumps(value, ensure_ascii=False, cls=field.encoder)
        except TypeError:
            return display_for_value(value, empty_value_display)
    return display_for_value(value, empty_value_display)


def display_for_value(value: object, empty_value_display: str) -> object:
    """Format a bare `value` for display: a property, method or annotation result."""
    if value in EMPTY_VALUES:
        return empty_value_display
    if isinstance(value, bool):
        return value
    if isinstance(value, datetime.datetime):
        return formats.localize(_template_localtime(value))
    if isinstance(value, (datetime.date, datetime.time)):
        return formats.localize(value)
    if isinstance(value, (int, decimal.Decimal, float)):
        return formats.number_format(value)
    if isinstance(value, (list, tuple)):
        return ", ".join(str(v) for v in value)
    return str(value)
