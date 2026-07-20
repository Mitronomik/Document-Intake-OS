from __future__ import annotations

import ast
import tomllib
from pathlib import Path


def test_package_imports_without_sqlcipher3_eager_import() -> None:
    import document_intake.persistence as persistence

    assert persistence.CURRENT_SCHEMA_VERSION == 3


def test_dependency_marker_is_exact_and_spike_keeps_cryptography_only() -> None:
    data = tomllib.loads(Path("pyproject.toml").read_text())
    assert (
        "sqlcipher3==0.6.2; sys_platform == 'win32' and platform_machine == 'AMD64'"
        in data["project"]["dependencies"]
    )
    spike = data["dependency-groups"]["encryption-spike"]
    assert spike == ["cryptography==49.0.0; sys_platform == 'win32'"]


def test_production_persistence_contains_no_sqlite3_import() -> None:
    for path in Path("src/document_intake/persistence").glob("**/*.py"):
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                assert all(alias.name != "sqlite3" for alias in node.names), path
            if isinstance(node, ast.ImportFrom):
                assert node.module != "sqlite3", path
