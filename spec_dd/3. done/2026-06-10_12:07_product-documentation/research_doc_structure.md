# Research: Structuring Product Documentation for Compliance + Sales

Audience: SDD idea-refinement. Actionable notes only.

---

## 1. The Core Structural Insight: Capabilities, Not Procedures

The most reusable pattern for dual-audience (compliance + sales) docs is a **capability/control inventory**: each document describes WHAT the system can do (the capability), not HOW to configure or use it (a manual), and not a policy narrative (a compliance document).

- Compliance reviewers map capabilities to their own framework's controls — you don't pre-map for them.
- Sales teams pull capability bullets directly into pitch decks or proposal responses.
- One set of facts, multiple consumers.

This is explicitly the pattern used by trust centers (SafeBase/Drata, Conveyor, Vanta) and by vendor security questionnaire responses.

---

## 2. Top-Level Section Set (framework-agnostic, covers all major frameworks)

The following categories cover ~95% of what SOC 2, ISO 27001, GDPR, POPIA, and typical vendor security questionnaires ask about. Each should be a separate markdown file.

### Must-have sections

| File name | What it covers |
|---|---|
| `identity-and-access.md` | Authentication (MFA, email verification, session mgmt), authorisation (roles, RBAC, least-privilege), account lifecycle (create/deactivate/invite) |
| `data-handling.md` | What personal/sensitive data is collected, how it's classified, storage location/residency, encryption in transit, encryption at rest |
| `audit-and-logging.md` | What events are logged, log retention, who can access logs, tamper-evidence |
| `data-retention-and-deletion.md` | Retention periods per data type, how deletion/erasure works, backup retention |
| `incident-response.md` | Breach detection approach, notification capability (to whom, in what timeframe), recovery procedures |
| `backups-and-recovery.md` | Backup frequency, RPO/RTO targets, restore testing, off-site/geo-redundancy |
| `infrastructure-and-deployment.md` | Hosting provider, geographic location, provider certifications (e.g. ISO 27001), network security, TLS version |
| `application-security.md` | CSRF, input validation, dependency management, SDLC practices, test automation, secrets management |
| `data-subject-rights.md` | What rights data subjects have (access, correction, deletion, objection), how the system supports fulfilling them |
| `third-party-and-integrations.md` | External services used, subprocessor list, data shared with third parties |

### Useful additions

| File name | What it covers |
|---|---|
| `content-and-configuration.md` | Content editing workflow, version control, AI-assisted authoring, customisation/extension model |
| `multi-tenancy-and-isolation.md` | Site-aware model, tenant separation, data isolation guarantees |
| `future-roadmap.md` | Half-built features that will be material later (RBAC depth, xAPI, etc.) — honest, brief |

---

## 3. Compliance Reviewer Checklist (framework-agnostic categories)

A reviewer from any of POPIA/GDPR/ISO 27001/SOC 2 will look for factual answers to these questions. The doc set must cover each one:

- **Authentication** — what factors are supported, is MFA available/enforced, session expiry
- **Access control** — how roles/permissions work, least-privilege enforcement, admin access procedures
- **User lifecycle** — how accounts are created, transferred (role change), and deactivated/deleted
- **Data classification** — what counts as personal/sensitive, how it is labelled or handled differently
- **Encryption in transit** — TLS version, enforced HTTPS
- **Encryption at rest** — DB/field level, key management
- **Audit trails** — what is logged (who did what, when), retention period, tamper protection
- **Data retention** — how long data is kept, automated purge vs manual, backup retention
- **Data deletion / right to erasure** — can personal data be deleted on request, what is actually removed
- **Data residency** — where data physically lives, relevant jurisdiction
- **Incident detection and response** — how breaches are detected, notification capability, timelines
- **Backups and recovery** — RTO/RPO, frequency, tested restore
- **Vulnerability management** — how dependencies are tracked, how security defects are triaged
- **Third-party / subprocessors** — what external services receive personal data
- **Data subject rights** — access, correction, portability, objection — how system supports them
- **Change management** — how code changes are controlled, reviewed, deployed

POPIA-specific additions (South Africa): lawful basis for processing, information officer designation capability, cross-border transfer controls.

---

## 4. How Successful Products Structure Their Trust/Security Docs

From reviewing real trust centers (Asana, Google Cloud, Conveyor guide, Drata/SafeBase):

- **Landing page / index** (`README.md` or `index.md`): one-page overview linking to all sections, with a short "security posture summary" paragraph (3–5 sentences max). This is the sales-friendly entry point.
- **Separate files per domain** (not one giant doc) — reviewers navigate directly to the section they care about.
- **Certifications and third-party attestations** called out prominently in the index — even if Freedom LS is not yet certified, the infrastructure provider's certifications are noted here.
- **FAQ / Common Questions** section (or inline per doc) — "Where is data hosted?", "Can we delete a user's data on request?" These double as sales objection handlers.
- **Versioning/date stamp** on each doc (front matter or footer) so reviewers know currency.

Trust centers typically organise under: Overview → Product Security → Infrastructure Security → Data Privacy → Compliance & Certifications → Legal (DPA/ToS). For a plain-markdown repo, the same grouping works as subdirectories or a flat file list with consistent prefixes.

---

## 5. Dual-Audience Without Bloat

The tension: compliance reviewers want exhaustive, precise, caveat-laden descriptions; sales wants punchy bullets.

Practical resolution used by mature products:
- **Write for compliance reviewers first** (precise, factual, no hype). This is the canonical file.
- Add a `## Summary` or `## Key Points` callout block at the top of each file — 3–5 bullets. Sales uses that block; reviewers read the rest.
- No separate "sales version" of docs — single source of truth.
- Keep a `CHANGELOG.md` or date in each file's front matter. Reviewers care that docs are current; stale docs are worse than no docs.

---

## 6. Plain-Markdown Repo Conventions

**Directory layout** (recommended for `docs/product/`):

```
docs/product/
  README.md                      ← index / entry point, links to all files
  identity-and-access.md
  data-handling.md
  audit-and-logging.md
  data-retention-and-deletion.md
  incident-response.md
  backups-and-recovery.md
  infrastructure-and-deployment.md
  application-security.md
  data-subject-rights.md
  third-party-and-integrations.md
  content-and-configuration.md
  multi-tenancy-and-isolation.md
  future-roadmap.md
```

**File naming** — kebab-case lowercase, no spaces, `.md` extension. Consistent with npm/MkDocs/GitHub rendering conventions.

**Within each file:**
```
# [Title]
_Last updated: YYYY-MM-DD_

## Summary
- bullet
- bullet

## [Section]
...
```

**Cross-linking** — use relative links: `[data handling](./data-handling.md)`. Anchor links use lowercase-with-hyphens: `#encryption-in-transit`. Both render correctly on GitHub and in MkDocs/static site generators.

**README.md index** — one-line description per file, grouped into: Core Security, Data & Privacy, Infrastructure, Product Features.

---

## 7. What NOT to Put in These Docs

- Internal implementation details (ORM queries, migration files, Python version specifics) — this is for product-level docs, not a developer wiki.
- Policy assertions without factual backing ("We take security seriously") — write capabilities, not promises.
- Prescriptive user instructions ("Click the Settings button to...") — not a user manual.
- Framework-specific compliance claims ("This satisfies GDPR Article 17") — leave mapping to the reviewer.

---

## 8. Relevant to the Existing Idea

The idea.md lists these doc areas: content editing workflow, authentication, learner experience, learner tracking, educator interface, admin interface, security, configuration/extension, deployment, future work.

Mapping to the compliance-ready structure above:
- "Authentication" → `identity-and-access.md` (expand to include authorisation)
- "Security" (dev + runtime) → `application-security.md` + `infrastructure-and-deployment.md`
- "Deployment" → `infrastructure-and-deployment.md` + `backups-and-recovery.md`
- "Content editing workflow" → `content-and-configuration.md`
- "Learner tracking" → relevant part of `audit-and-logging.md` + new `learner-experience.md` (product feature, not compliance)
- "Future work" → `future-roadmap.md`
- New files to add beyond the idea: `data-handling.md`, `data-retention-and-deletion.md`, `incident-response.md`, `data-subject-rights.md`, `third-party-and-integrations.md` — these are required for any compliance review and not currently listed in the idea.

---

## Sources

- [Building a Trust Center: A Guide to Security Transparency (Astra)](https://www.getastra.com/blog/compliance/building-a-trust-center/)
- [The Ultimate Guide to Trust Centers (Conveyor)](https://www.conveyor.com/blog/the-ultimate-guide-to-trust-centers-showcase-your-security-posture-and-build-trust-faster)
- [What is a Trust Center? (SafeBase/Drata)](https://safebase.io/resources/what-is-a-trust-center)
- [OWASP Product Security Capability Framework](https://owasp.org/www-project-product-security-capability-framework/)
- [Your Ultimate Guide to Security Frameworks (CSA)](https://cloudsecurityalliance.org/blog/2024/04/29/your-ultimate-guide-to-security-frameworks)
- [SOC 2 Common Criteria (Secureframe)](https://secureframe.com/hub/soc-2/common-criteria)
- [SOC 2 vs ISO 27001 (Secureframe)](https://secureframe.com/blog/soc-2-vs-iso-27001)
- [POPIA Compliance Checklist (Usercentrics)](https://usercentrics.com/resources/popia-checklist/)
- [Comparing privacy laws: GDPR v. POPIA (DataGuidance)](https://www.dataguidance.com/sites/default/files/onetrustdataguidance_comparingprivacylaws_gdprvpopia.pdf)
- [Data Subject Rights - POPI Act](https://www.popiact-compliance.co.za/popia-information/10-data-subject-rights)
- [Access Control Compliance Guide 2025 (Veza)](https://veza.com/blog/access-control-compliance-guide-2025/)
- [Building a Markdown-Based Documentation System (Medium)](https://medium.com/@rosgluk/building-a-markdown-based-documentation-system-72bef3cb1db3)
- [Markdown for Documentation: Structure, Cross-Links (The Product Guy)](https://theproductguy.in/blogs/markdown-for-documentation/)
- [Vendor Security Questionnaire Guide (TrustCloud)](https://www.trustcloud.ai/security-questionnaires/ultimate-security-questionnaire-guide-for-vendors/)
- [Information Security Questionnaire: Templates & Best Practices (SiftHub)](https://www.sifthub.io/blog/information-security-questionnaire)
- [IT Audit Compliance Checklist (Sprinto)](https://sprinto.com/blog/it-compliance-checklist/)
- [Single Source of Truth for Compliance (Skematic)](https://skematic.com/you-need-a-single-source-of-truth-for-compliance/)

status: ok
