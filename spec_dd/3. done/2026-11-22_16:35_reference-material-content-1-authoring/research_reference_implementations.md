# Research: how reference implementations model reference material

Topic: `reference_implementations`. Facts only. Written from background knowledge of each tool's documented behaviour, not re-fetched in this run; each item lists the documentation URL to check against. Details marked (verify) are the ones least certain.

## Open edX (OLX)

- Course structure is an XML tree: `course.xml` -> `course/<run>.xml` holds `<chapter>` -> `<sequential>` -> `<vertical>` -> components. Each element is a url_name reference to a file in a type directory (`chapter/`, `sequential/`, `vertical/`, `html/`, `problem/`).
- Supplementary material sits outside the chapter tree:
  - Static tabs: `tabs/` directory and `<course>` children (`<static_tab>` / `<tab>` elements) pointing at html files. They appear as extra top-level course tabs (e.g. "Syllabus", "Resources"), not inside the outline.
  - Handouts: `info/handouts.html`; updates in `info/updates.html`. Both are fixed-name files, discovered by name.
  - Static assets under `static/` referenced as `/static/...`.
- Ordering: tabs are ordered by the order of the `<tab>`/`<static_tab>` elements in `course.xml`; outline order is the order of child elements.
- Completion/grading: only blocks inside the chapter tree participate in progress and grading; grading is configured in `grading_policy.json` by assignment type (`format` attribute on sequentials). Tab and handout content has no graded or completion state.
- Sharing across courses: not supported natively in OLX; content is copied or imported (export/import tarball). Library content (Content Libraries) is the separate sharing mechanism, pulled into a course by `<library_content>` / library-sourced blocks.
- URLs: https://docs.openedx.org/en/latest/educators/olx/ ; https://docs.openedx.org/en/latest/educators/navigation/course_outline.html ; https://docs.openedx.org/en/latest/educators/references/course_development/ (verify exact paths).

## Moodle

- Course is a set of sections (topics/weeks), each holding activities and resources (modules). "Resource" modules are File, Folder, Page, Book, URL, Label, IMS content package. "Activities" (Assignment, Quiz, Forum, ...) are the other family.
- Authoring is through the UI or backup/restore (`.mbz` archive with `moodle_backup.xml`, `sections/section_N/section.xml`, `activities/<mod>_<id>/`). There is no file-per-course authoring format.
- Ordering: a section's `sequence` field is a comma-separated list of course module ids; order is explicit in that list. Sections are ordered by `section` number.
- Completion: each module has a "completion tracking" setting (None / Manual / Automatic with conditions). With None the module does not count towards course completion; course completion is defined by explicit criteria (activity completion criteria chosen per module), not by everything on the page. Resources default to no tracking in many setups. Visibility can also be "available but not shown on course page" (stealth), so a resource can be linked without appearing in the list.
- Sharing: a module can be duplicated; a Folder/File can be reused through repositories ("Private files", "Server files", Course Files) and Moodle Sharing Cart/MoodleNet. Same module is not shared live between courses.
- URLs: https://docs.moodle.org/en/Resources ; https://docs.moodle.org/en/Activity_completion ; https://docs.moodle.org/en/Course_completion ; https://docs.moodle.org/dev/Backup_2.0_for_developers (backup format).

## Canvas LMS

- Content types: Modules (ordered, can have completion requirements and prerequisites), Pages, Files, Assignments, Quizzes, Discussions, Syllabus.
- Pages and Files exist independently of Modules; they are reachable from course navigation ("Pages" index, "Files" index) whether or not added to a module. Adding to a module is optional and gives ordering and (optionally) completion requirements.
- Ordering: only inside a module (drag order; export stores it in `imsmanifest.xml` / `course_settings/module_meta.xml` with `<position>`). Pages index is alphabetical/by date, not authored order.
- Completion: per module item "requirements" (view, mark done, submit, min score). Items with no requirement do not block module completion. Ungraded content has no assignment object; only Assignments/Quizzes/Graded discussions carry points.
- Authoring: UI, or Common Cartridge/Canvas course export (zip with `course_settings/`, `wiki_content/*.html`, `web_resources/`). Sharing across courses by import of selected content (Course Import Tool) or Canvas Commons; copies, not live links.
- URLs: https://community.canvaslms.com/t5/Canvas-Basics-Guide/tkb-p/canvaslms-basics-guide (Modules, Pages, Files guides); https://canvas.instructure.com/doc/api/modules.html (completion_requirements).

## Docusaurus

- Docs are markdown files in a `docs/` directory; sidebars in `sidebars.js` define ordering and grouping. Multiple named sidebars can exist; each doc set may be bound to one, and a doc not in any sidebar is still routable (reachable by URL, not listed) unless `docs.sidebarPath` autogeneration is used.
- Auto-discovery: `{type: 'autogenerated', dirName: 'x'}` builds a sidebar from a directory; order from `sidebar_position` front matter, `_category_.json` (`label`, `position`), or numeric filename prefixes (`01-intro.md`).
- Separate docs "instances" (multi-instance docs plugin) with own paths and sidebars are the way to hold a distinct section such as "API reference".
- Sharing: MDX partial imports (`import X from './_partial.md'`); files starting with `_` are excluded from routes. Symlink/shared content via plugin config, not a core feature.
- No concept of completion.
- URLs: https://docusaurus.io/docs/sidebar ; https://docusaurus.io/docs/sidebar/autogenerated ; https://docusaurus.io/docs/docs-multi-instance

## MkDocs (and Material for MkDocs)

- `mkdocs.yml` `nav:` is an explicit nested list of titles -> file paths. If `nav` is omitted, files in `docs_dir` are auto-discovered, alphabetical, with `index.md` first.
- Files in `docs_dir` that are not in `nav` are still built and reachable by URL; MkDocs logs an info message (configurable via `validation.nav.omitted_files`). They are therefore "published but unlisted".
- Plugins (`awesome-pages` with `.pages` files, `literate-nav`) add per-directory ordering and hide/collapse controls; `exclude_docs` (gitignore-style) removes files from the build entirely.
- Sharing across projects: monorepo plugin (`!include ../other/mkdocs.yml` in `nav`) and `mkdocs-multirepo`; snippets extension (`--8<--`) for shared fragments.
- URLs: https://www.mkdocs.org/user-guide/configuration/#nav ; https://www.mkdocs.org/user-guide/configuration/#validation ; https://squidfunk.github.io/mkdocs-material/setup/setting-up-navigation/

## GitBook

- Structure is `SUMMARY.md` (legacy, markdown list of links defining the table of contents) or the newer Git Sync with `.gitbook.yaml` (`root:`, `structure: {readme:, summary:}`). Pages not listed in SUMMARY.md are not part of the book.
- Ordering is the list order in SUMMARY.md; nesting is list indentation; `##` headings in SUMMARY.md create groups.
- Sharing: "reusable content" blocks (UI) and multiple spaces in a collection; variants for versions. No completion concept.
- URLs: https://docs.gitbook.com/getting-started/git-sync/content-configuration ; https://docs.gitbook.com/product-tour/reusable-content

## Hugo

- Content is a directory tree under `content/`; each top-level directory is a section. Ordering within a section is by front matter `weight`, then date, then title; `_index.md` carries section metadata (title, weight, `cascade`).
- Auto-discovery is the default: every markdown file is a page. Excluding is by front matter (`draft`, `build: {render: never, list: never}`) or config `ignoreFiles`. `build.list: never` keeps a page out of listings but routable; `render: never` hides it entirely.
- Sharing: module mounts (`module.mounts` in config, with `source`/`target`) can mount a directory from another module or path into `content/`, so one source directory is used in multiple sites/sections.
- No completion concept.
- URLs: https://gohugo.io/content-management/sections/ ; https://gohugo.io/content-management/build-options/ ; https://gohugo.io/hugo-modules/configuration/#module-configuration-mounts ; https://gohugo.io/methods/page/weight/

## Jupyter Book

- `_toc.yml` declares the table of contents: `format: jb-book`, `root: intro`, `chapters:` list of `- file: path` (extensionless), optional nested `sections:`, and `parts:` with `caption:` for grouping. `jb-article` format uses `sections:` only. Newer (v2/MyST) uses `project.toc` in `myst.yml` with `- file:`, `- title:`, `children:`.
- Ordering is the list order. Files not in the TOC give a build warning ("document isn't included in any toctree") and are not in navigation, but can be built; `exclude_patterns` in `_config.yml` removes them. `- glob: dir/*` entries do pattern auto-discovery; `- url:` and `- file:` can mix.
- Sharing: `{include}` and `{literalinclude}` directives for fragments; external references via intersphinx. No completion concept.
- URLs: https://jupyterbook.org/en/stable/structure/toc.html ; https://mystmd.org/guide/table-of-contents

## Quarto

- `_quarto.yml` project types: `website` (`website: sidebar:` with `contents:` list, `section:` groups, `href:` entries, `auto:` glob entries) and `book` (`book: chapters:`, `appendices:`, `parts:`).
- Appendices are a distinct key from chapters: `book: appendices:` lists files that are numbered differently (A, B, ...) and sit after the chapters, so supplementary material is a separate list in the same config (closest analogue to a `reference:` sibling key).
- `project: render:` selects which files are built; files starting with `_` or `.` are ignored by default. `auto:` entries auto-discover by glob and order by filename/`order:` front matter.
- Sharing: `{{< include _file.qmd >}}` shortcode; `resources:` copies extra files; `website: sidebar:` can be multiple (`id:`) and bound per page via `sidebar:` front matter. No completion concept.
- URLs: https://quarto.org/docs/books/book-structure.html ; https://quarto.org/docs/websites/website-navigation.html ; https://quarto.org/docs/projects/quarto-projects.html

## Cross-cutting observations

- Separate key/list for supplementary material (not a flag on items in the main list): Open edX (tabs/handouts outside the chapter tree), Quarto (`appendices:` beside `chapters:`), Jupyter Book (`parts:`), Docusaurus (separate sidebar or docs instance), Moodle/Canvas (items with no completion requirement or not in any module).
- Ordering is declared by list order in a config file in every file-based tool except those using filename/front-matter/weight (Hugo, Docusaurus autogenerated, MkDocs without `nav`).
- Auto-discovery with an escape hatch is common (MkDocs default, Hugo, Docusaurus `autogenerated`, Jupyter Book `glob`); explicit lists are the alternative (GitBook SUMMARY.md, Jupyter Book `_toc.yml`, Quarto `chapters`). Unlisted files are typically built but unlisted, with a warning (MkDocs, Jupyter Book).
- Completion exclusion: only the LMSs have a completion concept. Open edX excludes by being outside the chapter tree; Moodle by per-module completion tracking "None"; Canvas by having no module requirement. In none of them is it a property of a shared global flag on the content; it follows from where the item is attached.
- Sharing across courses: live sharing by path/mount exists in static-site tools (Hugo mounts, MkDocs monorepo `!include`, MyST/Quarto includes). The LMSs copy on import/duplicate (Moodle, Canvas) or use a library mechanism (Open edX Content Libraries) rather than a relative path.

status: ok
