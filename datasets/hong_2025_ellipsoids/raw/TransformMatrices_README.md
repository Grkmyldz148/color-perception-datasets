# Transformation Matrices — Dell Monitor, 02/24/2025

Calibration and transformation matrices for the Dell monitor used in the
Hong et al. (2025) color-discrimination experiment.

## Calibration file

**B_monitor_dell_02242025.mat** — spectral power distributions of the
monitor's R, G, and B primaries, measured on 2025-02-24.  Stored in
Psychtoolbox wls/S format with S = [380 2 201] (380–780 nm, 2 nm steps).
CSV matrices below are derived from it.

## MATLAB generation script

**ComputeTransformMatrices.m** computes and writes a number of the CSV
files.  The other files were provided directly by Hong. Requirements:

- Psychtoolbox-3 on the MATLAB path (tbUse('Psychtoolbox-3'))
- Run from this directory (or set MATLAB's current folder to it before running)

The script loads B_monitor_dell_02242025.mat and three Psychtoolbox CMF files
(T_xyz1931, T_xyzCIEPhys2, T_cones_ss2), then writes the CSV files listed
below.

## Coordinate spaces

| Label | Description |
|-------|-------------|
| 2DW (aka W) | 2D isoluminant model space. [0, 0] = neutral monitor gray [0.5, 0.5, 0.5] in linear RGB. Augmented to [w1, w2, 1] for affine transforms. |
| DKL | Derrington–Krauskopf–Lennie color space restricted to the isoluminant plane, also augmented as [d1, d2, 1]. |
| RGB | Linear (non-gamma-corrected) monitor RGB, range [0, 1]. |
| XYZ 1931 | CIE 1931 XYZ. Y is in cd/m² (CMF scaled by 683 in the script). |
| XYZ 2015 | CIE 2015 XYZ (physiologically based, T_xyzCIEPhys2). Y is in cd/m². |
| LMS | Stockman–Sharpe 2° cone fundamentals (T_cones_ss2). Output order is L, M, S.  These are also the CIE 2006 2-deg physiologically based fundamentals. |

## CSV files

All files follow the naming pattern `M_<From>To<To>_DELL_02242025_copy.csv`.
The `_copy` suffix indicates these were copied from the original calibration
location into this directory or generated for this location.  All matrices are 3×3.  They are set up so that they should be applied to column vectors from the left.  For example, LMS = M_RGBToLMS*RGB, where LMS and RGB are 3x1 column vectors.

### Affine matrices (augmented coordinates)

2DW and DKL transforms use an augmented third coordinate (always 1) to handle
the DC offset between model-space origin and monitor-gray.  The 3rd column of
these matrices is the DC offset vector. 

| File | Transform | Source |
|------|-----------|--------|
| M_2DWToRGB_DELL_02242025_copy.csv | 2DW → RGB | Inverse of RGB -> 2DW |
| M_RGBTo2DW_DELL_02242025_copy.csv | RGB → 2DW | Paper Table S2 |
| M_2DWToDKLPlane_DELL_02242025_copy.csv | 2DW → DKL plane | Inverse of DKL plane -> 2DW |
| M_DKLPlaneTo2DW_DELL_02242025_copy.csv | DKL plane → 2DW | Paper Table S2 |

### Linear matrices (monitor colorimetry)

These are derived from `B_monitor_dell_02242025.mat` via Psychtoolbox CMFs.
Computed via monitor primaries (e.g. `M_LMSToXYZ1931 = M_RGBToXYZ1931 @ M_LMSToRGB`)
to ensure consistency with the monitor gamut.  RGB refers to linear monitor values (before gamma correction).

| `File` | `Transform` | `Notes` |
|------|-----------|-------|
| M_RGBToLMS_DELL_02242025_copy.csv | RGB -> LMS | CIE 2006 2-deg fundamentals (same as Stockman-Sharpe 2-deg fundamentals) |
| M_LMSToRGB_DELL_02242025_copy.csv | LMS -> RGB | Inverse of above |
| M_RGBToXYZ1931_DELL_02242025_copy.csv | RGB → XYZ 1931 | Y in cd/m2 with PTB radiance conventions for XYZ1931. Y ≈ 190 cd/m² at full white. |
| M_XYZ1931ToRGB_DELL_02242025_copy.csv | XYZ 1931 → RGB | Inverse of above |
| M_LMSToXYZ1931_DELL_02242025_copy.csv | LMS → XYZ 1931 | This transfromation goes through RGB to handle difference in underlying colorimetric observers. |
| M_XYZ1931ToLMS_DELL_02242025_copy.csv | XYZ 1931 → LMS | Inverse of above. |
| M_RGBToXYZ2015_DELL_02242025_copy.csv | RGB -> XYZ 2015 | Y in cd/2 with PTB radiance conventions for XYZ2015.         |
| M_XYZ2015ToRGB_DELL_02242025_copy.cs  | XYZ 2015 -> RGB | Inverse of above                                             |
| M_LMSToXYZ2015_DELL_02242025_copy.csv | LMS → XYZ 2015 | Goes through RGB to handle difference in underlying colorimetric observers |
| M_XYZ2015ToLMS_DELL_02242025_copy.csv | XYZ 2015 → LMS | Inverse of the above |

## Deriving matrices

Transform matrices not provided above can generally be derived by combining the above, or by starting with the monitor primary spectra.

## Usage in Python 

Python can read `transform_dir` from `local_config.json` and load matrices with:

```python
transform_dir = pathlib.Path(cfg["transform_dir"])
M_2DWToRGB = np.loadtxt(transform_dir / "M_2DWToRGB_DELL_02242025_copy.csv", delimiter=",")
```

The `transform_dir` key must point to this directory on each machine for the relevant experiment.
