#!/usr/bin/env python3
"""Normalise the spec roadmap and draw its dependency diagrams.

Usage:
    python3 roadmap.py "spec_dd/1. next/roadmap.md"

The roadmap's feature sections are the source. Each run:

- sets every spec bullet's status from where its directory sits (in progress, ready, blocked),
  drops bullets whose directory is done and drops done specs from every "blocked by" list;
- retires a feature section that has no spec bullets left, archiving it to
  ``<parent>/spec-order.md`` when it names a parent;
- regenerates the "Up next" section;
- writes one SVG per feature with edges, plus ``up-next.svg``, into ``<stem>_diagrams/``.

Problems it cannot fix (directories with no bullet, bullets for directories that exist nowhere,
unknown dependencies, cycles) are printed and make the exit status 1.

The format is defined in ``claude_plugins/sdd/resources/roadmap_format.md``.
"""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass, field
from datetime import UTC, datetime
from html import escape
from itertools import pairwise
from pathlib import Path

IN_PROGRESS_DIR = "2. in progress"
DONE_DIR = "3. done"
UP_NEXT_HEADING = "## Up next"

BULLET_RE = re.compile(
    r"^- `(?P<dir>[^`]+)` — \*\*(?P<status>in progress|ready|blocked)\*\*"
    r"(?: by (?P<by>`[^`]+`(?:, `[^`]+`)*))? — (?P<rest>.*)$"
)
PARENT_RE = re.compile(r"Parent: `([^`]+)`")
IMAGE_RE = re.compile(r"^!\[[^\]]*\]\([^)]*_diagrams/[^)]*\.svg\)$")
PRECURSOR = "Before starting:"
REMOVED = "\0removed"

UP_NEXT_LEVELS = 3

# Diagram geometry.
BOX_W = 250
LAYER_GAP = 80
ROW_GAP = 18
LINE_H = 15
PAD_Y = 10
MARGIN = 24
TITLE_H = 34
LEGEND_H = 40
WRAP_CHARS = 30
WAYPOINT_H = 6
CHAR_W = 7.3
FONT = "ui-monospace, SFMono-Regular, Menlo, Consolas, monospace"

STYLES = {
    "in progress": ("#dbeafe", "#2563eb", ""),
    "ready": ("#dcfce7", "#16a34a", ""),
    "needs main": ("#fef3c7", "#d97706", ""),
    "blocked": ("#f3f4f6", "#9ca3af", ""),
    "external": ("#ffffff", "#6b7280", "5 4"),
}
LEGEND = [
    ("in progress", "in progress"),
    ("ready", "ready"),
    ("needs main", "needs work on main first"),
    ("blocked", "blocked"),
    ("external", "other feature"),
]


@dataclass
class Spec:
    dir: str
    status: str
    deps: list[str]
    rest: str
    feature: str

    @property
    def precursor(self) -> str | None:
        if PRECURSOR not in self.rest:
            return None
        return self.rest.split(PRECURSOR, 1)[1].strip()

    @property
    def state(self) -> str:
        """Display state: the status, with ready-plus-precursor shown as 'needs main'."""
        if self.status == "ready" and self.precursor:
            return "needs main"
        return self.status

    def render(self) -> str:
        by = ""
        if self.deps:
            by = " by " + ", ".join(f"`{d}`" for d in self.deps)
        return f"- `{self.dir}` — **{self.status}**{by} — {self.rest}"


@dataclass
class Section:
    heading: str
    lines: list[str]
    specs: list[Spec] = field(default_factory=list)

    @property
    def name(self) -> str:
        return self.heading[3:].strip()

    @property
    def parent(self) -> str | None:
        for line in self.lines:
            match = PARENT_RE.search(line)
            if match:
                return match.group(1)
        return None


def slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def split_sections(text: str) -> tuple[list[str], list[Section]]:
    """Split the file into its preamble and its `##` sections."""
    preamble: list[str] = []
    sections: list[Section] = []
    for line in text.splitlines():
        if line.startswith("## "):
            sections.append(Section(heading=line, lines=[]))
        elif sections:
            sections[-1].lines.append(line)
        else:
            preamble.append(line)
    return preamble, sections


def trim_blank(lines: list[str]) -> list[str]:
    start, end = 0, len(lines)
    while start < end and not lines[start].strip():
        start += 1
    while end > start and not lines[end - 1].strip():
        end -= 1
    return lines[start:end]


def list_dirs(path: Path) -> set[str]:
    if not path.is_dir():
        return set()
    return {p.name for p in path.iterdir() if p.is_dir() and not p.name.startswith(".")}


def done_names(path: Path) -> set[str]:
    """Done entries are `<timestamp>_<name>`; return every possible `<name>` suffix."""
    names: set[str] = set()
    for entry in list_dirs(path):
        parts = entry.split("_")
        for i in range(1, len(parts)):
            names.add("_".join(parts[i:]))
    return names


def wrap_name(name: str) -> list[str]:
    """Wrap a directory name at hyphens and underscores, keeping each line short."""
    tokens = re.findall(r"[^-_]+[-_]?", name)
    lines: list[str] = []
    current = ""
    for token in tokens:
        if current and len(current) + len(token) > WRAP_CHARS:
            lines.append(current)
            current = ""
        current += token
    if current:
        lines.append(current)
    return lines


def find_cycles(graph: dict[str, list[str]]) -> list[list[str]]:
    cycles: list[list[str]] = []
    state: dict[str, int] = {}
    stack: list[str] = []

    def visit(node: str) -> None:
        state[node] = 1
        stack.append(node)
        for dep in graph.get(node, []):
            if state.get(dep) == 1:
                cycles.append([*stack[stack.index(dep) :], dep])
            elif dep not in state:
                visit(dep)
        stack.pop()
        state[node] = 2

    for node in graph:
        if node not in state:
            visit(node)
    return cycles


def layer_by_longest_path(
    nodes: list[str], edges: list[tuple[str, str]]
) -> dict[str, int]:
    """Assign each node the length of the longest dependency chain leading to it."""
    preds: dict[str, list[str]] = {n: [] for n in nodes}
    for dep, spec in edges:
        preds[spec].append(dep)
    layer: dict[str, int] = {}

    def depth(node: str, seen: frozenset[str]) -> int:
        if node in layer:
            return layer[node]
        if node in seen:
            return 0
        value = 0
        for dep in preds[node]:
            value = max(value, depth(dep, seen | {node}) + 1)
        layer[node] = value
        return value

    for node in nodes:
        depth(node, frozenset())
    return layer


def order_layers(
    nodes: list[str], layer: dict[str, int], edges: list[tuple[str, str]]
) -> list[list[str]]:
    """Order nodes inside each layer by the mean position of their neighbours."""
    count = max(layer.values()) + 1
    layers: list[list[str]] = [
        [n for n in nodes if layer[n] == i] for i in range(count)
    ]
    preds: dict[str, list[str]] = {n: [] for n in nodes}
    succs: dict[str, list[str]] = {n: [] for n in nodes}
    for dep, spec in edges:
        preds[spec].append(dep)
        succs[dep].append(spec)

    def positions() -> dict[str, float]:
        return {n: i for row in layers for i, n in enumerate(row)}

    for _ in range(4):
        for i in range(1, count):
            pos = positions()
            layers[i].sort(key=lambda n: _mean([pos[p] for p in preds[n]], pos[n]))
        for i in range(count - 2, -1, -1):
            pos = positions()
            layers[i].sort(key=lambda n: _mean([pos[s] for s in succs[n]], pos[n]))
    return layers


def _mean(values: list[float], default: float) -> float:
    return sum(values) / len(values) if values else default


def draw_svg(
    title: str,
    nodes: list[str],
    edges: list[tuple[str, str]],
    states: dict[str, str],
    captions: dict[str, str],
    layer: dict[str, int] | None = None,
) -> str:
    layer = dict(layer or layer_by_longest_path(nodes, edges))

    # An edge that skips layers runs through one waypoint per layer it crosses, so the waypoints
    # take part in ordering and spacing and the edge never passes under a box.
    routes: list[list[str]] = []
    chained: list[tuple[str, str]] = []
    for dep, spec in edges:
        route = [dep]
        for step in range(layer[dep] + 1, layer[spec]):
            waypoint = f"\0{dep}\0{spec}\0{step}"
            layer[waypoint] = step
            route.append(waypoint)
        route.append(spec)
        routes.append(route)
        chained += list(pairwise(route))
    waypoints = [n for route in routes for n in route[1:-1]]
    layers = order_layers([*nodes, *waypoints], layer, chained)

    labels = {n: wrap_name(n) for n in nodes}
    heights = {
        n: (len(labels[n]) + (1 if n in captions else 0)) * LINE_H + 2 * PAD_Y
        for n in nodes
    }
    heights.update(dict.fromkeys(waypoints, WAYPOINT_H))
    column_heights = [
        sum(heights[n] for n in row) + ROW_GAP * max(len(row) - 1, 0) for row in layers
    ]
    body_h = max(column_heights)

    boxes: dict[str, tuple[float, float, float]] = {}
    for i, row in enumerate(layers):
        x = float(MARGIN + i * (BOX_W + LAYER_GAP))
        y = MARGIN + TITLE_H + (body_h - column_heights[i]) / 2
        for node in row:
            boxes[node] = (x, y, heights[node])
            y += heights[node] + ROW_GAP

    width = float(2 * MARGIN + len(layers) * BOX_W + (len(layers) - 1) * LAYER_GAP)
    legend_x: list[float] = []
    cursor = float(MARGIN)
    for _, label in LEGEND:
        legend_x.append(cursor)
        cursor += 22 + len(label) * CHAR_W + 28
    width = max(width, cursor + MARGIN)
    height = MARGIN + TITLE_H + body_h + 24 + LEGEND_H

    out = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width:.0f}" height="{height:.0f}" '
        f'viewBox="0 0 {width:.0f} {height:.0f}" font-family="{FONT}" font-size="12">',
        '<defs><marker id="arrow" viewBox="0 0 10 10" refX="10" refY="5" markerWidth="7" '
        'markerHeight="7" orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" fill="#4b5563"/>'
        "</marker></defs>",
        f'<rect width="{width:.0f}" height="{height:.0f}" fill="#ffffff"/>',
        f'<text x="{MARGIN}" y="{MARGIN + 14}" font-size="15" font-weight="bold" '
        f'fill="#111827">{escape(title)}</text>',
    ]
    for route in routes:
        points: list[tuple[float, float]] = []
        for node in route:
            x, y, h = boxes[node]
            cy = y + h / 2
            if node == route[0]:
                points.append((x + BOX_W, cy))
            elif node == route[-1]:
                points.append((x, cy))
            else:
                points += [(x, cy), (x + BOX_W, cy)]
        path = f"M{points[0][0]:.1f},{points[0][1]:.1f}"
        for i in range(1, len(points)):
            (sx, sy), (ex, ey) = points[i - 1], points[i]
            if i % 2 == 0:
                path += f" L{ex:.1f},{ey:.1f}"
                continue
            bend = max(30.0, (ex - sx) / 2)
            path += (
                f" C{sx + bend:.1f},{sy:.1f} {ex - bend:.1f},{ey:.1f} {ex:.1f},{ey:.1f}"
            )
        out.append(
            f'<path d="{path}" fill="none" stroke="#4b5563" stroke-width="1.3" '
            'marker-end="url(#arrow)"/>'
        )
    for node in nodes:
        x, y, h = boxes[node]
        fill, stroke, dash = STYLES[states[node]]
        dash_attr = f' stroke-dasharray="{dash}"' if dash else ""
        out.append(
            f'<rect x="{x:.1f}" y="{y:.1f}" width="{BOX_W}" height="{h:.0f}" rx="6" '
            f'fill="{fill}" stroke="{stroke}" stroke-width="1.5"{dash_attr}/>'
        )
        ty = y + PAD_Y + LINE_H - 3
        for line in labels[node]:
            out.append(
                f'<text x="{x + 10:.1f}" y="{ty:.1f}" fill="#111827">{escape(line)}</text>'
            )
            ty += LINE_H
        if node in captions:
            out.append(
                f'<text x="{x + 10:.1f}" y="{ty:.1f}" fill="#6b7280" font-style="italic">'
                f"{escape(captions[node])}</text>"
            )

    ly = MARGIN + TITLE_H + body_h + 24
    for i, (state, label) in enumerate(LEGEND):
        fill, stroke, dash = STYLES[state]
        dash_attr = f' stroke-dasharray="{dash}"' if dash else ""
        lx = legend_x[i]
        out.append(
            f'<rect x="{lx}" y="{ly}" width="16" height="12" rx="3" fill="{fill}" '
            f'stroke="{stroke}" stroke-width="1.5"{dash_attr}/>'
        )
        out.append(
            f'<text x="{lx + 22}" y="{ly + 10}" fill="#374151">{escape(label)}</text>'
        )
    out.append("</svg>")
    return "\n".join(out) + "\n"


def feature_graph(
    section: Section, specs: dict[str, Spec]
) -> tuple[list[str], list[tuple[str, str]], dict[str, str], dict[str, str]]:
    own = [s.dir for s in section.specs]
    edges: list[tuple[str, str]] = []
    captions: dict[str, str] = {}
    for spec in section.specs:
        for dep in spec.deps:
            if dep in specs:
                edges.append((dep, spec.dir))
                if dep not in own:
                    captions[dep] = specs[dep].feature
    linked = {n for edge in edges for n in edge}
    nodes = [n for n in own if n in linked] + sorted(n for n in captions if n in linked)
    states = {n: ("external" if n in captions else specs[n].state) for n in nodes}
    return nodes, edges, states, captions


def up_next_graph(
    specs: dict[str, Spec],
) -> tuple[list[str], list[tuple[str, str]], dict[str, str], dict[str, int]]:
    dependents: dict[str, list[str]] = {d: [] for d in specs}
    for spec in specs.values():
        for dep in spec.deps:
            if dep in specs:
                dependents[dep].append(spec.dir)
    level: dict[str, int] = {}
    frontier = [d for d, s in specs.items() if s.status != "blocked" and dependents[d]]
    for d in frontier:
        level[d] = 0
    for depth in range(1, UP_NEXT_LEVELS):
        frontier = sorted(
            {c for d in frontier for c in dependents[d] if c not in level}
        )
        for d in frontier:
            level[d] = depth
    nodes = [d for d in specs if d in level]
    edges = [(dep, s) for s in nodes for dep in specs[s].deps if dep in level]
    states = {n: specs[n].state for n in nodes}
    return nodes, edges, states, level


def build_up_next(specs: list[Spec], has_diagram: bool, diagram_dir: str) -> list[str]:
    def bullets(items: list[str]) -> list[str]:
        return items or ["None."]

    in_progress = sorted(
        f"- `{s.dir}` ({s.feature})" for s in specs if s.state == "in progress"
    )
    ready = sorted(f"- `{s.dir}` ({s.feature})" for s in specs if s.state == "ready")
    needs = sorted(
        f"- `{s.dir}` ({s.feature}): {s.precursor}"
        for s in specs
        if s.state == "needs main"
    )
    lines = [
        "",
        "Generated by the sdd roadmap script from the feature sections below. Do not edit by hand.",
        "",
        "### In progress",
        "",
        *bullets(in_progress),
        "",
        "### Ready to start",
        "",
        *bullets(ready),
        "",
        "### Needs work on main first",
        "",
        *bullets(needs),
        "",
    ]
    if has_diagram:
        lines += [f"![Up next]({diagram_dir}/up-next.svg)", ""]
    return lines


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print(__doc__)
        return 2
    roadmap = Path(argv[1])
    next_dir = roadmap.parent
    spec_root = next_dir.parent
    diagram_dir_name = f"{roadmap.stem}_diagrams"
    diagram_dir = next_dir / diagram_dir_name

    waiting = list_dirs(next_dir) - {diagram_dir_name}
    in_progress = list_dirs(spec_root / IN_PROGRESS_DIR)
    done = done_names(spec_root / DONE_DIR)
    problems: list[str] = []
    notices: list[str] = []

    preamble, sections = split_sections(roadmap.read_text())
    features = [s for s in sections if s.heading.strip() != UP_NEXT_HEADING]

    # Parse and normalise every spec bullet.
    for section in features:
        for i, line in enumerate(section.lines):
            match = BULLET_RE.match(line)
            if not match:
                continue
            name = match.group("dir")
            deps = re.findall(r"`([^`]+)`", match.group("by") or "")
            spec = Spec(
                name, match.group("status"), deps, match.group("rest"), section.name
            )
            if name not in waiting and name not in in_progress:
                if name in done:
                    notices.append(f"dropped done spec: {name}")
                else:
                    problems.append(
                        f"bullet for a directory that exists nowhere: {name}"
                    )
                section.lines[i] = REMOVED
                continue
            spec.deps = [d for d in deps if d not in done]
            for dep in spec.deps:
                if dep not in waiting and dep not in in_progress:
                    problems.append(f"{name} is blocked by unknown directory: {dep}")
            if name in in_progress:
                spec.status = "in progress"
            elif spec.deps:
                spec.status = "blocked"
            else:
                spec.status = "ready"
            section.specs.append(spec)
            section.lines[i] = spec.render()

    for section in features:
        section.lines = [ln for ln in section.lines if ln != REMOVED]

    # Retire emptied features.
    kept: list[Section] = []
    for section in features:
        if section.specs:
            kept.append(section)
            continue
        parent = section.parent
        if parent and (next_dir / parent).is_dir():
            archive = next_dir / parent / "spec-order.md"
            archived = "\n".join(
                [
                    section.heading,
                    *[ln for ln in section.lines if not IMAGE_RE.match(ln)],
                ]
            )
            note = f"Archived from the spec roadmap on {datetime.now(UTC).date().isoformat()}, when the last of its specs finished.\n\n"
            prior = archive.read_text() + "\n" if archive.exists() else ""
            archive.write_text(prior + note + archived.strip() + "\n")
            notices.append(f"effort retired: {next_dir / parent}")
            waiting.discard(parent)
        else:
            notices.append(f"feature removed, no specs left: {section.name}")
    features = kept

    specs = {s.dir: s for section in features for s in section.specs}
    for section in features:
        if section.parent:
            waiting.discard(section.parent)
    for name in sorted((waiting | in_progress) - set(specs)):
        problems.append(f"directory with no bullet: {name}")
    for cycle in find_cycles(
        {d: [x for x in s.deps if x in specs] for d, s in specs.items()}
    ):
        problems.append("cycle: " + " -> ".join(cycle))

    # Diagrams.
    diagram_dir.mkdir(exist_ok=True)
    written: set[str] = set()
    for section in features:
        nodes, edges, states, captions = feature_graph(section, specs)
        image = f"![{section.name}]({diagram_dir_name}/{slugify(section.name)}.svg)"
        body = [ln for ln in section.lines if not IMAGE_RE.match(ln)]
        if edges and not any(
            find_cycles({n: [d for d, s in edges if s == n] for n in nodes})
        ):
            filename = f"{slugify(section.name)}.svg"
            (diagram_dir / filename).write_text(
                draw_svg(section.name, nodes, edges, states, captions)
            )
            written.add(filename)
            last = max(i for i, ln in enumerate(body) if BULLET_RE.match(ln))
            body = [*body[: last + 1], "", image, *body[last + 1 :]]
        section.lines = body

    nodes, edges, states, level = up_next_graph(specs)
    has_up_next = bool(edges) and not problems_with_cycles(problems)
    if has_up_next:
        (diagram_dir / "up-next.svg").write_text(
            draw_svg("Up next", nodes, edges, states, {}, level)
        )
        written.add("up-next.svg")
    for stale in diagram_dir.glob("*.svg"):
        if stale.name not in written:
            stale.unlink()

    # Reassemble.
    out = trim_blank(preamble)
    out += [
        "",
        UP_NEXT_HEADING,
        *build_up_next(list(specs.values()), has_up_next, diagram_dir_name),
    ]
    for section in features:
        out += [section.heading, "", *collapse_blank(trim_blank(section.lines)), ""]
    roadmap.write_text("\n".join(trim_blank(out)) + "\n")

    for line in notices:
        print(line)
    for line in problems:
        print(f"PROBLEM: {line}")
    print(f"status: {'failed' if problems else 'ok'}")
    return 1 if problems else 0


def problems_with_cycles(problems: list[str]) -> bool:
    return any(p.startswith("cycle:") for p in problems)


def collapse_blank(lines: list[str]) -> list[str]:
    out: list[str] = []
    for line in lines:
        if line == "" and out and out[-1] == "":
            continue
        out.append(line)
    return out


if __name__ == "__main__":
    sys.exit(main(sys.argv))
