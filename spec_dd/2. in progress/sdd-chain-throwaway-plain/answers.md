# Answers: sdd-chain-throwaway-plain

Asked by `/sdd:start` before the spec was written.

- Q: How should `format_duration` render a duration under one minute (e.g. 45 seconds)? → A: `0h 00m`: the same hours-and-minutes shape as every other value, seconds floored away (asked up front)
- Q: What should `format_score(earned, possible)` return when `possible` is `0`? → A: Render `0 / 0`: no division happens, so the numbers are rendered as given and callers never guard (asked up front)
- Q: What should both helpers do with negative numbers (e.g. `-60` seconds, or `earned=-1`)? → A: Raise `ValueError` (asked while the research ran)
