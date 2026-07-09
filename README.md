# color-perception-datasets

A clean, schema-validated pool of psychophysical color datasets used in color-space and color-difference research. **46 datasets**, one consistent layout, **every dataset digit- or byte-verified against its primary source** (a 2026-07 audit repaired ~30 OCR/transcription errors across 7 sets — see each `meta.yaml` provenance block).

Maintained by **[Görkem Yıldız](https://gorkemyildiz.com)** as part of the [helmlab](https://helmlab.space) research toolkit.

**Browse with details and downloads:** <https://grkmyldz148.github.io/color-perception-datasets/>

---

## What's in the pool

| Dataset | Type | Rows | Native illuminant | Notes |
|---|---|---|---|---|
| [COMBVD](datasets/combvd/) | Pair color difference (suprathreshold) | 3,813 | mixed (D65, C, other) | 4 sub-datasets: BFD-P, LEEDS, RIT-DuPont, WITT |
| [MacAdam 1942](datasets/macadam1942/) | **JND** discrimination ellipses | 25 | Illuminant C | The classic MacAdam ellipses (Observer PGN). Real JND. |
| [MacAdam 1974](datasets/macadam1974/) | Pair color difference (suprathreshold) | 128 | D65 / 2° | OSA UCS — **NOT** the 1942 JND ellipses |
| [MacAdam 1935](datasets/macadam1935_optimal/) | Theoretical gamut boundary | 657 | A, C, D65 | Optimal color stimuli (max-reflectance bound) |
| [Breneman 1987](datasets/breneman1987/) | Corresponding colors (chromatic adaptation) | 160 | varies | 12 experiments × ~13 pairs each |
| [Corresponding Colours](datasets/corresponding_colours/) | Corresponding colors compilation | 746 | varies | Luo & Rhodes 1999 bundle: Breneman + CSAJ + Helson + Kuo + Lam + LUTCHI + McCann + RIT + Stevens |
| [LUTCHI](datasets/lutchi/) | Color appearance (magnitude estimation) | 100 files | varies | Luo & Rhodes 1997, 43k estimations across 100 raw files — compound legacy schema |
| [He 2022](datasets/he2022/) | Pair Δ values (suprathreshold) | 82 | D65 / 10° | 3D-printed spheres, Δ-only schema |
| [HelmlabFB](datasets/helmlabfb/) | Pair color difference (per-judgement) | 3,477 | sRGB / D65 | Collected by [helmlab.space](https://helmlab.space); 71 observers pseudonymized; 4 designed zones |
| [Hung-Berns](datasets/hung_berns/) | Constant-hue chips | 156 | D65 / 2° | Hue-uniformity test |
| [Ebner-Fairchild](datasets/ebner_fairchild/) | Constant-hue surfaces | 306 | D65 / 2° | 15 hue centers (0°…336°, 24° step) |
| [Pointer 1980](datasets/pointer/) | Real-surface gamut boundary | 576 | Illuminant C | Boundary points (L × hue grid) |
| [Munsell](datasets/munsell/) | Renotation chips | 2,734 | Illuminant C | Snapshot from `colour` library |
| [xkcd colors](datasets/xkcd_colors/) | Color naming (English) | 949 | sRGB / D65 | Curated 949 most-popular names (Munroe 2010, CC0) |
| [WCS](datasets/wcs/) | Cross-cultural naming | 330 chips × 110 langs × 863k responses | Munsell / Illum C | World Color Survey (Kay-Berlin-Maffi 1976–1981) |
| [Luo-Rigg 1986](datasets/luo_rigg_ellipses/) | **JND** chromaticity ellipses | 132 (10 source sets) | Illuminant C | Surface-color JND, larger than MacAdam 1942 |
| [Alman 1989](datasets/alman1989/) | 3D tolerance ellipsoids | 45 (9 centers) | D65 / 2° | RIT-DuPont probit-fitted tolerance, industrial QA |
| [Hong 2025](datasets/hong_2025_ellipsoids/) | **JND** isoluminant ellipsoids (modern) | OSF pointer | calibrated display | 8 observers, Wishart Process, eLife 2025 |
| [Cherepkova 2025](datasets/cherepkova_contrast/) | Contrast preference (accessibility) | 10,978 (499 images × 22 observers) | sRGB | NTNU, CC-BY-4.0 — APCA/WCAG-adjacent |
| [Asano observers](datasets/asano_observers/) | Observer CMF database | 151 individuals + 1000 MC + 10 categorical | spectral | Inter-observer uncertainty bands on any predicted ΔE |
| [Brown-MacAdam 1949](datasets/brown_macadam_1949_ellipsoids/) | **JND** 3D ellipsoids | 114 (38 centers × 3 obs) | dark surround | WRJB + DLM (3D) + PGN (2D MacAdam). First 3-D color-matching variance with luminance. From W-S 1982 Table I(5.4.2). |
| [Brown 1957](datasets/brown_1957_12obs_ellipsoids/) | **JND** 3D ellipsoids (12-obs avg) | 46 (22 centers × straight + weighted) | white | First large-N (n=12) average ellipsoids. From W-S 1982 Table II(5.4.2). |
| [Wyszecki-Fielder 1971](datasets/wyszecki_fielder_1971_ellipsoids/) | **JND** 3D ellipsoids | 84 (28 centers × 3 obs) | white surround | GF, AR, GW observers; constant Y₀=12 cd/m². From W-S 1982 Table I(5.4.3). |
| [Sanders-Wyszecki 1964](datasets/sanders_wyszecki_1964_HK/) | Heterochromatic brightness (H-K) | 95 (wavelength series × directions) | white | 20 observers, B/L ratio per chromaticity. From W-S 1982 Table 1(5.8.1). |
| [Wyszecki 1967 OSA tiles](datasets/wyszecki_1967_osa_tiles/) | Tile lightness vs brightness | 43 tiles | C / artificial daylight | 76 observers, Y_gray/Y_color ratio (H-K). From W-S 1982 Table 2(5.8.1). |
| [Wright 1941](datasets/wright_1941_jnd_chromaticity/) | **JND** chromaticity steps (35+ lines) | 533 | CIE 1931 / 2° foveal | Original "Wright dashes" — 4 observers, CIE + RUCS charts, founding non-uniformity evidence. From Proc Phys Soc 53, 93 (1941) Tables 1-7. |
| [Smet 2010 memory colors](datasets/smet_2010_memory_colors/) | Memory colour distributions | 10 | IPT / D65 | 10 familiar objects × ~250 observer ratings, Sa metric. Optics Express 18, 26229. |
| [CIE 224:2017 TM-30 CES](datasets/cie_224_2017_tm30_ces/) | Reflectance spectra | 99 samples × 400 wavelengths | spectral 380-779nm | 99 color evaluation samples for modern fidelity index (TM-30 R_f). Mirrored from colour-science. |
| [CIE 170-2 cone fundamentals](datasets/cie_170_2_2015_cone_fundamentals/) | Spectral sensitivities | 4 files | spectral 390-830nm | Stockman-Sharpe 2°/10° cone fundamentals at 1/5 nm. From CVRL + official CIE. |
| [Bartleson 1960 memory](datasets/bartleson_1960_memory_colors/) | Memory colors | 20 (10×2 illuminants) | Munsell + CIE A/C | 50 observers × 10 natural objects × 931 Munsell chips. Historical predecessor to Smet 2010. |
| [Zhang 2023 laser display](datasets/zhang_2023_laser_display_brightness/) | Heterochromatic brightness (H-K) | 30 | BT.2020 / 16 observers | Modern wide-gamut H-K data on laser projection display. Micromachines 14, 1850 (2023). |
| [Berns 1991 RIT-DuPont vectors](datasets/berns_1991_rit_dupont_tolerance_vectors/) | Tolerance ellipsoid vectors | 156 (19 centers × 7-14 vectors) | CIELAB | Per-vector T50 + eigenvectors for 19 color centers. Color Res Appl 16, 297 (1991) Table IV. |
| [Lu 2023 facial skin](datasets/lu_2023_facial_skin_colors/) | Facial skin color appearance | 8 + 19 + 6 (3 files) | CIELAB / D65 | 80 CA+CN faces, 80+ observers, cross-cultural matching. Leeds PhD thesis 2023. |
| [SPCD 2023](datasets/spcd_2023_photographic_color_difference/) | **Image-level** perceptual color difference | **30,000 pairs** | sRGB / 15,273 photos | Smartphone photographic CD by Wang et al. 2023 IEEE TPAMI. Score-only (images downloaded separately). Largest CD dataset by 1000×. |
| [Manalansan-Webster 2025](datasets/manalansan_2025_warm_cool_colors/) | Warm-cool dimension, unique+binary hues | 20 + 4 + 6 (3 files) | cone-opponent / CRT | 19 observers, 36 hues × 3 luminance. First systematic warm-cool mapping. JoV 2025. |
| [Huang 2012](datasets/huang_2012_cielab_ellipses/) | **JND** chromaticity ellipses (printed) | 17 centers | CIELAB10 / D65 | 9 observers, 446 pairs × 27 reps. Industrial printed samples. JOSA A 29, 883 (2012). |
| [Koenderink 2026 3D metric](datasets/koenderink_2026_3d_metric_field/) | **JND** 3D metric field | 35 (BCC lattice) | RGB / display | 8 observers, 7 orientations × 14 extents. Median 3D Σ matrices. bioRxiv 2026. |
| [Klabes 2024 lighting preference](datasets/klabes_2024_color_preference_lighting/) | Color preference aggregation | **890 scenarios** × 67 metrics + SPDs | various / mixed | Z-score color preference + SPD for 890 lighting scenes from ~20 studies. TU Darmstadt 2024. |
| [Natural objects 2024 Argentina](datasets/natural_objects_2024_southern_cone_spectra/) | Spectral reflectance | 1,576 measurements (3 domains) | 400-1000 nm at 4 nm | Plants/Animals/Stones from Northwestern Argentina. Southern hemisphere bias correction. Scientific Data 2025. |
| [OSA-UCS 1974](datasets/osa_ucs_1974/) | **Uniform spacing** (committee atlas) | 558 samples + 344 equal-step pairs | D65 / 10° | The OSA committee's cuboctahedral equal-spacing lattice — the independent, **non-Munsell** spacing anchor. From ASTM E1360 Table 1; every row formula-validated. |
| [Fairchild-Pirrotta 1991](datasets/fairchild_pirrotta_1991/) | **H-K** object-colour lightness | 36 chromatic Munsell samples | Illuminant C | 11 observers matched achromatic lightness to chromatic surfaces — the classic CIELAB L\* correction reference. Color Res Appl 16, 385 (1991) Table I. |
| [Regan-Reffin-Mollon 1994](datasets/regan_1994_cvd_ellipses/) | **CVD discrimination ellipses** | 27 observers × 79 ellipses | display (equiluminant) | The pool's first **real colour-vision-deficient** observer data — protan/deutan/tritan + normal ellipses (Cambridge Colour Test). Validates CVD simulations. Vision Res 34, 1279 (1994) Tables 1-2. |

## Layout

Every dataset directory follows the same shape:

```
datasets/<name>/
├── canonical.csv     # one row per item, normalized schema
├── meta.yaml         # provenance, citation, illuminant, caveats
└── raw/              # original files, untouched
```

All canonical CSVs use CIELAB. The illuminant used to derive each pair's L*a*b* is preserved in either a row column or the dataset's `meta.yaml` — apply chromatic adaptation if you compare across datasets.

## Schemas

Three schemas cover everything. Each is fully specified under [`schemas/`](schemas/).

- **`pair_diff`** — color-difference pairs with both endpoints in CIELAB and a `dv` (visual difference) score. Used by COMBVD, MacAdam 1974, HelmlabFB.
- **`jnd_ellipses`** — discrimination-threshold ellipses around chromaticity centers. Used by MacAdam 1942.
- **`corresponding_colors`** — chromatic-adaptation pairs (test stimulus + matched stimulus under reference illuminant). Used by Breneman 1987.
- **`constant_hue`** — chips arranged on perceptual constant-hue loci. Used by Hung-Berns, Ebner-Fairchild, Munsell.
- **`gamut_boundary`** — boundary points of a color gamut (real or theoretical). Used by Pointer 1980, MacAdam 1935.
- **`delta_only`** — pair Δ values where endpoint Lab is not reconstructible from the source publication. Used by He 2022.
- **`color_names`** — natural-language color name ↔ RGB swatch. Used by xkcd colors.
- **`compound_legacy`** — multi-file dataset where per-file schemas differ; `canonical.csv` is an index of raw files, not a flat table. Used by LUTCHI.

## How to use

Each `canonical.csv` is plain CSV — read it with anything that reads CSV.

```python
import csv
with open("datasets/combvd/canonical.csv") as f:
    rows = list(csv.DictReader(f))
print(len(rows), "pairs")
print(rows[0])
# {'pair_id': 'combvd_0001', 'L1': '53.7...', 'a1': '49.4...', ..., 'sub_dataset': 'BFD-P', ...}
```

Or with pandas:

```python
import pandas as pd
df = pd.read_csv("datasets/combvd/canonical.csv")
df.groupby("sub_dataset")["dv"].describe()
```

## Reproduce the canonical export

The build script lives in [`scripts/build_canonical.py`](scripts/build_canonical.py). It reads raw files from a sibling `color-space/datasets/` directory by default; override with `RAW_ROOT`:

```bash
python3 scripts/build_canonical.py            # default raw root
RAW_ROOT=/path/to/raw python3 scripts/build_canonical.py
```

Validate against the declared schemas:

```bash
python3 scripts/validate.py
```

Requirements: `numpy`, `openpyxl`, `pyyaml`, and `colour-science` (for the Munsell snapshot).

## Known caveats

Each dataset's `meta.yaml` carries a `caveats:` field. The ones most often missed:

- **MacAdam 1974 is suprathreshold, not JND.** The famous MacAdam *ellipses* are from his 1942 paper; the 1974 paper is OSA UCS sample-pair spacing. If your code labels it `is_jnd = True`, that's a bug.
- **COMBVD uses three different reference whites.** The canonical CIELAB is computed under each pair's own white, not a common D65. Don't mix-and-match without chromatic adaptation.
- **He 2022 chip-pair linkage is missing in the source xlsx.** The pair sheet reports only Δ values, not which two chips form each pair. We keep the chips and Δ values in separate CSVs (`chips.csv`, `canonical.csv`).
- **HelmlabFB has no display calibration.** Observer monitors and ambient light vary across sessions; treat any per-pair number as a noisy estimate. Stratify by `color_gamut` (sRGB vs P3) and `platform` if you need cleaner subsets.
- **HelmlabFB observers are all tr-TR.** Cross-cultural generalization is unverified.
- **Pointer 1980 was specified under Illuminant SC**, not D65. The canonical L*a*b* is derived from the LCH source without chromatic adaptation.

## License

Canonical export: **CC BY 4.0** ([`LICENSE`](LICENSE)).

Each underlying dataset is academic and citation-based; cite the primary paper(s) when you use a dataset. Citations are listed in each `meta.yaml` and in `LICENSE`.

## Wanted (not yet included)

These would round out the pool but were not added for license, access, or scope reasons. Contributions welcome.

**Publicly fetchable but not yet added:**
- **World Color Survey** (Kay, Berlin, Maffi, Merrifield, Cook) — [linguistics.berkeley.edu/wcs/](https://linguistics.berkeley.edu/wcs/). 110 languages × ~24 speakers × 330 Munsell chips. Berkeley host was unreachable from here on 2026-05-28; will retry. The cross-cultural color-naming dataset.
- **xkcd full survey** — [xkcd.com/color/colorsurvey.tar.gz](https://xkcd.com/color/colorsurvey.tar.gz). ~5M raw color-naming responses. Public domain (CC0). Hundreds of MB, kept out of this repo for size; we ship only the curated 950-color list.
- **coloria-dev/color-data** — [github.com/coloria-dev/color-data](https://github.com/coloria-dev/color-data). Cleaner per-source split of BFD-P, LEEDS, RIT-DuPont, WITT, Luo-Rigg raw, Hung-Berns, MacAdam 1942 — useful if you want each constituent of COMBVD as a separate dataset rather than the aggregated form we ship.

**Behind a paywall or unreachable in plain text:**
- Brown 1957 small-field JND
- Wyszecki-Fielder 1971 ellipses
- Huang 2015 SCD/LCD
- Melgosa M&S 1997
- Kuehni 2003 constant-hue
- Sanders-Wyszecki 1958 / Wyszecki 1976 Helmholtz-Kohlrausch
- Lindsey-Brown 2014 color lexicon

## Related projects

- **[helmlab](https://helmlab.space)** — a color-science library and research toolkit that uses these datasets for color-space training, evaluation, and perceptual benchmarking. If you want to do something with the data instead of just look at it, helmlab is the place to start.
- **[gorkemyildiz.com](https://gorkemyildiz.com)** — author site with writing on perceptual color spaces, applied research, and related work.

## Citing this pool

```
color-perception-datasets (2026). Canonical pool of psychophysical color datasets.
https://github.com/Grkmyldz148/color-perception-datasets
```

Plus the underlying dataset citations (see `LICENSE`).
