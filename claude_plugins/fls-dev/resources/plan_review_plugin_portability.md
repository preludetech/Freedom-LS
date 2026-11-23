# Plan review brief: generic plugins stay generic

Inputs from the caller: `<plan-path>`, `<spec-path>`, `<output-path>`.

Read the spec and the plan in full. List every step that creates or edits a file under
`claude_plugins/sdd`, `claude_plugins/django-stack` or `claude_plugins/productivity`.

Flag a step when the text it puts into one of those plugins:

- names FreedomLS, an FLS app, path or value (any of the three plugins);
- names a test runner, test command, language tool, framework, CI service or another plugin's
  path (`claude_plugins/sdd` only). `sdd` reaches those through a hook key in
  `.claude/sdd/config.md`. Running tests is its `Test runner` hook, and how tests are selected,
  run, recorded or sent to CI belongs in `claude_plugins/django-stack`.

Write `<output-path>` in a single `Write`. Its first line is `callout: Plugin portability`. Then
one line per flagged step,
`<plan step>: <plugin file>: <what it would name>: clear fix: <the hook key, config value or plugin that should carry it>`,
then the `status:` footer. No flagged step is `status: ok` with `no portability concern`.
