"""Thin task wrappers. Only primitives cross the queue; ids are strings."""

from __future__ import annotations

from uuid import UUID

from django.tasks import task

from freedom_ls.registration_rules.evaluation import evaluate_rule


@task()
def evaluate_rule_task(rule_id: str, site_id: int) -> None:
    evaluate_rule(UUID(rule_id), site_id)
