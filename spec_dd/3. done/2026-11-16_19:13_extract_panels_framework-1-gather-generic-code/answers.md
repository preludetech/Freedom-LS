# Answers: extract_panels_framework-1-gather-generic-code

Asked by `/sdd:start` before the spec was written.

- Q: Where should `sidePanel` (base JS), `refreshTimer` (comms JS) and the `conversationChanged` event live? → A: Both move into the framework; each nav item carries the event names its count refreshes on, so the host supplies `conversationChanged` and the framework names no `comms` event (asked up front)
- Q: `sidePanel` drives every interface's sidebar via `base/_base_interface.html` and `refreshTimer` the header messages button on every page, while the framework JS loads only in the educator shell: how do they move? → A: The panel framework must be self-contained; FLS's base templates load the side panel from the framework (host → framework is the allowed direction) (re-asked after research)
- Q: What form should the framework's declared public surface take? → A: `__all__` per public module (tables, panels, actions, filters, models, context, …); private helpers in `views.py` get a leading underscore or stay out of `__all__`; a test checks every name a host imports is listed (asked up front)
