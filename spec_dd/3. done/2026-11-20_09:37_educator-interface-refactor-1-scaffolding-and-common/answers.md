# Answers: educator-interface-refactor-1-scaffolding-and-common

Asked by `/sdd:start` before the spec was written.

- Q: No test calls the shared action helpers directly; they are covered only by HTTP tests of area actions. Should `tests/panels/common/test_actions.py` be created from the "optional reason" and "empty pickers" sections? → A: No. Those tests stay in `tests/test_actions.py` and move with their areas; `common/actions.py` gets no test file in this spec. (asked after the research)
- Q: Should the moved underscore-prefixed helpers (`_interface_link`, `_uuid_from`, `_picker_title` and the rest) lose their underscores now that other modules import them? → A: No, keep the names as they are. (asked after the research)
- Q: How should the rule that `panels/common/` imports no flat module and no area package be enforced? → A: A grep check in the success criteria only; no import-linter contract. (asked after the research)
