"""Generate the static documentation site under docs/ and zip bundles under
docs/downloads/. The site is plain HTML + CSS — no framework, no JS build
step. GitHub Pages serves it directly from the docs/ folder.

Run after build_canonical.py:
    python3 scripts/build_site.py
"""

from __future__ import annotations

import csv
import html
import json
import shutil
import zipfile
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parent.parent
DATASETS = REPO / "datasets"
DOCS = REPO / "docs"
DL = DOCS / "downloads"
SCHEMAS = REPO / "schemas"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def load_meta(ds_dir: Path) -> dict:
    return yaml.safe_load((ds_dir / "meta.yaml").read_text())


def first_n_rows(csv_path: Path, n: int = 5) -> tuple[list[str], list[list[str]]]:
    with open(csv_path) as f:
        rdr = csv.reader(f)
        header = next(rdr)
        rows = []
        for i, r in enumerate(rdr):
            if i >= n:
                break
            rows.append(r)
    return header, rows


def row_count(csv_path: Path) -> int:
    with open(csv_path) as f:
        return sum(1 for _ in f) - 1


def make_zip(ds_dir: Path, out_path: Path) -> int:
    if out_path.exists():
        out_path.unlink()
    with zipfile.ZipFile(out_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for p in sorted(ds_dir.rglob("*")):
            if p.is_file():
                zf.write(p, arcname=p.relative_to(ds_dir.parent))
    return out_path.stat().st_size


def make_combined_zip(out_path: Path) -> int:
    if out_path.exists():
        out_path.unlink()
    with zipfile.ZipFile(out_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for ds_dir in sorted(DATASETS.iterdir()):
            if not ds_dir.is_dir():
                continue
            for p in sorted(ds_dir.rglob("*")):
                if p.is_file():
                    zf.write(p, arcname=str(p.relative_to(REPO)))
        for extra in [REPO / "schemas", REPO / "README.md", REPO / "LICENSE"]:
            if extra.is_dir():
                for p in sorted(extra.rglob("*")):
                    if p.is_file():
                        zf.write(p, arcname=str(p.relative_to(REPO)))
            elif extra.is_file():
                zf.write(extra, arcname=extra.name)
    return out_path.stat().st_size


def human_size(n: int) -> str:
    for unit in ["B", "KB", "MB", "GB"]:
        if n < 1024:
            return f"{n:.1f} {unit}" if unit != "B" else f"{n} B"
        n /= 1024
    return f"{n:.1f} TB"


# ---------------------------------------------------------------------------
# Dataset metadata (year per slug — used for sort + badge)
# ---------------------------------------------------------------------------
DATASET_YEARS = {
    "alder1982": 1982, "alman1989": 1989, "asano_observers": 2015,
    "breneman1987": 1987, "cherepkova_contrast": 2025, "combvd": 1995,
    "corresponding_colours": 1999, "ebner_fairchild": 1998,
    "fairchild_chen": 2010, "fairchild_johnson": 1999, "he2022": 2022,
    "helmlabfb": 2026, "hong_2025_ellipsoids": 2025, "hung_berns": 1995,
    "luo_rigg_ellipses": 1986, "lutchi": 1997,
    "macadam1935_optimal": 1935, "macadam1942": 1942, "macadam1974": 1974,
    "munsell": 1943, "pointer": 1980, "wcs": 1981,
    "xiao_unique_hues": 2011, "xkcd_colors": 2010,
}

TAG_COLORS = {
    "JND":                  "#dc2626",  # red
    "tolerance":            "#ea580c",  # orange
    "pair-diff":            "#2563eb",  # blue
    "constant-hue":         "#0891b2",  # teal
    "gamut":                "#7c3aed",  # purple
    "corresponding-colors": "#d97706",  # amber
    "naming":               "#475569",  # slate
    "observer-data":        "#0284c7",  # sky
    "contrast-pref":        "#9333ea",  # violet
    "lightness":            "#ca8a04",  # yellow
    "Δ-only":               "#64748b",  # neutral
    "suprathreshold":       "#16a34a",  # green (secondary)
}

# Order chips render in (left-to-right)
TAG_ORDER = [
    "JND", "pair-diff", "suprathreshold", "constant-hue", "gamut",
    "corresponding-colors", "tolerance", "naming", "lightness",
    "contrast-pref", "observer-data", "Δ-only",
]


def classify_tags(m: dict) -> list[str]:
    """Return the tags for a dataset, primary first."""
    tags = []
    schema = m.get("schema", "")
    slug = m.get("__slug", "")
    if "jnd_ellipses" in schema:
        tags.append("JND")
    elif "tolerance_ellipsoids" in schema:
        tags.append("tolerance")
    elif "corresponding_colors" in schema:
        tags.append("corresponding-colors")
    elif "color_names" in schema:
        tags.append("naming")
    elif "lightness_scaling" in schema:
        tags.append("lightness")
    elif "contrast_preference" in schema:
        tags.append("contrast-pref")
    elif "constant_hue" in schema:
        tags.append("constant-hue")
    elif "gamut" in schema:
        tags.append("gamut")
    elif "delta" in schema:
        tags.append("Δ-only")
    elif "pair_diff" in schema:
        tags.append("pair-diff")
    elif "compound_legacy" in schema:
        if "asano" in slug:
            tags.append("observer-data")
        elif "wcs" in slug:
            tags.append("naming")
        elif "xiao" in slug:
            tags.append("constant-hue")
        elif "lutchi" in slug:
            tags.append("corresponding-colors")
        elif "hong" in slug:
            tags.append("JND")
        else:
            tags.append("constant-hue")
    if m.get("is_jnd") and "JND" not in tags:
        tags.append("JND")
    elif not m.get("is_jnd", True) and m.get("is_suprathreshold") and "suprathreshold" not in tags:
        tags.append("suprathreshold")
    return tags


def short_illuminant(m: dict) -> str:
    illum = m.get("illuminant") or (
        m.get("illuminants", ["?"])[0] if m.get("illuminants") else "?"
    )
    if not isinstance(illum, str):
        return "mixed"
    parts = illum.split("/")
    short = parts[0].strip().split()
    if not short:
        return "mixed"
    val = short[0].rstrip(",")
    if val.lower() in ("unknown", "?", "varies", "mixed"):
        return "mixed"
    return val


def count_label(m: dict, n_rows: int) -> str:
    """Human-friendly count label for cards (e.g. '128 pairs', '25 ellipses')."""
    schema = m.get("schema", "")
    if "jnd_ellipses" in schema:
        return f"{n_rows:,} ellipses"
    if "tolerance_ellipsoids" in schema:
        return f"{n_rows:,} ellipsoids"
    if "constant_hue" in schema:
        return f"{n_rows:,} chips"
    if "gamut" in schema:
        return f"{n_rows:,} points"
    if "color_names" in schema:
        return f"{n_rows:,} colors"
    if "corresponding_colors" in schema:
        return f"{n_rows:,} pairs"
    if "pair_diff" in schema:
        return f"{n_rows:,} pairs"
    if "delta" in schema:
        return f"{n_rows:,} Δ entries"
    if "contrast_preference" in schema:
        return f"{n_rows:,} responses"
    if "lightness_scaling" in schema:
        return f"{n_rows:,} samples"
    if "compound_legacy" in schema:
        return f"{n_rows:,} files indexed"
    return f"{n_rows:,} rows"


# ---------------------------------------------------------------------------
# CSS — modern light theme, single source of truth
# ---------------------------------------------------------------------------
CSS = """\
:root {
  --bg:        #f7f8fa;
  --surface:   #ffffff;
  --text:      #0f172a;
  --text-soft: #475569;
  --muted:     #94a3b8;
  --border:    #e2e8f0;
  --border-strong: #cbd5e1;
  --accent:    #2563eb;
  --accent-hover: #1d4ed8;
  --accent-soft: #eff6ff;
  --code-bg:   #f1f5f9;
  --warn-bg:   #fffbeb;
  --warn-border: #fde68a;
  --warn-text: #92400e;
  --radius:    10px;
  --radius-sm: 6px;
  --shadow-sm: 0 1px 2px 0 rgba(15,23,42,.04);
  --shadow:    0 1px 3px 0 rgba(15,23,42,.06), 0 1px 2px -1px rgba(15,23,42,.04);
}

* { box-sizing: border-box; }
html, body { margin: 0; overflow-x: hidden; }
body {
  font-family: -apple-system, BlinkMacSystemFont, "Inter", "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
  font-size: 15px;
  line-height: 1.55;
  color: var(--text);
  background: var(--bg);
  -webkit-font-smoothing: antialiased;
}

h1, h2, h3 { line-height: 1.25; letter-spacing: -0.015em; margin: 0 0 12px; }
h1 { font-size: 30px; font-weight: 700; }
h2 { font-size: 20px; font-weight: 600; margin-top: 32px; }
h3 { font-size: 16px; font-weight: 600; margin-top: 20px; }
p  { margin: 12px 0; color: var(--text-soft); }
a  { color: var(--accent); text-decoration: none; }
a:hover { text-decoration: underline; }
code, pre { font-family: "SF Mono", Menlo, Monaco, Consolas, monospace; font-size: 13px; }
code { background: var(--code-bg); padding: 1px 5px; border-radius: 3px; color: var(--text); }
pre  { background: var(--code-bg); border-radius: var(--radius-sm); padding: 14px 16px; overflow-x: auto; line-height: 1.5; }
pre code { background: transparent; padding: 0; }

/* ---- Site chrome ---- */
.site-header {
  position: sticky; top: 0; z-index: 50;
  background: rgba(255,255,255,0.85);
  backdrop-filter: saturate(180%) blur(10px);
  -webkit-backdrop-filter: saturate(180%) blur(10px);
  border-bottom: 1px solid var(--border);
}
.site-header .inner {
  max-width: 1200px; margin: 0 auto;
  display: flex; align-items: center; justify-content: space-between;
  gap: 16px; padding: 14px 24px;
}
.brand {
  display: inline-flex; align-items: center; gap: 10px;
  color: var(--text); font-weight: 600; font-size: 15px; letter-spacing: -0.01em;
  line-height: 1;
}
.brand:hover { text-decoration: none; }
.brand-dot {
  display: inline-block;
  width: 18px; height: 18px; border-radius: 4px; flex-shrink: 0;
  background: linear-gradient(135deg,#dc2626,#ea580c,#ca8a04,#16a34a,#0891b2,#2563eb,#9333ea);
}
.nav {
  display: flex; align-items: center; gap: 20px;
}
.nav a {
  color: var(--text-soft); font-size: 14px; font-weight: 500;
  display: inline-flex; align-items: center;
  line-height: 1;
}
.nav a:hover { color: var(--accent); text-decoration: none; }
.nav a.active { color: var(--text); }
.nav a.cta {
  padding: 8px 14px; border-radius: 6px;
  background: var(--text); color: white;
  line-height: 1;
}
.nav a.cta:hover { background: var(--accent); color: white; }

main { max-width: 1200px; margin: 0 auto; padding: 32px 24px 80px; }

.site-footer {
  border-top: 1px solid var(--border);
  background: var(--surface);
  margin-top: 60px;
  padding: 28px 24px;
  color: var(--muted); font-size: 13px;
}
.site-footer .inner {
  max-width: 1200px; margin: 0 auto;
  display: flex; justify-content: space-between; align-items: center;
  flex-wrap: wrap; gap: 12px;
}

/* ---- Hero ---- */
.hero {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 32px 32px 28px;
  margin-bottom: 28px;
  box-shadow: var(--shadow-sm);
}
.hero .eyebrow {
  display: inline-flex; align-items: center; gap: 6px;
  font-size: 12px; font-weight: 600; letter-spacing: 0.06em; text-transform: uppercase;
  color: var(--accent); margin-bottom: 12px;
}
.hero .eyebrow::before {
  content: ""; width: 6px; height: 6px; border-radius: 50%; background: var(--accent);
}
.hero h1 { font-size: 34px; margin-bottom: 10px; max-width: 760px; }
.hero p.lede {
  font-size: 16px; color: var(--text-soft); max-width: 720px; margin: 0 0 20px;
}
.hero-actions { display: flex; gap: 10px; flex-wrap: wrap; }
.btn {
  display: inline-flex; align-items: center; gap: 8px;
  padding: 10px 16px; border-radius: 8px; font-size: 14px; font-weight: 500;
  border: 1px solid transparent; cursor: pointer;
  transition: background .12s ease, color .12s ease, border-color .12s ease;
}
.btn-primary { background: var(--text); color: white; }
.btn-primary:hover { background: var(--accent); color: white; text-decoration: none; }
.btn-ghost { background: transparent; color: var(--text); border-color: var(--border-strong); }
.btn-ghost:hover { border-color: var(--accent); color: var(--accent); text-decoration: none; }

.hero-stats {
  display: flex; gap: 28px; margin-top: 24px; padding-top: 20px;
  border-top: 1px solid var(--border); flex-wrap: wrap;
}
.hero-stat .num {
  font-size: 22px; font-weight: 700; letter-spacing: -0.02em;
  color: var(--text); font-variant-numeric: tabular-nums;
}
.hero-stat .lbl {
  font-size: 12px; color: var(--muted); margin-top: 2px;
  letter-spacing: 0.04em; text-transform: uppercase;
}

/* ---- Toolbar ---- */
.toolbar {
  position: sticky; top: 56px; z-index: 30;
  background: rgba(247,248,250,0.9);
  backdrop-filter: blur(8px);
  padding: 14px 0; margin-bottom: 16px;
}
.toolbar-row {
  display: flex; gap: 10px; align-items: center; flex-wrap: wrap;
}
.search-wrap {
  flex: 1 1 240px; min-width: 200px;
  position: relative;
}
.search-wrap input {
  width: 100%; border: 1px solid var(--border);
  border-radius: 8px; padding: 9px 12px 9px 34px;
  font-size: 14px; font-family: inherit;
  background: var(--surface); color: var(--text);
  transition: border-color .12s ease;
}
.search-wrap input:focus { outline: none; border-color: var(--accent); }
.search-wrap::before {
  content: ""; position: absolute; left: 12px; top: 50%; transform: translateY(-50%);
  width: 14px; height: 14px;
  background: url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='%2394a3b8' stroke-width='2'><circle cx='11' cy='11' r='7'/><path d='m21 21-4.3-4.3'/></svg>") no-repeat center / contain;
  pointer-events: none;
}
.sort-wrap select {
  border: 1px solid var(--border); border-radius: 8px;
  padding: 9px 28px 9px 12px; font-size: 13px; font-family: inherit;
  background: var(--surface); color: var(--text); cursor: pointer;
  appearance: none; -webkit-appearance: none;
  background-image: url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='%2394a3b8' stroke-width='2'><polyline points='6 9 12 15 18 9'/></svg>");
  background-repeat: no-repeat; background-position: right 8px center; background-size: 14px;
}
.count-pill {
  margin-left: auto; font-size: 13px; color: var(--text-soft);
  background: var(--surface); border: 1px solid var(--border);
  border-radius: 999px; padding: 6px 12px; font-variant-numeric: tabular-nums;
}

.chip-row {
  display: flex; gap: 6px; flex-wrap: wrap; margin-top: 10px;
}
.chip {
  display: inline-flex; align-items: center; gap: 6px;
  padding: 5px 10px; border-radius: 999px;
  background: var(--surface); border: 1px solid var(--border);
  color: var(--text-soft); font-size: 12px; font-weight: 500;
  cursor: pointer; user-select: none;
  transition: border-color .1s ease, background .1s ease, color .1s ease;
}
.chip:hover { border-color: var(--border-strong); }
.chip .dot { width: 8px; height: 8px; border-radius: 50%; background: currentColor; opacity: .6; }
.chip .n { color: var(--muted); font-size: 11px; font-variant-numeric: tabular-nums; }
.chip.active { background: var(--text); color: white; border-color: var(--text); }
.chip.active .n { color: rgba(255,255,255,0.7); }

/* ---- Card grid ---- */
.grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(330px, 1fr));
  gap: 14px;
}

.card {
  position: relative;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 18px 18px 16px;
  display: flex; flex-direction: column; gap: 10px;
  transition: border-color .12s ease, box-shadow .12s ease, transform .12s ease;
}
.card:hover {
  border-color: var(--border-strong);
  box-shadow: var(--shadow);
}
.card.hidden { display: none; }
.card.matches-search { border-color: var(--accent); }

.card-top {
  display: flex; align-items: center; justify-content: space-between;
}
.card-type {
  display: inline-flex; align-items: center; gap: 6px;
  font-size: 11px; font-weight: 600; letter-spacing: 0.02em;
  padding: 3px 9px; border-radius: 999px;
}
.card-type .dot { width: 8px; height: 8px; border-radius: 50%; background: currentColor; }
.card-year {
  font-size: 12px; color: var(--muted); font-weight: 500; font-variant-numeric: tabular-nums;
}

.card-title {
  font-size: 16px; font-weight: 600; line-height: 1.3;
  margin: 0; color: var(--text);
}
.card-title a { color: inherit; }
.card-title a:hover { color: var(--accent); text-decoration: none; }

.card-desc {
  margin: 0; font-size: 13.5px; color: var(--text-soft);
  line-height: 1.5;
  display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical;
  overflow: hidden; min-height: 41px;
}

.card-meta {
  display: flex; gap: 8px; align-items: center; flex-wrap: wrap;
  font-size: 12px; color: var(--muted);
  border-top: 1px solid var(--border); padding-top: 10px;
  margin-top: auto;  /* push meta + actions to the bottom of the card */
}
.card-meta .sep { color: var(--border-strong); }
.card-meta .v { color: var(--text-soft); font-weight: 500; }

.card-actions {
  display: flex; gap: 8px; margin-top: 2px;
}
.card-actions a {
  flex: 1; text-align: center;
  padding: 7px 10px; border-radius: 6px;
  font-size: 13px; font-weight: 500;
  border: 1px solid var(--border);
  color: var(--text-soft);
  display: inline-flex; align-items: center; justify-content: center; gap: 6px;
  transition: border-color .1s ease, color .1s ease, background .1s ease;
}
.card-actions a:hover {
  border-color: var(--accent); color: var(--accent);
  text-decoration: none;
}
.card-actions a.primary {
  background: var(--text); color: white; border-color: var(--text);
}
.card-actions a.primary:hover {
  background: var(--accent); border-color: var(--accent); color: white;
}

.empty-state {
  text-align: center; padding: 48px 16px; color: var(--muted); font-size: 14px;
}
.empty-state.hidden { display: none; }

/* ---- Dataset detail page ---- */
.detail-header {
  background: var(--surface); border: 1px solid var(--border);
  border-radius: var(--radius); padding: 24px 28px; margin-bottom: 24px;
}
.detail-header .crumbs {
  font-size: 13px; color: var(--muted); margin-bottom: 8px;
}
.detail-header .crumbs a { color: var(--muted); }
.detail-header .crumbs a:hover { color: var(--accent); }
.detail-header h1 { font-size: 26px; margin: 4px 0 8px; }
.detail-header .lede { font-size: 15px; color: var(--text-soft); max-width: 760px; margin: 0; }
.detail-tags { margin-top: 14px; display: flex; gap: 6px; flex-wrap: wrap; }

.detail-grid {
  display: grid; grid-template-columns: minmax(0, 1fr) 280px; gap: 28px;
  align-items: start;
}
.detail-grid > * { min-width: 0; }
@media (max-width: 900px) {
  .detail-grid { grid-template-columns: 1fr; }
}

/* Detail content: ensure long text wraps inside the column */
.detail-grid p, .detail-grid li, .detail-grid h1,
.detail-grid h2, .detail-grid h3, .detail-grid .citation {
  overflow-wrap: break-word;
  word-wrap: break-word;
}

.aside-card {
  background: var(--surface); border: 1px solid var(--border);
  border-radius: var(--radius); padding: 18px;
}
.aside-card h4 {
  margin: 0 0 10px; font-size: 11px; font-weight: 600;
  letter-spacing: 0.06em; text-transform: uppercase; color: var(--muted);
}
.aside-stat {
  display: flex; justify-content: space-between; align-items: center;
  padding: 6px 0; font-size: 13px;
}
.aside-stat + .aside-stat { border-top: 1px dashed var(--border); }
.aside-stat .k { color: var(--text-soft); }
.aside-stat .v { color: var(--text); font-weight: 500; font-variant-numeric: tabular-nums; }

.download-block {
  background: var(--surface); border: 1px solid var(--border);
  border-radius: var(--radius); padding: 14px 16px;
  display: flex; align-items: center; gap: 12px; margin: 14px 0;
  flex-wrap: wrap;
}
.download-block .info { flex: 1; min-width: 140px; }
.download-block .name { font-weight: 500; font-size: 14px; }
.download-block .sub  { font-size: 12px; color: var(--muted); margin-top: 2px; }
.download-block .size {
  font-size: 12px; color: var(--muted);
  padding: 4px 10px; border-radius: 999px; background: var(--bg);
  font-variant-numeric: tabular-nums;
}

.notes-list { margin: 16px 0; padding: 0; list-style: none; }
.notes-list li {
  background: var(--warn-bg); border-left: 3px solid var(--warn-border);
  padding: 12px 14px; margin: 8px 0; border-radius: var(--radius-sm);
  font-size: 14px; color: var(--text);
}
.citation {
  background: var(--code-bg); border-radius: var(--radius-sm);
  padding: 12px 14px; font-size: 13px; margin: 8px 0;
  color: var(--text-soft);
}

.table-wrap {
  overflow-x: auto; margin: 14px 0;
  border: 1px solid var(--border); border-radius: var(--radius-sm);
  background: var(--surface);
}
.table-wrap table { margin: 0; }
table { width: 100%; border-collapse: collapse; font-size: 13.5px; margin: 14px 0; }
th, td { padding: 9px 12px; text-align: left; border-bottom: 1px solid var(--border); }
.table-wrap th, .table-wrap td { white-space: nowrap; }
th {
  background: var(--surface); font-weight: 600; font-size: 11px;
  text-transform: uppercase; letter-spacing: 0.05em; color: var(--muted);
}
td.num, th.num { text-align: right; font-variant-numeric: tabular-nums; }
"""


# ---------------------------------------------------------------------------
# HTML chrome (header + footer + page shell)
# ---------------------------------------------------------------------------
def header(active: str = "") -> str:
    items = [
        ("Datasets", "./", "home"),
        ("Schemas", "./schemas.html", "schemas"),
        ("About", "./about.html", "about"),
    ]
    nav = "".join(
        f'<a href="{url}"{ " class=\"active\"" if k==active else ""}>{n}</a>'
        for n, url, k in items
    )
    return f"""<header class="site-header">
  <div class="inner">
    <a class="brand" href="./">
      <span class="brand-dot"></span>
      color-perception-datasets
    </a>
    <nav class="nav">
      {nav}
      <a href="https://helmlab.space" target="_blank" rel="noopener">helmlab ↗</a>
      <a class="cta" href="https://github.com/Grkmyldz148/color-perception-datasets" target="_blank" rel="noopener">GitHub</a>
    </nav>
  </div>
</header>
"""


FOOTER = """<footer class="site-footer">
  <div class="inner">
    <span>Released under CC BY 4.0 · Maintained by <a href="https://gorkemyildiz.com">Görkem Yıldız</a> · part of <a href="https://helmlab.space">helmlab</a>.</span>
    <span><a href="https://github.com/Grkmyldz148/color-perception-datasets">Source on GitHub</a></span>
  </div>
</footer>
"""


def page(title: str, body: str, active: str = "") -> str:
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{html.escape(title)} · color-perception-datasets</title>
  <link rel="stylesheet" href="./css/style.css">
</head>
<body>
{header(active)}
<main>
{body}
</main>
{FOOTER}
</body>
</html>
"""


def page_subdir(title: str, body: str, active: str = "") -> str:
    """Page for a file one level deep (datasets/X.html); fix asset paths."""
    out = page(title, body, active)
    return (
        out.replace('href="./css/', 'href="../css/')
        .replace('href="./"', 'href="../"')
        .replace('href="./about.html"', 'href="../about.html"')
        .replace('href="./schemas.html"', 'href="../schemas.html"')
        .replace('href="./datasets/', 'href="./')
    )


# ---------------------------------------------------------------------------
# Build
# ---------------------------------------------------------------------------
def build() -> None:
    DOCS.mkdir(exist_ok=True)
    (DOCS / "css").mkdir(exist_ok=True)
    (DOCS / "datasets").mkdir(exist_ok=True)
    DL.mkdir(exist_ok=True)
    (DOCS / "css" / "style.css").write_text(CSS)

    # ----- collect datasets -----
    datasets = []
    for ds_dir in sorted(DATASETS.iterdir()):
        if not ds_dir.is_dir():
            continue
        meta = load_meta(ds_dir)
        canon = ds_dir / "canonical.csv"
        meta["__slug"] = ds_dir.name
        meta["__rows"] = row_count(canon) if canon.exists() else 0
        datasets.append(meta)

    # ----- zips -----
    print("Building zip bundles…")
    for m in datasets:
        slug = m["__slug"]
        zp = DL / f"{slug}.zip"
        m["__zip_size"] = make_zip(DATASETS / slug, zp)
        print(f"  {slug}.zip: {human_size(m['__zip_size'])}")
    all_zip = DL / "all-datasets.zip"
    all_size = make_combined_zip(all_zip)
    print(f"  all-datasets.zip: {human_size(all_size)}")

    # ----- card data -----
    cards = []
    tag_counts: dict[str, int] = {}
    years: list[int] = []
    sources_total = 0
    for m in datasets:
        slug = m["__slug"]
        tags = classify_tags(m)
        primary = tags[0] if tags else "pair-diff"
        year = DATASET_YEARS.get(slug, 0)
        illum = short_illuminant(m)
        if year:
            years.append(year)
        sources_total += len(m.get("sources", []) or [])
        for t in tags:
            tag_counts[t] = tag_counts.get(t, 0) + 1
        cards.append({
            "slug":         slug,
            "title":        m.get("full_name", m.get("name", slug)),
            "desc":         (m.get("description") or m.get("type") or "")[:200],
            "tags":         tags,
            "primary":      primary,
            "year":         year,
            "illuminant":   illum,
            "count_label":  count_label(m, m["__rows"]),
            "size_bytes":   m["__zip_size"],
            "size_str":     human_size(m["__zip_size"]),
            "is_jnd":       bool(m.get("is_jnd")),
            "n_rows":       m["__rows"],
            "search_blob":  " ".join([
                m.get("full_name", ""), m.get("type", ""),
                m.get("description", ""), " ".join(tags), slug,
                illum, str(year),
            ]).lower(),
        })

    total_rows = sum(c["n_rows"] for c in cards)
    year_span = f"{min(years)}–{max(years)}" if years else "—"

    # ----- toolbar chips -----
    chip_html = ['<span class="chip active" data-tag="">All <span class="n">{}</span></span>'.format(len(cards))]
    for t in TAG_ORDER:
        if t not in tag_counts:
            continue
        color = TAG_COLORS.get(t, "#64748b")
        chip_html.append(
            f'<span class="chip" data-tag="{html.escape(t)}" style="--c:{color}">'
            f'<span class="dot" style="background:{color}"></span>'
            f'{html.escape(t)} <span class="n">{tag_counts[t]}</span>'
            f'</span>'
        )

    # ----- card HTML -----
    card_html_chunks = []
    for c in cards:
        primary = c["primary"]
        color = TAG_COLORS.get(primary, "#64748b")
        card_html_chunks.append(f"""<article class="card"
  data-tags="{html.escape(','.join(c['tags']))}"
  data-search="{html.escape(c['search_blob'])}"
  data-year="{c['year']}"
  data-rows="{c['n_rows']}"
  data-size="{c['size_bytes']}"
  data-name="{html.escape(c['title'].lower())}">
  <div class="card-top">
    <span class="card-type" style="background:{color}15;color:{color}">
      <span class="dot"></span>{html.escape(primary)}
    </span>
    <span class="card-year">{c['year'] or '—'}</span>
  </div>
  <h3 class="card-title"><a href="datasets/{c['slug']}.html">{html.escape(c['title'])}</a></h3>
  <p class="card-desc">{html.escape(c['desc'])}</p>
  <div class="card-meta">
    <span class="v">{html.escape(c['count_label'])}</span>
    <span class="sep">·</span>
    <span>Illum {html.escape(c['illuminant'])}</span>
    <span class="sep">·</span>
    <span>{html.escape(c['size_str'])}</span>
  </div>
  <div class="card-actions">
    <a class="primary" href="datasets/{c['slug']}.html">View details</a>
    <a href="downloads/{c['slug']}.zip" download>↓ Download</a>
  </div>
</article>""")

    # ----- index page -----
    index_body = f"""
<section class="hero">
  <span class="eyebrow">Open dataset pool</span>
  <h1>Psychophysical color-perception datasets, cleaned and unified.</h1>
  <p class="lede">A single pool of {len(cards)} classic and modern datasets — JND ellipses, suprathreshold color difference, constant hue, gamut boundaries, corresponding colors, color naming and more — packaged in consistent schemas with provenance and caveats intact.</p>
  <div class="hero-actions">
    <a class="btn btn-primary" href="downloads/all-datasets.zip" download>Download all ({human_size(all_size)})</a>
    <a class="btn btn-ghost" href="https://github.com/Grkmyldz148/color-perception-datasets" target="_blank" rel="noopener">View on GitHub</a>
  </div>
  <div class="hero-stats">
    <div class="hero-stat"><div class="num">{len(cards)}</div><div class="lbl">datasets</div></div>
    <div class="hero-stat"><div class="num">{total_rows:,}</div><div class="lbl">total rows</div></div>
    <div class="hero-stat"><div class="num">{len(tag_counts)}</div><div class="lbl">categories</div></div>
    <div class="hero-stat"><div class="num">{year_span}</div><div class="lbl">year range</div></div>
    <div class="hero-stat"><div class="num">CC BY 4.0</div><div class="lbl">license</div></div>
  </div>
</section>

<section class="toolbar">
  <div class="toolbar-row">
    <div class="search-wrap">
      <input type="search" id="q" placeholder="Search name, description, illuminant, year…" autocomplete="off" />
    </div>
    <div class="sort-wrap">
      <select id="sort">
        <option value="name">Sort: Name (A–Z)</option>
        <option value="year-desc">Sort: Newest first</option>
        <option value="year-asc">Sort: Oldest first</option>
        <option value="rows-desc">Sort: Most rows</option>
        <option value="size-desc">Sort: Largest file</option>
      </select>
    </div>
    <span class="count-pill" id="count">{len(cards)} shown</span>
  </div>
  <div class="chip-row" id="chips">
    {''.join(chip_html)}
  </div>
</section>

<section class="grid" id="grid">
{''.join(card_html_chunks)}
</section>

<div class="empty-state hidden" id="empty">No datasets match these filters. <a href="#" id="clear">Clear all</a>.</div>

<script>
(function() {{
  const grid = document.getElementById('grid');
  const cards = Array.from(grid.querySelectorAll('.card'));
  const q = document.getElementById('q');
  const sortSel = document.getElementById('sort');
  const chips = Array.from(document.querySelectorAll('#chips .chip'));
  const count = document.getElementById('count');
  const empty = document.getElementById('empty');
  const clearLink = document.getElementById('clear');
  let activeTag = '';

  function apply() {{
    const needle = (q.value || '').trim().toLowerCase();
    let shown = 0;
    cards.forEach(c => {{
      const tags = (c.dataset.tags || '').split(',');
      const okText = !needle || (c.dataset.search || '').includes(needle);
      const okTag  = !activeTag || tags.includes(activeTag);
      const vis = okText && okTag;
      c.classList.toggle('hidden', !vis);
      if (vis) shown++;
    }});
    count.textContent = (shown === cards.length)
      ? `${{shown}} datasets`
      : `${{shown}} of ${{cards.length}} shown`;
    empty.classList.toggle('hidden', shown !== 0);
  }}

  function applySort() {{
    const mode = sortSel.value;
    const list = cards.slice();
    list.sort((a, b) => {{
      switch (mode) {{
        case 'year-desc': return (b.dataset.year|0) - (a.dataset.year|0);
        case 'year-asc':  return (a.dataset.year|0) - (b.dataset.year|0);
        case 'rows-desc': return (b.dataset.rows|0) - (a.dataset.rows|0);
        case 'size-desc': return (b.dataset.size|0) - (a.dataset.size|0);
        default:          return (a.dataset.name || '').localeCompare(b.dataset.name || '');
      }}
    }});
    list.forEach(c => grid.appendChild(c));
  }}

  q.addEventListener('input', apply);
  sortSel.addEventListener('change', applySort);
  chips.forEach(chip => chip.addEventListener('click', () => {{
    chips.forEach(c => c.classList.remove('active'));
    chip.classList.add('active');
    activeTag = chip.dataset.tag;
    apply();
  }}));
  clearLink.addEventListener('click', (e) => {{
    e.preventDefault();
    q.value = '';
    activeTag = '';
    chips.forEach(c => c.classList.toggle('active', !c.dataset.tag));
    apply();
  }});

  applySort();
}})();
</script>
"""
    (DOCS / "index.html").write_text(page("Datasets", index_body, "home"))

    # ----- per-dataset pages -----
    for m in datasets:
        slug = m["__slug"]
        canon = DATASETS / slug / "canonical.csv"
        header_row, sample_rows = first_n_rows(canon, n=5)
        tags = classify_tags(m)
        primary = tags[0] if tags else "pair-diff"
        color = TAG_COLORS.get(primary, "#64748b")
        year = DATASET_YEARS.get(slug, 0)
        illum = short_illuminant(m)

        tag_chip_html = "".join(
            f'<span class="card-type" style="background:{TAG_COLORS.get(t,"#64748b")}15;color:{TAG_COLORS.get(t,"#64748b")}">'
            f'<span class="dot"></span>{html.escape(t)}</span>'
            for t in tags
        )

        sample_table = (
            "<div class='table-wrap'><table><thead><tr>"
            + "".join(f"<th>{html.escape(h)}</th>" for h in header_row)
            + "</tr></thead><tbody>"
            + "".join(
                "<tr>" + "".join(f"<td>{html.escape(str(c))}</td>" for c in r) + "</tr>"
                for r in sample_rows
            )
            + "</tbody></table></div>"
        )

        sources_html = ""
        for src in m.get("sources", []) or []:
            if "paper" in src:
                sources_html += f'<div class="citation">{html.escape(src["paper"])}</div>'
            elif "note" in src:
                sources_html += f'<div class="citation">{html.escape(src["note"])}</div>'
            elif "snapshot_source" in src:
                sources_html += f'<div class="citation">Snapshot: {html.escape(src["snapshot_source"])}</div>'

        notes = m.get("notes") or m.get("caveats") or []
        notes_html = ""
        if notes:
            notes_html = (
                "<h2>Notes</h2><ul class='notes-list'>"
                + "".join(f"<li>{html.escape(c)}</li>" for c in notes)
                + "</ul>"
            )

        description_html = ""
        if m.get("description"):
            description_html = f"<h2>Description</h2><p>{html.escape(m['description'])}</p>"

        # Aside (right column): key facts
        aside_items = []
        def add(k, v):
            if v is not None and v != "":
                aside_items.append(f'<div class="aside-stat"><span class="k">{k}</span><span class="v">{html.escape(str(v))}</span></div>')
        add("Year", year or "—")
        add("Illuminant", illum)
        add("Schema", m.get("schema", "—"))
        add("Rows", f"{m['__rows']:,}")
        if m.get("n_observers"): add("Observers", m["n_observers"])
        if m.get("dv_units"): add("Δv units", m["dv_units"][:40] + ("…" if len(str(m["dv_units"])) > 40 else ""))
        if "is_jnd" in m: add("JND data?", "yes" if m["is_jnd"] else "no")
        add("File size", human_size(m["__zip_size"]))

        sub_html = ""
        if m.get("sub_datasets"):
            sub_html = (
                "<h3>Sub-datasets</h3><div class='table-wrap'><table><thead><tr><th>Name</th><th class='num'>Rows</th></tr></thead><tbody>"
                + "".join(
                    f"<tr><td>{html.escape(name)}</td><td class='num'>{count:,}</td></tr>"
                    for name, count in m["sub_datasets"].items()
                )
                + "</tbody></table></div>"
            )

        raw_dir = DATASETS / slug / "raw"
        raw_files_html = ""
        if raw_dir.exists():
            files = sorted(raw_dir.iterdir())
            if files:
                raw_files_html = "<h3>Raw files preserved</h3><div class='table-wrap'><table><thead><tr><th>File</th><th class='num'>Size</th></tr></thead><tbody>" + "".join(
                    f"<tr><td><code>raw/{html.escape(f.name)}</code></td><td class='num'>{human_size(f.stat().st_size)}</td></tr>"
                    for f in files
                ) + "</tbody></table></div>"

        body = f"""<div class="detail-header">
  <div class="crumbs"><a href="../">Datasets</a> / {html.escape(m.get('name', slug))}</div>
  <h1>{html.escape(m.get('full_name', m.get('name', slug)))}</h1>
  <p class="lede">{html.escape(m.get('type', ''))}</p>
  <div class="detail-tags">{tag_chip_html}</div>
</div>

<div class="detail-grid">
  <div>
    {description_html}

    <div class="download-block">
      <div class="info">
        <div class="name">{slug}.zip</div>
        <div class="sub">Contains canonical.csv + meta.yaml + raw/</div>
      </div>
      <span class="size">{human_size(m['__zip_size'])}</span>
      <a class="btn btn-primary" href="../downloads/{slug}.zip" download>Download</a>
    </div>

    {notes_html}

    <h2>Sample rows</h2>
    <p>First 5 rows of <code>canonical.csv</code>:</p>
    {sample_table}

    {sub_html}

    {raw_files_html}

    <h2>Source publications</h2>
    {sources_html}
  </div>

  <aside>
    <div class="aside-card">
      <h4>At a glance</h4>
      {''.join(aside_items)}
    </div>
  </aside>
</div>
"""
        (DOCS / "datasets" / f"{slug}.html").write_text(page_subdir(m.get("name", slug), body, ""))

    # ----- About page -----
    schemas_in_use = sorted({m.get("schema", "").split("+")[0].split("_with_")[0].strip() for m in datasets if m.get("schema") and isinstance(m.get("schema"), str)})
    about_body = f"""<section class="hero">
  <span class="eyebrow">About</span>
  <h1>Why this pool exists.</h1>
  <p class="lede">Color-science datasets live in many incompatible formats — paper-PDF tables, vendor xlsx, ad-hoc JSON, and code-only loaders that disappear when libraries change. Several widely-used datasets carry well-known but rarely-cited caveats (MacAdam 1974 is often mis-cited as the 1942 JND ellipses; COMBVD has three different reference whites; He 2022 ships chip and pair data in incompatible sheets). This pool normalizes the format, preserves the raw, and writes the caveats down where you'll actually see them.</p>
</section>

<h2>Maintainer &amp; related projects</h2>
<p>Maintained by <a href="https://gorkemyildiz.com"><strong>Görkem Yıldız</strong></a> as part of the <a href="https://helmlab.space"><strong>helmlab</strong></a> research toolkit — a color-science library that uses these datasets for color-space training, evaluation, and perceptual benchmarking. If you want to do something with the data instead of just look at it, helmlab is the place to start.</p>

<h2>Methodology</h2>
<ul>
  <li><strong>Canonical CSV</strong> per dataset, under one of {len(schemas_in_use)} documented schemas (<a href="schemas.html">see schemas</a>).</li>
  <li><strong>meta.yaml</strong> per dataset capturing: native illuminant + observer, native color space, what <code>dv</code> literally means, citation, and caveats.</li>
  <li><strong>raw/</strong> per dataset — original files preserved unchanged.</li>
  <li><strong>scripts/validate.py</strong> checks every canonical file against its declared schema (range checks, row counts, sentinel detection).</li>
</ul>

<h2>What this pool is not</h2>
<ul>
  <li>It is <em>not</em> a benchmark. It packages data; it does not define a leaderboard.</li>
  <li>It is <em>not</em> exhaustive — paywalled / out-of-print datasets (Brown 1957, Wyszecki-Fielder 1971, Huang 2015 SCD/LCD, Sanders-Wyszecki 1958, Bartleson 1960, etc.) are listed as <em>Wanted</em> in the README. PRs welcome.</li>
  <li>It is <em>not</em> a substitute for reading the original papers. The papers carry experimental conditions, observer briefing, and uncertainty estimates that no CSV row count can replace.</li>
</ul>

<h2>Privacy</h2>
<p>The HelmlabFB dataset is self-collected and originally contained 71 named observers. All names have been replaced with deterministic pseudonyms (<code>observer_001</code>..<code>observer_071</code>) so per-observer grouping is preserved for analysis but no personal data is published.</p>

<h2>How to contribute</h2>
<p>Open an issue or a pull request on <a href="https://github.com/Grkmyldz148/color-perception-datasets">GitHub</a>. Useful contributions: missing datasets (especially the paywalled classics), corrections to caveats, additional metadata fields, schema extensions.</p>
"""
    (DOCS / "about.html").write_text(page("About", about_body, "about"))

    # ----- Schemas page -----
    schema_blocks = []
    for sp in sorted(SCHEMAS.glob("*.yaml")):
        sd = yaml.safe_load(sp.read_text())
        cols_html = "".join(
            f"<tr><td><code>{html.escape(k)}</code></td>"
            f"<td>{html.escape(v.get('type',''))}</td>"
            f"<td>{'yes' if v.get('required') else 'no'}</td>"
            f"<td>{html.escape(v.get('description','').strip())}</td></tr>"
            for k, v in sd.get("columns", {}).items()
        )
        invs = sd.get("invariants", []) or []
        inv_html = "".join(f"<li>{html.escape(i)}</li>" for i in invs)
        invariants = ("<h3>Invariants</h3><ul>" + inv_html + "</ul>") if inv_html else ""
        schema_blocks.append(f"""<section style="margin-bottom:36px">
  <h2><code>{html.escape(sd['schema_name'])}</code></h2>
  <p>{html.escape(sd.get('description','').strip())}</p>
  <div class="table-wrap"><table>
    <thead><tr><th>Column</th><th>Type</th><th>Required</th><th>Description</th></tr></thead>
    <tbody>{cols_html}</tbody>
  </table></div>
  {invariants}
</section>""")
    schemas_body = f"""<section class="hero">
  <span class="eyebrow">Schemas</span>
  <h1>Every canonical CSV follows one of these schemas.</h1>
  <p class="lede">Each <code>meta.yaml</code> declares which schema its <code>canonical.csv</code> uses. Schemas live in the repo at <code>schemas/&lt;name&gt;.yaml</code>.</p>
</section>
{''.join(schema_blocks)}
"""
    (DOCS / "schemas.html").write_text(page("Schemas", schemas_body, "schemas"))

    (DOCS / ".nojekyll").write_text("")

    print(f"\nSite built at {DOCS}")
    print(f"Datasets: {len(datasets)}, total rows: {total_rows:,}, combined zip: {human_size(all_size)}")


if __name__ == "__main__":
    build()
