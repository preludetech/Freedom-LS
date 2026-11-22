# Icon test failures inherited from main

The final full run of this branch (19,844 collected: 19,831 passed, 10 failed, 3 skipped) failed
only in icon tests. The failures come from `main` (at `bf62c572f`), not from this branch: this
branch changes nothing under `freedom_ls/icons/`, `scripts/` or `tests/test_generate_icon_subset.py`.

## Cause

`freedom_ls/icons/data/` (the bundled icon data) is out of date with `freedom_ls/icons/mappings.py`.
`49674d13d [batch 3] c-audio-clip plays and pauses its own audio` (content-widget-longer-audio)
added `media_play` and `media_pause` to every icon set's mapping. The bundled data was last
regenerated before that mapping landed, so the new glyphs are missing from it. The check reports:

```
Mapping 'media_pause' -> 'pause' not found in 'heroicons' Iconify JSON   (icons.E003)
```

`uv run python scripts/generate_icon_subset.py --check` confirms it: `heroicons/icons.json`,
`lucide/icons.json`, `tabler/icons.json` and `manifest.json` under `freedom_ls/icons/data/` all
differ from a fresh build. The installed `@iconify-json` packages match `package-lock.json`
(heroicons 1.2.3, lucide 1.2.101, tabler 1.2.33), so the committed data is what is stale, not the
local install.

## Failed tests

```
freedom_ls/icons/tests/invariants/test_bundled_data.py::TestBundledSet::test_icons_plus_missing_glyphs_equal_the_required_glyphs[heroicons]
freedom_ls/icons/tests/invariants/test_bundled_data.py::TestBundledSet::test_icons_plus_missing_glyphs_equal_the_required_glyphs[lucide]
freedom_ls/icons/tests/invariants/test_bundled_data.py::TestBundledSet::test_icons_plus_missing_glyphs_equal_the_required_glyphs[tabler]
freedom_ls/icons/tests/test_checks.py::TestCheckMappingValuesExist::test_heroicons_mappings_valid
freedom_ls/icons/tests/test_checks.py::TestCheckMappingValuesExist::test_valid_config_no_errors
freedom_ls/icons/tests/test_checks.py::TestCheckMappingValuesExist::test_variant_suffixed_names_are_validated
freedom_ls/icons/tests/test_checks.py::test_default_settings_produce_no_icons_check_output
tests/test_generate_icon_subset.py::TestCommittedDataMatchesUpstream::test_committed_icons_equal_the_subset_of_installed_upstream[heroicons]
tests/test_generate_icon_subset.py::TestCommittedDataMatchesUpstream::test_committed_icons_equal_the_subset_of_installed_upstream[lucide]
tests/test_generate_icon_subset.py::TestCommittedDataMatchesUpstream::test_committed_icons_equal_the_subset_of_installed_upstream[tabler]
```

## Fix on main

1. On `main`, run `npm ci` so `node_modules/@iconify-json` matches `package-lock.json`.
2. Run `uv run python scripts/generate_icon_subset.py` to regenerate `freedom_ls/icons/data/`.
3. Check `uv run python scripts/generate_icon_subset.py --check` reports no differences.
4. Re-run the ten tests above by node ID, then commit the regenerated data.

Once `main` has the fix, rebasing this branch picks it up.
