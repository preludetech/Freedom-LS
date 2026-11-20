# Research: reference implementations of a short editable list of child records

Method note: written from working knowledge of each system. Only one fetch was attempted (a GOV.UK URL that 404ed), so no page was re-verified this session. URLs are the canonical docs locations; treat details as "recalled, check before quoting". Terms stay as each system names them.

## Comparison

| System | Consumer declares | Per-entry edit/delete routing and scope | Max count | Empty state |
|---|---|---|---|---|
| Django admin inlines | `InlineModelAdmin` subclass (`TabularInline`/`StackedInline`) with `model`, `form`, `fields`, `extra`, `ordering`, nested on the parent `ModelAdmin.inlines` | No per-entry URL. Entries are formset forms posted with the parent form. Scope is the parent's reverse FK queryset (`get_queryset`). Delete is a `DELETE` checkbox per form. | `max_num`, `min_num`, `extra`. At the cap the "Add another" link is hidden by JS. | Shows `extra` blank forms. No text empty state. |
| django-unfold | Same `InlineModelAdmin` API, restyled. Adds `tab = True`, `hide_title`, sortable inlines through `ordering_field` + `hide_ordering_field`. | Same as Django admin (parent form post). | Same `max_num`. | Same as Django admin. |
| Wagtail `InlinePanel` | `InlinePanel("relation_name", panels=[...], min_num, max_num, label)` on a `ClusterableModel` parent, children are `Orderable` models. | Children live in a modelcluster formset saved with the parent. No per-entry URL. Scope is the parent's cluster relation. Delete is a per-child DELETE flag and the child is removed from the DOM. | `min_num`, `max_num`. At max the add button is disabled. | Shows only the "Add" button, with the label. |
| Wagtail `ListBlock` (StreamField) | `ListBlock(ChildBlock)` | Items are JSON inside one field, so there is no child record or routing. | `min_num`, `max_num` | Add button only. |
| Filament `RelationManager` (Laravel) | A class on the parent resource with `$relationship`, `form()`, `table()` (columns = the summary), header `CreateAction`, row `EditAction`/`DeleteAction`, `->defaultSort()` | Row actions are modal actions bound to the row `$record`. Livewire resolves it through the parent's relationship query (`getTableQuery`), so a record outside the relationship cannot be reached. Delete asks for confirmation (`requiresConfirmation()`). | None built in. Done by `->visible(fn () => $count < N)` on `CreateAction`. | `emptyStateHeading/Description/Actions` on the table, with an icon. |
| Filament `Repeater` | `Repeater::make('items')->relationship()->schema([...])->maxItems()->minItems()->reorderable()->itemLabel(fn)->addActionLabel()->collapsible()` | Entries are inline in the parent form, saved with it. `itemLabel` is the per-entry summary. The relationship mode scopes to the parent's relation. | `maxItems()`. At the cap the add button is hidden. | Empty list shows only the add button. |
| Rails nested forms (Hotwire) | `accepts_nested_attributes_for :entries, allow_destroy: true, limit: N`. The view uses `fields_for` plus a Stimulus nested-form controller that clones a `<template>`. The alternative is separate CRUD: `resources :users do resources :entries end` with Turbo Frames and Turbo Streams. | Nested attributes: parent form post, `_destroy` flag, scoped by `parent.entries`. Separate CRUD: `/users/:user_id/entries/:id` with `current_user.entries.find(params[:id])`. Scoped lookup raises `RecordNotFound`, which is a 404. Edit loads into a `turbo_frame`. | `limit:` on nested attributes (server side, raises `TooManyRecords`). The UI hides the add button by hand. | By hand in the view. Turbo Stream `remove` is often paired with an `empty` partial. |
| Phoenix LiveView streams | `stream(socket, :entries, list)`. The template iterates `@streams.entries` with a DOM id per item. `stream_insert`, `stream_delete`, `limit:` option. | Events are `phx-click="delete" phx-value-id=...`. The server must re-scope with `Repo.get_by!(Entry, id: id, user_id: user.id)`. The framework gives no scoping. | `stream(..., limit: n)` trims the DOM, not the data. A cap on adds is by hand. | The CSS `only:block` trick on a sibling of the stream container (`hidden only:block`) shows the empty state when the container has no children. |
| GOV.UK "add another thing" | Pattern, not code. Each item is a grouped form. Page has "Add another [thing]" and "Remove" buttons. Content names the thing. | Per-item "Remove" posts to the server with the item index. | Advice: set a sensible limit, say it up front, and explain on reaching it. Suggests a separate summary page past about 10 items. | Start with one item, or ask "Do you want to add any?" first. |
| GOV.UK summary list | Component: `<dl>` of key, value, actions. Each row has "Change" and "Delete" links. | Links go to a separate page per row. Each link has visually hidden text naming the row ("Change <span class="govuk-visually-hidden">name</span>"). | n/a | Pattern "Check answers" shows "Not provided" for empty rows. |
| LinkedIn profile Experience section | Not public. Observed UI. | Section header has a "+" (add) and a pencil. The pencil opens a list, and each entry has its own pencil that opens a modal dialog. Delete sits inside the edit modal, with a confirmation. | No visible cap for experience. Skills and featured have caps. | Owner sees an "Add experience" prompt card. Visitors see nothing, and the section is hidden. |

## Patterns across them

1. Two families exist.
   - **Formset-in-parent-form**: Django admin, Unfold, Wagtail InlinePanel, Filament Repeater, Rails nested attributes. Entries save with the parent and there is no per-entry route. It suits forms with one Save. It does not fit this spec, which saves each entry on its own from a dialog and refreshes through events.
   - **Child-resource-with-own-endpoint**: Filament RelationManager, Rails nested resources with Turbo, GOV.UK summary list, LinkedIn. Each entry has its own add/edit/delete request, scoped by the parent. This matches the idea.
2. Scoping is always done by resolving the entry through the parent relation (`parent.entries.get(pk=…)`), not by a global `get(pk)` followed by a check. Filament does it through the relationship query. Rails does it through `current_user.entries.find`. Phoenix leaves it to the developer and it is the usual source of insecure code. The framework should resolve through the consumer's scoped query and return 404 on miss.
3. The consumer declares the same four things in every system: the model/relationship, the form, the order (default sort or `ordering`), and a label for each entry (Filament `itemLabel` or table columns, Wagtail `Orderable` `__str__`, GOV.UK row key/value). A callable returning a title and detail line is close to Filament's `itemLabel` and the GOV.UK key/value shape.
4. Max count:
   - Django, Wagtail and Filament Repeater hide or disable the add control at the cap.
   - Rails also enforces on the server (`limit`).
   - Filament RelationManager has no cap and uses a `visible` condition.
   - GOV.UK says to tell the user the limit before and at the point it is hit.
   - Best practice for this spec (matching the answers): hide Add, show a line saying the limit is reached, and refuse the add endpoint server side too. Client-hiding alone is the Django admin weakness (the cap is also enforced on its server side by the formset).
5. Empty state: Filament RelationManager has the richest (heading, description, call-to-action). Phoenix uses a CSS-only `only:block`. LinkedIn shows an owner-only prompt. The common form is a short message plus the Add button. Each fits `EditableListPanel` best when the empty text is a consumer-overridable string with a framework default.
6. Per-entry controls name the entry: GOV.UK uses visually hidden text ("Change *job title*"). Filament uses the record title in the modal heading and confirmation. This matches the panel-framework skill rule that every button names its entry.
7. Delete confirmation: Filament `requiresConfirmation()`, LinkedIn confirm dialog, GOV.UK "Remove" often goes to a confirm page. Django admin, Wagtail and Rails nested forms have none because removal only applies on Save.
8. Ordering: Filament Repeater, Wagtail Orderable and Unfold support manual reorder. Filament RelationManager, Rails separate CRUD and LinkedIn experience (date-based) order by query. The decided query-order-only matches the simpler family and avoids a reorder endpoint and a position field.
9. Refresh after change: Filament uses Livewire events to refresh other components. Rails uses Turbo Streams. Both are comparable to `success_events`/`refresh_events`.

## Implications for the spec

- Build the child-resource family: one panel with three framework actions (add, edit, remove) that resolve the entry from the URL through the consumer's scoped query, and 404 outside it. Closest analogue is Filament RelationManager with header create, row edit and delete.
- Enforce the cap in two places (render and add endpoint), as Rails does, and treat the cap as optional.
- Summary callable returns title plus optional detail, as Filament `itemLabel`/GOV.UK key-value, and the framework owns the markup.
- Empty state: default text plus the Add button, with the text overridable.
- Do not follow Phoenix on scoping. Make scoped resolution part of the framework so consumers cannot forget it.
- Watch the cap race: two concurrent adds can exceed the cap if the count check and insert are not in one transaction. Rails `limit` has the same issue. Check inside the action's transaction.

## Reference URLs

- Django admin inlines: https://docs.djangoproject.com/en/stable/ref/contrib/admin/#inlinemodeladmin-objects
- Django-unfold inlines: https://unfoldadmin.com/docs/inlines/
- Wagtail InlinePanel: https://docs.wagtail.org/en/stable/reference/pages/panels.html#inline-panels
- Wagtail ListBlock: https://docs.wagtail.org/en/stable/reference/streamfield/blocks.html#wagtail.blocks.ListBlock
- Filament relation managers: https://filamentphp.com/docs/3.x/panels/resources/relation-managers
- Filament table empty state: https://filamentphp.com/docs/3.x/tables/empty-state
- Filament Repeater: https://filamentphp.com/docs/3.x/forms/fields/repeater
- Filament confirmation modals: https://filamentphp.com/docs/3.x/actions/prebuilt-actions/delete (and `requiresConfirmation` under https://filamentphp.com/docs/3.x/actions/modals)
- Rails nested attributes: https://api.rubyonrails.org/classes/ActiveRecord/NestedAttributes/ClassMethods.html
- Hotwire Turbo Frames and Streams: https://turbo.hotwired.dev/handbook/frames
- Phoenix LiveView streams: https://hexdocs.pm/phoenix_live_view/Phoenix.LiveView.html#stream/4
- GOV.UK add multiple things pattern: https://design-system.service.gov.uk/patterns/add-multiple-things/ (the `/patterns/add-another/` path I tried returned 404)
- GOV.UK summary list: https://design-system.service.gov.uk/components/summary-list/
- LinkedIn Experience help: https://www.linkedin.com/help/linkedin/answer/a542685 (recalled, unverified)

status: ok
