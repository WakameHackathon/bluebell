"""Dependency-free JSON Schema subset validator for the aftercare contracts.

`app.py` previously only compared the *key names* of a result envelope against
`$defs.<skill>Result.required`, so `data` was never checked at all. This module
validates the payload for real: the result envelope *and* the artifact in
`data`, against the central `contracts.schema.json`.

Supported keywords: type, const, enum, required, properties,
additionalProperties, items, $ref (local), allOf, anyOf, oneOf, not,
if/then/else, pattern, minLength, maxLength, minimum, maximum,
minItems, maxItems, minProperties, maxProperties.

Deliberately *not* supported (kept out to stay dependency-free; none are used
by the aftercare contracts for correctness-critical constraints):
``format``, ``uniqueItems``, ``dependentRequired``, ``propertyNames`` and
remote ``$ref``.
"""
from __future__ import annotations

import re
from typing import Any

__all__ = ["SchemaError", "validate", "is_valid", "format_errors", "SPEC_VERSION"]

SPEC_VERSION = "subset-1.0.0"

_MAX_ERRORS = 40

_SIMPLE_TYPES = {
    "object": dict,
    "array": list,
    "string": str,
    "number": (int, float),
    "integer": int,
    "boolean": bool,
    "null": type(None),
}


class SchemaError(Exception):
    """Raised when data does not satisfy the schema it was validated against."""

    def __init__(self, errors: list[str], schema_id: str = ""):
        self.errors = list(errors)
        self.schema_id = schema_id
        where = f" against {schema_id}" if schema_id else ""
        detail = "; ".join(self.errors[:6])
        if len(self.errors) > 6:
            detail += f" (+{len(self.errors) - 6} more)"
        super().__init__(f"schema validation failed{where}: {detail}")


class _Ctx:
    __slots__ = ("root", "errors", "limit")

    def __init__(self, root: Any, limit: int = _MAX_ERRORS):
        # ``root`` is always the *whole* schema document, so a fragment such as
        # ``$defs.aftercare-verifyResult`` can still resolve ``#/$defs/...``.
        self.root = root
        self.errors: list[str] = []
        self.limit = limit

    def err(self, path: str, msg: str) -> None:
        if len(self.errors) < self.limit:
            self.errors.append(f"{path or '$'}: {msg}")

    @property
    def full(self) -> bool:
        return len(self.errors) >= self.limit

    def resolve(self, ref: str) -> Any:
        """Resolve a local JSON pointer such as ``#/$defs/TaskIntent``."""
        if not isinstance(ref, str) or not ref.startswith("#"):
            return None
        node = self.root
        pointer = ref[1:]
        if pointer in ("", "/"):
            return node
        if not pointer.startswith("/"):
            return None
        for raw in pointer[1:].split("/"):
            token = raw.replace("~1", "/").replace("~0", "~")
            if isinstance(node, dict) and token in node:
                node = node[token]
            elif isinstance(node, list):
                try:
                    node = node[int(token)]
                except (ValueError, IndexError):
                    return None
            else:
                return None
        return node


def _type_matches(value: Any, expected: str) -> bool:
    # bool is a subclass of int in Python; keep the two JSON types distinct.
    if expected == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if expected == "boolean":
        return isinstance(value, bool)
    if expected == "object":
        return isinstance(value, dict)
    if expected == "array":
        return isinstance(value, list)
    if expected == "string":
        return isinstance(value, str)
    if expected == "null":
        return value is None
    klass = _SIMPLE_TYPES.get(expected)
    return True if klass is None else isinstance(value, klass)


def _check(schema: Any, value: Any, path: str, ctx: _Ctx) -> None:
    if ctx.full or not isinstance(schema, dict):
        return

    ref = schema.get("$ref")
    if isinstance(ref, str):
        target = ctx.resolve(ref)
        if target is None:
            ctx.err(path, f"unresolvable $ref {ref!r}")
            return
        _check(target, value, path, ctx)
        # A sibling keyword set next to $ref is unusual but legal in 2020-12.
        rest = {k: v for k, v in schema.items() if k != "$ref"}
        if rest:
            _check(rest, value, path, ctx)
        return

    if "const" in schema and value != schema["const"]:
        ctx.err(path, f"expected const {schema['const']!r}, got {value!r}")
    if "enum" in schema and value not in schema["enum"]:
        ctx.err(path, f"{value!r} not in enum {schema['enum']!r}")

    if "type" in schema:
        expected = schema["type"]
        allowed = expected if isinstance(expected, list) else [expected]
        if not any(_type_matches(value, t) for t in allowed):
            ctx.err(path, f"expected type {allowed}, got {type(value).__name__}")
            return  # further keyword checks would be misleading

    if "allOf" in schema:
        for sub in schema["allOf"]:
            _check(sub, value, path, ctx)

    for keyword in ("anyOf", "oneOf"):
        if keyword in schema:
            branches = schema[keyword]
            matched = 0
            for sub in branches:
                probe = _Ctx(ctx.root, ctx.limit)
                _check(sub, value, path, probe)
                if not probe.errors:
                    matched += 1
            if matched == 0:
                ctx.err(path, f"no {keyword} branch matched")
            elif keyword == "oneOf" and matched > 1:
                ctx.err(path, f"{matched} oneOf branches matched, expected exactly 1")

    if "not" in schema:
        probe = _Ctx(ctx.root, ctx.limit)
        _check(schema["not"], value, path, probe)
        if not probe.errors:
            ctx.err(path, "matched a 'not' schema")

    if "if" in schema:
        probe = _Ctx(ctx.root, ctx.limit)
        _check(schema["if"], value, path, probe)
        branch = "then" if not probe.errors else "else"
        if branch in schema:
            _check(schema[branch], value, path, ctx)

    if isinstance(value, str):
        pattern = schema.get("pattern")
        if isinstance(pattern, str):
            try:
                if re.search(pattern, value) is None:
                    ctx.err(path, f"{value!r} does not match pattern {pattern!r}")
            except re.error:
                pass
        if "minLength" in schema and len(value) < schema["minLength"]:
            ctx.err(path, f"shorter than minLength {schema['minLength']}")
        if "maxLength" in schema and len(value) > schema["maxLength"]:
            ctx.err(path, f"longer than maxLength {schema['maxLength']}")

    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if "minimum" in schema and value < schema["minimum"]:
            ctx.err(path, f"{value} < minimum {schema['minimum']}")
        if "maximum" in schema and value > schema["maximum"]:
            ctx.err(path, f"{value} > maximum {schema['maximum']}")

    if isinstance(value, list):
        if "minItems" in schema and len(value) < schema["minItems"]:
            ctx.err(path, f"has {len(value)} items, minItems {schema['minItems']}")
        if "maxItems" in schema and len(value) > schema["maxItems"]:
            ctx.err(path, f"has {len(value)} items, maxItems {schema['maxItems']}")
        items = schema.get("items")
        if isinstance(items, dict):
            for index, item in enumerate(value):
                _check(items, item, f"{path}[{index}]", ctx)

    if isinstance(value, dict):
        properties = schema.get("properties", {})
        if isinstance(properties, dict):
            for name in schema.get("required", []):
                if name not in value:
                    ctx.err(path, f"missing required property {name!r}")
        if "minProperties" in schema and len(value) < schema["minProperties"]:
            ctx.err(path, f"has {len(value)} properties, minProperties {schema['minProperties']}")
        if "maxProperties" in schema and len(value) > schema["maxProperties"]:
            ctx.err(path, f"has {len(value)} properties, maxProperties {schema['maxProperties']}")
        additional = schema.get("additionalProperties", True)
        for name, item in value.items():
            child = f"{path}.{name}"
            if isinstance(properties, dict) and name in properties:
                _check(properties[name], item, child, ctx)
            elif additional is False:
                ctx.err(path, f"unexpected property {name!r} (additionalProperties=false)")
            elif isinstance(additional, dict):
                _check(additional, item, child, ctx)


def _run(schema: Any, value: Any, root: Any) -> list[str]:
    ctx = _Ctx(root if root is not None else schema)
    _check(schema, value, "$", ctx)
    return ctx.errors


def validate(schema: dict, value: Any, schema_id: str = "", root: Any = None) -> None:
    """Validate ``value`` against ``schema``; raise :class:`SchemaError` on failure.

    Pass ``root`` (the enclosing document) when ``schema`` is a fragment whose
    ``$ref``s point elsewhere in that document.
    """
    errors = _run(schema, value, root)
    if errors:
        raise SchemaError(errors, schema_id)


def is_valid(schema: dict, value: Any, root: Any = None) -> bool:
    return not _run(schema, value, root)


def format_errors(schema: dict, value: Any, root: Any = None) -> list[str]:
    return _run(schema, value, root)
