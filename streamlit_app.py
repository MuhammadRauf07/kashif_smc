import os
from pathlib import Path

os.environ.setdefault("SMC_CREDIT", "0")

import pandas as pd
from smartmoneyconcepts.smc import smc

SAMPLE_OHLC = (
    Path(__file__).resolve().parent
    / "tests"
    / "test_data"
    / "EURUSD"
    / "EURUSD_15M.csv"
)


def load_sample_ohlc(max_bars: int = 400) -> pd.DataFrame:
    if max_bars < 1:
        raise ValueError("max_bars must be at least 1")

    df = pd.read_csv(SAMPLE_OHLC)
    df["Date"] = pd.to_datetime(df["Date"], format="%Y.%m.%d %H:%M:%S")
    df = df.set_index("Date")
    df = df.rename(columns=str.lower)
    if len(df) > max_bars:
        df = df.iloc[-max_bars:].copy()
    return df


def fvg_rectangles(index, fvg: pd.DataFrame) -> list:
    rects = []
    last = len(index) - 1
    for i, row in enumerate(fvg.itertuples(index=False)):
        if pd.isna(row.FVG):
            continue
        end = row.MitigatedIndex
        end_i = last if pd.isna(end) or int(end) == 0 else min(int(end), last)
        rects.append(
            {
                "x0": index[i],
                "x1": index[end_i],
                "y0": float(row.Bottom),
                "y1": float(row.Top),
                "bullish": float(row.FVG) == 1.0,
            }
        )
    return rects


def swing_markers(index, swings: pd.DataFrame) -> dict:
    highs_x, highs_y, lows_x, lows_y = [], [], [], []
    for i, row in enumerate(swings.itertuples(index=False)):
        if pd.isna(row.HighLow):
            continue
        if row.HighLow == 1:
            highs_x.append(index[i])
            highs_y.append(float(row.Level))
        elif row.HighLow == -1:
            lows_x.append(index[i])
            lows_y.append(float(row.Level))
    return {
        "highs_x": highs_x,
        "highs_y": highs_y,
        "lows_x": lows_x,
        "lows_y": lows_y,
    }


def structure_labels(index, structure: pd.DataFrame) -> dict:
    xs, ys, texts = [], [], []
    for i, row in enumerate(structure.itertuples(index=False)):
        if not pd.isna(row.BOS):
            text = "BOS"
        elif not pd.isna(row.CHOCH):
            text = "CHoCH"
        else:
            continue
        xs.append(index[i])
        ys.append(float(row.Level))
        texts.append(text)
    return {"x": xs, "y": ys, "text": texts}


def order_block_rectangles(index, order_blocks: pd.DataFrame) -> list:
    rects = []
    for i, row in enumerate(order_blocks.itertuples(index=False)):
        if pd.isna(row.OB):
            continue
        rects.append(
            {
                "x0": index[i],
                "x1": index[-1],
                "y0": float(row.Bottom),
                "y1": float(row.Top),
                "bullish": float(row.OB) == 1.0,
            }
        )
    return rects


def _add_rects(fig, rects, bull_color, bear_color):
    for rect in rects:
        fig.add_shape(
            type="rect",
            x0=rect["x0"],
            x1=rect["x1"],
            y0=rect["y0"],
            y1=rect["y1"],
            fillcolor=bull_color if rect["bullish"] else bear_color,
            line={"width": 0},
            layer="below",
        )


def render():
    import plotly.graph_objects as go
    import streamlit as st

    st.set_page_config(page_title="Smart Money Concepts", layout="wide")
    st.title("Smart Money Concepts")
    st.caption("EURUSD 15-minute sample. Overlays come from the smartmoneyconcepts indicators.")

    bars = st.sidebar.slider("Candles", min_value=100, max_value=1500, value=400, step=50)
    swing_length = st.sidebar.slider("Swing length", min_value=2, max_value=50, value=5)
    show_fvg = st.sidebar.checkbox("Fair value gaps", value=True)
    show_swings = st.sidebar.checkbox("Swing highs and lows", value=True)
    show_structure = st.sidebar.checkbox("BOS and CHoCH", value=True)
    show_ob = st.sidebar.checkbox("Order blocks", value=False)

    df = load_sample_ohlc(bars)
    swings = smc.swing_highs_lows(df, swing_length=swing_length)

    fig = go.Figure(
        data=[
            go.Candlestick(
                x=df.index,
                open=df["open"],
                high=df["high"],
                low=df["low"],
                close=df["close"],
                name="EURUSD",
            )
        ]
    )

    if show_fvg:
        _add_rects(
            fig,
            fvg_rectangles(df.index, smc.fvg(df)),
            "rgba(38, 166, 91, 0.28)",
            "rgba(214, 69, 69, 0.28)",
        )
    if show_ob:
        _add_rects(
            fig,
            order_block_rectangles(df.index, smc.ob(df, swings)),
            "rgba(52, 152, 219, 0.25)",
            "rgba(241, 196, 15, 0.25)",
        )
    if show_swings:
        markers = swing_markers(df.index, swings)
        fig.add_trace(
            go.Scatter(
                x=markers["highs_x"],
                y=markers["highs_y"],
                mode="markers",
                name="Swing high",
                marker={"color": "#e74c3c", "size": 7, "symbol": "triangle-down"},
            )
        )
        fig.add_trace(
            go.Scatter(
                x=markers["lows_x"],
                y=markers["lows_y"],
                mode="markers",
                name="Swing low",
                marker={"color": "#2ecc71", "size": 7, "symbol": "triangle-up"},
            )
        )
    if show_structure:
        labels = structure_labels(df.index, smc.bos_choch(df, swings))
        fig.add_trace(
            go.Scatter(
                x=labels["x"],
                y=labels["y"],
                mode="markers+text",
                name="BOS / CHoCH",
                text=labels["text"],
                textposition="top center",
                marker={"color": "#f1c40f", "size": 6},
            )
        )

    fig.update_layout(
        template="plotly_dark",
        height=720,
        xaxis_rangeslider_visible=False,
        margin={"l": 10, "r": 10, "t": 30, "b": 10},
        legend={"orientation": "h", "y": 1.05},
    )
    st.plotly_chart(fig, use_container_width=True)


if __name__ == "__main__":
    render()
