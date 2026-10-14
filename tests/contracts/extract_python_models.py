"""QA-00 static extractor for Python contract models.

Reads Python source files with the standard-library ``ast`` module (no application import, no
installed backend required) and prints JSON describing, per file:

- ``classes``: Pydantic models, dataclasses and enums, with annotated fields (annotation source text
  and whether a default exists), ``unsupported`` constructs the validators must not silently accept
  (extra base classes, field aliases, alias generators, computed fields) and, for enums, their
  member values. Non-string members are emitted as ``<unsupported: ...>`` markers so they never match.
- ``aliases``: module-level ``Name = Literal[...]`` aliases and their string values.

Usage: python -I tests/contracts/extract_python_models.py <file.py> [<file.py> ...]
Exit 0 = JSON on stdout. Exit 1 = a file could not be read or parsed (message on stderr).
"""

from __future__ import annotations

import ast
import json
import sys

_ENUM_BASES = {"StrEnum", "Enum", "IntEnum"}


def _base_names(node: ast.ClassDef) -> list[str]:
    return [ast.unparse(base).split(".")[-1] for base in node.bases]


def _is_dataclass(node: ast.ClassDef) -> bool:
    for decorator in node.decorator_list:
        target = decorator.func if isinstance(decorator, ast.Call) else decorator
        if ast.unparse(target).split(".")[-1] == "dataclass":
            return True
    return False


def _literal_values(node: ast.expr) -> list[str] | None:
    if not (isinstance(node, ast.Subscript) and ast.unparse(node.value).endswith("Literal")):
        return None
    elements = node.slice.elts if isinstance(node.slice, ast.Tuple) else [node.slice]
    return [_member_value(e) for e in elements]


def _member_value(node: ast.expr) -> str:
    """A string member's value; anything else becomes a marker that can never match a contract."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return f"<unsupported: {ast.unparse(node)}>"


_ALIAS_KEYWORDS = {"alias", "serialization_alias", "validation_alias"}


def _unsupported_features(node: ast.ClassDef, kind: str) -> list[str]:
    """Constructs that change field names or the field set beyond what this extractor reads."""
    found = []
    allowed_bases = {"BaseModel"} if kind == "pydantic" else set()
    found += [f"base class {b}" for b in _base_names(node) if b not in allowed_bases]
    for stmt in node.body:
        value = getattr(stmt, "value", None)
        if isinstance(value, ast.Call):
            for keyword in value.keywords:
                if keyword.arg in _ALIAS_KEYWORDS or keyword.arg == "alias_generator":
                    found.append(f"{keyword.arg}= in {ast.unparse(stmt)[:80]}")
        if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for decorator in stmt.decorator_list:
                if ast.unparse(decorator).split("(")[0].split(".")[-1] == "computed_field":
                    found.append(f"@computed_field {stmt.name}")
    return found


def _class_info(node: ast.ClassDef) -> dict[str, object] | None:
    bases = _base_names(node)
    if any(base in _ENUM_BASES for base in bases):
        values = [
            _member_value(stmt.value)
            for stmt in node.body
            if isinstance(stmt, (ast.Assign, ast.AnnAssign)) and stmt.value is not None
        ]
        return {"kind": "enum", "values": values}

    if "BaseModel" in bases:
        kind = "pydantic"
    elif _is_dataclass(node):
        kind = "dataclass"
    else:
        return None

    fields: dict[str, dict[str, object]] = {}
    for stmt in node.body:
        if not (isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name)):
            continue
        name = stmt.target.id
        annotation = ast.unparse(stmt.annotation)
        if name == "model_config" or annotation.startswith(("ClassVar", "typing.ClassVar")):
            continue
        fields[name] = {"annotation": annotation, "has_default": stmt.value is not None}
    return {"kind": kind, "fields": fields, "unsupported": _unsupported_features(node, kind)}


def extract(path: str) -> dict[str, object]:
    with open(path, encoding="utf-8") as handle:
        tree = ast.parse(handle.read(), filename=path)

    classes: dict[str, object] = {}
    aliases: dict[str, list[str]] = {}
    for node in tree.body:
        if isinstance(node, ast.ClassDef):
            info = _class_info(node)
            if info is not None:
                classes[node.name] = info
        elif isinstance(node, ast.Assign) and len(node.targets) == 1:
            target = node.targets[0]
            values = _literal_values(node.value)
            if isinstance(target, ast.Name) and values is not None:
                aliases[target.id] = values
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name) and node.value:
            values = _literal_values(node.value)
            if values is not None:
                aliases[node.target.id] = values
    return {"classes": classes, "aliases": aliases}


def main(paths: list[str]) -> int:
    if not paths:
        print("usage: extract_python_models.py <file.py> [...]", file=sys.stderr)
        return 1
    result: dict[str, object] = {}
    for path in paths:
        try:
            result[path] = extract(path)
        except (OSError, SyntaxError, UnicodeDecodeError) as exc:
            print(f"cannot extract {path}: {exc}", file=sys.stderr)
            return 1
    json.dump(result, sys.stdout, indent=2, sort_keys=True)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
