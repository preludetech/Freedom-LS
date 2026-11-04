# Research: reference implementations

Question: how do others format seconds as hours and minutes, and render earned/possible scores?
Sources below are from background knowledge, not fetched this session.

## Duration

- **`divmod` idiom (Python stdlib pattern):** `minutes, _ = divmod(int(seconds) // 60, 60)` style,
  or `hours, rem = divmod(int(seconds), 3600); minutes = rem // 60`. Integer floor division drops
  leftover seconds, which matches the answer: 45s renders `0h 00m`.
  Format with `f"{hours}h {minutes:02d}m"`. Hours are unbounded (no wrap at 24h), unlike
  `datetime.timedelta` string output (`1 day, 2:03:04`).
- **Django `django.utils.timesince.timesince` / `humanize.naturaltime`:** these take two datetimes
  and produce prose ("1 hour, 2 minutes ago"), localised and pluralised. They are the wrong shape
  for a plain seconds-to-`1h 02m` helper, so don't reuse them. They do show the convention of
  flooring to the largest two units and never showing seconds.
  Ref: https://docs.djangoproject.com/en/stable/ref/contrib/humanize/
  and https://docs.djangoproject.com/en/stable/ref/utils/#module-django.utils.timesince
- **`datetime.timedelta`:** `str(timedelta(seconds=3720))` gives `1:02:00`, a fixed format with
  seconds. Not directly usable.

## Score

- **Moodle** shows grades as "earned / possible" (for example "7.00 / 10.00") and a percentage
  separately. A zero maximum grade shows no percentage, since the percentage is a separate field.
  Ref: https://docs.moodle.org/en/Grade_display_types (from memory, not fetched).
- **Canvas** shows "score / points possible". With zero points possible it still shows the raw
  numbers, e.g. "0 / 0", and does not compute a percentage.
  Ref: https://community.canvaslms.com (from memory, not fetched).
- Common pattern: render the fraction as plain text and treat the percentage as a separate
  calculation, so zero `possible` cannot raise `ZeroDivisionError`. This matches the answer
  `0 / 0`: format with `f"{earned} / {possible}"` and no division.

## Takeaways for the spec

- Duration: `hours, rem = divmod(int(seconds), 3600)`, `minutes = rem // 60`,
  `f"{hours}h {minutes:02d}m"`. Seconds floored, so 3720 gives `1h 02m` and 45 gives `0h 00m`.
- Score: plain `f"{earned} / {possible}"`, no division and no guard.
- Open edge not covered by the answers: negative seconds (not decided; out of scope unless asked).

status: ok
