"""Report Python module size, dependency direction, fan-out, and cycles."""

from __future__ import annotations

import argparse
import ast
import json
from collections.abc import Callable, Iterable, Sequence
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
    module_metrics: tuple[ModuleMetric, ...]
    function_metrics: tuple[FunctionMetric, ...]

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class ArchitectureBaseline:
    """Versioned expectations for architecture failures that must not regress."""

    expected_backend_ui_edges: tuple[tuple[str, str], ...]
    expected_eager_cycles: tuple[tuple[str, ...], ...]
    new_module_line_limit: int | None = None
    new_function_line_limit: int | None = None
    allowed_module_line_counts: tuple[tuple[str, int], ...] = ()
    allowed_function_line_counts: tuple[tuple[str, int], ...] = ()


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
        module_metrics=tuple(sorted(metrics, key=lambda item: item.module)),
        function_metrics=tuple(
            sorted(functions, key=lambda item: (item.module, item.name, item.line_count))
        ),
    )


def load_architecture_baseline(path: Path) -> ArchitectureBaseline:
    """Load the small checked-in baseline without importing application code."""

    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("schema_version") != "architecture-baseline-v2":
        raise ValueError("Unsupported architecture baseline schema version.")
    return ArchitectureBaseline(
        expected_backend_ui_edges=tuple(
            sorted(tuple(edge) for edge in payload.get("expected_backend_ui_edges", []))
        ),
        expected_eager_cycles=tuple(
            sorted(tuple(sorted(cycle)) for cycle in payload.get("expected_eager_cycles", []))
        ),
        new_module_line_limit=_optional_positive_int(
            payload.get("new_module_line_limit"), field="new_module_line_limit"
        ),
        new_function_line_limit=_optional_positive_int(
            payload.get("new_function_line_limit"), field="new_function_line_limit"
        ),
        allowed_module_line_counts=_line_count_limits(
            payload.get("allowed_module_line_counts", {}),
            field="allowed_module_line_counts",
        ),
        allowed_function_line_counts=_line_count_limits(
            payload.get("allowed_function_line_counts", {}),
            field="allowed_function_line_counts",
        ),
    )


def architecture_baseline_violations(
    report: ArchitectureReport,
    baseline: ArchitectureBaseline,
) -> list[str]:
    """Return deterministic regression messages for baseline-protected invariants."""

    violations: list[str] = []
    if report.backend_ui_edges != baseline.expected_backend_ui_edges:
        violations.append(
            "backend-to-UI edges differ from baseline: "
            f"expected={baseline.expected_backend_ui_edges}, actual={report.backend_ui_edges}"
        )
    if report.cycles != baseline.expected_eager_cycles:
        violations.append(
            "eager import cycles differ from baseline: "
            f"expected={baseline.expected_eager_cycles}, actual={report.cycles}"
        )
    _append_size_limit_violations(
        violations,
        metrics=report.module_metrics,
        limit=baseline.new_module_line_limit,
        allowed_counts=dict(baseline.allowed_module_line_counts),
        metric_name=lambda metric: metric.module,
        label="module",
    )
    _append_size_limit_violations(
        violations,
        metrics=report.function_metrics,
        limit=baseline.new_function_line_limit,
        allowed_counts=dict(baseline.allowed_function_line_counts),
        metric_name=lambda metric: (
            f"{metric.module}.{metric.name}"
            if isinstance(metric, FunctionMetric)
            else metric.module
        ),
        label="function",
    )
    return violations


def _optional_positive_int(value: object, *, field: str) -> int | None:
    if value is None:
        return None
    if not isinstance(value, int) or value < 1:
        raise ValueError(f"{field} must be a positive integer when provided.")
    return value


def _line_count_limits(value: object, *, field: str) -> tuple[tuple[str, int], ...]:
    if not isinstance(value, dict):
        raise ValueError(f"{field} must be a mapping of names to positive integers.")
    limits: list[tuple[str, int]] = []
    for name, maximum in value.items():
        if not isinstance(name, str) or not name:
            raise ValueError(f"{field} names must be non-empty strings.")
        if not isinstance(maximum, int) or maximum < 1:
            raise ValueError(f"{field} values must be positive integers.")
        limits.append((name, maximum))
    return tuple(sorted(limits))


def _append_size_limit_violations(
    violations: list[str],
    *,
    metrics: Sequence[ModuleMetric] | Sequence[FunctionMetric],
    limit: int | None,
    allowed_counts: dict[str, int],
    metric_name: Callable[[ModuleMetric | FunctionMetric], str],
    label: str,
) -> None:
    if limit is None:
        return
    for metric in metrics:
        name = metric_name(metric)
        allowed_count = allowed_counts.get(name, limit)
        if metric.line_count > allowed_count:
            violations.append(
                f"{label} line count exceeds its approved limit: "
                f"{name}={metric.line_count}, allowed={allowed_count}"
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
    parser.add_argument("--baseline", type=Path)
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
    violations: list[str] = []
    if args.baseline:
        violations = architecture_baseline_violations(
            report,
            load_architecture_baseline(args.baseline),
        )
        for violation in violations:
            print(f"baseline violation: {violation}")
    if violations or (args.fail_on_backend_ui and report.backend_ui_edges):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
