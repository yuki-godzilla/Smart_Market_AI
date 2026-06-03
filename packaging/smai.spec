# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files, collect_submodules, copy_metadata


project_root = Path(SPECPATH).parent


def project_path(*parts):
    return project_root.joinpath(*parts)


def add_tree(root, prefix):
    entries = []
    root_path = Path(root)
    for path in root_path.rglob("*"):
        if not path.is_file():
            continue
        relative_path = path.relative_to(root_path)
        if "__pycache__" in relative_path.parts:
            continue
        if path.suffix in {".pyc", ".pyo"}:
            continue
        destination = Path(prefix) / relative_path.parent
        entries.append((str(path), str(destination)))
    return entries


def add_metadata(distribution_name):
    try:
        return copy_metadata(distribution_name)
    except Exception:
        return []


datas = []
datas += collect_data_files("streamlit")
datas += collect_data_files("altair")
datas += collect_data_files("st_aggrid")
for distribution in (
    "streamlit",
    "streamlit-aggrid",
    "altair",
    "pandas",
    "numpy",
    "yfinance",
    "fastapi",
    "pydantic",
    "SQLAlchemy",
    "PyYAML",
    "requests",
    "curl_cffi",
    "pyarrow",
):
    datas += add_metadata(distribution)
datas += add_tree(project_path("backend"), "backend")
datas += add_tree(project_path("ui"), "ui")
datas += add_tree(project_path("config"), "config")
datas += add_tree(project_path("data", "research_docs"), "data/research_docs")
datas += add_tree(project_path("examples", "rebalance_scenarios"), "examples/rebalance_scenarios")
datas += [
    (str(project_path("data", "marketdata", "symbol_universe.csv")), "data/marketdata"),
    (str(project_path("data", "marketdata", "ohlcv.csv")), "data/marketdata"),
    (str(project_path("data", "marketdata", "fundamentals.csv")), "data/marketdata"),
    (str(project_path("data", "marketdata", "fx_rates.csv")), "data/marketdata"),
]

hiddenimports = []
hiddenimports += collect_submodules("streamlit")
hiddenimports += collect_submodules("backend")
hiddenimports += collect_submodules("ui")
hiddenimports += collect_submodules("yfinance")
hiddenimports += [
    "streamlit.web.cli",
    "st_aggrid",
    "yaml",
    "requests",
    "curl_cffi.requests",
]

excluded_modules = [
    "black",
    "mypy",
    "pytest",
    "ruff",
    "setuptools.tests",
    "numpy.tests",
    "pandas.tests",
]

a = Analysis(
    [str(project_path("packaging", "smai_launcher.py"))],
    pathex=[str(project_root)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excluded_modules,
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="SMAI",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(project_path("packaging", "smai_icon.ico")),
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="SMAI",
    contents_directory="_internal",
)
