"""bk_theme against the Braga design system v2.1 (braga-portfolio-v2 design-system/)."""
import json
import re
import warnings
from pathlib import Path

import pytest

import bk_theme as bk

ROOT = Path(__file__).resolve().parent.parent


def test_no_hex_literal_in_the_module():
    """Every colour comes from tokens.json; the module carries none of its own."""
    src = (ROOT / "bk_theme.py").read_text(encoding="utf-8")
    assert not re.findall(r"#[0-9A-Fa-f]{6}\b", src)


def test_snapshot_matches_a_design_system_checkout():
    sibling = ROOT.parent / "braga-portfolio-v2" / "design-system" / "tokens.json"
    if not sibling.is_file():
        pytest.skip("no braga-portfolio-v2 checkout next to this one")
    assert json.loads((ROOT / "bk_design" / "tokens.json").read_text()) == json.loads(sibling.read_text())


def test_roles_resolve_in_both_modes():
    for m in ("light", "dark"):
        bk.apply(m)
        for role in ("surface", "ink", "ink-2", "mid", "rule-c", "hl", "sc-ac", "sc-py", "sc-pl",
                     "var-pos", "var-neg", "alert", "cat-1", "cat-5", "cat-other", "catg-1"):
            assert re.fullmatch(r"#[0-9A-F]{6}", bk.c(role)), (m, role)
        assert bk.c("hl") == bk.TOKENS["color"][m]["accent-01"]
    bk.apply("light")


def test_fonts_are_bkribitz():
    bk.apply("light")
    assert bk._FAMILY == {"display": "BKribitz", "mono": "BKribitz Mono"}


def test_retired_roles_and_v1_scales():
    with pytest.raises(KeyError, match="retired"):
        bk.c("accent-02")
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        assert bk.palette("seq-blue") == bk.palette("seq")
        assert any(issubclass(x.category, DeprecationWarning) for x in w)


def test_one_highlight_and_the_alert_glyph():
    bk.apply("light")
    cols = bk.highlight_palette(["a", "b", "c"], highlight="b")
    assert cols.count(bk.c("hl")) == 1
    assert bk.variance_color(-3) == bk.c("var-neg") and bk.variance_color(2) == bk.c("var-pos")
    assert bk.variance_label("-3%", -3).startswith("▲")
    assert bk.variance_label("+2%", 2) == "+2%"


def test_epistemic_tags_never_spend_the_accent():
    assert set(bk.EPISTEMIC_TAGS.values()) == {"ink-2"}


def test_type_floor():
    # 12px at the 96px/in figure resolution is 9pt
    assert min(bk.SIZE.values()) >= 9.0
    assert bk.WEIGHT["display"] == 700 and bk.WEIGHT["wordmark"] == 800


# ---------------------------------------------------------------- continuous fills (D-053)
def test_one_sided_fill_takes_the_sequential_scale_darker_for_more():
    bk.apply("light")
    f = bk.fill_scale(1.2, 2.9)
    lo, hi = f.cmap(f.norm(1.2)), f.cmap(f.norm(2.9))
    assert sum(hi[:3]) < sum(lo[:3])                        # more is darker
    assert f.levels is None


def test_midpoint_fill_is_anchored_at_the_midpoint_not_the_data():
    from matplotlib.colors import to_hex
    bk.apply("light")
    f = bk.fill_scale(-1.0, 3.0, midpoint=0.0)
    neutral = bk.palette("div")[len(bk.palette("div")) // 2]
    got, want = to_hex(f.cmap(f.norm(0.0))), neutral
    assert all(abs(int(got[i:i + 2], 16) - int(want[i:i + 2], 16)) <= 2 for i in (1, 3, 5))


def test_one_sided_data_with_a_midpoint_has_no_tie_colour():
    from matplotlib.colors import to_hex
    bk.apply("light")
    neutral = bk.palette("div")[len(bk.palette("div")) // 2].upper()
    above = bk.fill_scale(1.2, 2.9, midpoint=0.0, steps=9)
    colours = {to_hex(above.cmap(i)).upper() for i in range(above.cmap.N)}
    assert neutral not in colours and len(colours) == 9
    below = bk.fill_scale(-2.9, -1.2, midpoint=0.0)
    assert sum(below.cmap(below.norm(-2.9))[:3]) < sum(below.cmap(below.norm(-1.2))[:3])


def test_stepped_fill_cannot_have_more_bands_than_its_scale():
    bk.apply("light")
    assert len(bk.fill_scale(0, 1, steps=9).levels) == 10
    with pytest.raises(ValueError):
        bk.fill_scale(0, 1, steps=16)
    with pytest.raises(ValueError):
        bk.fill_scale(-1, 1, midpoint=0, steps=7)
    f = bk.fill_scale(-1, 3, midpoint=0, steps=6)
    assert len(f.levels) == 13 and 0 in f.levels


def test_a_weight_the_files_lack_snaps_to_one_they_have():
    bk.apply("light")
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        fp = bk.font("mono", "semibold", "mono")
    assert fp.get_weight() in ("medium", "bold")


def test_rendering_logs_no_weight_fallback_warnings(caplog, tmp_path):
    import logging
    bk.apply("light")
    with caplog.at_level(logging.WARNING, logger="matplotlib.font_manager"):
        fig, ax = bk.new_figure()
        ax.bar([1, 2], [3, 4])
        bk.value_labels(ax)
        bk.footer(fig, source="test")
        fig.savefig(tmp_path / "t.png")
    assert not [r for r in caplog.records if "Failed to find font weight" in r.getMessage()]


def test_explicit_diverging_scale_falls_back_when_data_is_one_sided():
    bk.apply("light")
    f = bk.fill_scale(1, 2, midpoint=0, scale="two")
    assert f.norm.vmin == 1 and f.norm.vmax == 2


def test_one_band_per_side_takes_matching_outer_stops():
    from matplotlib.colors import to_hex
    bk.apply("light")
    for name in ("div", "two"):
        stops = bk.palette(name)
        f = bk.fill_scale(-1, 1, midpoint=0, scale=name, steps=1)
        got = [to_hex(f.cmap(i)).upper() for i in range(f.cmap.N)]
        assert got == [stops[0].upper(), stops[-1].upper()]


def test_diverging_bands_mirror_each_other_for_every_step_count():
    from matplotlib.colors import to_hex
    bk.apply("light")
    for name in ("div", "two"):
        stops = [s.upper() for s in bk.palette(name)]
        centre = len(stops) // 2
        for k in range(1, centre + 1):
            f = bk.fill_scale(-1, 1, midpoint=0, scale=name, steps=k)
            got = [to_hex(f.cmap(i)).upper() for i in range(f.cmap.N)]
            low = [centre - stops.index(x) for x in got[:k]][::-1]
            high = [stops.index(x) - centre for x in got[k:]]
            assert low == high, (name, k, low, high)
