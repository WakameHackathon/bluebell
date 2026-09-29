"""Dependency-free validator for the JSON Schema keywords used in this excerpt."""
import json
import re
from pathlib import Path

ROOT = Path(__file__).parents[1]
SCHEMA = json.loads((ROOT / "references" / "appeal.schema.json").read_text(encoding="utf-8"))
DEFS = SCHEMA["$defs"]


def validate(value, schema, path="$", errors=None):
    errors = errors if errors is not None else []
    if "$ref" in schema:
        name = schema["$ref"].rsplit("/", 1)[-1]
        validate(value, DEFS[name], path, errors)
        return errors
    typ = schema.get("type")
    checks = {"object": lambda v: isinstance(v, dict), "array": lambda v: isinstance(v, list),
              "string": lambda v: isinstance(v, str), "integer": lambda v: isinstance(v, int) and not isinstance(v, bool),
              "boolean": lambda v: isinstance(v, bool), "null": lambda v: v is None}
    if typ in checks and not checks[typ](value):
        errors.append(f"{path}:type")
        return errors
    if "const" in schema and value != schema["const"]: errors.append(f"{path}:const")
    if "enum" in schema and value not in schema["enum"]: errors.append(f"{path}:enum")
    if isinstance(value, str):
        if len(value) < schema.get("minLength", 0): errors.append(f"{path}:minLength")
        if "pattern" in schema and not re.search(schema["pattern"], value): errors.append(f"{path}:pattern")
    if isinstance(value, int):
        if value < schema.get("minimum", value): errors.append(f"{path}:minimum")
    if isinstance(value, list):
        if len(value) < schema.get("minItems", 0): errors.append(f"{path}:minItems")
        if len(value) > schema.get("maxItems", len(value)): errors.append(f"{path}:maxItems")
        if "items" in schema:
            for i, item in enumerate(value): validate(item, schema["items"], f"{path}[{i}]", errors)
    if isinstance(value, dict):
        for key in schema.get("required", []):
            if key not in value: errors.append(f"{path}:required:{key}")
        props = schema.get("properties", {})
        if schema.get("additionalProperties") is False:
            for key in value.keys() - props.keys(): errors.append(f"{path}:additional:{key}")
        for key, item in value.items():
            if key in props: validate(item, props[key], f"{path}.{key}", errors)
    if "anyOf" in schema:
        alternatives = [validate(value, candidate, path, []) for candidate in schema["anyOf"]]
        if all(alternatives): errors.append(f"{path}:anyOf")
    if "allOf" in schema:
        for candidate in schema["allOf"]: validate(value, candidate, path, errors)
    if "if" in schema:
        condition_errors = validate(value, schema["if"], path, [])
        if not condition_errors and "then" in schema: validate(value, schema["then"], path, errors)
    return errors


def main():
    results = {}
    for file, def_name in (("request.json", "aftercare-appealRequest"), ("result.json", "aftercare-appealResult")):
        payload = json.loads((ROOT / "examples" / file).read_text(encoding="utf-8"))
        errors = validate(payload["body"], {"$ref": f"#/$defs/{def_name}"})
        results[file] = {"valid": not errors, "errors": errors}
    print(json.dumps(results, ensure_ascii=False, indent=2))
    return 0 if all(r["valid"] for r in results.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
