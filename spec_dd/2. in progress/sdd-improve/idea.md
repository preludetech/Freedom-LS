Currently, the STD process stalls quite often because it needs user input. We need to improve things so that it can keep going for a longer time successfully without any user input.

1.  If a stage in the process needs to ask questions, then try to front-load those questions as much as possible instead of delaying. If you do need to ask questions later, then still ask them, but try to front-load them as much as possible for user efficiency.

2. Combine certain steps:

Here are possabilities to review
- improve idea could make the spec
- we can review the spec with a subagent instead of in a seperate step
- the plan stage already fires off subagents to add extra info. Can we add other reviews there?
    - check app structure
    - check if we are introducing new threats
    Note that the current threat-mopdel and security review commands typically are not executed and an be removed. We dont do them because they do too wide and too paranoid and it just ends up wasting time. We haven't used them for ages
- When implementing the plan we have a subagent that reviews changes as we go.Get it to:
    - check comments and docstrings becasuse sometimes spec numbers and things like that slip in
    - check that the tests are to standard
- combined documentation step:
    Once we have finished implementing the plan then we need to make documentation. This should happen after implementation, but it can be one command that does everythin:
    - update app structure
    - updater tupgrade notes
    - update product docs
    - ONLY IF NEEDED: updater fls content plugin
