# color-perception-datasets

A clean, schema-validated pool of psychophysical color datasets used in color-space and color-difference research. 24 datasets, one consistent layout, every file CC BY 4.0.

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
| [xkcd colors](datasets/xkcd_colors/) | Color naming (English) | 949 | sRGB / D65 | Curated 950 most-popular names (Munroe 2010, CC0) |
| [WCS](datasets/wcs/) | Cross-cultural naming | 330 chips × 110 langs × 863k responses | Munsell / Illum C | World Color Survey (Kay-Berlin-Maffi 1976–1981) |
| [Luo-Rigg 1986](datasets/luo_rigg_ellipses/) | **JND** chromaticity ellipses | 132 (10 source sets) | Illuminant C | Surface-color JND, larger than MacAdam 1942 |
| [Alman 1989](datasets/alman1989/) | 3D tolerance ellipsoids | 45 (9 centers) | D65 / 2° | RIT-DuPont probit-fitted tolerance, industrial QA |
| [Hong 2025](datasets/hong_2025_ellipsoids/) | **JND** isoluminant ellipsoids (modern) | OSF pointer | calibrated display | 8 observers, Wishart Process, eLife 2025 |
| [Cherepkova 2025](datasets/cherepkova_contrast/) | Contrast preference (accessibility) | 10,978 (499 images × 22 observers) | sRGB | NTNU, CC-BY-4.0 — APCA/WCAG-adjacent |
| [Asano observers](datasets/asano_observers/) | Observer CMF database | 151 individuals + 1000 MC + 10 categorical | spectral | Inter-observer uncertainty bands on any predicted ΔE |

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
