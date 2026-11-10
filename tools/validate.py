#!/usr/bin/env python3
# SPDX-FileCopyrightText: Open Camera contributors
# SPDX-License-Identifier: Apache-2.0
"""Validate device profiles in data/ against the schema and the semantic rules.

Usage: python tools/validate.py [profile.json ...]   (default: every data/**/*.json)
The JSON Schema check runs when the `jsonschema` package is installed; the
semantic checks below always run and need only the standard library.
"""

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCHEMA_PATH = ROOT / "schema" / "device-profile.schema.json"

ZOOM_ROLES = {"main", "ultra", "tele"}
PII_KEYS = re.compile(r"serial|imei|meid|imsi|iccid|androidid|android_id|mac|email|phone|"
                      r"location|latitude|longitude|gps|account", re.IGNORECASE)
PII_VALUES = [
    (re.compile(r"\b\d{14,16}\b"), "looks like an IMEI/IMSI"),
    (re.compile(r"\b[0-9a-f]{2}(:[0-9a-f]{2}){5}\b", re.IGNORECASE), "looks like a MAC address"),
    (re.compile(r"[^@\s]+@[^@\s]+\.[a-z]{2,}", re.IGNORECASE), "looks like an e-mail address"),
]


def walk(node, path="$"):
    if isinstance(node, dict):
        for key, value in node.items():
            yield f"{path}.{key}", key, value
            yield from walk(value, f"{path}.{key}")
    elif isinstance(node, list):
        for i, value in enumerate(node):
            yield from walk(value, f"{path}[{i}]")


def schema_errors(profile, schema):
    try:
        import jsonschema
    except ImportError:
        return []
    validator = jsonschema.Draft202012Validator(schema)
    return [f"schema: {'/'.join(map(str, e.absolute_path)) or '$'}: {e.message}"
            for e in validator.iter_errors(profile)]


def semantic_errors(profile, rel_path, in_data):
    errors = []
    expected_id = "/".join(rel_path.with_suffix("").parts[-2:])
    if in_data and profile.get("id") != expected_id:
        errors.append(f"id '{profile.get('id')}' must match path '{expected_id}'")

    cameras = profile.get("cameras", [])
    by_id = {}
    for cam in cameras:
        if cam.get("id") in by_id:
            errors.append(f"duplicate camera id {cam.get('id')}")
        by_id[cam.get("id")] = cam
    for cam in cameras:
        dup = cam.get("duplicateOf")
        if dup is not None and (dup not in by_id or by_id[dup].get("duplicateOf")):
            errors.append(f"camera {cam['id']}: duplicateOf {dup} must name a canonical camera")
        for pid in cam.get("physicalIds", []):
            if pid not in by_id:
                errors.append(f"camera {cam['id']}: unknown physical id {pid}")

    stops = profile.get("zoomStops", [])
    ratios = [s.get("ratio", 0) for s in stops]
    if any(b <= a for a, b in zip(ratios, ratios[1:])):
        errors.append(f"zoomStops ratios must be strictly increasing: {ratios}")
    if ratios.count(1) != 1:
        errors.append("exactly one zoom stop must have ratio 1")
    for stop in stops:
        cam = by_id.get(stop.get("cameraId"))
        if cam is None:
            errors.append(f"zoom stop {stop.get('label')}: unknown camera {stop.get('cameraId')}")
            continue
        if cam.get("duplicateOf"):
            errors.append(f"zoom stop {stop.get('label')}: camera {cam['id']} is a duplicate id")
        if stop.get("mode") in ("physical", "crop") and cam.get("role") not in ZOOM_ROLES:
            errors.append(f"zoom stop {stop.get('label')}: role '{cam.get('role')}' cannot be a zoom stop")
        if stop.get("mode") == "logical" and cam.get("role") != "logical":
            errors.append(f"zoom stop {stop.get('label')}: logical mode needs a logical camera")
        if stop.get("mode") == "crop" and cam.get("role") != "main":
            errors.append(f"zoom stop {stop.get('label')}: crop stops must use the main camera")

    for path, key, value in walk(profile):
        if PII_KEYS.search(key):
            errors.append(f"{path}: field name suggests personal data")
        if isinstance(value, str):
            for pattern, why in PII_VALUES:
                if pattern.search(value):
                    errors.append(f"{path}: value {why}")
    return errors


def main(argv):
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    files = [Path(a).resolve() for a in argv] or sorted((ROOT / "data").rglob("*.json"))
    seen_ids = {}
    failed = 0
    for file in files:
        in_data = (ROOT / "data") in file.parents
        rel = file.relative_to(ROOT / "data") if in_data else Path(file.name)
        try:
            profile = json.loads(file.read_text(encoding="utf-8-sig"))
        except (OSError, json.JSONDecodeError) as e:
            print(f"FAIL {file}: {e}")
            failed += 1
            continue
        errors = schema_errors(profile, schema) + semantic_errors(profile, rel, in_data)
        pid = profile.get("id")
        if pid in seen_ids:
            errors.append(f"profile id {pid} also defined in {seen_ids[pid]}")
        seen_ids[pid] = file
        if errors:
            failed += 1
            print(f"FAIL {rel}")
            for err in errors:
                print(f"  - {err}")
        else:
            print(f"ok   {rel}")
    print(f"{len(files) - failed}/{len(files)} profiles valid")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))