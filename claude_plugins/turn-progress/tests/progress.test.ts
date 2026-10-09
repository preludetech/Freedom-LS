import { expect, mock, test } from 'claude-code/testing'
import type { On } from 'claude-code'

import type { AgentRow, Checklist, ToolRow, TurnInfo } from '../types'

const PLUGIN = 'turn-progress'
const SET_STEPS = 'mcp__turn-progress__set_steps'
const STEP = 'mcp__turn-progress__step'

const BAND = {
  plugin: PLUGIN,
  component: 'AbovePrompt',
  props: {
    hasSurvey: false,
    isWorking: true,
    maxRows: 4,
    bodyColumns: 100,
    scroll: { offset: 0, bodyRows: 4 },
    view: {},
  },
} as const

const PANE = {
  plugin: PLUGIN,
  component: 'Pane',
  requestId: 'turn-progress',
  props: {
    title: 'Progress',
    isFocused: false,
    bodyColumns: 100,
    placement: 'dock',
    scroll: { offset: 0, bodyRows: 20 },
    view: {},
  },
} as const

const SPAWN = {
  tool_use_id: 'agent-call',
  provider: { plugin: 'engine', tier: 'core' },
  parentModel: 'claude-opus-5-5',
  background: false,
  fork: false,
} as const

const SHELL_OK = { result: { stdout: '', stderr: '', interrupted: false } }

// Records the plugin's latest state write per key, since a test's `$` has no state noun.
function watchState(on: On): Map<string, unknown> {
  const written = new Map<string, unknown>()
  on('state.set', { plugin: PLUGIN }, ($, e, next) => {
    written.set(e.key, e.value)
    return next(e)
  })
  return written
}

test('set_steps declares the steps and step advances them', async ($, on) => {
  mock.clock(on, { now: 1_000 })
  const state = watchState(on)

  const set = await $.tool.call({
    tool: SET_STEPS,
    tool_use_id: 's1',
    title: 'Fix three bugs',
    steps: ['Fix bug 1', 'Fix bug 2', 'Fix bug 3'],
  })
  expect(set.deny).toBeUndefined()
  expect(set.result).toContain('Step 1 of 3: Fix bug 1')

  let list = state.get('checklist') as Checklist
  expect(list).toMatchObject({ done: 0, total: 3, active: 'Fix bug 1', source: 'tool', title: 'Fix three bugs' })

  const done = await $.tool.call({ tool: STEP, tool_use_id: 's2', index: 0, status: 'completed' })
  expect(done.result).toContain('Step 2 of 3: Fix bug 2')
  list = state.get('checklist') as Checklist
  expect(list?.done).toBe(1)
  expect(list?.items.map(item => item.status)).toEqual(['completed', 'in_progress', 'pending'])

  const out = await $.tool.call({ tool: STEP, tool_use_id: 's3', index: 9, status: 'completed' })
  expect(out.deny).toContain('between 0 and 2')
})

test('a subagent cannot declare the steps', async ($, on) => {
  const state = watchState(on)
  const set = await $.tool.call({ tool: SET_STEPS, tool_use_id: 's4', steps: ['a', 'b'], agentId: 'a9' })
  expect(set.deny).toBeDefined()
  expect(state.get('checklist')).toBeUndefined()
})

test('the system prompt ends with the steps instruction', async ($, on) => {
  on('prompt.compose', () => ({ sections: [{ id: 'base', text: 'You are Claude.', scope: 'shared' }] }))
  const { sections } = await $.prompt.compose({
    model: 'claude-opus-5-5',
    promptModel: 'claude-opus-5-5',
    surfaces: ['terminal'],
    tools: ['Bash', 'Read'],
    outputStyle: null,
    traits: [],
  })
  const last = sections[sections.length - 1]
  expect(last).toMatchObject({ id: 'turn-progress', scope: 'session' })
  expect(last?.text).toContain(SET_STEPS)
  expect(last?.text).toContain(STEP)
})

test('a fan-out of agents becomes the steps until set_steps replaces them', async ($, on) => {
  mock.clock(on, { now: 1_000 })
  const state = watchState(on)
  let spawned = 0
  on('agent.spawn', () => ({ model: 'haiku', agentId: `fan-${++spawned}` }))
  on('turn.complete', () => ({ text: '' }))

  await $.agent.spawn({ ...SPAWN, prompt: 'Fix bug 1', description: 'Fix bug 1', subagentType: 'fls-dev:qa-bugfixer' })
  await $.agent.spawn({ ...SPAWN, prompt: 'Fix bug 2', description: 'Fix bug 2', subagentType: 'fls-dev:qa-bugfixer' })

  let list = state.get('checklist') as Checklist
  expect(list).toMatchObject({ done: 0, total: 2, source: 'agents' })
  expect(list?.items.map(item => item.label)).toEqual(['Fix bug 1', 'Fix bug 2'])

  await $.turn.complete({ answer: 'ok', durationMs: 5, isAborted: false, turnId: 't-fan', agentId: 'fan-1', reason: 'answer' })
  list = state.get('checklist') as Checklist
  expect(list?.done).toBe(1)

  await $.tool.call({ tool: SET_STEPS, tool_use_id: 's5', steps: ['Run the suite'] })
  list = state.get('checklist') as Checklist
  expect(list).toMatchObject({ total: 1, source: 'tool' })

  // Declared steps win: a later spawn does not add to them.
  await $.agent.spawn({ ...SPAWN, prompt: 'Look', description: 'Look', subagentType: 'Explore' })
  list = state.get('checklist') as Checklist
  expect(list?.total).toBe(1)
})

test('the band leads with the step line and the pane lists the steps', async ($, on) => {
  mock.clock(on, { now: 1_000 })
  on('turn.start', (_, e) => ({ turnId: e.turnId }))
  on('ui.render', { component: 'AbovePrompt' }, () => ({ type: 'engine', ref: 0 }))

  await $.turn.start({ text: 'go', turnId: 't5' })
  await $.tool.call({
    tool: SET_STEPS,
    tool_use_id: 's6',
    steps: ['Fix bug 1', 'Fixing the second bug', 'Fix bug 3', 'Run the suite', 'Commit'],
    current: 1,
  })

  for (const surface of ['terminal', 'desktop'] as const) {
    const band = await $.ui.mount({ ...BAND, surface })
    const line = await band.find({ key: 'step-line' })
    expect(line?.text).toContain('Step 2 of 5: Fixing the second bug')
    expect(line?.text).toContain('██░░░░░░░░ 1/5')
    await band.unmount()

    const pane = await $.ui.mount({ ...PANE, surface })
    expect((await pane.find({ key: 'steps' }))?.text).toContain('Step 2 of 5: Fixing the second bug')
    expect((await pane.find({ key: 'steps-bar' }))?.text).toContain('20%')
    expect((await pane.find({ key: 'step-0' }))?.text).toBe('✓ Fix bug 1')
    expect((await pane.find({ key: 'step-1' }))?.text).toBe('● Fixing the second bug')
    expect((await pane.find({ key: 'step-4' }))?.text).toBe('○ Commit')
    await pane.unmount()
  }
})

test('steps survive a new turn until they are all done', async ($, on) => {
  mock.clock(on, { now: 1_000 })
  const state = watchState(on)
  on('turn.start', (_, e) => ({ turnId: e.turnId }))

  await $.tool.call({ tool: SET_STEPS, tool_use_id: 's7', steps: ['One', 'Two'] })
  await $.turn.start({ text: 'carry on', turnId: 't6' })
  expect((state.get('checklist') as Checklist)?.total).toBe(2)

  await $.tool.call({ tool: STEP, tool_use_id: 's8', index: 0, status: 'completed' })
  await $.tool.call({ tool: STEP, tool_use_id: 's9', index: 1, status: 'completed' })
  await $.turn.start({ text: 'next task', turnId: 't7' })
  expect(state.get('checklist')).toBeNull()
})

test('a turn records its tool calls and marks each one done', async ($, on) => {
  mock.clock(on, { now: 1_000 })
  const state = watchState(on)
  on('turn.start', (_, e) => ({ turnId: e.turnId }))
  on('tool.call', () => SHELL_OK)

  await $.turn.start({ text: 'run the tests', turnId: 't1' })
  expect((state.get('turn') as TurnInfo)?.step).toBe(0)

  await $.tool.call({ tool: 'Bash', tool_use_id: 'b1', command: 'uv run pytest', description: 'Run the tests' })
  await $.tool.call({ tool: 'Read', tool_use_id: 'r1', file_path: 'README.md' })

  const rows = state.get('tools') as ToolRow[]
  expect(rows).toHaveLength(2)
  expect(rows[0]).toMatchObject({ id: 'b1', tool: 'Bash', label: 'Run the tests', isError: false })
  expect(rows[0]?.endedAt).toBeDefined()
  expect(rows[1]).toMatchObject({ id: 'r1', tool: 'Read', label: 'Read' })
})

test('a spawned agent is listed until its turn completes', async ($, on) => {
  mock.clock(on, { now: 1_000 })
  const state = watchState(on)
  on('agent.spawn', () => ({ model: 'haiku', agentId: 'a1' }))
  on('turn.complete', () => ({ text: '' }))

  await $.agent.spawn({ ...SPAWN, prompt: 'Find the login view', description: 'Find login view', subagentType: 'Explore' })

  let rows = state.get('agents') as AgentRow[]
  expect(rows).toHaveLength(1)
  expect(rows[0]).toMatchObject({ id: 'a1', type: 'Explore', description: 'Find login view', status: 'running' })
  expect(rows[0]?.endedAt).toBeUndefined()

  await $.turn.complete({ answer: 'done', durationMs: 10, isAborted: false, turnId: 't-agent', agentId: 'a1', reason: 'answer' })

  rows = state.get('agents') as AgentRow[]
  expect(rows[0]).toMatchObject({ id: 'a1', status: 'completed' })
  expect(rows[0]?.endedAt).toBeDefined()
})

test('a TodoWrite call fills the checklist', async ($, on) => {
  mock.clock(on, { now: 1_000 })
  const state = watchState(on)
  const todos = [
    { content: 'Write the model', status: 'completed', activeForm: 'Writing the model' },
    { content: 'Run the tests', status: 'in_progress', activeForm: 'Running tests' },
    { content: 'Commit', status: 'pending', activeForm: 'Committing' },
  ] as const
  on('tool.call', { tool: 'TodoWrite' }, () => ({ result: { oldTodos: [], newTodos: [...todos] } }))

  await $.tool.call({ tool: 'TodoWrite', tool_use_id: 'w1', todos: [...todos] })

  expect(state.get('checklist') as Checklist).toEqual({
    done: 1,
    total: 3,
    active: 'Running tests',
    source: 'todo',
    title: null,
    items: [
      { label: 'Write the model', status: 'completed' },
      { label: 'Running tests', status: 'in_progress' },
      { label: 'Commit', status: 'pending' },
    ],
  })
})

test('the band draws only while work runs and hides on press', async ($, on) => {
  mock.clock(on, { now: 1_000 })
  on('turn.start', (_, e) => ({ turnId: e.turnId }))
  on('tool.call', () => SHELL_OK)
  on('ui.render', { component: 'AbovePrompt' }, () => ({ type: 'engine', ref: 0 }))

  for (const surface of ['terminal', 'desktop'] as const) {
    const idle = await $.ui.mount({ ...BAND, surface })
    expect(await idle.find({ key: 'summary' })).toBeUndefined()
    await idle.unmount()
  }

  await $.turn.start({ text: 'go', turnId: 't2' })
  await $.tool.call({ tool: 'Bash', tool_use_id: 'b2', command: 'ls', description: 'List files' })

  for (const surface of ['terminal', 'desktop'] as const) {
    const busy = await $.ui.mount({ ...BAND, surface })
    expect((await busy.find({ key: 'summary' }))?.text).toContain('1 tools')
    await busy.unmount()
  }

  const band = await $.ui.mount({ ...BAND, surface: 'terminal' })
  await band.press({ key: 'hide' })
  expect(await band.find({ key: 'summary' })).toBeUndefined()
  await band.unmount()
})

test('the pane lists agents and shells on every surface', async ($, on) => {
  mock.clock(on, { now: 1_000 })
  on('turn.start', (_, e) => ({ turnId: e.turnId }))
  on('agent.spawn', () => ({ model: 'haiku', agentId: 'a2' }))
  on('tool.call', () => SHELL_OK)

  for (const surface of ['terminal', 'desktop'] as const) {
    const idle = await $.ui.mount({ ...PANE, surface })
    expect(await idle.find({ key: 'idle' })).toBeDefined()
    await idle.unmount()
  }

  await $.turn.start({ text: 'go', turnId: 't3' })
  await $.agent.spawn({ ...SPAWN, prompt: 'Look around', description: 'Survey the app', subagentType: 'Explore' })
  await $.tool.call({ tool: 'Bash', tool_use_id: 'b3', command: 'uv run pytest -q', description: 'Run the suite' })

  for (const surface of ['terminal', 'desktop'] as const) {
    const pane = await $.ui.mount({ ...PANE, surface })
    expect((await pane.find({ key: 'agent-a2' }))?.text).toContain('Survey the app')
    expect((await pane.find({ key: 'shell-b3' }))?.text).toContain('Run the suite')
    await pane.unmount()
  }
})
