import os
import sys

import pandas as pd
import pytest

BASE_DIR = os.path.dirname(__file__)
ROOT = os.path.abspath(os.path.join(BASE_DIR, ".."))
sys.path.insert(0, ROOT)

from web.app import present_coins
from web.dashboard import build_dashboard_state
from web.market import (
    binance_symbol_for_coin,
    coins_from_binance_tickers,
    coins_from_coingecko,
    extract_usdt_symbols,
    fetch_klines,
    format_compact,
    format_price,
    get_top_coins,
    klines_to_ohlc,
    merge_coin_lists,
    sanitize_interval,
    sanitize_symbol,
    clear_market_cache,
)


@pytest.fixture(autouse=True)
def _clear_cache():
    clear_market_cache()
    yield
    clear_market_cache()


def test_sanitize_symbol_accepts_usdt_spot_only():
    assert sanitize_symbol("btcusdt") == "BTCUSDT"
    with pytest.raises(ValueError):
        sanitize_symbol("EURUSD")
    with pytest.raises(ValueError):
        sanitize_symbol("BTCUPUSDT")


def test_sanitize_interval_rejects_unknown():
    assert sanitize_interval("15m") == "15m"
    with pytest.raises(ValueError):
        sanitize_interval("3w")


def test_format_helpers():
    assert format_price(67000) == "67,000.00"
    assert format_price(1.23456) == "1.2346"
    assert format_price(0.0001234000) == "0.0001234"
    assert format_compact(1.2e12) == "$1.20T"
    assert format_compact(4.5e9) == "$4.50B"


def test_extract_usdt_symbols_skips_leverage_and_non_usdt():
    symbols = extract_usdt_symbols(
        {
            "symbols": [
                {
                    "symbol": "BTCUSDT",
                    "status": "TRADING",
                    "quoteAsset": "USDT",
                    "isSpotTradingAllowed": True,
                },
                {
                    "symbol": "ETHBTC",
                    "status": "TRADING",
                    "quoteAsset": "BTC",
                    "isSpotTradingAllowed": True,
                },
                {
                    "symbol": "BTCUPUSDT",
                    "status": "TRADING",
                    "quoteAsset": "USDT",
                    "isSpotTradingAllowed": True,
                },
            ]
        }
    )
    assert symbols == {"BTCUSDT"}


def test_binance_symbol_for_coin_skips_stables_and_uses_alias():
    usdt = {"TONUSDT", "BTCUSDT"}
    assert binance_symbol_for_coin({"id": "tether", "symbol": "usdt"}, usdt) is None
    assert (
        binance_symbol_for_coin({"id": "the-open-network", "symbol": "ton"}, usdt)
        == "TONUSDT"
    )
    assert binance_symbol_for_coin({"id": "bitcoin", "symbol": "btc"}, usdt) == "BTCUSDT"


def test_coins_from_coingecko_returns_tradeable_top_list():
    markets = [
        {
            "id": "tether",
            "symbol": "usdt",
            "name": "Tether",
            "market_cap_rank": 3,
            "current_price": 1,
            "price_change_percentage_24h": 0.01,
            "market_cap": 100,
            "image": None,
        },
        {
            "id": "bitcoin",
            "symbol": "btc",
            "name": "Bitcoin",
            "market_cap_rank": 1,
            "current_price": 60000,
            "price_change_percentage_24h": 1.5,
            "market_cap": 1.2e12,
            "image": "btc.png",
        },
        {
            "id": "offline-coin",
            "symbol": "zzz",
            "name": "Offline",
            "market_cap_rank": 2,
            "current_price": 3,
            "price_change_percentage_24h": -1,
            "market_cap": 10,
            "image": None,
        },
    ]
    coins = coins_from_coingecko(markets, {"BTCUSDT"}, limit=50)
    assert [coin["binance_symbol"] for coin in coins] == ["BTCUSDT"]
    assert coins[0]["name"] == "Bitcoin"


def test_coins_from_binance_tickers_orders_by_quote_volume():
    tickers = [
        {"symbol": "ETHUSDT", "lastPrice": "2", "priceChangePercent": "1", "quoteVolume": "10"},
        {"symbol": "BTCUSDT", "lastPrice": "3", "priceChangePercent": "-1", "quoteVolume": "99"},
        {"symbol": "XRPBTC", "lastPrice": "1", "priceChangePercent": "0", "quoteVolume": "1000"},
    ]
    coins = coins_from_binance_tickers(tickers, {"ETHUSDT", "BTCUSDT"}, limit=50)
    assert [coin["binance_symbol"] for coin in coins] == ["BTCUSDT", "ETHUSDT"]
    assert coins[0]["rank"] == 1


def test_merge_coin_lists_fills_until_limit():
    merged = merge_coin_lists(
        [{"binance_symbol": "BTCUSDT", "name": "Bitcoin"}],
        [
            {"binance_symbol": "BTCUSDT", "name": "Dup"},
            {"binance_symbol": "ETHUSDT", "name": "Ethereum"},
        ],
        limit=2,
    )
    assert [coin["binance_symbol"] for coin in merged] == ["BTCUSDT", "ETHUSDT"]


def test_klines_to_ohlc_builds_datetime_index():
    rows = [
        [1700000000000, "1", "2", "0.5", "1.5", "10", 0, 0, 0, 0, 0, 0],
        [1700000900000, "1.5", "2.2", "1.4", "2.0", "11", 0, 0, 0, 0, 0, 0],
    ]
    frame = klines_to_ohlc(rows)
    assert list(frame.columns) == ["open", "high", "low", "close", "volume"]
    assert len(frame) == 2
    assert pd.api.types.is_datetime64_any_dtype(frame.index)
    assert frame["close"].iloc[-1] == 2.0


def test_klines_to_ohlc_rejects_empty():
    with pytest.raises(ValueError, match="No kline data"):
        klines_to_ohlc([])


def test_get_top_coins_uses_gecko_when_enough_pairs():
    def fake_fetch(url: str):
        if "exchangeInfo" in url:
            return {
                "symbols": [
                    {
                        "symbol": "BTCUSDT",
                        "status": "TRADING",
                        "quoteAsset": "USDT",
                        "isSpotTradingAllowed": True,
                    }
                ]
            }
        if "coingecko" in url:
            return [
                {
                    "id": "bitcoin",
                    "symbol": "btc",
                    "name": "Bitcoin",
                    "market_cap_rank": 1,
                    "current_price": 60000,
                    "price_change_percentage_24h": 1.2,
                    "market_cap": 1.1e12,
                    "image": None,
                }
            ]
        raise AssertionError(f"unexpected url {url}")

    coins = get_top_coins(limit=1, fetch_json_fn=fake_fetch, ttl=0)
    assert coins[0]["binance_symbol"] == "BTCUSDT"


def test_get_top_coins_falls_back_to_binance_tickers():
    def fake_fetch(url: str):
        if "exchangeInfo" in url:
            return {
                "symbols": [
                    {
                        "symbol": "ETHUSDT",
                        "status": "TRADING",
                        "quoteAsset": "USDT",
                        "isSpotTradingAllowed": True,
                    }
                ]
            }
        if "coingecko" in url:
            raise RuntimeError("Market request failed")
        if "ticker/24hr" in url:
            return [
                {
                    "symbol": "ETHUSDT",
                    "lastPrice": "3000",
                    "priceChangePercent": "2.5",
                    "quoteVolume": "500",
                }
            ]
        raise AssertionError(f"unexpected url {url}")

    coins = get_top_coins(limit=1, fetch_json_fn=fake_fetch, ttl=0)
    assert coins[0]["binance_symbol"] == "ETHUSDT"
    assert coins[0]["price"] == 3000


def test_fetch_klines_uses_injected_client():
    def fake_fetch(url: str):
        assert "symbol=BTCUSDT" in url
        assert "interval=15m" in url
        return [[1700000000000, "1", "2", "0.5", "1.5", "10", 0, 0, 0, 0, 0, 0]]

    frame = fetch_klines("btcusdt", interval="15m", limit=50, fetch_json_fn=fake_fetch, ttl=0)
    assert frame["close"].iloc[0] == 1.5


def test_build_dashboard_state_uses_provided_ohlc():
    ohlc = klines_to_ohlc(
        [
            [1700000000000 + i * 60000, "1", "1.2", "0.9", "1.1", "5", 0, 0, 0, 0, 0, 0]
            for i in range(40)
        ]
    )
    state = build_dashboard_state(candles=40, overlays=["fvg"], ohlc=ohlc, title="BTCUSDT · 15m")
    assert state["candle_count"] == 40
    assert state["fig"].layout.title.text == "BTCUSDT · 15m"


def test_present_coins_adds_open_chart_links():
    rows = present_coins(
        [
            {
                "rank": 9,
                "name": "Bitcoin",
                "symbol": "BTC",
                "binance_symbol": "BTCUSDT",
                "price": 60000,
                "change_24h": 1.25,
                "market_cap": 1.2e12,
                "image": None,
            }
        ]
    )
    assert rows[0]["chart_url"] == "/chart/BTCUSDT"
    assert rows[0]["rank"] == 1
    assert rows[0]["price_text"] == "60,000.00"
    assert rows[0]["change_class"] == "up"
