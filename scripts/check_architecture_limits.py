"""Enforce production module, symbol, complexity, and responsibility ratchets."""

from __future__ import annotations

import ast
import json
import subprocess
from collections.abc import Iterator
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config" / "architecture_limits.json"
SymbolNode = ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef


def _tracked(commit: str | None = None) -> tuple[str, ...]:
    command = (
        ["git", "ls-tree", "-r", "--name-only", commit, "src/document_intake"]
        if commit
        else ["git", "ls-files", "src/document_intake"]
    )
    return tuple(
        p
        for p in subprocess.check_output(command, cwd=ROOT, text=True).splitlines()
        if p.endswith(".py")
    )


def _source(path: str, commit: str | None = None) -> str:
    if commit:
        return subprocess.check_output(["git", "show", f"{commit}:{path}"], cwd=ROOT, text=True)
    return (ROOT / path).read_text(encoding="utf-8")


def _symbols(body: list[ast.stmt], prefix: str = "") -> Iterator[tuple[SymbolNode, str]]:
    for node in body:
        if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            name = f"{prefix}.{node.name}" if prefix else node.name
            yield node, name
            yield from _symbols(node.body, name)


def _complexity(node: ast.AST) -> int:
    value = 1
    for child in ast.walk(node):
        if isinstance(
            child,
            (
                ast.If,
                ast.For,
                ast.AsyncFor,
                ast.While,
                ast.IfExp,
                ast.ExceptHandler,
                ast.Assert,
                ast.comprehension,
            ),
        ):
            value += 1
        elif isinstance(child, ast.BoolOp):
            value += len(child.values) - 1
        elif isinstance(child, ast.Match):
            value += max(0, len(child.cases) - 1)
    return value


def _violations(path: str, text: str, config: dict[str, Any]) -> list[tuple[str, int]]:
    limits = config["limits"]
    legacy = config["legacy"].get(path, {})
    result = []
    lines = len(text.splitlines())
    tree = ast.parse(text)
    allowed = legacy.get("module_lines", limits["module_lines"])
    if lines > allowed:
        result.append(("MODULE_LINES", lines))
    base_symbols = legacy.get("symbols", {})
    for node, name in _symbols(tree.body):
        span = (node.end_lineno or node.lineno) - node.lineno + 1
        item = base_symbols.get(name, {})
        maximum = item.get(
            "lines",
            limits["class_lines"] if isinstance(node, ast.ClassDef) else limits["symbol_lines"],
        )
        if span > maximum:
            result.append(
                ("CLASS_LINES" if isinstance(node, ast.ClassDef) else "FUNCTION_LINES", span)
            )
        if not isinstance(node, ast.ClassDef):
            score = _complexity(node)
            maximum_complexity = item.get("complexity", limits["complexity"])
            if score > maximum_complexity:
                result.append(("COMPLEXITY", score))
    base_text = (
        _source(path, config["base_commit"]) if path in _tracked(config["base_commit"]) else ""
    )
    result.extend(_responsibility_violations(path, text, base_text, tree, lines))
    return result


def _responsibility_violations(
    path: str, text: str, base_text: str, tree: ast.Module, lines: int
) -> list[tuple[str, int]]:
    result: list[tuple[str, int]] = []
    if "import *" in text and "import *" not in base_text:
        result.append(("WILDCARD_IMPORT", 0))
    if (
        any(
            "# noqa" in line and not line.lstrip().startswith(("def ", "class "))
            for line in text.splitlines()
        )
        and "# noqa" not in base_text
    ):
        result.append(("FILE_NOQA", 0))
    if path.endswith("persistence/database.py"):
        base_classes = {
            n for node, n in _symbols(ast.parse(base_text).body) if isinstance(node, ast.ClassDef)
        }
        for node, name in _symbols(tree.body):
            if (
                isinstance(node, ast.ClassDef)
                and name.endswith("Repo")
                and name not in base_classes
            ):
                result.append(("DATABASE_REPOSITORY", node.lineno))
    if (
        "/repositories/" in path
        and "from document_intake.persistence.database import" in text
        and "from document_intake.persistence.database import" not in base_text
        and len(tree.body) <= 4
    ):
        result.append(("REPOSITORY_REEXPORT", lines))
    if "/application/services/" in path and any(
        token in text.upper() for token in ("SELECT ", "INSERT ", "UPDATE ", "DELETE ")
    ):
        result.append(("SERVICE_SQL", 0))
    if "/migrations/" in path and "application.services" in text:
        result.append(("MIGRATION_SERVICE", 0))
    return result


def _expected_legacy(config: dict[str, Any]) -> dict[str, Any]:
    expected: dict[str, Any] = {}
    limits = config["limits"]
    for path in _tracked(config["base_commit"]):
        text = _source(path, config["base_commit"])
        entry: dict[str, Any] = {}
        if len(text.splitlines()) > limits["module_lines"]:
            entry["module_lines"] = len(text.splitlines())
        symbols: dict[str, Any] = {}
        for node, name in _symbols(ast.parse(text).body):
            item: dict[str, int] = {}
            span = (node.end_lineno or node.lineno) - node.lineno + 1
            maximum = (
                limits["class_lines"] if isinstance(node, ast.ClassDef) else limits["symbol_lines"]
            )
            if span > maximum:
                item["lines"] = span
            if not isinstance(node, ast.ClassDef) and _complexity(node) > limits["complexity"]:
                item["complexity"] = _complexity(node)
            if item:
                symbols[name] = item
        if symbols:
            entry["symbols"] = symbols
        if entry:
            expected[path] = entry
    return expected


def main() -> int:
    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    if config["legacy"] != _expected_legacy(config):
        print("config/architecture_limits.json BASELINE_INCREASE 0")
        return 1
    errors = []
    for path in _tracked():
        for rule, count in _violations(path, _source(path), config):
            errors.append(f"{path} {rule} {count}")
    if errors:
        print("\n".join(sorted(errors)))
        return 1
    print("architecture_limits PASS 0")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
