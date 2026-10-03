import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request

import pandas as pd

from web.dashboard import normalize_ohlc

COINGECKO_MARKETS_URL = (
    "https://api.coingecko.com/api/v3/coins/markets"
    "?vs_currency=usd&order=market_cap_desc&per_page=150&page=1&sparkline=false"
)
BINANCE_EXCHANGE_INFO_URL = "https://api.binance.com/api/v3/exchangeInfo"
BINANCE_TICKER_URL = "https://api.binance.com/api/v3/ticker/24hr"
BINANCE_KLINES_URL = "https://api.binance.com/api/v3/klines"
COINGECKO_SEARCH_URL = "https://api.coingecko.com/api/v3/search?query="
ALLOWED_INTERVALS = frozenset({"1m", "5m", "15m", "30m", "1h", "4h", "1d"})
SKIP_BASES = frozenset(
    {
        "usdt",
        "usdc",
        "dai",
        "fdusd",
        "usde",
        "tusd",
        "usds",
        "busd",
        "usdd",
        "pyusd",
        "usd1",
    }
)
SYMBOL_ALIASES = {
    "the-open-network": ("TONUSDT",),
    "polygon-ecosystem-token": ("POLUSDT", "MATICUSDT"),
    "matic-network": ("POLUSDT", "MATICUSDT"),
    "avalanche-2": ("AVAXUSDT",),
    "binancecoin": ("BNBUSDT",),
    "wrapped-bitcoin": ("WBTCUSDT",),
}
LEVERAGE_MARKERS = ("UPUSDT", "DOWNUSDT", "BULLUSDT", "BEARUSDT")
_CACHE: dict[str, tuple[float, object]] = {}


def clear_market_cache() -> None:
    _CACHE.clear()


def _cache_get(key: str, ttl: float):
    hit = _CACHE.get(key)
    if hit is None:
        return None
    stamped, value = hit
    if time.time() - stamped >= ttl:
        return None
    return value


def _cache_set(key: str, value: object) -> object:
    _CACHE[key] = (time.time(), value)
    return value


def fetch_json(url: str, timeout: int = 15):
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "smc-dashboard/1.0", "Accept": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"Market request failed ({exc.code})") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError("Market request failed") from exc


def normalize_search_query(query: str) -> str:
    return " ".join((query or "").strip().split()).lower()


def _coin_search_text(coin: dict) -> str:
    return " ".join(
        str(coin.get(key) or "")
        for key in ("name", "symbol", "binance_symbol", "id")
    ).lower()


def filter_coins(coins: list[dict], query: str) -> list[dict]:
    needle = normalize_search_query(query)
    if not needle:
        return list(coins)
    compact = re.sub(r"[^a-z0-9]", "", needle)
    matches = []
    for coin in coins:
        haystack = _coin_search_text(coin)
        compact_haystack = re.sub(r"[^a-z0-9]", "", haystack)
        if needle in haystack or (compact and compact in compact_haystack):
            matches.append(coin)
    return matches


def _match_score(coin: dict, needle: str, compact: str) -> int:
    symbol = str(coin.get("symbol") or "").lower()
    pair = str(coin.get("binance_symbol") or "").lower()
    name = str(coin.get("name") or "").lower()
    if needle == pair or compact == pair:
        return 100
    if needle == symbol or compact == symbol:
        return 90
    if name == needle:
        return 80
    if symbol.startswith(compact) or pair.startswith(compact) or name.startswith(needle):
        return 70
    return 50


def resolve_search_query(
    query: str,
    coins: list[dict] | None = None,
    usdt_symbols: set[str] | None = None,
) -> str | None:
    needle = normalize_search_query(query)
    if not needle:
        return None

    compact = re.sub(r"[^a-z0-9]", "", needle)
    if compact in SKIP_BASES:
        return None

    catalog = list(coins or [])
    if usdt_symbols:
        catalog = build_search_catalog(catalog, usdt_symbols)
    ranked = filter_coins(catalog, needle)
    if ranked:
        ranked.sort(key=lambda coin: _match_score(coin, needle, compact), reverse=True)
        pair = ranked[0].get("binance_symbol")
        if pair:
            return pair

    if not compact:
        return None
    candidate = compact.upper() if compact.endswith("usdt") else f"{compact.upper()}USDT"
    try:
        pair = sanitize_symbol(candidate)
    except ValueError:
        return None
    if usdt_symbols is not None and pair not in usdt_symbols:
        return None
    return pair


def catalog_from_symbols(usdt_symbols: set[str]) -> list[dict]:
    rows = []
    for pair in sorted(usdt_symbols):
        base = pair[:-4] if pair.endswith("USDT") else pair
        if base.lower() in SKIP_BASES:
            continue
        rows.append(
            {
                "name": base,
                "symbol": base,
                "binance_symbol": pair,
                "id": pair.lower(),
            }
        )
    return rows


def build_search_catalog(listed_coins: list[dict], usdt_symbols: set[str]) -> list[dict]:
    catalog = {row["binance_symbol"]: row for row in catalog_from_symbols(usdt_symbols)}
    for coin in listed_coins or []:
        pair = coin.get("binance_symbol")
        if not pair:
            continue
        current = catalog.get(pair, {})
        catalog[pair] = {
            "name": coin.get("name") or current.get("name") or pair.replace("USDT", ""),
            "symbol": coin.get("symbol") or current.get("symbol") or pair.replace("USDT", ""),
            "binance_symbol": pair,
            "id": coin.get("id") or current.get("id") or pair.lower(),
            "image": coin.get("image") or current.get("image"),
        }
    return list(catalog.values())


def suggest_coins(query: str, catalog: list[dict], limit: int = 12) -> list[dict]:
    needle = normalize_search_query(query)
    if not needle:
        return []
    compact = re.sub(r"[^a-z0-9]", "", needle)
    matches = filter_coins(catalog, needle)
    matches.sort(key=lambda coin: _match_score(coin, needle, compact), reverse=True)
    return matches[: max(int(limit), 1)]


def coins_from_gecko_search(hits: list, usdt_symbols: set[str]) -> list[dict]:
    mapped = []
    seen = set()
    for hit in hits or []:
        pair = binance_symbol_for_coin(hit, usdt_symbols)
        if not pair or pair in seen:
            continue
        seen.add(pair)
        mapped.append(
            {
                "name": hit.get("name") or pair.replace("USDT", ""),
                "symbol": str(hit.get("symbol") or "").upper(),
                "binance_symbol": pair,
                "id": hit.get("id"),
            }
        )
    return mapped


def search_coingecko_coins(query: str, fetch_json_fn=fetch_json) -> list[dict]:
    needle = normalize_search_query(query)
    if not needle:
        return []
    payload = fetch_json_fn(COINGECKO_SEARCH_URL + urllib.parse.quote(needle))
    if not isinstance(payload, dict):
        return []
    return payload.get("coins") or []


def sanitize_symbol(symbol: str) -> str:
    cleaned = (symbol or "").strip().upper()
    if not re.fullmatch(r"[A-Z0-9]{5,25}", cleaned) or not cleaned.endswith("USDT"):
        raise ValueError("Only USDT spot pairs are supported")
    if any(marker in cleaned for marker in LEVERAGE_MARKERS):
        raise ValueError("Leveraged tokens are not supported")
    return cleaned


def sanitize_interval(interval: str, default: str = "15m") -> str:
    value = (interval or default).strip()
    if value not in ALLOWED_INTERVALS:
        raise ValueError(f"Unsupported interval: {interval}")
    return value


def format_price(price) -> str:
    if price is None:
        return "—"
    number = float(price)
    if number >= 1000:
        return f"{number:,.2f}"
    if number >= 1:
        return f"{number:,.4f}"
    return f"{number:.8f}".rstrip("0").rstrip(".")


def format_compact(value) -> str:
    if value is None:
        return "—"
    number = float(value)
    abs_number = abs(number)
    if abs_number >= 1_000_000_000_000:
        return f"${number / 1_000_000_000_000:.2f}T"
    if abs_number >= 1_000_000_000:
        return f"${number / 1_000_000_000:.2f}B"
    if abs_number >= 1_000_000:
        return f"${number / 1_000_000:.2f}M"
    return f"${number:,.0f}"


def extract_usdt_symbols(exchange_info: dict) -> set[str]:
    symbols = set()
    for item in exchange_info.get("symbols", []):
        symbol = item.get("symbol", "")
        if (
            item.get("status") == "TRADING"
            and item.get("quoteAsset") == "USDT"
            and item.get("isSpotTradingAllowed", True)
            and symbol
            and not any(marker in symbol for marker in LEVERAGE_MARKERS)
        ):
            symbols.add(symbol)
    return symbols


def binance_symbol_for_coin(coin: dict, usdt_symbols: set[str]) -> str | None:
    coin_id = str(coin.get("id") or "").lower()
    base = str(coin.get("symbol") or "").lower()
    if base in SKIP_BASES:
        return None
    candidates = []
    candidates.extend(SYMBOL_ALIASES.get(coin_id, ()))
    if base:
        candidates.append(f"{base.upper()}USDT")
    for candidate in candidates:
        if candidate in usdt_symbols:
            return candidate
    return None


def coins_from_coingecko(markets: list, usdt_symbols: set[str], limit: int = 50) -> list[dict]:
    selected = []
    seen = set()
    for coin in markets:
        pair = binance_symbol_for_coin(coin, usdt_symbols)
        if pair is None or pair in seen:
            continue
        seen.add(pair)
        selected.append(
            {
                "rank": coin.get("market_cap_rank") or len(selected) + 1,
                "id": coin.get("id"),
                "name": coin.get("name") or pair.replace("USDT", ""),
                "symbol": str(coin.get("symbol") or "").upper(),
                "binance_symbol": pair,
                "price": coin.get("current_price"),
                "change_24h": coin.get("price_change_percentage_24h"),
                "market_cap": coin.get("market_cap"),
                "image": coin.get("image"),
            }
        )
        if len(selected) >= limit:
            break
    return selected


def coins_from_binance_tickers(
    tickers: list, usdt_symbols: set[str], limit: int = 50
) -> list[dict]:
    ranked = []
    for ticker in tickers:
        symbol = ticker.get("symbol")
        if symbol not in usdt_symbols:
            continue
        ranked.append(
            {
                "rank": 0,
                "id": symbol,
                "name": symbol.replace("USDT", ""),
                "symbol": symbol.replace("USDT", ""),
                "binance_symbol": symbol,
                "price": float(ticker.get("lastPrice") or 0),
                "change_24h": float(ticker.get("priceChangePercent") or 0),
                "market_cap": None,
                "image": None,
                "quote_volume": float(ticker.get("quoteVolume") or 0),
            }
        )
    ranked.sort(key=lambda row: row["quote_volume"], reverse=True)
    selected = ranked[:limit]
    for index, row in enumerate(selected, start=1):
        row["rank"] = index
    return selected


def merge_coin_lists(primary: list[dict], fallback: list[dict], limit: int = 50) -> list[dict]:
    merged = []
    seen = set()
    for row in list(primary) + list(fallback):
        symbol = row.get("binance_symbol")
        if not symbol or symbol in seen:
            continue
        seen.add(symbol)
        merged.append(row)
        if len(merged) >= limit:
            break
    return merged


def klines_to_ohlc(rows: list) -> pd.DataFrame:
    if not rows:
        raise ValueError("No kline data returned")
    frame = pd.DataFrame(
        rows,
        columns=[
            "open_time",
            "open",
            "high",
            "low",
            "close",
            "volume",
            "close_time",
            "quote_volume",
            "trades",
            "taker_base",
            "taker_quote",
            "ignore",
        ],
    )
    frame = frame.loc[:, ["open_time", "open", "high", "low", "close", "volume"]]
    frame["open_time"] = pd.to_datetime(frame["open_time"], unit="ms")
    for column in ("open", "high", "low", "close", "volume"):
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    frame = frame.rename(columns={"open_time": "date"})
    return normalize_ohlc(frame)


def get_usdt_symbols(fetch_json_fn=fetch_json, ttl: float = 600) -> set[str]:
    cached = _cache_get("usdt_symbols", ttl)
    if cached is not None:
        return cached
    info = fetch_json_fn(BINANCE_EXCHANGE_INFO_URL)
    return _cache_set("usdt_symbols", extract_usdt_symbols(info))


def get_top_coins(limit: int = 50, fetch_json_fn=fetch_json, ttl: float = 60) -> list[dict]:
    cache_key = f"top_coins:{limit}"
    cached = _cache_get(cache_key, ttl)
    if cached is not None:
        return cached

    usdt_symbols = get_usdt_symbols(fetch_json_fn=fetch_json_fn)
    gecko_coins = []
    try:
        gecko_coins = coins_from_coingecko(
            fetch_json_fn(COINGECKO_MARKETS_URL), usdt_symbols, limit=limit
        )
    except RuntimeError:
        gecko_coins = []

    if len(gecko_coins) >= limit:
        return _cache_set(cache_key, gecko_coins)

    fallback = coins_from_binance_tickers(
        fetch_json_fn(BINANCE_TICKER_URL), usdt_symbols, limit=limit
    )
    return _cache_set(cache_key, merge_coin_lists(gecko_coins, fallback, limit=limit))


def fetch_klines(
    symbol: str,
    interval: str = "15m",
    limit: int = 250,
    fetch_json_fn=fetch_json,
    ttl: float = 5,
) -> pd.DataFrame:
    pair = sanitize_symbol(symbol)
    candle_interval = sanitize_interval(interval)
    candles = min(max(int(limit), 20), 1000)
    cache_key = f"klines:{pair}:{candle_interval}:{candles}"
    cached = _cache_get(cache_key, ttl)
    if cached is not None:
        return cached.copy()

    url = (
        f"{BINANCE_KLINES_URL}?symbol={pair}&interval={candle_interval}&limit={candles}"
    )
    rows = fetch_json_fn(url)
    if not isinstance(rows, list):
        raise RuntimeError("Unexpected kline response")
    frame = klines_to_ohlc(rows)
    return _cache_set(cache_key, frame).copy()
