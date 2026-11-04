# Research: ux_patterns (durations and fraction scores)

Note: written from general knowledge; the URLs below are well-known references and were not fetched in this run.

## Durations
- Compact `Xh YYm` is common for short spans (video players, fitness and transit apps). Zero-padding minutes
  (`1h 02m`) keeps columns aligned and avoids `1h 2m` reading as 1.2 hours. Hours are not padded.
- Under one minute is usually shown as `0m`, `<1m`, or seconds (`45s`). The decided `0h 00m` is consistent
  in shape, but it can read as "nothing happened" in a progress table; it is acceptable for a uniform column.
- Clock style `1:02` is ambiguous (h:mm vs m:ss), so labelled units are clearer for learners.
- Accessibility: screen readers tend to read `1h 02m` as "1 h 02 m" or "one H zero two M". The robust fix is a
  visible compact string plus an accessible full-text label, e.g. `<span aria-label="1 hour 2 minutes">1h 02m</span>`,
  or `<time datetime="PT1H2M">`. `<time>` with an ISO 8601 duration is machine-readable but is not reliably
  announced, so pair it with an aria-label or visually-hidden text. (WCAG 1.3.1 Info and Relationships.)
  That belongs to a future template. The helper only returns the visible string.

## Fraction scores
- `7 / 10` (spaced) is easier to read and wraps cleanly. `7/10` is tighter and fine in dense tables.
  Pick one and use it everywhere. The decided `7 / 10` matches.
- Percentages summarise at a glance and compare across forms with different totals, but hide the raw count.
  Learners and educators both usually want the fraction (what was earned), with a percentage beside it where
  comparison matters. Show both rather than choosing one.
- `possible == 0` means no marks exist, so any percentage is undefined. Rendering `0 / 0` avoids a divide
  by zero, but a percentage view would need a separate "n/a" case. This is out of scope for the helper.
- Accessibility: the slash is commonly read as "7 slash 10" or "7 divided by 10". Prefer an accessible label
  such as `aria-label="7 out of 10"`, or visually hidden text. Don't rely on colour alone to show pass or fail
  (WCAG 1.4.1).

## Takeaway for the spec
Both helpers return plain visible strings. Any screen-reader wording ("1 hour 2 minutes", "7 out of 10") is a
presentation concern for later templates, not for these helpers. A note in the docstrings is enough.

## References
- https://www.w3.org/WAI/WCAG22/Understanding/info-and-relationships.html
- https://www.w3.org/WAI/WCAG22/Understanding/use-of-color.html
- https://developer.mozilla.org/en-US/docs/Web/HTML/Element/time
- https://developer.mozilla.org/en-US/docs/Web/Accessibility/ARIA/Attributes/aria-label

status: ok
