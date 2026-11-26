# Fix the tests a run left failing

A failing test is work for this run, never a todo for the user. It does not matter whether the test
also failed before this run's changes, or on `main`.

Inputs: `<failed>`, the failing test ids, and `<change>`, the range the test run covered.

1. Spawn one `general-purpose` sub-agent (`model: "sonnet"`) as a solo `Agent` call. Write every
   input into its prompt: each test id with its failure output, and `<change>`. Its rules:
   - Read `claude_plugins/sdd/commands/protected/run_tests.md` and run each failing test alone
     with the request `one test` to see the failure for itself.
   - Find and fix the root cause, in the code or in the test, whichever is wrong. Never skip,
     delete, mark or loosen a test to get a pass: the test still checks what it was written to
     check.
   - Follow `run_tests.md` with the request `one test` for each id until it passes, then with the
     request `failed`, `<failed>` and `<change>`.
   - Commit each fix with the project's commit rules and push.
   - A test it can fix only by choosing between behaviours the spec documents leave open is
     `blocked` on that decision. Every other failure is its to fix.
   - Return one line per test: `<test id> · fixed · <commit>` or
     `<test id> · blocked · decision: <the question>`, or `<test id> · failed · diagnosis: <one line>`.
2. A `failed` test gets one more sub-agent, briefed the same way plus the first diagnosis. Fix it
   yourself at depth 0 if that one also fails: read the test, its failure and the code, and work it
   the same way.
3. Only a `blocked` test leaves this file unfixed. It goes to the user as a decision:
   `Decide <the question>, then <what follows for the test>`, never as "fix the tests".

Done when every test in `<failed>` passes or is `blocked` on a named decision.
