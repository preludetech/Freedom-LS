# Research: known complaints

Question: What do users commonly complain about with this kind of work?

Evidence is thin: two web searches, mostly vendor accessibility audits and one Wagtail upgrade blog
post, not forum threads. Items marked "inference" have no source.

## A. Educators and admins (LMS dashboards)

| Complaint | Evidence | Guard in the spec |
|---|---|---|
| Dashboards are hard to use with a screen reader because headings, status updates and field labels are missing. | [UW Explorance Blue evaluation](https://kb.wisc.edu/158237) | The screen-reader pass covers the quick view, modal and tables. Check each for headings, labels and live-region announcements. |
| Page or section changes in a dynamic app are not announced. A date-range selection was shown visually only. | [Zensai conformance report](https://trustcenter.zensai.com/hc/en-us/article_attachments/23419676549277) | HTMX swaps and modal opens need `aria-live` or focus management. State must not be conveyed by colour alone, including badges. |
| Tables have no caption or summary, confusing header text, or broken row and column structure. Some audits also found layout tables. | [Learning Pool](https://learningpool.com/accessibility-statement-for-learning-pool-lms), [INSEAD](https://www.insead.edu/accessibility-statement/online-programmes), [UW Cornerstone](https://kb.wisc.edu/accessibility/164756) | Every table gets a caption, `th scope`, and no layout tables. Check the reports and history tables. |
| Parts of the site cannot be used by keyboard alone, and analytics dashboards lack structure and labels. | [Manchester Canvas statement](https://www.itservices.manchester.ac.uk/uom-accessibility-statements/canvas-learning-management-system/) | Keyboard pass through every action. Dashboard and report widgets need labels and headings. |
| An in-page link moves the viewport but not keyboard focus. | [Learning Pool](https://learningpool.com/accessibility-statement-for-learning-pool-lms) | Modal and quick-view open and close must move focus and return it to the trigger. |
| Tab-style navigation is not announced as tabs. | [UW Cornerstone](https://kb.wisc.edu/accessibility/164756) | Correct ARIA roles on section navigation, or plain links with `aria-current`. |
| The side navigation is sometimes hidden on mobile (thin evidence). | [UBC blog](https://blogs.ubc.ca/rankang/?p=655) | Check navigation at 390 px. Tables scroll or collapse without hiding actions. |
| Automated tools alone miss keyboard and screen-reader problems. | [Drupal LMS issue](https://www.drupal.org/project/lms/issues/3586897), [Continual Engine](https://www.continualengine.com/blog/lms-accessibility/) | Don't rely on an automated scan alone; state a manual method and record what is deliberately left. |

Inference:

- **Wording:** inconsistent action names (deactivate, remove, unregister), unclear destructive
  confirmations, empty states that say nothing. Guard: one wording table from
  `fls-dev:domain-glossary`, one confirmation shape, one empty-state pattern with a next step.
- **Dark mode:** bugs are usually low contrast on badges, borders or inputs. Check every screen in
  both themes.
- **Stale docs:** out-of-date screenshots. Take them fresh and recheck against the final UI.

## B. Downstream developers (extensible frameworks)

| Complaint | Evidence | Guard in the spec |
|---|---|---|
| Overridden templates silently break after a refactor, because a file was removed or its content moved to another partial. | [Tivix, Wagtail upgrade](https://www.tivix.com/blog/wagtail-wagtail-smite-me-a-blow), [Wagtail 2.16 breaking changes](https://next.wagtail.org/blog/wagtail-216-and-upcoming-breaking-changes/) | List every template moved, renamed or deleted and where its content went, plus every template a downstream may have overridden. |
| Developers skip the upgrade section, or assume nothing applies when they have no override app. | [Tivix](https://www.tivix.com/blog/wagtail-wagtail-smite-me-a-blow) | Open the notes with a short "do you need to act" checklist. |
| Module or path renames break projects. | [Wagtail 2.0 notes](https://github.com/wagtail/wagtail/blob/v2.8/docs/releases/2.0.rst) | Old against new for every URL change; say whether a redirect exists. |
| Deprecations are discovered late. | [Wagtail 2.16 post](https://next.wagtail.org/blog/wagtail-216-and-upcoming-breaking-changes/), [CodeRed 0.19.0](https://docs.coderedcorp.com/wagtail-crx/stable/releases/v0.19.0.html) | Mark removed against deprecated. |

Inference:

- **Settings:** every new setting needs name, default and effect.
- **Tailwind:** a missed rebuild leaves new classes unstyled. Set `requires_tailwind_rebuild` and
  name `npm run tailwind_build`.
- **Migrations and events:** list them explicitly.
- **Docs drift:** the `alpine-js` skill's non-existent component already shows it. Verify the
  inventory against registered code, not older docs.

## Cross-cutting guard

Check the notes and docs against the code: URL names, template paths, settings, registered Alpine
components. The consolidated notes link to each spec's own notes.

status: ok
