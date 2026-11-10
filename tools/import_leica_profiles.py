#!/usr/bin/env python3
# SPDX-FileCopyrightText: Open Camera contributors
# SPDX-License-Identifier: Apache-2.0
"""Import the public-spec lens catalog of the Leica camera port into data/.

Usage:
  python tools/import_leica_profiles.py CATALOG.json [EXTRA.json | EXTRA.md ...]

CATALOG.json is the port's `device-profiles.json` ({"profiles": [...]}). Each EXTRA
is a single record in the same format, either a .json file or a Markdown file with
the record in its first ```json block. Extras replace catalog records with the same
id or a shared model code. When the target file already holds measured `cameras`,
only the catalog facts (name, aliases, year, lenses, provenance, model codes) are
merged into it; measured data and `source` are kept.

Every record keeps its facts (brand, name, model codes, year, lens roles, focal
lengths, ratios, source URLs). Chinese text is translated to English. Values the
spec pages do not publish are listed in each lens's `runtimeFields` and are filled
from Camera2 metadata on the phone.
"""

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
IMPORTED_FROM = "Leica camera port device catalog"

CJK = re.compile(r"[　-鿿＀-￯]")
# Longest phrases first; an empty replacement drops page-title and slogan text.
TRANSLATIONS = [
    ("参数 | OPPO 官方网站", ""),
    ("超抗摔金刚石旗舰手机", ""),
    ("卫星通信版", "Satellite Edition"),
    ("活力版", "Energy Edition"),
    ("天玑版", "Dimensity Edition"),
    ("电竞版", "Gaming Edition"),
    ("极速版", "Speed Edition"),
    ("系列", "Series"),
    ("手机", ""),
    ("小米", "Xiaomi"),
    ("超", "Ultra"),
]
NOTE_PARTS = {
    "固定倍率采用公开标识；未取得可靠公开焦距或倍率时由本机镜头参数补齐。只有元数据可读不代表已经调用成功。":
        "Fixed zoom stops follow the manufacturer's published labels; focal lengths or ratios "
        "that are not reliably published are filled from this phone's lens metadata. Readable "
        "metadata alone does not mean the camera can be opened.",
    "独立微距等辅助镜头不列为普通变焦停点。":
        "Dedicated macro and other auxiliary lenses are not ordinary zoom stops.",
    "本机保留兼容路由，避免新增辅助ID进入原生会话。":
        "Keeps the compatibility routing so newly added auxiliary ids do not enter the native session.",
}
RATIO_ORIGINS = {
    "official_optical_zoom", "official_ui_stop", "display_convention",
    "official_optical_reference", "official_continuous_zoom",
}


def translate(text):
    for zh, en in TRANSLATIONS:
        text = text.replace(zh, f" {en} " if en else " ")
    text = re.sub(r"\s+", " ", text).strip(" |")
    if CJK.search(text):
        raise ValueError(f"untranslated Chinese text: {text!r}")
    return text


def translate_note(note):
    note = note.strip()
    out = []
    for zh, en in NOTE_PARTS.items():
        if zh in note:
            out.append(en)
            note = note.replace(zh, "").strip()
    if note:
        out.append(translate(note))
    return " ".join(out)


def unique(items):
    seen, out = set(), []
    for item in items:
        key = re.sub(r"[^a-z0-9]", "", item.lower())
        if item and key not in seen:
            seen.add(key)
            out.append(item)
    return out


def convert_lens(lens):
    role = lens["role"]
    out = {"role": role}
    runtime = []
    mm = lens.get("mm") or 0
    if mm > 0 and lens.get("focal_status") != "runtime_metadata_required":
        out["equivFocalMm"] = mm
        if lens.get("max_mm"):
            out["maxEquivFocalMm"] = lens["max_mm"]
    else:
        runtime.append("equivFocalMm")
    ratio = lens.get("ratio") or 0
    if ratio > 0:
        out["ratio"] = ratio
        if lens.get("max_ratio"):
            out["maxRatio"] = lens["max_ratio"]
        origin = lens.get("ratio_origin")
        out["ratioOrigin"] = origin if origin in RATIO_ORIGINS else "derived"
    elif role not in ("macro", "depth"):
        runtime.append("ratio")
    if runtime:
        out["runtimeFields"] = runtime
    src = lens.get("ratio_source") or lens.get("mm_source")
    if src:
        out["source"] = src
    return out


def convert(rec):
    brand = rec["brand"].lower()
    name = translate(rec["name"])
    aliases = unique([translate(a) for a in rec.get("aliases", [])] + [name])
    codes = unique(rec.get("codes", []))
    # Records without model codes fall back to marketing names, which some ROMs use as Build.MODEL.
    # Lower-case codes are device codenames (Build.DEVICE); the rest are model numbers (Build.MODEL).
    devices = [c for c in codes if re.fullmatch(r"[a-z][a-z0-9_]*", c)]
    models = [c for c in codes if c not in devices]
    match = {"brand": brand, "model": models or aliases}
    if devices:
        match["device"] = devices
    lenses = [convert_lens(l) for l in rec["lenses"] + rec.get("auxiliary_lenses", [])
              if l.get("ratio_origin") != "digital_crop_of_main"]
    order = {"ultra": 0, "main": 1, "tele": 2, "macro": 3, "depth": 4}
    lenses.sort(key=lambda l: (order.get(l["role"], 9), l.get("ratio", 0)))
    sources = unique([rec["source"]] + rec.get("sources", []))
    provenance = {
        "importedFrom": IMPORTED_FROM,
        "sources": [s for s in sources if s.startswith("http")],
        "auditDate": rec["audit_date"],
    }
    if rec.get("ambiguous_codes"):
        provenance["ambiguousCodes"] = rec["ambiguous_codes"]
    return {
        "schemaVersion": 1,
        "id": rec["id"].lower(),
        "name": name,
        "aliases": aliases,
        "year": rec["year"],
        "match": match,
        "lenses": lenses,
        "notes": translate_note(rec.get("note", "")),
        "source": "community",
        "provenance": provenance,
    }


def merge_into_measured(existing, imported):
    """Adds catalog facts to a measured profile without touching its measurements."""
    merged = dict(existing)
    for key in ("name", "aliases", "year", "lenses", "notes", "provenance"):
        merged[key] = imported[key]
    merged["match"] = dict(existing["match"])
    for key in ("device", "model"):
        merged["match"][key] = unique(existing["match"].get(key, []) + imported["match"].get(key, []))
    # Keep the conventional key order: catalog facts right after the id.
    order = ["schemaVersion", "id", "name", "aliases", "year", "match", "cameras", "zoomStops",
             "lenses", "quirks", "vendorTags", "notes", "knownBugs", "source", "provenance",
             "testedBuilds"]
    return {k: merged[k] for k in order if k in merged}


def load_extra(path):
    text = path.read_text(encoding="utf-8")
    if path.suffix == ".md":
        block = re.search(r"```json\s*\n(.*?)```", text, re.S)
        if not block:
            raise ValueError(f"{path}: no ```json block")
        text = block.group(1)
    return json.loads(text)


def write(profile):
    brand, slug = profile["id"].split("/", 1)
    target = DATA / brand / f"{slug}.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(profile, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main(argv):
    if not argv:
        print(__doc__)
        return 2
    catalog = json.loads(Path(argv[0]).read_text(encoding="utf-8"))
    records = {r["id"]: r for r in catalog["profiles"]}
    for extra in map(Path, argv[1:]):
        rec = load_extra(extra)
        for rid, other in list(records.items()):
            if rid == rec["id"] or set(other.get("codes", [])) & set(rec.get("codes", [])):
                del records[rid]
        records[rec["id"]] = rec

    # Existing measured profiles, found by any shared model or device code.
    measured = {}
    for file in DATA.rglob("*.json"):
        prof = json.loads(file.read_text(encoding="utf-8"))
        if prof.get("cameras"):
            for code in prof["match"].get("device", []) + prof["match"].get("model", []):
                measured[code.lower()] = prof

    written = merged = 0
    for rec in records.values():
        profile = convert(rec)
        target = next((measured[c.lower()] for c in rec.get("codes", []) if c.lower() in measured), None)
        if target:
            profile = merge_into_measured(target, profile)
            merged += 1
        write(profile)
        written += 1
    print(f"wrote {written} profiles ({merged} merged into measured profiles)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
