# Research: what FLS's shipped default footer should contain

Scope: establish (A) what FLS already has in code to build a minimal legal footer from, and (B) what
a minimal legal footer conventionally/legally needs, so the two can be matched item-for-item. The
decision that `partials/footer.html` is a minimal legal footer (copyright + links to legal documents)
is settled and not re-argued here.

## Part A — what FLS already has

### A1. Legal documents: model, addressing, association with `Site`, zero-doc case

FLS does **not** store legal documents as database rows. There is no `LegalDoc` Django model. Instead:

- **`freedom_ls/accounts/legal_docs.py`** defines a frozen dataclass `LegalDoc` (`doc_type`,
  `site_domain`, `relative_path`, `version`, `title`, `effective_date`, `body_markdown`, `git_hash`) that is
  *assembled at request time*, not persisted. The content lives as files on disk, sourced from the
  **git blob at `HEAD`** (never the working tree), under:
  ```
  legal_docs/
  ├── _default/
  │   ├── terms.md
  │   └── privacy.md
  └── <site_domain>/        # optional per-site override
      ├── terms.md
      └── privacy.md
  ```
  Each file carries required YAML frontmatter: `version`, `title`, `type`, `effective_date`.
- **`ALLOWED_DOC_TYPES: frozenset[str] = frozenset({"terms", "privacy"})`** (`legal_docs.py:37`) — these
  are the *only* two document types FLS's legal-doc machinery knows about. There is no `cookies` or
  `accessibility` doc type today.
- **Lookup / association with `Site`:** `get_legal_doc(site: Site, doc_type: str) -> LegalDoc | None`
  (`legal_docs.py:220`) looks in `legal_docs/<site.domain>/<doc_type>.md` first, then falls back to
  `legal_docs/_default/<doc_type>.md`. Association with `Site` is by directory name matching
  `site.domain` — there is no FK from a document to a `Site` row, because there is no document row at all.
- **`has_legal_doc(site: Site, doc_type: str) -> bool`** (`legal_docs.py:277`) — returns whether
  `get_legal_doc` would resolve. Currently called only from Python (`accounts/forms.py` — gates the
  signup checkboxes; `accounts/checks.py` — a boot-time warning when a doc is missing but
  `require_terms_acceptance` is on). **It is not exposed to templates** (no template filter/tag, not in
  any context processor). A footer partial that wants to conditionally show/hide the Terms/Privacy link
  needs this exposed — see "what would need something new" below.
- **URL addressing:** `accounts/urls.py` — `path("legal/<str:doc_type>/", views.legal_doc_view, name="legal_doc")`,
  under `app_name = "accounts"`. So the URL name is **`accounts:legal_doc`**, resolved with
  `doc_type="terms"` or `doc_type="privacy"`, e.g. `{% url 'accounts:legal_doc' 'terms' %}`.
  `views.legal_doc_view` (`accounts/views.py:43`) 404s if `doc_type` isn't one of `{"terms", "privacy"}`
  or if `get_legal_doc` returns `None`.
- **Can a site have zero legal documents?** Yes. `get_legal_doc` returns `None` and `legal_doc_view`
  404s; nothing forces a document to exist. In practice **FLS's own repository ships both**
  `legal_docs/_default/terms.md` and `legal_docs/_default/privacy.md` (confirmed present at those
  paths), so FLS's own reference configuration always resolves both docs for every site — the
  zero-doc case only actually arises if a downstream project deletes both defaults and supplies no
  per-site override, or (per the registration skill) `legal_docs/` fails site-domain validation.
- **`fls-dev:registration` skill** (`claude_plugins/fls-dev/skills/registration/SKILL.md`) documents
  this whole area authoritatively — lookup order, frontmatter format, the "commit before it's visible"
  git-blob-at-HEAD rule, and the `LegalConsent` append-only consent-tracking model (`accounts/models.py`,
  `SiteAwareModel` — records `document_type`, `document_version`, `git_hash`, `timestamp`, `ip_address`
  per acceptance). `LegalConsent` is not itself footer-relevant, but confirms `"terms"` / `"privacy"`
  are the vocabulary's only two document types end to end.

### A2. Branding / site identity available in every template (no new plumbing)

Two context processors are registered in `config/settings_base.py:189-197` and run on every request:

- **`freedom_ls.site_aware_models.context_processors.site_config`** (`freedom_ls/site_aware_models/context_processors.py:9`) supplies:
  - `site_name` — the `Site` row's own `.name`
  - `site_title` — `site_conf[site_name]["SITE_TITLE"]` if configured, else `site_name`
  - `site_header` — `site_conf[site_name]["SITE_HEADER"]` if configured, else `site_name`
  - `header_logo_static_path` — from `config.HEADER_LOGO_STATIC_PATH` (settings, default `None`)
  - `favicon_static_path` — from `config.FAVICON_STATIC_PATH` (settings, default `None`)
  - `header_title` — `config.HEADER_TITLE` if set, else `site_title`
  - `header_title_style` — from `config.HEADER_TITLE_STYLE` (settings, default `None`)
- **`freedom_ls.accounts.context_processors.signup_policy`** (`freedom_ls/accounts/context_processors.py:6`)
  supplies only `allow_signups: bool`.

No context processor exposes a contact email, an organisation/legal-entity name distinct from
`site_name`/`HEADER_TITLE`, or a postal address. **There is no `contact_email` or equivalent template
variable anywhere in FLS** (confirmed by grep across `freedom_ls/` and `config/`).

The canonical "what is this installation called" helper is **`site_display_name(site)`**
(`freedom_ls/site_aware_models/models.py:85`): returns `config.HEADER_TITLE` if set, else `site.name`.
Its docstring states this is deliberately the *one* answer shared by the site header, outbound email,
and the cohort report, "so a project that renamed itself in one place is not still called something
else in another." A footer copyright line should use this same value for the same reason — but note
`site_display_name` itself is not in the template context under that name; `header_title` (from
`site_config`) is the already-injected template variable carrying the equivalent value
(`header_title = config.HEADER_TITLE or site_title`, and `site_title` falls back to `site_name`).

### A3. Copyright / organisation-name value

No dedicated copyright-holder or legal-entity-name setting exists. Candidates found and their fitness:

- **`Site.name`** (Django's own `contrib.sites.models.Site`) / **`header_title`** template variable —
  fits: it's exactly the value FLS already uses for the copyright line in its **outbound email footer**
  (see A4 below). This is "data FLS already has."
- **`freedom_ls.organisations.models.Organisation`** — a real model with `name`, `logo`,
  `logo_on_dark`, `wordmark_name` fields, used on the cohort report cover
  (`data.organisation.name`, `data-meta="organisation"` hook). Its own docstring: *"the tenancy layer
  that sits below a Site."* This is a **per-cohort/per-client organisation** (SiteAwareModel — many can
  exist per site), not the platform operator/legal entity. **Wrong fit for a site-wide footer
  copyright line** — there is no single "the" Organisation for a site to key a global footer off.
- `docs/product/configuration-and-extension.md` "Branding" section lists only `HEADER_LOGO_STATIC_PATH`,
  `HEADER_LOGO_ON_DARK_STATIC_PATH`, `FAVICON_STATIC_PATH`, `HEADER_TITLE`, `HEADER_TITLE_STYLE`,
  `EMAIL_LOGO_STATIC_PATH`. No copyright-holder setting.
- `freedom_ls/base/app_settings.py` / `freedom_ls/site_aware_models/config.py` (`SiteAwareModelsConfig`)
  confirm the same list — no `COPYRIGHT_HOLDER` or similar `Setting`.

**Conclusion: a copyright line can be rendered today from data FLS already has** (`site.name` /
`header_title`, i.e. `site_display_name`), the same value the email footer already uses. No new field
is required to render *a* copyright line — only to render one naming a distinct legal entity from the
tenant's own display name (e.g. if the operator's registered company name differs from the friendly
site name), which is out of scope for "minimal."

### A4. Existing footers elsewhere in FLS (to not contradict)

- **Outbound email footer** — `freedom_ls/accounts/templates/emails/base_email.html:31-36`:
  ```django
  <tr>
    <td class="email-footer">
      {% include "emails/includes/footer_links.html" %}
      <p style="margin: 8px 0 0 0;">&copy; {% now "Y" %} {{ email_label|default:current_site.name }} | {{ current_site.domain }}</p>
    </td>
  </tr>
  ```
  This is the closest existing precedent for the exact pattern requested:
  - `&copy;` entity (not the word "Copyright")
  - `{% now "Y" %}` — Django's built-in template tag, auto-updating current year, **not hardcoded**
  - `{{ email_label|default:current_site.name }}` — `email_label` is injected by
    `freedom_ls/accounts/allauth_account_adapter.py:89` as `site_display_name(current_site)`
    (i.e. `HEADER_TITLE` or site name) when sending through the allauth adapter; falls back to
    `current_site.name` directly when `email_label` isn't in context. Either way, it resolves to the
    same "installation display name" concept as A2/A3.
  - `{{ current_site.domain }}` appended after a `|` separator
  - **`emails/includes/footer_links.html`** (`freedom_ls/accounts/templates/emails/includes/footer_links.html`):
    ```django
    {# Empty by default. Override in downstream projects to add privacy policy, terms, etc. #}
    ```
    This is a one-line comment, empty by default — FLS's own email footer **does not link to
    Terms/Privacy out of the box**, and explicitly documents that as a downstream override point. This
    is the one place FLS's existing chrome is inconsistent with the footer-area decision: the settled
    design wants the *web* footer to link to legal docs by default, while the *email* footer
    deliberately ships empty and defers to downstream. Worth noting so the new `partials/footer.html`
    doesn't read as contradicting `footer_links.html`'s "empty by default" precedent — the difference is
    defensible (email footer is not a legal footer requirement in the same way, and FLS's decision here
    is explicitly to *not* leave the web footer empty), but it's an existing asymmetry, not something
    this research invents.

- **PDF cohort report** — `freedom_ls/reports/templates/reports/partials/title_page.html`. No copyright
  line or legal-document links. Its `data-meta="organisation"` row shows `data.organisation.name` (the
  learner_management `Organisation`, A3 above) — an internal-audience PDF for the operator, not
  learner-facing chrome, so it's not a footer-content precedent to align with. `data.site_name` appears
  in the "Powered by" band, giving another (rare) example of using the installation's own display name
  in report chrome, consistent with `site_display_name`.

### A5. Where this needs documenting

- **`docs/product/configuration-and-extension.md`** — the "Branding" section (lines 15-27) lists
  settings that control chrome without template edits; a shipped `partials/footer.html` overridable at
  Tier 3 is a *template* extension point, so it belongs instead in the "Three-Tier Theming" section
  (lines 28-40) as an example of Tier 3 whole-file shadowing, and/or gets its own bullet in the
  page's Summary. The doc currently gives no example of a shadowable *partial* (only cotton components
  and "app template or partial" in `theme-fls.md`), so `partials/footer.html` would be a good first
  concrete instance to name.
- **`docs/how tos/theme-fls.md`**:
  - **Tier 3 section** (~line 278 onward) — "Template overrides" already documents the "app template or
    partial override" pattern generically (`themes/my-theme/templates/learner_interface/partials/course_card_registered.html`
    as its example). `partials/footer.html` fits this pattern exactly — a downstream project overrides
    wholesale at `templates/partials/footer.html`, no `theme.css` layer, no `<c-vars>` contract (it's a
    partial, not a cotton component) — but the doc should say so explicitly, since Part A2/A3 above show
    the variables such an override could safely rely on (`site_name`, `header_title`,
    `favicon_static_path`, etc. — all already in every template's context) versus what it would have to
    supply itself (a distinct legal-entity name, a contact address, a cookie-preferences reopen control —
    none of which FLS injects today).
  - **"Structural hooks an override must keep" table** (~line 326) — currently lists `id`/`data-*`
    hooks FLS's own test suite asserts on, across `learner_interface`, `reports/partials`. If FLS adds
    conformance-suite or template-level assertions on the footer block/partial (e.g. that the
    `{% block footer %}` exists in `_base.html`, or that a footer partial exists at
    `partials/footer.html`), a new row belongs here so a downstream Tier-3 override knows what it must
    preserve. Nothing there today for a footer, because there is no footer today.
- **Conformance suite** (`freedom_ls/contrib/conformance/`, esp. `test_theme.py`) — confirmed by
  reading `test_theme.py`: it currently asserts nothing about `_base.html` structure or footer content.
  Since `docs/product/configuration-and-extension.md` states the conformance suite "confirms FLS's page
  and feature wiring resolves," adding the footer as a documented Tier-3 extension point (per above)
  is a natural candidate for a conformance check later (e.g. "the footer block renders without
  erroring"), but nothing currently exists to update — this is a gap to flag for the follow-on
  implementation work, not a finding about existing structure.

---

## Part B — what a minimal legal footer should contain

### B1. The conventional minimum, item by item

| Item | Status | Regime / source |
|---|---|---|
| Copyright notice | Strong convention, not a legal requirement (copyright exists without the notice) | General practice — [Staying Current: Automating Copyright Year Updates](https://johnkavanagh.co.uk/articles/staying-current-by-automating-copyright-year-updates/), [Kalamazoo Web Design — Do Website Copyright Dates Need to Be Updated Every Year?](https://www.kalamazoo-webdesign.com/do-website-copyright-dates-need-to-be-updated-every-year/) |
| Terms of service link | Strong convention / contractual necessity if a ToS is to be enforceable at all (needs to be findable/presented) | General e-commerce/consumer practice |
| Privacy policy link | **Legal obligation** wherever personal data is processed | GDPR Arts. 12–14 (EU/UK), POPIA (South Africa) — see B2 |
| Cookie notice / preferences link | **Legal obligation** if non-essential cookies are set | ePrivacy Directive + GDPR consent standard (EU/UK); POPIA has no cookie-specific consent-banner mandate but personal-info-processing consent principles still apply |
| Accessibility statement link | **Legal obligation** for in-scope EU/UK public-sector and (from June 28 2025) many private-sector services; convention elsewhere | European Accessibility Act + EN 301 549 / WCAG — see B2 |
| Contact (support/legal) | Strong convention; POPIA privacy policies specifically require responsible-party and Information Officer contact details | POPIA — [PocketAdvisor — privacy policy template South Africa](https://pocketadvisor.co.za/privacy-policy-template-south-africa/) |

### B2. Obligations that actually bite, and whose responsibility

Framing per the task: FLS is a product installed by others. The question for each obligation is
"what must FLS make *possible* for the downstream operator" not "what must FLS itself assert" —
FLS is not the data controller or the in-scope service; the deploying organisation is.

- **GDPR / ePrivacy (EU/UK).**
  - GDPR requires a findable privacy notice (Arts. 12–14); ePrivacy (plus UK PECR) requires consent
    before setting non-essential cookies, and — per current guidance — that consent/preferences be
    reachable persistently, "typically a small floating button or a footer link, so a visitor can
    change their mind at any time" ([CookieYes — EU Cookie Compliance 2026 Guide](https://www.cookieyes.com/blog/eu-cookie-compliance/)).
  - **FLS's own `docs/product/signup-attribution.md`** already documents that FLS ships a tracking
    cookie (`fls_attribution`) with **no consent gate**, and states plainly: *"FLS is installed into
    someone else's project, and that operator is the data controller… The tracking cookie almost
    certainly needs consent… FLS ships no consent gate."* This is the existing, explicit precedent for
    the "downstream operator's job, FLS makes it possible" framing the footer should follow: FLS's
    minimal footer should provide the *link* (to a legal doc / cookie notice), not implement consent
    UI or banner logic itself.
  - Controller identity: GDPR requires the data controller be identifiable — this is exactly what a
    footer's privacy-policy link with a copyright/organisation line services, and it's the piece FLS
    *can* supply out of the box (site name + link to a `privacy` legal doc), leaving the *content* of
    the privacy doc (who the controller actually is) to the operator, which is already how
    `legal_docs/_default/privacy.md` works.
  - Sources: [ConsentPixel — GDPR Cookie Consent Requirements 2026](https://consentpixel.com/blogs/gdpr-cookie-consent-requirements/), [CookieYes — EU Cookie Compliance 2026 Guide](https://www.cookieyes.com/blog/eu-cookie-compliance/)

- **POPIA (South Africa).** FLS's own `docs/product/security-and-data-handling.md` has a "POPIA Data
  Residency" section, confirming the project already reasons about POPIA explicitly (it notes POPIA has
  no blanket data-residency mandate, and hosting choice is "a practical advantage, not a legal
  mandate"). POPIA requires a compliant privacy policy to name the responsible party and the appointed
  Information Officer, with contact details ([PocketAdvisor — privacy policy template South Africa](https://pocketadvisor.co.za/privacy-policy-template-south-africa/);
  [WiredWeb Services — POPIA Website Compliance Checklist 2026](https://wiredwebservices.co.za/popia-website-compliance-a-practical-2026-checklist/)).
  That content lives *inside* the privacy legal doc (`legal_docs/*/privacy.md`), which FLS already
  supports per-site — the footer's job is only to make that document reachable, which the settled
  design already does via the `privacy` link.

- **EU Accessibility Act / EN 301 549 / WCAG.** The EAA became enforceable **28 June 2025**; in-scope
  private-sector digital services need "an accurate accessibility declaration that shows whether or not
  your website and your app supports accessibility," per EN 301 549 Annex B/C — scope, standards
  referenced, conformance status, known limitations, and contact information for reporting accessibility
  issues ([Level Access — European Accessibility Act](https://www.levelaccess.com/compliance-overview/european-accessibility-act-eaa/)).
  A microenterprise exemption exists (<10 employees, ≤€2m turnover/balance sheet, services only) — see
  [Taylor Wessing — Key EU Accessibility Act exemptions](https://www.taylorwessing.com/en/interface/2025/accessibility/key-eu-accessibility-act-exemptions-and-the-challenges-they-pose).
  Whether a given downstream operator is in scope depends on its own size/turnover and whether it's a
  private or public-sector body — **not something FLS can determine** — so this is squarely an item
  FLS should *make possible* (a link slot for "Accessibility statement") rather than assert. **FLS has
  no accessibility-statement content or doc type today** — `ALLOWED_DOC_TYPES` is only
  `{"terms", "privacy"}` (A1). This is the one footer item, of the conventional set, that FLS's
  legal-docs machinery does not currently support at all — adding it would mean extending
  `ALLOWED_DOC_TYPES`, which is more than "minimal" for this piece of work.
  - Education-sector-specific note: search results did not surface an EAA carve-out specific to
    e-learning/education services beyond the general microenterprise exemption; treat education/LMS
    services as in-scope like any other digital service unless a downstream operator's own counsel
    determines otherwise.

### B3. What a copyright line needs to be meaningful

- **Holder**: the legal or trading name of the entity claiming copyright — convention is to use the
  real legal/trading name, not a marketing nickname, "so the notice points to whoever truly owns the
  content" ([John Kavanagh — Staying Current](https://johnkavanagh.co.uk/articles/staying-current-by-automating-copyright-year-updates/)).
  FLS's closest available value is `site_display_name` (`HEADER_TITLE` or `Site.name`) — see A2/A3.
  This is the tenant's *display* name, not necessarily its registered legal entity name; for many
  installations they'll coincide, but FLS cannot guarantee that.
- **Year**: current convention is `© <current year> <Holder>`, auto-updated rather than hardcoded —
  "an outdated year doesn't void your copyright, but it can make a website feel neglected"
  ([Kalamazoo Web Design](https://www.kalamazoo-webdesign.com/do-website-copyright-dates-need-to-be-updated-every-year/); [It is 2026. Update Your Website Footer.](https://updateyourfooter.com/)).
  Django's `{% now "Y" %}` template tag is the exact mechanism FLS's own email footer already uses
  (A4) — no new capability needed.
- **`©` vs "Copyright"**: either is acceptable; `©` (or `&copy;`) is the more compact, common choice
  and is what FLS's email footer already uses.
- Legally, none of this is required for copyright to subsist — it's a trust/professionalism signal,
  not a compliance item ([Kalamazoo Web Design](https://www.kalamazoo-webdesign.com/do-website-copyright-dates-need-to-be-updated-every-year/)).

---

## The concrete answer: what `partials/footer.html` should render

| Item | Renders from | New plumbing needed? |
|---|---|---|
| Copyright line: `© {year} {holder}` | `{% now "Y" %}` (Django built-in) + `header_title` (already in every template's context via `site_config` context processor — resolves to `HEADER_TITLE` or `site_name`) | **No** — same pattern as `emails/base_email.html`'s existing `&copy; {% now "Y" %} {{ email_label|default:current_site.name }}` line |
| Terms of service link | `{% url 'accounts:legal_doc' 'terms' %}`, shown only when the doc resolves | **Yes, small** — `has_legal_doc(site, "terms")` exists in `freedom_ls/accounts/legal_docs.py` but is not exposed to templates today (only called from Python in `forms.py`/`checks.py`). Needs a context processor addition or template tag to reach the footer partial without a raw Python import in a template. |
| Privacy policy link | `{% url 'accounts:legal_doc' 'privacy' %}`, shown only when the doc resolves | **Yes, small** — same gap as above, for `has_legal_doc(site, "privacy")` |
| Cookie notice / preferences | — | **Yes, real gap.** FLS has no cookie-consent mechanism, no cookie legal-doc type, and `docs/product/signup-attribution.md` explicitly documents that FLS ships a tracking cookie with no consent gate. There is nothing to link to. Minimal footer can at most reuse the `privacy` doc link for this (common practice bundles cookie disclosure into the privacy policy) rather than add a distinct item — a genuinely separate cookie-preferences control is out of scope for "minimal" and not data FLS has. |
| Accessibility statement | — | **Yes, real gap.** `ALLOWED_DOC_TYPES` is `{"terms", "privacy"}` only — no third doc type, no URL, no content. Out of scope for a footer built only from what FLS already has; flagged as the most expensive missing item if this is ever required. |
| Contact (support/legal) email | — | **Yes, real gap.** No `contact_email`/`support_email` setting or context-processor value exists anywhere in FLS (confirmed by grep). Would need a new `Setting` (e.g. on `SiteAwareModelsConfig` or a new footer-specific config) plus a context-processor addition. |
| Site/organisation name (for the copyright line and/or a "powered by" mention) | `site_name` / `header_title` (already injected) | **No** |

### The degenerate case — a site with no legal documents configured

Because `has_legal_doc` gates the Terms and Privacy links, a site with **zero** resolvable legal
documents (both `legal_docs/_default/*.md` removed and no per-site override) renders a footer with:

- the copyright line (`© {year} {header_title}`) — always renders, since it depends only on
  always-present context values, never on `has_legal_doc`
- **no** Terms link, **no** Privacy link — both conditionally suppressed
- nothing else, since cookie/accessibility/contact links are not implemented at all today

This mirrors the existing pattern in `legal_doc_view` (404 when `get_legal_doc` returns `None`) and in
`accounts/checks.py` (boot-time warning, not a hard failure, when a doc is missing) — FLS already treats
"no legal doc for this site" as a valid, non-error state elsewhere, so the footer degrading to
"copyright line only" is consistent with how the rest of the legal-docs system already behaves, not a
new failure mode being invented for the footer.

---

status: ok
reason: Part A grounded in freedom_ls/accounts/legal_docs.py, models.py, context_processors.py, urls.py, views.py, the registration skill, and existing email/report footer precedent; Part B grounded in web research with sources cited inline. Two real gaps flagged (cookie-preferences and accessibility-statement doc type/content, plus a contact-email setting) as items FLS does not currently have data for.
