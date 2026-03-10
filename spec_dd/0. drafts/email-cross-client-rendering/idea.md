# Cross-Client Email Rendering

## Goal

Ensure all transactional emails render correctly across major email clients (Gmail, Outlook, Apple Mail, Yahoo, etc.).

## Why

Currently emails are only tested in Chromium. Email clients have wildly inconsistent CSS support - Outlook uses Word's rendering engine, Gmail strips most CSS, Yahoo has its own quirks. Browser testing catches almost none of these issues.

## Approach

1. **Mailpit as dev SMTP server** - Capture and inspect emails during development. Has a built-in HTML check that flags basic compatibility issues. Good for fast iteration, but its renderer is browser-based so it won't catch client-specific rendering problems.

2. **Email-safe HTML** - Audit templates to use only widely-supported CSS: table-based layout, inline styles, no flexbox/grid. Use caniemail.com as reference. Consider MJML or Maizzle to generate cross-client-compatible HTML.

3. **Cross-client screenshot testing** - Use Litmus or Email on Acid to render emails across real clients and compare. Paid tools but industry standard for verifying rendering across clients.

## Scope

All transactional emails: password reset, signup confirmation, notifications, etc.
