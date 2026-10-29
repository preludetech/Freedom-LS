# Idea: `test_sidebar_lists_the_six_sections_each_with_an_icon` assumes `MESSAGING_ENABLED = True`, so it fails in any project that leaves messaging at its default

## The bug

Source: `uv run pytest` in this downstream project, integrating the
`user-communication-4-direct-messaging` spec (FLS `1803e100`). With messaging left at its
default, one test fails:

```
FAILED submodules/Freedom-LS/freedom_ls/educator_interface/tests/test_sidebar.py
       ::test_sidebar_lists_the_six_sections_each_with_an_icon
```

The test asserts the educator sidebar's links are exactly:

```python
assert [link.text_content().strip() for link in links] == [
    "Dashboard",
    "Cohorts",
    "Learners",
    "Courses",
    "Messages",
    "Members",
]
```

The "Messages" entry only renders when `MESSAGING_ENABLED` is true
(`freedom_ls/educator_interface/views.py`, which checks `comms_config.MESSAGING_ENABLED`). The
setting defaults to `False` (`freedom_ls/comms/config.py`, and `config/settings_base.py`), and
only FLS's own `config/settings_dev.py` turns it on. The test never pins the setting, so it
passes in FLS's dev configuration and fails in any downstream that keeps the documented default.
The upgrade notes for this spec describe `MESSAGING_ENABLED` as optional and off by default,
so leaving it off is a supported configuration. FLS's CI does not catch this because it runs on
FLS's own dev settings.

The sidebar is correct in both configurations; only the test is wrong.

## Expected fix

Pin the setting the assertion depends on, and cover the other branch too:

```python
@pytest.mark.django_db
@override_settings(MESSAGING_ENABLED=True)
def test_sidebar_lists_the_six_sections_each_with_an_icon(...): ...


@pytest.mark.django_db
@override_settings(MESSAGING_ENABLED=False)
def test_sidebar_omits_messages_when_messaging_is_off(...): ...
```

The `sidebar` fixture renders the page, so the override has to apply before the fixture runs
(use the `settings` fixture inside a wrapping fixture, or parametrise the fixture), not only on
the test function.

Marking the test `fls_internal` would be the wrong call: the behaviour is portable, only the
test's dependency on ambient settings is not.

Also worth checking: the three `TestMessagesButton` tests in `freedom_ls/comms/tests/test_bell_tag.py`
render the real `partials/header_bar.html`, so they fail in any downstream that shadows that
template without `{% messages_button %}`. That is a legitimate drift signal rather than a bug,
but the upgrade notes could say so explicitly.

## Downstream workaround in place

None. This project turned messaging on (`MESSAGING_ENABLED = True` in
`config/settings_base.py`), so the test passes here. A downstream that keeps messaging off still
hits the failure.
