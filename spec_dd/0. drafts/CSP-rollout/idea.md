# CSP Rollout: From Report-Only to Enforcing

## Context

As part of the Django 6.0 upgrade (see `spec_dd/1. next/01. upgrade-to-django-6/`), CSP was set up in **report-only mode**. This follow-up spec covers tightening the policy and switching to enforcing mode.

## Goals

1. Analyze CSP violation reports from report-only mode to understand what resources are loaded
2. Migrate inline scripts and styles to use nonce-based CSP (`{{ csp_nonce }}`)
3. Tighten the CSP policy to remove `unsafe-inline` for scripts
4. Switch from `SECURE_CSP_REPORT_ONLY` to `SECURE_CSP` (enforcing mode)
5. Ensure HTMX compatibility with strict CSP (HTMX fetch requests, `hx-headers` inline attribute)
6. Set up CSP violation reporting endpoint for production monitoring

## Key considerations

- HTMX uses inline attributes (`hx-get`, `hx-post`, `hx-headers`) which CSP does not block (CSP targets `<script>` and `<style>` elements, not HTML attributes)
- The CSRF token in `<body hx-headers='{"X-CSRFToken": "{{ csrf_token }}"}'>` is an HTML attribute, not inline JS — should be CSP-safe
- Any `<script>` or `<style>` tags in templates need nonces
- django-browser-reload auto-includes CSP nonces on Django 6
- Third-party resources (CDN scripts, external images) need explicit allowlisting
