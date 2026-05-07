from pathlib import Path

from tools.run_black_check import check_files, iter_python_files


def test_iter_python_files_skips_virtualenv_like_directories():
    files = iter_python_files(["tools"])

    assert Path("tools/run_black_check.py").resolve() in files
    assert not any("venv_SMAI" in path.parts for path in files)


def test_check_files_accepts_formatted_file():
    unformatted = check_files([Path("tools/run_black_check.py").resolve()])

    assert unformatted == []
