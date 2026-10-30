"""Running a recorded bulk action: the part that needs only a run id."""

from __future__ import annotations

from collections.abc import Callable

from django.db.models import QuerySet
from django.shortcuts import get_object_or_404
from django.utils.module_loading import import_string

from freedom_ls.panel_framework.actions import count_noun, count_phrase
from freedom_ls.panel_framework.bulk_actions import (
    RESULT_ENTRY_LIMIT,
    BulkCount,
    BulkResult,
    BulkResultEntry,
    RecordedBulkAction,
    run_apply,
)
from freedom_ls.panel_framework.models import BulkActionRun, RunStatus
from freedom_ls.panel_framework.run_records import record_run

NOT_FOUND = "not found"
ACTION_UNAVAILABLE = "This action is no longer available."


def action_for(run: BulkActionRun) -> RecordedBulkAction | None:
    """The action a stored run names, or None once it has been renamed or
    removed: a run outlives the code that recorded it."""
    try:
        action_class = import_string(run.action_path)
    except ImportError:
        return None
    if not (
        isinstance(action_class, type) and issubclass(action_class, RecordedBulkAction)
    ):
        return None
    return action_class()


def save_processed(run: BulkActionRun) -> Callable[[int], None]:
    """A progress callback that stores how many objects have been handled."""

    def save(processed: int) -> None:
        run.processed_count = processed
        run.save(update_fields=["processed_count"])

    return save


def with_missing_keys(
    result: BulkResult, keys: list[str], queryset: QuerySet, reason: str
) -> BulkResult:
    """`result` plus one skipped entry for every snapshot key `queryset` no
    longer holds, so a row deleted since the confirmation is reported rather
    than silently dropped."""
    found = {str(pk) for pk in queryset.values_list("pk", flat=True)}
    missing = [key for key in keys if key not in found]
    if not missing:
        return result
    room = max(RESULT_ENTRY_LIMIT - len(result.entries), 0)
    entries = result.entries + [
        BulkResultEntry(key=key, row_label=key, status="skipped", reason=reason)
        for key in missing[:room]
    ]
    return BulkResult(
        counts=[*result.counts, BulkCount("skipped", reason, len(missing))],
        entries=entries,
        left_out=result.left_out + max(len(missing) - room, 0),
    )


def _run_on_site(run_id: str, site_id: int) -> QuerySet[BulkActionRun]:
    """Callable from a background task, which has no request and so no
    ambient site: the run is read through `_base_manager` filtered on
    `site_id`."""
    return (
        BulkActionRun._base_manager.filter(site_id=site_id, pk=run_id)
        .select_related("requested_by", "scope_type")
        .prefetch_related("scope")
    )


def run_bulk_action(run_id: str, site_id: int) -> BulkResult:
    """Apply the run's action to its snapshot of keys and store the result.

    It returns the live result so the inline path never parses its own JSON.
    """
    run = get_object_or_404(_run_on_site(run_id, site_id))
    with record_run(run, extra_fields=("result",)):
        action = action_for(run)
        if action is None:
            run.status, run.error_message = RunStatus.FAILED, ACTION_UNAVAILABLE
            return BulkResult(counts=[], entries=[], left_out=0)
        cleaned_data = action.resolve_target(run.scope, run.target)
        queryset = action.with_related(action.objects_for_keys(run.scope, run.keys))
        result = run_apply(
            action,
            run.requested_by,
            run.scope,
            queryset,
            cleaned_data,
            on_progress=save_processed(run),
        )
        result = with_missing_keys(result, run.keys, queryset, NOT_FOUND)
        run.result, run.status = result.to_json(), RunStatus.DONE
    return result


def report_finished(run_id: str, site_id: int) -> None:
    """Tell the run's action a background run is over, however it ended. A run
    still queued or running, or one whose action is gone, is left alone."""
    run = (
        _run_on_site(run_id, site_id)
        .filter(status__in=[RunStatus.DONE, RunStatus.FAILED])
        .first()
    )
    if run is None:
        return
    action = action_for(run)
    if action is not None:
        action.on_finished(run)


def run_label(run: BulkActionRun, action: RecordedBulkAction | None) -> str:
    """The action's label, or its stored name spelled out when the action is
    no longer registered."""
    if action is not None:
        return action.label
    return run.action_name.replace("_", " ").capitalize()


def _counted(action: RecordedBulkAction | None, count: int) -> str:
    if action is None:
        return count_phrase(count, "row", "rows")
    return count_noun(action.noun_model, count)


def stopped_after(run: BulkActionRun, action: RecordedBulkAction | None) -> str:
    """Where a run that did not finish got to: "after 1 of 2 learners"."""
    return f"after {run.processed_count} of {_counted(action, len(run.keys))}"


def run_summary(run: BulkActionRun) -> str:
    """One sentence on how a finished run went, for someone who was not
    watching it."""
    action = action_for(run)
    label = run_label(run, action)
    if run.status == RunStatus.FAILED or run.result is None:
        return f"{label} stopped {stopped_after(run, action)}."
    result = BulkResult.from_json(run.result)
    parts = [f"{_counted(action, result.changed)} changed"]
    for status in ("skipped", "failed"):
        count = sum(item.count for item in result.counts if item.status == status)
        if count:
            parts.append(f"{count} {status}")
    return f"{label} finished: {', '.join(parts)}."
