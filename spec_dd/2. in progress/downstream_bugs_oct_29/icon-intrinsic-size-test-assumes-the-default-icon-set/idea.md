# Idea: `test_svg_has_intrinsic_width_and_height` hardcodes heroicons' 24px, so it fails in any project that configures a different icon set

## The bug

Source: `uv run pytest` in this downstream project, integrating the `error-pages` spec
(FLS `3b6d5f09`). One test that had never run before started failing:

```
FAILED submodules/Freedom-LS/freedom_ls/icons/tests/test_renderer.py
       ::TestRenderIcon::test_svg_has_intrinsic_width_and_height
       assert 'width="24"' in '<svg xmlns="..." viewBox="0 0 256 256" width="256" height="256" ...>'
```

`error-pages` added intrinsic dimensions to rendered icons: `freedom_ls.icons.backend.build_svg`
now emits the icon set's own `width`/`height` alongside the existing `viewBox`, so an icon stays
small when the stylesheet has not loaded. The upgrade notes describe it exactly that way — "the
icon set's intrinsic dimensions".

The test added with it asserts a literal instead:

```python
def test_svg_has_intrinsic_width_and_height(self) -> None:
    """Without a stylesheet, only the width/height attributes bound the icon."""
    result = render_icon("success")
    assert 'width="24"' in result
    assert 'height="24"' in result
```

`24` is heroicons' intrinsic size, and heroicons is the default of `FREEDOM_LS_ICON_SET`
(`freedom_ls/icons/config.py:12`). The test never pins that setting, so it silently depends on the
ambient configuration. This project sets `FREEDOM_LS_ICON_SET = "phosphor"`
(`config/customisation.py:42`); phosphor icons are 256x256, so the render is correct and the
assertion fails.

The feature is not at fault and neither is the configuration. The very next test in the same class
demonstrates the pattern this one should have used:

```python
@override_settings(FREEDOM_LS_ICON_SET="heroicons")
def test_intrinsic_size_tracks_the_icon_sets_own_dimensions(
    self, monkeypatch: pytest.MonkeyPatch
) -> None:
    real_data = load_iconify_data("heroicons")
    fake_heroicons = {**real_data, "width": 20, "height": 20}
    ...
```

That one pins the set *and* fakes its dimensions, so it asserts the real invariant — the emitted
size tracks whatever the active set declares — without depending on any particular set. Its
neighbour asserts a constant that is only true for one of them.

This is a portability defect rather than a correctness one: the behaviour under test is right in
every project, but the test only passes in projects that left `FREEDOM_LS_ICON_SET` at its default.
Every downstream that picks a different set — which is the setting's entire purpose — inherits a
red suite on a green codebase. It is also not caught by FLS's own CI, because FLS runs on its own
default.

## Expected fix

Make the assertion track the active set instead of a literal, so the test says what its docstring
means. Either read the dimensions from the loaded set:

```python
def test_svg_has_intrinsic_width_and_height(self) -> None:
    """Without a stylesheet, only the width/height attributes bound the icon."""
    data = load_iconify_data(config.FREEDOM_LS_ICON_SET)
    result = render_icon("success")
    assert f'width="{data["width"]}"' in result
    assert f'height="{data["height"]}"' in result
```

or pin the set the literal belongs to, matching the sibling test:

```python
@override_settings(FREEDOM_LS_ICON_SET="heroicons")
def test_svg_has_intrinsic_width_and_height(self) -> None:
    ...
```

The first is the better of the two — it keeps the test meaningful for whichever set a project
actually runs, rather than only proving the invariant under one. A regex assertion
(`re.search(r'width="\d+"', result)`) would also pass everywhere but would stop catching a
missing-dimension regression's most likely shape, so it is the weakest option.

Marking the test `fls_internal` would unblock downstreams but is the wrong call here: the
behaviour is portable, only the assertion is not, and the marker exists for tests that genuinely
assume FLS's own settings.

## Downstream workaround in place

`pyproject.toml` deselects the test by node id, alongside the three
`test_settings_defaults.py` deselects recorded in
`spec_dd/for_freedom_ls/settings-defaults-tests-assert-against-the-downstream-config-package/`.
Remove the deselect once the assertion is pinned upstream.
