Sometimes tests are not organized very well. some of it seems quite chaotic.

We need to make sure that tests are organized well into the right folders and files. This should not feel philosophical, it should feel obvious for the most part.

1. The test file hierarchy should mirror the application file hierarchy as much as possible.
2. If an app does not itself depend on a different app, then ideally its tests should not depend on that different app.

The SDD workflow needs to take these best practices into account while writing and reviewing code.

We also need to add something to the STD process so that it acts like a Boy Scout. It shouldn't do Big Bang epic cleanups unless it's specifically asked to, but if it touches some code that doesn't meet standard, it should clean it up as we go. Use suitable subagents to make this happen.

This should ideally be broken down into multiple specs. The first one will be about setting up the skills and best practices and then we can make a bunch of other tasks specifically for cleaning up different things.  Maybe it would make sense to make a speck per app or something like that. Then we can run those one at a time and get everything up to scratch. We won't implement this all in a Big Ben kind of way, but many small bangs are fine
