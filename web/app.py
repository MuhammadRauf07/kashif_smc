import json
import os
import sys
from urllib.parse import urlencode

from flask import Flask, jsonify, redirect, render_template_string, request

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from web.dashboard import ALLOWED_OVERLAYS, build_dashboard_state
from web.charts import CHART_HEIGHT, PLOTLY_CONFIG
from web.market import (
    build_search_catalog,
    coins_from_gecko_search,
    fetch_klines,
    format_compact,
    format_price,
    get_top_coins,
    get_usdt_symbols,
    resolve_search_query,
    sanitize_interval,
    sanitize_symbol,
    search_coingecko_coins,
    suggest_coins,
)

app = Flask(__name__)

SHARED_CSS = """
:root {
  --bg: #0c0e12;
  --panel: #151922;
  --line: #242a36;
  --text: #e8edf5;
  --muted: #93a0b5;
  --accent: #7dd3a8;
  --down: #ff6962;
}
* { box-sizing: border-box; }
body {
  margin: 0;
  background: var(--bg);
  color: var(--text);
  font-family: "Segoe UI", sans-serif;
}
.wrap { max-width: 1280px; margin: 0 auto; padding: 24px; }
h1 { margin: 0 0 8px; font-size: 28px; }
p { color: var(--muted); margin-top: 0; }
a { color: var(--accent); }
.panel, form, .stats, .chart, .error {
  background: var(--panel);
  border: 1px solid var(--line);
  border-radius: 14px;
  padding: 16px;
  margin-bottom: 16px;
}
.row { display: flex; flex-wrap: wrap; gap: 16px; align-items: end; }
label { display: block; font-size: 12px; color: var(--muted); margin-bottom: 6px; }
input, select {
  background: #0c0e12;
  color: var(--text);
  border: 1px solid var(--line);
  border-radius: 8px;
  padding: 8px 10px;
}
.checks { display: flex; flex-wrap: wrap; gap: 10px 16px; }
.checks label { color: var(--text); font-size: 14px; }
button, .btn {
  background: var(--accent);
  color: #0c0e12;
  border: 0;
  border-radius: 8px;
  padding: 8px 14px;
  font-weight: 700;
  cursor: pointer;
  text-decoration: none;
  display: inline-block;
}
.stats { display: grid; grid-template-columns: repeat(auto-fit, minmax(140px, 1fr)); gap: 12px; }
.stat { background: #0c0e12; border-radius: 10px; padding: 12px; }
.stat span { display: block; color: var(--muted); font-size: 12px; }
.stat strong { font-size: 22px; }
table { width: 100%; border-collapse: collapse; }
th, td { padding: 12px; border-bottom: 1px solid var(--line); text-align: left; }
th { color: var(--muted); font-size: 12px; font-weight: 600; }
tr:hover td { background: #1b2130; }
.coin { display: flex; align-items: center; gap: 10px; }
.coin img { width: 28px; height: 28px; border-radius: 50%; }
.up { color: var(--accent); }
.down { color: var(--down); }
.live { color: var(--accent); font-weight: 700; }
.header-row { display: flex; justify-content: space-between; gap: 12px; align-items: start; flex-wrap: wrap; }
.search-bar { display: flex; flex-wrap: wrap; gap: 10px; align-items: center; margin-bottom: 16px; }
.search-bar input[type="search"] { flex: 1; min-width: 220px; padding: 10px 12px; }
.search-note { color: var(--muted); font-size: 13px; margin: 0 0 12px; }
.search-wrap { position: relative; flex: 1; min-width: 220px; }
.suggest {
  position: absolute;
  left: 0;
  right: 0;
  top: calc(100% + 4px);
  background: #151922;
  border: 1px solid var(--line);
  border-radius: 8px;
  z-index: 30;
  max-height: 280px;
  overflow: auto;
}
.suggest button {
  display: block;
  width: 100%;
  text-align: left;
  background: transparent;
  color: var(--text);
  font-weight: 500;
  border-radius: 0;
}
.suggest button:hover { background: #1b2130; }
html, body { height: 100%; }
body.chart-body { overflow: hidden; }
.chart-shell {
  height: 100%;
  display: flex;
  flex-direction: column;
  min-height: 0;
  padding: 8px 10px 0;
}
.chart-shell .chart-toolbar { flex: 0 0 auto; }
.chart-shell form, .chart-shell .stats {
  margin-bottom: 8px;
  padding: 8px 10px;
}
.chart-shell .stats { gap: 8px; }
.chart-shell .stat { padding: 6px 8px; }
.chart-shell .stat strong { font-size: 16px; }
.chart-fill {
  position: relative;
  flex: 1 1 auto;
  min-height: 0;
  margin: 0 -10px 0;
  padding: 0;
  border-radius: 12px 12px 0 0;
  border-left: 0;
  border-right: 0;
  border-bottom: 0;
}
#live-chart { width: 100%; height: 100%; }
.chart-pane {
  flex: 1 1 auto;
  display: flex;
  flex-direction: column;
  min-height: 0;
  margin: 0 -10px 0;
  position: relative;
}
.chart-pane .chart-fill {
  margin: 0;
  border-radius: 12px 12px 0 0;
}
.chart-resize {
  position: sticky;
  bottom: 0;
  flex: 0 0 18px;
  height: 18px;
  cursor: ns-resize;
  z-index: 40;
  background: #121722;
  border-top: 1px solid var(--line);
  user-select: none;
  touch-action: none;
}
.chart-resize::before {
  content: "";
  position: absolute;
  left: 0;
  right: 0;
  top: -10px;
  height: 28px;
}
.chart-resize::after {
  content: "";
  display: block;
  width: 52px;
  height: 4px;
  margin: 7px auto 0;
  border-radius: 999px;
  background: #8b95a8;
}
.chart-resize:hover,
.chart-resize.dragging {
  background: #1b2230;
}
.chart-resize:hover::after,
.chart-resize.dragging::after {
  background: #7dd3a8;
  width: 72px;
}
"""

LIST_PAGE = """
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Top 50 Crypto · SMC</title>
  <style>{{ css }}</style>
</head>
<body>
  <div class="wrap">
    <h1>Top 50 Crypto</h1>
    <p>Market-cap leaders plus search for any Binance USDT crypto pair.</p>
    {% if error %}
    <div class="error">{{ error }}</div>
    {% endif %}
    {% if search_error %}
    <div class="error">{{ search_error }}</div>
    {% endif %}
    <form class="search-bar panel" method="get" action="/search">
      <div class="search-wrap">
        <input id="coin-search" name="q" type="search" placeholder="Search any crypto (PEPE, WIF, Avalanche, ARBUSDT)" value="{{ query }}" autocomplete="off">
        <div id="search-suggest" class="suggest" hidden></div>
      </div>
      <button type="submit">Open Chart</button>
    </form>
    <p class="search-note">Search is global across Binance USDT coins, not only this top list. Type to filter the table or pick a suggestion.</p>
    <div class="panel">
      <table>
        <thead>
          <tr>
            <th>#</th>
            <th>Coin</th>
            <th>Price</th>
            <th>24h</th>
            <th>Market cap</th>
            <th></th>
          </tr>
        </thead>
        <tbody id="coin-rows">
          {% for coin in coins %}
          <tr data-search="{{ coin.name }} {{ coin.symbol }} {{ coin.binance_symbol }}">
            <td>{{ coin.rank }}</td>
            <td>
              <div class="coin">
                {% if coin.image %}<img src="{{ coin.image }}" alt="{{ coin.symbol }}">{% endif %}
                <div>
                  <strong>{{ coin.name }}</strong><br>
                  <span>{{ coin.symbol }} · {{ coin.binance_symbol }}</span>
                </div>
              </div>
            </td>
            <td>{{ coin.price_text }}</td>
            <td class="{{ coin.change_class }}">{{ coin.change_text }}</td>
            <td>{{ coin.market_cap_text }}</td>
            <td><a class="btn" href="{{ coin.chart_url }}">Open Chart</a></td>
          </tr>
          {% endfor %}
        </tbody>
      </table>
    </div>
  </div>
  <script>
    {{ search_js|safe }}
    bindCoinSearch("coin-search", "search-suggest");
    const searchInput = document.getElementById("coin-search");
    const rows = Array.from(document.querySelectorAll("#coin-rows tr"));
    searchInput.addEventListener("input", () => {
      const needle = searchInput.value.trim().toLowerCase().replace(/[^a-z0-9]/g, "");
      rows.forEach((row) => {
        const hay = (row.dataset.search || "").toLowerCase().replace(/[^a-z0-9]/g, "");
        row.style.display = !needle || hay.includes(needle) ? "" : "none";
      });
    });
  </script>
</body>
</html>
"""

SEARCH_JS = """
function bindCoinSearch(inputId, suggestId) {
  const input = document.getElementById(inputId);
  const box = document.getElementById(suggestId);
  if (!input || !box) return;
  let timer = null;
  async function loadSuggest() {
    const query = input.value.trim();
    if (query.length < 1) {
      box.hidden = true;
      box.innerHTML = "";
      return;
    }
    const response = await fetch("/api/search?q=" + encodeURIComponent(query));
    if (!response.ok) return;
    const rows = await response.json();
    box.innerHTML = rows.map((row) => (
      '<button type="button" data-pair="' + row.binance_symbol + '">' +
      row.name + " · " + row.symbol + " · " + row.binance_symbol +
      "</button>"
    )).join("");
    box.hidden = rows.length === 0;
    box.querySelectorAll("button").forEach((button) => {
      button.addEventListener("click", () => {
        window.location.href = "/chart/" + button.dataset.pair;
      });
    });
  }
  input.addEventListener("input", () => {
    clearTimeout(timer);
    timer = setTimeout(loadSuggest, 200);
  });
  input.addEventListener("focus", loadSuggest);
  document.addEventListener("click", (event) => {
    if (!box.contains(event.target) && event.target !== input) {
      box.hidden = true;
    }
  });
}
"""

CHART_PAGE = """
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{{ symbol }} live · SMC</title>
  <script src="https://cdn.plot.ly/plotly-2.35.2.min.js"></script>
  <style>{{ css }}</style>
</head>
<body class="chart-body">
  <div class="chart-shell">
    <div class="chart-toolbar">
      <div class="header-row">
        <div>
          <h1>{{ display_name }}</h1>
          <p>
            <span class="live">LIVE</span>
            Binance {{ symbol }} · {{ interval }} · last candle {{ last_time }} at {{ last_close }}.
            Updated <span id="last-updated">just now</span>. Scroll to zoom. Drag the bar under the chart to resize height.
          </p>
        </div>
        <div>
          <form class="search-bar" method="get" action="/search" style="margin:0;">
            <div class="search-wrap">
              <input id="chart-search" name="q" type="search" placeholder="Search any crypto" autocomplete="off">
              <div id="chart-suggest" class="suggest" hidden></div>
            </div>
            <button type="submit">Open Chart</button>
          </form>
          <a class="btn" href="/" style="margin-top:8px;">Back to Top 50</a>
        </div>
      </div>
      <form method="get">
        <div class="row">
          <div>
            <label for="interval">Chart interval</label>
            <select id="interval" name="interval">
              {% for name in intervals %}
              <option value="{{ name }}" {% if name == interval %}selected{% endif %}>{{ name }}</option>
              {% endfor %}
            </select>
          </div>
          <div>
            <label for="candles">Candles</label>
            <input id="candles" name="candles" type="number" min="50" max="800" value="{{ candles }}">
          </div>
          <div>
            <label for="swing_length">Swing length</label>
            <input id="swing_length" name="swing_length" type="number" min="1" max="50" value="{{ swing_length }}">
          </div>
          <div>
            <label for="session">Session</label>
            <select id="session" name="session">
              {% for name in sessions %}
              <option value="{{ name }}" {% if name == session %}selected{% endif %}>{{ name }}</option>
              {% endfor %}
            </select>
          </div>
          <div>
            <label for="time_frame">Previous high/low TF</label>
            <select id="time_frame" name="time_frame">
              {% for name in time_frames %}
              <option value="{{ name }}" {% if name == time_frame %}selected{% endif %}>{{ name }}</option>
              {% endfor %}
            </select>
          </div>
          <label style="color:var(--text);">
            <input id="live-toggle" type="checkbox" checked> Auto refresh
          </label>
          <button type="submit">Update chart</button>
        </div>
        <div class="checks" style="margin-top:8px;">
          {% for name, label in overlay_labels %}
          <label><input type="checkbox" name="overlay" value="{{ name }}" {% if name in overlays %}checked{% endif %}> {{ label }}</label>
          {% endfor %}
        </div>
      </form>
      <div class="stats">
        <div class="stat"><span>Candles</span><strong id="stat-candles">{{ candle_count }}</strong></div>
        <div class="stat"><span>Last close</span><strong id="stat-close">{{ last_close }}</strong></div>
        <div class="stat"><span>Swing points</span><strong id="stat-swings">{{ stats.swing_points }}</strong></div>
        <div class="stat"><span>Bull / Bear FVG</span><strong id="stat-fvg">{{ stats.bullish_fvg }} / {{ stats.bearish_fvg }}</strong></div>
        <div class="stat"><span>Bull / Bear OB</span><strong id="stat-ob">{{ stats.bullish_ob }} / {{ stats.bearish_ob }}</strong></div>
        <div class="stat"><span>BOS</span><strong id="stat-bos">{{ stats.bullish_bos }} / {{ stats.bearish_bos }}</strong></div>
        <div class="stat"><span>CHoCH</span><strong id="stat-choch">{{ stats.bullish_choch }} / {{ stats.bearish_choch }}</strong></div>
      </div>
    </div>
    <div class="chart-pane">
      <div class="chart chart-fill" id="chart-fill">
        <div id="live-chart" data-api="{{ api_url }}"></div>
      </div>
      <div id="chart-resize" class="chart-resize" role="separator" aria-orientation="horizontal" aria-label="Resize chart height" title="Drag to resize chart height"></div>
    </div>
  </div>
  <script>
    {{ search_js|safe }}
    bindCoinSearch("chart-search", "chart-suggest");
    const initial = {{ figure_json|safe }};
    const plotConfig = {{ plot_config|safe }};
    const heightCfg = {{ chart_height_config|safe }};
    const chartNode = document.getElementById("live-chart");
    const chartFill = document.getElementById("chart-fill");
    const resizeHandle = document.getElementById("chart-resize");
    let userHeight = null;

    function clampHeight(value) {
      return Math.min(Math.max(Math.round(Number(value) || heightCfg.min), heightCfg.min), heightCfg.max);
    }

    function defaultFillHeight() {
      return Math.max(chartFill.clientHeight || 0, heightCfg.min);
    }

    function chartHeight() {
      return userHeight || defaultFillHeight();
    }

    function applyHeight(value, persist) {
      userHeight = clampHeight(value);
      chartFill.style.flex = "none";
      chartFill.style.height = userHeight + "px";
      document.body.style.overflowY = "auto";
      Plotly.relayout(chartNode, {autosize: true, height: userHeight});
      if (persist !== false) {
        localStorage.setItem("smcChartHeight", String(userHeight));
      }
    }

    function applyStats(payload) {
      document.getElementById("stat-candles").textContent = payload.candle_count;
      document.getElementById("stat-close").textContent = payload.last_close;
      document.getElementById("stat-swings").textContent = payload.stats.swing_points;
      document.getElementById("stat-fvg").textContent = payload.stats.bullish_fvg + " / " + payload.stats.bearish_fvg;
      document.getElementById("stat-ob").textContent = payload.stats.bullish_ob + " / " + payload.stats.bearish_ob;
      document.getElementById("stat-bos").textContent = payload.stats.bullish_bos + " / " + payload.stats.bearish_bos;
      document.getElementById("stat-choch").textContent = payload.stats.bullish_choch + " / " + payload.stats.bearish_choch;
      document.getElementById("last-updated").textContent = new Date().toLocaleTimeString();
    }

    initial.layout.autosize = true;
    initial.layout.height = chartHeight();
    initial.layout.uirevision = "smc-keep-view";
    Plotly.newPlot(chartNode, initial.data, initial.layout, plotConfig).then(() => {
      const saved = Number(localStorage.getItem("smcChartHeight"));
      if (saved) applyHeight(saved);
      resizeHandle.scrollIntoView({ block: "end" });
    });

    let drag = null;
    resizeHandle.addEventListener("pointerdown", (event) => {
      event.preventDefault();
      try { resizeHandle.setPointerCapture(event.pointerId); } catch (err) {}
      drag = { startY: event.clientY, startH: userHeight || defaultFillHeight() };
      resizeHandle.classList.add("dragging");
    });
    resizeHandle.addEventListener("pointermove", (event) => {
      if (!drag) return;
      applyHeight(drag.startH + (event.clientY - drag.startY), false);
    });
    function endDrag() {
      if (!drag) return;
      resizeHandle.classList.remove("dragging");
      if (userHeight) localStorage.setItem("smcChartHeight", String(userHeight));
      drag = null;
    }
    resizeHandle.addEventListener("pointerup", endDrag);
    resizeHandle.addEventListener("pointercancel", endDrag);
    resizeHandle.addEventListener("dblclick", () => {
      userHeight = null;
      chartFill.style.flex = "1 1 auto";
      chartFill.style.height = "";
      document.body.style.overflowY = "hidden";
      localStorage.removeItem("smcChartHeight");
      fitChart();
    });

    function fitChart() {
      Plotly.relayout(chartNode, {autosize: true, height: chartHeight()});
    }
    window.addEventListener("resize", fitChart);

    async function refreshChart() {
      const response = await fetch(chartNode.dataset.api);
      if (!response.ok) return;
      const payload = await response.json();
      payload.figure.layout.autosize = true;
      payload.figure.layout.height = chartHeight();
      payload.figure.layout.uirevision = "smc-keep-view";
      Plotly.react(chartNode, payload.figure.data, payload.figure.layout, plotConfig);
      applyStats(payload);
    }

    let timer = setInterval(refreshChart, 15000);
    document.getElementById("live-toggle").addEventListener("change", (event) => {
      if (event.target.checked) {
        refreshChart();
        timer = setInterval(refreshChart, 15000);
      } else {
        clearInterval(timer);
      }
    });
  </script>
</body>
</html>
"""

ERROR_PAGE = """
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Chart unavailable</title>
  <style>{{ css }}</style>
</head>
<body>
  <div class="wrap">
    <h1>Live chart unavailable</h1>
    <div class="error">{{ error }}</div>
    <a class="btn" href="/">Back to Top 50</a>
  </div>
</body>
</html>
"""

OVERLAY_LABELS = (
    ("fvg", "Fair Value Gap"),
    ("swings", "Swing highs / lows"),
    ("bos_choch", "BOS / CHoCH"),
    ("ob", "Order blocks"),
    ("liquidity", "Liquidity"),
    ("previous_high_low", "Previous high / low"),
    ("sessions", "Session"),
    ("retracements", "Retracements"),
)
SESSIONS = (
    "London",
    "New York",
    "Tokyo",
    "Sydney",
    "Asian kill zone",
    "London open kill zone",
    "New York kill zone",
    "london close kill zone",
)
TIME_FRAMES = ("15min", "1h", "4h", "1D", "1W")
INTERVALS = ("5m", "15m", "1h", "4h", "1d")


def parse_chart_args(args):
    session = args.get("session", "London")
    time_frame = args.get("time_frame", "4h")
    interval = args.get("interval", "15m")
    if session not in SESSIONS:
        session = "London"
    if time_frame not in TIME_FRAMES:
        time_frame = "4h"
    if interval not in INTERVALS:
        interval = "15m"
    return {
        "candles": min(max(args.get("candles", 250, type=int) or 250, 50), 800),
        "swing_length": min(max(args.get("swing_length", 5, type=int) or 5, 1), 50),
        "session": session,
        "time_frame": time_frame,
        "interval": interval,
        "overlays": args.getlist("overlay"),
    }


def change_class(change) -> str:
    if change is None:
        return ""
    return "up" if float(change) >= 0 else "down"


def change_text(change) -> str:
    if change is None:
        return "—"
    return f"{float(change):+.2f}%"


def present_coins(coins: list[dict]) -> list[dict]:
    presented = []
    for coin in coins:
        row = dict(coin)
        row["price_text"] = format_price(coin.get("price"))
        row["change_text"] = change_text(coin.get("change_24h"))
        row["change_class"] = change_class(coin.get("change_24h"))
        row["market_cap_text"] = format_compact(coin.get("market_cap"))
        row["chart_url"] = f"/chart/{coin['binance_symbol']}"
        presented.append(row)
    for index, row in enumerate(presented, start=1):
        row["rank"] = index
    return presented


def serialize_state(state: dict) -> dict:
    return {
        "figure": json.loads(state["fig"].to_json()),
        "stats": state["stats"],
        "last_close": format_price(state["last_close"]),
        "last_time": state["last_time"],
        "candle_count": state["candle_count"],
    }


def build_live_state(symbol: str, params: dict) -> dict:
    pair = sanitize_symbol(symbol)
    interval = sanitize_interval(params["interval"])
    ohlc = fetch_klines(pair, interval=interval, limit=params["candles"])
    return build_dashboard_state(
        candles=params["candles"],
        swing_length=params["swing_length"],
        overlays=params["overlays"] or None,
        session=params["session"],
        time_frame=params["time_frame"],
        ohlc=ohlc,
        title=f"{pair} · {interval}",
    )


def render_coin_list(error=None, search_error=None, query=""):
    coins = []
    try:
        coins = present_coins(get_top_coins(limit=50))
    except Exception:
        error = error or "Top 50 coins could not be loaded from CoinGecko/Binance. Refresh in a moment."
    return render_template_string(
        LIST_PAGE,
        css=SHARED_CSS,
        coins=coins,
        error=error,
        search_error=search_error,
        query=query or "",
        search_js=SEARCH_JS,
    )


@app.route("/", methods=["GET"])
def index():
    return render_coin_list()


def load_search_catalog() -> tuple[list[dict], set[str]]:
    usdt_symbols: set[str] = set()
    listed: list[dict] = []
    try:
        usdt_symbols = get_usdt_symbols()
    except Exception:
        usdt_symbols = set()
    try:
        listed = get_top_coins(limit=50)
    except Exception:
        listed = []
    return build_search_catalog(listed, usdt_symbols), usdt_symbols


@app.route("/search", methods=["GET"])
def search_coin():
    query = request.args.get("q", "")
    catalog, usdt_symbols = load_search_catalog()
    pair = resolve_search_query(query, coins=catalog, usdt_symbols=usdt_symbols or None)
    if not pair and usdt_symbols:
        try:
            extra = coins_from_gecko_search(search_coingecko_coins(query), usdt_symbols)
            pair = resolve_search_query(
                query, coins=catalog + extra, usdt_symbols=usdt_symbols
            )
        except Exception:
            pair = None
    if pair:
        return redirect(f"/chart/{pair}")
    message = "Coin not found. Try BTC, Ethereum, or a Binance pair like SOLUSDT."
    if not (query or "").strip():
        message = "Type a coin name or symbol to open its chart."
    return render_coin_list(search_error=message, query=query), 404


@app.route("/chart/<symbol>", methods=["GET"])
def chart(symbol):
    params = parse_chart_args(request.args)
    try:
        pair = sanitize_symbol(symbol)
        state = build_live_state(pair, params)
    except Exception as exc:
        message = str(exc) if isinstance(exc, ValueError) else "Live Binance data is unavailable right now."
        return render_template_string(ERROR_PAGE, css=SHARED_CSS, error=message), 400

    query = urlencode(
        [
            ("interval", params["interval"]),
            ("candles", params["candles"]),
            ("swing_length", params["swing_length"]),
            ("session", params["session"]),
            ("time_frame", params["time_frame"]),
        ]
        + [("overlay", name) for name in state["overlays"]],
        doseq=False,
    )
    payload = serialize_state(state)
    return render_template_string(
        CHART_PAGE,
        css=SHARED_CSS,
        symbol=pair,
        display_name=pair.replace("USDT", "/USDT"),
        interval=params["interval"],
        figure_json=json.dumps(payload["figure"]),
        stats=state["stats"],
        last_close=payload["last_close"],
        last_time=state["last_time"],
        candle_count=state["candle_count"],
        candles=params["candles"],
        swing_length=params["swing_length"],
        session=params["session"],
        time_frame=params["time_frame"],
        overlays=state["overlays"],
        overlay_labels=OVERLAY_LABELS,
        sessions=SESSIONS,
        time_frames=TIME_FRAMES,
        intervals=INTERVALS,
        api_url=f"/api/chart/{pair}?{query}",
        allowed=ALLOWED_OVERLAYS,
        search_js=SEARCH_JS,
        plot_config=json.dumps(PLOTLY_CONFIG),
        chart_height_config=json.dumps(CHART_HEIGHT),
    )


@app.route("/api/search", methods=["GET"])
def api_search():
    query = request.args.get("q", "")
    catalog, _usdt_symbols = load_search_catalog()
    suggestions = [
        {
            "name": row.get("name"),
            "symbol": row.get("symbol"),
            "binance_symbol": row.get("binance_symbol"),
        }
        for row in suggest_coins(query, catalog)
    ]
    return jsonify(suggestions)


@app.route("/api/chart/<symbol>", methods=["GET"])
def chart_api(symbol):
    params = parse_chart_args(request.args)
    try:
        state = build_live_state(symbol, params)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    except Exception:
        return jsonify({"error": "Live Binance data is unavailable right now."}), 502
    return jsonify(serialize_state(state))


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=False, threaded=True)
