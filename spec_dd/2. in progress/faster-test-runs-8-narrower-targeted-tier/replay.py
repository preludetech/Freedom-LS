#!/usr/bin/env python3
# ruff: noqa: T201
"""Replay the `[batch ...]` commits on main through the selector with `narrow` off and on.

Run once from anywhere with `python3 replay.py`. It writes the measured section of
`replay.md` (between the replay markers) and nothing else: no cache and no temp files.
Both selector runs use HEAD's tree and HEAD's module graph, not each batch's.
"""

from __future__ import annotations

import re
import shlex
import statistics
import subprocess
import sys
import time
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath

REPO = Path(
    subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        capture_output=True,
        text=True,
        check=True,
        cwd=Path(__file__).resolve().parent,
    ).stdout.strip()
)
SELECTOR = REPO / ".claude/ds/scripts/select_tests.sh"
REPLAY_MD = Path(__file__).resolve().parent / "replay.md"
BEGIN = "<!-- replay:begin -->"
END = "<!-- replay:end -->"
SINCE = "2026-11-19"
RESEARCH_COUNT = 119
LEAF_MODULE = "freedom_ls/panel_framework/csv_safety.py"
APP_TESTS = re.compile(r"^freedom_ls/[^/]+/tests$")
TEST_DEF = re.compile(r"^\s*(?:async\s+)?def test_", re.MULTILINE)
SECONDS_PER_TEST = 294 / 657 - 54 / 657  # accounts sample: 657 tests, 294s, 54s of setup

sys.path.insert(0, str(REPO / "claude_plugins/django-stack/scripts"))
import module_graph  # noqa: E402


@dataclass(frozen=True)
class Run:
    tier: str
    seconds: float
    why: tuple[tuple[str, str], ...]  # (path, rest of the line)
    targets: tuple[str, ...]


@dataclass
class Batch:
    sha: str
    subject: str
    paths: list[str]
    off: Run
    on: Run
    parent_only: int = 0
    reached: int = 0
    notes: list[str] = field(default_factory=list)


def git(*args: str) -> str:
    return subprocess.run(
        ["git", *args], capture_output=True, text=True, check=True, cwd=REPO
    ).stdout


def select(args: list[str]) -> Run:
    start = time.perf_counter()
    try:
        out = subprocess.run(
            [str(SELECTOR), *args],
            capture_output=True,
            text=True,
            check=True,
            cwd=REPO,
        ).stdout
    except subprocess.CalledProcessError as exc:
        raise SystemExit(f"selector failed for {args}: {exc.stderr}") from exc
    seconds = time.perf_counter() - start
    tier = "none"
    why: list[tuple[str, str]] = []
    targets: list[str] = []
    for line in out.splitlines():
        if line.startswith("tier: "):
            tier = line.removeprefix("tier: ").strip()
        elif line.startswith("why: "):
            path, _, rest = line.removeprefix("why: ").partition(" -> ")
            why.append((path, rest))
        elif line.startswith("command: "):
            tokens = shlex.split(line.removeprefix("command: "))
            after = tokens[tokens.index("-m") + 2 :] if "-m" in tokens else []
            targets = [t for t in after if not t.startswith("-")]
    return Run(tier, seconds, tuple(why), tuple(targets))


def app_dirs(run: Run) -> set[str]:
    return {t for t in run.targets if APP_TESTS.match(t)}


def bucket(run: Run, many: int) -> str:
    dirs = len(app_dirs(run))
    if run.tier in {"none", "full"}:
        return run.tier
    if dirs >= many:
        return f"targeted, {many}+ app test directories"
    if dirs >= 6:
        return f"targeted, 6 to {many - 1} app test directories"
    if dirs >= 1:
        return "targeted, 1 to 5 app test directories"
    return "targeted, test files or other targets only"


BUCKETS = (
    "full",
    "targeted, 28+ app test directories",
    "targeted, 6 to 27 app test directories",
    "targeted, 1 to 5 app test directories",
    "targeted, test files or other targets only",
    "none",
)


def full_reasons(run: Run) -> set[str]:
    found: set[str] = set()
    for _, rest in run.why:
        match = re.match(r"full \((.*)\)", rest)
        if match:
            found.add(re.sub(r"^matches ", "", match.group(1)))
    return found


def narrow_rules(run: Run) -> set[str]:
    rules: set[str] = set()
    for _, rest in run.why:
        if "changed test file" in rest:
            continue
        for needle, label in (
            ("through imports", "imports"),
            ("conftest scope", "conftest scope"),
            ("owning app", "owning app"),
            (" dep on ", "one app hop"),
            ("tooling", "tooling"),
        ):
            if needle in rest:
                rules.add(label)
    return rules


def dropped_reasons(off: Run, dropped: set[str]) -> Counter[str]:
    kinds: Counter[str] = Counter()
    seen: set[str] = set()
    for _, rest in off.why:
        for directory in dropped:
            if rest.startswith(f"{directory} (") and directory not in seen:
                seen.add(directory)
                kinds["test-only dep" if "test-only dep" in rest else "runtime dep"] += 1
    return kinds


class TestCounts:
    def __init__(self) -> None:
        self.files = [
            p
            for p in git("ls-files", "-z", "--", "*.py").split("\0")
            if p and PurePosixPath(p).name.startswith("test_")
        ]
        self.cache: dict[str, int] = {}

    def of_file(self, path: str) -> int:
        if path not in self.cache:
            try:
                text = (REPO / path).read_text(encoding="utf-8")
            except (FileNotFoundError, UnicodeDecodeError):
                text = ""
            self.cache[path] = len(TEST_DEF.findall(text))
        return self.cache[path]

    def of_target(self, target: str) -> int:
        if target.endswith(".py"):
            return self.of_file(target)
        prefix = target.rstrip("/") + "/"
        return sum(
            self.of_file(p)
            for p in self.files
            if p.startswith(prefix) and "/playwright/" not in p
        )

    def of_run(self, run: Run) -> int:
        if run.tier == "none":
            return 0
        if run.tier == "full":
            return sum(self.of_file(p) for p in self.files if "/playwright/" not in p)
        return sum(self.of_target(t) for t in run.targets)


def parent_edge_counts(
    graph: module_graph.ModuleGraph, modules: set[str]
) -> tuple[int, int]:
    """Test files reached from `modules`, and how many of them only through a parent-package edge.

    An importer X of package P is a parent-package edge when X also imports a name below P.
    A plain `import P` next to `import P.x` is counted as a parent edge too, so the second
    number is an upper bound.
    """
    pruned: dict[str, set[str]] = {}
    for name, importers in graph.importing_modules.items():
        is_package = graph.paths.get(name, "").endswith("__init__.py")
        if not is_package:
            pruned[name] = set(importers)
            continue
        below = {
            x
            for sub, subs in graph.importing_modules.items()
            if sub.startswith(name + ".")
            for x in subs
        }
        pruned[name] = {x for x in importers if x not in below}
    without = module_graph.ModuleGraph(pruned, graph.paths)
    full = graph.test_files_reaching(modules)
    return len(full), len(full - without.test_files_reaching(modules))


def median(values: list[float]) -> float:
    return statistics.median(values) if values else 0.0


def main() -> None:
    commits = git(
        "log", "--first-parent", "main", f"--since={SINCE}", "--grep=^\\[batch",
        "--format=%H %s",
    ).splitlines()
    tracked = git("ls-files", "-z", "--", "*.py").split("\0")
    graph = module_graph.build(REPO, [p for p in tracked if p])
    counts = TestCounts()
    all_app_dirs = {
        "/".join(p.split("/")[:3])
        for p in git("ls-files").splitlines()
        if re.match(r"^freedom_ls/[^/]+/tests/", p)
    }
    many = 28
    limit = int(sys.argv[1]) if len(sys.argv) > 1 else len(commits)
    batches: list[Batch] = []
    for index, line in enumerate(commits[:limit], 1):
        sha, _, subject = line.partition(" ")
        rng = f"{sha}^..{sha}"
        paths = git("diff", "--name-only", f"{sha}^", sha).splitlines()
        off = select(["--wide", "--range", rng])
        on = select(["--range", rng])
        batch = Batch(sha, subject, paths, off, on)
        modules = {
            module_graph.path_module_name(p)
            for p, rest in on.why
            if "through imports" in rest and p.endswith(".py")
        }
        if modules:
            batch.reached, batch.parent_only = parent_edge_counts(graph, modules)
        batches.append(batch)
        print(f"{index}/{limit} {sha[:9]} off {off.seconds:.1f}s on {on.seconds:.1f}s", file=sys.stderr)

    leaf_off = select(["--wide", LEAF_MODULE])
    leaf_on = select([LEAF_MODULE])

    section = render(batches, len(commits), len(all_app_dirs), counts, leaf_off, leaf_on, many)
    text = REPLAY_MD.read_text(encoding="utf-8") if REPLAY_MD.exists() else f"{BEGIN}\n{END}\n"
    head, _, rest = text.partition(BEGIN)
    _, _, tail = rest.partition(END)
    REPLAY_MD.write_text(f"{head}{BEGIN}\n{section}\n{END}{tail}", encoding="utf-8")


def short(directory: str) -> str:
    return directory.split("/")[1]


def render(
    batches: list[Batch],
    found: int,
    app_dir_total: int,
    counts: TestCounts,
    leaf_off: Run,
    leaf_on: Run,
    many: int,
) -> str:
    out: list[str] = []
    n = len(batches)
    out.append(
        f"Replayed {n} batch commits (`git log --first-parent main --since={SINCE} "
        f"--grep='^\\[batch'` finds {found}; the research used {RESEARCH_COUNT}). "
        f"HEAD has {app_dir_total} `freedom_ls/<app>/tests` directories."
    )
    out.append("")

    off_b = Counter(bucket(b.off, many) for b in batches)
    on_b = Counter(bucket(b.on, many) for b in batches)
    research = {
        "full": "34",
        "targeted, 28+ app test directories": "35",
        "targeted, 6 to 27 app test directories": "0",
        "targeted, 1 to 5 app test directories": "47",
        "targeted, test files or other targets only": "0",
        "none": "3",
    }
    out += ["### Buckets", "", "| Result | Research | Narrow off | Narrow on |", "|---|---|---|---|"]
    for name in BUCKETS:
        out.append(f"| {name} | {research[name]} | {off_b[name]} | {on_b[name]} |")
    out.append(f"| total | 119 | {n} | {n} |")
    wide_or_full = lambda c: c["full"] + c["targeted, 28+ app test directories"]  # noqa: E731
    out += [
        "",
        f"Batches at `full` or {many}+ directories: off {wide_or_full(off_b)}, on {wide_or_full(on_b)}.",
        "",
    ]

    for label, pick in (("off", lambda b: b.off), ("on", lambda b: b.on)):
        reasons: Counter[str] = Counter()
        for b in batches:
            run = pick(b)
            if run.tier == "full":
                for r in full_reasons(run) or {"(no reason parsed)"}:
                    reasons[r] += 1
        out += [f"### Why batches are `full`, narrow {label}", "", "| Reason | Batches |", "|---|---|"]
        out += [f"| {r} | {c} |" for r, c in reasons.most_common()]
        out.append("")

    out += ["### Selector run time", ""]
    out += ["| | Median | Max | Over 10s |", "|---|---|---|---|"]
    for label, pick in (("narrow off", lambda b: b.off), ("narrow on", lambda b: b.on)):
        times = [pick(b).seconds for b in batches]
        out.append(
            f"| {label} | {median(times):.1f}s | {max(times):.1f}s | {sum(t >= 10 for t in times)} of {n} |"
        )
    out.append("")

    out += ["### Test-run time estimate", ""]
    off_t = [counts.of_run(b.off) * SECONDS_PER_TEST for b in batches]
    on_t = [counts.of_run(b.on) * SECONDS_PER_TEST for b in batches]
    out += [
        f"Estimate, not a measurement: `def test_` count of the selected targets (Playwright "
        f"directories excluded, parametrised cases counted once) times {SECONDS_PER_TEST:.2f}s, "
        f"the `accounts` sample's per-test cost with its database setup taken out. Serial test-body "
        f"seconds, before xdist and the 55 to 65s database setup per worker.",
        "",
        "| | Median per batch | Total over all batches |",
        "|---|---|---|",
        f"| narrow off | {median(off_t) / 60:.1f} min | {sum(off_t) / 3600:.1f} h |",
        f"| narrow on | {median(on_t) / 60:.1f} min | {sum(on_t) / 3600:.1f} h |",
        "",
    ]

    out += ["### Parent-package edges", ""]
    graphed = [b for b in batches if b.reached]
    out.append(
        f"{len(graphed)} batches have a changed Python path that the narrow selector resolved "
        f"through imports. Test files reached through those paths: "
        f"{sum(b.reached for b in graphed)}, of which at most {sum(b.parent_only for b in graphed)} "
        f"only through a parent-package edge."
    )
    out.append("")
    heavy = [b for b in graphed if b.parent_only]
    if heavy:
        out += ["| Batch | Reached | Only via parent edge |", "|---|---|---|"]
        out += [f"| {b.sha[:9]} {b.subject} | {b.reached} | {b.parent_only} |" for b in heavy]
        out.append("")

    out += ["### The leaf-module case", ""]
    out.append(f"`{LEAF_MODULE}`, one tracked non-`__init__` module of `panel_framework`.")
    out.append("")
    for label, run in (("narrow off", leaf_off), ("narrow on", leaf_on)):
        dirs = sorted(app_dirs(run))
        files = [t for t in run.targets if t.endswith(".py")]
        file_apps = sorted({short(PurePosixPath(f).as_posix()) for f in files if f.startswith("freedom_ls/")})
        out.append(
            f"- {label}: tier {run.tier}, {len(dirs)} app test directories"
            f"{' (' + ', '.join(short(d) for d in dirs) + ')' if len(dirs) <= 5 else ''}, "
            f"{len(files)} test files in {len(file_apps)} apps."
        )
    out.append("")

    out += ["### Per batch", ""]
    out.append(
        "Dropped means an app test directory narrow off selects and narrow on does not. A test "
        "file from a dropped directory can still be selected by name. Rule columns: what the "
        "wide `why:` lines gave the dropped directories, then the rules the narrow `why:` lines used."
    )
    out.append("")
    out.append("| Batch | Off | On | Dropped | Wide rule of the dropped | Narrow rules |")
    out.append("|---|---|---|---|---|---|")
    for b in batches:
        dropped = app_dirs(b.off) - app_dirs(b.on)
        if b.off.tier == "full" or b.on.tier == "full":
            drop_text = "n/a"
        else:
            drop_text = f"{len(dropped)}"
        wide = dropped_reasons(b.off, dropped)
        wide_text = ", ".join(f"{k} {v}" for k, v in sorted(wide.items())) or "-"
        rules = sorted(narrow_rules(b.on) | full_reasons(b.on))
        out.append(
            f"| {b.sha[:9]} | {bucket(b.off, many)} ({len(app_dirs(b.off))}) | "
            f"{bucket(b.on, many)} ({len(app_dirs(b.on))}) | {drop_text} | {wide_text} | {', '.join(rules) or '-'} |"
        )
    return "\n".join(out)


if __name__ == "__main__":
    main()
