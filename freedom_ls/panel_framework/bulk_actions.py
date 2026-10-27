"""Row selection and bulk actions: the payload a bulk-action POST names, and
the action that runs once over the rows it resolves to."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from typing import TYPE_CHECKING, Literal, cast

from django import forms
from django.contrib.auth.base_user import AbstractBaseUser
from django.contrib.auth.models import AnonymousUser
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Model, QuerySet
from django.http import HttpRequest, QueryDict

from freedom_ls.panel_framework.config import config
from freedom_ls.panel_framework.context import PanelContext
from freedom_ls.panel_framework.models import BulkActionRun, RunStatus

if TYPE_CHECKING:
    from freedom_ls.panel_framework.panels import DataTablePanel


Status = Literal["changed", "skipped", "failed"]

RESULT_ENTRY_LIMIT = 500
FAILED_REASON = "could not be changed"


@dataclass(frozen=True)
class BulkOutcome:
    """What `BulkAction.apply` did to one object."""

    status: Status
    reason: str = ""  # empty for "changed"


@dataclass(frozen=True)
class BulkCount:
    """How many objects ended in one (status, reason) pair."""

    status: Status
    reason: str
    count: int


@dataclass(frozen=True)
class ConfirmationWording:
    """What a confirmation says before anything runs.

    Each skip reason is a predicate that follows "is" or "are" ("already
    processed", "already in the cohort"), so one template renders both the
    confirmation line "3 are already processed and will be skipped." and the
    result line "3 already processed".
    """

    sentence: str
    skips: list[BulkCount] = field(default_factory=list)
    consequences: list[str] = field(default_factory=list)


class BulkConfirmForm(forms.Form):
    """The framework's own fields on a bulk-action POST."""

    expected_count = forms.IntegerField(min_value=0, required=False)
    confirmed = forms.BooleanField(required=False)
    refresh = forms.BooleanField(required=False)


def count_outcomes(outcomes: dict[str, BulkOutcome]) -> list[BulkCount]:
    """Tally outcomes into one count per distinct (status, reason), in the
    order the pairs first appear."""
    tallies: dict[tuple[Status, str], int] = {}
    for outcome in outcomes.values():
        pair = (outcome.status, outcome.reason)
        tallies[pair] = tallies.get(pair, 0) + 1
    return [
        BulkCount(status=status, reason=reason, count=count)
        for (status, reason), count in tallies.items()
    ]


@dataclass(frozen=True)
class BulkResultEntry:
    """One skipped or failed object, named so the reader can find it."""

    key: str
    row_label: str
    status: Literal["skipped", "failed"]
    reason: str


@dataclass(frozen=True)
class BulkResult:
    """What a bulk run did, in a form that survives a JSON round trip.

    `counts` has one item per distinct (status, reason), in the order the
    pairs first appeared. `entries` names at most RESULT_ENTRY_LIMIT skipped
    or failed objects; `left_out` counts those beyond the limit, so the
    stored result stays a bounded size however large the run was.
    """

    counts: list[BulkCount]
    entries: list[BulkResultEntry]
    left_out: int

    @property
    def changed(self) -> int:
        return sum(item.count for item in self.counts if item.status == "changed")

    def to_json(self) -> dict[str, object]:
        return asdict(self)

    @classmethod
    def from_json(cls, data: dict[str, object]) -> BulkResult:
        counts = cast(list[dict[str, object]], data["counts"])
        entries = cast(list[dict[str, object]], data["entries"])
        return cls(
            counts=[
                BulkCount(
                    status=cast(Status, item["status"]),
                    reason=str(item["reason"]),
                    count=cast(int, item["count"]),
                )
                for item in counts
            ],
            entries=[
                BulkResultEntry(
                    key=str(item["key"]),
                    row_label=str(item["row_label"]),
                    status=cast(Literal["skipped", "failed"], item["status"]),
                    reason=str(item["reason"]),
                )
                for item in entries
            ],
            left_out=cast(int, data["left_out"]),
        )


@dataclass(frozen=True)
class BackgroundRun:
    """Returned by `execute` when the work continues out of the request. The
    page polls `status_url`, which answers 204 until the run finishes and
    then the result fragment."""

    status_url: str


class BulkAction:
    """One action a table panel offers over a set of selected rows.

    Its URL is the table panel's own base_url plus "/__actions/<action_name>",
    the same shape a PanelAction's URL takes. Unlike a PanelAction, it never
    binds to a single instance: has_permission works over the request alone,
    and execute over the panel context and the resolved queryset.
    """

    label: str = ""
    action_name: str = ""
    variant: str = "secondary"
    #: The most rows one run inside the request handles. A selection the
    #: action hands to a background task (see `runs_in_background`) is not
    #: bounded by it.
    max_rows: int = 500
    confirm_template_name: str = "panel_framework/partials/bulk_confirmation.html"
    result_template_name: str = "panel_framework/partials/bulk_result.html"
    #: Exception types `apply` may turn into a failed outcome. Any other
    #: exception propagates: a failure the action did not name is a bug.
    failure_exceptions: tuple[type[Exception], ...] = ()
    #: A form the educator fills in before the action can run, such as a
    #: target picker. Its cleaned data becomes `cleaned_data` everywhere else.
    form_class: type[forms.Form] | None = None

    def get_form(
        self, request: HttpRequest, data: QueryDict | None
    ) -> forms.Form | None:
        """The action's own form, bound to `data` or unbound when None; None
        when the action takes no input."""
        if self.form_class is None:
            return None
        return self.form_class(data)

    def has_permission(self, request: HttpRequest) -> bool:
        return True

    def apply(
        self,
        user: AbstractBaseUser | AnonymousUser,
        obj: Model,
        cleaned_data: dict[str, object],
    ) -> BulkOutcome:
        raise NotImplementedError

    def runs_in_background(self, count: int) -> bool:
        """Whether `execute` hands a run over `count` objects to a task. The
        confirmation then skips `classify_all`, whose cost grows with the
        selection, and shows only the total."""
        return False

    def classify_all(
        self,
        request: HttpRequest,
        queryset: QuerySet,
        cleaned_data: dict[str, object],
    ) -> dict[str, BulkOutcome] | None:
        """What `apply` would do to each row, keyed by `str(pk)`, without
        changing anything. None means the action does not predict, and the
        confirmation shows the plain count. Unlike `apply`, this only ever
        runs inside a request, so it gets the whole request and whatever a
        view has resolved onto it."""
        return None

    def confirmation_wording(
        self,
        request: HttpRequest,
        queryset: QuerySet,
        classified: dict[str, BulkOutcome] | None,
        cleaned_data: dict[str, object],
    ) -> ConfirmationWording:
        """The confirmation sentence and one skip line per skip reason."""
        model = queryset.model
        if classified is None:
            count = queryset.count()
            skips: list[BulkCount] = []
        else:
            counts = count_outcomes(classified)
            count = sum(item.count for item in counts if item.status == "changed")
            skips = [item for item in counts if item.status != "changed"]
        return ConfirmationWording(
            sentence=f"This will affect {count} {model._meta.verbose_name_plural}.",
            skips=skips,
        )

    def row_label(self, obj: Model) -> str:
        return str(obj)

    def execute(
        self,
        ctx: PanelContext,
        queryset: QuerySet,
        cleaned_data: dict[str, object],
    ) -> BulkResult | BackgroundRun:
        """Run the action over `queryset`. Takes the panel context rather
        than the bare request because a run that outlives the request needs
        the table's scope and URL as well."""
        return run_apply(self, ctx.request.user, queryset, cleaned_data)

    def get_action_url(self, ctx: PanelContext) -> str:
        return f"{ctx.base_url}/__actions/{self.action_name}"


class RecordedBulkAction(BulkAction):
    """A bulk action whose every run is recorded as a `BulkActionRun`.

    `execute` snapshots the resolved keys into a run and either applies the
    action inside the request or hands the run to a background task, so the
    reader can leave the page and the result still lands somewhere. The hooks
    rebuild what the task needs from the row alone: `resolve_target` turns
    the stored `target` back into cleaned data, and `objects_for_keys` turns
    the stored keys back into rows. A host that scopes its tables narrows
    `objects_for_keys` to its scope object and reacts to `on_finished` and
    `on_result_shown`, for example by raising and clearing a notification.
    """

    table_key: str = ""
    noun_model: type[Model]

    def with_related(self, queryset: QuerySet) -> QuerySet:
        return queryset

    def target_json(self, cleaned_data: dict[str, object]) -> dict[str, str]:
        """The picker's choice as JSON, stored on the run."""
        return {}

    def resolve_target(
        self, scope: Model | None, target: dict[str, str]
    ) -> dict[str, object]:
        """Rebuild `cleaned_data` from the stored target."""
        return {}

    def objects_for_keys(self, scope: Model | None, keys: list[str]) -> QuerySet:
        """The rows the stored keys name. The keys were snapshotted from the
        table's own scoped queryset, so the default trusts them; a host that
        scopes its tables narrows this to `scope` as well."""
        return self.noun_model._base_manager.filter(pk__in=keys)

    def runs_in_background(self, count: int) -> bool:
        return count > config.BULK_BACKGROUND_THRESHOLD

    def on_finished(self, run: BulkActionRun) -> None:
        """A background run has ended, however it ended. Nothing by default."""

    def on_result_shown(self, request: HttpRequest, run: BulkActionRun) -> None:
        """The requester has seen a finished run's outcome. Nothing by default."""

    def execute(
        self,
        ctx: PanelContext,
        queryset: QuerySet,
        cleaned_data: dict[str, object],
    ) -> BulkResult | BackgroundRun:
        # Imported here because bulk_runs builds actions from this module, and
        # tasks imports bulk_runs.
        from freedom_ls.panel_framework.bulk_runs import run_bulk_action
        from freedom_ls.panel_framework.tasks import _run_bulk_action_task

        run = BulkActionRun.objects.create(
            requested_by=ctx.request.user,
            scope=ctx.scope,
            action_path=f"{type(self).__module__}.{type(self).__qualname__}",
            table_key=self.table_key,
            action_name=self.action_name,
            target=self.target_json(cleaned_data),
            keys=[str(pk) for pk in queryset.values_list("pk", flat=True)],
            status=RunStatus.QUEUED,
        )
        if self.runs_in_background(len(run.keys)):
            # A worker, not this request, does the work; the run record is
            # already queued.
            _run_bulk_action_task.enqueue(str(run.pk), run.site_id)
            return BackgroundRun(status_url=f"{ctx.base_url}/__runs/{run.pk}")
        return run_bulk_action(str(run.pk), run.site_id)


def run_apply(
    action: BulkAction,
    user: AbstractBaseUser | AnonymousUser,
    queryset: QuerySet,
    cleaned_data: dict[str, object],
    on_progress: Callable[[int], None] | None = None,
) -> BulkResult:
    """Apply `action` to each object in `queryset`, each in its own
    transaction, so one failure leaves the objects before it changed.

    A module function rather than a method so a background task can call it
    without a request.
    """
    tallies: dict[tuple[Status, str], int] = {}
    entries: list[BulkResultEntry] = []
    left_out = 0
    for processed, obj in enumerate(queryset.iterator(chunk_size=200), start=1):
        try:
            with transaction.atomic():
                outcome = action.apply(user, obj, cleaned_data)
        except action.failure_exceptions:
            # A fixed reason: exception text is for developers and never
            # reaches the page.
            outcome = BulkOutcome("failed", FAILED_REASON)
        pair = (outcome.status, outcome.reason)
        tallies[pair] = tallies.get(pair, 0) + 1
        if outcome.status != "changed":
            if len(entries) < RESULT_ENTRY_LIMIT:
                entries.append(
                    BulkResultEntry(
                        key=str(obj.pk),
                        row_label=action.row_label(obj),
                        status=outcome.status,
                        reason=outcome.reason,
                    )
                )
            else:
                left_out += 1
        if on_progress and processed % 50 == 0:
            on_progress(processed)
    counts = [
        BulkCount(status=status, reason=reason, count=count)
        for (status, reason), count in tallies.items()
    ]
    return BulkResult(counts=counts, entries=entries, left_out=left_out)


@dataclass(frozen=True)
class Selection:
    """The rows a bulk-action request names.

    "keys" names rows one by one. "all_matching" names every row the table's
    current search and filters match, across every page, minus `excluded`.
    """

    mode: Literal["keys", "all_matching"]
    keys: list[str] = field(default_factory=list)
    excluded: list[str] = field(default_factory=list)


def parse_selection(request: HttpRequest) -> Selection:
    """This bulk-action POST's own selection payload.

    An unrecognised or missing mode parses as "keys" with whatever keys (if
    any) came with it, so a malformed request falls through to the ordinary
    "zero selected" answer rather than a different error path.
    """
    mode: Literal["keys", "all_matching"] = (
        "all_matching" if request.POST.get("mode") == "all_matching" else "keys"
    )
    return Selection(
        mode=mode,
        keys=request.POST.getlist("keys"),
        excluded=request.POST.getlist("excluded"),
    )


def resolve_selection(
    panel: DataTablePanel, request: HttpRequest, selection: Selection
) -> QuerySet:
    """The rows `selection` names, scoped to `panel`.

    A key the model's primary-key field can't parse, or one outside the
    panel's own scope, drops out silently rather than raising: it reaches
    here straight from a form submission that may be stale or tampered with,
    and handlers must never see the raw keys or payload themselves.
    """

    def parsed(keys: list[str]) -> list[object]:
        pk_field = panel.get_queryset(request).model._meta.pk
        values: list[object] = []
        for key in keys:
            try:
                values.append(pk_field.to_python(key))
            except ValidationError:
                continue
        return values

    if selection.mode == "all_matching":
        # The bar put the table's own state into the action URL's query
        # string, so narrow() reads it from request.GET exactly as a render
        # or export would.
        _query, rows = panel.narrow(request)
        return rows.exclude(pk__in=parsed(selection.excluded))
    scoped = panel.get_queryset(request)
    return scoped.filter(pk__in=parsed(selection.keys))
