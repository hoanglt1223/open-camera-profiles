<!--
SPDX-FileCopyrightText: Open Camera contributors
SPDX-License-Identifier: Apache-2.0
-->

# Open Camera device profiles

Lens profiles for Open Camera (`dev.opencamera.app`): which
Camera2 ids are real lenses, which are duplicates, macro or depth helpers, and
which zoom stops (0.6x / 1x / 2x ...) the app shows. The app generates an `auto`
profile on first launch; profiles in this repository are bundled into each app
release and take precedence (`verified` > `community` > `auto`).

## Layout

| Path | Content |
|---|---|
| `schema/device-profile.schema.json` | JSON Schema 2020-12, `schemaVersion: 1` |
| `data/<brand>/<codename>.json` | One profile per device; `id` must equal `<brand>/<codename>` |
| `tools/validate.py` | Schema + semantic validator (stdlib; uses `jsonschema` if installed) |
| `tools/import_leica_profiles.py` | One-off importer for the spec catalog (see Provenance) |

## Two kinds of profile

- **Measured** (`cameras` + `zoomStops`): Camera2 ids, focal lengths and sensor sizes read on
  the phone, for example `xiaomi/gauguin`.
- **Catalog** (`lenses`): the rear lenses a manufacturer publishes (role, 35 mm equivalent
  focal length, zoom label). Values the spec pages do not publish are named in the lens's
  `runtimeFields` and come from Camera2 metadata on the phone.

### Runtime merge

On first launch the app scans Camera2 (listed ids plus probed ids 0-15) and builds an
`auto` profile. It then picks the best bundled profile whose `match` fits `Build.BRAND`
(Xiaomi/Redmi/POCO and vivo/iQOO count as one family) and `Build.DEVICE` or `Build.MODEL`:

- a measured profile replaces the scan;
- a catalog profile keeps the scanned cameras but limits the zoom stops to the published
  roles and uses the published labels (for example 3.7 for a 85 mm tele);
- the user can pin another profile or "Automatic" in Settings; that choice is stored on
  the phone and wins over everything else.

Zoom stops are the main, ultrawide and tele lenses (one stop per physical sensor, duplicate
ids merged), plus a 2x crop of the main when there is no tele. Macro, depth and mono lenses
are never stops.

### Quirks

| Key | Effect in the app |
|---|---|
| `ULTRAWIDE_DUP_ID`, `DUPLICATE_CAMERA_ID` | One sensor under several ids; stops use the lowest id |
| `HIDDEN_PHYSICAL_IDS` | Lenses are not in `getCameraIdList()`; the app probes ids 0-15 and only shows stops it can open |
| `USE_LOGICAL_ZOOM` | Every stop is a zoom ratio on the listed logical camera instead of a camera switch |
| `NO_ZSL`, `JPEG_ORIENTATION_WRONG`, `HDR_VIDEO_BROKEN`, `RAW_BLACK_LEVEL_WRONG` | Capture fixes owned by the capture layer |

## Validate

```sh
pip install jsonschema        # optional, enables the JSON Schema check
python tools/validate.py      # all profiles in data/
python tools/validate.py my-export.json
```

Semantic rules: camera ids unique, `duplicateOf` and `physicalIds` point to
existing cameras, zoom ratios strictly increasing with exactly one `1`, stops
use canonical (non-duplicate) cameras, only `main`/`ultra`/`tele` cameras become
physical or crop stops (never `macro`/`depth`), crop stops use the main camera,
and no field looks like personal data (serial, IMEI, MAC, location, e-mail).

## Contributing a profile

1. In Open Camera open Settings, then "Export device profile", and share the JSON.
2. Check it against `adb shell dumpsys media.camera` and fix roles or stops.
3. Save it as `data/<brand>/<codename>.json`, set `source` to `community`
   (maintainers promote to `verified` after testing on hardware), run the
   validator, and open a pull request or a "Device profile" issue.

Only measured data (focal lengths, sensor sizes, camera ids) or facts from public
spec pages (with the page URL in `provenance.sources`) are accepted.

## Provenance

The catalog profiles (`source: community`, `provenance.importedFrom`) were imported with
`tools/import_leica_profiles.py` from the device catalog of the Leica camera port. That
catalog only holds facts printed on public manufacturer spec pages (brand, marketing name,
model codes, year, lens roles, focal lengths, zoom labels); the pages for each record are
listed in its `provenance.sources` and per-lens `source`. Chinese names and notes were
translated to English. `provenance.ambiguousCodes` lists model codes that more than one
record claims.

Release tags (`vYYYY.MM.DD`) are what the app build pins; see the app's
`openCamera.profiles.version` Gradle property.

## License

Apache-2.0 (see `LICENSE`).