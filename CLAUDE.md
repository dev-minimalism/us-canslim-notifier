# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

US stock signal bot based on William O'Neil's CAN SLIM method. It scans a watchlist with `yfinance`, detects pivot breakouts, tracks paper positions, and talks to the user over Telegram. It also has a separate historical backtester. User-facing docs (README) are in Korean; code, comments and bot messages are in English.

## Commands

```bash
cp .env.example .env            # set TELEGRAM_TOKEN and CHAT_ID (needed for the bot, not for backtest)
pip install -e ".[dev]"

python -m us_canslim_notifier            # run the bot (same as: us-canslim-notifier)
python -m us_canslim_notifier backtest   # run the backtest with BACKTEST_* values from .env

pytest                                   # tests/ currently holds only __init__.py
pytest tests/test_foo.py::test_bar       # single test (files must match test_*.py)
black src/
ruff check src/
mypy src/
```

Background run on a server (from README): `nohup python -u -m us_canslim_notifier > logs/bot_$(date +%Y%m%d).log 2>&1 &`

## Backtest config

`backtest/config.py` defines the `BacktestConfig` dataclass and `default_config`. Each field reads its environment variable at instantiation time (via `default_factory`), so explicit constructor arguments override `.env`. Fundamental thresholds and `VOLUME_SURGE_MIN` / `BREAKOUT_MAX` reuse the live bot's env var names. Everything else uses `BACKTEST_*`. Units differ by field: the fundamentals, `volume_surge_pct` and `breakout_pct_max` are percents, the risk fields are fractions, and `above_52w_low_pct` is a multiplier. `.gitignore` only ignores a root-level `/config.py`; a bare `config.py` pattern previously hid this file from git.

## Architecture

Two independent code paths share the same strategy idea but **not** the same code. A change to strategy logic usually needs to go into both:

| | Live bot (`bot.py`, `CANSLIMDetector`) | Backtest (`backtest/runner.py`, `ONeilBacktester`) |
|---|---|---|
| Config | `settings.py` `Settings` class | `BacktestConfig` (`BACKTEST_*` env vars) |
| Fundamentals (C, A, I) | `yf.Ticker(...).info` per scan | Pre-screened once up front with the *current* `Ticker.info` (look-ahead bias: today's fundamentals filter historical trades) |
| N / L / breakout | Computed from `info` + recent history | Precomputed rolling columns (52w high/low, avg volume, pivot high) over bulk-downloaded prices |
| Exits | Hardcoded in `add_position` / `check_positions`: -8%, +20%, 30 days | Configurable `stop_loss_pct`, `take_profit_pct`, `holding_days_max` |

### Live bot flow
- `__main__.py` `run_bot()` starts `start_command_listener()` (a daemon thread that long-polls Telegram `getUpdates` with raw `requests`, no bot library), then loops `run_scheduled_scan()` every `SCAN_INTERVAL` seconds.
- `run_scheduled_scan()` runs the full scan only when `is_market_open()` is true; otherwise it only runs `check_positions()`.
- `run_scan()`: M filter (`check_market_direction`, SPY vs 50/200 MA) blocks new entries in a downtrend → `check_positions()` → for each watchlist ticker, `get_can_slim_factors` (all of C/A/N/I/L must pass) then `detect_pivot_breakout`; a hit sends an alert and auto-opens a position via `add_position`.
- `/scan` and `/check` run in their own threads. `scan_lock` is acquired non-blocking, so a second concurrent scan is rejected instead of queued.
- Messages are sent with HTML parse mode (`<b>` tags), so escape `<`/`>`/`&` in dynamic text.
- State is saved to JSON files in the **current working directory**: `watchlist.json` (`{"tickers": [...]}`; the legacy `{"us": [...]}` format is still read) and `positions.json`. Both are gitignored.

### Things that are easy to get wrong
- `is_market_open()` uses naive `datetime.now()` and a fixed 22:30–06:00 window, so it assumes the host clock is KST and ignores US daylight saving time and holidays.
- `Settings` reads env vars into class attributes at import time (`load_dotenv()` runs on import), so changing `os.environ` after import has no effect.
- `STOP_LOSS_PERCENT`, `ANALYSIS_PERIOD` and `ANALYSIS_PERIOD_DAYS` are defined in `settings.py` and `.env.example` but nothing reads them. The live exit rules are the hardcoded values above.
- yfinance `info` fields (`earningsQuarterlyGrowth`, `heldPercentInstitutions`, etc.) are often missing or `None`. The code treats a missing value as 0, which makes that factor fail.

## Telegram Commands
`/scan`, `/check [ticker]`, `/positions`, `/close [ticker]`, `/add [ticker]`, `/remove [ticker]`, `/list`, `/status`, `/help`. All of them are handled in `CANSLIMDetector.process_command`.
