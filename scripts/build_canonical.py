"""Convert each raw dataset into canonical CSV + meta.yaml.

Run from the repo root:
    python3 scripts/build_canonical.py

Sources are read from a sibling directory (../color-space/datasets/) — the
project's working copy. If your raw files live elsewhere, set RAW_ROOT.
"""

from __future__ import annotations

import csv
import hashlib
import json
import math
import os
import re
import shutil
from pathlib import Path

import numpy as np
import openpyxl
import yaml

REPO = Path(__file__).resolve().parent.parent
RAW_ROOT = Path(os.environ.get("RAW_ROOT", REPO.parent / "color-space" / "datasets"))
OUT = REPO / "datasets"

# CIE D65 / 2° reference white (X,Y,Z normalized to Y=1)
D65 = np.array([0.95047, 1.0, 1.08883])
# CIE C / 2° (OSA UCS uses D65 actually; here for reference)
C_2 = np.array([0.98074, 1.0, 1.18232])


# ---------------------------------------------------------------------------
# Color conversion helpers
# ---------------------------------------------------------------------------
def _f(t: np.ndarray) -> np.ndarray:
    delta = 6.0 / 29.0
    return np.where(t > delta**3, np.cbrt(t), t / (3 * delta**2) + 4.0 / 29.0)


def xyz_to_lab(xyz: np.ndarray, white: np.ndarray = D65) -> np.ndarray:
    """xyz: (..., 3). Caller must pass xyz and white on the SAME scale (both 0-1
    or both 0-100). CIELAB only depends on the ratio xyz/white, so internal
    scale conversion is unnecessary and error-prone."""
    xyz = np.asarray(xyz, dtype=float)
    white = np.asarray(white, dtype=float)
    f = _f(xyz / white)
    L = 116 * f[..., 1] - 16
    a = 500 * (f[..., 0] - f[..., 1])
    b = 200 * (f[..., 1] - f[..., 2])
    return np.stack([L, a, b], axis=-1)


def xyY_to_xyz(x: float, y: float, Y: float) -> tuple[float, float, float]:
    if y == 0:
        return 0.0, 0.0, 0.0
    X = x * Y / y
    Z = (1 - x - y) * Y / y
    return X, Y, Z


def srgb_to_linear(c: np.ndarray) -> np.ndarray:
    c = np.asarray(c, dtype=float)
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)


def hex_to_lab(hex_color: str) -> tuple[float, float, float]:
    h = hex_color.lstrip("#")
    rgb = np.array([int(h[i : i + 2], 16) / 255.0 for i in (0, 2, 4)])
    rgb_lin = srgb_to_linear(rgb)
    # sRGB → XYZ (D65) using ITU-R BT.709 matrix
    M = np.array(
        [
            [0.4124564, 0.3575761, 0.1804375],
            [0.2126729, 0.7151522, 0.0721750],
            [0.0193339, 0.1191920, 0.9503041],
        ]
    )
    xyz = M @ rgb_lin
    lab = xyz_to_lab(xyz, D65)
    return float(lab[0]), float(lab[1]), float(lab[2])


def write_meta(path: Path, data: dict) -> None:
    with open(path, "w") as f:
        yaml.safe_dump(data, f, sort_keys=False, allow_unicode=True)


def write_csv(path: Path, rows: list[dict], fieldnames: list[str]) -> None:
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for r in rows:
            w.writerow(r)


def copy_raw(src: Path, dst_dir: Path) -> None:
    dst_dir.mkdir(parents=True, exist_ok=True)
    if src.is_dir():
        for f in src.iterdir():
            shutil.copy2(f, dst_dir / f.name)
    else:
        shutil.copy2(src, dst_dir / src.name)


# ---------------------------------------------------------------------------
# COMBVD
# ---------------------------------------------------------------------------
def build_combvd() -> None:
    print("Building COMBVD…")
    out_dir = OUT / "combvd"
    out_dir.mkdir(parents=True, exist_ok=True)
    raw_dir = out_dir / "raw"
    copy_raw(RAW_ROOT / "combvd_pairs.json", raw_dir)
    copy_raw(RAW_ROOT / "combvd.xlsx", raw_dir)

    # Use the xlsx for sub-dataset labels; json gives clean numeric pairs.
    wb = openpyxl.load_workbook(RAW_ROOT / "combvd.xlsx", data_only=True)
    ws = wb["COM_Corrected_UNWEIGHTED"]
    rows_raw = list(ws.iter_rows(values_only=True))[3:]  # skip 3 header rows

    rows = []
    current_sub = None
    pair_idx = 0
    for r in rows_raw:
        if r[1] is None:
            continue
        if r[0]:
            current_sub = str(r[0]).strip()
        sub = current_sub or "unknown"
        try:
            dv = float(r[1])
            X0, Y0, Z0 = float(r[2]), float(r[3]), float(r[4])
            X1, Y1, Z1 = float(r[5]), float(r[6]), float(r[7])
            X2, Y2, Z2 = float(r[8]), float(r[9]), float(r[10])
        except (TypeError, ValueError):
            continue
        white = np.array([X0, Y0, Z0])
        lab1 = xyz_to_lab(np.array([X1, Y1, Z1]), white)
        lab2 = xyz_to_lab(np.array([X2, Y2, Z2]), white)
        # Illuminant tag from sub-name (e.g. "BFD-P(D65)" → "D65")
        m = re.search(r"\(([^)]+)\)$", sub)
        illum = m.group(1) if m else ""
        sub_clean = re.sub(r"\(.*?\)$", "", sub).strip()
        pair_idx += 1
        rows.append(
            {
                "pair_id": f"combvd_{pair_idx:04d}",
                "L1": round(float(lab1[0]), 6),
                "a1": round(float(lab1[1]), 6),
                "b1": round(float(lab1[2]), 6),
                "L2": round(float(lab2[0]), 6),
                "a2": round(float(lab2[1]), 6),
                "b2": round(float(lab2[2]), 6),
                "dv": round(dv, 6),
                "sub_dataset": sub_clean,
                "illuminant": illum,
            }
        )

    fields = ["pair_id", "L1", "a1", "b1", "L2", "a2", "b2", "dv", "sub_dataset", "illuminant"]
    write_csv(out_dir / "canonical.csv", rows, fields)

    sub_counts: dict[str, int] = {}
    for r in rows:
        sub_counts[r["sub_dataset"]] = sub_counts.get(r["sub_dataset"], 0) + 1

    write_meta(
        out_dir / "meta.yaml",
        {
            "name": "COMBVD",
            "full_name": "Combined Visual Difference dataset",
            "schema": "pair_diff",
            "n_pairs": len(rows),
            "sub_datasets": sub_counts,
            "illuminants": sorted({r["illuminant"] for r in rows if r["illuminant"]}),
            "observer": "CIE 1931 2°",
            "color_space_native": "XYZ → CIELAB",
            "dv_units": "ΔE_CMC-normalized (suprathreshold)",
            "type": "suprathreshold color difference",
            "is_jnd": False,
            "is_suprathreshold": True,
            "description": (
                "Aggregated suprathreshold color-difference dataset combining four classic visual experiments: BFD-P (Luo & Rigg 1987), LEEDS (Kim & Nobbs 1997), RIT-DuPont (Berns et al. 1991), and WITT (Witt 1999). Compiled and used during the CIE TC1-47 work that produced CIEDE2000, and remains the standard training/validation pool for new color-difference formulae and uniform color spaces."
            ),
            "notes": [
                "Three distinct reference whites; canonical CIELAB is computed under each pair's own white, not a common D65 — apply chromatic adaptation before mixing with D65-anchored data.",
                "Sub-dataset nstar (effective observer count) is heterogeneous; BFD-P alone spans 6 sub-experiments with mean DV varying ~58–69. Aggregate fits hide sub-dataset structure.",
                "Original raw/combvd.xlsx preserved unchanged — it contains a WEIGHTED variant sheet (COM_Corrected_WEIGHTED) and the original tristimulus columns if you need them.",
            ],
            "sources": [
                {"sub": "BFD-P", "paper": "Luo, M. R. & Rigg, B. (1987). BFD(l:c) colour-difference formula. Color Research & Application 12, 154–158."},
                {"sub": "LEEDS", "paper": "Kim, H. & Nobbs, J. (1997). New weighting functions for the weighted CIELAB colour difference formula. AIC Color 97."},
                {"sub": "RIT-DuPont", "paper": "Berns, R. S., et al. (1991). Visual determination of suprathreshold color-difference tolerances using probit analysis. Color Research & Application 16, 297–316."},
                {"sub": "WITT", "paper": "Witt, K. (1999). Geometric relations between scales of small colour differences. Color Research & Application 24, 78–92."},
            ],
            "license": "CC BY 4.0 for this canonical export. Cite the sub-dataset papers above when using the data.",
        },
    )
    print(f"  → {len(rows)} pairs, {len(sub_counts)} sub-datasets")


# ---------------------------------------------------------------------------
# MacAdam 1974
# ---------------------------------------------------------------------------
def build_macadam1974() -> None:
    print("Building MacAdam 1974…")
    out_dir = OUT / "macadam1974"
    out_dir.mkdir(parents=True, exist_ok=True)
    raw_dir = out_dir / "raw"
    copy_raw(RAW_ROOT / "macadam1974", raw_dir)

    with open(RAW_ROOT / "macadam1974" / "table1.yaml") as f:
        t1 = yaml.safe_load(f)
    with open(RAW_ROOT / "macadam1974" / "table2.yaml") as f:
        t2 = yaml.safe_load(f)

    # t2: chip_id -> [x, y, Y, L_osa, j_osa, g_osa]; Y is 0-100 scale
    chips = {}
    for cid, vals in t2.items():
        x, y, Y, *_ = vals
        X, Y_, Z = xyY_to_xyz(x, y, Y)  # 0-100 scale
        lab = xyz_to_lab(np.array([X, Y_, Z]), D65 * 100.0)
        chips[str(cid)] = (float(lab[0]), float(lab[1]), float(lab[2]))

    rows = []
    for r in t1:
        idx, c1, c2, dv1, dv2, *_ = r
        c1, c2 = str(c1), str(c2)
        if c1 not in chips or c2 not in chips:
            continue
        L1, a1, b1 = chips[c1]
        L2, a2, b2 = chips[c2]
        # Two observer means → take their mean as canonical dv
        dv = (float(dv1) + float(dv2)) / 2.0
        rows.append(
            {
                "pair_id": f"macadam_{idx:04d}",
                "L1": round(L1, 6),
                "a1": round(a1, 6),
                "b1": round(b1, 6),
                "L2": round(L2, 6),
                "a2": round(a2, 6),
                "b2": round(b2, 6),
                "dv": round(dv, 6),
                "sub_dataset": "OSA_UCS",
                "illuminant": "D65",
            }
        )

    fields = ["pair_id", "L1", "a1", "b1", "L2", "a2", "b2", "dv", "sub_dataset", "illuminant"]
    write_csv(out_dir / "canonical.csv", rows, fields)
    write_meta(
        out_dir / "meta.yaml",
        {
            "name": "MacAdam_1974",
            "full_name": "MacAdam (1974) Uniform Color Scales — OSA UCS pair distances",
            "schema": "pair_diff",
            "n_pairs": len(rows),
            "n_chips": len(chips),
            "illuminant": "D65 / 2°",
            "color_space_native": "OSA UCS chips specified in CIE xyY",
            "dv_units": "OSA UCS visual-difference units (mean of two observer scalings per pair)",
            "type": "suprathreshold color difference (OSA UCS spacing)",
            "is_jnd": False,
            "is_suprathreshold": True,
            "description": (
                "Suprathreshold visual-difference scalings between 59 OSA Uniform Color Scales chips, reported by David MacAdam (1974) as part of the OSA effort to construct a perceptually uniform color sample arrangement. Each of the 128 pairs was scaled by two observers; the canonical dv is their mean. Used as a held-out test set for color-space uniformity claims."
            ),
            "notes": [
                "★ COMMONLY MISIDENTIFIED AS JND DATA. This is suprathreshold OSA UCS sample-pair spacing, NOT the MacAdam (1942) threshold ellipses. If your code labels it `is_jnd=True`, that's a bug — many papers in the literature carry this mistake.",
                "Each pair has two observer scalings; both are preserved in raw/table1.yaml columns 4–5 and the canonical dv is their mean.",
            ],
            "sources": [
                {"paper": "MacAdam, D. L. (1974). Uniform color scales. Journal of the Optical Society of America 64(12), 1691–1702."},
            ],
            "license": "CC BY 4.0 for this canonical export. Cite MacAdam (1974).",
        },
    )
    print(f"  → {len(rows)} pairs, {len(chips)} chips")


# ---------------------------------------------------------------------------
# He 2022
# ---------------------------------------------------------------------------
def build_he2022() -> None:
    print("Building He 2022…")
    out_dir = OUT / "he2022"
    out_dir.mkdir(parents=True, exist_ok=True)
    raw_dir = out_dir / "raw"
    copy_raw(RAW_ROOT / "he2022_3d_printed.xlsx", raw_dir)

    wb = openpyxl.load_workbook(RAW_ROOT / "he2022_3d_printed.xlsx", data_only=True)
    ws_chips = wb["CIELAB of 3D printed samples"]
    all_chip_rows = list(ws_chips.iter_rows(values_only=True))
    # Sheet has 5 groups (Grey, Red, Green, Yellow, Blue), each a label row
    # followed by ~10 numeric rows. We tag each chip with its group.
    chips: dict[str, tuple[float, float, float]] = {}
    chip_groups: dict[str, str] = {}
    current_group = None
    for r in all_chip_rows:
        if r[0] is None:
            continue
        if isinstance(r[0], str) and r[0] in {"Grey", "Red", "Green", "Yellow", "Blue"}:
            current_group = r[0]
            continue
        if isinstance(r[0], (int, float)):
            cid = f"{current_group}_{int(r[0])}" if current_group else str(int(r[0]))
            try:
                chips[cid] = (float(r[1]), float(r[2]), float(r[3]))
                chip_groups[cid] = current_group or ""
            except (TypeError, ValueError):
                continue

    ws_pairs = wb["Information of 3D sample Pairs"]
    pair_rows = list(ws_pairs.iter_rows(values_only=True))
    rows = []
    section = None  # "I" or "II"
    pair_count = 0
    for r in pair_rows:
        # detect section header rows
        if r[0] and isinstance(r[0], str) and r[0].startswith("Experiment"):
            section = "I" if "I" in r[0] and "II" not in r[0] else "II"
            continue
        # data row pattern: (group_or_None, 'Pair N', DEab, DE00, DL, DC, DH, DV_CLAB, DV_DE2000)
        if r[1] and isinstance(r[1], str) and r[1].startswith("Pair"):
            # column layout: DE*ab10, DE00,10, DL, DC, DH, DV(CLAB), DV(DE2000)
            # We need the chip IDs — but this sheet does not contain them directly;
            # the dataset provides Δ values per labeled pair. He 2022 maps Pair-N → chip-pair
            # in a separate enumeration. Without explicit chip indices we cannot reconstruct
            # L1/a1/b1 from the chips sheet. We record pair metadata + the chip-pair Δ values.
            pair_count += 1
            try:
                de00 = float(r[3])
                dv = float(r[7]) if r[7] is not None else None
            except (TypeError, ValueError):
                continue
            rows.append(
                {
                    "pair_id": f"he2022_{section}_{pair_count:03d}",
                    "experiment": section or "?",
                    "pair_label": str(r[1]),
                    "DE_ab10": round(float(r[2]), 6) if r[2] is not None else "",
                    "DE_00_10": round(de00, 6),
                    "DL_10": round(float(r[4]), 6) if r[4] is not None else "",
                    "DC_ab10": round(float(r[5]), 6) if r[5] is not None else "",
                    "DH_ab10": round(float(r[6]), 6) if r[6] is not None else "",
                    "dv_CLAB": round(float(r[7]), 6) if r[7] is not None else "",
                    "dv_DE2000": round(float(r[8]), 6) if r[8] is not None else "",
                }
            )

    fields = [
        "pair_id",
        "experiment",
        "pair_label",
        "DE_ab10",
        "DE_00_10",
        "DL_10",
        "DC_ab10",
        "DH_ab10",
        "dv_CLAB",
        "dv_DE2000",
    ]
    write_csv(out_dir / "canonical.csv", rows, fields)

    # Also write the chip list to a sidecar (the raw xlsx has them but a flat CSV is easier)
    chip_rows_out = [
        {"chip_id": cid, "group": chip_groups.get(cid, ""), "L": L, "a": a, "b": b}
        for cid, (L, a, b) in chips.items()
    ]
    write_csv(out_dir / "chips.csv", chip_rows_out, ["chip_id", "group", "L", "a", "b"])

    write_meta(
        out_dir / "meta.yaml",
        {
            "name": "He_2022_3D_printed",
            "full_name": "He et al. (2022) — 3D-printed spherical samples color-difference",
            "schema": "delta_only",
            "n_pairs": len(rows),
            "n_chips": len(chips),
            "experiments": ["I (42 pairs)", "II (40 pairs)"],
            "illuminant": "D65, CIE 1964 10° observer",
            "color_space_native": "CIELAB (D65, 10°)",
            "dv_units": "Visual difference, two reporting conventions: dv_CLAB (CIELAB-anchored) and dv_DE2000 (DE2000-anchored)",
            "type": "suprathreshold 3D-printed sample color difference",
            "is_jnd": False,
            "is_suprathreshold": True,
            "description": (
                "Color-difference measurements on 45 3D-printed spherical samples by He et al. (2022). Two experiments (I: 42 pairs, II: 40 pairs) measured under D65 with the CIE 1964 10° observer. The unusual physical substrate (matte 3D-printed plastic) makes it a useful out-of-distribution test for color-difference formulae trained on flat paint chips."
            ),
            "notes": [
                "Source xlsx ships chips and pair-Δ values in separate sheets without a shared chip-pair index — the canonical layout therefore keeps chips in chips.csv and per-pair Δ values in canonical.csv with no direct link.",
                "Known scale-compression bias: model fits trained on it underestimate large differences and overestimate small ones. Don't fit a simple linear regression and call it done.",
            ],
            "sources": [
                {"paper": "He, R., Xiao, K., Pointer, M., Bressler, Y., Liu, Z. & Lu, Y. (2022). Development of an Image-Based Measurement System for Human Facial Skin Colour. Color Research & Application."},
            ],
            "license": "CC BY 4.0 for this canonical export. Cite He et al. (2022).",
        },
    )
    print(f"  → {len(rows)} pairs, {len(chips)} chips")


# ---------------------------------------------------------------------------
# HelmlabFB (helmlab.space self-collected test, pseudonymized)
# ---------------------------------------------------------------------------
def build_helmlabfb() -> None:
    print("Building HelmlabFB (pseudonymized)…")
    out_dir = OUT / "helmlabfb"
    out_dir.mkdir(parents=True, exist_ok=True)
    raw_dir = out_dir / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)

    with open(RAW_ROOT / "human_feedback.json") as f:
        d = json.load(f)
    observers = d["observers"]
    judgements = d["judgements"]

    # Deterministic pseudonymization: sort observers alphabetically, assign
    # observer_001..N. Mapping is written to a LOCAL-ONLY file (gitignored).
    observers_sorted = sorted(set(observers + [j["observer_id"] for j in judgements]))
    mapping = {real: f"observer_{i+1:03d}" for i, real in enumerate(observers_sorted)}
    with open(REPO / "observer_mapping.local.json", "w") as f:
        json.dump(mapping, f, indent=2, ensure_ascii=False)

    from datetime import datetime

    def parse_iso(s: str | None) -> datetime | None:
        if not s:
            return None
        try:
            return datetime.fromisoformat(s.replace("Z", "+00:00"))
        except (TypeError, ValueError):
            return None

    rows = []
    skipped_catch = 0
    zone_counts: dict[str, int] = {}
    platform_counts: dict[str, int] = {}
    gamut_counts: dict[str, int] = {}
    durations: list[float] = []
    for jdx, j in enumerate(judgements):
        hex1, hex2 = j["hex1"], j["hex2"]
        if hex1.lower() == hex2.lower():
            skipped_catch += 1
            continue
        L1, a1, b1 = hex_to_lab(hex1)
        L2, a2, b2 = hex_to_lab(hex2)
        pseudo = mapping.get(j["observer_id"], "observer_unknown")
        m = j.get("metadata", {}) or {}
        di = m.get("device_info", {}) or {}
        t_start = parse_iso(di.get("timestamp_start"))
        t_end = parse_iso(di.get("timestamp_end"))
        duration_sec = (t_end - t_start).total_seconds() if t_start and t_end else ""
        if isinstance(duration_sec, (int, float)):
            durations.append(float(duration_sec))

        zone = m.get("zone", "")
        platform = di.get("platform", "")
        gamut = di.get("color_gamut", "")
        zone_counts[zone] = zone_counts.get(zone, 0) + 1
        platform_counts[platform] = platform_counts.get(platform, 0) + 1
        gamut_counts[gamut] = gamut_counts.get(gamut, 0) + 1

        rows.append(
            {
                "pair_id": f"helmlabfb_{jdx:05d}",
                "L1": round(L1, 6),
                "a1": round(a1, 6),
                "b1": round(b1, 6),
                "L2": round(L2, 6),
                "a2": round(a2, 6),
                "b2": round(b2, 6),
                "dv": float(j["perceived_dv"]),
                "category_rating": m.get("category_rating", ""),
                "predicted_de": round(float(m["predicted_de"]), 6) if "predicted_de" in m else "",
                "observer_id": pseudo,
                "hex1": hex1,
                "hex2": hex2,
                "zone": zone,
                "color_gamut": gamut,
                "platform": platform,
                "duration_sec": round(duration_sec, 2) if isinstance(duration_sec, (int, float)) else "",
                "timestamp": j.get("timestamp", ""),
            }
        )

    fields = [
        "pair_id",
        "L1", "a1", "b1",
        "L2", "a2", "b2",
        "dv",
        "category_rating",
        "predicted_de",
        "observer_id",
        "hex1", "hex2",
        "zone",
        "color_gamut",
        "platform",
        "duration_sec",
        "timestamp",
    ]
    write_csv(out_dir / "canonical.csv", rows, fields)

    # Redacted raw — full original structure, observer names replaced
    redacted = {
        "observers": [mapping[o] for o in observers],
        "judgements": [
            {
                **{k: v for k, v in j.items() if k != "observer_id"},
                "observer_id": mapping.get(j["observer_id"], "observer_unknown"),
            }
            for j in judgements
            if j["hex1"].lower() != j["hex2"].lower()
        ],
    }
    with open(raw_dir / "helmlabfb_pseudonymized.json", "w") as f:
        json.dump(redacted, f, indent=2, ensure_ascii=False)

    # Collection window from timestamps
    all_ts = [parse_iso(j.get("timestamp")) for j in judgements]
    all_ts = [t for t in all_ts if t]
    window_first = min(all_ts).isoformat() if all_ts else ""
    window_last = max(all_ts).isoformat() if all_ts else ""
    median_duration = (
        round(sorted(durations)[len(durations) // 2], 2) if durations else None
    )

    write_meta(
        out_dir / "meta.yaml",
        {
            "name": "HelmlabFB",
            "full_name": "helmlab.space color-difference feedback test (pseudonymized)",
            "schema": "pair_diff",
            "n_judgements": len(rows),
            "n_observers": len(set(r["observer_id"] for r in rows)),
            "n_catch_trials_excluded": skipped_catch,
            "collection_window": {"first": window_first, "last": window_last},
            "median_session_duration_sec": median_duration,
            "zones": zone_counts,
            "platforms": platform_counts,
            "color_gamuts": gamut_counts,
            "illuminant": "sRGB D65 (web display)",
            "color_space_native": "sRGB hex; canonical CIELAB computed via IEC 61966-2-1 sRGB→XYZ(D65)→CIELAB(D65)",
            "dv_units": "0–100 slider scale, raw observer response (in practice observers used 5–90)",
            "type": "suprathreshold color difference (mobile-web designed test)",
            "is_jnd": False,
            "is_suprathreshold": True,
            "description": (
                "Self-collected mobile-web color-difference test run by helmlab (helmlab.space) over ~3.5 hours on 24–25 February 2026. 71 Turkish-speaking observers gave 3,477 valid suprathreshold judgements on a 0–100 slider plus a 1–5 categorical rating. Stimuli were not random — pairs are drawn from four designed zones (uniform, hk_boundary, achromatic_chromatic, blue_region) targeting specific perceptual regions. Each pair carries the device/platform/gamut/duration metadata captured at submission time. Useful as a real-world stress test for any color-difference formula or color space, especially for zone-specific failure modes."
            ),
            "notes": [
                "★ Self-collected by helmlab — not a published academic dataset. Cite as such.",
                "Four designed zones (not random sampling). Aggregating across zones dilutes the zone-specific signal — stratify by `zone` when fitting.",
                "`predicted_de` is the L2 Euclidean distance from the helmlab prototype space active at stimulus-design time (formula in helmlab/feedback/generator.py). The prototype predates the public helmlab repo and is not version-pinned, so `predicted_de` is NOT exactly reproducible. r≈0.95 with CIEDE2000 but non-constant scaling. Use it as a design tag, not ground truth.",
                "75 catch trials (identical hex pairs) already excluded — these were designed-in zero-difference pairs for reliability scoring.",
                "No display calibration. Observer monitors and ambient light vary. Stratify by `color_gamut` (sRGB vs P3) and `platform` if you need cleaner subsets.",
                "All observers are Turkish-language users (tr-TR); cross-cultural generalization is unverified.",
                "Observer names → `observer_001`..`observer_071`. The real-name mapping (observer_mapping.local.json) is NOT included in this repository.",
            ],
            "sources": [
                {"note": "Collected by helmlab (https://helmlab.space), February 2026."},
            ],
            "license": "CC BY 4.0. Cite helmlab (helmlab.space) and this repository.",
        },
    )
    print(
        f"  → {len(rows)} judgements, {len(observers_sorted)} observers, "
        f"{len(zone_counts)} zones (catch trials excluded: {skipped_catch})"
    )


# ---------------------------------------------------------------------------
# Hung-Berns
# ---------------------------------------------------------------------------
def build_hung_berns() -> None:
    print("Building Hung-Berns…")
    out_dir = OUT / "hung_berns"
    out_dir.mkdir(parents=True, exist_ok=True)
    raw_dir = out_dir / "raw"
    copy_raw(RAW_ROOT / "hung_berns", raw_dir)

    with open(RAW_ROOT / "hung_berns" / "hung_berns_1995.json") as f:
        d = json.load(f)

    # Table III: constant_lightness XYZ + Table IV: variable_lightness XYZ
    # plus constant_hue_loci_CL. Provide the constant-hue loci as canonical.
    rows = []
    for variant_key, variant_label in [
        ("table_III_constant_lightness_XYZ", "constant_L"),
        ("table_IV_variable_lightness_XYZ", "variable_L"),
    ]:
        if variant_key not in d:
            continue
        entries = d[variant_key]
        # entries is a flat list of dicts: each has Color_name (hue family) + X,Y,Z
        for i, ent in enumerate(entries):
            try:
                hue_name = ent.get("Color_name", f"unk{i}")
                X = float(ent.get("X", 0))
                Y = float(ent.get("Y", 0))
                Z = float(ent.get("Z", 0))
            except (TypeError, ValueError):
                continue
            lab = xyz_to_lab(np.array([X, Y, Z]), D65 * 100.0)
            rows.append(
                {
                    "chip_id": f"hb_{variant_label}_{i:03d}",
                    "hue_id": hue_name,
                    "variant": variant_label,
                    "L": round(float(lab[0]), 6),
                    "a": round(float(lab[1]), 6),
                    "b": round(float(lab[2]), 6),
                    "illuminant": "D65",
                }
            )

    fields = ["chip_id", "hue_id", "variant", "L", "a", "b", "illuminant"]
    write_csv(out_dir / "canonical.csv", rows, fields)
    write_meta(
        out_dir / "meta.yaml",
        {
            "name": "Hung_Berns_1995",
            "full_name": "Hung & Berns (1995) constant-hue loci",
            "schema": "constant_hue",
            "n_chips": len(rows),
            "illuminant": "D65 / 2°",
            "type": "constant-hue lines for hue-uniformity evaluation",
            "description": (
                "Constant-hue chip loci collected by Hung & Berns (1995) on a CRT, used to evaluate how well a color space predicts perceptually constant hue lines. Observers selected chips that appeared to be the same hue at different chroma and lightness levels. Two variants are included: constant-lightness loci (table III) and variable-lightness loci (table IV)."
            ),
            "notes": [
                "Not a color-difference dataset — used for hue-uniformity testing only. A perceptually uniform color space should map chips with the same hue label onto a straight line passing through the achromatic axis.",
                "Famous for revealing the blue-hue rotation problem in CIELAB and (later) the partial improvement in CAM02-UCS and OKLab.",
            ],
            "sources": [
                {"paper": "Hung, P.-C. & Berns, R. S. (1995). Determination of constant hue loci for a CRT gamut and their predictions using color appearance spaces. Color Research & Application 20(5), 285–295."},
            ],
            "license": "CC BY 4.0 for this canonical export. Cite Hung & Berns (1995).",
        },
    )
    print(f"  → {len(rows)} chips")


# ---------------------------------------------------------------------------
# Ebner-Fairchild
# ---------------------------------------------------------------------------
def build_ebner_fairchild() -> None:
    print("Building Ebner-Fairchild…")
    out_dir = OUT / "ebner_fairchild"
    out_dir.mkdir(parents=True, exist_ok=True)
    raw_dir = out_dir / "raw"
    copy_raw(RAW_ROOT / "ebner_fairchild", raw_dir)

    with open(RAW_ROOT / "ebner_fairchild" / "ebner_fairchild_1998.json") as f:
        d = json.load(f)

    rows = []
    for hue_key, hue_data in d.items():
        hue_angle = hue_data.get("hue_angle", hue_key)
        white = np.array(hue_data.get("XYZ_reference_white", [0.95047, 1.0, 1.08883]))
        targets = hue_data.get("XYZ_color_targets", [])
        for i, xyz in enumerate(targets):
            lab = xyz_to_lab(np.array(xyz), white)
            rows.append(
                {
                    "chip_id": f"ef_h{hue_angle}_{i:02d}",
                    "hue_id": str(hue_angle),
                    "variant": "color_target",
                    "L": round(float(lab[0]), 6),
                    "a": round(float(lab[1]), 6),
                    "b": round(float(lab[2]), 6),
                    "illuminant": "D65",
                }
            )

    fields = ["chip_id", "hue_id", "variant", "L", "a", "b", "illuminant"]
    write_csv(out_dir / "canonical.csv", rows, fields)
    write_meta(
        out_dir / "meta.yaml",
        {
            "name": "Ebner_Fairchild_1998",
            "full_name": "Ebner & Fairchild (1998) constant-perceived-hue surfaces",
            "schema": "constant_hue",
            "n_chips": len(rows),
            "n_hue_centers": len(d),
            "illuminant": "D65 / 2° (per-experiment white in raw)",
            "type": "constant-perceived-hue surfaces at 15 hue centers (0°–336° in 24° steps)",
            "description": (
                "Constant-perceived-hue surfaces collected by Ebner & Fairchild (1998) at 15 hue centers spaced 24° apart around the hue circle. Provides denser hue-circle coverage than Hung-Berns and is the standard secondary corroboration for hue-uniformity claims in modern color appearance models."
            ),
            "notes": [
                "Not a color-difference dataset — used for hue-uniformity testing only.",
                "Denser hue coverage than Hung-Berns (15 vs 5 hue families), but still chip-based rather than continuous.",
            ],
            "sources": [
                {"paper": "Ebner, F. & Fairchild, M. D. (1998). Finding constant hue surfaces in color space. Proc. SPIE 3300, 107–117."},
            ],
            "license": "CC BY 4.0 for this canonical export. Cite Ebner & Fairchild (1998).",
        },
    )
    print(f"  → {len(rows)} chips, {len(d)} hue centers")


# ---------------------------------------------------------------------------
# Pointer
# ---------------------------------------------------------------------------
def build_pointer() -> None:
    print("Building Pointer…")
    out_dir = OUT / "pointer"
    out_dir.mkdir(parents=True, exist_ok=True)
    raw_dir = out_dir / "raw"
    copy_raw(RAW_ROOT / "pointer_gamut", raw_dir)

    # Use the LCH json: dict with L_levels, H_angles, data (list of [L*, C*ab, hab])
    src = RAW_ROOT / "pointer_gamut" / "pointer_gamut_lch.json"
    rows = []
    if src.exists():
        with open(src) as f:
            d = json.load(f)
        illum = d.get("illuminant", "CIE Illuminant C").replace("CIE Illuminant ", "").strip() or "C"
        for i, row in enumerate(d.get("data", [])):
            L, C, h = float(row[0]), float(row[1]), float(row[2])
            a = C * math.cos(math.radians(h))
            b = C * math.sin(math.radians(h))
            rows.append(
                {
                    "point_id": f"pointer_{i:04d}",
                    "L": round(L, 6),
                    "a": round(a, 6),
                    "b": round(b, 6),
                    "illuminant": illum,
                }
            )

    fields = ["point_id", "L", "a", "b", "illuminant"]
    write_csv(out_dir / "canonical.csv", rows, fields)
    write_meta(
        out_dir / "meta.yaml",
        {
            "name": "Pointer_1980",
            "full_name": "Pointer (1980) real surface-color gamut",
            "schema": "gamut_boundary",
            "n_points": len(rows),
            "illuminant": "CIE Illuminant SC / 2°",
            "type": "real-world surface-color gamut boundary",
            "description": (
                "Maximum-chroma boundary of real-world surface colors compiled by Michael Pointer (1980) from over 4,000 measured samples (paints, dyes, inks, natural materials). Used as the de-facto reference for how much of a color space's chromaticity volume corresponds to physically realizable surface colors — a wide-gamut display does not need to reach outside this volume."
            ),
            "notes": [
                "Specified under CIE Illuminant SC, not D65. The canonical L,a,b is derived from the LCH source without chromatic adaptation — apply your own CAT (Bradford or CAT02) if you compare against D65-anchored data.",
                "Sparse grid (lightness × hue); interpolate with care, especially near the saturated yellows where the boundary curves sharply.",
            ],
            "sources": [
                {"paper": "Pointer, M. R. (1980). The gamut of real surface colours. Color Research & Application 5(3), 145–155."},
            ],
            "license": "CC BY 4.0 for this canonical export. Cite Pointer (1980).",
        },
    )
    print(f"  → {len(rows)} boundary points")


# ---------------------------------------------------------------------------
# Munsell renotation snapshot (from `colour` library)
# ---------------------------------------------------------------------------
def build_munsell() -> None:
    print("Building Munsell renotation snapshot…")
    out_dir = OUT / "munsell"
    out_dir.mkdir(parents=True, exist_ok=True)

    try:
        import colour
        from colour.notation.datasets.munsell import MUNSELL_COLOURS_REAL
    except Exception as e:
        print(f"  ! colour library not available ({e}); skipping Munsell snapshot.")
        return

    # Illuminant C white point for CIELAB conversion (Munsell native)
    illum_C = np.array([0.98074, 1.0, 1.18232])
    rows = []
    for spec_tuple, xyY_arr in MUNSELL_COLOURS_REAL:
        # spec_tuple = (hue_letter, value, chroma); xyY_arr = [x, y, Y]
        hue_str, value, chroma = spec_tuple
        x, y, Y = float(xyY_arr[0]), float(xyY_arr[1]), float(xyY_arr[2])
        X, Yn, Z = xyY_to_xyz(x, y, Y / 100.0)
        lab = xyz_to_lab(np.array([X, Yn, Z]), illum_C)
        spec = f"{hue_str} {value}/{chroma}"
        rows.append(
            {
                "chip_id": spec,
                "hue_family": hue_str,
                "value": round(float(value), 4),
                "chroma": round(float(chroma), 4),
                "x": round(x, 6),
                "y": round(y, 6),
                "Y": round(Y, 6),
                "L": round(float(lab[0]), 6),
                "a": round(float(lab[1]), 6),
                "b": round(float(lab[2]), 6),
                "illuminant": "C",
            }
        )

    fields = ["chip_id", "hue_family", "value", "chroma", "x", "y", "Y", "L", "a", "b", "illuminant"]
    write_csv(out_dir / "canonical.csv", rows, fields)
    write_meta(
        out_dir / "meta.yaml",
        {
            "name": "Munsell_renotation_real",
            "full_name": "Munsell Renotation Data (real chips)",
            "schema": "constant_hue",
            "n_chips": len(rows),
            "illuminant": "CIE Illuminant C / 2°",
            "type": "Munsell renotation chips (hue × value × chroma grid)",
            "description": (
                "Snapshot of the Munsell Renotation (Newhall, Nickerson & Judd 1943) for chips physically realizable in paint. Maps each Munsell notation (hue, value, chroma) to CIE xyY under illuminant C. Munsell's hue × value × chroma arrangement is perceptually uniform by construction, which makes this dataset the standard reference grid for evaluating constant-hue lines, constant-value planes, and the lightness scale of a candidate color space."
            ),
            "notes": [
                "Native illuminant is C (Munsell paper's standard). Apply chromatic adaptation before comparing with D65-anchored data.",
                "This is the `real` subset — chips that can actually be produced in paint. The full `all` renotation includes extrapolated chips outside the realizable gamut; not included here.",
                "Snapshot from the `colour` Python library (MUNSELL_COLOURS_REAL) for offline reproducibility, so the data is identical regardless of which version of `colour` you have installed.",
            ],
            "sources": [
                {"paper": "Newhall, S. M., Nickerson, D. & Judd, D. B. (1943). Final report of the OSA subcommittee on the spacing of the Munsell colors. Journal of the Optical Society of America 33(7), 385–418."},
                {"paper": "Munsell, A. H. (1905). A Color Notation. Boston: G. H. Ellis."},
            ],
            "license": "CC BY 4.0 for this canonical export. Underlying data is public-domain.",
        },
    )
    print(f"  → {len(rows)} chips")


# ---------------------------------------------------------------------------
# MacAdam 1942 JND ellipses (from colour library)
# ---------------------------------------------------------------------------
def build_macadam1942() -> None:
    print("Building MacAdam 1942 ellipses…")
    out_dir = OUT / "macadam1942"
    out_dir.mkdir(parents=True, exist_ok=True)
    try:
        import colour
        m = colour.DATA_MACADAM_1942_ELLIPSES
    except Exception as e:
        print(f"  ! colour library missing ({e}); skipping.")
        return
    # Columns per row: [x_c, y_c, 10*a, 10*b, theta_deg, sqrt(g11), sqrt(g22), sqrt(g33)]
    rows = []
    for i, r in enumerate(m):
        x_c, y_c, a10, b10, theta = float(r[0]), float(r[1]), float(r[2]), float(r[3]), float(r[4])
        rows.append({
            "center_id": f"macadam1942_{i+1:02d}",
            "x_c": round(x_c, 6),
            "y_c": round(y_c, 6),
            "a": round(a10 / 1000.0, 8),     # convert "10*a" → a in chromaticity units (a was scaled by 10³ in source)
            "b": round(b10 / 1000.0, 8),
            "theta_deg": round(theta, 4),
            "illuminant": "C",  # MacAdam 1942 used Illuminant C
        })
    write_csv(out_dir / "canonical.csv", rows,
              ["center_id", "x_c", "y_c", "a", "b", "theta_deg", "illuminant"])
    write_meta(out_dir / "meta.yaml", {
        "name": "MacAdam_1942_Ellipses",
        "full_name": "MacAdam (1942) discrimination ellipses (Observer PGN)",
        "schema": "jnd_ellipses",
        "n_ellipses": len(rows),
        "illuminant": "CIE Illuminant C",
        "type": "JND threshold ellipses",
        "is_jnd": True,
        "is_suprathreshold": False,
        "description": (
            "The classic 25 just-noticeable-difference (JND) chromaticity ellipses measured by David MacAdam in 1942 under daylight illumination, using a single highly trained observer (Perley G. Nutting Jr., 'PGN'). Each ellipse maps the locus of color matches around a fixed center — the inside of the ellipse is the threshold of perceptual indistinguishability. Foundational data for color discrimination thresholds, the inspiration for the entire 'perceptually uniform color space' research line, and the reason CIELAB and CIELUV were developed."
        ),
        "notes": [
            "★ This is the REAL JND dataset — not to be confused with MacAdam (1974) OSA UCS which is suprathreshold. Many papers cite '1942' but use '1974' data, or vice versa. Always check.",
            "Single observer (PGN). MacAdam later replicated with 2 more observers in 1949 but the 1942 PGN data is the canonical set used in every textbook.",
            "Ellipse semi-axes (a, b) are stored in CIE chromaticity units, NOT the source paper's ×10³ convention — divide-by-1000 already applied in canonical.csv.",
            "Illuminant C (Munsell-era daylight standard); apply chromatic adaptation if using under D65.",
        ],
        "sources": [
            {"paper": "MacAdam, D. L. (1942). Visual Sensitivities to Color Differences in Daylight. Journal of the Optical Society of America 32(5), 247–274."},
            {"paper": "Wyszecki, G. & Stiles, W. S. (2000). Color Science: Concepts and Methods, Quantitative Data and Formulae, Table 2(5.4.1). Wiley."},
            {"snapshot_source": "colour.DATA_MACADAM_1942_ELLIPSES (BSD-3 licensed source data)"},
        ],
        "license": "CC BY 4.0 for this canonical export. Underlying data public-domain (1942 publication).",
    })
    print(f"  → {len(rows)} ellipses")


# ---------------------------------------------------------------------------
# Breneman 1987 corresponding colors
# ---------------------------------------------------------------------------
def build_breneman1987() -> None:
    print("Building Breneman 1987 corresponding colors…")
    out_dir = OUT / "breneman1987"
    out_dir.mkdir(parents=True, exist_ok=True)
    try:
        import colour
        exps = colour.BRENEMAN_EXPERIMENTS
    except Exception as e:
        print(f"  ! colour library missing ({e}); skipping.")
        return
    rows = []
    pid = 0
    for exp_id, pairs in exps.items():
        for p in pairs:
            pid += 1
            ut, vt = float(p.uv_t[0]), float(p.uv_t[1])
            um, vm = float(p.uv_m[0]), float(p.uv_m[1])
            s = getattr(p, "s_uv", None)
            row = {
                "pair_id": f"breneman_{pid:04d}",
                "experiment_id": f"Breneman_Exp_{exp_id}",
                "color_name": getattr(p, "name", ""),
                "u_t": round(ut, 6),
                "v_t": round(vt, 6),
                "u_m": round(um, 6),
                "v_m": round(vm, 6),
                "sigma_u": round(float(s[0]), 4) if s is not None else "",
                "sigma_v": round(float(s[1]), 4) if s is not None else "",
            }
            rows.append(row)

    write_csv(out_dir / "canonical.csv", rows,
              ["pair_id", "experiment_id", "color_name",
               "u_t", "v_t", "u_m", "v_m", "sigma_u", "sigma_v"])

    by_exp: dict[str, int] = {}
    for r in rows:
        by_exp[r["experiment_id"]] = by_exp.get(r["experiment_id"], 0) + 1

    write_meta(out_dir / "meta.yaml", {
        "name": "Breneman_1987",
        "full_name": "Breneman (1987) corresponding-colors experiments",
        "schema": "corresponding_colors",
        "n_pairs": len(rows),
        "experiments": by_exp,
        "color_space_native": "CIE 1976 u'v' chromaticity",
        "type": "chromatic-adaptation corresponding-colors data",
        "is_jnd": False,
        "is_suprathreshold": False,
        "description": (
            "Twelve memory-matching and haploscopic-matching experiments by Edwin Breneman (1987), pairing test stimuli viewed under one illuminant with the chromaticities observers reported as 'looking the same' under the reference illuminant. Used as the empirical ground truth for chromatic adaptation transforms — CAT02 and CIECAM02 were both validated against subsets of this data. Each pair carries the matched chromaticities plus inter-observer scatter when reported."
        ),
        "notes": [
            "Twelve separate experiments under different illuminants and adaptation conditions; filter by `experiment_id` if you want a single condition.",
            "Some pairs include inter-observer scatter (sigma_u, sigma_v); others don't — empty cells are real, not missing-data bugs.",
            "Data is in u'v' chromaticity space (no luminance) — combine with the experiment's stated white point and Y-level to recover full XYZ.",
        ],
        "sources": [
            {"paper": "Breneman, E. J. (1987). Corresponding chromaticities for different states of adaptation to complex visual fields. Journal of the Optical Society of America A 4(6), 1115–1129."},
            {"snapshot_source": "colour.BRENEMAN_EXPERIMENTS (BSD-3 licensed source data)"},
        ],
        "license": "CC BY 4.0 for this canonical export. Cite Breneman (1987).",
    })
    print(f"  → {len(rows)} pairs across {len(by_exp)} experiments")


# ---------------------------------------------------------------------------
# MacAdam 1935 Optimal Color Stimuli
# ---------------------------------------------------------------------------
def build_macadam1935() -> None:
    print("Building MacAdam 1935 Optimal Color Stimuli…")
    out_dir = OUT / "macadam1935_optimal"
    out_dir.mkdir(parents=True, exist_ok=True)
    try:
        from colour.volume.datasets.optimal_colour_stimuli import (
            OPTIMAL_COLOUR_STIMULI_ILLUMINANTS as O,
        )
    except Exception as e:
        print(f"  ! colour library missing ({e}); skipping.")
        return
    rows = []
    pid = 0
    for illum, arr in O.items():
        for r in arr:
            pid += 1
            x, y, Y = float(r[0]), float(r[1]), float(r[2])
            rows.append({
                "point_id": f"optimal_{illum}_{pid:04d}",
                "illuminant": illum,
                "x": round(x, 6),
                "y": round(y, 6),
                "Y": round(Y, 4),
            })
    write_csv(out_dir / "canonical.csv", rows,
              ["point_id", "illuminant", "x", "y", "Y"])
    counts = {k: int(v.shape[0]) for k, v in O.items()}
    write_meta(out_dir / "meta.yaml", {
        "name": "MacAdam_1935_Optimal_Colors",
        "full_name": "MacAdam (1935) optimal color stimuli — theoretical color-volume boundary",
        "schema": "gamut_boundary",
        "n_points": len(rows),
        "by_illuminant": counts,
        "illuminants": list(O.keys()),
        "type": "theoretical maximum-reflectance color volume",
        "description": (
            "Spectral boundary of the theoretical maximum-luminance-factor color stimuli derived by David MacAdam in 1935. Each point is a chromaticity on the boundary of what is physically realizable as a surface color under the named illuminant — the upper bound that no real ink, paint, or dye can exceed. Provided for illuminants A, C, and D65. Used as a theoretical ceiling for surface-color gamut coverage, distinct from Pointer's empirical real-color gamut."
        ),
        "notes": [
            "Theoretical bound, not measured surface colors. Combine with Pointer 1980 to compare 'what's physically possible' vs 'what's been observed in real pigments'.",
            "Three illuminants (A, C, D65). Filter by `illuminant` for a single set.",
            "Boundary points are sparse; interpolation needs care near the yellow corner where the boundary is sharply curved.",
        ],
        "sources": [
            {"paper": "MacAdam, D. L. (1935). Maximum visual efficiency of colored materials. Journal of the Optical Society of America 25(11), 361–367."},
            {"snapshot_source": "colour.volume.datasets.OPTIMAL_COLOUR_STIMULI_ILLUMINANTS (BSD-3 licensed source data)"},
        ],
        "license": "CC BY 4.0 for this canonical export. Underlying data public-domain.",
    })
    print(f"  → {len(rows)} points across {len(O)} illuminants")


# ---------------------------------------------------------------------------
# Corresponding-Colour Datasets (Luo & Rhodes 1999, Zenodo 3270903)
# ---------------------------------------------------------------------------
def build_corresponding_colours() -> None:
    print("Building Corresponding-Colour Datasets (Luo & Rhodes 1999)…")
    out_dir = OUT / "corresponding_colours"
    raw_dir = out_dir / "raw"
    if not raw_dir.exists() or not any(raw_dir.iterdir()):
        print("  ! raw/ missing or empty; skipping.")
        return

    # Each .dat: line1 = 6 numbers (whitepoint_test_XYZ + whitepoint_ref_XYZ),
    # line2 = n_pairs, following lines = 6 numbers (test_XYZ + ref_XYZ).
    rows = []
    counts: dict[str, int] = {}
    for path in sorted(raw_dir.iterdir()):
        if path.suffix != ".dat":
            continue
        name = path.stem  # e.g. "Brene.p1", "CSAJ.da", "mcan.r"
        # subdataset = leading family token
        family = name.split(".")[0]
        try:
            text = path.read_text().split()
            nums = [float(t) for t in text]
        except (ValueError, OSError) as e:
            print(f"  skip {path.name}: {e}")
            continue
        if len(nums) < 7:
            continue
        wp_t = tuple(nums[0:3])
        wp_r = tuple(nums[3:6])
        n_pairs = int(nums[6])
        if len(nums) < 7 + n_pairs * 6:
            print(f"  {path.name}: declared {n_pairs} pairs but only {len(nums)-7} numbers")
            continue
        for i in range(n_pairs):
            base = 7 + i * 6
            X_t, Y_t, Z_t = nums[base : base + 3]
            X_r, Y_r, Z_r = nums[base + 3 : base + 6]
            # Convert XYZ to u'v' chromaticity for the corresponding_colors schema
            def xyz_to_uv(X, Y, Z):
                denom = X + 15 * Y + 3 * Z
                if denom < 1e-12:
                    return 0.0, 0.0
                return 4 * X / denom, 9 * Y / denom

            u_t, v_t = xyz_to_uv(X_t, Y_t, Z_t)
            u_r, v_r = xyz_to_uv(X_r, Y_r, Z_r)
            rows.append({
                "pair_id": f"{name}_{i+1:03d}",
                "experiment_id": name,
                "dataset_family": family,
                "color_name": "",
                "u_t": round(u_t, 6),
                "v_t": round(v_t, 6),
                "u_m": round(u_r, 6),
                "v_m": round(v_r, 6),
                "X_t": round(X_t, 4), "Y_t": round(Y_t, 4), "Z_t": round(Z_t, 4),
                "X_r": round(X_r, 4), "Y_r": round(Y_r, 4), "Z_r": round(Z_r, 4),
                "whitepoint_test_xyz": f"{wp_t[0]:.2f},{wp_t[1]:.2f},{wp_t[2]:.2f}",
                "whitepoint_reference_xyz": f"{wp_r[0]:.2f},{wp_r[1]:.2f},{wp_r[2]:.2f}",
            })
        counts[family] = counts.get(family, 0) + n_pairs

    write_csv(out_dir / "canonical.csv", rows,
              ["pair_id", "experiment_id", "dataset_family", "color_name",
               "u_t", "v_t", "u_m", "v_m",
               "X_t", "Y_t", "Z_t", "X_r", "Y_r", "Z_r",
               "whitepoint_test_xyz", "whitepoint_reference_xyz"])

    write_meta(out_dir / "meta.yaml", {
        "name": "Corresponding_Colours_Luo_Rhodes_1999",
        "full_name": "Corresponding-Colour Datasets (Luo & Rhodes 1999 compilation)",
        "schema": "corresponding_colors",
        "n_pairs": len(rows),
        "dataset_families": counts,
        "color_space_native": "CIE XYZ (whitepoint-referenced); canonical u'v' computed",
        "type": "chromatic-adaptation corresponding-colors compilation",
        "is_jnd": False,
        "is_suprathreshold": False,
        "description": (
            "A compilation of corresponding-colors experiments curated by Luo & Rhodes (1999) and republished on Zenodo, bundling nine independent studies into a single comparable format: Breneman 1987 (12 phases), CSAJ (Color Science Association of Japan), Helson 1938, Hunt-via-LUTCHI, Kuo, Lam, McCann mondrian (r/g/b/y/grey backgrounds), RIT 1–4, and Stevens-style scaling experiments. Each row pairs a test stimulus (viewed under one illuminant) with the matched stimulus (viewed under the reference illuminant). The canonical export keeps both XYZ and u'v' columns so users can choose their working representation. This is the de facto training set for chromatic adaptation transforms (CAT02, CAT16, Bradford) and color appearance models (CIECAM02, CIECAM16)."
        ),
        "notes": [
            "Multi-source compilation. Filter by `experiment_id` or `dataset_family` to recover a single original experiment. CSAJ, Helson 1938, McCann mondrian and Stevens-style scalings are otherwise hard to obtain.",
            "Some experiments overlap with our standalone Breneman 1987 dataset (sourced via colour); use whichever copy matches your downstream tooling. The numbers should be identical.",
            "Original Zenodo record (DOI: 10.5281/zenodo.3270903) lists license as 'notspecified'. Included here on the same academic-use convention used by colour-science, AIM3, ColorAIDE, and other downstream projects. Cite Luo & Rhodes (1999) when using the data.",
            "Per-pair white-point XYZ for both test and reference is preserved in the last two columns so you can rebuild the experiment's full radiometric context.",
        ],
        "sources": [
            {"paper": "Luo, M. R. & Rhodes, P. A. (1999). Corresponding-colour datasets. Color Research & Application 24(4), 295–296."},
            {"paper": "Breneman, E. J. (1987). Corresponding chromaticities… JOSA A 4(6), 1115–1129."},
            {"paper": "Helson, H. (1938). Fundamental problems in color vision I. JOSA 28(7), 252–264."},
            {"paper": "McCann, J. J., McKee, S. P. & Taylor, T. H. (1976). Quantitative studies in retinex theory. Vision Research 16(5), 445–458."},
            {"snapshot_source": "Zenodo DOI 10.5281/zenodo.3270903 (Luo & Rhodes 1999 republished compilation)"},
        ],
        "license": "License unspecified by uploader on Zenodo. Included for research convenience under the academic-use convention. Cite Luo & Rhodes (1999) and the individual experiment authors.",
    })
    print(f"  → {len(rows)} pairs across {len(counts)} dataset families")


# ---------------------------------------------------------------------------
# LUTCHI Colour Appearance Data (Luo & Rhodes 1997, Zenodo 4394536)
# ---------------------------------------------------------------------------
def build_lutchi() -> None:
    print("Building LUTCHI Colour Appearance Data…")
    out_dir = OUT / "lutchi"
    raw_dir = out_dir / "raw"
    if not raw_dir.exists() or not any(raw_dir.iterdir()):
        print("  ! raw/ missing or empty; skipping.")
        return

    # LUTCHI ships ~100 small files of mixed formats (mean appearance estimates,
    # colorimetric reference data, per-phase variants, multiple sub-experiments).
    # We don't try to parse every variant — instead we build an index.csv that
    # lists each raw file with its purpose so users can navigate without guessing.

    def classify(name: str) -> str:
        n = name.lower()
        if n.startswith("mean.") or n.startswith("mean4."):
            return "mean appearance estimates"
        if n.startswith("nlmean.") or n.startswith("nla.") or n.startswith("nld65."):
            return "non-linear mean appearance estimates"
        if n.startswith("col.") or n.startswith("cold") or n.startswith("colah") or n.startswith("colal") or n.startswith("colwf"):
            return "colorimetric reference data"
        if n.startswith("kuo."):
            return "Kuo experiment"
        if n.startswith("bit_p"):
            return "BIT experiment"
        if "wf" in n:
            return "weighted fit"
        if "mean" in n:
            return "mean variant"
        return "other"

    index_rows = []
    for path in sorted(raw_dir.iterdir()):
        if path.is_file():
            index_rows.append({
                "filename": path.name,
                "size_bytes": path.stat().st_size,
                "category": classify(path.name),
                "lines": sum(1 for _ in path.open()) if path.suffix != ".zip" else "",
            })
    write_csv(out_dir / "canonical.csv", index_rows,
              ["filename", "size_bytes", "category", "lines"])

    cats: dict[str, int] = {}
    for r in index_rows:
        cats[r["category"]] = cats.get(r["category"], 0) + 1

    write_meta(out_dir / "meta.yaml", {
        "name": "LUTCHI_1997",
        "full_name": "LUTCHI Colour Appearance Data (Luo & Rhodes 1997)",
        "schema": "compound_legacy",
        "n_files": len(index_rows),
        "categories": cats,
        "type": "color appearance — magnitude estimations across multiple experiments",
        "is_jnd": False,
        "is_suprathreshold": True,
        "description": (
            "The LUTCHI (Loughborough University of Technology, Computer Human Interface) color-appearance dataset compiled by Luo & Rhodes (1997). 43,332 magnitude estimations across multiple experiments (BIT, Kuo, mean appearance phases p1–p12) under varying illuminants, surround conditions, and adaptation states. Standard empirical basis for CAM02, CIECAM02 and CIECAM16 validation. The dataset ships as ~100 small plain-text files with mixed schemas — this canonical export does NOT attempt to merge them into a single table; instead, `canonical.csv` is an index of every raw file with its category, and the original .dat files live unchanged in `raw/`."
        ),
        "notes": [
            "★ Compound dataset — `canonical.csv` is just an index, not a flat table. To use a specific experiment, read its raw file directly (e.g. `raw/mean.p1` for phase-1 mean appearance estimates). See the Luo & Rhodes 1997 paper for per-file schemas.",
            "File naming convention: `mean.pN` = mean magnitude estimates for phase N; `col.pN` = colorimetric reference data; `kuo.*` = Kuo experiment; `bit_pN.*` = BIT experiment phase N; `nl*` = non-linear analysis variants.",
            "Original Zenodo record (DOI: 10.5281/zenodo.4394536) lists license as 'notspecified'. Included here on the academic-use convention. Cite Luo, Clarke, Rhodes, Schappo, Scrivener & Tait (1991) and Luo & Rhodes (1997).",
            "Some files in the bundle are appearance estimates without colorimetric anchoring — useful only paired with the matching `col.*` file from the same phase.",
        ],
        "sources": [
            {"paper": "Luo, M. R., Clarke, A. A., Rhodes, P. A., Schappo, A., Scrivener, S. A. R. & Tait, C. J. (1991). Quantifying colour appearance. Part I. LUTCHI colour appearance data. Color Research & Application 16(3), 166–180."},
            {"paper": "Luo, M. R. & Rhodes, P. A. (1997). Using the LUTCHI Colour-Appearance Data. In: Color Research & Application, Wiley."},
            {"snapshot_source": "Zenodo DOI 10.5281/zenodo.4394536"},
        ],
        "license": "License unspecified by uploader on Zenodo. Included for research convenience under the academic-use convention. Cite the LUTCHI papers above.",
    })
    print(f"  → {len(index_rows)} raw files indexed across {len(cats)} categories")


# ---------------------------------------------------------------------------
# Alder et al. 1982 — chromaticity discrimination ellipses (D65 + A)
# ---------------------------------------------------------------------------
def build_alder1982() -> None:
    print("Building Alder 1982 ellipses…")
    out_dir = OUT / "alder1982"
    raw_dir = out_dir / "raw"
    if not raw_dir.exists():
        print("  ! raw/ missing; skipping.")
        return
    rows = []
    for tbl_file, illum in [("table4.dat", "D65"), ("table5.dat", "A")]:
        path = raw_dir / tbl_file
        if not path.exists():
            continue
        for line in path.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split()
            if len(parts) < 8:
                continue
            try:
                set_id = " ".join(parts[:2])  # e.g. "RCK 1"
                x_c = float(parts[2]); y_c = float(parts[3]); Y = float(parts[4])
                a_e4 = float(parts[5]); ratio = float(parts[6]); theta = float(parts[7])
                a = a_e4 / 10000.0
                b = a / ratio
            except (ValueError, IndexError):
                continue
            rows.append({
                "center_id": f"alder1982_{illum}_{set_id.replace(' ','_')}",
                "x_c": round(x_c, 6), "y_c": round(y_c, 6),
                "a": round(a, 8), "b": round(b, 8),
                "theta_deg": round(theta, 4),
                "Y": round(Y, 4),
                "illuminant": illum,
            })
    write_csv(out_dir / "canonical.csv", rows,
              ["center_id", "x_c", "y_c", "a", "b", "theta_deg", "Y", "illuminant"])
    by_illum: dict[str, int] = {}
    for r in rows:
        by_illum[r["illuminant"]] = by_illum.get(r["illuminant"], 0) + 1
    write_meta(out_dir / "meta.yaml", {
        "name": "Alder_1982_Ellipses",
        "full_name": "Alder, Chaing, Chong, Coates, Khalili & Rigg (1982) chromaticity discrimination ellipses",
        "schema": "jnd_ellipses",
        "n_ellipses": len(rows),
        "by_illuminant": by_illum,
        "illuminants": list(by_illum.keys()),
        "type": "JND chromaticity-discrimination ellipses under two illuminants",
        "is_jnd": True,
        "is_suprathreshold": False,
        "description": (
            "Chromaticity-discrimination ellipses measured by Alder, Chaing, Chong, Coates, Khalili & Rigg (1982) at the Society of Dyers and Colourists' uniform-chromaticity-scale study. Replicates the MacAdam 1942 methodology with a different observer pool and reports ellipses under both Illuminant D65 and Illuminant A — useful for testing whether a color space's small-difference geometry generalizes across illumination, not just across chromaticity. Each row reports the ellipse center (x_c, y_c, Y), the semi-major axis a, the semi-minor axis b (derived from the published a/b ratio), and the orientation theta."
        ),
        "notes": [
            "Two illuminants (D65 and A) — filter by `illuminant` for a single condition. Comparing D65 vs A ellipse fields tells you how well a chromatic adaptation transform preserves discrimination performance.",
            "Each ellipse summarizes n trials (the original `n` column in raw/table*.dat); 7–15 trials per center.",
            "Semi-axes were published as `a×10^4` and `a/b` ratio; canonical csv stores a (already divided by 10^4) and b (= a / ratio).",
        ],
        "sources": [
            {"paper": "Alder, C., Chaing, K. P., Chong, T. F., Coates, E., Khalili, A. A. & Rigg, B. (1982). Uniform Chromaticity Scales — New Experimental Data. Journal of the Society of Dyers and Colourists 98, 14–20."},
            {"snapshot_source": "coloria-dev/color-data on GitHub (community extraction of the published tables)."},
        ],
        "license": "Underlying data published in 1982; extraction by coloria-dev. License at the coloria-dev repo unspecified; included here under the academic-use convention. Cite Alder et al. (1982).",
    })
    print(f"  → {len(rows)} ellipses ({by_illum})")


# ---------------------------------------------------------------------------
# Fairchild-Johnson 1999 — constant-perceived-hue surfaces (306 chips × 15 hues × 30 observers)
# ---------------------------------------------------------------------------
def build_fairchild_johnson() -> None:
    print("Building Fairchild-Johnson 1999 constant-hue…")
    out_dir = OUT / "fairchild_johnson"
    raw_dir = out_dir / "raw"
    if not raw_dir.exists():
        print("  ! raw/ missing; skipping.")
        return
    try:
        d = yaml.safe_load((raw_dir / "fairchild-johnson.yaml").read_text())
    except Exception as e:
        print(f"  ! load failed: {e}")
        return
    rows = []
    for medium, scenes in d.items():
        if not isinstance(scenes, dict):
            continue
        for scene_name, samples in scenes.items():
            for i, xyz in enumerate(samples):
                X, Y, Z = float(xyz[0]), float(xyz[1]), float(xyz[2])
                lab = xyz_to_lab(np.array([X, Y, Z]), D65 * 100.0)
                rows.append({
                    "chip_id": f"fj_{medium}_{scene_name}_{i:02d}",
                    "hue_id": scene_name,
                    "variant": medium,
                    "L": round(float(lab[0]), 6),
                    "a": round(float(lab[1]), 6),
                    "b": round(float(lab[2]), 6),
                    "illuminant": "D65",
                })
    write_csv(out_dir / "canonical.csv", rows,
              ["chip_id", "hue_id", "variant", "L", "a", "b", "illuminant"])
    write_meta(out_dir / "meta.yaml", {
        "name": "Fairchild_Johnson_1999",
        "full_name": "Fairchild & Johnson (1999) constant-perceived-hue surfaces",
        "schema": "constant_hue",
        "n_chips": len(rows),
        "n_hue_angles": 15,
        "n_observers": 30,
        "n_trials_per_observer": 3,
        "illuminant": "D65 / 2°",
        "type": "constant-perceived-hue surfaces (306 colors × 15 hue angles, 30 observers × 3 trials)",
        "description": (
            "Constant-perceived-hue surfaces measured by Fairchild & Johnson (1999) on a calibrated CRT for the cross-medium matching task 'which printed color corresponds to which CRT color of the same perceived hue?'. 306 sampled colors across 15 equally spaced hue angles (24° step in CIELAB), 30 observers, 3 trials each. Used to evaluate CIELAB and CIECAM97s hue uniformity; the article is the standard reference for cross-medium (printed vs display) hue surfaces."
        ),
        "notes": [
            "Denser than both Hung-Berns (156 chips × 5 hue families) and Ebner-Fairchild (306 chips × 15 hue centers); but Ebner-Fairchild was on CRT only, while this dataset spans printed AND CRT media.",
            "The YAML's top-level key is the medium (e.g. `printed`); inner keys are scene names rather than hue numbers — refer to the paper for the angle-to-scene mapping.",
            "Per-chip observer counts and inter-observer variability are summarized in the paper but not preserved in the raw YAML.",
        ],
        "sources": [
            {"paper": "Fairchild, M. D. & Johnson, G. M. (1999). Color Appearance Reproduction: Visual Data and Predictive Modeling. Color Research & Application 24(2), 121–131."},
            {"snapshot_source": "coloria-dev/color-data (community extraction)."},
        ],
        "license": "Underlying data 1999; extraction by coloria-dev. License unspecified at coloria-dev; included under academic-use convention. Cite Fairchild & Johnson (1999).",
    })
    print(f"  → {len(rows)} chips")


# ---------------------------------------------------------------------------
# Xiao et al. 2011 — unique-hue loci (185 observers)
# ---------------------------------------------------------------------------
def build_xiao_unique_hues() -> None:
    print("Building Xiao et al. 2011 unique hues…")
    out_dir = OUT / "xiao_unique_hues"
    raw_dir = out_dir / "raw"
    if not raw_dir.exists():
        print("  ! raw/ missing; skipping.")
        return
    # The xiao bundle ships per-hue nested arrays per observer × session.
    # We store raw as-is and emit a compound_legacy index.
    index_rows = []
    for path in sorted(raw_dir.iterdir()):
        if not path.is_file():
            continue
        ext = path.suffix
        cat = (
            "unique-hue loci (per-observer arrays)" if path.stem.startswith("unique_") else
            "averages" if "averages" in path.stem else
            "neutral gray" if "neutral" in path.stem else
            "documentation" if path.suffix == ".md" else
            "original xlsx" if path.suffix == ".xlsx" else
            "support script" if path.suffix == ".py" else
            "other"
        )
        index_rows.append({
            "filename": path.name,
            "size_bytes": path.stat().st_size,
            "category": cat,
            "lines": "",
        })
    write_csv(out_dir / "canonical.csv", index_rows,
              ["filename", "size_bytes", "category", "lines"])
    write_meta(out_dir / "meta.yaml", {
        "name": "Xiao_2011_Unique_Hues",
        "full_name": "Xiao, Wuerger, Fu & Karatzas (2011) unique hue loci",
        "schema": "compound_legacy",
        "n_files": len(index_rows),
        "n_observers": 185,
        "hues": ["red", "green", "blue", "yellow", "neutral-gray"],
        "type": "unique hue loci (CIECAM02 evaluation, 185 color-normal observers)",
        "description": (
            "Unique-hue loci (red, green, blue, yellow) plus neutral gray measured by Xiao, Wuerger, Fu & Karatzas (2011) on a calibrated CRT with a large color-normal observer pool (n = 185). The data is the standard empirical anchor for evaluating where CIECAM02's hue angles place the four unique hues, and a frequent counterexample for the assumption that CIECAM02's NCS-based hue scale is correct. Useful as a hue-uniformity test that goes beyond constant-hue surfaces — it asks where the perceptually pure hues actually sit."
        ),
        "notes": [
            "★ Compound dataset — per-observer × per-session × per-hue nested arrays. `canonical.csv` is just an index; read the JSON files directly to use the data (see the original paper for the array layout).",
            "n = 185 is among the largest unique-hue samples published; analyses on smaller datasets (Hering's original 4, Kuehni's ~12) often produce noisy unique-hue estimates.",
            "The paper's main finding: CIECAM02's hue angles for unique red/green/blue/yellow are inconsistent with the NCS hues embedded in the model — useful for stress-testing any new color space's hue assignment.",
        ],
        "sources": [
            {"paper": "Xiao, K., Wuerger, S., Fu, C. & Karatzas, D. (2011). Unique Hue Data for Colour Appearance Models. Part I: Loci of Unique Hues and Hue Uniformity. Color Research & Application 36(5), 316–323."},
            {"snapshot_source": "coloria-dev/color-data (retrieved by email from Kaida Xiao, per the coloria-dev README)."},
        ],
        "license": "Author-provided data, redistributed via coloria-dev. License unspecified; included under academic-use convention. Cite Xiao et al. (2011).",
    })
    print(f"  → {len(index_rows)} raw files indexed")


# ---------------------------------------------------------------------------
# Fairchild-Chen 2010 — HDR lightness scaling
# ---------------------------------------------------------------------------
def build_fairchild_chen() -> None:
    print("Building Fairchild-Chen 2010 HDR lightness…")
    out_dir = OUT / "fairchild_chen"
    raw_dir = out_dir / "raw"
    if not raw_dir.exists():
        print("  ! raw/ missing; skipping.")
        return
    try:
        d = json.loads((raw_dir / "fairchild_chen.json").read_text())
    except Exception as e:
        print(f"  ! load failed: {e}")
        return
    rows = []
    for exp_id, exp in d.items():
        viewing = exp.get("viewing angle", "")
        Ls = exp.get("lightness", [])
        XYZs = exp.get("xyz", [])
        for i, (L, xyz) in enumerate(zip(Ls, XYZs)):
            rows.append({
                "sample_id": f"fc_{exp_id}_{i:02d}",
                "experiment_id": exp_id,
                "viewing_angle_deg": viewing,
                "evaluated_lightness": float(L),
                "X": float(xyz[0]),
                "Y": float(xyz[1]),
                "Z": float(xyz[2]),
            })
    write_csv(out_dir / "canonical.csv", rows,
              ["sample_id", "experiment_id", "viewing_angle_deg",
               "evaluated_lightness", "X", "Y", "Z"])
    write_meta(out_dir / "meta.yaml", {
        "name": "Fairchild_Chen_2010_HDR_Lightness",
        "full_name": "Fairchild & Chen (2010) brightness/lightness in HDR scenes",
        "schema": "lightness_scaling",
        "n_samples": len(rows),
        "experiments": list(d.keys()),
        "type": "lightness scaling for HDR scenes (luminance up to 3,000+ cd/m²)",
        "description": (
            "Magnitude estimation of perceived lightness in high-dynamic-range scenes by Fairchild & Chen (2010), spanning luminances up to ~3,000 cd/m² — well beyond the ~100 cd/m² range that CIELAB's L* function was calibrated for. Each sample is an XYZ tristimulus value alongside an observer-evaluated lightness score. Used to test whether a color space's lightness curve extrapolates correctly into HDR territory; CIELAB L* is the standard underperformer here."
        ),
        "notes": [
            "Not a color-difference dataset. Used only for lightness-curve validation in HDR.",
            "Two experiments (SL1, SL2 = Sequential Lightness experiment 1, 2) at different viewing angles.",
            "Critical for any color space claiming HDR support: a flat CIELAB-style L* curve underestimates perceived lightness above ~200 cd/m².",
        ],
        "sources": [
            {"paper": "Fairchild, M. D. & Chen, P.-H. (2010). Brightness, Lightness, and Specifying Color in High-Dynamic-Range Scenes and Images. Proc. SPIE 7867. DOI: 10.1117/12.872075"},
            {"snapshot_source": "coloria-dev/color-data (community extraction)."},
        ],
        "license": "Underlying data 2010; extraction by coloria-dev. Included under academic-use convention. Cite Fairchild & Chen (2010).",
    })
    print(f"  → {len(rows)} samples across {len(d)} experiments")


# ---------------------------------------------------------------------------
# xkcd color survey — curated 950 colors
# ---------------------------------------------------------------------------
def build_xkcd() -> None:
    print("Building xkcd colors…")
    out_dir = OUT / "xkcd_colors"
    out_dir.mkdir(parents=True, exist_ok=True)
    raw = out_dir / "raw" / "xkcd_rgb.txt"
    if not raw.exists():
        print("  ! raw/xkcd_rgb.txt missing; skipping. Download from https://xkcd.com/color/rgb.txt")
        return
    rows = []
    with open(raw) as f:
        for line in f:
            line = line.rstrip()
            if not line or line.startswith("#"):
                continue
            parts = line.split("\t")
            if len(parts) < 2:
                continue
            name, hex_code = parts[0].strip(), parts[1].strip()
            if not hex_code.startswith("#") or len(hex_code) != 7:
                continue
            R, G, B = int(hex_code[1:3], 16), int(hex_code[3:5], 16), int(hex_code[5:7], 16)
            L, a, b_lab = hex_to_lab(hex_code)
            rows.append({
                "name": name,
                "hex": hex_code,
                "R": R, "G": G, "B": B,
                "L": round(L, 4),
                "a": round(a, 4),
                "b": round(b_lab, 4),
            })
    write_csv(out_dir / "canonical.csv", rows,
              ["name", "hex", "R", "G", "B", "L", "a", "b"])
    write_meta(out_dir / "meta.yaml", {
        "name": "xkcd_colors",
        "full_name": "xkcd Color Survey — curated 950 named colors (Munroe 2010)",
        "schema": "color_names",
        "n_colors": len(rows),
        "color_space_native": "sRGB hex; canonical CIELAB computed via IEC 61966-2-1 sRGB→XYZ(D65)→CIELAB(D65)",
        "type": "color naming — most-popular color name → RGB swatch",
        "description": (
            "Curated 950 most-popular color names from the xkcd Color Survey conducted by Randall Munroe in 2010. Over 200,000 participants gave free-form names to randomly displayed RGB swatches; the published list keeps the most-agreed-upon name for each color region. The full raw survey contains ~5 million responses (not redistributed here — see Munroe's original archive). Useful as a real-world naming corpus and as an out-of-distribution sanity check for color appearance models."
        ),
        "notes": [
            "Curated subset, not the full 5M-response survey. For the full raw dump see https://xkcd.com/color/colorsurvey.tar.gz (hundreds of MB, not included here).",
            "English-language only; names reflect the cultural/linguistic vocabulary of the participant pool (mostly US/English-speaking internet users in 2010).",
            "RGB values are sRGB display-space; the L*a*b* columns are added for convenience and may not match the participants' perceived color (their displays were uncalibrated).",
        ],
        "sources": [
            {"paper": "Munroe, R. (2010). Color Survey Results. xkcd. https://blog.xkcd.com/2010/05/03/color-survey-results/"},
            {"snapshot_source": "https://xkcd.com/color/rgb.txt (CC0 public domain dedication, see file header)"},
        ],
        "license": "CC0 (xkcd colors are in the public domain via Munroe's explicit dedication). This canonical export remains CC BY 4.0 for the schema and metadata; the underlying data is unrestricted.",
    })
    print(f"  → {len(rows)} named colors")


# ---------------------------------------------------------------------------
def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    build_combvd()
    build_macadam1942()
    build_macadam1974()
    build_macadam1935()
    build_breneman1987()
    build_he2022()
    build_helmlabfb()
    build_hung_berns()
    build_ebner_fairchild()
    build_pointer()
    build_munsell()
    build_xkcd()
    build_corresponding_colours()
    build_lutchi()
    build_alder1982()
    build_fairchild_johnson()
    build_xiao_unique_hues()
    build_fairchild_chen()
    build_wcs()
    build_luo_rigg_ellipses()
    build_alman1989()
    build_hong2025()
    build_cherepkova()
    build_asano_observers()
    print("\nDone.")


# ---------------------------------------------------------------------------
# Cherepkova 2025 — Individual contrast preferences (NTNU)
# ---------------------------------------------------------------------------
def build_cherepkova() -> None:
    print("Building Cherepkova 2025 contrast preferences…")
    out_dir = OUT / "cherepkova_contrast"
    raw_dir = out_dir / "raw"
    if not raw_dir.exists():
        print("  ! raw/ missing; skipping.")
        return
    try:
        import openpyxl
        wb = openpyxl.load_workbook(raw_dir / "22_observers_preferred_contrast.xlsx", data_only=True)
        ws = wb.active
        all_rows = list(ws.iter_rows(values_only=True))
    except Exception as e:
        print(f"  ! load failed: {e}")
        return

    header = all_rows[0]
    # Long-format canonical: image × observer → preferred_contrast
    rows = []
    n_images = 0
    n_observers_seen = set()
    for r in all_rows[1:]:
        if not r[0]:
            continue
        image_id = str(r[0])
        n_images += 1
        for col_idx, val in enumerate(r[1:], start=1):
            if val is None or col_idx >= len(header):
                continue
            obs_id = str(header[col_idx]) if header[col_idx] else f"obs_{col_idx}"
            n_observers_seen.add(obs_id)
            try:
                fval = float(val)
            except (TypeError, ValueError):
                continue
            rows.append({
                "image_id": image_id,
                "observer_id": f"obs_{obs_id}",
                "preferred_contrast_delta": round(fval, 6),
            })
    write_csv(out_dir / "canonical.csv", rows,
              ["image_id", "observer_id", "preferred_contrast_delta"])
    write_meta(out_dir / "meta.yaml", {
        "name": "Cherepkova_2025_Contrast_Preferences",
        "full_name": "Cherepkova et al. (2025) Individual Contrast Preferences Database (NTNU)",
        "schema": "contrast_preference",
        "n_responses": len(rows),
        "n_images": n_images,
        "n_observers": len(n_observers_seen),
        "type": "individual contrast preferences for natural images (accessibility-relevant)",
        "is_jnd": False,
        "is_suprathreshold": False,
        "description": (
            "Per-observer preferred contrast adjustments for 500 natural images, gathered by Cherepkova and colleagues at the NTNU Colour and Visual Computing Lab (2025). 22 observers each rated their preferred contrast modification for every image; values are signed deltas (negative = less contrast preferred, positive = more contrast preferred). Useful as a perceptual ground-truth for image-adaptive contrast algorithms (APCA / WCAG-adjacent work), and as a sanity test for any color space that claims a perceptually meaningful lightness curve — preferred contrast should correlate with image L*-distribution properties in a well-calibrated space."
        ),
        "notes": [
            "★ This is a CONTRAST-PREFERENCE dataset, not a color-difference dataset. Adjacent to image quality assessment and accessibility (APCA/WCAG) research, not classical color-space evaluation.",
            "22 observers, 500 images = 11,000 max responses (some cells empty in source).",
            "Reference images (JPEGs at zero-contrast adjustment) are bundled in `raw/full_bundle.zip` if you need to compute image-level features. The canonical.csv only contains observer responses.",
            "Stratifies well by image content (faces, landscapes, indoor) — see the original NTNU paper for image categorization.",
        ],
        "sources": [
            {"paper": "Cherepkova, O. et al. (2025). Individual Contrast Preferences Database. NTNU Colour and Visual Computing Lab. Zenodo DOI 10.5281/zenodo.17430959"},
        ],
        "license": "CC BY 4.0 (declared on Zenodo). Cite Cherepkova et al. (2025).",
    })
    print(f"  → {len(rows)} responses ({n_images} images × {len(n_observers_seen)} observers)")


# ---------------------------------------------------------------------------
# Asano 151 observers — color matching function database
# ---------------------------------------------------------------------------
def build_asano_observers() -> None:
    print("Building Asano 151 observer CMF database…")
    out_dir = OUT / "asano_observers"
    raw_dir = out_dir / "raw"
    if not raw_dir.exists():
        print("  ! raw/ missing; skipping.")
        return
    try:
        import xlrd
        wb = xlrd.open_workbook(raw_dir / "Data_151Obs.xls")
    except Exception as e:
        print(f"  ! xls load failed: {e}")
        return
    sheets = wb.sheet_names()
    index_rows = []
    for path in sorted(raw_dir.iterdir()):
        if path.is_file():
            index_rows.append({
                "filename": path.name,
                "size_bytes": path.stat().st_size,
                "category": (
                    "151 individual observers (CMFs + cone fundamentals, 2° + 10°)" if "151Obs" in path.name
                    else "10 categorical observers (age × field-size groupings)" if "10CatObs" in path.name
                    else "1000 Monte Carlo observers (simulated)" if "1000Monte" in path.name
                    else "source URLs + checksums" if path.suffix == ".txt"
                    else "other"
                ),
                "lines": "",
            })
    write_csv(out_dir / "canonical.csv", index_rows,
              ["filename", "size_bytes", "category", "lines"])
    write_meta(out_dir / "meta.yaml", {
        "name": "Asano_2015_Observer_CMFs",
        "full_name": "Asano (2015) Observer Function Database — 151 individual + 1000 Monte Carlo observer CMFs",
        "schema": "compound_legacy",
        "n_files": len(index_rows),
        "n_individual_observers": 151,
        "n_categorical_observers": 10,
        "n_monte_carlo_observers": 1000,
        "fields_of_view": ["2°", "10°"],
        "type": "observer color-matching functions (CMFs) and cone fundamentals — 151 color-normal individuals",
        "description": (
            "Yuta Asano's (2015) database of color-matching functions and cone fundamentals from 151 individual color-normal observers measured at the RIT Munsell Color Science Laboratory, plus 10 categorical observer averages stratified by age/field-of-view, plus 1000 Monte-Carlo-simulated observers spanning the natural variation envelope. Each observer has full CMFs (x̄, ȳ, z̄) and LMS cone fundamentals at both 2° and 10° fields, sampled at 1 nm. Useful for two questions: (1) how much does inter-observer variation shift the position of any predicted ΔE? (2) what observer subgroups are over- or under-represented in CIE 1931 / CIE 1964 standard observers? Important for accessibility work — color-vision-deficient observers are not in this set, but the natural variation among normal observers is itself ±5–10 nm in cone peak λ, which affects ΔE predictions at low chroma."
        ),
        "notes": [
            "★ This is OBSERVER CHARACTERIZATION data, not color-difference data. It tells you 'observer N matches color X with these primaries', not 'observer N rated this difference at level Y'.",
            "Each Excel file has 5 sheets: xyz-02deg, xyz-10deg, lms-02deg, lms-10deg, parameters. Read directly from raw/ — `canonical.csv` is just a file index.",
            "Use case for color-space work: compute an 'observer-uncertainty envelope' around any predicted ΔE by running it through all 1000 Monte Carlo observers and reporting the IQR. Essential for showing that a champion's STRESS advantage is not an artifact of CIE 1931 standard observer choice.",
            "151 individuals are a real demographic sample; 1000 Monte Carlo are model-generated to span the natural envelope; 10 categorical are population means.",
            "Original distribution: rit-mcsl.org/StudentResearch/YutaAsano/ (mirrored to Zenodo DOI 10.5281/zenodo.3252742).",
        ],
        "sources": [
            {"paper": "Asano, Y. (2015). Individual Colorimetric Observers for Personalized Color Imaging. PhD dissertation, Rochester Institute of Technology."},
            {"paper": "Asano, Y., Fairchild, M. D. & Blondé, L. (2016). Individual Colorimetric Observer Model. PLoS ONE 11(2): e0145671."},
            {"snapshot_source": "Zenodo DOI 10.5281/zenodo.3252742 (mirrored from rit-mcsl.org)"},
        ],
        "license": "License unspecified on Zenodo (original at RIT-MCSL was free-academic-use). Included under academic-use convention. Cite Asano et al. (2016).",
    })
    print(f"  → {len(index_rows)} raw files indexed")


# ---------------------------------------------------------------------------
# Hong et al. 2025 — modern isoluminant ellipsoids (Brainard lab UPenn)
# ---------------------------------------------------------------------------
def build_hong2025() -> None:
    print("Building Hong 2025 ellipsoid pointer…")
    out_dir = OUT / "hong_2025_ellipsoids"
    raw_dir = out_dir / "raw"
    if not raw_dir.exists():
        print("  ! raw/ missing; skipping.")
        return
    # We only ship the README.pdf + a DATA_LOCATION pointer because the OSF data
    # is multi-folder and ~hundreds of MB. canonical.csv is a one-row pointer.
    index_rows = []
    for path in sorted(raw_dir.iterdir()):
        if path.is_file():
            index_rows.append({
                "filename": path.name,
                "size_bytes": path.stat().st_size,
                "category": "OSF data pointer" if path.name == "DATA_LOCATION.md"
                            else "official dataset README" if path.suffix == ".pdf"
                            else "other",
                "lines": "",
            })
    write_csv(out_dir / "canonical.csv", index_rows,
              ["filename", "size_bytes", "category", "lines"])
    write_meta(out_dir / "meta.yaml", {
        "name": "Hong_2025_Ellipsoids",
        "full_name": "Hong et al. (2025) modern isoluminant color-discrimination ellipsoids (Brainard Lab, UPenn)",
        "schema": "compound_legacy",
        "n_files": len(index_rows),
        "n_observers": 8,
        "n_trials_approx": 12000,
        "illuminant": "calibrated display (isoluminant plane)",
        "type": "modern replacement-class for MacAdam 1942 — Wishart Process ellipsoid fits in isoluminant plane",
        "is_jnd": True,
        "is_suprathreshold": False,
        "description": (
            "The modern descendant of MacAdam 1942: dense color-discrimination ellipsoids measured by Hong, Yoon, Yoo & Brainard (2025) at UPenn using a 3AFC oddity task with adaptive psychophysics (AEPsych) on a calibrated display. ~6,000 adaptive + ~6,000 validation trials per observer × 8 color-normal observers, fitted with a Wishart Process Psychophysical Model that yields a smooth ellipsoid field across the isoluminant plane (rather than 25 isolated ellipses). Published in eLife 2025; code on GitHub, raw + organized data on OSF. The first JND-class dataset that fixes MacAdam 1942's two biggest problems: (1) a single observer and (2) sparse sampling. Use this dataset to test whether your color space's small-difference geometry generalizes beyond the historical 25 centers."
        ),
        "notes": [
            "★ The actual data lives on OSF (https://osf.io/k27js/) and is too large for this repo. raw/ contains only the dataset README.pdf and a pointer file with download instructions.",
            "Wishart Process fits give a smooth ellipsoid field, not discrete ellipses — use the OSF 'Organized data' folder for the model predictions, 'Raw experimental data' for the trial-level data.",
            "Adaptive psychophysics (AEPsych framework) means trial placements are non-uniform; standard JND comparisons against MacAdam 1942 require care.",
            "8 color-normal observers — much smaller than WCS's 24/lang but much larger than MacAdam's 1. Each observer has individual ellipsoids + the paper reports a group-level fit.",
        ],
        "sources": [
            {"paper": "Hong, F. F., Yoon, J., Yoo, Y. & Brainard, D. H. (2025). Comprehensive characterization of color discrimination thresholds with a Wishart Process Psychophysical Model. eLife reviewed preprint 108943."},
            {"snapshot_source": "OSF project https://osf.io/k27js/ (CC-BY); code https://github.com/fh862/ellipsoids_eLife2025"},
        ],
        "license": "CC BY (per OSF project metadata). Cite Hong et al. (2025) when using the data.",
    })
    print(f"  → pointer dataset ({len(index_rows)} files in raw/, full data on OSF)")


# ---------------------------------------------------------------------------
# Alman, Berns, Snyder & Larsen 1989 — RIT color tolerance ellipsoids
# ---------------------------------------------------------------------------
def build_alman1989() -> None:
    print("Building Alman 1989 tolerance ellipsoids…")
    out_dir = OUT / "alman1989"
    raw_dir = out_dir / "raw"
    if not raw_dir.exists():
        print("  ! raw/ missing; skipping.")
        return
    try:
        d = yaml.safe_load((raw_dir / "alman1989.yaml").read_text())
    except Exception as e:
        print(f"  ! load failed: {e}")
        return
    rows = []
    for center_name, entries in d.items():
        if not isinstance(entries, list):
            continue
        for i, e in enumerate(entries):
            if not isinstance(e, list) or len(e) < 12:
                continue
            try:
                L_c, a_c, b_c = float(e[0]), float(e[1]), float(e[2])
                dL, da, db = float(e[3]), float(e[4]), float(e[5])
                eigenvalue = float(e[6])
                T50, LFL, UFL, S, P_chisq = (float(e[7]), float(e[8]),
                                              float(e[9]), float(e[10]), float(e[11]))
            except (TypeError, ValueError):
                continue
            rows.append({
                "ellipsoid_id": f"alman1989_{center_name.replace(' ','_')}_{i+1:02d}",
                "color_center": center_name,
                "L_c": round(L_c, 4), "a_c": round(a_c, 4), "b_c": round(b_c, 4),
                "dL_unit": round(dL, 6), "da_unit": round(da, 6), "db_unit": round(db, 6),
                "eigenvalue": round(eigenvalue, 6),
                "T50": round(T50, 4),
                "LFL_95": round(LFL, 4), "UFL_95": round(UFL, 4),
                "S_dev": round(S, 4), "P_chisq": round(P_chisq, 4),
                "illuminant": "D65",
            })
    write_csv(out_dir / "canonical.csv", rows,
              ["ellipsoid_id", "color_center",
               "L_c", "a_c", "b_c",
               "dL_unit", "da_unit", "db_unit", "eigenvalue",
               "T50", "LFL_95", "UFL_95", "S_dev", "P_chisq",
               "illuminant"])
    by_center: dict[str, int] = {}
    for r in rows:
        by_center[r["color_center"]] = by_center.get(r["color_center"], 0) + 1
    write_meta(out_dir / "meta.yaml", {
        "name": "Alman_1989_Tolerance_Ellipsoids",
        "full_name": "Alman, Berns, Snyder & Larsen (1989) RIT color tolerance ellipsoids",
        "schema": "tolerance_ellipsoids",
        "n_ellipsoids": len(rows),
        "by_center": by_center,
        "color_centers": list(by_center.keys()),
        "illuminant": "D65 / 2°",
        "type": "3D color-tolerance ellipsoids in CIELAB (probit-fitted, with fiducial limits)",
        "is_jnd": False,
        "is_suprathreshold": True,
        "description": (
            "Per-direction color-tolerance ellipsoids in CIELAB space, fitted via probit analysis from the RIT/DuPont visual color difference experiment by Alman, Berns, Snyder & Larsen (1989). Unlike MacAdam-style 2D chromaticity ellipses, these are 3D tolerance ellipsoids — for each color center, multiple probe directions report a T50 tolerance (50% acceptability point), 95% fiducial limits, standard deviation, and the chi-square fit probability. Used historically to develop the CIE94 and CIEDE2000 weighted formulas. Different geometry than Luo-Rigg / MacAdam / Alder ellipses: those measure JND of light, this measures acceptability tolerance for printed-textile color matches."
        ),
        "notes": [
            "★ Tolerance, not JND. Asks 'what color difference is still acceptable to industrial QA?' rather than 'what color difference can be detected?'. T50 ≈ 1 in CIELAB roughly corresponds to ΔE ≈ 1 acceptability.",
            "Each row is a single probe direction at a color center, not a full 3D ellipsoid. Multiple rows per center (typically 9) span the principal axes around the center.",
            "Berns version (raw/berns.yaml) reports the same data with extra metadata (lighting condition I/II, color appearance name) — read both if you need full provenance.",
            "Critical for evaluating color spaces against industrial color-tolerance standards (textile, paint, automotive) where 'acceptably close' matters more than 'perceptually identical'.",
        ],
        "sources": [
            {"paper": "Alman, D. H., Berns, R. S., Snyder, G. D. & Larsen, W. A. (1989). Performance testing of color-difference metrics using a color tolerance dataset. Color Research & Application 14(3), 139–151."},
            {"paper": "Berns, R. S., Alman, D. H., Reniff, L., Snyder, G. D. & Balonon-Rosen, M. R. (1991). Visual determination of suprathreshold color-difference tolerances using probit analysis. Color Research & Application 16, 297–316."},
            {"snapshot_source": "coloria-dev/color-data (extracted from Alman 1989 Table II and Berns 1991 Table 4)"},
        ],
        "license": "Underlying data 1989/1991; extraction by coloria-dev. Included under academic-use convention. Cite Alman et al. (1989) and Berns et al. (1991).",
    })
    print(f"  → {len(rows)} ellipsoids across {len(by_center)} color centers")


# ---------------------------------------------------------------------------
# Luo & Rigg 1986 — surface-color chromaticity discrimination ellipses
# ---------------------------------------------------------------------------
def build_luo_rigg_ellipses() -> None:
    print("Building Luo-Rigg 1986 ellipses…")
    out_dir = OUT / "luo_rigg_ellipses"
    raw_dir = out_dir / "raw"
    if not raw_dir.exists():
        print("  ! raw/ missing; skipping.")
        return
    try:
        d = yaml.safe_load((raw_dir / "luo-rigg.yaml").read_text())
    except Exception as e:
        print(f"  ! load failed: {e}")
        return
    rows = []
    by_set: dict[str, int] = {}
    for set_name, ellipses in d.items():
        if not isinstance(ellipses, dict):
            continue
        for center_label, vals in ellipses.items():
            try:
                x, y, Y, a_e4, ratio, theta, set_factor = (float(v) for v in vals)
            except (TypeError, ValueError):
                continue
            a = a_e4 / 10000.0
            b = a / ratio
            rows.append({
                "center_id": f"luorigg_{set_name}_{center_label}",
                "set_name": set_name,
                "center_label": center_label,
                "x_c": round(x, 6), "y_c": round(y, 6),
                "a": round(a, 8), "b": round(b, 8),
                "theta_deg": round(theta, 4),
                "Y": round(Y, 4),
                "set_factor": round(set_factor, 4),
                "illuminant": "C",
            })
            by_set[set_name] = by_set.get(set_name, 0) + 1
    write_csv(out_dir / "canonical.csv", rows,
              ["center_id", "set_name", "center_label",
               "x_c", "y_c", "a", "b", "theta_deg", "Y",
               "set_factor", "illuminant"])
    write_meta(out_dir / "meta.yaml", {
        "name": "Luo_Rigg_1986_Ellipses",
        "full_name": "Luo & Rigg (1986) chromaticity discrimination ellipses for surface colours",
        "schema": "jnd_ellipses",
        "n_ellipses": len(rows),
        "by_set": by_set,
        "sets": list(by_set.keys()),
        "illuminant": "CIE Illuminant C",
        "type": "JND chromaticity-discrimination ellipses from 10 different source studies, harmonized",
        "is_jnd": True,
        "is_suprathreshold": False,
        "description": (
            "A compilation of 132+ chromaticity-discrimination ellipses for surface colours, gathered by M. R. Luo and B. Rigg (1986) from ten independent source studies (VVVR, BFD, MMB, CISCC, CIE, STROCKA, WITT, DF, MCD, K) and harmonized via per-set scaling factors. Larger and more diverse than the MacAdam 1942 set (which used a single observer on isolated lights) — Luo-Rigg covers real surface-color conditions and multiple observer pools. The paper's headline finding: contrary to MacAdam 1942, the smallest discrimination ellipses lie in the blue-grey region for surface colors. The standard JND dataset for any color space that claims to model real-world textile/paint/dye color tolerances rather than just isolated stimuli."
        ),
        "notes": [
            "10 source sets with very different sample sizes — filter by `set_name` for a single source. Don't pool naively; the `set_factor` column carries the per-set scaling Luo & Rigg derived to bring sets onto a common scale.",
            "★ Surface-color JND — different from MacAdam 1942 (isolated lights). The blue-grey minimum here vs MacAdam's blue maximum is a long-standing puzzle in the literature.",
            "Ellipse semi-axes (a, b) stored in chromaticity units (a×10⁻⁴ scale already applied). Use a/b ratio when comparing aspect ratios to MacAdam.",
            "set_factor R̄ is the relative size factor per source set; multiply a and b by R̄ to recover the raw per-source size, or divide by R̄ to project onto the common scale.",
        ],
        "sources": [
            {"paper": "Luo, M. R. & Rigg, B. (1986). Chromaticity Discrimination Ellipses for Surface Colours. Color Research & Application 11(1), 25–42."},
            {"snapshot_source": "coloria-dev/color-data (community extraction of Table 3)"},
        ],
        "license": "Underlying data 1986; extraction by coloria-dev (license unspecified). Included under academic-use convention. Cite Luo & Rigg (1986).",
    })
    print(f"  → {len(rows)} ellipses across {len(by_set)} source sets")


# ---------------------------------------------------------------------------
# World Color Survey (Kay, Berlin, Maffi, Merrifield, Cook)
# ---------------------------------------------------------------------------
def build_wcs() -> None:
    print("Building World Color Survey…")
    out_dir = OUT / "wcs"
    raw_dir = out_dir / "raw"
    if not raw_dir.exists():
        print("  ! raw/ missing; skipping.")
        return
    # The full WCS is too large to flatten into one canonical row-per-judgement
    # (term.txt is ~863k rows). We build a multi-file canonical:
    #   - chips.csv (330 Munsell chips with Lab)
    #   - languages.csv (110 languages)
    #   - canonical.csv = a summary index of the bundle (compound_legacy)
    # The raw files are preserved unchanged for users who want the full data.

    # Parse cnum-vhcm-lab-new.txt → chips.csv
    chips = []
    for line in (raw_dir / "cnum-vhcm-lab-new.txt").read_text().splitlines():
        if line.startswith("#") or not line.strip():
            continue
        parts = line.split("\t")
        if len(parts) < 9:
            continue
        try:
            chips.append({
                "cnum": int(parts[0]),
                "V": parts[1],
                "H": int(parts[2]),
                "C": int(parts[3]),
                "MunH": parts[4],
                "MunV": parts[5],
                "L": float(parts[6]),
                "a": float(parts[7]),
                "b": float(parts[8]),
            })
        except (ValueError, IndexError):
            continue
    write_csv(out_dir / "chips.csv", chips,
              ["cnum", "V", "H", "C", "MunH", "MunV", "L", "a", "b"])

    # Parse lang.txt → languages.csv
    langs = []
    for line in (raw_dir / "lang.txt").read_text().splitlines():
        if not line.strip():
            continue
        parts = line.split("\t")
        if len(parts) < 7:
            continue
        langs.append({
            "lnum": int(parts[0]),
            "name": parts[1],
            "country": parts[2],
            "fieldworker": parts[3],
            "analyst": parts[4],
            "transcription": parts[5],
            "filename": parts[6],
        })
    write_csv(out_dir / "languages.csv", langs,
              ["lnum", "name", "country", "fieldworker", "analyst", "transcription", "filename"])

    # canonical.csv = index of every raw file (compound)
    index_rows = []
    file_descriptions = {
        "chip.txt": "330 WCS Munsell chips (cnum, V, H, MunH)",
        "cnum-vhcm-lab-new.txt": "Chip# → V/H/C + Munsell hue/value + CIELAB L*a*b*",
        "lang.txt": "110 languages with country + fieldworker metadata",
        "dict.txt": "Color term dictionary: lang# × term# → transliteration + WCS code",
        "foci.txt": "Focal-color selections (aggregated): lang# × speaker# × term# → chip# or range",
        "foci-exp.txt": "Focal-color selections (per-experiment / individual responses)",
        "term.txt": "Color naming responses: lang# × speaker# × chip# → WCS code (THE main dataset, ~863k rows)",
    }
    for path in sorted(raw_dir.iterdir()):
        if path.is_file():
            index_rows.append({
                "filename": path.name,
                "size_bytes": path.stat().st_size,
                "category": file_descriptions.get(path.name, "other"),
                "lines": sum(1 for _ in path.open()),
            })
    write_csv(out_dir / "canonical.csv", index_rows,
              ["filename", "size_bytes", "category", "lines"])

    write_meta(out_dir / "meta.yaml", {
        "name": "WCS",
        "full_name": "World Color Survey (Kay, Berlin, Maffi, Merrifield & Cook)",
        "schema": "compound_legacy",
        "n_files": len(index_rows),
        "n_languages": len(langs),
        "n_chips": len(chips),
        "n_naming_responses": sum(1 for _ in (raw_dir / "term.txt").open()),
        "n_focal_responses": sum(1 for _ in (raw_dir / "foci-exp.txt").open()),
        "color_space_native": "Munsell Renotation chips; CIELAB under Illuminant C",
        "type": "cross-cultural color naming (110 languages × ~24 speakers × 330 chips)",
        "is_jnd": False,
        "is_suprathreshold": False,
        "description": (
            "The World Color Survey, conducted by Paul Kay, Brent Berlin, Luisa Maffi, William Merrifield and Richard Cook between 1976 and 1981. 110 unwritten languages, ~24 speakers per language, each shown a standard 330-Munsell-chip grid and asked to (a) name every chip in their own language and (b) pick the best example chip for their basic color terms. Originally collected to test the Berlin-Kay hypothesis of universal color-term evolution; now the de facto reference dataset for cross-cultural color cognition and a powerful stress test for any color space that claims perceptual uniformity (a uniform space's focal-color clusters across languages should land in compact regions)."
        ),
        "notes": [
            "★ Compound dataset — chips.csv + languages.csv are flat tables; `canonical.csv` is an index of every raw file. The actual naming data lives in raw/term.txt (~863k rows) and raw/foci-exp.txt (~18k rows). Read those directly.",
            "term.txt format: <lnum> <speaker> <cnum> <WCS_code>. Look up <WCS_code> in raw/dict.txt to get the language-specific transliteration.",
            "foci.txt and foci-exp.txt: focal-color picks per speaker per basic-color-term. Chip column may be a single cnum or a range (e.g. 'D9..12') — strip and explode for cleanest analysis.",
            "The 330-chip grid is Berlin & Kay's 'Mercator projection of color space' — Munsell hue 1..40 × value 1..8 plus 10 neutrals. Coordinates in chips.csv are under Illuminant C.",
            "Test: if your color space is uniform, focal-color centroids per term (e.g. all 'red' picks across all languages) should form tight clusters. Cross-cultural variation should sit along Munsell hue, not jump around in your space's chromaticity plane.",
        ],
        "sources": [
            {"paper": "Berlin, B. & Kay, P. (1969). Basic Color Terms: Their Universality and Evolution. University of California Press."},
            {"paper": "Kay, P., Berlin, B., Maffi, L., Merrifield, W. R. & Cook, R. (2009). The World Color Survey. CSLI Publications."},
            {"snapshot_source": "linguistics.berkeley.edu/wcs/ (Berkeley host, March 2011 bundle WCS-Data-20110316.zip)"},
        ],
        "license": "WCS data has been publicly distributed by Berkeley since the early 2000s for free academic use. Cite Kay et al. (2009) and the original Berlin & Kay (1969) when using.",
    })
    print(f"  → {len(chips)} chips, {len(langs)} languages, {sum(1 for _ in (raw_dir / 'term.txt').open()):,} naming responses indexed")


if __name__ == "__main__":
    main()
