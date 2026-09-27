# Research: rendering a Claude Design design locally and screenshotting its artboards

A spike run on 2026-09-27 against sections 1 and 2 of `User Communication.html` (project
`019df696-b642-74bb-a97b-ad6a760b0491`). It worked. The ten screenshots are in `design_screenshots/`.

## What was done

1. **Sync.** At depth 0, `DesignSync.get_file` read `User Communication.html`, `design-canvas.jsx`,
   `design-system/kit.css`, `design-system/colors_and_type.css`, `uc/uc.css`, `uc/uc-data.jsx`,
   `uc/uc-shell.jsx` and `uc/uc-notify.jsx`. Each was written to a scratch directory with `Write`.
   For speed, the spike kept only the parts sections 1 and 2 use. A real sync copies files whole.
2. **Flat canvas.** Claude Design canvases use a pan/zoom component, `design-canvas.jsx`
   (`DesignCanvas`, `DCSection`, `DCArtboard`, `DCPostIt`). It opens at 30% zoom inside a
   `100vh` viewport with `overflow:hidden`, so artboards can't be screenshotted as they are. The
   spike replaced it with a flat stand-in that exports the same four names and lays every artboard
   out at 1:1 in normal flow, each wrapped in `data-artboard="<section-id>/<artboard-id>"` (source
   below). The entry HTML loads the stand-in in place of `design-canvas.jsx`. Nothing else changes.
3. **Serve.** `python3 -m http.server 8765 --bind 127.0.0.1` in the scratch directory. `file://`
   won't work because Babel-standalone fetches each `text/babel` script by URL.
4. **Screenshot.** A `general-purpose` subagent loaded the Playwright MCP tools through
   `ToolSearch`, resized to 1440x900, opened the page, waited three seconds for Babel, and took
   one element screenshot per artboard. `browser_take_screenshot` accepts a CSS selector as its
   target directly (`[data-artboard="uc-2-centre/pop"]`), no snapshot refs needed. Each PNG came
   out at the artboard's natural size, including the 1800px-tall long list. The run took about 40
   seconds.

## What rendered and what didn't

- React, ReactDOM, Babel-standalone and the Phosphor icon font all load from unpkg. The
  browser had network access to unpkg, and all 113 icons rendered.
- **Binary assets don't come through DesignSync.** `get_file` on `design-system/assets/logo-color.png`
  returned base64 flagged `truncated: true` at the 256 KiB cap. The logo is a 404 in every
  screenshot, and the header shows only the site name. The TTF fonts weren't synced, so text
  renders in the system fallback. Neither matters for FLS, which takes neither the design's fonts
  nor its logo. It does mean the screenshots are not pixel-exact copies of what the designer saw.
- **Rendering shows what reading the code misses.** `uc.css` gives `.uc-day` (the day headings)
  `font-size:12px`, but `.uc h2` has higher specificity and wins, so the rendered headings are
  18px ("TODAY", "MONDAY 21 SEPTEMBER" in `uc-2-centre__pop.png`). An agent reading the CSS would
  build 12px headings. An agent looking at the picture builds what the designer actually saw.

## Friction to design around

- **Every byte passes through the model.** DesignSync returns content into context, and the
  model re-types it with `Write`. That costs roughly twice the file size in tokens, and a long
  file can be copied wrong. A copy error that breaks the JSX shows up as a render failure, but a
  subtle one (a changed value) would not. The sync step should write files whole and unedited,
  and never summarise or trim them.
- **Screenshot paths.** With a relative `filename`, Playwright MCP writes PNGs to the worktree
  root. The step must pass absolute paths. The MCP also leaves console logs and snapshot YAML in
  `.playwright-mcp/`, which is already gitignored.
- **Waiting.** A fixed three-second wait was enough on localhost. Polling for
  `document.querySelectorAll('[data-artboard]').length` to reach the expected count is sturdier.
- **One call per artboard.** Each screenshot is its own tool call. They batch fine in parallel.
  A single `browser_run_code_unsafe` loop could do them all at once (untested).
- **Resolution.** Screenshots are 1x (`scale: "css"`). `scale: "device"` gives sharper images at
  a larger file size. The ten 1x PNGs total about 830 KB, the largest 204 KB, all under the 1 MB
  `check-added-large-files` limit.
- **Designs that aren't canvases.** A Claude Design file that isn't built on `DesignCanvas` has
  no artboards to select. The fallback is to screenshot the whole page at 1280 and 375 wide.

## The flat canvas stand-in

```jsx
// Flat stand-in for Claude Design's design-canvas.jsx. Same exports
// (DesignCanvas, DCSection, DCArtboard, DCPostIt), but every artboard renders
// at 1:1 in normal document flow, so a browser can screenshot each one by
// selector: [data-artboard="<section-id>/<artboard-id>"].
function DesignCanvas({ children }) {
  return <div style={{ padding: 40, background: "#ECEEF3" }}>{children}</div>;
}

function DCArtboard() { return null; }

function DCSection({ id, title, subtitle, children }) {
  const boards = React.Children.toArray(children).filter((c) => c && c.type === DCArtboard);
  return (
    <section data-section={id} style={{ marginBottom: 80 }}>
      <h2 style={{ font: "600 24px system-ui", margin: "0 0 4px" }}>{title}</h2>
      {subtitle && <p style={{ font: "14px system-ui", margin: "0 0 24px", color: "#555" }}>{subtitle}</p>}
      <div style={{ display: "flex", flexWrap: "wrap", gap: 48, alignItems: "flex-start" }}>
        {boards.map((b) => {
          const { id: aid, label, width = 260, height = 480, children: body } = b.props;
          return (
            <figure key={aid} style={{ margin: 0 }}>
              <figcaption style={{ font: "13px system-ui", marginBottom: 6 }}>{label}</figcaption>
              <div data-artboard={`${id}/${aid}`} data-label={label}
                style={{ width, height, overflow: "hidden", background: "#fff" }}>{body}</div>
            </figure>
          );
        })}
      </div>
    </section>
  );
}

function DCPostIt({ children }) { return <aside>{children}</aside>; }

Object.assign(window, { DesignCanvas, DCSection, DCArtboard, DCPostIt });
```

## References

- `design_screenshots/` (the ten artboards: `uc-1-bell__{hd,hdm,pop,popm}.png`,
  `uc-2-centre__{pop,read,empty,long,popm,emptym}.png`)
- `research_claude_design_export.md` (why the sync goes through `DesignSync` rather than an export)
- [Playwright: element screenshots](https://playwright.dev/docs/screenshots#element-screenshot)
- [Babel standalone: script tags with `src`](https://babeljs.io/docs/babel-standalone)

status: ok
