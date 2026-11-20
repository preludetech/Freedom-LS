# Answers: sacaa-compliance-2-shuffle

Asked by `/sdd:start` before the spec was written.

- Q: How should a keep-together group be modelled? → A: A `group: <name>` string key on each member content block and question; a contiguous run with the same key is one atom. No separate group model. (asked up front)
- Q: May a keep-together group exist on a quiz whose within-page shuffle is off? → A: Allowed, since question pools will draw groups as units on unshuffled pages too. Nested groups stay a validation error. (asked up front)
- Q: Can a page file override the form-level shuffle knobs? → A: No. The three knobs are form-level only, in the form front matter. (asked up front)
- Q: With shuffle_pages on, can an author pin a page so it doesn't move? → A: No page lock. All pages shuffle; instructions go in the form body, or the author leaves shuffle_pages off. (asked up front)
