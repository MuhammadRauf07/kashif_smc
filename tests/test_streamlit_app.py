import os
import sys

os.environ["SMC_CREDIT"] = "0"

import pandas as pd
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from smartmoneyconcepts.smc import smc
from streamlit_app import (
    fvg_rectangles,
    load_sample_ohlc,
    order_block_rectangles,
    structure_labels,
    swing_markers,
)


def test_load_sample_ohlc_has_price_columns():
    df = load_sample_ohlc(max_bars=50)

    assert len(df) == 50
    assert {"open", "high", "low", "close", "volume"} <= set(df.columns)
    assert df.index.is_monotonic_increasing


def test_load_sample_ohlc_rejects_empty_window():
    with pytest.raises(ValueError):
        load_sample_ohlc(max_bars=0)


def test_fvg_rectangles_match_detected_gaps():
    df = load_sample_ohlc(max_bars=200)
    fvg = smc.fvg(df)
    rects = fvg_rectangles(df.index, fvg)

    assert len(rects) == int(fvg["FVG"].notna().sum())
    assert rects
    assert all(rect["y0"] <= rect["y1"] for rect in rects)
    assert all(rect["x0"] <= rect["x1"] for rect in rects)


def test_swing_markers_follow_high_low_sign():
    df = load_sample_ohlc(max_bars=200)
    swings = smc.swing_highs_lows(df, swing_length=5)
    markers = swing_markers(df.index, swings)

    assert len(markers["highs_x"]) == int((swings["HighLow"] == 1).sum())
    assert len(markers["lows_x"]) == int((swings["HighLow"] == -1).sum())
    assert markers["highs_y"]
    assert markers["lows_y"]


def test_structure_labels_use_bos_or_choch():
    df = load_sample_ohlc(max_bars=200)
    swings = smc.swing_highs_lows(df, swing_length=5)
    structure = smc.bos_choch(df, swings)
    labels = structure_labels(df.index, structure)

    expected = int((structure["BOS"].notna() | structure["CHOCH"].notna()).sum())
    assert len(labels["text"]) == expected
    assert set(labels["text"]) <= {"BOS", "CHoCH"}
    assert not any(pd.isna(level) for level in labels["y"])


def test_order_block_rectangles_match_detected_blocks():
    df = load_sample_ohlc(max_bars=200)
    swings = smc.swing_highs_lows(df, swing_length=5)
    blocks = smc.ob(df, swings)
    rects = order_block_rectangles(df.index, blocks)

    assert len(rects) == int(blocks["OB"].notna().sum())
    assert all(rect["y0"] <= rect["y1"] for rect in rects)
