---
description: Execute a frontend QA test plan using Playwright MCP
allowed-tools: Read, Write, Glob, mcp__playwright*
---

Act like a human QA expert. Execute the given test plan

# Useful info

- Base url: http://127.0.0.1:8000/
- Admin email and password: demodev@email.com 
- Runserver is already running. You don't need to start the runserver


# CRITICAL

You MUST use Playwright MCP. If you can't use it then:

- explain why you can't use it
- explain how to fix the error
- DO NOT CONTINUE WITH THE TESTS IF YOU CAN'T USE PLAYWRIGHT

Before doing anything else, use playwright to open the base url and make sure it works.

# Instructions

Use the Playwright MCP server tools (browser_navigate, browser_snapshot, browser_click, browser_type, browser_take_screenshot, etc.) to manually walk through the test plan. Do NOT write test scripts — interact with the site directly using the MCP tools, just as a human tester would.

Take screenshots of relevant functionality and put them in a "screenshots" directory in this current directory (alongside the frontend_qa file). Make sure the screenshots are named in a way that ties them back to the specific test you are running through.

If anything unrelated to the current feature under test seems out of place or broken then use a sub agent to explore it.

# Generate a report

Create a new file called qa_report.md (in the same directory as the frontend_qa file we are working with).

For each error:
- give it a title
- include relevant screenshots using markdown syntax
- mention the test that was failed
- say what the expected behavior was, and the desired behavior

If anything was not tested for any reason, or if there were any difficulties, then explain.

If anything unrelated to the current tests, or tangentiual to the functionality under test seemed out of place then include that in the report.


