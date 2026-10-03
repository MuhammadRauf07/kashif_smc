import os
import sys

import pytest

BASE_DIR = os.path.dirname(__file__)
ROOT = os.path.abspath(os.path.join(BASE_DIR, ".."))
sys.path.insert(0, ROOT)

from web.market import (
    build_search_catalog,
    coins_from_gecko_search,
    filter_coins,
    normalize_search_query,
    resolve_search_query,
    suggest_coins,
)


SAMPLE_COINS = [
    {
        "name": "Bitcoin",
        "symbol": "BTC",
        "binance_symbol": "BTCUSDT",
        "id": "bitcoin",
    },
    {
        "name": "Ethereum",
        "symbol": "ETH",
        "binance_symbol": "ETHUSDT",
        "id": "ethereum",
    },
    {
        "name": "Solana",
        "symbol": "SOL",
        "binance_symbol": "SOLUSDT",
        "id": "solana",
    },
]


def test_normalize_search_query_trims_and_lowers():
    assert normalize_search_query("  BTC  ") == "btc"
    assert normalize_search_query("") == ""


def test_filter_coins_empty_query_returns_all():
    assert filter_coins(SAMPLE_COINS, "   ") == SAMPLE_COINS


def test_filter_coins_matches_name_symbol_and_pair():
    assert [coin["symbol"] for coin in filter_coins(SAMPLE_COINS, "ether")] == ["ETH"]
    assert [coin["symbol"] for coin in filter_coins(SAMPLE_COINS, "btc")] == ["BTC"]
    assert [coin["symbol"] for coin in filter_coins(SAMPLE_COINS, "solusdt")] == ["SOL"]


def test_resolve_search_query_prefers_listed_coin_names():
    assert resolve_search_query("ethereum", coins=SAMPLE_COINS) == "ETHUSDT"
    assert resolve_search_query("BTC/USDT", coins=SAMPLE_COINS) == "BTCUSDT"


def test_resolve_search_query_opens_unlisted_manual_symbol():
    assert resolve_search_query("pepe", coins=SAMPLE_COINS) == "PEPEUSDT"
    assert resolve_search_query("dogeusdt", coins=[]) == "DOGEUSDT"


def test_resolve_search_query_rejects_empty_and_stables():
    assert resolve_search_query("   ", coins=SAMPLE_COINS) is None
    assert resolve_search_query("usdt", coins=SAMPLE_COINS) is None
    assert resolve_search_query("usdc", coins=SAMPLE_COINS) is None


def test_resolve_search_query_respects_usdt_allowlist():
    assert (
        resolve_search_query("xyz", coins=[], usdt_symbols={"BTCUSDT"}) is None
    )
    assert (
        resolve_search_query("btc", coins=[], usdt_symbols={"BTCUSDT"}) == "BTCUSDT"
    )


def test_search_catalog_includes_all_usdt_pairs_not_just_top_list():
    catalog = build_search_catalog(
        SAMPLE_COINS,
        {"BTCUSDT", "ETHUSDT", "SOLUSDT", "PEPEUSDT", "WIFUSDT", "ARBUSDT"},
    )
    pairs = {coin["binance_symbol"] for coin in catalog}
    assert {"PEPEUSDT", "WIFUSDT", "ARBUSDT", "BTCUSDT"}.issubset(pairs)
    bitcoin = next(coin for coin in catalog if coin["binance_symbol"] == "BTCUSDT")
    assert bitcoin["name"] == "Bitcoin"


def test_suggest_coins_finds_unlisted_pairs():
    catalog = build_search_catalog([], {"PEPEUSDT", "PENDLEUSDT", "BTCUSDT"})
    names = [coin["binance_symbol"] for coin in suggest_coins("pepe", catalog)]
    assert names[0] == "PEPEUSDT"


def test_coins_from_gecko_search_maps_name_to_binance_pair():
    mapped = coins_from_gecko_search(
        [{"id": "avalanche-2", "symbol": "avax", "name": "Avalanche"}],
        {"AVAXUSDT"},
    )
    assert mapped[0]["binance_symbol"] == "AVAXUSDT"
