import { atom, read, update } from 'claude-code'
import type { EngineInterface, Register, Timer } from 'claude-code'

import type { AgentRow, Checklist, ChecklistItem, ChecklistSource, ToolRow, TurnInfo } from '../types'

const PANE = 'turn-progress'
const TOOL_PREFIX = 'mcp__turn-progress__'
const TOOL_SET_STEPS = 'mcp__turn-progress__set_steps'
const TOOL_STEP = 'mcp__turn-progress__step'
const MAX_TOOL_ROWS = 50
const ENDED_AGENT_TTL_MS = 30_000
const TICK_MS = 1000
const BAND_BAR_WIDTH = 10
const PANE_BAR_WIDTH = 30
const MAX_CHECKLIST_ROWS = 12

const STEPS_PROMPT = `# Progress steps

The person watches a progress pane that shows the steps of the current task. Before you start any task that has more than one distinct piece — the slices or batches of a plan, the tests in a QA plan, several bugs, files or PR comments to work through, the numbered steps of a slash command you are following, a fan-out of subagents — call \`${TOOL_SET_STEPS}\` with one short label per piece, in order, before doing the first piece. As you begin each piece call \`${TOOL_STEP}\` with \`in_progress\`; when it is done, \`completed\` (or \`failed\`). Marking a step completed starts the next pending one, so one call per piece is enough. If you learn of more pieces midway, call \`${TOOL_SET_STEPS}\` again with the full list and the right \`current\`. A task with one piece needs no steps. Never describe progress in prose instead of calling these tools.`

const turn = atom({ plugin: 'turn-progress', key: 'turn' } as const, null as TurnInfo)
const tools = atom({ plugin: 'turn-progress', key: 'tools' } as const, [] as ToolRow[])
const agents = atom({ plugin: 'turn-progress', key: 'agents' } as const, [] as AgentRow[])
const checklist = atom({ plugin: 'turn-progress', key: 'checklist' } as const, null as Checklist)
const now = atom({ plugin: 'turn-progress', key: 'now' } as const, 0)
const isBandHidden = atom({ plugin: 'turn-progress', key: 'isBandHidden' } as const, false)

const ENDED_STATUSES = new Set(['completed', 'failed', 'killed'])
const ITEM_STATUSES: readonly ChecklistItem['status'][] = ['pending', 'in_progress', 'completed', 'failed']

let ticker: Timer | null = null

function stopTicker(): void {
  ticker?.cancel()
  ticker = null
}

type TodoItem = { content: string; status: string; activeForm: string }
type TaskItem = { subject: string; status: string }

function seconds(from: number, to: number): string {
  const total = Math.max(0, Math.round((to - from) / 1000))
  if (total < 60) return `${total}s`
  const minutes = Math.floor(total / 60)
  return `${minutes}m ${total - minutes * 60}s`
}

function clip(text: string, width: number): string {
  const line = text.replace(/\s+/g, ' ').trim()
  return line.length > width ? `${line.slice(0, Math.max(0, width - 1))}…` : line
}

function isBashRow(row: ToolRow): boolean {
  return row.tool === 'Bash'
}

function isRunning(row: ToolRow): boolean {
  return row.endedAt === undefined
}

function isOpenAgent(row: AgentRow): boolean {
  return row.endedAt === undefined
}

function isEndedItem(item: ChecklistItem): boolean {
  return item.status === 'completed' || item.status === 'failed'
}

function statusOf(status: string): ChecklistItem['status'] {
  return (ITEM_STATUSES as readonly string[]).includes(status) ? (status as ChecklistItem['status']) : 'pending'
}

function checklistOf(items: readonly ChecklistItem[], source: ChecklistSource, title: string | null): Checklist {
  if (items.length === 0) return null
  const active = items.find(item => item.status === 'in_progress')
  return {
    done: items.filter(item => item.status === 'completed').length,
    total: items.length,
    active: active ? active.label : null,
    items: [...items],
    source,
    title,
  }
}

function checklistOfTodos(todos: readonly TodoItem[]): Checklist {
  return checklistOf(
    todos.map(todo => ({
      label: todo.status === 'in_progress' ? todo.activeForm || todo.content : todo.content,
      status: statusOf(todo.status),
    })),
    'todo',
    null,
  )
}

function checklistOfTasks(tasks: readonly TaskItem[]): Checklist {
  return checklistOf(
    tasks.map(task => ({ label: task.subject, status: statusOf(task.status) })),
    'todo',
    null,
  )
}

// The 1-based number of the step the task is on: the in-progress one, else the first pending one.
function currentStep(list: NonNullable<Checklist>): number | null {
  const active = list.items.findIndex(item => item.status === 'in_progress')
  if (active >= 0) return active + 1
  const pending = list.items.findIndex(item => item.status === 'pending')
  return pending >= 0 ? pending + 1 : null
}

function stepLine(list: NonNullable<Checklist>): string {
  const current = currentStep(list)
  if (current === null) {
    const failed = list.items.filter(item => item.status === 'failed').length
    return failed > 0 ? `${list.done} of ${list.total} steps done, ${failed} failed` : `All ${list.total} steps done`
  }
  const label = list.items[current - 1]?.label ?? ''
  return `Step ${current} of ${list.total}: ${label}`
}

function bar(done: number, total: number, width: number): string {
  const filled = total > 0 ? Math.round((done / total) * width) : 0
  return `${'█'.repeat(filled)}${'░'.repeat(Math.max(0, width - filled))}`
}

function glyphOfItem(item: ChecklistItem): string {
  switch (item.status) {
    case 'completed':
      return '✓'
    case 'in_progress':
      return '●'
    case 'failed':
      return '✗'
    default:
      return '○'
  }
}

function stringsOf(value: unknown): string[] | undefined {
  if (!Array.isArray(value)) return undefined
  const labels = value.filter((entry): entry is string => typeof entry === 'string' && entry.trim() !== '')
  return labels.length === value.length ? labels.map(label => label.trim()) : undefined
}

function backgroundTaskIdOf(result: unknown): string | undefined {
  if (typeof result !== 'object' || result === null) return undefined
  const id = (result as { backgroundTaskId?: unknown }).backgroundTaskId
  return typeof id === 'string' ? id : undefined
}

function todosOf(result: unknown): readonly TodoItem[] | undefined {
  if (typeof result !== 'object' || result === null) return undefined
  const todos = (result as { newTodos?: unknown }).newTodos
  return Array.isArray(todos) ? (todos as TodoItem[]) : undefined
}

function tasksOf(result: unknown): readonly TaskItem[] | undefined {
  if (typeof result !== 'object' || result === null) return undefined
  const tasks = (result as { tasks?: unknown }).tasks
  return Array.isArray(tasks) ? (tasks as TaskItem[]) : undefined
}

type Summary = {
  elapsed: string | null
  request: number | null
  activity: string | null
  toolsDone: number
  toolsRunning: number
  agentsOpen: number
  shellsBackground: number
}

function summarise(
  info: TurnInfo,
  toolRows: readonly ToolRow[],
  agentRows: readonly AgentRow[],
  at: number,
): Summary {
  return {
    elapsed: info ? seconds(info.startedAt, at) : null,
    request: info ? info.step : null,
    activity: info ? info.mode ?? info.word : null,
    toolsDone: toolRows.filter(row => !isRunning(row)).length,
    toolsRunning: toolRows.filter(isRunning).length,
    agentsOpen: agentRows.filter(isOpenAgent).length,
    shellsBackground: toolRows.filter(row => row.isBackground === true && isRunning(row)).length,
  }
}

function summaryFacts(summary: Summary): string[] {
  const facts: string[] = []
  if (summary.elapsed !== null) facts.push(`⟳ ${summary.elapsed}`)
  if (summary.request !== null && summary.request > 0) facts.push(`req ${summary.request}`)
  if (summary.activity) facts.push(summary.activity)
  const toolsTotal = summary.toolsDone + summary.toolsRunning
  if (toolsTotal > 0) {
    facts.push(
      summary.toolsRunning > 0
        ? `${toolsTotal} tools (${summary.toolsRunning} running)`
        : `${toolsTotal} tools`,
    )
  }
  if (summary.agentsOpen > 0) {
    facts.push(`${summary.agentsOpen} agent${summary.agentsOpen === 1 ? '' : 's'}`)
  }
  if (summary.shellsBackground > 0) {
    facts.push(`${summary.shellsBackground} shell${summary.shellsBackground === 1 ? '' : 's'} in bg`)
  }
  return facts
}

// Marks the checklist item that stands for an agent, when the fan-out fallback made one.
function endAgentItem(list: Checklist, agentId: string, status: 'completed' | 'failed'): Checklist {
  if (!list || list.source !== 'agents') return list
  return checklistOf(
    list.items.map(item => (item.agentId === agentId && !isEndedItem(item) ? { ...item, status } : item)),
    list.source,
    list.title,
  )
}

export const register: Register = on => {
  on('session.start', async ($, e, next) => {
    await $.command.register({
      name: 'progress',
      description: 'Open the turn progress pane; `clear` drops the declared steps',
      argumentHint: '[clear]',
    })
    await $.tool.register({
      name: 'set_steps',
      description:
        'Declare the steps of the current task for the progress pane, in order, before starting the first one. Replaces any earlier steps. Call again with the full list when the steps change.',
      isDeferred: false,
      inputSchema: {
        type: 'object',
        properties: {
          title: { type: 'string', description: 'What the task is, in a few words' },
          steps: {
            type: 'array',
            items: { type: 'string' },
            minItems: 1,
            description: 'One short label per step, in the order they will be done',
          },
          current: {
            type: 'integer',
            minimum: 0,
            description: '0-based index of the step in progress now; default 0',
          },
        },
        required: ['steps'],
      },
    })
    await $.tool.register({
      name: 'step',
      description:
        'Update one step of the progress pane: in_progress when you begin it, completed or failed when it ends. Completing a step starts the next pending one.',
      isDeferred: false,
      inputSchema: {
        type: 'object',
        properties: {
          index: { type: 'integer', minimum: 0, description: '0-based index of the step' },
          status: { type: 'string', enum: ['in_progress', 'completed', 'failed'] },
          note: { type: 'string', description: 'Optional: a new label for the step' },
        },
        required: ['index', 'status'],
      },
    })
    return next(e)
  })

  on('prompt.compose', async ($, e, next) => {
    const { sections } = await next(e)
    return {
      sections: [...sections, { id: 'turn-progress', scope: 'session', text: STEPS_PROMPT }],
    }
  })

  on('command.run', { command: 'progress' }, async ($, e) => {
    if (e.args.trim() === 'clear') {
      await update($, checklist, () => null)
      return { text: 'Progress steps cleared.' }
    }
    await update($, isBandHidden, () => false)
    const opened = await $.ui.open({ id: PANE, title: 'Progress', focus: true })
    return {
      text: opened.isPlaced
        ? 'Progress pane opened.'
        : `Progress pane is waiting: ${opened.reason}`,
    }
  })

  on('tool.call', { tool: TOOL_SET_STEPS }, async ($, e) => {
    if (e.agentId !== undefined) {
      return { deny: 'Progress steps belong to the main task; a subagent does not declare them.' }
    }
    const steps = stringsOf(e.steps)
    if (!steps || steps.length === 0) {
      return { deny: '`steps` must be a non-empty list of strings.' }
    }
    const current = typeof e.current === 'number' && Number.isInteger(e.current) ? e.current : 0
    if (current < 0 || current >= steps.length) {
      return { deny: `\`current\` must be between 0 and ${steps.length - 1}.` }
    }
    const title = typeof e.title === 'string' && e.title.trim() !== '' ? e.title.trim() : null
    const list = checklistOf(
      steps.map((label, index) => ({
        label,
        status: index < current ? 'completed' : index === current ? 'in_progress' : 'pending',
      })),
      'tool',
      title,
    )
    await update($, checklist, () => list)
    await update($, isBandHidden, () => false)
    return { result: list ? `Steps set. ${stepLine(list)}` : 'Steps set.' }
  })

  on('tool.call', { tool: TOOL_STEP }, async ($, e) => {
    if (e.agentId !== undefined) {
      return { deny: 'Progress steps belong to the main task; a subagent does not update them.' }
    }
    const list = await read($, checklist)
    if (!list) {
      return { deny: `No steps declared; call ${TOOL_SET_STEPS} first.` }
    }
    const index = e.index
    if (typeof index !== 'number' || !Number.isInteger(index) || index < 0 || index >= list.total) {
      return { deny: `\`index\` must be between 0 and ${list.total - 1}.` }
    }
    const status = e.status
    if (status !== 'in_progress' && status !== 'completed' && status !== 'failed') {
      return { deny: '`status` must be in_progress, completed or failed.' }
    }
    const note = typeof e.note === 'string' && e.note.trim() !== '' ? e.note.trim() : undefined

    let items: ChecklistItem[] = list.items.map((item, at) =>
      at === index ? { ...item, status, label: note ?? item.label } : item,
    )
    const hasActive = items.some(item => item.status === 'in_progress')
    if (!hasActive) {
      const nextPending = items.findIndex(item => item.status === 'pending')
      if (nextPending >= 0) {
        items = items.map((item, at) =>
          at === nextPending ? { ...item, status: 'in_progress' as const } : item,
        )
      }
    }
    const updated = checklistOf(items, list.source === 'agents' ? 'tool' : list.source, list.title)
    await update($, checklist, () => updated)
    const verb = status === 'in_progress' ? 'started' : status
    return { result: updated ? `Step ${index + 1} of ${list.total} ${verb}. ${stepLine(updated)}` : 'Step updated.' }
  })

  on('turn.start', async ($, e, next) => {
    const startedAt = await $.clock.now()
    await update($, turn, () => ({
      turnId: e.turnId,
      startedAt,
      step: 0,
      chars: 0,
      mode: null,
      word: null,
    }))
    await update($, tools, list => list.filter(row => row.isBackground === true && isRunning(row)))
    await update($, checklist, list => (list && list.items.every(isEndedItem) ? null : list))
    await update($, now, () => startedAt)

    startTicker($)

    return next(e)
  })

  on('turn.step', async function* ($, e, next) {
    if (e.agentId === undefined) {
      await update($, turn, info => (info ? { ...info, step: e.index + 1 } : info))
    }

    const stream = next(e)
    let chars = 0
    let pending = 0
    for await (const chunk of stream) {
      if (e.agentId === undefined && chunk.kind === 'text') {
        chars += chunk.text.length
        pending += 1
        if (pending >= 40) {
          pending = 0
          const total = chars
          await update($, turn, info => (info ? { ...info, chars: total } : info))
        }
      }
      yield chunk
    }
    if (e.agentId === undefined && pending > 0) {
      const total = chars
      await update($, turn, info => (info ? { ...info, chars: total } : info))
    }
    return await stream.result
  })

  on('turn.complete', async ($, e, next) => {
    if (e.agentId !== undefined) {
      const endedAt = await $.clock.now()
      const agentId = e.agentId
      await update($, agents, list =>
        list.map(row =>
          row.id === agentId && isOpenAgent(row)
            ? { ...row, endedAt, status: e.reason === 'answer' ? 'completed' : e.reason }
            : row,
        ),
      )
      await update($, checklist, list => endAgentItem(list, agentId, e.reason === 'answer' ? 'completed' : 'failed'))
      return next(e)
    }

    await update($, turn, () => null)
    await update($, tools, list => list.filter(row => row.isBackground === true && isRunning(row)))
    const stillOpen = (await read($, agents)).some(isOpenAgent)
    const stillBackground = (await read($, tools)).some(isRunning)
    if (!stillOpen && !stillBackground) stopTicker()

    return next(e)
  })

  on('ui.render', { component: 'Spinner' }, async ($, e, next) => {
    const { mode, word } = e.props
    const info = await read($, turn)
    if (info && (info.mode !== mode || info.word !== word)) {
      await update($, turn, current => (current ? { ...current, mode, word } : current))
    }
    return next(e)
  })

  on('tool.call', async ($, e, next) => {
    const isOwnCall = next.origin.plugin === $.plugin.name || String(e.tool).startsWith(TOOL_PREFIX)
    if (isOwnCall) return next(e)

    const startedAt = await $.clock.now()
    const label =
      e.tool === 'Bash' ? e.description ?? clip(e.command, 60) : String(e.tool)
    const row: ToolRow = {
      id: e.tool_use_id,
      tool: String(e.tool),
      label,
      agentId: e.agentId,
      startedAt,
      isBackground: e.tool === 'Bash' && e.run_in_background === true,
    }
    await update($, tools, list => [...list, row].slice(-MAX_TOOL_ROWS))
    if (e.agentId !== undefined) {
      const agentId = e.agentId
      await update($, agents, list =>
        list.map(agent => (agent.id === agentId ? { ...agent, tools: agent.tools + 1 } : agent)),
      )
    }

    const ran = await next(e)

    const endedAt = await $.clock.now()
    const taskId = ran.deny === undefined ? backgroundTaskIdOf(ran.result) : undefined
    const isBackground = taskId !== undefined
    await update($, tools, list =>
      list.map(one =>
        one.id === row.id
          ? {
              ...one,
              isBackground,
              taskId,
              endedAt: isBackground ? undefined : endedAt,
              isError: ran.isError === true,
            }
          : one,
      ),
    )

    if (ran.deny === undefined && e.agentId === undefined) {
      if (e.tool === 'TodoWrite') {
        const todos = todosOf(ran.result)
        if (todos) await update($, checklist, () => checklistOfTodos(todos))
      } else if (e.tool === 'TaskCreate' || e.tool === 'TaskUpdate' || e.tool === 'TaskList') {
        const listed = await $.tool.call({ tool: 'TaskList' })
        const tasks = listed.deny === undefined ? tasksOf(listed.result) : undefined
        if (tasks) await update($, checklist, () => checklistOfTasks(tasks))
      }
    }

    return ran
  }).catch(($, e, next) => next(e))

  on('agent.spawn', async ($, e, next) => {
    const ran = await next(e)
    if (ran.deny === undefined && ran.agentId !== undefined) {
      const startedAt = await $.clock.now()
      const agentId = ran.agentId
      const row: AgentRow = {
        id: agentId,
        type: e.subagentType,
        description: e.description,
        startedAt,
        status: 'running',
        tools: 0,
        parentId: e.parentAgentId,
      }
      await update($, agents, list => [...list.filter(one => one.id !== row.id), row])
      if (e.parentAgentId === undefined) {
        // With no declared steps, a fan-out of agents is the task's steps.
        await update($, checklist, list => {
          if (list && list.source !== 'agents') return list
          const items = (list?.items ?? []).filter(item => item.agentId !== agentId)
          return checklistOf(
            [...items, { label: e.description, status: 'in_progress', agentId }],
            'agents',
            list?.title ?? null,
          )
        })
      }
      startTicker($)
    }
    return ran
  }).catch(($, e, next) => next(e))

  on('classic.Stop', async ($, e, next) => {
    const inFlight = new Set((e.background_tasks ?? []).map(task => task.id))
    const endedAt = await $.clock.now()
    await update($, tools, list =>
      list.map(row =>
        row.isBackground === true && isRunning(row) && row.taskId !== undefined && !inFlight.has(row.taskId)
          ? { ...row, endedAt }
          : row,
      ),
    )
    return next(e)
  }).catch(($, e, next) => next(e))

  on('ui.render', { component: 'AbovePrompt' }, async ($, e, next) => {
    if (e.props.hasSurvey || (await read($, isBandHidden))) return next(e)

    const info = await read($, turn)
    const toolRows = await read($, tools)
    const agentRows = await read($, agents)
    const list = await read($, checklist)
    const at = await read($, now)
    const summary = summarise(info, toolRows, agentRows, at)
    const hasOpenSteps = list !== null && !list.items.every(isEndedItem)
    const isBusy = info !== null || summary.agentsOpen > 0 || summary.shellsBackground > 0 || hasOpenSteps
    if (!isBusy) return next(e)

    const { Box, Button, Text } = $.ui.resolve(e)
    const facts = summaryFacts(summary)

    return (
      <Box>
        {list && (
          <Box key="step-line">
            <Text wrap="truncate-end">
              <Text bold>{`▶ ${stepLine(list)}`}</Text>
              {'  '}
              <Text color="success">{bar(list.done, list.total, BAND_BAR_WIDTH)}</Text>
              <Text dimColor>{` ${list.done}/${list.total}`}</Text>
              {facts.length > 0 && <Text dimColor>{'   ·  '}</Text>}
            </Text>
          </Box>
        )}
        {facts.length > 0 && (
          <Box key="summary">
            <Text dimColor={list !== null} wrap="truncate-end">
              {facts.map((fact, index) => (
                <Text>
                  {index > 0 && <Text dimColor>{' · '}</Text>}
                  {fact}
                </Text>
              ))}
              {' '}
            </Text>
          </Box>
        )}
        <Button key="hide" label="Hide" onPress={() => update($, isBandHidden, () => true)} />
      </Box>
    )
  })

  on('ui.render', { component: 'Pane', requestId: PANE }, async ($, e) => {
    const { Box, Text } = $.ui.resolve(e)
    const info = await read($, turn)
    const toolRows = await read($, tools)
    const agentRows = await read($, agents)
    const list = await read($, checklist)
    const at = await read($, now)
    const width = Math.max(20, e.props.bodyColumns)
    const summary = summarise(info, toolRows, agentRows, at)

    const shells = toolRows.filter(isBashRow)
    const others = toolRows.filter(row => !isBashRow(row) && isRunning(row))
    const hasAnything =
      list !== null || info !== null || agentRows.length > 0 || shells.length > 0 || others.length > 0

    if (!hasAnything) {
      return (
        <Box key="idle" flexDirection="column">
          <Text dimColor>Idle.</Text>
        </Box>
      )
    }

    const glyphOfAgent = (row: AgentRow): string => {
      if (isOpenAgent(row)) return row.status === 'waiting' || row.status === 'idle' ? '◌' : '●'
      return row.status === 'completed' ? '✓' : '✗'
    }
    const glyphOfTool = (row: ToolRow): string => {
      if (isRunning(row)) return row.isBackground === true ? '◌' : '●'
      return row.isError === true ? '✗' : '✓'
    }
    const facts = summaryFacts(summary).slice(info ? 1 : 0)
    const barWidth = Math.min(PANE_BAR_WIDTH, Math.max(10, width - 12))

    return (
      <Box flexDirection="column">
        {list && (
          <Box key="steps" flexDirection="column">
            {list.title && <Text dimColor>{clip(list.title, width)}</Text>}
            <Text bold wrap="truncate-end">
              {stepLine(list)}
            </Text>
            <Box key="steps-bar">
              <Text>
                <Text color="success">{bar(list.done, list.total, barWidth)}</Text>
                <Text dimColor>{` ${Math.round((list.done / list.total) * 100)}%`}</Text>
              </Text>
            </Box>
            {list.items.slice(0, MAX_CHECKLIST_ROWS).map((item, index) => (
              <Box key={`step-${index}`}>
                <Text
                  dimColor={isEndedItem(item)}
                  bold={item.status === 'in_progress'}
                  color={item.status === 'failed' ? 'error' : undefined}
                  wrap="truncate-end"
                >
                  {`${glyphOfItem(item)} ${clip(item.label, Math.max(10, width - 4))}`}
                </Text>
              </Box>
            ))}
            {list.items.length > MAX_CHECKLIST_ROWS && (
              <Text dimColor>{`… ${list.items.length - MAX_CHECKLIST_ROWS} more`}</Text>
            )}
          </Box>
        )}
        <Box key="header" marginTop={list ? 1 : 0}>
          <Text wrap="truncate-end">
            <Text bold>{info ? `Turn ${summary.elapsed}` : 'Between turns'}</Text>
            {facts.map(fact => (
              <Text>
                <Text dimColor>{' · '}</Text>
                {fact}
              </Text>
            ))}
          </Text>
        </Box>
        {agentRows.length > 0 && (
          <Box key="agents" flexDirection="column" marginTop={1}>
            <Text dimColor>Agents</Text>
            {agentRows.map(row => (
              <Box key={`agent-${row.id}`}>
                <Text dimColor={!isOpenAgent(row)} wrap="truncate-end">
                  {`${glyphOfAgent(row)} ${row.type} `}
                  {clip(row.description, Math.max(10, width - 30))}
                  <Text dimColor>{` ${seconds(row.startedAt, row.endedAt ?? at)} · ${row.tools} tools`}</Text>
                </Text>
              </Box>
            ))}
          </Box>
        )}
        {shells.length > 0 && (
          <Box key="shells" flexDirection="column" marginTop={1}>
            <Text dimColor>Shells</Text>
            {shells.map(row => (
              <Box key={`shell-${row.id}`}>
                <Text dimColor={!isRunning(row)} wrap="truncate-end">
                  {`${glyphOfTool(row)} `}
                  {clip(row.label, Math.max(10, width - 20))}
                  <Text dimColor>{` ${seconds(row.startedAt, row.endedAt ?? at)}`}</Text>
                  {row.isBackground === true && <Text dimColor>{' [bg]'}</Text>}
                </Text>
              </Box>
            ))}
          </Box>
        )}
        {others.length > 0 && (
          <Box key="others" flexDirection="column" marginTop={1}>
            <Text dimColor>Running</Text>
            {others.map(row => (
              <Box key={`tool-${row.id}`}>
                <Text wrap="truncate-end">
                  {`● ${row.label}`}
                  <Text dimColor>{` ${seconds(row.startedAt, at)}`}</Text>
                </Text>
              </Box>
            ))}
          </Box>
        )}
      </Box>
    )
  })
}

function startTicker($: EngineInterface): void {
  if (ticker !== null) return
  ticker = $.clock.every(TICK_MS, async () => {
    const at = await $.clock.now()
    await update($, now, () => at)
    await refreshAgents($, at)
  })
}

async function refreshAgents($: EngineInterface, at: number): Promise<void> {
  const rows = await read($, agents)
  if (rows.length === 0) return
  const live = new Map((await $.agent.list()).map(info => [info.id, info.status] as const))
  const ended: { id: string; status: string }[] = []
  await update($, agents, list =>
    list
      .map(row => {
        const status = live.get(row.id)
        if (status === undefined || !isOpenAgent(row)) return row
        if (ENDED_STATUSES.has(status)) {
          ended.push({ id: row.id, status })
          return { ...row, status, endedAt: at }
        }
        return { ...row, status }
      })
      .filter(row => isOpenAgent(row) || (row.endedAt ?? at) + ENDED_AGENT_TTL_MS > at),
  )
  for (const { id, status } of ended) {
    await update($, checklist, list => endAgentItem(list, id, status === 'completed' ? 'completed' : 'failed'))
  }
}
