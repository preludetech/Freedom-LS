Research topic: how a `DataTable` should declare filters (Django form fields vs a small
purpose-built class), for `educator-interface-2-panel-framework-tables`.

## The mockup, exactly

`Educator LMS Interface Design/Educator Learners.dc.html`, screen 02, the toolbar row above the
learner table (lines 46-55):

- A search box (`mol` typed in, focus ring shown).
- A **closed, unopened** filter: a pill labelled "Cohort" with a funnel icon and a caret-down —
  this is a filter that exists but has no value chosen, rendered as a dropdown trigger, not a chip
  with a value.
- An **active** filter: a pill reading "Status: Stalled", styled differently (primary-coloured
  border and text, filled background) with an "x" to remove it — this is a filter with a value
  chosen, shown as a removable chip carrying its own label and current value inline.
- An "Add filter" pill: a plain "+ Add filter" button, no value, no caret — this is the affordance
  for filters not yet placed in the toolbar at all.
- To the right, unrelated to filtering: "Sorted by Last active" text and a columns-picker icon.

So the mockup encodes three distinct states for a filter, not one: **not yet added** (only reachable
through "Add filter"), **added but unset** (a dropdown pill showing just its label, e.g. "Cohort"),
and **added and set** (a chip showing `Label: value` with a clear affordance). Only one filter
("Status") is set in the screenshot; "Cohort" is present as a dropdown but empty. This matches the
idea's line "a choice filter (status, cohort) ... They render as a toolbar ... matching the
mockup's 'Cohort', 'Status', 'Add filter' chips" (`idea.md:27`).

## Reference designs

**Django admin `list_filter` / `SimpleListFilter`.** `ModelAdmin.list_filter` takes a field name, a
`(field, FieldListFilter subclass)` pair, or a `SimpleListFilter` subclass. `SimpleListFilter`
declares `title`, `parameter_name`, a `lookups(request, model_admin)` method returning
`[(coded_value, label), ...]`, and a `queryset(request, queryset)` method that narrows the
queryset from `self.value()`. Every choice filter always renders in the sidebar — there is no
add/remove; the sidebar itself is the "always visible, densely packed" pattern, which is what
FLS's mockup explicitly rejects in favour of chips.
(https://docs.djangoproject.com/en/5.1/ref/contrib/admin/filters/,
https://github.com/django/django/blob/main/django/contrib/admin/filters.py)

Historically an unrecognised or malformed filter value on a `ForeignKey`/`__in` filter raised
`IncorrectLookupParameters`, and the changelist view caught it and redirected to `?e=1` (an "error"
marker), dropping the offending filter — ticket #17936
(https://code.djangoproject.com/ticket/17936). That is the opposite of the idea's stated contract
("unknown values are ignored, not errored", `idea.md:27`): admin's own error path is a full
redirect, not a same-page no-op, and different filter subclasses raise differently, which is a
maintenance hazard admin authors specifically warn about.

FLS already has its own in-house precedent for the "ignore, don't error" contract, in
`freedom_ls/site_aware_models/admin_filters.py`. `CompletionListFilter.queryset()` checks
`self.value() not in {"complete", "incomplete"}` and returns the queryset unchanged rather than
raising; `InclusiveRangeDateTimeFilter.queryset()` catches `ValueError`/`ValidationError` around
the actual `.filter()` call and returns `None` (admin's "drop this filter" contract) instead of
propagating. Both are `SimpleListFilter`-style: a declarative class with a `lookups`/choices method
and a queryset-narrowing method, no Django form involved. This is the closest existing FLS
convention to copy in spirit (not the class itself — it's admin-only and depends on
`ModelAdmin`/`used_parameters`).

**django-filter `FilterSet`.** Form-backed: a `FilterSet` is built like a `ModelForm`, each
`Filter` (e.g. `ChoiceFilter`, `ModelChoiceFilter`, `BooleanFilter`) wraps a form field, and
`filterset.qs` applies validated filters to a queryset; `filterset.form` renders the filter UI
through ordinary Django form rendering. Two knobs map directly onto the idea's open question:
`Meta.strict` / `FilterSet.strict` (or per-instance) controls whether an invalid value is dropped
silently (`STRICTNESS.IGNORE`, filters are a no-op but valid filters still apply) or raises/renders
form errors, and `Meta.unknown_field_behavior` (`UnknownFieldBehavior.RAISE`/`WARN`/`IGNORE`)
controls what happens when a name in the query string isn't a declared filter at all — `IGNORE`
and `WARN` both drop the field from the applied filters.
(https://django-filter.readthedocs.io/en/stable/ref/filterset.html,
https://django-filter.readthedocs.io/en/stable/guide/tips.html) This is exactly the "ignored, not
errored" behaviour FLS wants, but it comes wrapped in full form machinery: a `django.forms.Form`
per filter set, `ModelChoiceField` querysets that must be scoped per request (django-filter has no
first-class "scope this queryset to the request" hook — the common pattern is overriding
`__init__` on the FilterSet to narrow `self.filters['cohort'].queryset`), and form rendering that
FLS would have to override entirely to get chips instead of a form.

**django-tables2 + django-filter pairing.** The documented pattern is `SingleTableMixin` +
`FilterView`, i.e. two separate class-based-view mixins each contributing a table and a filterset,
composed in the view, with the filter form rendered separately from the table
(https://django-tables2.readthedocs.io/en/stable/pages/filtering.html). This is a "two libraries,
two contracts" composition, not "one declaration matching how columns are declared." It reinforces
what `research_tables2_viability.md` (cited in `idea.md:17`) already found: the pairing exists, but
buying it means two dependencies and two conventions where FLS wants one declarative surface next
to `get_columns()`.

**Wagtail admin listing filters.** Wagtail's snippet/model admin listing views use django-filter
under the hood: `list_filter = [...]` on the view is passed straight through as
`FilterSet.Meta.fields`, or a consumer sets `filterset_class` to a `WagtailFilterSet` subclass for
anything the declarative shortcut can't express — the shortcut is ignored once a custom class is
set. (https://docs.wagtail.org/en/v5.1/topics/snippets/customising.html) So Wagtail's answer to
"simple declaration vs a full form-backed class" is: offer the simple declaration as sugar over the
same form-backed engine, escape-hatch to the full class when needed. Wagtail's listing template
renders active filters as removable chips above the table with a count and a "clear all" — the
same visual language FLS's mockup uses, but Wagtail always renders every declared filter's control
(no add/remove state), it just renders *active* ones as chips and *inactive* ones through the
filter panel/button.

**Filament (Laravel/PHP) table filters.** Not Django, cited for the declaration shape only.
Filament filters are one class per filter (`SelectFilter::make('status')->options([...])`,
`TernaryFilter::make('active')` for a three-state true/false/blank toggle with `boolean()`,
`trueLabel()`, `falseLabel()`), declared in a `filters()` array next to the table's `columns()`
array — the same flat, side-by-side declaration style as columns, which is what FLS's idea asks
for. (https://filamentphp.com/docs/4.x/tables/filters/overview,
https://filamentphp.com/docs/4.x/tables/filters/ternary) `TernaryFilter` is a good model for FLS's
"boolean toggle (show inactive)" filter: a bare boolean field is often really three states (yes/no/
don't care), and collapsing "don't care" into "no query param present" is cleaner than a `False`
that has to be distinguished from "not filtered."

**GitHub/Linear "Add filter" chip UX.** General filter-UI surveys describe the same pattern the
mockup uses: filters as removable chips in a toolbar, with a "+ Add filter" trigger that surfaces a
picker of filter *types* not yet placed, so the toolbar only shows filters someone actually chose to
use (https://www.pencilandpaper.io/articles/ux-pattern-analysis-enterprise-filtering,
https://goodpractices.design/components/filter-chips). This is a genuinely different model from
admin's "every filter always occupies space in the sidebar": in the chip model, a table can declare
many filters without cluttering the toolbar for a user who uses none of them, and "Cohort" versus
"Status" in the mockup shows the two chip states this implies — a filter that's been added to the
toolbar but has no value yet (dropdown-styled pill, label only) is visually distinct from one that's
both added and set (filled pill, `Label: value`, with a clear "x").

## FLS-specific trade-offs

**Multi-tenancy on choice lists.** A cohort filter's choices must be exactly the requesting
educator's organisation's cohorts, never every cohort on the site. `SimpleListFilter.lookups()` and
django-filter's `ModelChoiceFilter` both take a plain queryset/list of choices computed at
call-time, so either shape can be scoped from the request — the question is *where* that scoping
is expressed. Django admin filters get `request` into `lookups()` directly. django-filter needs the
FilterSet instantiated with `request` and the per-request queryset narrowed in `__init__` (there is
no clean per-field "scope me" hook), which is exactly the kind of form-plumbing the idea's open
question worries about. A purpose-built filter class can define `get_choices(request)` the same
shape `DataTable.get_queryset(request)` already takes, so the scoping code lives in one obvious
place and reads the same way the table's own row-scoping does.

**Related-object filters and N+1.** A cohort filter's choices are themselves a queryset
(`Cohort.objects.filter(organisation=...)`), so `get_choices` needs `select_related`/values the
same discipline as any other query in the project (`CLAUDE.md`: "Use select_related()/
prefetch_related() for all related-object queries"). Because the choice list is small and re-run
once per table render (not per row), this is a single extra query per filter, not an N+1 in the row
sense — worth stating explicitly since "related-object filter" can sound like it risks one.

**Filters must survive pagination with prefixed keys.** The idea already settles `<key>-<filter>`
naming (`idea.md:23`). Neither `SimpleListFilter` (admin owns its own unprefixed `parameter_name`)
nor django-filter (a `FilterSet` reads a flat `QueryDict`, no per-instance prefix convention) does
prefixed keys out of the box — both would need a wrapper. A purpose-built class can take the
already-namespaced key as a constructor/declaration detail and needs no wrapper.

**Unknown values ignored, not errored.** Settled by the idea already (`idea.md:27`). This rules out
admin's default (`IncorrectLookupParameters` + `?e=1` redirect) as a model to imitate literally,
though FLS's own `CompletionListFilter`/`InclusiveRangeDateTimeFilter` already show the target
behaviour: check the value, fall through to "no-op" on anything unrecognised. django-filter offers
the same behaviour via `strict`/`unknown_field_behavior`, but only by taking on the rest of the form
machinery to get it.

**Feeding CSV export and the bulk-action "current filter" payload.** The idea's export hook must
"honour the table's filters and scoping" and the bulk-action hook receives "the selected primary
keys and the current filter" (`idea.md:29,31`) so that "select all matching" can be added later
without a second contract. That means the *applied* filter state (which filters are active and
their validated values) has to be representable as something serialisable — realistically the
already-validated `dict[str, str]` of `<filter_key>: <raw_value>` slice of `request.GET`, or
equivalently the querystring itself, not a bound Django `Form` instance (forms don't serialise
cleanly into a bulk-action POST body or a signed token). A purpose-built filter class that exposes
"the query params this table understands, already narrowed to declared filters, unknown ones
dropped" is a more natural fit for that payload than "the FilterSet instance."

**Rendering as chips/dropdown vs a rendered form.** django-filter's `filterset.form` is a bound
Django form meant to be rendered as form fields (`{{ filter.form }}` or field-by-field), which
fights the mockup's three-state chip/dropdown/add-button rendering rather than helping it — FLS
would override every widget's template to get chips, at which point the form layer contributes
almost nothing beyond validation. Column declarations in `tables.py` are plain dicts
(`get_columns() -> list[dict[str, object]]`) rendered by `cotton/data-table-cells/` templates keyed
on attributes the dict carries (`sortable`, `text_attr`, `attr`); a filter declaration that is a
small dataclass/class with a `kind` ("choice", "boolean", "related") and a render-relevant shape
mirrors that existing pattern exactly, whereas a Django form field is a different rendering unit
from a column dict and would introduce a second declaration idiom into the same file.

## UX findings

- **Hidden active filters and no clear-all** are the most cited complaint about admin-style
  sidebars: a filter set two clicks ago (a stale "only stalled learners" filter) is easy to forget
  is applied, because the sidebar looks the same whether zero or three filters are active
  (https://code.djangoproject.com/ticket/15935,
  https://appliku.com/post/filters-and-custom-filters-in-django-admin/). The chip toolbar the
  mockup uses is a direct answer: an active filter is a filled, coloured chip with its value
  printed inline (`Status: Stalled`) and an explicit "x", so "what's currently filtered" is legible
  at a glance without opening anything, and a table-level "clear all" (not shown in the screen 02
  crop but implied by there being multiple independently-removable chips) is cheap to add next to
  it.
- **"Add filter" implies optional, hidden-until-added filters**, as opposed to every declared filter
  always occupying toolbar space (admin's sidebar, Wagtail's filter panel). This matters for FLS
  because a table may accumulate filters over time (spec 8's bulk actions, spec 10's reporting
  views reusing the same table) without the toolbar growing unbounded for a user who only ever uses
  one or two.
- **Filter + search interaction.** The mockup places search and filters in the same toolbar row, at
  the same visual weight, and the idea's already-settled behaviour ("Changing sort, a filter or the
  search resets that table's page", `idea.md:23`) treats them uniformly for pagination purposes —
  worth carrying that uniformity into the filter declaration too, so a filter is a peer of "sort"
  and "search," not a special case.
- **Counts on choices** (e.g. "Stalled (4)") are a documented enhancement in the wider filter-UX
  literature but appear nowhere in the mockup's chips, which show only the label and picked value —
  not required for this spec; worth flagging as an easy follow-up once the choice-fetching path
  exists, not a reason to complicate the first declaration shape.

## Recommendation

Build a small purpose-built filter class, not Django form fields, mirroring the shape
`DataTable.get_columns()` already uses for columns. Reasons:

1. **Matches the existing declaration idiom in `tables.py`.** Columns are plain, render-oriented
   dicts consumed by `cotton/data-table-cells/`. A filter class with a `kind` and the attributes
   each kind needs (a choice filter's `key`/`label`/`get_choices(request)`; a boolean filter's
   `key`/`label`/on-value; a related filter's `key`/`label`/`get_queryset(request)`) is the same
   shape of thing, reads the same way, and needs no second rendering idiom bolted on.
2. **The "unknown values ignored, not errored" contract is a two-line check per filter**
   (`value in {declared choices}` else no-op), exactly what FLS's own
   `CompletionListFilter`/`InclusiveRangeDateTimeFilter` already do without a form — a Django form
   would have to be configured (`strict=IGNORE`, `unknown_field_behavior=IGNORE`) to get the same
   behaviour it already has by default in the wrong direction (raise/error).
3. **Multi-tenant choice scoping wants a request-taking method, not a form-level `__init__`
   override.** `get_choices(request)` / `get_queryset(request)` on the filter class is the same
   contract `DataTable.get_queryset(request)` and `Panel.get_queryset(request)` already use
   throughout the framework — one scoping idiom project-wide, not a new one for filters.
4. **The mockup's three chip states (not-added / added-unset / added-set) and the export/
   bulk-action payload both want "declared filter → validated raw value," a small serialisable
   unit** — closer to what a purpose-built class naturally produces than to a bound Django `Form`
   instance, which is built to be rendered as HTML controls and validated as a batch, not
   serialised into a CSV-export URL or a bulk-action POST body.
5. **No new rendering machinery to fight.** Form fields buy validation and widgets FLS doesn't need
   (the widgets are wrong for the mockup regardless — chips, not `<select>` boxes, for most of
   them) at the cost of a rendering model (`BoundField`, widget templates) that has to be
   overridden anyway to get chips.

What Django forms would still legitimately be reused for, narrowly: if a filter's *value* is
genuinely complex to validate (e.g. a date-range bound, which Django's own
`InclusiveRangeDateTimeFilter` above shows is fiddly), the filter class's `validate(raw_value)` can
delegate to a single `forms.Field.clean()` call internally without the table needing a whole
`Form`. That keeps validation reuse available per-filter without adopting form rendering.

## Declaration shape (prose sketch, not a checklist)

A table declares filters the way it declares columns: `get_filters()` returns a list of small
filter objects, each carrying the things its `kind` needs to render its toolbar chip/dropdown and
to narrow a queryset. Every filter has a `key` (the part after the table's prefix, e.g. `status`,
so the query param is `<table-key>-status`), a `label` for the chip, and a `kind` distinguishing at
least "choice," "boolean," and "related" (a related filter is a choice filter whose choices come
from a scoped queryset rather than a static list — same rendering, different `get_choices`). A
choice filter supplies its choices either as a static list of `(value, label)` pairs or as a
`get_choices(request)` method for anything that must be scoped per request (cohorts, any other
organisation-owned lookup) — the same request-scoping shape `DataTable.get_queryset(request)` and
`DataTablePanel.get_queryset(request)` already use, so a consumer overriding a filter's choices for
multi-tenancy writes exactly the pattern it already knows from scoping the table's own rows. A
boolean filter is the Filament ternary shape collapsed to what FLS needs: present in the query
string with one accepted "on" value narrows the queryset, absent means "don't care," so there is no
tri-state to represent beyond "filtered" and "not mentioned."

Applying filters to a request follows the same read-only-my-own-keys discipline the table already
has for sort/search/page: for each declared filter, read `request.GET.get(f"{table_key}-{key}")`,
and if it is present, validate it against the filter's declared choices (or its `validate` for
anything more than a fixed set); a value that doesn't validate is dropped silently, exactly as
`CompletionListFilter` drops an unrecognised value today, so a stale or hand-edited URL degrades to
"filter not applied" rather than an error page. The set of `(filter, applied_value)` pairs that
survived validation is what the toolbar renders (an added-and-set chip per applied filter, an
added-but-unset control for any filter the consumer has chosen to always show — "Cohort" in the
mockup — and the rest reachable through "Add filter"), what narrows the queryset before pagination,
what the CSV export URL carries forward unchanged, and what the bulk-action hook is handed as "the
current filter" alongside the selected primary keys — one small, serialisable value used in all
four places, rather than a bound form that only really serves rendering and validation.

## References

- Django admin filters: https://docs.djangoproject.com/en/5.1/ref/contrib/admin/filters/
- Django admin filters source: https://github.com/django/django/blob/main/django/contrib/admin/filters.py
- `IncorrectLookupParameters` / `?e=1` redirect ticket: https://code.djangoproject.com/ticket/17936
- Persistent-filter and hide-filter tickets: https://code.djangoproject.com/ticket/3777, https://code.djangoproject.com/ticket/15935
- django-filter `FilterSet` reference (strict, unknown_field_behavior): https://django-filter.readthedocs.io/en/stable/ref/filterset.html
- django-filter tips (strictness): https://django-filter.readthedocs.io/en/stable/guide/tips.html
- django-tables2 + django-filter pairing: https://django-tables2.readthedocs.io/en/stable/pages/filtering.html
- Wagtail snippet listing filters (`list_filter`, `WagtailFilterSet`): https://docs.wagtail.org/en/v5.1/topics/snippets/customising.html
- Filament table filters overview: https://filamentphp.com/docs/4.x/tables/filters/overview
- Filament ternary filter: https://filamentphp.com/docs/4.x/tables/filters/ternary
- Enterprise filter UX patterns (chips, add-filter, clear-all): https://www.pencilandpaper.io/articles/ux-pattern-analysis-enterprise-filtering
- Filter chip UI good practices: https://goodpractices.design/components/filter-chips
- Django admin filter UX commentary: https://appliku.com/post/filters-and-custom-filters-in-django-admin/

## Files read

- `spec_dd/1. next/educator-interface-2-panel-framework-tables/idea.md`
- `spec_dd/1. next/roadmap.md` ("Educator interface rebuild" section)
- `freedom_ls/panel_framework/tables.py`
- `freedom_ls/panel_framework/panels.py` (`DataTablePanel`)
- `spec_dd/1. next/educator-interface-full-polish/Educator LMS Interface Design/Educator Learners.dc.html` (screen 02, toolbar lines 46-55)
- `spec_dd/1. next/educator-interface-full-polish/htmx-modal-drawer-url-state.md` (prefix convention, `{% querystring %}`)
- `freedom_ls/site_aware_models/admin_filters.py` (`CompletionListFilter`, `InclusiveRangeDateTimeFilter` — FLS's existing "ignore unknown, don't error" precedent)

status: ok
