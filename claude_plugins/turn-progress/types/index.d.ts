export type TurnInfo = {
  turnId: string
  startedAt: number
  step: number
  chars: number
  mode: string | null
  word: string | null
} | null

export type ToolRow = {
  id: string
  tool: string
  label: string
  agentId?: string
  startedAt: number
  endedAt?: number
  isError?: boolean
  isBackground?: boolean
  taskId?: string
}

export type AgentRow = {
  id: string
  type: string
  description: string
  startedAt: number
  endedAt?: number
  status: string
  tools: number
  parentId?: string
}

export type ChecklistItem = {
  label: string
  status: 'pending' | 'in_progress' | 'completed' | 'failed'
  agentId?: string
}

export type ChecklistSource = 'tool' | 'todo' | 'agents'

export type Checklist = {
  done: number
  total: number
  active: string | null
  items: ChecklistItem[]
  source: ChecklistSource
  title: string | null
} | null

declare module 'claude-code' {
  interface PluginState {
    'turn-progress': {
      turn: TurnInfo
      tools: ToolRow[]
      agents: AgentRow[]
      checklist: Checklist
      now: number
      isBandHidden: boolean
    }
  }
}
