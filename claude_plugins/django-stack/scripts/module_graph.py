# ruff: noqa: T201
"""The Python import graph of a repository: which modules import which, by dotted name.

Used by `select_tests.py` to find the test files a changed module can reach. It runs no git
command: the caller passes the tracked `.py` paths. Stdlib only, like its siblings.
"""

from __future__ import annotations

import ast
import sys
from collections import deque
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from check_test_mirroring import is_collected
from generate_app_map import in_skipped_dir


def path_module_name(path: str) -> str:
    """`a/b/c.py` is `a.b.c` and `a/b/__init__.py` is `a.b`.

    Works for a path the checkout no longer has, so a deleted module keeps its name.
    """
    posix = PurePosixPath(path)
    parts = (
        posix.parent.parts
        if posix.name == "__init__.py"
        else posix.with_suffix("").parts
    )
    return ".".join(parts)


def imported_names(tree: ast.Module, module: str, is_package: bool) -> set[str]:
    """Every dotted name the module's imports name, parent packages included.

    The whole tree is walked, so an import inside a function or under `if TYPE_CHECKING:`
    counts. `from a.b import c` names `a`, `a.b` and `a.b.c`, whether `c` is a module or an
    attribute: edges are keyed by module name, so an attribute name matches no module.

    A relative import is resolved against `module`: level 1 is the module's own package
    (the module itself when `is_package`, else its parent) and each further level strips one
    more part. A level deeper than the package has parts names nothing.
    """
    package = module.split(".") if module else []
    if not is_package:
        package = package[:-1]
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            dotted = [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom):
            if node.level > len(package) + 1:
                continue
            base = package[: len(package) - (node.level - 1)] if node.level else []
            if node.module:
                base = base + node.module.split(".")
            prefix = ".".join(base)
            if not prefix:
                dotted = [alias.name for alias in node.names]
            else:
                dotted = [prefix] + [f"{prefix}.{alias.name}" for alias in node.names]
        else:
            continue
        for name in dotted:
            parts = name.split(".")
            names.update(".".join(parts[: i + 1]) for i in range(len(parts)))
    return names


def conftests_above(test_path: str, conftests: set[str]) -> set[str]:
    """The `conftest.py` paths in `conftests` that pytest loads for `test_path`: one for the
    test file's directory and each ancestor up to the root."""
    directory = PurePosixPath(test_path).parent
    return {
        conftest
        for folder in (directory, *directory.parents)
        if (conftest := (folder / "conftest.py").as_posix()) in conftests
    }


@dataclass(frozen=True)
class ModuleGraph:
    # module name -> names of the modules that import it
    importing_modules: dict[str, set[str]]
    # module name -> repo-relative path, for every tracked module
    paths: dict[str, str]

    def test_files_reaching(self, modules: set[str]) -> set[str]:
        """The paths of the test files that import any of `modules`, directly or through
        other modules. The `modules` themselves are not in the result."""
        reached: set[str] = set()
        queue = deque(modules)
        while queue:
            for importer in self.importing_modules.get(queue.popleft(), ()):
                if importer not in reached and importer not in modules:
                    reached.add(importer)
                    queue.append(importer)
        return {
            self.paths[name]
            for name in reached
            if is_collected(PurePosixPath(self.paths[name]).name)
        }


def build(project_root: Path, tracked: list[str]) -> ModuleGraph:
    """Parse each tracked `.py` file once and record who imports whom.

    A file the working tree has deleted is skipped, since it is simply gone; a file that
    does not parse is skipped with a warning. Each collected test file also gets an edge from
    every `conftest.py` above it, since pytest loads those without an import.
    """
    importing_modules: dict[str, set[str]] = {}
    paths: dict[str, str] = {}
    sources = [path for path in tracked if not in_skipped_dir(Path(path), Path())]
    conftests = {p for p in sources if PurePosixPath(p).name == "conftest.py"}
    for path in sources:
        name = path_module_name(path)
        paths[name] = path
        try:
            tree = ast.parse(
                (project_root / path).read_text(encoding="utf-8"), filename=path
            )
        except FileNotFoundError:
            continue
        except (SyntaxError, UnicodeDecodeError) as exc:
            print(f"WARN: could not parse {path}: {exc}", file=sys.stderr)
            continue
        is_package = PurePosixPath(path).name == "__init__.py"
        for imported in imported_names(tree, name, is_package):
            importing_modules.setdefault(imported, set()).add(name)
    for path in paths.values():
        if is_collected(PurePosixPath(path).name):
            for conftest in conftests_above(path, conftests):
                importing_modules.setdefault(path_module_name(conftest), set()).add(
                    path_module_name(path)
                )
    return ModuleGraph(importing_modules, paths)
