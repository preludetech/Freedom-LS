# Claude Code Plugin System - Research Notes

Date: 2026-03-31

## Overview

Claude Code plugins are extensions that enhance Claude Code with custom slash commands, specialized agents, skills, hooks, and MCP (Model Context Protocol) servers. Plugins can be shared across projects and teams.

The plugin system uses **convention-over-configuration** with auto-discovery of components from standardized directory locations.

---

## Plugin Directory Structure

Every plugin follows this layout:

```
plugin-name/
├── .claude-plugin/
│   └── plugin.json          # REQUIRED: Plugin manifest
├── commands/                 # Slash commands (.md files)
├── agents/                   # Subagent definitions (.md files)
├── skills/                   # Agent skills (subdirectories with SKILL.md)
│   └── skill-name/
│       ├── SKILL.md          # Required for each skill
│       ├── references/       # Detailed docs loaded on demand
│       ├── examples/         # Working code examples
│       └── scripts/          # Utility scripts
├── hooks/
│   └── hooks.json            # Event handler configuration
├── .mcp.json                 # MCP server definitions (optional)
├── scripts/                  # Shared helper scripts/utilities
└── README.md                 # Plugin documentation
```

### Critical Rules

1. The `plugin.json` manifest MUST be in `.claude-plugin/` directory
2. All component directories (commands, agents, skills, hooks) MUST be at plugin root level, NOT nested inside `.claude-plugin/`
3. Only create directories for components the plugin actually uses
4. Use **kebab-case** for all directory and file names

---

## Manifest Format (plugin.json)

Located at `.claude-plugin/plugin.json`.

### Only Required Field

```json
{
  "name": "plugin-name"
}
```

Name must be kebab-case, lowercase with hyphens, unique across installed plugins.

### Full Manifest Example

```json
{
  "name": "plugin-name",
  "version": "1.0.0",
  "description": "Brief explanation of plugin purpose",
  "author": {
    "name": "Author Name",
    "email": "author@example.com",
    "url": "https://example.com"
  },
  "homepage": "https://docs.example.com",
  "repository": "https://github.com/user/plugin-name",
  "license": "MIT",
  "keywords": ["testing", "automation"]
}
```

### Optional Component Path Overrides

Custom paths **supplement** defaults (they don't replace them):

```json
{
  "name": "plugin-name",
  "commands": "./custom-commands",
  "agents": ["./agents", "./specialized-agents"],
  "hooks": "./config/hooks.json",
  "mcpServers": "./.mcp.json"
}
```

Paths must be relative and start with `./`.

### Real-World Examples from Official Plugins

**code-review:**
```json
{
  "name": "code-review",
  "description": "Automated code review for pull requests using multiple specialized agents with confidence-based scoring",
  "version": "1.0.0",
  "author": {
    "name": "Boris Cherny",
    "email": "boris@anthropic.com"
  }
}
```

**hookify:**
```json
{
  "name": "hookify",
  "version": "0.1.0",
  "description": "Easily create hooks to prevent unwanted behaviors by analyzing conversation patterns",
  "author": {
    "name": "Daisy Hollman",
    "email": "daisy@anthropic.com"
  }
}
```

---

## What Can Be Included in a Plugin

### 1. Skills

Skills are modular packages of specialized knowledge that auto-activate based on context.

**Location:** `skills/skill-name/SKILL.md`

**SKILL.md format:**
```markdown
---
name: Skill Name
description: This skill should be used when the user asks to "specific phrase 1", "specific phrase 2"...
version: 0.1.0
---

Skill instructions and guidance in imperative/infinitive form...
```

**Progressive disclosure system:**
1. **Metadata** (name + description) - Always in context (~100 words)
2. **SKILL.md body** - Loaded when skill triggers (<5k words, ideally 1,500-2,000)
3. **Bundled resources** (references/, examples/, scripts/) - Loaded as needed

**Key points:**
- Description MUST use third person: "This skill should be used when..."
- Include specific trigger phrases in quotes
- Body uses imperative/infinitive form, not second person
- Claude auto-activates skills based on task context matching the description

### 2. Commands (Slash Commands)

Frequently-used prompts defined as Markdown files.

**Location:** `commands/*.md`

**Format:**
```markdown
---
description: Brief description shown in /help
allowed-tools: Read, Write, Edit, Bash(git:*)
model: sonnet
argument-hint: [pr-number] [priority]
disable-model-invocation: false
---

Command instructions for Claude (written as directives TO Claude)...
Use $ARGUMENTS for all args, or $1, $2, $3 for positional args.
Use @filename for file references.
```

**Frontmatter fields:**
- `description` - Brief description shown in `/help`
- `allowed-tools` - Which tools command can use (string or array)
- `model` - sonnet/opus/haiku/inherit
- `argument-hint` - Documents expected arguments for autocomplete
- `disable-model-invocation` - Prevents programmatic invocation (boolean)

**Dynamic features:**
- `$ARGUMENTS` - All arguments as single string
- `$1`, `$2`, `$3` - Positional arguments
- `@filepath` - Include file contents
- `` !`bash command` `` - Execute bash for dynamic context

**Commands are namespaced:** `/command-name (plugin:plugin-name)`

### 3. Agents (Subagents)

Autonomous subprocesses for complex multi-step tasks.

**Location:** `agents/*.md`

**Format:**
```markdown
---
name: agent-identifier
description: Use this agent when [conditions]. Examples:

<example>
Context: [Situation]
user: "[Request]"
assistant: "[Response]"
<commentary>
[Why this agent triggers]
</commentary>
</example>

model: inherit
color: blue
tools: ["Read", "Write", "Grep"]
---

You are [agent role]...

**Your Core Responsibilities:**
1. ...
```

**Required frontmatter fields:**
- `name` - Lowercase, hyphens, 3-50 chars
- `description` - Triggering conditions with `<example>` blocks (2-4 examples)
- `model` - inherit/sonnet/opus/haiku
- `color` - blue/cyan/green/yellow/magenta/red

**Optional:**
- `tools` - Array of tool names (defaults to all tools if omitted)

### 4. Hooks (Event Handlers)

Event-driven automation scripts that execute in response to Claude Code events.

**Location:** `hooks/hooks.json`

**Plugin hooks.json format (note the wrapper):**
```json
{
  "description": "Optional description",
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Write|Edit",
        "hooks": [
          {
            "type": "command",
            "command": "bash ${CLAUDE_PLUGIN_ROOT}/hooks/scripts/validate.sh",
            "timeout": 30
          }
        ]
      }
    ]
  }
}
```

**Real-world example (security-guidance plugin):**
```json
{
  "description": "Security reminder hook that warns about potential security issues when editing files",
  "hooks": {
    "PreToolUse": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "python3 ${CLAUDE_PLUGIN_ROOT}/hooks/security_reminder_hook.py"
          }
        ],
        "matcher": "Edit|Write|MultiEdit"
      }
    ]
  }
}
```

**Hook types:**
- **Prompt-based** (recommended) - LLM-driven decision making
- **Command** - Bash scripts for deterministic checks

**Available hook events:**

| Event | When | Use For |
|-------|------|---------|
| PreToolUse | Before tool runs | Validation, modification, blocking |
| PostToolUse | After tool completes | Feedback, logging |
| Stop | Main agent stopping | Completeness verification |
| SubagentStop | Subagent stopping | Task validation |
| SessionStart | Session begins | Context loading, env setup |
| SessionEnd | Session ends | Cleanup, logging |
| UserPromptSubmit | User submits prompt | Context injection, validation |
| PreCompact | Before context compaction | Preserve critical info |
| Notification | Notification sent | Reactions, logging |

**Matchers:** Exact match, pipe-separated (`Write|Edit`), wildcard (`*`), regex (`mcp__.*__delete.*`)

**Important:** Hooks load at session start. Changes require restarting Claude Code.

### 5. MCP Servers (External Tool Integration)

Model Context Protocol servers for integrating external services.

**Location:** `.mcp.json` at plugin root OR inline `mcpServers` in plugin.json

**Server types:**
- **stdio** - Local process (command + args)
- **SSE** - Server-Sent Events with OAuth (url)
- **HTTP** - REST API with token auth (url + headers)
- **WebSocket** - Real-time bidirectional (wss:// url)

**Example .mcp.json:**
```json
{
  "database-tools": {
    "command": "${CLAUDE_PLUGIN_ROOT}/servers/db-server",
    "args": ["--config", "${CLAUDE_PLUGIN_ROOT}/config.json"],
    "env": {
      "DB_URL": "${DB_URL}"
    }
  }
}
```

**Tool naming convention:** `mcp__plugin_<plugin-name>_<server-name>__<tool-name>`

### 6. Settings (Per-Project Configuration)

User-configurable state stored in `.claude/plugin-name.local.md` files.

**Format:** YAML frontmatter + markdown body

```markdown
---
enabled: true
strict_mode: false
max_retries: 3
---

# Additional Context
Instructions or notes for the plugin.
```

- Should be in `.gitignore`
- Read from hooks, commands, and agents via bash parsing
- Changes require Claude Code restart

---

## How Plugins Are Installed/Referenced

### Installation Methods

1. **Marketplace install:**
   ```
   /plugin install plugin-name@claude-code-marketplace
   ```

2. **Local development (--plugin-dir flag):**
   ```bash
   claude --plugin-dir /path/to/plugin
   # or
   cc --plugin-dir /path/to/plugin
   ```

3. **Project settings** (`.claude/settings.json`):
   Configure plugins in the project's settings file.

### Auto-Discovery Mechanism

When a plugin is enabled, Claude Code:
1. Reads `.claude-plugin/plugin.json`
2. Scans `commands/` for `.md` files
3. Scans `agents/` for `.md` files
4. Scans `skills/` for subdirectories containing `SKILL.md`
5. Loads `hooks/hooks.json` or hook config from manifest
6. Loads `.mcp.json` or MCP config from manifest

No restart required for installation, but hook changes need a session restart.

---

## Portable Path References

### ${CLAUDE_PLUGIN_ROOT}

All intra-plugin paths MUST use `${CLAUDE_PLUGIN_ROOT}`:

```json
{
  "command": "bash ${CLAUDE_PLUGIN_ROOT}/scripts/validate.sh"
}
```

Available in:
- Hook command paths
- MCP server command arguments
- Script execution references
- Environment variable in bash scripts

**Never use:** Hardcoded absolute paths, relative paths from working directory, or home directory shortcuts.

### Other Environment Variables

- `$CLAUDE_PROJECT_DIR` - Project root path
- `$CLAUDE_ENV_FILE` - SessionStart only: persist env vars here
- `$CLAUDE_CODE_REMOTE` - Set if running in remote context

---

## Validation Process

### Plugin Validator Agent

The plugin-dev toolkit includes a `plugin-validator` agent that performs comprehensive validation:

1. **Manifest validation** - JSON syntax, required `name` field, kebab-case format, semver version
2. **Directory structure** - Components at root level, correct locations
3. **Command validation** - YAML frontmatter present, `description` field exists
4. **Agent validation** - Frontmatter with name/description/model/color, `<example>` blocks in description, valid model and color values
5. **Skill validation** - `SKILL.md` exists with frontmatter containing `name` and `description`
6. **Hook validation** - Valid JSON, valid event names, hook type is `command` or `prompt`, scripts use `${CLAUDE_PLUGIN_ROOT}`
7. **MCP validation** - Valid JSON, correct server configuration fields
8. **Security checks** - No hardcoded credentials, HTTPS/WSS usage, no secrets in examples
9. **File organization** - README exists, no unnecessary files

### Utility Scripts (from plugin-dev)

- `validate-hook-schema.sh` - Validate hooks.json structure
- `test-hook.sh` - Test hooks with sample input
- `hook-linter.sh` - Check hook scripts for issues
- `validate-agent.sh` - Validate agent file structure
- `validate-settings.sh` - Validate settings file structure
- `parse-frontmatter.sh` - Extract frontmatter fields

### Manual Testing

```bash
# Test with debug mode
claude --debug

# Test with local plugin
cc --plugin-dir /path/to/plugin

# View loaded hooks
/hooks

# View MCP servers
/mcp
```

---

## Limitations and Constraints

1. **Hooks load at session start** - Changes to hooks require restarting Claude Code. Cannot hot-swap hooks during a session.
2. **No interactive hooks** - Hooks cannot prompt the user for input during execution.
3. **Hook parallelism** - All matching hooks run in parallel. They don't see each other's output and ordering is non-deterministic.
4. **Hook timeouts** - Command hooks default to 60s, prompt hooks to 30s.
5. **Settings changes require restart** - `.claude/plugin-name.local.md` changes are only picked up on session start.
6. **Naming constraints** - Plugin names must be kebab-case. Agent names must be 3-50 chars, lowercase with hyphens only.
7. **File format constraints** - Commands are `.md` files only. Skills require `SKILL.md` specifically (not README.md).
8. **Custom paths supplement, don't replace** - Component paths in plugin.json add to default directories, they don't override them.
9. **No hot-reload for any component** - All plugin component changes require a new Claude Code session.
10. **SKILL.md size** - Should ideally be 1,500-2,000 words to avoid bloating context. Detailed content should go in `references/`.

---

## Plugin Patterns

### Minimal Plugin (single command)

```
my-plugin/
├── .claude-plugin/
│   └── plugin.json    # {"name": "my-plugin"}
└── commands/
    └── hello.md
```

### Skill-Only Plugin

```
my-plugin/
├── .claude-plugin/
│   └── plugin.json
└── skills/
    ├── skill-one/
    │   └── SKILL.md
    └── skill-two/
        └── SKILL.md
```

### Full-Featured Plugin

```
my-plugin/
├── .claude-plugin/
│   └── plugin.json
├── commands/
├── agents/
├── skills/
├── hooks/
│   ├── hooks.json
│   └── scripts/
├── .mcp.json
├── scripts/
└── README.md
```

---

## Guided Plugin Creation

The `plugin-dev` toolkit provides a `/plugin-dev:create-plugin` command that guides through an 8-phase process:

1. **Discovery** - Understand plugin purpose and requirements
2. **Component Planning** - Determine needed skills, commands, agents, hooks, MCP
3. **Detailed Design** - Specify each component, resolve ambiguities
4. **Structure Creation** - Set up directories and manifest
5. **Component Implementation** - Create each component
6. **Validation** - Run plugin-validator and checks
7. **Testing** - Verify plugin works in Claude Code
8. **Documentation** - Finalize README

---

## Official Plugins (Examples to Study)

All at: `https://github.com/anthropics/claude-code/tree/main/plugins/`

| Plugin | Components | Good Example Of |
|--------|-----------|-----------------|
| code-review | 1 command, 5 agents | Multi-agent workflow |
| commit-commands | 3 commands | Git workflow commands |
| security-guidance | 1 hook | PreToolUse hook with Python |
| hookify | 4 commands, 1 agent, 1 skill | Full-featured plugin |
| feature-dev | 1 command, 3 agents | Guided workflow command |
| plugin-dev | 1 command, 3 agents, 7 skills | Comprehensive toolkit |
| explanatory-output-style | 1 hook | SessionStart hook |
| ralph-wiggum | 2 commands, 1 hook | Loop/iteration pattern with settings |
| frontend-design | 1 skill | Skill-only plugin |

---

## Reference URLs

- **Official Plugin Docs:** https://docs.claude.com/en/docs/claude-code/plugins
- **Official Hooks Docs:** https://docs.claude.com/en/docs/claude-code/hooks
- **Official MCP Docs:** https://docs.claude.com/en/docs/claude-code/mcp
- **MCP Protocol:** https://modelcontextprotocol.io/
- **Plugin-dev toolkit README:** https://github.com/anthropics/claude-code/tree/main/plugins/plugin-dev
- **All official plugins:** https://github.com/anthropics/claude-code/tree/main/plugins
- **Claude Code Overview:** https://docs.claude.com/en/docs/claude-code/overview
