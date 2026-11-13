We recently made the SDD workflow more parallel, and added parallelism to our tests.

While it was a good idea in theory we often run our of ram. When that happens, test suites often die and need to be restarted, wasting a lot of time.

We need stratergies for ram management.

some ideas
- check ram availability before running tests. If there isn't enough then wait until there is
- if a test suite dies because of not enough ram, do some kind of backoff and try again
- reduce the number of parallel tests when ram is low
- run sections of the test suite individually so that we can checkpoint progress, so if something falls over we can more easily pick up where we left off (or have some other way to resume)

Implement the fixes that are most likely to make an impact, dont blindly follow my ideas
