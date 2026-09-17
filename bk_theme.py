"""
bk_theme
========

Braga-Kribitz Design System, applied to charts.

Every value here is transcribed from the system's own token files
(`tokens/colors.css`, `typography.css`, `spacing.css`, `grid.css`,
`chart-palettes.css`). Nothing is invented. If a token changes there, change it
here; this module is a mirror, not a second opinion.

The non-negotiables it enforces
-------------------------------
1. **Flat and opaque.** Surface colours only, no gradients, no shadow, no alpha
   tricks. Recessive elements use a lighter *token*, never transparency.
2. **Hairlines are structure.** 1px in `mid`, used the way rules are used in a
   printed technical document.
3. **Orange is spent once.** `--accent-01` marks the single impact figure. A
   chart reads almost monochrome until one number earns it. Passing more than
   one highlight warns.
4. **Blue is a moment, not a default.** `--accent-02` only for a deliberate
   theme-shift, or as the anchor of the sequential-blue data ramp.
5. **Figures are tabular.** matplotlib cannot toggle OpenType features, so the
   system's own rule solves it: all numbering, data labels and tags are set in
   Söhne Mono, which is tabular by construction.
6. **Square corners, no radius.** Nothing to configure; stated so nobody adds it.
7. **Every published figure carries provenance.** `footer()` stamps the source
   rows, run id and epistemic tag.

Usage
-----
    import bk_theme as bk

    bk.register_fonts("assets/fonts")     # optional but strongly preferred
    bk.apply(mode="light")

    fig, ax = bk.decision_panel(
        kpis=[{"label": "5-YEAR SAVING", "value": "EUR 684k",
               "note": "net present value, 8% discount", "accent": True}],
        finding="Hybrid + AMR is EUR 684k cheaper than staying all-human",
        context="5-year TCO by workforce scenario, 8% discount rate.",
    )

Font licence note
-----------------
The Söhne files shipped with the design system are Klim's TRIAL weights, marked
evaluation-only. Raster export (PNG) does not embed a font. SVG written with
``svg.fonttype: none`` references the family by name and does not embed either.
PDF export **does** embed, so PDF is disabled by default in :func:`save`. Turn it
on once retail Söhne is licensed.
"""

from __future__ import annotations

import json
import re
import warnings
from pathlib import Path
from typing import Callable, Iterable, Mapping, Sequence

import matplotlib as mpl
import matplotlib.pyplot as plt
from matplotlib.axes import Axes
from matplotlib.figure import Figure
from matplotlib.font_manager import FontProperties, fontManager
from matplotlib.ticker import FuncFormatter, MaxNLocator

__all__ = [
    "TOKENS", "COLOR", "CHART_PALETTES", "EPISTEMIC_TAGS",
    "register_fonts", "apply", "mode", "c", "font",
    "figsize", "new_figure", "decision_panel",
    "highlight_palette", "neutral_ramp", "palette", "tag_color",
    "finding_title", "footer", "direct_label", "value_labels", "kpi_row",
    "strip_chrome", "reference_line", "annotate_delta", "check_glyphs",
    "fmt_eur", "fmt_eur_k", "fmt_eur_m", "fmt_pct", "fmt_pp",
    "fmt_months", "fmt_int", "money_axis", "pct_axis",
    "save", "dump_tokens", "plotly_template",
]

# ---------------------------------------------------------------------------
# 1. Colour — tokens/colors.css
# ---------------------------------------------------------------------------

#: Raw base palette, verbatim from the system.
RAW = {
    "off-white": "#E6E6E6",
    "paper": "#DEDEDE",
    "light": "#D6D6D6",
    "mid": "#A0A0A0",
    "dark-grey": "#646464",
    "off-black": "#282828",
    "orange": "#FA6400",
    "blue": "#5B7FFF",
}

#: Semantic roles per mode. Light is the default; dark is a property an element
#: carries, exactly as the system defines it.
COLOR = {
    "light": {
        "surface": RAW["off-white"],   # page background
        "surface-2": RAW["paper"],     # raised / hover wash
        "surface-3": RAW["light"],     # borders of raised blocks
        "ink": RAW["off-black"],       # primary text
        "ink-2": "#4A4A4A",            # secondary text — darker than the token's #646464 (readability revision 2026-09-17)
        "mid": RAW["mid"],             # numbering, labels, hairlines
        "accent-01": RAW["orange"],    # impact, arrows, status
        "accent-02": RAW["blue"],      # theme-shift moments only
    },
    "dark": {
        "surface": "#1A1A1A",
        "surface-2": "#2D2D2D",
        "surface-3": "#4A4A4A",
        "ink": "#F5F5F5",
        "ink-2": "#D0D0D0",
        "mid": "#808080",
        "accent-01": RAW["orange"],
        "accent-02": RAW["blue"],
    },
}

_MODE = "light"


def mode() -> str:
    """Current render mode, ``"light"`` or ``"dark"``."""
    return _MODE


def c(role: str) -> str:
    """Resolve a semantic colour role in the current mode.

    ``c("ink")``, ``c("accent-01")``, ``c("mid")``. Use this instead of a hex
    literal anywhere in project code; the system's own lint rule forbids raw hex.
    """
    try:
        return COLOR[_MODE][role]
    except KeyError as exc:
        raise KeyError(
            f"Unknown colour role {role!r}. Available: {sorted(COLOR[_MODE])}"
        ) from exc


# ---------------------------------------------------------------------------
# 2. Chart palettes — tokens/chart-palettes.css
# ---------------------------------------------------------------------------
# Stop convention: index 0 = most saturated / darkest, last = lightest.

CHART_PALETTES = {
    "seq-blue": [
        "#111D7A", "#2133B0", "#5B7FFF", "#7A97FF", "#97B1FF",
        "#B3C9FF", "#CDDCFF", "#E2ECFF", "#F2F5FF",
    ],
    "seq-orange": [
        "#6B2A00", "#A83F00", "#FA6400", "#FF8332", "#FF9F60",
        "#FFB98E", "#FFD0B3", "#FFE4D0", "#FFF3EC",
    ],
    "div-warm-cool": [
        "#00876C", "#449A71", "#6CAC78", "#91BD80", "#B6CF8B", "#DAE09A",
        "#FFF0A8",
        "#FDD880", "#FBBE5E", "#F9A03C", "#F78220", "#F56E0A", "#FA6400",
    ],
    "div-political": [
        "#111D7A", "#2A42B8", "#4D67D4", "#748FE6", "#9DB5F2", "#C6D8FA",
        "#EBEBEB",
        "#F5D2D4", "#EFB2B8", "#E5909A", "#D86E7E", "#C74B62", "#B22848",
    ],
    "interp-long": [
        "#5B7FFF", "#1280CC", "#008FA8", "#009882",
        "#2EA05A", "#78A028", "#B89C10", "#DDA026",
    ],
    "interp-short": [
        "#5B7FFF", "#9D6FF6", "#CD5AE0", "#F041C0",
        "#FF2A99", "#FF2B6F", "#FF4643", "#FA6400",
    ],
}

#: Dark-mode stop overrides, so near-white stops stay legible on dark surfaces.
CHART_DARK_OVERRIDES = {
    ("seq-blue", 7): "#C8DCFF",
    ("seq-blue", 8): "#DCEAFF",
    ("seq-orange", 7): "#FFD8BF",
    ("seq-orange", 8): "#FFEADE",
    ("div-political", 6): "#909090",
    ("div-warm-cool", 6): "#E8D860",
}

#: Categorical structure greys. Drawn from the system's own neutral roles rather
#: than invented, because the system defines no categorical ramp: a chart is grey
#: structure plus one orange signal.
_NEUTRAL_ROLES = ["ink", "ink-2", "mid", "surface-3"]

#: Epistemic tags, carried on every published figure via footer().
#: Tags are recessive wayfinding, set in mid grey like the numbering system.
#: The two that flag a weakness borrow the StatusDot convention and go orange,
#: which is honest but spends the accent: when a tag is orange, do not also mark
#: a KPI accent, or the figure carries two accents and reads as none.
EPISTEMIC_TAGS = {
    "VERIFIED": "mid",
    "CALIBRATED": "mid",
    "SIMULATED": "mid",
    "ASSUMED": "accent-01",
    "ILLUSTRATIVE": "accent-01",
}


def palette(name: str, n: int = None, *, reverse: bool = False) -> list[str]:
    """Return a design-system chart ramp, mode-corrected.

    ``n`` samples the ramp evenly rather than truncating it, so a 3-colour draw
    from a 9-stop sequential scale spans the whole range instead of clustering at
    the dark end.
    """
    if name not in CHART_PALETTES:
        raise KeyError(
            f"Unknown palette {name!r}. Available: {sorted(CHART_PALETTES)}"
        )
    stops = list(CHART_PALETTES[name])
    if _MODE == "dark":
        for (pal, idx), hexv in CHART_DARK_OVERRIDES.items():
            if pal == name and idx < len(stops):
                stops[idx] = hexv
    if n is not None and n != len(stops):
        if n == 1:
            stops = [stops[len(stops) // 2]]
        else:
            step = (len(stops) - 1) / (n - 1)
            stops = [stops[round(i * step)] for i in range(n)]
    return list(reversed(stops)) if reverse else stops


def neutral_ramp(n: int) -> list[str]:
    """``n`` structure greys, darkest first. Wraps if ``n`` exceeds the roles."""
    return [c(_NEUTRAL_ROLES[i % len(_NEUTRAL_ROLES)]) for i in range(n)]


def tag_color(tag: str) -> str:
    """Colour for an epistemic tag."""
    return c(EPISTEMIC_TAGS.get(str(tag).upper(), "mid"))


# ---------------------------------------------------------------------------
# 3. Typography — tokens/typography.css and tokens/fonts.css
# ---------------------------------------------------------------------------
# The system is single-family: Söhne for display and body, Söhne Mono for all
# numbering, data labels, tags and timestamps. Söhne Mono is monospaced, which
# is how the CSS rule `tabular-nums lining-nums slashed-zero` gets honoured in a
# renderer that has no OpenType feature switch.

#: Söhne German weight naming, mapped from filename stem to numeric weight.
_WEIGHT_FROM_STEM = {
    "buch": 400,
    "buchkursiv": 400,
    "kraftig": 500,
    "halbfett": 600,
    "dreiviertelfett": 700,
    "fett": 800,
    "extrafett": 900,
}

#: Fallback stacks, used only when the real files are not registered.
_FALLBACK = {
    "display": ["Söhne", "Inter", "Helvetica Neue", "Liberation Sans", "DejaVu Sans"],
    "mono": ["Söhne Mono", "SF Mono", "Menlo", "Liberation Mono", "DejaVu Sans Mono"],
}
#: Retail Söhne needs no fallback. The trial binaries do, so the stack always
#: ends in a metric-neutral grotesque rather than failing to a tofu box.

#: Resolved FontProperties per (role, weight). Populated by register_fonts().
_FP: dict[tuple[str, int], FontProperties] = {}
#: Family names as the installed files actually report them.
_FAMILY: dict[str, str | None] = {"display": None, "mono": None}
_FONT_WARNED = False

#: Type scale in points, converted from the CSS rem/clamp values at 96px/rem.
#: 2026-09-17 readability revision: chart titles, context lines, and mono labels were
#: judged too small when a figure is scaled into a README; every size below the hero
#: is raised by at least 1 pt over the CSS-derived values (shown in the comments).
SIZE = {
    "hero": 84.0,      # --t-hero        7rem
    "section": 31.0,   # --t-section     2.5rem  (was 30.0)
    "project": 20.0,   # --t-project     1.5rem  (was 18.0) — chart titles
    "lead": 16.5,      # --t-lead        1.25rem (was 15.0)
    "body": 13.8,      # --t-body        1.05rem (was 12.6) — context / subtitle lines
    "mono": 11.0,      # --t-mono        0.8rem  (was 9.6)  — labels, footer, ticks
    "mono-sm": 9.5,    # --t-mono-sm     0.6875rem (was 8.25)
    "kpi": 36.0,       # MetricGrid value, clamp(2rem, 3.5vw, 3rem)
}

WEIGHT = {
    "extrablack": 900, "black": 800, "bold": 700,
    "semibold": 600, "medium": 500, "regular": 400,
}

#: matplotlib's SVG backend resolves weights through a name table, so a numeric
#: weight raises there. This bridges the system's numbers to the names it knows.
#: Note the collision of vocabulary: the system's `--w-black` is 800, which is
#: matplotlib's "heavy"; matplotlib's "black" is 900, the system's Extrafett.
_MPL_WEIGHT = {
    400: "normal", 500: "medium", 600: "semibold",
    700: "bold", 800: "heavy", 900: "black",
}

LINE_HEIGHT = {"tight": 1.02, "snug": 1.18, "body": 1.55}


def register_fonts(path: str | Path = None) -> dict[str, str | None]:
    """Register the Söhne binaries and discover their real family names.

    Family names are read back from the installed files rather than hardcoded,
    because the trial binaries ship a mangled name-table entry and report as
    ``Test S?hne``. Hardcoding that string would break the moment the retail
    files are dropped in.

    ``path`` should point at the design system's ``assets/fonts``. When omitted,
    a few conventional locations are tried. Returns the resolved family names.
    """
    global _FONT_WARNED

    candidates = [Path(path)] if path else [
        Path("assets/fonts"), Path("../assets/fonts"),
        Path("design-system/assets/fonts"), Path.home() / ".fonts",
    ]
    root = next((p for p in candidates if p.is_dir()), None)
    if root is None:
        return dict(_FAMILY)

    files = sorted(list(root.glob("*.otf")) + list(root.glob("*.ttf")))
    for f in files:
        stem = f.stem
        if not stem.lower().startswith("sohne"):
            continue
        role = "mono" if "mono" in stem.lower() else "display"
        suffix = re.sub(r"^sohnemono-|^sohne-", "", stem.lower())
        weight = _WEIGHT_FROM_STEM.get(suffix)
        if weight is None or "kursiv" in suffix:
            continue
        fontManager.addfont(str(f))
        _FP[(role, weight)] = str(f)
        if _FAMILY[role] is None:
            _FAMILY[role] = FontProperties(fname=str(f)).get_name()

    if not _FP and not _FONT_WARNED:
        warnings.warn(
            f"bk_theme: no Söhne files found under {root}. Charts will render in "
            "a fallback face and will not match the design system.",
            stacklevel=2,
        )
        _FONT_WARNED = True
    return dict(_FAMILY)


def font(role: str = "display", weight: int | str = 400,
         size: float | str = None) -> FontProperties:
    """Return FontProperties for a role and weight.

    ``role`` is ``"display"`` or ``"mono"``. ``weight`` accepts a number or a
    name from :data:`WEIGHT`. ``size`` accepts points or a key from :data:`SIZE`.

    Returns a family *list*, not a file path, so matplotlib falls back per glyph.
    That matters here: the bundled trial Söhne binaries carry 68 glyphs and have
    no ``%``, ``+``, euro sign, parentheses, slash, colon or arrows. Bound to a
    file path there is no fallback chain and those characters render as tofu.
    """
    w = WEIGHT.get(weight, weight) if isinstance(weight, str) else weight
    if isinstance(size, str):
        size = SIZE[size]

    stack = ([_FAMILY[role]] if _FAMILY[role] else []) + _FALLBACK[role]
    fp = FontProperties(family=stack, weight=_MPL_WEIGHT.get(w, "normal"))
    if size is not None:
        fp.set_size(size)
    return fp


def check_glyphs(fig: Figure, *, raise_on_missing: bool = False) -> list[str]:
    """Report characters in the figure the installed Söhne files cannot render.

    Silent per-glyph fallback is convenient and dishonest: a chart can look fine
    while every percent sign is set in a different typeface. This walks every
    text artist and names the gaps, so mixing faces is a decision rather than an
    accident. Called automatically by :func:`save`.
    """
    if not _FP:
        return []
    try:
        from fontTools.ttLib import TTFont
    except ImportError:
        return []

    covered: set[int] = set()
    for path in set(_FP.values()):
        try:
            covered |= set(TTFont(path).getBestCmap().keys())
        except Exception:
            continue
    if not covered:
        return []

    texts = list(fig.texts)
    for ax in fig.axes:
        texts += [ax.title, ax.xaxis.label, ax.yaxis.label]
        texts += list(ax.texts) + list(ax.get_xticklabels()) + list(ax.get_yticklabels())

    gaps = sorted({
        ch for t in texts for ch in (t.get_text() or "")
        if ch.strip() and ord(ch) not in covered
    })
    if gaps:
        msg = (
            "bk_theme: these characters are not in the installed Söhne files: "
            + " ".join(gaps)
            + ". They render from the fallback face, so this figure mixes "
            "typefaces. The bundled trial binaries carry 68 glyphs only; "
            "licensed retail Söhne covers them."
        )
        if raise_on_missing:
            raise ValueError(msg)
        warnings.warn(msg, stacklevel=2)
    return gaps


# ---------------------------------------------------------------------------
# 4. Layout — tokens/spacing.css and tokens/grid.css
# ---------------------------------------------------------------------------

PAGE_MAX_PX = 1320
PAGE_GUTTER_PX = 64        # --gutter, upper bound of the clamp
GRID_GUTTER_PX = 24        # --grid-gutter, upper bound of the clamp
GRID_COLS = 12
PX_PER_IN = 96

CONTENT_PX = PAGE_MAX_PX - 2 * PAGE_GUTTER_PX                       # 1192
COL_PX = (CONTENT_PX - (GRID_COLS - 1) * GRID_GUTTER_PX) / GRID_COLS  # 77.33

#: 8px base grid with 4px half-steps, in points, for figure-space maths.
SPACE_PX = {0: 0, "h": 4, 1: 8, 2: 16, 3: 24, 4: 32, 5: 40,
            6: 48, 8: 64, 10: 80, 12: 96, 16: 128, 20: 160}

HAIRLINE_PT = 1 * 72 / PX_PER_IN   # 1 CSS px expressed in points
EASE = (0.2, 0, 0, 1)              # --ease, for any consumer that animates
DUR_MS = 140                       # --dur

TOKENS = {
    "raw": RAW,
    "color": COLOR,
    "chart_palettes": CHART_PALETTES,
    "chart_dark_overrides": {f"{k[0]}-{k[1]}": v
                             for k, v in CHART_DARK_OVERRIDES.items()},
    "epistemic": EPISTEMIC_TAGS,
    "type_scale_pt": SIZE,
    "weights": WEIGHT,
    "line_height": LINE_HEIGHT,
    "spacing_px": SPACE_PX,
    "layout": {
        "page_max_px": PAGE_MAX_PX,
        "page_gutter_px": PAGE_GUTTER_PX,
        "grid_cols": GRID_COLS,
        "grid_gutter_px": GRID_GUTTER_PX,
        "column_px": round(COL_PX, 3),
        "measure_ch": 72,
        "radius_px": [0, 2],
    },
    "motion": {"ease": list(EASE), "duration_ms": DUR_MS},
}


def figsize(cols: int = 12, rows: float = 6) -> tuple[float, float]:
    """Convert a column span into inches using the real 12-column page maths.

    A 12-column figure is exactly the page content width, so a full-bleed chart
    lands pixel-aligned with the site's grid at 1x.
    """
    def span(n):
        return (n * COL_PX + (n - 1) * GRID_GUTTER_PX) / PX_PER_IN
    return (span(cols), span(rows))


# ---------------------------------------------------------------------------
# 5. Theme application
# ---------------------------------------------------------------------------

def _prune_fallbacks() -> None:
    """Drop fallback families that are not installed.

    matplotlib's per-glyph fallback walks the family list; a name that resolves
    to nothing can end the walk early and leave a tofu box where a fallback
    should have been. Pruning keeps the chain honest.
    """
    installed = {e.name for e in fontManager.ttflist}
    for role, stack in _FALLBACK.items():
        kept = [f for f in stack if f in installed]
        _FALLBACK[role] = kept or stack[-1:]


def apply(theme: str = "light", *, scale: float = 1.0, grid: str = "y",
          fonts: str | Path = None) -> None:
    """Install the design system as matplotlib rcParams.

    ``theme`` is ``"light"`` or ``"dark"``. ``fonts`` optionally points at the
    Söhne directory and calls :func:`register_fonts` for you.

    Defaults are set to the mono face at label size, because in this system every
    axis tick, data label and tag is mono. Display type is applied explicitly by
    the helpers that need it.
    """
    global _MODE
    if theme not in COLOR:
        raise ValueError(f"theme must be 'light' or 'dark', got {theme!r}")
    _MODE = theme

    if fonts is not None or not _FP:
        register_fonts(fonts)

    _prune_fallbacks()
    mono_family = [_FAMILY["mono"]] if _FAMILY["mono"] else []
    disp_family = [_FAMILY["display"]] if _FAMILY["display"] else []

    mpl.rcParams.update({
        # --- typography: mono is the default because labels are mono ------
        "font.family": "monospace",
        "font.monospace": mono_family + _FALLBACK["mono"],
        "font.sans-serif": disp_family + _FALLBACK["display"],
        "font.size": SIZE["mono"] * scale,
        "axes.labelsize": SIZE["mono"] * scale,
        "xtick.labelsize": SIZE["mono"] * scale,
        "ytick.labelsize": SIZE["mono"] * scale,
        "legend.fontsize": SIZE["mono"] * scale,
        "axes.titlesize": SIZE["project"] * scale,
        "axes.titleweight": _MPL_WEIGHT[WEIGHT["black"]],
        "axes.titlelocation": "left",
        "axes.titlepad": SPACE_PX[2] * 72 / PX_PER_IN,
        "axes.labelpad": SPACE_PX[1] * 72 / PX_PER_IN,

        # --- colour: flat surfaces, no white ------------------------------
        "figure.facecolor": c("surface"),
        "axes.facecolor": c("surface"),
        "savefig.facecolor": c("surface"),
        "savefig.edgecolor": c("surface"),
        "text.color": c("ink"),
        "axes.labelcolor": c("ink-2"),
        "axes.titlecolor": c("ink"),
        "xtick.color": c("mid"),
        "ytick.color": c("mid"),
        "xtick.labelcolor": c("ink-2"),
        "ytick.labelcolor": c("ink-2"),
        "axes.prop_cycle": mpl.cycler(color=neutral_ramp(4)),

        # --- hairlines as structure ---------------------------------------
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.spines.left": True,
        "axes.spines.bottom": True,
        "axes.edgecolor": c("mid"),
        "axes.linewidth": HAIRLINE_PT,
        "xtick.major.size": 0,
        "ytick.major.size": 0,
        "xtick.minor.size": 0,
        "ytick.minor.size": 0,
        "xtick.major.pad": SPACE_PX[1] * 72 / PX_PER_IN,
        "ytick.major.pad": SPACE_PX[1] * 72 / PX_PER_IN,

        "axes.grid": grid != "none",
        "axes.grid.axis": grid if grid in ("x", "y", "both") else "y",
        "grid.color": c("surface-3"),
        "grid.linewidth": HAIRLINE_PT,
        "grid.alpha": 1.0,          # opaque and flat, never alpha
        "axes.axisbelow": True,

        # --- marks: square, no decoration ---------------------------------
        "lines.linewidth": 1.75,
        "lines.solid_capstyle": "butt",
        "lines.markersize": 4,
        "patch.linewidth": 0,
        "patch.force_edgecolor": False,
        "errorbar.capsize": 0,

        # --- legend: present but discouraged; prefer direct labels --------
        "legend.frameon": False,
        "legend.handlelength": 1.0,
        "legend.borderpad": 0.0,

        # --- output --------------------------------------------------------
        "figure.dpi": PX_PER_IN,
        "savefig.dpi": 2 * PX_PER_IN,
        "savefig.bbox": None,       # geometry is explicit; do not re-crop
        "svg.fonttype": "none",     # reference by name, do not embed
        "pdf.fonttype": 42,
    })


# ---------------------------------------------------------------------------
# 6. Figure construction
# ---------------------------------------------------------------------------

def new_figure(cols: int = 12, rows: float = 6, *, nrows: int = 1,
               ncols: int = 1, **kwargs):
    """``plt.subplots`` sized on the 12-column grid."""
    kwargs.setdefault("figsize", figsize(cols, rows))
    kwargs.setdefault("constrained_layout", True)
    return plt.subplots(nrows=nrows, ncols=ncols, **kwargs)


def decision_panel(*, kpis: Sequence[Mapping] = (), finding: str = "",
                   context: str = "", cols: int = 12, rows: float = 8,
                   left: float = 0.06, right: float = 0.02,
                   bottom: float = 0.16):
    """The executive one-pager: metric row, finding, chart, provenance strip.

    Band heights are computed in inches from the 8px spacing scale and converted,
    so the layout holds at any figure size and the bands never collide.

    ``kpis`` items take ``label``, ``value``, optional ``note`` and optional
    ``accent``. Set ``accent`` on at most one, per the system's rule that a
    single impact number earns the orange.

    Returns ``(fig, ax)``. Call :func:`footer` afterwards.
    """
    w_in, h_in = figsize(cols, rows)
    fig = plt.figure(figsize=(w_in, h_in))

    def px(v):
        return v / PX_PER_IN / h_in

    span = 1.0 - left - right
    span_px = span * w_in * PX_PER_IN
    n_kpi = len(kpis)
    col_px = ((span - GRID_GUTTER_PX / PX_PER_IN / w_in * (n_kpi - 1)) / n_kpi * w_in * PX_PER_IN - SPACE_PX[1]) if n_kpi else span_px
    kpi_h = px(kpi_band_px(_kpi_note_lines(kpis, col_px))) if kpis else 0.0
    gap = px(SPACE_PX[4])
    title_fp = font("display", "black", "project")
    ctx_fp = font("display", "regular", "body")
    finding_wrapped = wrap_to_px(finding, title_fp, span_px) if finding else ""
    context_wrapped = wrap_to_px(context, ctx_fp, span_px) if context else ""
    title_lines = finding_wrapped.count("\n") + 1 if finding else 0
    ctx_lines = context_wrapped.count("\n") + 1 if context else 0
    title_h = px(SIZE["project"] * PX_PER_IN / 72 * LINE_HEIGHT["snug"] * title_lines) if finding else 0.0
    ctx_h = px(SPACE_PX[2] + SIZE["body"] * PX_PER_IN / 72 * 1.15 * ctx_lines) if context else 0.0

    top_used = kpi_h + (gap if kpis else 0.0) + title_h + ctx_h + (gap if finding or context else 0.0)
    ax_height = 1.0 - top_used - bottom
    if ax_height <= 0.15:
        raise ValueError(
            "decision_panel: not enough vertical room. Increase `rows`, or drop "
            "the context line."
        )

    ax = fig.add_axes([left, bottom, 1.0 - left - right, ax_height])

    if kpis:
        kpi_row(fig, kpis, top=1.0, height=kpi_h, left=left, right=right)

    y = 1.0 - kpi_h - (gap if kpis else 0.0)
    if finding:
        fig.text(left, y, finding_wrapped, ha="left", va="top", color=c("ink"),
                 linespacing=LINE_HEIGHT["snug"], fontproperties=title_fp)
        y -= title_h
    if context:
        fig.text(left, y - px(SPACE_PX[2]), context_wrapped, ha="left", va="top",
                 color=c("ink-2"), linespacing=1.15, fontproperties=ctx_fp)

    return fig, ax


# ---------------------------------------------------------------------------
# 7. Colour assignment
# ---------------------------------------------------------------------------

def highlight_palette(labels: Sequence, highlight=None, *,
                      base: str = "ink-2", accent: str = "accent-01") -> list[str]:
    """Structure grey for everything, orange for the one thing that earned it.

    ``highlight`` may be a label or an index. Passing more than one warns: the
    system spends the accent on a single impact figure, and two accents read as
    none.
    """
    labels = list(labels)
    if highlight is None:
        targets: set = set()
    elif isinstance(highlight, (str, bytes, int)) or not hasattr(highlight, "__iter__"):
        targets = {highlight}
    else:
        targets = set(highlight)
        if len(targets) > 1:
            warnings.warn(
                "bk_theme: more than one highlight requested. The design system "
                "spends --accent-01 on a single impact figure; two accents read "
                "as none. Consider ordering the chart so the winner is obvious "
                "instead.",
                stacklevel=2,
            )

    return [c(accent) if (lab in targets or i in targets) else c(base)
            for i, lab in enumerate(labels)]


# ---------------------------------------------------------------------------
# 8. Annotation
# ---------------------------------------------------------------------------

def _contrast_ink(facecolor) -> str:
    """Ink or surface, whichever is readable on ``facecolor``."""
    r, g, b = mpl.colors.to_rgb(facecolor)

    def lin(x):
        return x / 12.92 if x <= 0.04045 else ((x + 0.055) / 1.055) ** 2.4

    lum = 0.2126 * lin(r) + 0.7152 * lin(g) + 0.0722 * lin(b)
    return c("ink") if lum > 0.42 else c("surface")


def finding_title(ax: Axes, finding: str, context: str = None) -> None:
    """Headline states the conclusion; the line under it states the variable.

    Use on a bare axes. :func:`decision_panel` already does this at figure level.
    """
    ax.set_title(finding, loc="left", color=c("ink"),
                 fontproperties=font("display", "black", "project"))
    if context:
        ax.annotate(context, xy=(0, 1), xycoords="axes fraction",
                    xytext=(0, SPACE_PX[1]), textcoords="offset points",
                    ha="left", va="bottom", color=c("ink-2"),
                    fontproperties=font("display", "regular", "body"))


def text_width_px(text: str, fp) -> float:
    """Rendered width of ``text`` in CSS px for FontProperties ``fp`` (no renderer needed)."""
    from matplotlib.textpath import TextPath
    if not text:
        return 0.0
    return TextPath((0, 0), text, prop=fp).get_extents().width * PX_PER_IN / 72


def wrap_to_px(text: str, fp, max_px: float) -> str:
    """Greedy word wrap so no line is wider than ``max_px`` at ``fp``.

    Added in the 2026-09-17 readability revision: larger body and note sizes must
    not collide with the next KPI column or run past the figure edge, so the
    context line, KPI notes, and the footer note are measured and wrapped.
    """
    words = str(text).split()
    lines: list[str] = []
    cur: list[str] = []
    for w in words:
        trial = " ".join(cur + [w])
        if not cur or text_width_px(trial, fp) <= max_px:
            cur.append(w)
        else:
            lines.append(" ".join(cur))
            cur = [w]
    if cur:
        lines.append(" ".join(cur))
    return "\n".join(lines)


def _kpi_note_lines(kpis, col_px: float) -> int:
    fp = font("display", "regular", "body")
    return max([wrap_to_px(k["note"], fp, col_px).count("\n") + 1 for k in kpis if k.get("note")] or [1])


#: Vertical rhythm of one MetricGrid cell, in CSS px from the top rule.
KPI_BAND_PX = {
    "label_top": SPACE_PX[3],                                    # 24
    "value_top": SPACE_PX[3] + SIZE["mono"] * PX_PER_IN / 72 + SPACE_PX[2],
    "note_gap": SPACE_PX[1],
    "pad_bottom": SPACE_PX[3],
}


def kpi_band_px(note_lines: int = 1) -> float:
    """Total height of a MetricGrid band in CSS px, rules included."""
    return (KPI_BAND_PX["value_top"] + SIZE["kpi"] * PX_PER_IN / 72
            + KPI_BAND_PX["note_gap"]
            + SIZE["body"] * PX_PER_IN / 72 * 1.15 * max(1, note_lines)
            + KPI_BAND_PX["pad_bottom"])


def kpi_row(fig: Figure, kpis: Sequence[Mapping], *, top: float = 1.0,
            height: float = None, left: float = 0.06,
            right: float = 0.02) -> None:
    """A MetricGrid in figure space: hairline rules, mono label, big figure.

    No fill and no box. The system defines a card by a hairline or a surface-2
    wash, never by shadow or rounding, and MetricGrid uses rules top and bottom.
    Positions come from a pixel cursor on the 8px spacing scale, so the label,
    the figure and the note cannot collide at any figure size.
    """
    n = len(kpis)
    if n == 0:
        return

    fig_h_in = fig.get_size_inches()[1]
    fig_w_in = fig.get_size_inches()[0]

    def dy(px_from_top: float) -> float:
        return top - px_from_top / PX_PER_IN / fig_h_in

    span = 1.0 - left - right
    gutter = GRID_GUTTER_PX / PX_PER_IN / fig_w_in
    width = (span - gutter * (n - 1)) / n
    col_px = width * fig_w_in * PX_PER_IN - SPACE_PX[1]
    note_fp = font("display", "regular", "body")

    if height is None:
        height = kpi_band_px(_kpi_note_lines(kpis, col_px)) / PX_PER_IN / fig_h_in

    if sum(1 for k in kpis if k.get("accent")) > 1:
        warnings.warn(
            "bk_theme: more than one KPI marked accent. MetricGrid allows the "
            "orange on at most one metric, the single impact number.",
            stacklevel=2,
        )

    def rule(x0, x1, y):
        fig.add_artist(mpl.lines.Line2D(
            [x0, x1], [y, y], transform=fig.transFigure, color=c("mid"),
            linewidth=HAIRLINE_PT, clip_on=False, zorder=3))

    rule(left, left + span, top)

    for i, kpi in enumerate(kpis):
        x0 = left + i * (width + gutter)
        rule(x0, x0 + width, top - height)

        fig.text(x0, dy(KPI_BAND_PX["label_top"]), str(kpi["label"]).upper(),
                 ha="left", va="top", color=c("ink-2"),
                 fontproperties=font("mono", "regular", "mono"))

        fig.text(x0, dy(KPI_BAND_PX["value_top"]), str(kpi["value"]),
                 ha="left", va="top",
                 color=c("accent-01") if kpi.get("accent") else c("ink"),
                 fontproperties=font("display", "black", "kpi"))

        if kpi.get("note"):
            note_top = (KPI_BAND_PX["value_top"] + SIZE["kpi"] * PX_PER_IN / 72
                        + KPI_BAND_PX["note_gap"])
            fig.text(x0, dy(note_top), wrap_to_px(kpi["note"], note_fp, col_px),
                     ha="left", va="top", color=c("ink-2"),
                     linespacing=1.15, fontproperties=note_fp)


def footer(fig: Figure, *, source: str, run_id: str = None, tag: str = None,
           note: str = None, number: str = None, left: float = 0.06,
           right: float = 0.02, y: float = 0.055) -> None:
    """Provenance strip: hairline rule, source and run, epistemic tag, note.

    ``number`` takes a numbering-system reference such as ``"02-04-03"``, set in
    mono mid grey as recessive wayfinding.
    """
    span = 1.0 - left - right
    fig_w_in, fig_h_in = fig.get_size_inches()
    fig_h_px = fig_h_in * PX_PER_IN
    wrapped = ""
    note_y = None
    if note:
        note_fp = font("display", "regular", "body")
        wrapped = wrap_to_px(note, note_fp, span * fig_w_in * PX_PER_IN)
        note_h_px = SIZE["body"] * PX_PER_IN / 72 * 1.15 * (wrapped.count("\n") + 1)
        note_y = y - (SIZE["mono"] * PX_PER_IN / 72 + SPACE_PX[1]) / fig_h_px
        # keep the whole note inside the canvas; when it would fall below the edge,
        # the strip, its rule, and the note all move up together
        floor = (SPACE_PX[1] + note_h_px) / fig_h_px
        if note_y < floor:
            y += floor - note_y
            note_y = floor

    fig.add_artist(mpl.lines.Line2D(
        [left, left + span], [y + 0.028, y + 0.028], transform=fig.transFigure,
        color=c("mid"), linewidth=HAIRLINE_PT, clip_on=False, zorder=3))

    bits = []
    if number:
        bits.append(number)
    bits.append(f"SOURCE {source}")
    if run_id:
        bits.append(f"RUN {run_id}")

    fig.text(left, y, "   ·   ".join(bits).upper(), ha="left", va="top",
             color=c("ink-2"), fontproperties=font("mono", "regular", "mono"))

    if tag:
        fig.text(left + span, y, str(tag).upper(), ha="right", va="top",
                 color=tag_color(tag),
                 fontproperties=font("mono", "semibold", "mono"))

    if note:
        fig.text(left, note_y, wrapped, ha="left", va="top",
                 color=c("ink-2"), linespacing=1.15, fontproperties=note_fp)


def direct_label(ax: Axes, x, y, text: str, *, color: str = None,
                 dx: int = 8, dy: int = 0, role: str = "mono",
                 weight: str = "medium", size: str = "mono",
                 ha: str = "left", va: str = "center") -> None:
    """Label a series at its endpoint instead of adding a legend entry."""
    ax.annotate(text, xy=(x, y), xytext=(dx, dy), textcoords="offset points",
                ha=ha, va=va, color=color or c("ink"),
                fontproperties=font(role, weight, size), annotation_clip=False)


def value_labels(ax: Axes, *, orient: str = "v",
                 fmt: Callable[[float], str] = None,
                 inside_threshold: float = 0.72, pad: int = 8) -> None:
    """Write each bar's value at its end, in mono so the figures stay tabular."""
    fmt = fmt or (lambda v: f"{v:,.0f}")
    containers = [c_ for c_ in ax.containers if hasattr(c_, "patches")]
    if not containers:
        return

    vals = [(p.get_width() if orient == "h" else p.get_height())
            for cont in containers for p in cont.patches]
    span = max(abs(v) for v in vals) or 1.0
    fp = font("mono", "semibold", "mono")

    for cont in containers:
        for patch in cont.patches:
            ink = _contrast_ink(patch.get_facecolor())
            v = patch.get_width() if orient == "h" else patch.get_height()
            inside = abs(v) / span >= inside_threshold
            sign = 1 if v >= 0 else -1
            off = (-pad * sign, 0) if inside else (pad * sign, 0)
            if orient == "h":
                anchor = (v, patch.get_y() + patch.get_height() / 2)
                if inside:
                    ha = "right" if v >= 0 else "left"
                else:
                    ha = "left" if v >= 0 else "right"
                va = "center"
            else:
                anchor = (patch.get_x() + patch.get_width() / 2, v)
                off = (0, -pad * sign) if inside else (0, pad * sign)
                ha = "center"
                if inside:
                    va = "top" if v >= 0 else "bottom"
                else:
                    va = "bottom" if v >= 0 else "top"
            ax.annotate(fmt(v), xy=anchor, xytext=off, textcoords="offset points",
                        ha=ha, va=va, fontproperties=fp,
                        color=ink if inside else c("ink"))


def reference_line(ax: Axes, value: float, label: str = None, *,
                   orient: str = "h", color: str = None) -> None:
    """A baseline or threshold, drawn as a hairline and labelled in place."""
    col = color or c("mid")
    fp = font("mono", "regular", "mono-sm")
    if orient == "h":
        ax.axhline(value, color=col, lw=HAIRLINE_PT, ls=(0, (3, 3)), zorder=1)
        if label:
            ax.annotate(label.upper(), xy=(1.0, value),
                        xycoords=("axes fraction", "data"),
                        xytext=(-4, 5), textcoords="offset points",
                        ha="right", va="bottom", color=col, fontproperties=fp)
    else:
        ax.axvline(value, color=col, lw=HAIRLINE_PT, ls=(0, (3, 3)), zorder=1)
        if label:
            ax.annotate(label.upper(), xy=(value, 1.0),
                        xycoords=("data", "axes fraction"),
                        xytext=(6, -4), textcoords="offset points",
                        ha="left", va="top", color=col, fontproperties=fp)


def annotate_delta(ax: Axes, x, y_from: float, y_to: float, text: str, *,
                   color: str = None) -> None:
    """Bracket the gap between two values and name it. The delta is the decision."""
    col = color or c("accent-01")
    ax.annotate("", xy=(x, y_to), xytext=(x, y_from),
                arrowprops=dict(arrowstyle="<->", color=col,
                                lw=HAIRLINE_PT * 1.5, shrinkA=0, shrinkB=0))
    ax.annotate(text, xy=(x, (y_from + y_to) / 2), xytext=(SPACE_PX[1], 0),
                textcoords="offset points", ha="left", va="center", color=col,
                fontproperties=font("mono", "semibold", "mono"))


# ---------------------------------------------------------------------------
# 9. Number formatting
# ---------------------------------------------------------------------------

def fmt_eur(v: float) -> str:
    return f"EUR {v:,.0f}" if v >= 0 else f"-EUR {abs(v):,.0f}"


def fmt_eur_k(v: float) -> str:
    s = f"EUR {abs(v) / 1_000:,.0f}k"
    return s if v >= 0 else "-" + s


def fmt_eur_m(v: float, decimals: int = 2) -> str:
    s = f"EUR {abs(v) / 1_000_000:,.{decimals}f}M"
    return s if v >= 0 else "-" + s


def fmt_pct(v: float, decimals: int = 1) -> str:
    """``v`` as a fraction: 0.0615 renders as 6.2%."""
    return f"{v * 100:.{decimals}f}%"


def fmt_pp(v: float, decimals: int = 2) -> str:
    """Percentage points, always signed."""
    return f"{v:+.{decimals}f} pp"


def fmt_months(v: float) -> str:
    return f"{v:.0f} mo" if v >= 1 else f"{v * 30:.0f} d"


def fmt_int(v: float) -> str:
    return f"{v:,.0f}"


def money_axis(ax: Axes, axis: str = "y", unit: str = "k",
               nbins: int = 5) -> None:
    """Euro formatting on an axis. ``nbins`` caps ticks; five is usually enough."""
    f = {"": fmt_eur, "k": fmt_eur_k, "M": fmt_eur_m}[unit]
    target = ax.yaxis if axis == "y" else ax.xaxis
    target.set_major_formatter(FuncFormatter(lambda v, _: f(v)))
    if nbins:
        target.set_major_locator(MaxNLocator(nbins=nbins))


def pct_axis(ax: Axes, axis: str = "y", decimals: int = 0,
             nbins: int = 5) -> None:
    target = ax.yaxis if axis == "y" else ax.xaxis
    target.set_major_formatter(FuncFormatter(lambda v, _: fmt_pct(v, decimals)))
    if nbins:
        target.set_major_locator(MaxNLocator(nbins=nbins))


# ---------------------------------------------------------------------------
# 10. Chrome and output
# ---------------------------------------------------------------------------

def strip_chrome(ax: Axes, keep: Sequence[str] = ("left", "bottom"),
                 *, ticks: bool = True) -> None:
    """Keep only the hairlines that carry structure; drop tick marks."""
    for side in ("top", "right", "bottom", "left"):
        ax.spines[side].set_visible(side in keep)
        ax.spines[side].set_color(c("mid"))
        ax.spines[side].set_linewidth(HAIRLINE_PT)
    if ticks:
        ax.tick_params(length=0)
    fp = font("mono", "regular", "mono")
    for lab in list(ax.get_xticklabels()) + list(ax.get_yticklabels()):
        lab.set_fontproperties(fp)


def save(fig: Figure, path: str | Path, *, formats: Sequence[str] = ("png", "svg"),
         dpi: int = None, close: bool = True, allow_pdf: bool = False) -> list[Path]:
    """Write the figure once per format. ``path`` is given without an extension.

    PDF is refused unless ``allow_pdf`` is set, because PDF export embeds the
    font and the bundled Söhne files are Klim trial weights. Enable it once
    retail Söhne is licensed.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    check_glyphs(fig)
    written = []
    for ext in formats:
        if ext.lower() == "pdf" and not allow_pdf:
            raise ValueError(
                "PDF export embeds the typeface, and the bundled Söhne files are "
                "Klim trial weights licensed for evaluation only. Pass "
                "allow_pdf=True once retail Söhne is licensed."
            )
        target = path.with_suffix(f".{ext}")
        fig.savefig(target, dpi=dpi or mpl.rcParams["savefig.dpi"],
                    facecolor=c("surface"))
        written.append(target)
    if close:
        plt.close(fig)
    return written


def dump_tokens(path: str | Path = "bk_tokens.json") -> Path:
    """Export the mirrored token set as JSON.

    Feed it to a Tableau custom palette, a Power BI theme file, or any surface
    that has to match these charts without reading CSS.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(TOKENS, indent=2) + "\n", encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# 11. Optional plotly parity, for the Streamlit dashboards
# ---------------------------------------------------------------------------

def plotly_template(register_as: str = "bk", set_default: bool = True):
    """Build and register the equivalent plotly template. Requires plotly."""
    try:
        import plotly.graph_objects as go
        import plotly.io as pio
    except ImportError as exc:  # pragma: no cover
        raise ImportError(
            "bk_theme.plotly_template() needs plotly. Install it, or stay on "
            "matplotlib."
        ) from exc

    disp = ", ".join(([_FAMILY["display"]] if _FAMILY["display"] else []) + _FALLBACK["display"])
    mono = ", ".join(([_FAMILY["mono"]] if _FAMILY["mono"] else []) + _FALLBACK["mono"])

    axis = dict(showgrid=True, gridcolor=c("surface-3"), gridwidth=1,
                zeroline=False, linecolor=c("mid"), linewidth=1, ticks="",
                tickfont=dict(family=mono, size=13, color=c("ink-2")),
                title=dict(font=dict(family=mono, size=13, color=c("mid"))))

    tpl = go.layout.Template(layout=dict(
        font=dict(family=disp, size=16, color=c("ink")),
        title=dict(x=0.0, xanchor="left",
                   font=dict(family=disp, size=24, color=c("ink"))),
        paper_bgcolor=c("surface"),
        plot_bgcolor=c("surface"),
        colorway=neutral_ramp(4),
        margin=dict(l=64, r=32, t=72, b=56),
        xaxis={**axis, "showgrid": False},
        yaxis=axis,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left",
                    x=0, bgcolor="rgba(0,0,0,0)", borderwidth=0),
        hoverlabel=dict(bgcolor=c("ink"), bordercolor=c("ink"),
                        font=dict(family=mono, color=c("surface"))),
    ))
    pio.templates[register_as] = tpl
    if set_default:
        pio.templates.default = register_as
    return tpl
