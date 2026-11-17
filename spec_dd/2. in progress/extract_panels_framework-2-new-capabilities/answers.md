# Answers: extract_panels_framework-2-new-capabilities

Asked by `/sdd:start` before the spec was written.

- Q: Is the "as of <time>" stamp on lazy panels opt-in or opt-out? (The idea says a panel can switch it off, but also that existing lazy panels render as before and no `educator_interface` screen changes.) → A: Opt-in. Off by default; a panel turns it on. (asked up front)
- Q: Do expandable rows also cover nested child rows, so the course outline moves onto `<c-data-table>` and loses its `HAND_WRITTEN_TABLE_EXEMPTIONS` entry? → A: Yes, cover nested child rows. If useful, allow fully custom child-row overrides. The outline moves onto `<c-data-table>` and its exemption is removed. (asked up front)
- Q: On a phone, how do nested child rows (the course outline on `<c-data-table>`) show, given `<c-data-table>` switches to cards below md? → A: Indented cards: each row a card, indented by depth, the same chevron hiding its descendants' cards. (asked during spec_from_idea)
