# Research: Automated Accessibility Testing for FLS

Date: 2026-03-13

## 1. Python/Django Accessibility Testing Tools

### axe-playwright-python (Recommended)

The best fit for this project. A Python wrapper around axe-core that integrates directly with Playwright, which FLS already uses.

- **Package**: `axe-playwright-python` (v0.1.7, released Dec 2025)
- **Install**: `uv add axe-playwright-python`
- **Maintained by**: Pamela Fox (Microsoft)
- **Supports**: Python 3.10+, Playwright 1.25+

Basic usage with pytest:

```python
from axe_playwright_python.sync_playwright import Axe

@pytest.mark.playwright
def test_page_accessibility(page, live_server):
    page.goto(f"{live_server.url}/courses/")
    results = Axe().run(page)
    assert results.violations_count == 0, results.generate_report()
```

Results API:
- `results.violations_count` -- number of violations found
- `results.generate_report()` -- human-readable report (good for assertion messages)
- `results.generate_snapshot()` -- concise rule summaries (good for test output)
- `results.response` -- full axe-core JSON response
- `results.save_to_file("results.json")` -- export for further analysis

References:
- [axe-playwright-python on PyPI](https://pypi.org/project/axe-playwright-python/)
- [axe-playwright-python on GitHub](https://github.com/pamelafox/axe-playwright-python)
- [axe-playwright-python documentation](https://pamelafox.github.io/axe-playwright-python/usage/)

### Other Python tools considered

| Tool | Status | Notes |
|------|--------|-------|
| `pytest-playwright-axe` | Available on PyPI | Thinner wrapper, less documentation |
| `curlylint` | **Unmaintained / effectively deprecated** | No releases in 12+ months, removed from none-ls.nvim. Had good a11y rules but not safe to adopt. |
| `djlint` | **Already in project** | Has some accessibility rules (see Section 4) |

## 2. Playwright Accessibility Testing

Playwright has first-class accessibility testing support via axe-core. The official Playwright docs recommend using `@axe-core/playwright` (JavaScript) but the Python equivalent is `axe-playwright-python`.

### How it works

axe-core injects JavaScript into the page under test and analyzes the rendered DOM against WCAG rules. This catches issues that static template linting cannot (dynamic content, HTMX-loaded elements, computed styles, etc.).

### Integration with existing FLS Playwright setup

FLS already has:
- `pytest-playwright` in dependencies
- A `playwright` pytest marker
- GitHub Actions job for Playwright tests with Chromium
- `live_server` fixture via pytest-django

Adding accessibility testing requires only:
1. `uv add axe-playwright-python`
2. Creating an `axe` fixture or helper
3. Adding accessibility assertions to existing or new e2e tests

### Suggested fixture for conftest.py

```python
from axe_playwright_python.sync_playwright import Axe

@pytest.fixture
def check_a11y():
    """Run axe-core accessibility checks on a page."""
    def _check(page, context=""):
        results = Axe().run(page)
        assert results.violations_count == 0, (
            f"Accessibility violations{f' ({context})' if context else ''}:\n"
            f"{results.generate_report()}"
        )
    return _check
```

References:
- [Playwright accessibility testing docs](https://playwright.dev/docs/accessibility-testing)
- [Blog: Automated accessibility audits for Python web apps](https://blog.pamelafox.org/2023/07/automated-accessibility-audits-for.html)

## 3. GitHub Actions for Accessibility

### Option A: Extend existing Playwright job (Recommended)

The simplest approach. Since FLS already runs Playwright tests in CI, adding `axe-playwright-python` to the test suite means accessibility tests run automatically with no new workflow needed. Just add the package dependency and write tests.

### Option B: pa11y-ci as a separate job

pa11y-ci is a standalone accessibility test runner that can crawl pages and test them.

```yaml
# .github/workflows/tests.yml (additional job)
a11y-tests:
  runs-on: ubuntu-latest
  steps:
    - uses: actions/checkout@v4
    - uses: actions/setup-node@v4
      with:
        node-version: 20
    - run: npm install -g pa11y-ci
    # Would need to start Django server, run pa11y against it
    - run: pa11y-ci --config .pa11yci.json
```

Configuration (`.pa11yci.json`):
```json
{
  "defaults": {
    "concurrency": 4,
    "standard": "WCAG2AA",
    "runners": ["axe"]
  },
  "urls": [
    "http://localhost:8000/",
    "http://localhost:8000/courses/"
  ]
}
```

**Downside**: Requires maintaining a separate URL list and spinning up the Django server. The Playwright approach is better because tests already handle server lifecycle and can test authenticated pages.

References:
- [pa11y-ci on GitHub](https://github.com/pa11y/pa11y-ci)
- [CivicActions: GitHub Actions + pa11y-ci with axe](https://accessibility.civicactions.com/posts/automated-accessibility-testing-leveraging-github-actions-and-pa11y-ci-with-axe)

### Option C: Lighthouse CI

Google Lighthouse includes accessibility audits as one category. Can be run via GitHub Actions.

```yaml
- name: Lighthouse CI
  uses: treosh/lighthouse-ci-action@v12
  with:
    urls: |
      http://localhost:8000/
    configPath: .lighthouserc.json
```

**Downside**: Lighthouse is broader (performance, SEO, etc.) and its accessibility checks are a subset of what axe-core provides directly. Better as a complement than a primary tool.

References:
- [Lighthouse CI on GitHub](https://github.com/GoogleChrome/lighthouse-ci)
- [treosh/lighthouse-ci-action](https://github.com/treosh/lighthouse-ci-action)

### Recommendation

**Use Option A** (extend existing Playwright tests with axe-playwright-python). It requires the least infrastructure, integrates with existing test patterns, and gives the best coverage since tests can authenticate and navigate to any page.

## 4. Linting / Static Analysis

### djLint (already in project)

FLS already uses djLint (`djlint>=1.36.4` in dev dependencies, configured in `pyproject.toml`). It includes these accessibility-relevant rules:

| Rule | Description |
|------|-------------|
| H005 | `<html>` tag should have `lang` attribute |
| H006 | `<img>` tag should have `height` and `width` attributes |
| H013 | `<img>` tag should have `alt` attribute |
| H016 | Missing `<title>` tag in HTML |
| H030 | Consider adding a `<meta>` description |

Current config ignores H006 (`ignore="H006"`). All other rules are enabled by default.

**Action needed**: Review whether H006 should remain ignored. Consider if any additional custom rules are needed.

References:
- [djLint linter rules](https://djlint.com/docs/linter/)

### curlylint (not recommended)

Had dedicated accessibility rules (image_alt, aria_role, html_has_lang, no_autofocus, tabindex_no_positive, django_forms_rendering) but is effectively unmaintained. Not safe to adopt for a new project.

References:
- [curlylint accessibility rules](https://www.curlylint.org/blog/accessibility-linting-rules/)
- [curlylint health analysis (Snyk)](https://snyk.io/advisor/python/curlylint)

### HTML validation

The Nu HTML Checker (v.Nu) can validate HTML output and catch some accessibility issues. Can be integrated via pytest by capturing response content and validating it. Lower priority than axe-core testing.

## 5. Claude/AI Integration for Accessibility

### Development workflow rules (Claude skills / CLAUDE.md)

Add accessibility requirements to the project's development conventions so Claude catches issues during development:

**Additions to CLAUDE.md conventions**:
```markdown
## Accessibility Conventions
- All `<img>` tags must have meaningful `alt` attributes (empty `alt=""` only for decorative images)
- All form inputs must have associated `<label>` elements (not just placeholder text)
- All interactive elements must be keyboard-accessible
- Use semantic HTML elements (`<nav>`, `<main>`, `<article>`, `<section>`, `<header>`, `<footer>`) over generic `<div>`
- ARIA attributes should only supplement, not replace, semantic HTML
- Color must not be the only means of conveying information
- All HTMX-loaded content must be announced to screen readers (use `aria-live` regions where appropriate)
- Heading levels must not skip (no `<h1>` followed by `<h3>`)
- Links must have descriptive text (no "click here" or "read more" without context)
```

**Claude skill for template review**: Create a skill that, when reviewing or creating templates, runs through an accessibility checklist. This could be added to the spec-driven development workflow so every new feature includes accessibility consideration.

**Pre-commit hook**: Add djLint as a pre-commit hook to catch template accessibility issues before code is committed:
```yaml
# .pre-commit-config.yaml
- repo: https://github.com/djlint/djLint
  rev: v1.36.4
  hooks:
    - id: djlint-django
```

### What AI can catch during development

- Missing alt text, labels, ARIA attributes in templates
- Non-semantic HTML structure
- Missing keyboard event handlers alongside mouse handlers
- Color contrast issues (if given design tokens)
- Heading hierarchy problems
- Missing landmark regions

### What AI cannot reliably catch

- Whether alt text is actually meaningful
- Whether the tab order makes sense in context
- Screen reader announcement quality
- Whether ARIA live regions update at the right time
- Complex widget interaction patterns

## 6. What Can and Cannot Be Automated

### Automatable (approximately 30-50% of WCAG 2.1 criteria)

| Category | Examples | Tool |
|----------|----------|------|
| Missing attributes | alt text absent, form labels missing, lang attribute missing | axe-core, djLint |
| Color contrast | Text/background contrast ratios below WCAG thresholds | axe-core |
| DOM structure | Heading hierarchy, list markup, table headers | axe-core |
| ARIA validity | Invalid roles, incorrect attributes, state mismatches | axe-core |
| Keyboard traps | Focus never leaves a component | axe-core (partial) |
| Duplicate IDs | Multiple elements with same ID | axe-core |
| Link/button text | Empty links, empty buttons | axe-core |
| Viewport meta | Prevents zoom, disables scaling | axe-core, djLint |

### Requires manual testing (approximately 50-70% of WCAG criteria)

| Category | Why automation fails |
|----------|---------------------|
| Alt text quality | Automation can detect presence, not whether the text is meaningful |
| Reading order | Logical reading order requires human judgment |
| Screen reader experience | Must test with JAWS, NVDA, or VoiceOver to verify announcements |
| Keyboard navigation flow | Tab order sensibility is contextual |
| Error identification | Whether error messages are clear and helpful |
| Content reflow | Whether content remains usable at 400% zoom |
| Cognitive load | Whether the interface is understandable |
| Motion/animation | Whether animations can be paused and are not disorienting |
| Touch target size | Whether touch targets are large enough (partially automatable) |

### Key insight

Automated tools catch the **presence** of accessibility features but not their **quality**. A page can pass all automated checks and still be unusable for people with disabilities. Automated testing is a baseline, not a finish line.

References:
- [Deque: Automated Accessibility Coverage Report](https://www.deque.com/automated-accessibility-coverage-report/)
- [Accessible.org: Scans reliably flag 13% of WCAG criteria](https://accessible.org/automated-scans-wcag/)
- [TestParty: Automated vs Manual Accessibility Testing](https://testparty.ai/blog/automated-vs-manual-accessibility-testing)

## 7. Recommended CI Pipeline Setup

### Tier 1: Immediate (low effort, high value)

1. **Add `axe-playwright-python`** to project dependencies
2. **Create a shared `check_a11y` fixture** in `tests/e2e/conftest.py`
3. **Add accessibility assertions to existing Playwright tests** -- after each page navigation, run axe
4. **Enable djLint in pre-commit** for template-level checks
5. **Add accessibility conventions to CLAUDE.md** so Claude enforces standards during development

### Tier 2: Short-term (moderate effort)

6. **Create dedicated accessibility test file** (`tests/e2e/test_accessibility.py`) that crawls key pages and runs axe on each
7. **Add a Claude skill for accessibility review** that checks templates against a11y standards
8. **Update spec-driven development workflow** to include accessibility as a requirement for new features

### Tier 3: Nice-to-have (higher effort)

9. **Add Lighthouse CI** as a separate GitHub Actions job for broader audits (performance + accessibility + SEO)
10. **Set up manual testing schedule** with screen reader testing checklist
11. **Add axe-core impact level thresholds** -- initially allow minor/moderate violations, fail only on serious/critical, then tighten over time

### Pipeline flow

```
Developer writes code
    |
    v
Pre-commit: djLint checks templates (static analysis)
    |
    v
Claude review: Accessibility conventions enforced during development
    |
    v
CI - Unit tests: pytest (no a11y here, backend only)
    |
    v
CI - Playwright tests: axe-core runs on every tested page
    |
    v
CI - (Optional) Lighthouse CI: Broader audit scores
    |
    v
Manual review: Screen reader testing for new features (periodic)
```

### Gradual adoption strategy

To avoid blocking all PRs immediately with existing violations:

1. Start by running axe in **report-only mode** (log violations but don't fail tests)
2. Fix existing violations page by page
3. Once a page is clean, add a strict assertion for that page
4. Eventually make all tests strict (zero violations = pass)

```python
# Phase 1: Report only
def test_page_a11y_audit(page, live_server):
    page.goto(f"{live_server.url}/courses/")
    results = Axe().run(page)
    if results.violations_count > 0:
        print(f"WARNING: {results.violations_count} a11y violations")
        print(results.generate_report())

# Phase 2: Strict (after fixing violations)
def test_page_a11y_strict(page, live_server):
    page.goto(f"{live_server.url}/courses/")
    results = Axe().run(page)
    assert results.violations_count == 0, results.generate_report()
```

## Summary: Tool Selection

| Layer | Tool | Status | Purpose |
|-------|------|--------|---------|
| Static template linting | **djLint** | Already installed | Catch missing alt, lang, title in templates |
| Runtime a11y testing | **axe-playwright-python** | To install | Full WCAG audit on rendered pages in CI |
| CI integration | **Existing Playwright job** | Already configured | No new workflow needed |
| Development workflow | **CLAUDE.md conventions** | To add | Catch issues during development |
| Pre-commit | **djLint hook** | To configure | Catch template issues before commit |
| Broader audits (optional) | **Lighthouse CI** | To add | Performance + a11y + SEO scores |
