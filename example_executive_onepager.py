"""
Worked example: the executive decision panel, in Braga-Kribitz.

Run:  python example_executive_onepager.py

Renders `out/01_tco_decision_panel.{png,svg}` in both light and dark.
Copy this file into a project, replace the DATA block with a read from your
metrics artifact, and the chart shape is done.
"""

from pathlib import Path

import bk_theme as bk

HERE = Path(__file__).parent

# --- DATA (replace with a read from your metrics artifact) ------------------
SCENARIOS = ["Baseline: all human", "Pure humanoid", "Hybrid 50/50",
             "Future mix 2028", "Hybrid + AMR"]
NPV = [-1_608_251, -960_000, -1_284_125, -1_284_125, -924_125]
RECOMMENDED = "Hybrid + AMR"
BASELINE = "Baseline: all human"

RUN_ID = "run-2026-08-11-a"
SOURCE = "DATA_SOURCES.md LAB-01, CAP-03, ENE-02"
TAG = "CALIBRATED"
NUMBER = "02-04-01"

# NPVs are costs, so they are negative. A less negative NPV is a saving.
saving = NPV[SCENARIOS.index(RECOMMENDED)] - NPV[SCENARIOS.index(BASELINE)]


def build(theme: str) -> Path:
    bk.apply(theme, fonts=HERE / "assets" / "fonts")

    fig, ax = bk.decision_panel(
        kpis=[
            # accent on exactly one metric: the single impact number
            {"label": "5-year saving", "value": bk.fmt_eur_k(saving),
             "note": "net present value, 8% discount", "accent": True},
            {"label": "Payback", "value": "11 mo", "note": "on EUR 120k capex"},
            {"label": "Cost per order", "value": "EUR 1.42",
             "note": "baseline EUR 2.47"},
            {"label": "Confidence", "value": "82%",
             "note": "wins in 820 of 1,000 draws"},
        ],
        finding=f"Hybrid + AMR is {bk.fmt_eur_k(saving)} cheaper than staying all-human",
        context=("Total cost of ownership over five years by workforce scenario, "
                 "Austrian intralogistics, 8% discount rate. Less negative is better."),
        cols=12, rows=7.4, left=0.16, bottom=0.19,
    )

    ax.barh(SCENARIOS, NPV, height=0.58,
            color=bk.highlight_palette(SCENARIOS, highlight=RECOMMENDED))

    bk.strip_chrome(ax, keep=("bottom",))
    ax.grid(axis="y", visible=False)
    ax.grid(axis="x", visible=True)
    ax.invert_yaxis()
    bk.money_axis(ax, axis="x", unit="k", nbins=5)
    bk.value_labels(ax, orient="h", fmt=bk.fmt_eur_k)
    bk.reference_line(ax, NPV[SCENARIOS.index(BASELINE)],
                      "do-nothing baseline", orient="v")

    bk.footer(fig, source=SOURCE, run_id=RUN_ID, tag=TAG, number=NUMBER,
              left=0.16,
              note="Recommendation reverses if humanoid capex falls below EUR 62k per unit.")

    suffix = "" if theme == "light" else "_dark"
    return bk.save(fig, HERE / "out" / f"01_tco_decision_panel{suffix}")[0]


if __name__ == "__main__":
    for t in ("light", "dark"):
        print(build(t))
    bk.dump_tokens(HERE / "bk_tokens.json")
