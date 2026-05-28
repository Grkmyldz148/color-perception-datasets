# Hong et al. 2025 — Where to find the full data

The full dataset (raw experimental data, organized data, model predictions,
calibration files) lives on OSF and is too large to redistribute here.

**Direct downloads:**

- OSF project: <https://osf.io/k27js/>
- Code repository: <https://github.com/fh862/ellipsoids_eLife2025>

**OSF folders:**

| Folder                                | Contents |
|---------------------------------------|----------|
| Raw experimental data                 | Per-observer 3AFC trial logs (8 observers, ~12k trials total) |
| Organized data and model predictions  | Fitted Wishart Process ellipsoids per observer + group |
| configs_aepsych                       | Adaptive psychophysics configs for AEPsych framework |
| Calibration and transformation        | Display calibration files, CIELAB transform parameters |

**To fetch a folder programmatically:**

    pip install osfclient
    osf -p k27js fetch "Organized data and model predictions/<file>"

The bundled README.pdf in this directory is the full data description from
the OSF root.
