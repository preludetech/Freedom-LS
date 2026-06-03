Currently, the do_qa step of our DSS process fakea a LONG time, even for simple changes. We use a lot of tokens and wait a long long time.

Improve the process:
- research available tools and see if we are using the right thing
- find ways to run tests in parallel if possible. Use faster models for differnt parts of the work
- build out any kind of helper script, agent or whatever else we need to add efficiency

If the qa finds a bug, then get it to ask another agent to fix that bug in a TDD way and report on what it did. Make good decisions about what bugs to fix. The fixer agent should report back on what changed and the QA process should re-check the given functionality to make sure it now works and nothing broke in the process.


Problem:
Parallel tool batches get cascade-cancelled when any one call is rejected,
    and rm -rf/cd trip a security hook — this caused a lot of apparent churn early
    on.
This can make QA get stuck in a loop even on the simplest qa runs.
