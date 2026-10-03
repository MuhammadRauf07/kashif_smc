import os
import sys

import pandas as pd
import plotly.graph_objects as go
import pytest

BASE_DIR = os.path.dirname(__file__)
ROOT = os.path.abspath(os.path.join(BASE_DIR, ".."))
sys.path.insert(0, ROOT)

from web.charts import (
    CHART_HEIGHT,
    PLOTLY_CONFIG,
    build_figure,
    clamp_chart_height,
    drag_chart_height,
    step_chart_height,
)
from web.dashboard import (
    ALLOWED_OVERLAYS,
    SAMPLE_CSV,
    build_dashboard_state,
    compute_indicators,
    load_sample_ohlc,
    normalize_ohlc,
    parse_overlays,
    summarize_indicators,
)


def test_normalize_ohlc_lowercases_and_adds_volume():
    raw = pd.DataFrame(
        {
            "Date": ["2024-01-01 00:00:00", "2024-01-01 00:15:00"],
            "Open": [1.1, 1.2],
            "High": [1.15, 1.25],
            "Low": [1.05, 1.18],
            "Close": [1.12, 1.22],
            "Tickvol": [10, 12],
        }
    )

    frame = normalize_ohlc(raw)

    assert list(frame.columns) == ["open", "high", "low", "close", "volume"]
    assert frame["volume"].tolist() == [10, 12]
    assert str(frame.index.name) == "date"


def test_normalize_ohlc_rejects_empty_and_missing_columns():
    with pytest.raises(ValueError, match="empty"):
        normalize_ohlc(pd.DataFrame())

    with pytest.raises(ValueError, match="Missing required OHLC columns"):
        normalize_ohlc(pd.DataFrame({"Date": ["2024-01-01"], "Open": [1.0]}))


def test_load_sample_ohlc_respects_limit():
    frame = load_sample_ohlc(limit=40, csv_path=SAMPLE_CSV)

    assert len(frame) == 40
    assert {"open", "high", "low", "close", "volume"}.issubset(frame.columns)
    assert pd.api.types.is_datetime64_any_dtype(frame.index)


def test_compute_and_summarize_indicators_on_sample_window():
    ohlc = load_sample_ohlc(limit=80, csv_path=SAMPLE_CSV)
    indicators = compute_indicators(ohlc, swing_length=5, session="London", time_frame="4h")
    stats = summarize_indicators(indicators)

    assert set(indicators) == ALLOWED_OVERLAYS
    assert all(len(frame) == len(ohlc) for frame in indicators.values())
    assert stats["swing_points"] >= 0
    assert stats["bullish_fvg"] + stats["bearish_fvg"] >= 0


def test_parse_overlays_filters_unknown_and_defaults():
    assert parse_overlays(None) == {
        "fvg",
        "swings",
        "bos_choch",
        "ob",
        "liquidity",
    }
    assert parse_overlays(["fvg", "not-real", "ob"]) == {"fvg", "ob"}


def test_build_figure_includes_candlestick_and_selected_overlay():
    ohlc = load_sample_ohlc(limit=80, csv_path=SAMPLE_CSV)
    indicators = compute_indicators(ohlc)
    fig = build_figure(ohlc, indicators, {"fvg"})

    assert isinstance(fig, go.Figure)
    assert any(isinstance(trace, go.Candlestick) for trace in fig.data)
    assert fig.layout.autosize is True
    assert fig.layout.uirevision == "smc-keep-view"
    assert fig.layout.dragmode == "zoom"
    assert PLOTLY_CONFIG["scrollZoom"] is True


def test_clamp_and_step_chart_height_do_not_change_price_data():
    assert clamp_chart_height(100) == CHART_HEIGHT["min"]
    assert clamp_chart_height(9000) == CHART_HEIGHT["max"]
    assert clamp_chart_height("640") == 640
    start = 400
    assert step_chart_height(start, 1) == start + CHART_HEIGHT["step"]
    assert step_chart_height(start, -1) == start - CHART_HEIGHT["step"]
    assert drag_chart_height(500, 120) == 620
    assert drag_chart_height(500, -400) == CHART_HEIGHT["min"]


def test_chart_page_resizes_by_drag_handle_not_height_buttons():
    from web.app import CHART_PAGE

    assert 'id="chart-resize"' in CHART_PAGE
    assert 'role="separator"' in CHART_PAGE
    assert 'id="height-plus"' not in CHART_PAGE
    assert 'id="height-minus"' not in CHART_PAGE
    assert ">Height +" not in CHART_PAGE
    assert "pointerdown" in CHART_PAGE


def test_build_dashboard_state_returns_chart_ready_payload():
    state = build_dashboard_state(candles=80, swing_length=5, overlays=["fvg", "swings"])

    assert state["candle_count"] == 80
    assert state["overlays"] == {"fvg", "swings"}
    assert isinstance(state["fig"], go.Figure)
    assert state["last_close"] > 0
    assert "stats" in state
