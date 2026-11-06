# Formatting helpers

## `format_duration`

Module: `freedom_ls.health.durations`

Renders whole seconds as hours and zero-padded minutes.

```python
format_duration(3720)  # "1h 02m"
```

## `format_score`

Module: `freedom_ls.form_engine.score_display`

Renders a score as `earned / possible`.

```python
format_score(7, 10)  # "7 / 10"
```
