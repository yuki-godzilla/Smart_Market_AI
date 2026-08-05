from pathlib import Path

from tools.audit_python_architecture import (
    ArchitectureBaseline,
    analyze_python_architecture,
    architecture_baseline_violations,
    load_architecture_baseline,
)


def _write_module(root: Path, relative_path: str, source: str) -> None:
    path = root / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(source, encoding="utf-8")


def test_architecture_audit_reports_reverse_dependency_cycle_and_metrics(tmp_path: Path) -> None:
    _write_module(tmp_path, "backend/__init__.py", "")
    _write_module(
        tmp_path, "backend/service.py", "from ui.view import render\n\ndef run():\n    render()\n"
    )
    _write_module(tmp_path, "ui/__init__.py", "")
    _write_module(
        tmp_path, "ui/view.py", "from backend.service import run\n\ndef render():\n    return run\n"
    )

    report = analyze_python_architecture(tmp_path)

    assert report.module_count == 4
    assert report.backend_ui_edges == (("backend.service", "ui.view"),)
    assert report.cycles == (("backend.service", "ui.view"),)
    assert report.largest_modules[0].module in {"backend.service", "ui.view"}
    assert report.highest_fan_out[0].fan_out == 1
    assert {metric.name for metric in report.largest_functions} == {"render", "run"}


def test_architecture_audit_resolves_relative_imports(tmp_path: Path) -> None:
    _write_module(tmp_path, "backend/__init__.py", "")
    _write_module(tmp_path, "backend/domain/__init__.py", "from .service import run\n")
    _write_module(tmp_path, "backend/domain/service.py", "from .contracts import Result\n")
    _write_module(tmp_path, "backend/domain/contracts.py", "class Result:\n    pass\n")
    _write_module(tmp_path, "ui/__init__.py", "")

    report = analyze_python_architecture(tmp_path)

    assert report.edge_count == 2
    assert report.backend_ui_edges == ()
    assert report.cycles == ()


def test_architecture_audit_does_not_report_lazy_or_type_only_cycle(tmp_path: Path) -> None:
    _write_module(tmp_path, "backend/__init__.py", "")
    _write_module(
        tmp_path,
        "backend/first.py",
        "from typing import TYPE_CHECKING\n"
        "if TYPE_CHECKING:\n"
        "    from backend.second import value\n"
        "def lazy():\n"
        "    from backend.second import value\n"
        "    return value\n",
    )
    _write_module(tmp_path, "backend/second.py", "from backend.first import lazy\nvalue = 1\n")
    _write_module(tmp_path, "ui/__init__.py", "")

    report = analyze_python_architecture(tmp_path)

    assert report.edge_count == 2
    assert report.cycles == ()


def test_architecture_baseline_detects_new_reverse_dependency_and_cycle(tmp_path: Path) -> None:
    _write_module(tmp_path, "backend/__init__.py", "")
    _write_module(tmp_path, "backend/service.py", "from ui.view import render\n")
    _write_module(tmp_path, "ui/__init__.py", "")
    _write_module(tmp_path, "ui/view.py", "from backend.service import run\n")
    report = analyze_python_architecture(tmp_path)
    baseline_path = tmp_path / "architecture_baseline.json"
    baseline_path.write_text(
        '{"schema_version":"architecture-baseline-v2",'
        '"expected_backend_ui_edges":[],"expected_eager_cycles":[]}',
        encoding="utf-8",
    )

    assert architecture_baseline_violations(report, load_architecture_baseline(baseline_path))
    assert (
        architecture_baseline_violations(
            report,
            ArchitectureBaseline(report.backend_ui_edges, report.cycles),
        )
        == []
    )


def test_architecture_baseline_detects_unapproved_large_modules_and_functions(
    tmp_path: Path,
) -> None:
    _write_module(tmp_path, "backend/__init__.py", "")
    _write_module(
        tmp_path,
        "backend/large.py",
        "\n".join(["def oversized():"] + ["    value = 1"] * 6),
    )
    _write_module(tmp_path, "ui/__init__.py", "")

    report = analyze_python_architecture(tmp_path)
    baseline = ArchitectureBaseline(
        (),
        (),
        new_module_line_limit=5,
        new_function_line_limit=5,
    )

    violations = architecture_baseline_violations(report, baseline)

    assert "module line count exceeds its approved limit" in violations[0]
    assert "function line count exceeds its approved limit" in violations[1]


def test_architecture_baseline_allows_only_the_named_legacy_function_size(
    tmp_path: Path,
) -> None:
    _write_module(tmp_path, "backend/__init__.py", "")
    _write_module(
        tmp_path,
        "backend/legacy.py",
        "\n".join(["def oversized():"] + ["    value = 1"] * 6),
    )
    _write_module(tmp_path, "ui/__init__.py", "")

    report = analyze_python_architecture(tmp_path)
    baseline = ArchitectureBaseline(
        (),
        (),
        new_function_line_limit=5,
        allowed_function_line_counts=(("backend.legacy.oversized", 7),),
    )

    assert architecture_baseline_violations(report, baseline) == []

    _write_module(
        tmp_path,
        "backend/legacy.py",
        "\n".join(["def oversized():"] + ["    value = 1"] * 7),
    )
    grown_report = analyze_python_architecture(tmp_path)

    assert architecture_baseline_violations(grown_report, baseline) == [
        "function line count exceeds its approved limit: " "backend.legacy.oversized=8, allowed=7"
    ]
