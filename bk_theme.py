"""
bk_theme
========

The Braga design system (v2.1), applied to charts.

Every value comes from the design system of record, braga-portfolio-v2
`design-system/tokens.json` (a snapshot ships in `bk_design/`; a sibling
checkout or `BRAGA_DS` wins). The chart rules are D-015, D-016, D-017, D-018,
D-033, D-036 and D-053 in its `DECISIONS.md`. Nothing is invented here: this
module is a mirror, not a second opinion.

The non-negotiables it enforces
-------------------------------
1. **Flat and opaque.** Surface colours only, no gradients, no shadow, no alpha
   tricks. Recessive elements use a lighter *token*, never transparency.
2. **Hairlines are structure.** Axes 1px `mid`, gridlines 1px `rule-c`.
3. **IBCS is the only notation.** Actual `sc-ac`, previous year `sc-py`, plan
   `sc-pl` (outline); good variance `var-pos`, bad variance `var-neg` with ▲.
4. **One highlight per chart.** `hl` (= the ultramarine accent) marks the one
   mark or figure that earned it. Passing more than one highlight warns.
5. **Colour lives in marks, never in type.** Labels are `ink` or `ink-2`; the
   only exception is the one earned KPI figure, which may take the accent.
6. **Figures are tabular.** All numbering, data labels and tags are set in
   BKribitz Mono, tabular with a slashed zero by construction.
7. **Square corners, no radius; no text below 12px.**
8. **Every published figure carries provenance.** `footer()` stamps the source
   rows, run id and epistemic tag.

Usage
-----
    import bk_theme as bk

    bk.apply("light")                     # registers the bundled BKribitz faces

    fig, ax = bk.decision_panel(
        kpis=[{"label": "5-YEAR SAVING", "value": "EUR 684k",
               "note": "net present value, 8% discount", "accent": True}],
        finding="Hybrid + AMR is EUR 684k cheaper than staying all-human",
        context="5-year TCO by workforce scenario, 8% discount rate.",
    )

Font licence note
-----------------
BKribitz and BKribitz Mono are modified Geist cuts under SIL OFL 1.1; the
licence and notice ship in `bk_design/fonts/`. PNG, SVG and PDF are all allowed.
"""

from __future__ import annotations

import json
import logging
import os
import re
import warnings
from pathlib import Path
from typing import Callable, Iterable, Mapping, NamedTuple, Sequence

import matplotlib as mpl
import matplotlib.pyplot as plt
from matplotlib.axes import Axes
from matplotlib.colors import (
    BoundaryNorm, LinearSegmentedColormap, ListedColormap, Normalize, TwoSlopeNorm,
)
from matplotlib.figure import Figure
from matplotlib.font_manager import FontProperties, fontManager
from matplotlib.ticker import FuncFormatter, MaxNLocator

__all__ = [
    "TOKENS", "CHART_TOKENS", "DS_VERSION", "COLOR", "CHART_PALETTES", "SCALES", "EPISTEMIC_TAGS",
    "register_fonts", "apply", "mode", "c", "font",
    "figsize", "new_figure", "decision_panel",
    "highlight_palette", "neutral_ramp", "palette", "fill_scale", "FillScale", "tag_color",
    "variance_color", "variance_label",
    "finding_title", "footer", "direct_label", "value_labels", "kpi_row",
    "strip_chrome", "reference_line", "annotate_delta", "check_glyphs",
    "fmt_eur", "fmt_eur_k", "fmt_eur_m", "fmt_pct", "fmt_pp",
    "fmt_months", "fmt_int", "money_axis", "pct_axis",
    "save", "dump_tokens", "plotly_template",
]

# ---------------------------------------------------------------------------
# 1. Colour — braga-portfolio-v2 design-system/tokens.json (v2.1)
# ---------------------------------------------------------------------------
# The design system of record lives in braga-portfolio-v2 `design-system/`.
# Its `tokens.json` is `tokens.css` resolved to plain values; this package
# vendors a snapshot of it in `bk_design/tokens.json` (`BRAGA_DS` or a sibling
# braga-portfolio-v2 checkout wins, so a token change there reaches the charts
# without a release). Nothing in this module carries its own hex value.

_HERE = Path(__file__).resolve().parent
_DESIGN = _HERE / "bk_design"


def _ds_tokens_path() -> Path:
    cands = [os.environ.get("BRAGA_DS"), _HERE.parent / "braga-portfolio-v2"]
    for cand in cands:
        if not cand:
            continue
        p = Path(cand)
        if p.name == "design-system":
            p = p.parent
        if (p / "design-system" / "tokens.json").is_file():
            return p / "design-system" / "tokens.json"
    return _DESIGN / "tokens.json"


#: The design-system tokens this module renders with.
TOKENS = json.loads(_ds_tokens_path().read_text(encoding="utf-8"))
DS_VERSION = TOKENS.get("version", "?")

_ROLES = ("surface", "surface-2", "surface-3", "ink", "ink-2", "ink-3", "mid",
          "rule-c", "edge", "accent-01", "on-accent")


def _theme(m: str) -> dict:
    t = TOKENS["color"][m]
    roles = {k: t[k] for k in _ROLES}
    roles.update(t["ibcs"])   # sc-ac sc-py sc-pl var-pos var-neg var-*-tint alert hl hl-6..8
    for i, v in enumerate(t["categorical"], 1):
        roles[f"cat-{i}"] = v
    for i, v in enumerate(t["on-categorical"], 1):
        roles[f"on-cat-{i}"] = v
    roles["cat-other"] = t["categorical-other"]
    for i, v in enumerate(t["categorical-grey"], 1):
        roles[f"catg-{i}"] = v
    return roles


#: Semantic roles per mode (D-006 neutrals, D-004 ultramarine accent, D-015/D-033
#: IBCS roles, D-018/D-033 categorical slots). Light is the default.
COLOR = {"light": _theme("light"), "dark": _theme("dark")}

#: Roles retired in v2: the v1 "moment" blue (D-005) and anything orange.
_RETIRED = {"accent-02": "retired in v2 (D-005): use the `.dark` inversion, or `hl` for the one highlight"}

_MODE = "light"


def mode() -> str:
    """Current render mode, ``"light"`` or ``"dark"``."""
    return _MODE


def c(role: str) -> str:
    """Resolve a semantic colour role in the current mode.

    ``c("ink")``, ``c("hl")``, ``c("var-neg")``, ``c("cat-2")``. Use this instead
    of a hex literal anywhere in project code; the system's own lint forbids raw hex.
    """
    if role in _RETIRED:
        raise KeyError(f"Colour role {role!r} is {_RETIRED[role]}")
    try:
        return COLOR[_MODE][role]
    except KeyError as exc:
        raise KeyError(
            f"Unknown colour role {role!r}. Available: {sorted(COLOR[_MODE])}"
        ) from exc


# ---------------------------------------------------------------------------
# 2. Chart palettes — the seven scales (D-017), per mode
# ---------------------------------------------------------------------------
# Stop convention: index 0 = darkest, last = lightest (as in tokens.css).

#: Scale name -> what it is for.
SCALES = {
    "seq": "sequential ultramarine, 9 stops: one-directional magnitude",
    "div": "diverging good/bad, 13 stops: arms match var-pos / var-neg, midpoint surface-3",
    "two": "two-sided ultramarine <-> ochre, 13 stops: neither side is good",
    "long": "long interpolation blue -> teal -> green -> yellow, 8 stops",
    "short": "short interpolation blue -> violet -> magenta -> amber, 8 stops",
}

#: v1 names, kept as aliases for one major version. seq-orange and the
#: political scale are retired; they resolve to their v2 replacements.
_ALIASES = {
    "seq-blue": "seq", "interp-long": "long", "interp-short": "short",
    "div-warm-cool": "div", "div-political": "two", "seq-orange": "two",
}

CHART_PALETTES = {m: dict(TOKENS["color"][m]["scales"]) for m in ("light", "dark")}

#: Epistemic tags, carried on every published figure via footer(). Recessive
#: wayfinding in ink-2; no tag spends the accent or a variance colour, because
#: colour never judges (D-025) and the accent belongs to the figure's one
#: earned mark (D-036). The tag's own word carries the warning.
EPISTEMIC_TAGS = {
    "VERIFIED": "ink-2",
    "CALIBRATED": "ink-2",
    "SIMULATED": "ink-2",
    "ASSUMED": "ink-2",
    "ILLUSTRATIVE": "ink-2",
}


def palette(name: str, n: int = None, *, reverse: bool = False) -> list[str]:
    """Return a design-system scale for the current mode.

    ``name`` is one of :data:`SCALES`, ``"categorical"`` (the five hue slots,
    D-018, used in order; a sixth series is ``c("cat-other")``) or
    ``"categorical-grey"`` (parts of a whole). ``n`` samples a scale evenly
    rather than truncating it, so a 3-colour draw from a 9-stop scale spans the
    whole range.
    """
    if name in _ALIASES:
        warnings.warn(f"bk_theme: palette {name!r} is a v1 name; use {_ALIASES[name]!r}",
                      DeprecationWarning, stacklevel=2)
        name = _ALIASES[name]
    if name == "categorical":
        stops = [c(f"cat-{i}") for i in range(1, 6)]
        if n is not None and n > len(stops):
            return stops + [c("cat-other")] * (n - len(stops))
        return stops[:n] if n else stops
    if name == "categorical-grey":
        stops = [c(f"catg-{i}") for i in range(1, 5)]
        return stops[:n] if n else stops
    if name not in CHART_PALETTES[_MODE]:
        raise KeyError(f"Unknown palette {name!r}. Available: {sorted(SCALES) + ['categorical', 'categorical-grey']}")
    stops = list(CHART_PALETTES[_MODE][name])
    if n is not None and n != len(stops):
        if n == 1:
            stops = [stops[len(stops) // 2]]
        else:
            step = (len(stops) - 1) / (n - 1)
            stops = [stops[round(i * step)] for i in range(n)]
    return list(reversed(stops)) if reverse else stops


def neutral_ramp(n: int) -> list[str]:
    """``n`` structure greys, darkest first (IBCS parts of a whole). Wraps past four."""
    stops = palette("categorical-grey")
    return [stops[i % len(stops)] for i in range(n)]


class FillScale(NamedTuple):
    """What a continuous fill is drawn with: pass ``cmap`` and ``norm`` to
    ``imshow`` / ``pcolormesh`` / ``contourf``, and ``levels`` to ``contourf``
    (``None`` for a smooth gradient)."""
    cmap: object
    norm: Normalize
    levels: list[float] | None


def fill_scale(vmin: float, vmax: float, *, midpoint: float = None,
               scale: str = None, steps: int = None) -> FillScale:
    """Colour map and norm for a continuous fill: heatmap, contour, choropleth (D-053).

    - A one-sided magnitude (no ``midpoint``) takes the sequential scale ``seq``,
      darker for more.
    - With a ``midpoint`` (zero, a tie, a target) and data on both sides of it,
      the diverging scale (``div``, or ``two`` when neither side is good)
      centred on the midpoint, never on the data's own range.
    - With a ``midpoint`` but every value on one side of it, there is no tie to
      show: the sequential scale, darker the farther from the midpoint.
    - ``steps`` draws a stepped fill with that many bands (per side, when
      diverging); it may not exceed the steps the scale has, because bands
      sliced finer than the scale cannot be told apart. Without ``steps`` the
      fill is a smooth gradient over the whole scale.
    """
    if not vmax > vmin:
        raise ValueError(f"fill_scale needs vmin < vmax, got {vmin!r}, {vmax!r}")
    if midpoint is not None and vmin < midpoint < vmax:
        name = scale or "div"
        if name not in ("div", "two"):
            raise ValueError(f"a fill around a midpoint takes 'div' or 'two', not {name!r}")
        stops = palette(name)                      # darkest of one pole first
        centre = len(stops) // 2
        if steps is None:
            return FillScale(LinearSegmentedColormap.from_list(f"bk-{name}", stops),
                             TwoSlopeNorm(vmin=vmin, vcenter=midpoint, vmax=vmax), None)
        if not 1 <= steps <= centre:
            raise ValueError(f"{name!r} has {centre} steps per side; asked for {steps}")
        # One arm is sampled and mirrored onto the other, so equal distances from
        # the midpoint always take equal intensities on both sides.
        arm = list(range(centre))                  # 0 = nearest the midpoint
        picks = _sample(arm, steps)
        low = [stops[centre - 1 - i] for i in reversed(picks)]   # darkest -> nearest
        high = [stops[centre + 1 + i] for i in picks]            # nearest -> darkest
        levels = ([vmin + (midpoint - vmin) * i / steps for i in range(steps)]
                  + [midpoint + (vmax - midpoint) * i / steps for i in range(steps + 1)])
        return FillScale(ListedColormap(low + high, f"bk-{name}-{steps}"),
                         BoundaryNorm(levels, 2 * steps), levels)
    name = scale or "seq"
    if midpoint is not None and name in ("div", "two"):
        name = "seq"                               # no tie to show: the diverging choice falls back
    if name not in ("seq", "long", "short"):
        raise ValueError(f"a one-sided fill takes 'seq', 'long' or 'short', not {name!r}")
    stops = palette(name)
    if name == "seq":                              # light -> dark, darker for more
        stops = stops[::-1]
    if midpoint is not None and vmax <= midpoint:  # all below: farther down reads darker
        stops = stops[::-1]
    if steps is None:
        return FillScale(LinearSegmentedColormap.from_list(f"bk-{name}", stops),
                         Normalize(vmin, vmax), None)
    if not 1 <= steps <= len(stops):
        raise ValueError(f"{name!r} has {len(stops)} steps; asked for {steps}")
    levels = [vmin + (vmax - vmin) * i / steps for i in range(steps + 1)]
    return FillScale(ListedColormap(_sample(stops, steps), f"bk-{name}-{steps}"),
                     BoundaryNorm(levels, steps), levels)


def _sample(stops: list, n: int) -> list:
    """``n`` stops spread evenly over ``stops``, keeping their order and both ends;
    a one-band draw takes the last (the darkest, the outermost of an arm)."""
    if n == 1:
        return [stops[-1]]
    step = (len(stops) - 1) / (n - 1)
    return [stops[round(i * step)] for i in range(n)]


def tag_color(tag: str) -> str:
    """Colour for an epistemic tag."""
    return c(EPISTEMIC_TAGS.get(str(tag).upper(), "ink-2"))


def variance_color(delta: float, *, higher_is_better: bool = True) -> str:
    """IBCS variance colour (D-015): ``var-pos`` when the delta is good, ``var-neg`` when bad."""
    good = (delta >= 0) == higher_is_better
    return c("var-pos") if good else c("var-neg")


def variance_label(text: str, delta: float, *, higher_is_better: bool = True) -> str:
    """A variance label: a bad variance always carries the ▲ alert glyph (D-016)."""
    good = (delta >= 0) == higher_is_better
    return text if good else f"▲ {text}"


# ---------------------------------------------------------------------------
# 3. Typography — BKribitz and BKribitz Mono (D-003)
# ---------------------------------------------------------------------------
# Display and body are BKribitz; every number, label, tick and tag is
# BKribitz Mono, whose figures are tabular with a slashed zero, which is how the
# CSS rule `tabular-nums lining-nums slashed-zero` is honoured in a renderer
# without OpenType feature switches. Both are modified Geist cuts under SIL OFL
# 1.1, shipped in `bk_design/fonts/` with the licence and notice.

#: Fallback stacks, used only when the files cannot be registered.
_FALLBACK = {
    "display": ["Inter", "Helvetica Neue", "Liberation Sans", "DejaVu Sans"],
    "mono": ["SF Mono", "Menlo", "Liberation Mono", "DejaVu Sans Mono"],
}

#: Resolved font files per (role, weight). Populated by register_fonts().
_FP: dict[tuple[str, int], str] = {}
#: Family names as the installed files report them ("BKribitz", "BKribitz Mono").
_FAMILY: dict[str, str | None] = {"display": None, "mono": None}
_FONT_WARNED = False

#: Type scale in points for a figure scaled into a README or a page column.
#: The floor is the system's 12px (D: no size below 12px): 9.5pt at the
#: 96px/in figure dpi is 12.7px.
SIZE = {
    "hero": 72.0,      # --t-display   6rem at its widest
    "section": 31.0,   # --t-h2        3rem
    "project": 20.0,   # --t-h3        1.875rem — chart titles
    "lead": 16.5,      # --t-lead      1.25rem
    "body": 13.8,      # --t-body      1.125rem — context / subtitle lines
    "mono": 11.0,      # --t-mono      13px      — labels, footer, ticks
    "mono-sm": 9.5,    # --t-mono-sm   12px, the floor
    "kpi": 36.0,       # metric value
}

#: Weights. Every heading is 700 (D-008); 800 is the BRAGA wordmark only (D-009a).
WEIGHT = {
    "wordmark": 800, "display": 700, "bold": 700,
    "semibold": 600, "medium": 500, "regular": 400,
    "black": 700,      # v1 name: titles follow the display weight (--w-black alias)
}

#: matplotlib's SVG backend resolves weights through a name table, so a numeric
#: weight raises there. This bridges the system's numbers to the names it knows.
_MPL_WEIGHT = {
    400: "normal", 500: "medium", 600: "semibold",
    700: "bold", 800: "heavy", 900: "black",
}

LINE_HEIGHT = {"tight": 1.05, "snug": 1.2, "body": 1.6}


def register_fonts(path: str | Path = None) -> dict[str, str | None]:
    """Register BKribitz and BKribitz Mono and read back their family names.

    ``path`` overrides the bundled ``bk_design/fonts``; it may hold ``.ttf`` or
    ``.otf`` files named as in braga-portfolio-v2 ``public/fonts``
    (``BKribitz-700.ttf``, ``BKribitzMono-400.ttf``). Returns the family names.
    """
    global _FONT_WARNED
    root = Path(path) if path else _DESIGN / "fonts"
    if root.is_dir():
        for f in sorted(list(root.glob("*.ttf")) + list(root.glob("*.otf"))):
            m = re.match(r"^BKribitz(Mono)?-(\d{3})$", f.stem)
            if not m:
                continue
            role = "mono" if m.group(1) else "display"
            fontManager.addfont(str(f))
            _FP[(role, int(m.group(2)))] = str(f)
            if _FAMILY[role] is None:
                _FAMILY[role] = FontProperties(fname=str(f)).get_name()
    if not _FP and not _FONT_WARNED:
        warnings.warn(
            f"bk_theme: no BKribitz files found under {root}. Charts will render in "
            "a fallback face and will not match the design system.",
            stacklevel=2,
        )
        _FONT_WARNED = True
    return dict(_FAMILY)


class _FallbackWeightFilter(logging.Filter):
    """Drop matplotlib's notice that a *fallback* face lacks a weight. The
    fallbacks only supply glyphs BKribitz lacks (``check_glyphs`` reports those),
    so their weight substitution is expected; a BKribitz miss still logs."""

    def filter(self, record: logging.LogRecord) -> bool:
        msg = record.getMessage()
        return not ("Failed to find font weight" in msg
                    and any(f"for {name}," in msg for stack in _FALLBACK.values() for name in stack))


logging.getLogger("matplotlib.font_manager").addFilter(_FallbackWeightFilter())


def _bundled_weight(role: str, w: int) -> int:
    """The nearest weight a registered face exists for (the lighter one on a tie),
    so a request for a weight the files lack, such as mono 600, never sends
    matplotlib hunting through the fallback stack."""
    have = sorted(wt for (r, wt) in _FP if r == role)
    if not have or w in have:
        return w
    return min(have, key=lambda x: (abs(x - w), x))


def font(role: str = "display", weight: int | str = 400,
         size: float | str = None) -> FontProperties:
    """Return FontProperties for a role and weight.

    ``role`` is ``"display"`` or ``"mono"``. ``weight`` accepts a number or a
    name from :data:`WEIGHT`. ``size`` accepts points or a key from :data:`SIZE`.
    A family list, not a file path, so matplotlib can still fall back per glyph.
    """
    w = WEIGHT.get(weight, weight) if isinstance(weight, str) else weight
    if isinstance(size, str):
        size = SIZE[size]

    stack = ([_FAMILY[role]] if _FAMILY[role] else []) + _FALLBACK[role]
    fp = FontProperties(family=stack, weight=_MPL_WEIGHT.get(_bundled_weight(role, w), "normal"))
    if size is not None:
        fp.set_size(size)
    return fp

def check_glyphs(fig: Figure, *, raise_on_missing: bool = False) -> list[str]:
    """Report characters in the figure the registered BKribitz files cannot render.

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
            "bk_theme: these characters are not in the registered BKribitz files: "
            + " ".join(gaps)
            + ". They render from the fallback face, so this figure mixes "
            "typefaces."
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

#: The chart layer's own view of the tokens (dump_tokens writes it): the
#: design-system values it renders with plus the figure-space conversions.
CHART_TOKENS = {
    "design_system": DS_VERSION,
    "color": COLOR,
    "scales": CHART_PALETTES,
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
        "measure_ch": 60,
        "radius_px": [0],
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
    BKribitz directory and calls :func:`register_fonts` for you (the bundled
    faces are registered by default).

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
        "axes.titleweight": _MPL_WEIGHT[WEIGHT["display"]],
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
        "grid.color": c("rule-c"),     # rhythm rule (D-020); axes stay mid
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
    single earned figure takes the accent (D-036).

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
                      base: str = "ink-2", accent: str = "hl") -> list[str]:
    """Structure grey for everything, the highlight for the one thing that earned it.

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
                "spends the highlight (--hl = --accent-01) on one mark per chart; two read "
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
    """Ink or surface, whichever contrasts more with ``facecolor`` (both modes)."""
    def lum(col):
        def lin(x):
            return x / 12.92 if x <= 0.04045 else ((x + 0.055) / 1.055) ** 2.4
        r, g, b = mpl.colors.to_rgb(col)
        return 0.2126 * lin(r) + 0.7152 * lin(g) + 0.0722 * lin(b)

    def ratio(a, b):
        la, lb = lum(a), lum(b)
        return (max(la, lb) + 0.05) / (min(la, lb) + 0.05)

    return max((c("ink"), c("surface")), key=lambda t: ratio(t, facecolor))


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
            "accent on at most one metric, the single earned figure (D-036).",
            stacklevel=2,
        )

    # the metric strip (site layout.css §8): one ink rule opens it; nothing
    # closes it (D-044, rules open, never close)
    fig.add_artist(mpl.lines.Line2D(
        [left, left + span], [top, top], transform=fig.transFigure, color=c("ink"),
        linewidth=HAIRLINE_PT, clip_on=False, zorder=3))

    for i, kpi in enumerate(kpis):
        x0 = left + i * (width + gutter)

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

    fig.add_artist(mpl.lines.Line2D(   # the footer's opening rule: ink (D-044)
        [left, left + span], [y + 0.028, y + 0.028], transform=fig.transFigure,
        color=c("ink"), linewidth=HAIRLINE_PT, clip_on=False, zorder=3))

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
    """A baseline or threshold, drawn as a hairline and labelled in place.

    The line is a ``mid`` hairline; its label is ``ink-2``, since mid is never
    text (D-007). A vertical line's label stands above the plot area.
    """
    col = color or c("mid")
    text_col = color or c("ink-2")
    fp = font("mono", "regular", "mono-sm")
    if orient == "h":
        ax.axhline(value, color=col, lw=HAIRLINE_PT, ls=(0, (3, 3)), zorder=1)
        if label:
            ax.annotate(label.upper(), xy=(1.0, value),
                        xycoords=("axes fraction", "data"),
                        xytext=(-4, 5), textcoords="offset points",
                        ha="right", va="bottom", color=text_col, fontproperties=fp)
    else:
        ax.axvline(value, color=col, lw=HAIRLINE_PT, ls=(0, (3, 3)), zorder=1)
        if label:
            ax.annotate(label.upper(), xy=(value, 1.0),
                        xycoords=("data", "axes fraction"),
                        xytext=(0, 4), textcoords="offset points",
                        ha="left", va="bottom", color=text_col, fontproperties=fp,
                        annotation_clip=False)


def annotate_delta(ax: Axes, x, y_from: float, y_to: float, text: str, *,
                   color: str = None) -> None:
    """Bracket the gap between two values and name it. The delta is the decision.

    The bracket and its label are ink: colour never judges (D-025). Colour the
    variance *bars* with :func:`variance_color`; a bad variance label takes the
    ▲ through :func:`variance_label`.
    """
    col = color or c("ink")
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

    BKribitz is under SIL OFL 1.1, so PDF (which embeds the face) is allowed;
    ``allow_pdf`` is kept for compatibility and ignored.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    check_glyphs(fig)
    written = []
    for ext in formats:
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
    path.write_text(json.dumps(CHART_TOKENS, indent=2) + "\n", encoding="utf-8")
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

    axis = dict(showgrid=True, gridcolor=c("rule-c"), gridwidth=1,
                zeroline=False, linecolor=c("mid"), linewidth=1, ticks="",
                tickfont=dict(family=mono, size=13, color=c("ink-2")),
                title=dict(font=dict(family=mono, size=13, color=c("ink-2"))))

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
