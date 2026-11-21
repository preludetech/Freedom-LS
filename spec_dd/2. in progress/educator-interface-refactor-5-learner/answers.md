# Answers: educator-interface-refactor-5-learner

Asked by `/sdd:start` before the spec was written.

Asked by `/sdd:spec_from_idea` while the research ran.

- Q: `learner_status_badge` in `instance_view.py` makes a cycle inside the learner area; where should it live? → A: `panels/common/badges.py`, beside `active_status_badge`
- Q: `partial_oversight_thread_older` in `messages.py` makes a config → instance_view → messages → config cycle; where should it go? → A: `panels/learner/import_views.py`
