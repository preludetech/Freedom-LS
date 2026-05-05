Two small standalone tweaks to the course content templates. Bundled together because each is too small to justify its own spec/branch and they touch the same area of the codebase.

Use playwright mcp to take screenshots before/after every visual change so regressions are caught. Verify each change at desktop, tablet, and mobile widths.

## 1. Next/Previous button icons

http://127.0.0.1:8000/courses/standard-markdown-demo-finance/1/ — the **Next** button should have a forward arrow to the *right* of the text. Mirror for the Previous button (arrow on the left). Use the project's existing icon component.

## 2. Finish page — remove "View Course" button

http://127.0.0.1:8000/courses/standard-markdown-demo-finance/finish/ — remove the "View Course" button.
