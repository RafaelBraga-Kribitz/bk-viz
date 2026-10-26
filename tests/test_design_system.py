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
