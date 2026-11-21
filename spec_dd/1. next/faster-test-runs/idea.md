> This idea has been cut into 13 specs. Their order, dependencies, the decisions already taken and
> the assumptions are in the "Faster test runs" section of `spec_dd/1. next/roadmap.md`. Start there.
> The text below is the original brief and is kept as written.

My sdd process is a bit slow. The challenge is the unit tests - they take a long time to run and take up a lot of system resources so I can't work on multiple worktrees at the same time.

I suspect there are redundant or useless tests eating up time, or multiple playwright tests that can be combined and that kind of thing.

Also is there a way for me to execute the tests remotely? Perhaps trigger a github action when I need to test the full suite instead of running locally? Or use claude code on the cloud to take on some parts of the implementation work?

We'll only get Claude cloud to run the tests in the cloud if the other stuff doesn't work.

The measurements behind the cut are in `research_test_timings.md`.
