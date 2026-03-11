A lot of the tests that Claude  writes are useless.
Eg model creation tests that check that default values are as configured.

Make a test-cleanup command that:
- goes over existing tests
- sees what is redundant and useless
- removes pointless tests
- always explains itself

Run it.

Then update all the testing and tdd docs for claude so it does a cleanup after every few tests. This cleanup should focus only on the tests that have recently been written.
