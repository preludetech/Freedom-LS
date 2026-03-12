# Outward Webhooks — QA Report

**Date:** 2026-03-12
**Tester:** Claude (automated via Playwright MCP)
**Environment:** http://127.0.0.1:8000 (Django dev server, DEBUG=True)

---

## Summary

| Test | Description | Result |
|------|-------------|--------|
| Test 1 | Create a Webhook Endpoint | PASS |
| Test 2 | Webhook Endpoint List View | PASS |
| Test 3 | Send Test Ping | PASS |
| Test 4 | Webhook Event List (Read-Only) | PASS |
| Test 5 | Webhook Delivery List and Retry | PASS |
| Test 6 | Enable/Disable Endpoint Actions | PASS |
| Test 7 | HTTPS Validation (Production Mode) | SKIPPED (per plan) |
| Test 8 | Event Type Validation | PASS |
| Test 9 | End-to-End Webhook Flow (User Registration) | PASS |

**Mobile/Tablet testing:** Skipped (Django admin interface).

**All tests pass.** No failures.

---

## Screenshots

| Screenshot | Description |
|------------|-------------|
| `desktop_1.1_add_endpoint_form.png` | Add webhook endpoint form with checkboxes |
| `desktop_1.2_endpoint_created.png` | Endpoint created with auto-generated secret |
| `desktop_2.1_endpoint_list.png` | Endpoint list view with all columns |
| `desktop_2.2_endpoint_list_filters.png` | List view filter options |
| `desktop_3.1_test_ping_event.png` | Test ping event created |
| `desktop_3.2_test_ping_delivery.png` | Test ping delivery record (failed as expected) |
| `desktop_4.1_event_detail_readonly.png` | Event detail view (read-only) |
| `desktop_5.1_delivery_detail.png` | Delivery detail view |
| `desktop_5.2_delivery_retry.png` | Delivery after retry (attempt count incremented) |
| `desktop_6.1_endpoint_disabled.png` | Endpoint disabled via bulk action |
| `desktop_8.1_event_type_validation.png` | Event type checkboxes (no free-text input) |
| `desktop_9.2_user_registered_event_pass.png` | Deliveries list showing user.registered delivery created on signup |
