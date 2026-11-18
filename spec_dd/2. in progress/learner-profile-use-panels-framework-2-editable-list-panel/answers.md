# Answers: learner-profile-use-panels-framework-2-editable-list-panel

Asked by `/sdd:start` before the spec was written.

- Q: Can a user reorder entries by hand, or does the order always come from the consumer's query? → A: Query order only. The consumer's query sets the order; there is no manual reorder (asked up front)
- Q: Should the panel support a maximum number of entries, and what shows when the limit is reached? → A: Optional cap set by the consumer. At the cap the Add button is replaced by a short line saying the limit is reached, and the add endpoint refuses too (asked up front)
- Q: What should the new panel class be called? → A: `EditableListPanel` (asked up front)
- Q: How does the consumer define each entry's summary? → A: A callable returning a title and an optional detail line; the framework owns the markup (asked up front)
- Q: Should the Add dialog offer "Add and add another" beside "Add"? → A: Add only by default; a consumer can switch on "Add and add another" (asked while the research ran)
- Q: How should the panel draw its entries: `<c-panel-list>` rows or data-table rows inside `.panel-data-table`? → A: Configurable: the consumer chooses (asked while the research ran)
