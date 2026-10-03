import os
import sys
from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from smartmoneyconcepts.smc import smc

SAMPLE_CSV = REPO_ROOT / "tests" / "test_data" / "EURUSD" / "EURUSD_15M.csv"
ALLOWED_OVERLAYS = frozenset(
    {
        "fvg",
        "swings",
        "bos_choch",
        "ob",
        "liquidity",
        "previous_high_low",
        "sessions",
        "retracements",
    }
)
DEFAULT_OVERLAYS = frozenset(
    {"fvg", "swings", "bos_choch", "ob", "liquidity"}
)
DATE_COLUMNS = ("date", "datetime", "timestamp", "time")
REQUIRED_OHLC = ("open", "high", "low", "close")


def normalize_ohlc(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        raise ValueError("OHLC data is empty")

    frame = df.copy()
    frame.columns = [str(column).lower() for column in frame.columns]

    date_col = next((name for name in DATE_COLUMNS if name in frame.columns), None)
    if date_col is not None:
        frame[date_col] = pd.to_datetime(frame[date_col])
        frame = frame.set_index(date_col)
    else:
        frame.index = pd.to_datetime(frame.index)

    missing = [column for column in REQUIRED_OHLC if column not in frame.columns]
    if missing:
        raise ValueError(f"Missing required OHLC columns: {', '.join(missing)}")

    if "volume" not in frame.columns:
        frame["volume"] = frame["tickvol"] if "tickvol" in frame.columns else 0

    return frame.loc[:, list(REQUIRED_OHLC) + ["volume"]]


def load_sample_ohlc(limit: int = 250, csv_path: os.PathLike | None = None) -> pd.DataFrame:
    path = Path(csv_path) if csv_path is not None else SAMPLE_CSV
    if not path.exists():
        raise FileNotFoundError(f"Sample OHLC file not found: {path}")

    candles = max(int(limit), 20)
    frame = normalize_ohlc(pd.read_csv(path))
    return frame.iloc[-candles:].copy()


def compute_indicators(
    ohlc: pd.DataFrame,
    swing_length: int = 5,
    join_consecutive: bool = True,
    session: str = "London",
    time_frame: str = "4h",
) -> dict[str, pd.DataFrame]:
    if ohlc is None or ohlc.empty:
        raise ValueError("OHLC data is empty")

    swings = smc.swing_highs_lows(ohlc, swing_length=max(int(swing_length), 1))
    return {
        "fvg": smc.fvg(ohlc, join_consecutive=join_consecutive),
        "swings": swings,
        "bos_choch": smc.bos_choch(ohlc, swings),
        "ob": smc.ob(ohlc, swings),
        "liquidity": smc.liquidity(ohlc, swings),
        "previous_high_low": smc.previous_high_low(ohlc, time_frame=time_frame),
        "sessions": smc.sessions(ohlc, session=session),
        "retracements": smc.retracements(ohlc, swings),
    }


def parse_overlays(selected) -> set[str]:
    if not selected:
        return set(DEFAULT_OVERLAYS)
    return {name for name in selected if name in ALLOWED_OVERLAYS}


def _count_value(series: pd.Series, value: float) -> int:
    return int((series == value).sum())


def summarize_indicators(indicators: dict[str, pd.DataFrame]) -> dict[str, int]:
    fvg = indicators["fvg"]["FVG"]
    ob = indicators["ob"]["OB"]
    bos = indicators["bos_choch"]["BOS"]
    choch = indicators["bos_choch"]["CHOCH"]
    return {
        "bullish_fvg": _count_value(fvg, 1),
        "bearish_fvg": _count_value(fvg, -1),
        "bullish_ob": _count_value(ob, 1),
        "bearish_ob": _count_value(ob, -1),
        "bullish_bos": _count_value(bos, 1),
        "bearish_bos": _count_value(bos, -1),
        "bullish_choch": _count_value(choch, 1),
        "bearish_choch": _count_value(choch, -1),
        "swing_points": int(indicators["swings"]["HighLow"].notna().sum()),
    }


def build_dashboard_state(
    candles: int = 250,
    swing_length: int = 5,
    overlays=None,
    session: str = "London",
    time_frame: str = "4h",
    csv_path: os.PathLike | None = None,
    ohlc: pd.DataFrame | None = None,
    title: str | None = None,
) -> dict:
    from web.charts import build_figure

    if ohlc is None:
        frame = load_sample_ohlc(candles, csv_path=csv_path)
    else:
        frame = normalize_ohlc(ohlc)
        frame = frame.iloc[-max(int(candles), 20) :].copy()
    selected = parse_overlays(overlays)
    indicators = compute_indicators(
        frame,
        swing_length=swing_length,
        session=session,
        time_frame=time_frame,
    )
    last_row = frame.iloc[-1]
    return {
        "ohlc": frame,
        "indicators": indicators,
        "overlays": selected,
        "fig": build_figure(frame, indicators, selected, title=title),
        "stats": summarize_indicators(indicators),
        "last_close": float(last_row["close"]),
        "last_time": str(frame.index[-1]),
        "candle_count": int(len(frame)),
    }
