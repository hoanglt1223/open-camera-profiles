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

Only measured data (focal lengths, sensor sizes, camera ids) is accepted. Do not
copy profile files from other camera apps.

## License

Apache-2.0 (see `LICENSE`).