# QA test data

**Missing data**: spawn **`sdd:qa-data-helper`** via the `Agent` tool (a paginator with too few
rows, a panel with no instance of the model, a flow with no user, group or course). Tell it the exact
shape you need: entity counts, relationships, which fixtures. It owns the data-creation
conventions, so do not hand-roll data scripts. Wait for it to confirm, then re-attempt the test.

**Blocking data**: a stale registration, an orphaned join row, a stray role grant, a password an
earlier run changed. Clear it, cheapest option first. Rungs 2 and 3 run the commands configured under
`## QA Dev Data` in `.claude/sdd/config.md`, with the literal values substituted.

1. Delegate the delete to `sdd:qa-data-helper`, naming the records by pk.
2. Run `Content reset`, then the test plan's seed list. It clears content and leaves users,
   organisations and role grants intact.
3. Full wipe. Run `DB drop`, `DB create`, `Migrate`, then the test plan's own `§0` seed list.

A rung whose config value is blank does not exist for this project. Skip it and try the next. If no
rung past 1 is configured and rung 1 cannot clear the blockage, treat the scenario as impossible to
set up: mark the test PARTIAL and file the Step 15 category-2 item naming the missing config key.

**If a command is refused**, use the project's allow-listed scripts. File a `(user)` item only when
a command is refused *and* has no allow-listed equivalent, naming the command and why you could
not issue it.

**This command never makes data itself.** It runs no ORM or SQL, no shell or fixture load and no
management command of its own. Every data change goes through `sdd:qa-data-helper` or a
`## QA Dev Data` command. Append one record per change:

```json
{"type": "data_change", "via": "sdd:qa-data-helper or the key name", "what": "…", "files": ["…"]}
```

`files` lists the paths the helper reported under **Files written** (empty when none). Those files
(factories, fixtures, data commands) are kept: Step 17 commits them. Never ask the user whether to keep or delete
them, and never file a `todo.md` item about them.

**Only** mark a test PARTIAL / skipped for one of two reasons: `sdd:qa-data-helper` reports the
scenario is impossible to set up, or the ladder above ran out of configured rungs.
