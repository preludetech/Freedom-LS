# Threat model: On-brand course content widgets

Threat model for `1. spec.md`. Mapped against **OWASP Top 10:2025**. The defining
characteristic of this feature is that **course-author markdown is untrusted input**
that flows through a `markdown → nh3 sanitise → cotton compile → Django render`
pipeline and is then displayed to students. Several new widgets widen the sanitiser
allowlist and one (`c-equation`/KaTeX) introduces a client-side rendering library that
runs *after* sanitisation. That post-sanitise execution surface is the highest-value
area of this model.

## 1. Assets at risk

- **Student sessions / cookies** — stealable via stored XSS in rendered content.
- **Student & educator accounts / PII** — reachable if an XSS payload acts on behalf
  of a viewer (CSRF token is exposed in the DOM via `<body hx-headers>`).
- **Content integrity** — what a student sees on a course page; a poisoned widget can
  deface or phish.
- **Cross-tenant isolation** — FLS is multi-site; content/files must not leak across
  sites (`SiteAwareModel`).
- **Server-side files** — `File` objects looked up by `get_file_by_path` for
  `c-picture` / `c-image-grid`.
- **The sanitiser allowlist itself** (`MARKDOWN_ALLOWED_TAGS`) — every new entry is a
  permanent widening of the trusted-HTML surface.

## 2. Threat actors

- **Malicious / compromised course author** (primary). Authors write the markdown that
  becomes widgets. They are *content* authors, not developers, and their input must be
  treated as untrusted — the whole nh3 pipeline exists for this. Highest-likelihood
  actor for this feature.
- **Authenticated student** (viewer). Mostly a *victim* of stored XSS, but also a
  potential actor if any widget reflects a request parameter (none currently planned).
- **Unauthenticated / external attacker** — relevant via third-party content
  (YouTube embeds, vendored KaTeX assets, KaTeX `\href`/`\includegraphics` resource
  loads) and supply-chain.
- **Cross-tenant tenant** — an author on site A trying to reference site B's files.

## 3. Attack vectors vs OWASP Top 10:2025 + controls + gaps

### A03 Injection — stored XSS through the markdown pipeline (PRIMARY RISK)

**Vector:** author embeds script-bearing markup, or abuses a new tag/attribute, to get
executable HTML past nh3 into a student's browser.

**Required controls**

1. Every new tag (`c-pull-quote`, `c-equation`, `c-image-grid`, `c-table`,
   `c-code-block`) and every new attribute on `c-youtube` / `c-picture` must be added
   to `MARKDOWN_ALLOWED_TAGS` with a **minimal, explicit attribute allowlist**. nh3
   strips anything not listed.
2. Author-controlled attribute values must map to **fixed role tokens / fixed CSS
   classes** inside the cotton template — never interpolated into `style=`, `class=`
   raw, `href`/`src` schemes, or `x-*` Alpine attributes.
3. Cotton templates run *after* nh3, so a template that echoes an attribute into a
   dangerous sink re-opens XSS even though nh3 passed the markup. Templates must rely on
   Django auto-escaping and must not `|safe` author input.

**Existing controls (verified):**
- `markdown_utils.render_markdown` runs `nh3.clean` with `tags`/`attributes` derived
  strictly from `MARKDOWN_ALLOWED_TAGS` before cotton compilation. Good.
- Current allowlist (`settings_base.py:284`) is tight: each tag exposes only a handful
  of named attributes.
- Existing templates render attributes through normal Django escaping (e.g.
  `picture.html` puts `{{ alt }}`, `{{ caption }}` into text/attribute positions; no
  `|safe`).

**Gaps to close in the plan / spec:**
- **G1 (must):** the spec defers exact attribute lists to the plan ("Exact attribute
  names/sets … in plan", §7). The threat model's requirement is that the
  `MARKDOWN_ALLOWED_TAGS` diff be **explicit and minimal**, and that no new attribute
  introduces a free-form URL or style sink. Call out specifically:
  - `c-pull-quote cite` and `c-pull-quote source` — `cite` is a URL. If rendered into
    `<blockquote cite="…">`, nh3's `cite` attribute is generally safe (no fetch), but
    if `source` ever becomes a link the scheme must be restricted to http/https
    (block `javascript:`/`data:`).
  - `c-youtube` chapter deep links / `?t=` — links must be constrained to the
    YouTube embed/host; do not let authors supply an arbitrary `href` that renders as
    a clickable link with an unrestricted scheme.
  - `c-table` `caption` and `c-code-block` `title`/`filename`/`language` — text only,
    rendered escaped; must not flow into class/style.
- **G2 (must):** confirm no new widget template uses `|safe`, `mark_safe`, or puts an
  author value into an `x-`/`@`/`:` Alpine binding. The CSP Alpine build forbids inline
  expressions, but a template that interpolates author text into a `data-*` attribute
  read by JS (as `scrollTableLabels`/`modal` do via `dataset`) must treat that value as
  untrusted in the JS too.

### A03 Injection — KaTeX client-side rendering (POST-SANITISE EXECUTION) (PRIMARY RISK)

**Vector:** `c-equation` hands author LaTeX to KaTeX, which renders in the browser
**after** nh3 has run, so nh3 never inspects KaTeX's output. Malicious LaTeX can
attempt `\href{javascript:…}`, `\url`, `\includegraphics`, or `\htmlData`/`\htmlClass`
(if HTML extensions enabled) to inject script or load external resources.

**Required controls**

1. **`trust: false`** (KaTeX default) so `\href`, `\url`, `\includegraphics` are
   disabled — the spec already mandates this (§3.2, §5.1). Do **not** pass a `trust`
   callback that re-enables any command.
2. **`throwOnError: false`** so malformed LaTeX degrades to readable source, not a JS
   error/blank page — spec mandates this.
3. **`strict`** handling / a constrained, fixed macro set — do not expose
   author-definable macros that could re-enable HTML output. KaTeX's `\html*` commands
   require `trust`, so `trust:false` covers them, but verify no `globalGroup`/macro
   escape.
4. **LaTeX delivered as text, not pre-parsed HTML** — the source must reach the browser
   as text content that nh3 already passed, and the init hook reads `.textContent`
   (not `innerHTML`) before typesetting. Spec calls this out; the plan must specify the
   exact DOM read.
5. **Widget-scoped rendering**, not a global `$$`/`$` auto-render, so the typesetter
   only touches `c-equation` containers and cannot be triggered by incidental `$`
   currency text elsewhere on the page. Spec leans this way; make it firm.

**Existing controls:** none yet — KaTeX is new. The CSP (`SECURE_CSP_REPORT_ONLY`)
is **report-only**, so it will *not block* a `\includegraphics`-style external fetch or
a `script-src` violation; it only reports. See A05 below.

**Gaps to close:**
- **G3 (must):** the plan must pin the KaTeX config object verbatim (`trust:false`,
  `throwOnError:false`, strict/macros) and the exact DOM API used to read author LaTeX
  (`textContent`), and confirm the renderer is scoped to `c-equation` containers only.
- **G4 (should):** decide whether `img-src`/`connect-src`/`font-src` in CSP need a KaTeX
  font entry. KaTeX fonts are vendored same-origin (`CSP.SELF` already covers them), so
  no relaxation should be needed — **explicitly confirm no CSP relaxation is required
  for KaTeX**, which is itself a security property worth stating.

### A08 Software & Data Integrity Failures — supply chain (vendored + CDN assets)

**Vector:** Alpine (currently loaded from `cdn.jsdelivr.net` in `_base.html`) and the
newly-vendored KaTeX JS/CSS/fonts. A compromised/swapped asset runs in every content
page.

**Required controls**

1. **Vendor KaTeX into static assets** and serve same-origin (spec §3.2 already says
   vendor, not CDN). Pin the exact version.
2. Prefer SRI / pinned versions for any remaining CDN script (Alpine is pre-existing
   and out of this spec's scope, but worth a note).

**Existing controls:** content_engine Alpine components are loaded same-origin via
`{% static %}` (`_base.html:24`), matching §2.3.

**Gaps:**
- **G5 (should):** confirm KaTeX is vendored + version-pinned and loaded via `{% static %}`,
  not a CDN. The spec says "vendor"; make it explicit in the plan that no new CDN
  origin is added (which would also avoid a CSP `script-src`/`font-src` change).

### A05 Security Misconfiguration — CSP is report-only

**Vector:** `SECURE_CSP_REPORT_ONLY` (settings_base.py:363) means the policy is **not
enforced**. `script-src` also allows `UNSAFE_INLINE`. So even though the CSP would
*report* an injected inline script, it would not *block* it — CSP is not a mitigating
control for the XSS vectors above; nh3 + the allowlist are the real defence.

**Required control:** treat nh3 + minimal allowlist + KaTeX `trust:false` as the
**sole** XSS defences; do not rely on CSP to catch a widget mistake.

**Gaps:**
- **G6 (note / out-of-scope but flag):** CSP being report-only and `script-src`
  allowing `unsafe-inline` is a pre-existing, app-wide posture, **not introduced by
  this spec**. Flag it so the plan/security reviewer knows the defence-in-depth net is
  weaker than it looks, and so the KaTeX assets don't get a false sense of CSP
  protection. Do not silently rely on `frame-src` (which *does* already constrain
  YouTube — good) as proof the rest is enforced.

### A01 Broken Access Control — file lookups & cross-tenant isolation

**Vector:** `c-picture` / `c-image-grid` resolve `src` via `get_file_by_path`. A
malicious `src` could attempt path traversal (`../`) or reference another tenant's
file.

**Required controls**

1. Resolve only within the content root — keep using
   `content_instance.calculate_path_from_root` + a `File` ORM lookup (no filesystem
   access from author input). Spec §5.4 mandates this.
2. The `File` lookup must remain **site-scoped** so site A's content cannot resolve
   site B's file.

**Existing controls (verified):** `get_file_by_path` (content_tags.py:10) takes the
author path, runs it through `calculate_path_from_root`, and does a `File.objects.get`
— ORM only, no `open()`/path join to disk from the author string.

**Gaps:**
- **G7 (should-verify):** confirm `calculate_path_from_root` normalises/rejects `..`
  traversal so an author can't escape the content root, and confirm the `File` query is
  site-scoped (via `SiteAwareModel`/default manager) so the lookup can't cross tenants.
  `c-image-grid` reuses this same lookup for each thumbnail — same guarantee applies
  per image. This is a verification item, not a known break.

### A04 Insecure Design — clickjacking / iframe & lightbox UX

**Vector:** YouTube iframe embed and the lightbox `role="dialog"`. Embeds are already
constrained; the new chapter deep-links must not become an open-redirect/arbitrary-link
vector.

**Required controls:** keep the fixed `https://www.youtube.com/embed/{{video_id}}`
template + `referrerpolicy` (youtube.html); chapter `?t=` links restricted to that
embed/YouTube host (spec §5.3). `frame-src` CSP already whitelists only youtube
origins (settings_base.py:369) — good, and this one *is* enforced regardless of
report-only because it's in the same dict… (note: the whole policy is report-only, so
frame-src is also report-only — see G6).

**Gaps:**
- **G8 (must):** `video_id` is interpolated straight into the iframe `src`
  (`youtube.html:8`). It is currently treated as an opaque id. The new chapter feature
  must not let an author inject extra URL params or a different host through `video_id`
  or a chapter param — keep author input constrained to an id + numeric timestamp, and
  build the deep-link URL server-side from those constrained pieces, not from a
  free-form author URL.

### A06 Vulnerable & Outdated Components

**Vector:** KaTeX has had historical XSS CVEs (mostly via `\href`/`trust`). Vendoring a
stale copy reintroduces them.

**Gaps:**
- **G9 (should):** pin a current KaTeX version and record it so it can be tracked for
  future CVEs. `trust:false` already neutralises the main historical class.

### Not applicable / low for this feature

- **A02 Cryptographic Failures** — no new secrets/crypto in scope.
- **A07 Auth Failures** — no new auth surface; widgets render inside existing
  authenticated student pages.
- **A09 Logging/Alerting** — no security-relevant new events; CLAUDE.md says no
  logging unless asked. (CSP report-only already emits reports.)
- **A10 SSRF** — no server-side fetch of author URLs introduced. KaTeX resource loads
  are client-side and blocked by `trust:false` (G3). `get_file_by_path` is ORM-only.
  Keep it that way.

## 4. Gap summary (action items for the spec/plan)

| ID | Sev | Gap |
|----|-----|-----|
| G1 | must | Pin an explicit, **minimal** `MARKDOWN_ALLOWED_TAGS` diff; no new free-form URL/style/`href` sink. Restrict any link scheme to http/https. |
| G2 | must | No new widget template may use `|safe`/`mark_safe` or interpolate author values into Alpine `x-`/`@`/`:` bindings; treat author values read via `dataset` in JS as untrusted. |
| G3 | must | KaTeX config pinned verbatim: `trust:false`, `throwOnError:false`, constrained macros; read LaTeX via `textContent`; render scoped to `c-equation` only. |
| G4 | should | Confirm KaTeX needs **no** CSP relaxation (fonts/JS vendored same-origin under `CSP.SELF`). |
| G5 | should | Vendor + version-pin KaTeX via `{% static %}`; add no new CDN origin. |
| G6 | note | Flag that app CSP is **report-only** + `script-src 'unsafe-inline'`; nh3/allowlist/`trust:false` are the real XSS defences — do not lean on CSP. |
| G7 | should | Verify `calculate_path_from_root` blocks `..` traversal and the `File` lookup is site-scoped (cross-tenant isolation), incl. each `c-image-grid` thumbnail. |
| G8 | must | `c-youtube` chapter deep-links built server-side from a constrained id + numeric timestamp; no free-form author URL/host/extra params via `video_id` or chapter input. |
| G9 | should | Pin a current, non-vulnerable KaTeX version and record it for CVE tracking. |

**Net:** the spec already names most of these (§3.2, §5), and the existing pipeline
(nh3 + tight allowlist + ORM file lookup + constrained YouTube embed) implements the
core controls well. The new, genuinely-new risk surfaces are **KaTeX post-sanitise
client-side execution (G3/G4/G5/G9)** and the **discipline of the allowlist diff +
no-sink templates (G1/G2/G8)**. Folding G1–G9 into the plan (and the plan security
review) closes the model.
