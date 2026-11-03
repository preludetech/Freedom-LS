# Idea: throwaway chain stop

Throwaway idea for proving that `/sdd:start` stops cleanly. It lives only on the local
`sdd-chain-throwaway-stop` branch and is never merged or pushed.

Planted problems, both on purpose:

- A stray `todo.md` already sits here, so the todo mechanic returns `blocked` and asks.
- `design_prompt.md` links a Claude Design project that does not exist, so registering the design
  fails and the chain stops before the spec is written.

Not decided yet:

- Whether this idea needs a spec at all.
