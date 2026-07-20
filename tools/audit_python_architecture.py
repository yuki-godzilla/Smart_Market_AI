"""Report Python module size, dependency direction, fan-out, and cycles."""

from __future__ import annotations

import argparse
import ast
import json
from collections.abc import Iterable, Sequence
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass(frozen=True)
class FunctionMetric:
    module: str
    name: str
    line_count: int


@dataclass(frozen=True)
class ModuleMetric:
    module: str
    path: str
    line_count: int
    definition_count: int
    fan_out: int


@dataclass(frozen=True)
class ArchitectureReport:
    module_count: int
    edge_count: int
    backend_ui_edges: tuple[tuple[str, str], ...]
    cycles: tuple[tuple[str, ...], ...]
    largest_modules: tuple[ModuleMetric, ...]
    largest_functions: tuple[FunctionMetric, ...]
    highest_fan_out: tuple[ModuleMetric, ...]

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class _ParsedModule:
    name: str
    path: Path
    tree: ast.Module
    line_count: int
    definition_count: int


def analyze_python_architecture(
    project_root: Path,
    *,
    source_roots: Sequence[str] = ("backend", "ui"),
    limit: int = 15,
) -> ArchitectureReport:
    """Analyze project-local imports without importing application modules."""

    parsed = _parse_modules(project_root, source_roots)
    module_names = set(parsed)
    edges: set[tuple[str, str]] = set()
    eager_edges: set[tuple[str, str]] = set()
    functions: list[FunctionMetric] = []
    for module in parsed.values():
        edges.update(_module_edges(module, module_names))
        eager_edges.update(_module_edges(module, module_names, eager_only=True))
        functions.extend(_function_metrics(module))

    adjacency: dict[str, set[str]] = {name: set() for name in module_names}
    for source, target in edges:
        adjacency[source].add(target)
    metrics = [
        ModuleMetric(
            module=module.name,
            path=str(module.path.relative_to(project_root)).replace("\\", "/"),
            line_count=module.line_count,
            definition_count=module.definition_count,
            fan_out=len(adjacency[module.name]),
        )
        for module in parsed.values()
    ]
    backend_ui_edges = tuple(
        sorted(
            edge for edge in edges if edge[0].startswith("backend.") and edge[1].startswith("ui.")
        )
    )
    eager_adjacency: dict[str, set[str]] = {name: set() for name in module_names}
    for source, target in eager_edges:
        eager_adjacency[source].add(target)
    return ArchitectureReport(
        module_count=len(parsed),
        edge_count=len(edges),
        backend_ui_edges=backend_ui_edges,
        cycles=tuple(_dependency_cycles(eager_adjacency)),
        largest_modules=tuple(
            sorted(metrics, key=lambda item: (-item.line_count, item.module))[:limit]
        ),
        largest_functions=tuple(
            sorted(functions, key=lambda item: (-item.line_count, item.module, item.name))[:limit]
        ),
        highest_fan_out=tuple(
            sorted(metrics, key=lambda item: (-item.fan_out, item.module))[:limit]
        ),
    )


def _parse_modules(
    project_root: Path,
    source_roots: Sequence[str],
) -> dict[str, _ParsedModule]:
    modules: dict[str, _ParsedModule] = {}
    for source_root in source_roots:
        root = project_root / source_root
        if not root.exists():
            continue
        for path in sorted(root.rglob("*.py")):
            text = path.read_text(encoding="utf-8")
            relative = path.relative_to(project_root).with_suffix("")
            parts = list(relative.parts)
            if parts[-1] == "__init__":
                parts.pop()
            name = ".".join(parts)
            tree = ast.parse(text, filename=str(path))
            modules[name] = _ParsedModule(
                name=name,
                path=path,
                tree=tree,
                line_count=len(text.splitlines()),
                definition_count=sum(
                    isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
                    for node in tree.body
                ),
            )
    return modules


def _module_edges(
    module: _ParsedModule,
    module_names: set[str],
    *,
    eager_only: bool = False,
) -> set[tuple[str, str]]:
    edges: set[tuple[str, str]] = set()
    nodes: Iterable[ast.AST]
    nodes = _eager_import_nodes(module.tree.body) if eager_only else ast.walk(module.tree)
    for node in nodes:
        candidates: Iterable[str]
        if isinstance(node, ast.Import):
            candidates = (alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imported_from = _absolute_import_from(module, node)
            candidates = (
                candidate
                for alias in node.names
                for candidate in (f"{imported_from}.{alias.name}", imported_from)
                if imported_from
            )
        else:
            continue
        target = _first_internal_target(candidates, module_names)
        if target and target != module.name:
            edges.add((module.name, target))
    return edges


def _eager_import_nodes(statements: Sequence[ast.stmt]) -> Iterable[ast.AST]:
    """Yield imports executed while the module itself is imported.

    Imports inside functions, classes, and ``TYPE_CHECKING`` blocks are useful
    for fan-out analysis but cannot form an eager import-time cycle.
    """

    for statement in statements:
        if isinstance(statement, (ast.Import, ast.ImportFrom)):
            yield statement
        elif isinstance(statement, ast.If):
            if _is_type_checking_guard(statement.test):
                continue
            yield from _eager_import_nodes(statement.body)
            yield from _eager_import_nodes(statement.orelse)
        elif isinstance(statement, ast.Try):
            yield from _eager_import_nodes(statement.body)
            yield from _eager_import_nodes(statement.orelse)
            yield from _eager_import_nodes(statement.finalbody)
            for handler in statement.handlers:
                yield from _eager_import_nodes(handler.body)


def _is_type_checking_guard(expression: ast.expr) -> bool:
    if isinstance(expression, ast.Name):
        return expression.id == "TYPE_CHECKING"
    return (
        isinstance(expression, ast.Attribute)
        and expression.attr == "TYPE_CHECKING"
        and isinstance(expression.value, ast.Name)
        and expression.value.id == "typing"
    )


def _absolute_import_from(module: _ParsedModule, node: ast.ImportFrom) -> str:
    if node.level == 0:
        return node.module or ""
    package = module.name.split(".")
    if module.path.name != "__init__.py":
        package.pop()
    trim = max(0, node.level - 1)
    if trim:
        package = package[:-trim]
    if node.module:
        package.extend(node.module.split("."))
    return ".".join(package)


def _first_internal_target(
    candidates: Iterable[str],
    module_names: set[str],
) -> str | None:
    for candidate in candidates:
        current = candidate
        while current:
            if current in module_names:
                return current
            current = current.rpartition(".")[0]
    return None


def _function_metrics(module: _ParsedModule) -> list[FunctionMetric]:
    metrics: list[FunctionMetric] = []
    for node in ast.walk(module.tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        end_line = getattr(node, "end_lineno", node.lineno)
        metrics.append(
            FunctionMetric(
                module=module.name,
                name=node.name,
                line_count=end_line - node.lineno + 1,
            )
        )
    return metrics


def _dependency_cycles(adjacency: dict[str, set[str]]) -> list[tuple[str, ...]]:
    index = 0
    indexes: dict[str, int] = {}
    low_links: dict[str, int] = {}
    stack: list[str] = []
    on_stack: set[str] = set()
    components: list[tuple[str, ...]] = []

    def visit(node: str) -> None:
        nonlocal index
        indexes[node] = low_links[node] = index
        index += 1
        stack.append(node)
        on_stack.add(node)
        for target in sorted(adjacency[node]):
            if target not in indexes:
                visit(target)
                low_links[node] = min(low_links[node], low_links[target])
            elif target in on_stack:
                low_links[node] = min(low_links[node], indexes[target])
        if low_links[node] != indexes[node]:
            return
        component: list[str] = []
        while stack:
            member = stack.pop()
            on_stack.remove(member)
            component.append(member)
            if member == node:
                break
        if len(component) > 1:
            components.append(tuple(sorted(component)))

    for node in sorted(adjacency):
        if node not in indexes:
            visit(node)
    return sorted(components)


def _print_report(report: ArchitectureReport) -> None:
    print(f"modules={report.module_count} edges={report.edge_count}")
    print(f"backend_ui_edges={len(report.backend_ui_edges)} cycles={len(report.cycles)}")
    for cycle in report.cycles:
        print(f"cycle: {' -> '.join(cycle)}")
    print("largest_modules:")
    for module_metric in report.largest_modules:
        print(f"  {module_metric.line_count:>6}  {module_metric.module}")
    print("highest_fan_out:")
    for module_metric in report.highest_fan_out:
        print(f"  {module_metric.fan_out:>6}  {module_metric.module}")
    print("largest_functions:")
    for function_metric in report.largest_functions:
        print(
            f"  {function_metric.line_count:>6}  "
            f"{function_metric.module}.{function_metric.name}"
        )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--json-output", type=Path)
    parser.add_argument("--limit", type=int, default=15)
    parser.add_argument("--fail-on-backend-ui", action="store_true")
    args = parser.parse_args()
    report = analyze_python_architecture(args.project_root.resolve(), limit=max(1, args.limit))
    _print_report(report)
    if args.json_output:
        args.json_output.parent.mkdir(parents=True, exist_ok=True)
        args.json_output.write_text(
            json.dumps(report.to_dict(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    return 1 if args.fail_on_backend_ui and report.backend_ui_edges else 0


if __name__ == "__main__":
    raise SystemExit(main())
