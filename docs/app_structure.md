# App Structure

This file is the authoritative picture of inter-app dependencies in this project. It is **generated** by running `/app_map`.

Treat it as the source of truth for what cross-app imports are allowed. Any implementation plan that introduces a new edge must flag the change via `/plan_structure_review` and get approval before code is written.

- **Solid arrows** — runtime imports (one app imports from another outside of tests).
- **Dashed arrows** — test-only imports (cross-app fixtures or helpers).
- **No arrow** — no import relationship; treat these apps as independent.

Regenerate this file whenever the graph changes: `/app_map`.

```mermaid
flowchart TB
    accounts
    app_authentication
    base
    content_engine
    educator_interface
    icons
    markdown_rendering
    panel_framework
    qa_helpers
    role_based_permissions
    site_aware_models
    student_interface
    student_management
    student_progress
    webhooks
    xapi_learning_record_store
    accounts --> markdown_rendering
    accounts --> site_aware_models
    accounts --> webhooks
    app_authentication --> site_aware_models
    content_engine --> markdown_rendering
    content_engine --> site_aware_models
    educator_interface --> accounts
    educator_interface --> content_engine
    educator_interface --> panel_framework
    educator_interface --> student_management
    educator_interface --> student_progress
    qa_helpers --> accounts
    qa_helpers --> content_engine
    qa_helpers --> student_management
    qa_helpers --> student_progress
    role_based_permissions --> accounts
    role_based_permissions --> site_aware_models
    student_interface --> accounts
    student_interface --> content_engine
    student_interface --> student_management
    student_interface --> student_progress
    student_interface --> webhooks
    student_management --> accounts
    student_management --> content_engine
    student_management --> site_aware_models
    student_management --> webhooks
    student_progress --> accounts
    student_progress --> content_engine
    student_progress --> site_aware_models
    student_progress --> student_management
    webhooks --> base
    webhooks --> site_aware_models
    xapi_learning_record_store --> site_aware_models
    role_based_permissions -.-> student_management
    site_aware_models -.-> accounts
    webhooks -.-> accounts
```

## Dependency table

| App | Runtime deps | Test-only deps |
| --- | --- | --- |
| accounts | markdown_rendering, site_aware_models, webhooks | — |
| app_authentication | site_aware_models | — |
| base | — | — |
| content_engine | markdown_rendering, site_aware_models | — |
| educator_interface | accounts, content_engine, panel_framework, student_management, student_progress | — |
| icons | — | — |
| markdown_rendering | — | — |
| panel_framework | — | — |
| qa_helpers | accounts, content_engine, student_management, student_progress | — |
| role_based_permissions | accounts, site_aware_models | student_management |
| site_aware_models | — | accounts |
| student_interface | accounts, content_engine, student_management, student_progress, webhooks | — |
| student_management | accounts, content_engine, site_aware_models, webhooks | — |
| student_progress | accounts, content_engine, site_aware_models, student_management | — |
| webhooks | base, site_aware_models | accounts |
| xapi_learning_record_store | site_aware_models | — |

## Legend

- `A --> B` — `A` imports from `B` at runtime.
- `A -.-> B` — `A` imports from `B` only in test code (tests, conftest, factories).
- Apps with no edges are self-contained.
