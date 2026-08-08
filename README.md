# bk-viz

The Braga-Kribitz Design System, applied to charts. A chart from any repo should
be indistinguishable from a chart on the site.

Every value in `bk_theme.py` is transcribed from the system's own token files
(`tokens/colors.css`, `typography.css`, `spacing.css`, `grid.css`,
`chart-palettes.css`). This module is a mirror, not a second opinion. When a
token changes there, change it here.

## Install

```bash
uv pip install "git+https://github.com/RafaelBraga-Kribitz/bk-viz@v1.0.0"
```

```toml
dependencies = ["bk-viz @ git+https://github.com/RafaelBraga-Kribitz/bk-viz@v1.0.0"]
```

The Söhne binaries are **not** bundled. Point the theme at the design system's
`assets/fonts` directory, or set `BK_FONTS`.

## Minimum viable chart

```python
import bk_theme as bk

bk.apply("light", fonts="path/to/design-system/assets/fonts")

fig, ax = bk.decision_panel(
    kpis=[
        {"label": "5-year saving", "value": "EUR 684k",
         "note": "net present value, 8% discount", "accent": True},
        {"label": "Payback", "value": "11 mo", "note": "on EUR 120k capex"},
    ],
    finding="Hybrid + AMR is EUR 684k cheaper than staying all-human",
    context="Five-year TCO by workforce scenario, 8% discount rate.",
    left=0.16,
)
ax.barh(labels, values, color=bk.highlight_palette(labels, highlight="Hybrid + AMR"))
bk.strip_chrome(ax, keep=("bottom",))
bk.money_axis(ax, axis="x", unit="k")
bk.value_labels(ax, orient="h", fmt=bk.fmt_eur_k)
bk.footer(fig, number="02-04-01", source="DATA_SOURCES.md LAB-01",
          run_id="run-2026-08-11-a", tag="CALIBRATED", left=0.16)
bk.save(fig, "reports/executive/01_tco_ranking")
```

`python example_executive_onepager.py` renders the full worked example in both
modes.

## What it enforces

| Rule | Where |
| --- | --- |
| Flat opaque surfaces, no gradient, no shadow, no alpha | `apply()` |
| Page surface is `#E6E6E6`, never white | `apply()`, `save()` |
| Hairlines at 1px `mid` as primary structure | `apply()`, `strip_chrome()` |
| Orange spent on exactly one figure | `highlight_palette()`, `kpi_row()` warn on more |
| Blue is a moment, not a default | only in the `seq-blue` data ramp |
| Numbers set in Söhne Mono, so figures are tabular | rcParams default is mono |
| Square corners, radius 0 | nothing to configure |
| Every published figure carries provenance | `footer()` |

## Modes

`bk.apply("light")` or `bk.apply("dark")`. Dark is a property the figure carries,
matching the system's `.dark` semantics. Chart-ramp dark overrides are applied
automatically by `palette()`.

## Data-vis ramps

All six system scales, by name: `seq-blue`, `seq-orange`, `div-warm-cool`,
`div-political`, `interp-long`, `interp-short`.

```python
bk.palette("div-political", n=5)   # samples evenly across the 13 stops
```

For categorical structure use `bk.neutral_ramp(n)`. A chart is grey structure
plus one orange signal; the system defines no categorical colour ramp on purpose.

## Two things to know about the fonts

**The trial binaries carry 68 glyphs.** They have no `%`, `+`, `€`, `/`, `:`,
parentheses, or the `→` / `↗` arrows the system names as its only iconography.
`bk_theme` builds a family *list* so matplotlib falls back per glyph, and
`check_glyphs()` runs on every `save()` to tell you which characters came from
the fallback face. Browsers do the same fallback silently, which is why the site
looks fine.

**PDF export is refused by default.** PDF embeds the typeface and the bundled
files are evaluation-only. PNG rasterises and SVG written with
`svg.fonttype: none` references by name, so both are safe. Pass `allow_pdf=True`
once retail Söhne is licensed.

## Non-Python surfaces

`bk.dump_tokens("bk_tokens.json")` exports the mirrored token set for a Tableau
custom palette, a Power BI theme file, or a CSS build.

## Acceptance test

If two charts from different repos do not look like siblings, the theme is not
applied.
