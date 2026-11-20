# Answers: misure-of-admonitions

Asked by `/sdd:start` before the spec was written.

- Q: No FLS template outside the content engine uses `<c-admonition>`; the content-styled callout in app pages is `<c-callout>` (base app), used by 9 FLS templates. Is `<c-callout>` the misuse this spec should fix? → A: Yes, replace `c-callout` with a new theme-fit alert component in every app page (asked up front)
- Q: What happens to `<c-callout>` once app pages use the new alert (First Class's `landing_pages` `lp/step.html` also uses it)? → A: Delete it and record the migration in the upgrade notes (asked up front)
- Q: Should a test enforce that content-engine cotton components are not used in app templates outside content rendering? → A: Yes, an invariant test (asked up front)
- Q: Should the new alert support being dismissed by the user? → A: No, static only (asked up front)
- Q: The panel framework already has `<c-panel-notice tone title>` (compact, used in 17 panel and dialog templates). How should the new page alert relate to it? → A: One component everywhere: the new alert in base replaces `c-panel-notice` too, and all its uses migrate (asked while research ran)
- Q: How should the alert be named inside the panel framework, which `extract_panels_framework-4-template-contract` is pulling out into its own package? → A: Panel-specific components are named `panel-{name}`: framework templates call `<c-panel-alert>`, never `<c-alert>`, and nothing here may contradict spec 4 (given after the spec review)
- Q: What are the components called? → A: `<c-callout>` and `<c-panel-callout>`, not `alert`: `c-callout` is rebuilt with the app look instead of being deleted (given after the spec review)
