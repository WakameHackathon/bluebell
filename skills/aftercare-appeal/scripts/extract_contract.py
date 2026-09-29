"""Regenerate the package-local schema excerpt from the project authority."""
import hashlib
import json
import argparse
from pathlib import Path

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("source_schema", type=Path, help="authoritative contracts.schema.json")
args = parser.parse_args()
SOURCE = args.source_schema
OUT = Path(__file__).parents[1] / "references" / "appeal.schema.json"
PROV = Path(__file__).parents[1] / "references" / "provenance.json"

source_bytes = SOURCE.read_bytes()
root = json.loads(source_bytes)
defs = root["$defs"]
needed = {"aftercare-appealRequest", "aftercare-appealResult"}

def visit(node):
    if isinstance(node, dict):
        ref = node.get("$ref")
        if isinstance(ref, str) and ref.startswith("#/$defs/"):
            name = ref.rsplit("/", 1)[1]
            if name not in needed:
                needed.add(name)
                visit(defs[name])
        for value in node.values():
            visit(value)
    elif isinstance(node, list):
        for value in node:
            visit(value)

visit({k: defs[k] for k in ("aftercare-appealRequest", "aftercare-appealResult")})
excerpt = {"$schema": root["$schema"], "$id": root["$id"] + "#aftercare-appeal", "title": "Derived aftercare-appeal contract excerpt", "$defs": {k: defs[k] for k in defs if k in needed}}
OUT.write_text(json.dumps(excerpt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
PROV.write_text(json.dumps({"authority": "contracts.schema.json", "authority_id": root["$id"], "contract_version": "1.0.0", "sha256": hashlib.sha256(source_bytes).hexdigest(), "derived_definitions": sorted(needed), "generated_by": "scripts/extract_contract.py", "status": "derived_snapshot_not_authority"}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
