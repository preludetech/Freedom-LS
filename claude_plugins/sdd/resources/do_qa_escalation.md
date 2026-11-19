# QA escalation

If something unrelated to the feature under test seems out of place, spawn **one `sdd:sdd-worker`**
to investigate. That agent has no Bash and no browser and reads source only, so scope the question
to "what in the code could explain this?", and give it an explicit output path
(`.sdd-work/qa_probe_<slug>.md`), which its contract requires.
