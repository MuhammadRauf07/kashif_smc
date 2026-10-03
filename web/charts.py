import pandas as pd
import plotly.graph_objects as go


def _mid_index(start: int, end: int) -> int:
    return int(round((start + end) / 2))


def _safe_index(value, fallback: int) -> int:
    if pd.isna(value) or value == 0:
        return fallback
    return int(value)


def add_fvg(fig: go.Figure, ohlc: pd.DataFrame, fvg_data: pd.DataFrame) -> go.Figure:
    last = len(ohlc) - 1
    for i in range(len(fvg_data)):
        if pd.isna(fvg_data["FVG"].iloc[i]):
            continue
        x1 = _safe_index(fvg_data["MitigatedIndex"].iloc[i], last)
        fig.add_shape(
            type="rect",
            x0=ohlc.index[i],
            y0=fvg_data["Top"].iloc[i],
            x1=ohlc.index[x1],
            y1=fvg_data["Bottom"].iloc[i],
            line=dict(width=0),
            fillcolor="yellow",
            opacity=0.18,
        )
        fig.add_trace(
            go.Scatter(
                x=[ohlc.index[_mid_index(i, x1)]],
                y=[(fvg_data["Top"].iloc[i] + fvg_data["Bottom"].iloc[i]) / 2],
                mode="text",
                text=["FVG"],
                textfont=dict(color="rgba(255,255,255,0.45)", size=10),
                hoverinfo="skip",
                showlegend=False,
            )
        )
    return fig


def add_swings(fig: go.Figure, ohlc: pd.DataFrame, swing_data: pd.DataFrame) -> go.Figure:
    points = [
        (i, swing_data["Level"].iloc[i], swing_data["HighLow"].iloc[i])
        for i in range(len(swing_data))
        if not pd.isna(swing_data["HighLow"].iloc[i])
    ]
    for (i, level, kind), (j, next_level, _) in zip(points, points[1:]):
        fig.add_trace(
            go.Scatter(
                x=[ohlc.index[i], ohlc.index[j]],
                y=[level, next_level],
                mode="lines",
                line=dict(
                    color="rgba(0,128,0,0.45)" if kind == -1 else "rgba(255,0,0,0.45)"
                ),
                hoverinfo="skip",
                showlegend=False,
            )
        )
    return fig


def add_bos_choch(fig: go.Figure, ohlc: pd.DataFrame, bos_data: pd.DataFrame) -> go.Figure:
    for i in range(len(bos_data)):
        broken = bos_data["BrokenIndex"].iloc[i]
        if pd.isna(broken):
            continue
        broken = int(broken)
        level = bos_data["Level"].iloc[i]
        if not pd.isna(bos_data["BOS"].iloc[i]):
            label, color = "BOS", "rgba(255,165,0,0.7)"
            bullish = bos_data["BOS"].iloc[i] == 1
        elif not pd.isna(bos_data["CHOCH"].iloc[i]):
            label, color = "CHoCH", "rgba(80,140,255,0.75)"
            bullish = bos_data["CHOCH"].iloc[i] == 1
        else:
            continue
        fig.add_trace(
            go.Scatter(
                x=[ohlc.index[i], ohlc.index[broken]],
                y=[level, level],
                mode="lines+text",
                text=["", label],
                textposition="top center" if bullish else "bottom center",
                line=dict(color=color),
                textfont=dict(color=color, size=10),
                hoverinfo="skip",
                showlegend=False,
            )
        )
    return fig


def add_order_blocks(fig: go.Figure, ohlc: pd.DataFrame, ob_data: pd.DataFrame) -> go.Figure:
    last = len(ohlc) - 1
    for i in range(len(ob_data)):
        side = ob_data["OB"].iloc[i]
        if pd.isna(side):
            continue
        x1 = _safe_index(ob_data["MitigatedIndex"].iloc[i], last)
        color = "rgba(46, 204, 113, 0.22)" if side == 1 else "rgba(231, 76, 60, 0.22)"
        fig.add_shape(
            type="rect",
            x0=ohlc.index[i],
            y0=ob_data["Bottom"].iloc[i],
            x1=ohlc.index[x1],
            y1=ob_data["Top"].iloc[i],
            line=dict(width=0),
            fillcolor=color,
        )
        fig.add_trace(
            go.Scatter(
                x=[ohlc.index[_mid_index(i, x1)]],
                y=[(ob_data["Bottom"].iloc[i] + ob_data["Top"].iloc[i]) / 2],
                mode="text",
                text=["Bull OB" if side == 1 else "Bear OB"],
                textfont=dict(color="rgba(255,255,255,0.5)", size=10),
                hoverinfo="skip",
                showlegend=False,
            )
        )
    return fig


def add_liquidity(fig: go.Figure, ohlc: pd.DataFrame, liquidity_data: pd.DataFrame) -> go.Figure:
    for i in range(len(liquidity_data)):
        side = liquidity_data["Liquidity"].iloc[i]
        if pd.isna(side):
            continue
        end = _safe_index(liquidity_data["End"].iloc[i], i)
        fig.add_trace(
            go.Scatter(
                x=[ohlc.index[i], ohlc.index[end]],
                y=[liquidity_data["Level"].iloc[i], liquidity_data["Level"].iloc[i]],
                mode="lines+text",
                text=["", "Liquidity"],
                textposition="top center" if side == 1 else "bottom center",
                line=dict(color="rgba(255,165,0,0.55)"),
                textfont=dict(color="rgba(255,165,0,0.7)", size=10),
                hoverinfo="skip",
                showlegend=False,
            )
        )
    return fig


def add_previous_high_low(
    fig: go.Figure, ohlc: pd.DataFrame, previous_data: pd.DataFrame
) -> go.Figure:
    fig.add_trace(
        go.Scatter(
            x=list(ohlc.index),
            y=previous_data["PreviousHigh"],
            mode="lines",
            line=dict(color="rgba(255,255,255,0.25)", dash="dot"),
            name="Previous High",
            hoverinfo="skip",
            showlegend=False,
        )
    )
    fig.add_trace(
        go.Scatter(
            x=list(ohlc.index),
            y=previous_data["PreviousLow"],
            mode="lines",
            line=dict(color="rgba(255,255,255,0.25)", dash="dot"),
            name="Previous Low",
            hoverinfo="skip",
            showlegend=False,
        )
    )
    return fig


def add_sessions(fig: go.Figure, ohlc: pd.DataFrame, sessions: pd.DataFrame) -> go.Figure:
    for i in range(len(sessions) - 1):
        if sessions["Active"].iloc[i] != 1:
            continue
        fig.add_shape(
            type="rect",
            x0=ohlc.index[i],
            y0=sessions["Low"].iloc[i],
            x1=ohlc.index[i + 1],
            y1=sessions["High"].iloc[i],
            line=dict(width=0),
            fillcolor="#16866E",
            opacity=0.12,
        )
    return fig


def add_retracements(
    fig: go.Figure, ohlc: pd.DataFrame, retracements: pd.DataFrame
) -> go.Figure:
    for i in range(len(retracements)):
        direction = retracements["Direction"].iloc[i]
        next_direction = (
            retracements["Direction"].iloc[i + 1] if i < len(retracements) - 1 else 0
        )
        if direction == 0:
            continue
        if i < len(retracements) - 1 and next_direction == direction:
            continue
        fig.add_annotation(
            x=ohlc.index[i],
            y=ohlc["high"].iloc[i] if direction == -1 else ohlc["low"].iloc[i],
            text=(
                f"C:{retracements['CurrentRetracement%'].iloc[i]}%<br>"
                f"D:{retracements['DeepestRetracement%'].iloc[i]}%"
            ),
            font=dict(color="rgba(255,255,255,0.45)", size=9),
            showarrow=False,
        )
    return fig


OVERLAY_BUILDERS = {
    "fvg": lambda fig, ohlc, indicators: add_fvg(fig, ohlc, indicators["fvg"]),
    "swings": lambda fig, ohlc, indicators: add_swings(fig, ohlc, indicators["swings"]),
    "bos_choch": lambda fig, ohlc, indicators: add_bos_choch(
        fig, ohlc, indicators["bos_choch"]
    ),
    "ob": lambda fig, ohlc, indicators: add_order_blocks(fig, ohlc, indicators["ob"]),
    "liquidity": lambda fig, ohlc, indicators: add_liquidity(
        fig, ohlc, indicators["liquidity"]
    ),
    "previous_high_low": lambda fig, ohlc, indicators: add_previous_high_low(
        fig, ohlc, indicators["previous_high_low"]
    ),
    "sessions": lambda fig, ohlc, indicators: add_sessions(
        fig, ohlc, indicators["sessions"]
    ),
    "retracements": lambda fig, ohlc, indicators: add_retracements(
        fig, ohlc, indicators["retracements"]
    ),
}


CHART_HEIGHT = {
    "min": 280,
    "max": 2000,
    "step": 80,
}


def clamp_chart_height(height, bounds: dict | None = None) -> int:
    config = bounds or CHART_HEIGHT
    try:
        value = int(round(float(height)))
    except (TypeError, ValueError):
        value = int(config["min"])
    return min(max(value, int(config["min"])), int(config["max"]))


def step_chart_height(height, steps: int, bounds: dict | None = None) -> int:
    config = bounds or CHART_HEIGHT
    return clamp_chart_height(height + int(steps) * int(config["step"]), config)


def drag_chart_height(start_height, delta_y, bounds: dict | None = None) -> int:
    return clamp_chart_height(float(start_height) + float(delta_y), bounds)


PLOTLY_CONFIG = {
    "responsive": True,
    "displaylogo": False,
    "scrollZoom": True,
    "doubleClick": "reset",
    "displayModeBar": True,
    "modeBarButtonsToAdd": ["drawline", "drawrect", "eraseshape"],
}


def build_figure(
    ohlc: pd.DataFrame,
    indicators: dict,
    overlays: set[str],
    title: str | None = None,
) -> go.Figure:
    fig = go.Figure(
        data=[
            go.Candlestick(
                x=list(ohlc.index),
                open=ohlc["open"],
                high=ohlc["high"],
                low=ohlc["low"],
                close=ohlc["close"],
                increasing_line_color="#77dd76",
                decreasing_line_color="#ff6962",
                name="OHLC",
                hovertemplate=(
                    "%{x}<br>O %{open}<br>H %{high}<br>L %{low}<br>C %{close}<extra></extra>"
                ),
            )
        ]
    )
    for name in overlays:
        builder = OVERLAY_BUILDERS.get(name)
        if builder is not None:
            fig = builder(fig, ohlc, indicators)

    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor="#0c0e12",
        plot_bgcolor="#0c0e12",
        font=dict(color="#e8edf5", family="Segoe UI, sans-serif"),
        margin=dict(l=6, r=56, t=32 if title else 8, b=8),
        autosize=True,
        title=title or "",
        uirevision="smc-keep-view",
        dragmode="zoom",
        xaxis_rangeslider_visible=False,
        showlegend=False,
        hovermode="x unified",
        hoverlabel=dict(bgcolor="#151922", font_size=13),
    )
    fig.update_xaxes(
        showgrid=True,
        gridcolor="rgba(255,255,255,0.06)",
        showspikes=True,
        spikemode="across",
        spikesnap="cursor",
        spikecolor="rgba(125,211,168,0.45)",
        spikedash="dot",
        fixedrange=False,
    )
    fig.update_yaxes(
        showgrid=True,
        gridcolor="rgba(255,255,255,0.06)",
        side="right",
        showspikes=True,
        spikemode="across",
        spikesnap="cursor",
        spikecolor="rgba(125,211,168,0.45)",
        spikedash="dot",
        fixedrange=False,
    )
    return fig
