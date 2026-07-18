# Research: Security considerations for a `c-mermaid` widget

Scope: author-supplied Mermaid.js diagram source rendered client-side inside course
content on FLS. Course authors are semi-trusted (staff/educators), but the
markdown -> nh3 -> cotton -> HTML pipeline must still prevent stored XSS, same
as it does for `c-equation` (KaTeX) and `c-code-block`.

## 0. How this maps onto the existing FLS pipeline

- `MARKDOWN_ALLOWED_TAGS` in `config/settings_base.py` allowlists `c-*` cotton
  tags and their attributes; nh3 strips anything else, including raw HTML
  inside the tag's *slot* text.
- `cotton/equation.html` is the closest analogue: the slot carries the raw
  LaTeX source as **text**, an Alpine component (`Alpine.data("equation", …)`
  in `freedom_ls/content_engine/static/content_engine/js/alpine-components.js`)
  reads it via `.textContent` (not `.innerHTML`) and hands it to a **vendored**
  (not CDN) copy of KaTeX with `trust: false` to block `\href`/`\url`/`\includegraphics`.
  Authors must HTML-escape `<`, `>`, `&` in the source (documented in
  `fls-content-plugin/skills/widget-reference/resources/c-equation.md`) so nh3
  doesn't eat diagram syntax before it reaches the slot.
- Alpine is loaded as the **CSP build** (`@alpinejs/csp`), which forbids
  inline JS expressions and requires `Alpine.data()` registration — this
  matters because Mermaid itself must not require `eval`/`new Function` or
  inline `<script>` execution to render, or it will need CSP carve-outs.
- `spec_dd/0. drafts/CSP-rollout/idea.md` confirms CSP is being tightened
  toward enforcing mode with no `unsafe-inline` for scripts — any mermaid
  integration should assume a strict CSP target, not `unsafe-inline`.

A `c-mermaid` widget should follow the exact same shape as `c-equation`:
raw Mermaid source as slot **text**, read via `.textContent`, rendered
client-side into an output node, with the *strictest* mermaid security
posture by default.

---

## 1. Mermaid `securityLevel`

Mermaid has rendered diagram text through a `securityLevel` gate since v8.2,
configured via `mermaid.initialize({ securityLevel: … })`. Four values:

| Level | HTML in labels/text | `click` (URL nav + JS callback) | Rendering context | Notes |
|---|---|---|---|---|
| **`strict`** (default) | HTML tags in text are **encoded** (escaped, shown as literal text, not executed) | **Disabled entirely** | Normal DOM | Safest non-iframe mode. This is mermaid's own default. |
| `antiscript` | HTML tags **allowed**, only `<script>` elements stripped | **Enabled** | Normal DOM | Still allows `onerror=`, `onclick=`, `<img>`, `<iframe>`, etc. — script-tag removal alone does not stop event-handler-based XSS. |
| `loose` | HTML tags **allowed**, unrestricted | **Enabled** (both `href` URL nav and `call` JS callback forms) | Normal DOM | The mode implicated in essentially every real-world mermaid XSS report (see §2). |
| `sandbox` | N/A — rendering happens inside a **sandboxed `<iframe>`** | Effectively neutralised: no JS executes in the parent page context | Sandboxed iframe | Strongest isolation but loses/complicates interactivity, sizing, theming, a11y (see §4). |

Mermaid's own docs state plainly: *"It is the site owner's responsibility to
discriminate between trustworthy and untrustworthy user-bases,"* and
recommend `strict` or `sandbox` — not `loose` — *"if rendering diagrams from
untrusted sources."* [Mermaid Usage docs](https://mermaid.js.org/config/usage.html)

**What's lost at `strict`:** `click` node interactions (both link-navigation
and JS-callback forms) and literal HTML inside labels (e.g. `<br/>` for
manual line breaks, `<b>`/`<i>` styling in node text). Text is still fully
supported; Mermaid has non-HTML alternatives for line breaks in most diagram
types (e.g. `\n` in flowchart labels is supported by the parser independent
of `htmlLabels`).

**Recommendation:** `strict` is the correct default for FLS (author content
is semi-trusted but XSS-must-still-be-prevented, matching the KaTeX
`trust:false` posture). See §5.

Sources:
- [Mermaid Usage / securityLevel docs](https://mermaid.js.org/config/usage.html)
- [Mermaid MermaidConfig interface](http://mermaid.js.org/config/setup/mermaid/interfaces/MermaidConfig.html)

---

## 2. Known XSS / injection vectors in Mermaid

Mermaid has a real, recurring XSS track record, almost entirely gated behind
permissive `securityLevel` or app-level misconfiguration:

- **`click` directive → JS callback or `javascript:` URL.** Flowchart/class/
  state diagrams support `click <nodeId> call <callbackFn>("tooltip")` and
  `click <nodeId> href "<url>"`. Under `loose`, both are live: a
  `javascript:` URL or an attacker-controlled callback name executes.
  Documented as the root cause of a real-world stored-XSS in Dify
  (`click Shape call href "javascript:alert(location.href)"`), and generalized
  in Snyk Labs' write-up on diagram-renderer exploitation. Sequence and Gantt
  diagrams have their own click/interaction syntax, so a sanitizer that only
  covers flowchart syntax leaves other diagram types exposed. [Snyk Labs — More than flowcharts: exploiting diagram renderers](https://labs.snyk.io/resources/exploiting-diagram-renderers/)
- **`%%{init}%%` directive overriding config, including `securityLevel`/`htmlLabels`, per-diagram.** Mermaid supports an in-source directive,
  `%%{init: {...}}%%`, that can override `mermaid.initialize()` config *for
  that one diagram*. Mermaid ships a `secure` array (default
  `['secure', 'securityLevel', 'startOnLoad', 'maxTextSize']`) whose listed
  keys are supposed to be immutable from within `%%{init}%%`. In practice this
  protection has been bypassed/misconfigured in the wild: the Docmost
  CVE-2026-23630 advisory describes an attacker using `%%{init}%%` to force
  `securityLevel: "loose"` and `htmlLabels: true` on a page that rendered the
  resulting SVG via `dangerouslySetInnerHTML` with no further sanitisation,
  achieving stored XSS via `<img src=x onerror=...>` in a node label.
  [Docmost GHSA-r4hj-mc62-jmwj](https://github.com/docmost/docmost/security/advisories/GHSA-r4hj-mc62-jmwj)
  — this means **the app's own render call, not just mermaid's internal
  defaults, is part of the trust boundary**: never widen the `secure` array,
  never spread caller-controlled objects into `mermaid.initialize()`, and
  don't assume `%%{init}%%` protections alone are sufficient.
- **HTML-in-labels / `htmlLabels: true` + `onerror`-style payloads.**
  CVE-2025-54881 (mermaid <11.10.0): malicious HTML injected into sequence
  diagram *participant* labels was processed and rendered without adequate
  sanitisation via `calculateMathMLDimensions`, e.g.
  `participant A as Alice<img src="x" onerror="...">`. Medium severity
  (CVSS 5.3), fixed in 11.10.0 by tightening the default `securityLevel` and
  adding DOMPurify sanitisation of the generated SVG.
  [Snyk SNYK-JS-MERMAID-12027649 / CVE-2025-54881](https://security.snyk.io/vuln/SNYK-JS-MERMAID-12027649)
- **`@mermaid-js/tiny` companion package XSS** — CVE-2025-54880, same family
  of issue in the lighter-weight tiny renderer.
  [Snyk SNYK-JS-MERMAIDJSTINY-12027658](https://security.snyk.io/vuln/SNYK-JS-MERMAIDJSTINY-12027658)
- **URL-sanitization XSS (historical)** — an early fix
  (`f4c335a`) hardened mermaid's URL sanitisation used for `click ... href`
  navigation. [mermaid-js commit f4c335a](https://github.com/mermaid-js/mermaid/commit/f4c335ad2f4059b3fbf9114f37440e77f8ca9a4d)
- **GitHub Security Lab GHSL-2021-1058 / GHSL-2021-1060** — two independent
  XSS findings in mermaid.js, part of the reason `securityLevel` and
  DOMPurify-based output sanitisation were introduced/hardened.
  [GitHub Security Lab advisory](https://securitylab.github.com/advisories/GHSL-2021-1058_GHSL-2021-1060_mermaid_js/)
- **GitLab HackerOne report** — stored XSS when viewing rendered mermaid
  diagrams, another real-world instance of the same class.
  [HackerOne #1212822](https://hackerone.com/reports/1212822)
- **Older CVE-2021-35513** — earlier XSS in mermaid, same lineage.
  [Snyk SNYK-JS-MERMAID-1314738](https://security.snyk.io/vuln/SNYK-JS-MERMAID-1314738)
- **OneUptime CVE-2026-32308 / GHSA-wvh5-6vjm-23qh** — "Stored XSS via
  Mermaid Diagram Rendering (securityLevel: 'loose')" — again, an app that
  explicitly opted into `loose`. [Miggo CVE-2026-32308](https://www.miggo.io/vulnerability-database/cve/CVE-2026-32308) / [OneUptime GHSA-wvh5-6vjm-23qh](https://github.com/OneUptime/oneuptime/security/advisories/GHSA-wvh5-6vjm-23qh)

**Mermaid's internal sanitisation and its limits.** Since the fixes above,
mermaid sanitises its generated SVG output with **DOMPurify** before
insertion (except when `securityLevel` is `loose`, where sanitisation is
intentionally skipped so `click`/HTML-label features can work; and except
inside `sandbox`, where the iframe boundary does the job instead). DOMPurify
is a strong, actively-maintained sanitizer, but two caveats apply:
1. It is only invoked as a *second* line of defence — it does not stop
   `click … call jsCallback()` under `loose`, because that's an intentional
   feature at that security level, not something DOMPurify is meant to catch.
2. DOMPurify itself has had documented mutation-XSS (mXSS) bypasses over the
   years (general library caveat, not mermaid-specific) — defence-in-depth
   (CSP, `strict` securityLevel, not `loose`) still matters even with it in
   the pipeline. [DOMPurify](https://github.com/cure53/dompurify) · [mXSS bypass write-up](https://mizu.re/post/exploring-the-dompurify-library-bypasses-and-fixes)

**Practical takeaway for FLS:** every cited real-world incident traces back
to `securityLevel: 'loose'` (or an app failing to lock down `%%{init}%%`
overrides) plus injecting the rendered SVG via `innerHTML`/
`dangerouslySetInnerHTML` without an additional sanitisation pass. FLS should
avoid both root causes (§5).

---

## 3. Interaction with the nh3 pre-sanitizer

Mermaid source will sit in the `c-mermaid` slot exactly like LaTeX does in
`c-equation` today — nh3 sanitises the *markdown-rendered HTML* before the
Alpine component ever sees it, and the mermaid JS library only receives
`.textContent`, never `.innerHTML`.

**This is net protective, for the same reason it is for KaTeX:** nh3 runs
first and will strip/escape any literal `<tag>` sequences an attacker tries
to smuggle into the slot as raw HTML (e.g. `<img src=x onerror=...>`,
`<script>`, or a `%%{init}%%` block wrapped to look like markup). Since the
mermaid renderer never receives real DOM nodes from the slot — only decoded
text — HTML-based injection into the *source* is blocked upstream, before
mermaid's own (weaker, `loose`-mode-bypassable) internal defences would even
be relevant. This is a strictly stronger posture than the app-level bugs in
§2, all of which involved *no* upstream HTML sanitisation of the diagram
source or its SVG output.

**What it mangles / the escaping burden on authors.** Mermaid's own syntax
legitimately uses `<` and `>` in several places that will collide with nh3's
tag-stripping behaviour if authors type them literally:

- **Edge/arrow syntax** — flowcharts use `-->`, `-.->` , `==>`, and
  (importantly) **`x-->` style variants are fine** because they don't start
  with `<`, but syntax that begins a token with `<` (e.g. bidirectional edges
  in some diagram types, or a literal `<` inside a label like `A[value < 10]`)
  will be interpreted by nh3 as the start of an HTML tag and eaten/mangled.
- **`<br/>` for manual line breaks inside labels** — a very common mermaid
  idiom (`A["Line 1<br/>Line 2"]`) is literal HTML and nh3 will strip it
  entirely (or leave broken text) unless escaped.
- **Comparison operators in labels** — `A --> B: x < y` (sequence/state
  diagram messages) collides the same way.

**What to document (mirroring `c-equation`'s escaping note):** authors must
HTML-escape `<`, `>`, and `&` in mermaid source exactly as they do for LaTeX
today — `&lt;`, `&gt;`, `&amp;` — including inside `<br/>` (write
`&lt;br/&gt;`, which mermaid's own label parser still recognises as a line
break after the browser/JS decodes the entity back to `<br/>` at
`.textContent` read time — since `.textContent` returns *decoded* characters,
the escaped form survives nh3 and is correctly un-escaped again before it
reaches mermaid's parser, same mechanism as `c-equation`). This should be a
one-line addition to a new `c-mermaid` widget-reference doc, e.g.:

```markdown
<c-mermaid>
flowchart TD
    A["value &lt; 10"] --&gt; B["done"]
</c-mermaid>
```

No new sanitizer behaviour is needed for this — it's the existing,
already-documented `c-equation`/`c-code-block` escaping convention applied to
a new widget, not a special case.

---

## 4. `sandbox` mode & iframes

`securityLevel: 'sandbox'` renders the diagram inside a sandboxed `<iframe>`
mermaid creates and manages itself. All script execution is confined to
(and effectively prevented within) that iframe context, which is the
strongest available isolation — even beyond `strict` — because it doesn't
rely on mermaid's own label-encoding/DOMPurify logic being bug-free (i.e. it
would have been immune to CVE-2025-54881-class issues in the *rendering*
step, since the iframe sandbox has no script execution regardless of what
DOMPurify does or doesn't catch).

**Tradeoffs mermaid's own docs call out:** sandbox mode "may hinder
interactive functionality of the diagram, like scripts, popups in the
sequence diagram, links to other tabs or targets, etc." In practice this
also means:
- **Sizing:** the iframe needs explicit height/width management or a
  postMessage-based resize handshake to avoid clipped/scrolling diagrams —
  more integration work than a plain inline SVG.
- **Theming:** CSS custom properties and Tailwind theme classes used
  elsewhere on the page don't automatically penetrate the iframe boundary;
  theme tokens must be re-injected into the iframe's own stylesheet, which
  is exactly the kind of complexity that caused the Dify regression cited in
  §2 (they downgraded `sandbox` → `loose` specifically to get theming
  working, and reopened the XSS hole doing so).
- **Accessibility:** an iframe boundary adds another landmark/focus-order
  hop for screen readers and complicates the `role="img"`/accessible-name
  pattern FLS already uses for `c-equation` (`role="math"` + `aria-label`).

**Is it warranted here?** No — not as the default. FLS course authors are
staff/educators (semi-trusted, not anonymous public input), the widget
doesn't need `click` interactivity or HTML labels, and `strict` already
removes the entire attack surface described in §2 (no `click`, no raw HTML
in labels) without the iframe integration cost. `sandbox` is worth keeping
in mind only if FLS later wants a *fully untrusted* diagram-source scenario
(e.g. student-submitted diagrams rendered for other students) — that's a
materially different trust boundary than course-author content and out of
scope for this widget's first cut.

Source: [Mermaid Usage docs — sandbox description](https://mermaid.js.org/config/usage.html)

---

## 5. Recommended safe defaults for FLS

Concrete posture for the `c-mermaid` cotton widget and its Alpine component:

1. **`securityLevel: 'strict'`** (mermaid's own default — set it explicitly
   anyway, don't rely on the library default silently staying safe across
   upgrades). This disables `click` entirely and HTML-encodes any HTML that
   makes it into a label, matching KaTeX's `trust:false` posture in
   `c-equation`.
2. **Do not enable `htmlLabels: true`.** Leave labels as text-only; document
   that `<br/>` needs escaping (§3) rather than opening HTML rendering in
   labels to make line breaks easier.
3. **Never widen the `secure` array** passed to `mermaid.initialize()` — use
   mermaid's default (`['secure', 'securityLevel', 'startOnLoad',
   'maxTextSize']`) or a superset, never a subset, so `%%{init}%%` blocks in
   author-supplied source cannot downgrade `securityLevel` or re-enable
   `htmlLabels` per-diagram (the exact mechanism behind the Docmost
   CVE-2026-23630 stored XSS in §2).
4. **No arbitrary click-callbacks, ever.** Don't add app-level support for
   `click … call <fn>` even as an opt-in "trusted author" feature — there is
   no reliable way to distinguish "trusted enough for JS callback execution"
   from "trusted enough to author markdown" within FLS's current author
   model, and the blast radius (arbitrary JS in every viewing student's
   session) is disproportionate to the feature value. If diagram
   click-to-navigate is wanted later, prefer implementing it as a separate,
   explicitly-reviewed FLS-level affordance (e.g. a `c-mermaid` `href`
   attribute wrapping the whole diagram in a real anchor) rather than
   exposing mermaid's `click href`/`click call` syntax to authors.
5. **Slot-as-text, `.textContent` read, vendored (non-CDN) mermaid build** —
   same shape as `c-equation`/KaTeX: keeps the library off any CDN-trust
   dependency and keeps the nh3 pass as the first line of defence over the
   diagram *source* (§3), before mermaid's own (loose-mode-bypassable)
   internal DOMPurify pass ever runs over the generated SVG.
6. **Pin a specific mermaid version ≥ 11.10.0** (the CVE-2025-54881 fix
   version) at initial integration, and track advisories going forward —
   mermaid's XSS history (§2) is frequent enough that this should be a
   dependency worth periodic security-update attention, not a "set and
   forget" vendor drop.
7. **`sandbox` mode is not needed for the initial widget** (§4) given
   `strict` + no click + no HTML labels already closes the known attack
   surface for this trust level; revisit only if FLS later renders diagrams
   from a genuinely untrusted source (e.g. student-authored).
8. **CSP compatibility check during implementation** — verify the specific
   mermaid version chosen doesn't require `unsafe-eval`/`new Function` for
   diagram parsing (some diagram types, e.g. `xychart`/expression evaluation,
   have historically used dynamic code execution internally); this repo is
   moving CSP to enforcing mode with no `unsafe-inline`/`unsafe-eval`
   (`spec_dd/0. drafts/CSP-rollout/idea.md`), so this is a compatibility gate,
   not just a defense-in-depth nicety.

This is a high-level idea-refinement posture, not an implementation plan —
the concrete `mermaid.initialize()` call, cotton template, and
widget-reference doc (mirroring `c-equation.md`) belong in the spec/plan
stage.

---

## References

- [Mermaid — Usage / securityLevel docs](https://mermaid.js.org/config/usage.html)
- [Mermaid — MermaidConfig interface (setup docs)](http://mermaid.js.org/config/setup/mermaid/interfaces/MermaidConfig.html)
- [Mermaid — Config Schema, `secure` array](https://mermaid.js.org/config/schema-docs/config-properties-secure.html)
- [Mermaid — 8.6.0 config changes (secure array introduction)](https://mermaid.js.org/config/8.6.0_docs.html)
- [Snyk Labs — More than flowcharts: exploiting diagram renderers](https://labs.snyk.io/resources/exploiting-diagram-renderers/)
- [Snyk — SNYK-JS-MERMAID-12027649 / CVE-2025-54881](https://security.snyk.io/vuln/SNYK-JS-MERMAID-12027649)
- [Snyk — SNYK-JS-MERMAIDJSTINY-12027658 / CVE-2025-54880](https://security.snyk.io/vuln/SNYK-JS-MERMAIDJSTINY-12027658)
- [Snyk — SNYK-JS-MERMAID-1314738 / CVE-2021-35513](https://security.snyk.io/vuln/SNYK-JS-MERMAID-1314738)
- [Docmost — GHSA-r4hj-mc62-jmwj / CVE-2026-23630 (init-directive securityLevel bypass)](https://github.com/docmost/docmost/security/advisories/GHSA-r4hj-mc62-jmwj)
- [OneUptime — GHSA-wvh5-6vjm-23qh / CVE-2026-32308](https://github.com/OneUptime/oneuptime/security/advisories/GHSA-wvh5-6vjm-23qh) · [Miggo CVE-2026-32308 writeup](https://www.miggo.io/vulnerability-database/cve/CVE-2026-32308)
- [GitHub Security Lab — GHSL-2021-1058 / GHSL-2021-1060 (mermaid.js)](https://securitylab.github.com/advisories/GHSL-2021-1058_GHSL-2021-1060_mermaid_js/)
- [HackerOne — GitLab stored XSS via mermaid rendering, #1212822](https://hackerone.com/reports/1212822)
- [mermaid-js — URL sanitization XSS fix, commit f4c335a](https://github.com/mermaid-js/mermaid/commit/f4c335ad2f4059b3fbf9114f37440e77f8ca9a4d)
- [DOMPurify](https://github.com/cure53/dompurify) · [DOMPurify mXSS bypass write-up](https://mizu.re/post/exploring-the-dompurify-library-bypasses-and-fixes)

## FLS files referenced

- `config/settings_base.py` (`MARKDOWN_ALLOWED_TAGS`)
- `freedom_ls/content_engine/templates/cotton/equation.html`
- `freedom_ls/content_engine/static/content_engine/js/alpine-components.js` (`Alpine.data("equation", …)`, `trust: false`)
- `fls-content-plugin/skills/widget-reference/resources/c-equation.md`
- `spec_dd/0. drafts/CSP-rollout/idea.md`

status: ok
