"""Test-only models standing in for a consumer app's tables.

They are not real FLS models and so get no factory_boy factories; the
constructors in ``helpers.py`` play that role. The ``_panel_test_tables``
fixture in ``conftest.py`` creates their tables for the test session.

Import them relatively (``from .stub_models import StubModel``) so Django
registers each model once.
"""

from __future__ import annotations

from django.db import models


class StubModel(models.Model):
    name = models.CharField(max_length=120, unique=True)
    kind = models.CharField(
        max_length=8,
        choices=[("a", "Alpha"), ("b", "Beta")],
        default="a",
    )
    is_active = models.BooleanField(default=True)
    sat_score = models.IntegerField(null=True, blank=True, verbose_name="SAT score")

    class Meta:
        app_label = "freedom_ls_panel_framework"

    def __str__(self) -> str:
        return self.name

    @property
    def display_name(self) -> str:
        return self.name.upper()

    def describe(self) -> str:
        return f"{self.name} ({self.kind})"


class StubChild(models.Model):
    parent = models.ForeignKey(StubModel, on_delete=models.CASCADE)

    class Meta:
        app_label = "freedom_ls_panel_framework"

    def __str__(self) -> str:
        return f"StubChild({self.pk})"


class StubGrandchild(models.Model):
    """Exists so Django's Collector puts StubChild in data (not fast_deletes)."""

    parent = models.ForeignKey(StubChild, on_delete=models.CASCADE)

    class Meta:
        app_label = "freedom_ls_panel_framework"

    def __str__(self) -> str:
        return f"StubGrandchild({self.pk})"


class StubProtectedChild(models.Model):
    """A child that refuses to let its parent go, so PROTECT can be exercised."""

    parent = models.ForeignKey(StubModel, on_delete=models.PROTECT)

    class Meta:
        app_label = "freedom_ls_panel_framework"
        verbose_name = "stub protected child"
        verbose_name_plural = "stub protected children"

    def __str__(self) -> str:
        return f"StubProtectedChild({self.pk})"
