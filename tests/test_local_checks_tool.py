from tools.run_local_checks import build_commands


def test_build_commands_runs_ruff_then_pytest():
    commands = build_commands("python")

    assert commands == [
        ["python", "tools/run_black_check.py"],
        ["python", "-m", "ruff", "check", "backend", "tests", "--no-cache"],
        ["python", "-m", "pytest", "tests", "-q", "-s", "-p", "no:cacheprovider"],
    ]


def test_build_commands_can_skip_individual_checks():
    assert build_commands("python", skip_ruff=True) == [
        ["python", "-m", "pytest", "tests", "-q", "-s", "-p", "no:cacheprovider"]
    ]
    assert build_commands("python", skip_pytest=True) == [
        ["python", "tools/run_black_check.py"],
        ["python", "-m", "ruff", "check", "backend", "tests", "--no-cache"],
    ]
