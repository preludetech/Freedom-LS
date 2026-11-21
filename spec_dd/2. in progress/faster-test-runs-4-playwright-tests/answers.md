# Answers: faster-test-runs-4-playwright-tests

Asked by `/sdd:start` before the spec was written.

- Q: When several Playwright tests merge into one flow, how should a failure partway through be reported? → A: Stop at the first failure: plain sequential expects, no soft assertions or subtests (asked up front)
- Q: For one page checked at several viewports, what shape should the merged test take? → A: One test loads the data once, then resizes the page to each viewport and checks it in turn (asked up front)
- Q: How should the owner approve the behaviours the audit proposes to drop? → A: In the spec review: the audit's "goes" rows are listed in the spec and approved there, before any test is touched (asked up front)
- Q: When should the audit of the Playwright tests be done, given drops are approved at spec review? → A: Now, beside the spec: `audit.md` lists every test node, and the spec lists its "goes" rows for approval at spec review (asked after the research)
- Q: How should the test fixture put a signed-in session into the browser? → A: `Client.force_login`, then add its session cookie to the page's browser context, per test (asked after the research)
