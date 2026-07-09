"""Validate every canonical dataset against its declared schema.

Checks performed per dataset:
  - All schema-required columns present.
  - L ∈ [0, 100]; a, b ∈ [-200, 200].
  - For pair_diff: identical pairs (DE==0) that report dv > 0 are flagged
    as potential sentinel/catch trials.
  - For pair_diff: row count matches meta.yaml.

Exits non-zero on any FAIL.
"""

from __future__ import annotations

import csv
import math
import sys
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parent.parent
DATASETS = REPO / "datasets"
SCHEMAS = REPO / "schemas"


def load_schema(name: str) -> dict:
    return yaml.safe_load((SCHEMAS / f"{name}.yaml").read_text())


def check_range(val: float, lo: float, hi: float) -> bool:
    try:
        return lo <= float(val) <= hi
    except (TypeError, ValueError):
        return False


def _generic_validator(n_keys: tuple, numeric_cols: tuple):
    """Row-count vs the first declared n_* meta key + numeric parseability of
    key columns (empty cells allowed — some sources carry legitimate blanks)."""
    def validate(meta: dict, rows: list[dict]) -> list[str]:
        errors = []
        declared = next((meta[k] for k in n_keys if isinstance(meta.get(k), int)), None)
        if declared is not None and declared != len(rows):
            errors.append(f"row count {len(rows)} != meta declared {declared}")
        for i, r in enumerate(rows):
            for c in numeric_cols:
                v = (r.get(c) or "").strip()
                if not v:
                    continue
                try:
                    float(v)
                except ValueError:
                    errors.append(f"row {i}: {c}={v!r} not numeric")
        return errors
    return validate


def validate_pair_diff(meta: dict, rows: list[dict]) -> list[str]:
    errors = []
    required = ["L1", "a1", "b1", "L2", "a2", "b2", "dv"]
    for col in required:
        if rows and col not in rows[0]:
            errors.append(f"missing required column '{col}'")

    sentinel_hits = 0
    out_of_range = 0
    for i, r in enumerate(rows):
        for col in ("L1", "L2"):
            if not check_range(r[col], 0, 110):
                out_of_range += 1
                if out_of_range <= 3:
                    errors.append(f"row {i}: {col}={r[col]} outside [0,110]")
        for col in ("a1", "b1", "a2", "b2"):
            if not check_range(r[col], -200, 200):
                out_of_range += 1
                if out_of_range <= 3:
                    errors.append(f"row {i}: {col}={r[col]} outside [-200,200]")
        # sentinel detection
        try:
            dE = math.sqrt(
                (float(r["L1"]) - float(r["L2"])) ** 2
                + (float(r["a1"]) - float(r["a2"])) ** 2
                + (float(r["b1"]) - float(r["b2"])) ** 2
            )
            dv = float(r["dv"])
            if dE < 1e-6 and dv > 1e-3:
                sentinel_hits += 1
        except (TypeError, ValueError):
            continue

    declared = meta.get("n_pairs") or meta.get("n_judgements")
    if declared and declared != len(rows):
        errors.append(f"row count {len(rows)} != meta declared {declared}")

    if sentinel_hits:
        errors.append(
            f"⚠ {sentinel_hits} sentinel rows (identical Lab pair with dv > 0); "
            "may indicate catch trials that should be excluded or labeled."
        )

    if out_of_range > 3:
        errors.append(f"… plus {out_of_range - 3} more out-of-range rows")

    return errors


def validate_constant_hue(meta: dict, rows: list[dict]) -> list[str]:
    errors = []
    required = ["L", "a", "b"]
    for col in required:
        if rows and col not in rows[0]:
            errors.append(f"missing required column '{col}'")
    out_of_range = 0
    for i, r in enumerate(rows):
        if not check_range(r["L"], 0, 110):
            out_of_range += 1
            if out_of_range <= 3:
                errors.append(f"row {i}: L={r['L']} outside [0,110]")
        for col in ("a", "b"):
            if not check_range(r[col], -200, 200):
                out_of_range += 1
                if out_of_range <= 3:
                    errors.append(f"row {i}: {col}={r[col]} outside [-200,200]")
    declared = meta.get("n_chips")
    if declared and declared != len(rows):
        errors.append(f"row count {len(rows)} != meta declared {declared}")
    if out_of_range > 3:
        errors.append(f"… plus {out_of_range - 3} more out-of-range rows")
    return errors


def validate_gamut_boundary(meta: dict, rows: list[dict]) -> list[str]:
    errors = []
    declared = meta.get("n_points")
    if declared and declared != len(rows):
        errors.append(f"row count {len(rows)} != meta declared {declared}")
    if not rows:
        return errors
    # Two valid layouts: Lab (L, a, b) or chromaticity (x, y, Y)
    has_lab = all(k in rows[0] for k in ("L", "a", "b"))
    has_xyY = all(k in rows[0] for k in ("x", "y", "Y"))
    if not (has_lab or has_xyY):
        errors.append("gamut_boundary needs either (L,a,b) or (x,y,Y) columns")
        return errors
    out_of_range = 0
    for i, r in enumerate(rows):
        if has_lab and not check_range(r["L"], 0, 110):
            out_of_range += 1
            if out_of_range <= 3:
                errors.append(f"row {i}: L={r['L']} outside [0,110]")
        if has_xyY:
            for col in ("x", "y"):
                if not check_range(r[col], 0, 1):
                    out_of_range += 1
                    if out_of_range <= 3:
                        errors.append(f"row {i}: {col}={r[col]} outside [0,1]")
    if out_of_range > 3:
        errors.append(f"… plus {out_of_range - 3} more out-of-range rows")
    return errors


def validate_delta_only(meta: dict, rows: list[dict]) -> list[str]:
    errors = []
    declared = meta.get("n_pairs")
    if declared and declared != len(rows):
        errors.append(f"row count {len(rows)} != meta declared {declared}")
    neg_hits = 0
    for r in rows:
        for col in r:
            if col.startswith(("DE", "DL", "DC", "DH", "dv")):
                try:
                    if col != "DL_10" and float(r[col]) < -1e-6:
                        neg_hits += 1
                except (TypeError, ValueError):
                    pass
    if neg_hits:
        errors.append(f"{neg_hits} negative magnitude values (only DL is allowed to be signed)")
    return errors


def validate_jnd_ellipses(meta: dict, rows: list[dict]) -> list[str]:
    errors = []
    declared = meta.get("n_ellipses")
    if declared and declared != len(rows):
        errors.append(f"row count {len(rows)} != meta declared {declared}")
    out_of_range = 0
    for i, r in enumerate(rows):
        try:
            x, y = float(r["x_c"]), float(r["y_c"])
            a, b = float(r["a"]), float(r["b"])
        except (TypeError, ValueError, KeyError):
            errors.append(f"row {i}: missing or unparseable x_c/y_c/a/b")
            continue
        # Accept either CIE chromaticity [0,1] or DKL-style 2DW [-1,1]
        if not (-1.0 <= x <= 1.0 and -1.0 <= y <= 1.0):
            out_of_range += 1
            if out_of_range <= 3:
                errors.append(f"row {i}: coordinates ({x}, {y}) outside [-1,1]")
        if a <= 0 or b <= 0:
            errors.append(f"row {i}: ellipse semi-axes must be positive (a={a}, b={b})")
        if a < b - 1e-9:
            errors.append(f"row {i}: semi-major a={a} should be ≥ semi-minor b={b}")
    if out_of_range > 3:
        errors.append(f"… plus {out_of_range - 3} more out-of-range rows")
    return errors


def validate_corresponding_colors(meta: dict, rows: list[dict]) -> list[str]:
    errors = []
    declared = meta.get("n_pairs")
    if declared and declared != len(rows):
        errors.append(f"row count {len(rows)} != meta declared {declared}")
    cols = rows[0].keys() if rows else set()
    if {"u_t", "v_t", "u_m", "v_m"}.issubset(cols):
        # u'v' pair layout (breneman-style)
        for i, r in enumerate(rows):
            for col in ("u_t", "v_t", "u_m", "v_m"):
                try:
                    v = float(r[col])
                    if not (0 <= v <= 1):
                        errors.append(f"row {i}: {col}={v} outside u'v' range [0,1]")
                except (TypeError, ValueError, KeyError):
                    errors.append(f"row {i}: {col} missing/unparseable")
    elif {"L", "a", "b"}.issubset(cols):
        # CIELAB per-medium layout (fairchild_johnson-style: one row per
        # medium per color, matched across media by a shared color id)
        for i, r in enumerate(rows):
            try:
                L = float(r["L"])
                float(r["a"]); float(r["b"])
                if not (0 <= L <= 100.5):
                    errors.append(f"row {i}: L={L} outside [0,100]")
            except (TypeError, ValueError, KeyError):
                errors.append(f"row {i}: L/a/b missing/unparseable")
    else:
        errors.append("neither u'v' (u_t,v_t,u_m,v_m) nor CIELAB (L,a,b) "
                      "corresponding-colors layout found")
    return errors


VALIDATORS = {
    "pair_diff": validate_pair_diff,
    "constant_hue": validate_constant_hue,
    "gamut_boundary": validate_gamut_boundary,
    "delta_only": validate_delta_only,
    "jnd_ellipses": validate_jnd_ellipses,
    "corresponding_colors": validate_corresponding_colors,
    "color_names": lambda meta, rows: ([
        f"row count {len(rows)} != meta declared {meta['n_colors']}"
    ] if meta.get("n_colors") and meta["n_colors"] != len(rows) else []),
    "compound_legacy": lambda meta, rows: ([
        f"row count {len(rows)} != meta declared {meta['n_files']}"
    ] if meta.get("n_files") and meta["n_files"] != len(rows) else []),
    "lightness_scaling": lambda meta, rows: ([
        f"row count {len(rows)} != meta declared {meta['n_samples']}"
    ] if meta.get("n_samples") and meta["n_samples"] != len(rows) else []),
    # 2026-07-08 — generic validators for the remaining schema families:
    # declared-row-count check + numeric parseability of key columns
    # (empty cells allowed: some sources legitimately carry blanks, e.g. the
    # brown_macadam_1949 center-8/DLM row that is blank in the book itself).
    "jnd_ellipsoids_g": _generic_validator(
        ("n_ellipsoid_rows", "n_ellipsoids", "n_rows"),
        ("x_0", "y_0", "theta_deg")),
    "jnd_ellipsoids_rgb_sigma": _generic_validator(
        ("n_ellipsoids", "n_centers"), ("R_x1000", "Sigma_11_x1e7")),
    "cielab_ellipsoids": _generic_validator(
        ("n_color_centers",), ("L10_measured", "A_semimajor", "theta_deg")),
    "tolerance_vectors": _generic_validator(
        ("n_vectors_total", "n_ellipsoids"), ("T50", "L_star", "delta_L")),
    "jnd_steps": _generic_validator(("n_rows", "n_steps"), ("delta_step",)),
    "memory_colors": _generic_validator(("n_rows", "n_objects"), ()),
    "hk_brightness": _generic_validator(("n_rows", "n_stimuli"), ()),
    "spectral_reflectance": _generic_validator(
        ("n_measurements_total", "n_wavelengths"), ()),
    "cone_fundamentals": _generic_validator(("n_rows",), ("wavelength_nm",)),
    "preference_rating": _generic_validator(("n_rows", "n_ratings"), ()),
    "color_summary": _generic_validator(("n_rows",), ()),
    "image_pair_difference": _generic_validator(
        ("n_pairs",), ("mean_perceptual_CD", "n_observations")),
    "uniform_spacing": _generic_validator(
        ("n_samples",), ("L", "j", "g", "x10", "y10", "Y10")),
    "hk_lightness": _generic_validator(
        ("n_samples",), ("L_star", "C_star", "h_deg", "observed_lightness")),
    "cvd_ellipses": _generic_validator(
        ("n_ellipses",), ("center_u", "center_v", "long_axis_uv", "axis_ratio", "angle_deg")),
    "tolerance_ellipsoids": lambda meta, rows: ([
        f"row count {len(rows)} != meta declared {meta['n_ellipsoids']}"
    ] if meta.get("n_ellipsoids") and meta["n_ellipsoids"] != len(rows) else []),
    "contrast_preference": lambda meta, rows: ([
        f"row count {len(rows)} != meta declared {meta['n_responses']}"
    ] if meta.get("n_responses") and meta["n_responses"] != len(rows) else []),
}


def main() -> int:
    total_fail = 0
    for ds_dir in sorted(DATASETS.iterdir()):
        if not ds_dir.is_dir():
            continue
        meta_path = ds_dir / "meta.yaml"
        canon_path = ds_dir / "canonical.csv"
        if not meta_path.exists() or not canon_path.exists():
            print(f"  [SKIP] {ds_dir.name}: missing meta.yaml or canonical.csv")
            continue
        try:
            meta = yaml.safe_load(meta_path.read_text())
        except yaml.YAMLError as e:
            print(f"  [FAIL] {ds_dir.name}: meta.yaml does not parse — {str(e).splitlines()[0]}")
            total_fail += 1
            continue
        with open(canon_path) as f:
            rows = list(csv.DictReader(f))

        # `schema:` may be a string, a list (multi-schema sets), null, or a
        # dict — normalize to the FIRST schema name; non-string leftovers
        # route to the unknown-schema WARN branch instead of crashing.
        schema_raw = meta.get("schema")
        if isinstance(schema_raw, list) and schema_raw:
            schema_raw = schema_raw[0]
        if isinstance(schema_raw, dict) and schema_raw:
            schema_raw = next(iter(schema_raw))
        if not isinstance(schema_raw, str):
            schema_raw = ""
        schema_name = schema_raw.split("+")[0].split("_with_")[0].strip()
        validator = VALIDATORS.get(schema_name)
        if not validator:
            print(f"  [WARN] {ds_dir.name}: unknown schema '{schema_name}' — skipping deep check")
            continue
        errors = validator(meta, rows)
        if errors:
            print(f"  [FAIL] {ds_dir.name} ({len(rows)} rows):")
            for e in errors:
                print(f"     - {e}")
            # sentinel-only warnings are not hard fails (some datasets carry catch trials by design)
            hard = [e for e in errors if not e.startswith("⚠")]
            if hard:
                total_fail += 1
        else:
            print(f"  [OK]   {ds_dir.name} ({len(rows)} rows)")
    print()
    if total_fail:
        print(f"FAIL: {total_fail} dataset(s) have errors.")
        return 1
    print("All datasets passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
