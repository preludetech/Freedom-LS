# productivity plugin

Generic writing and working skills for Claude Code: a skill that answers a question and changes
nothing, a skill that strips AI tells from prose, and a skill for writing the documents agents read.
It is independent and carries nothing specific to a project.

Manifest name: `productivity`. Namespace: `/productivity:*`, `Skill(productivity:*)`.

## What's inside (counted from disk)

### Skills (3)

| Skill | Invoked by | What it does |
|---|---|---|
| `answer` | user only, `/productivity:answer <question>` | Answers the question and does nothing else: no edits, no tests, no side effects |
| `unslop` | by description | Cuts AI tells from any writing |
| `writing-for-agents` | by description | Guides writing skills, `CLAUDE.md` files and other documents an agent consumes; `SKILL-MECHANICS.md` covers skill frontmatter, invocation choice and router skills |

### Commands (1)

`init` wires this plugin into a project.

### Resources (1)

`launcher_editing` is the procedure for editing `claude.sh` (with `<MAY_CREATE>` false:
`productivity` adds its line to an existing launcher and never creates one).

Depends on no other plugin.

## Loading

Run `/productivity:init`. It merges the `Skill(productivity:*)` permission and the
`"productivity": true` `enabledPlugins` key into `.claude/settings.json`, and adds this plugin's
`--plugin-dir` line to the project's `claude.sh`.
