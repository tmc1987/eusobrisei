from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Tuple

BASE = Path(__file__).resolve().parents[2] / "contracts" / "schemas"


def _load_schema(name: str) -> Dict[str, Any]:
    return json.loads((BASE / name).read_text(encoding="utf-8"))


def validate_against_schema(payload: Dict[str, Any], schema_name: str) -> Tuple[bool, str]:
    schema = _load_schema(schema_name)
    required = schema.get("required", [])
    missing = [k for k in required if k not in payload]
    if missing:
        return False, f"missing_fields:{','.join(missing)}"

    props = schema.get("properties", {})
    for key, prop in props.items():
        if key not in payload:
            continue
        if "enum" in prop and payload[key] not in prop["enum"]:
            return False, f"invalid_enum:{key}"

    return True, ""
