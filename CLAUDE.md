# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

CAN SLIM Bot is a US stock trading signal detection system based on William O'Neil's CAN SLIM investment methodology. It monitors the US stock market, detects breakout patterns, and sends alerts via Telegram.

## Commands

### Setup
```bash
cp .env.example .env
# Edit .env with your TELEGRAM_TOKEN and CHAT_ID
pip install -e .
```

### Run the Bot
```bash
# As module
python -m us_canslim_notifier

# Or via entry point (after pip install)
us-canslim-notifier
```

### Run Backtesting
```bash
# CLI (uses .env settings)
python -m us_canslim_notifier backtest

# Or via entry point
us-canslim-notifier backtest
```

Python:
```python
from us_canslim_notifier.backtest import run_backtest, BacktestConfig

# With .env settings
run_backtest()

# With custom config
config = BacktestConfig(
    start_date="2020-01-01",
    end_date="2024-12-31",
    initial_capital=50000.0,
)
run_backtest(config)
```

### Development
```bash
pip install -e ".[dev]"
pytest
black src/
ruff check src/
```

## Project Structure

```
us-canslim-notifier/
├── src/
│   └── us_canslim_notifier/
│       ├── __init__.py
│       ├── __main__.py      # Entry point (python -m us_canslim_notifier)
│       ├── bot.py           # CANSLIMDetector class
│       ├── settings.py      # Environment variable loading
│       ├── database.py      # SSH tunnel + PostgreSQL connection
│       ├── repository.py    # Position CRUD operations
│       └── backtest/
│           ├── __init__.py
│           ├── config.py    # BacktestConfig dataclass
│           └── runner.py    # ONeilBacktester class
├── scripts/
│   ├── init_db.py           # Database creation script
│   └── test_db.py           # Connection test script
├── tests/
├── .env.example
├── pyproject.toml
└── CLAUDE.md
```

## Architecture

### Core Modules

**`src/us_canslim_notifier/bot.py`** - `CANSLIMDetector` class:
- Telegram command listener (background thread)
- US market time detection (22:30-06:00 KST)
- Position tracking with automatic stop-loss/take-profit (DB-backed)
- Concurrent scan prevention via threading lock
- Duplicate alert prevention (skips if position exists)

**`src/us_canslim_notifier/settings.py`** - `Settings` class:
- Environment variable loading via python-dotenv
- SSH tunnel and PostgreSQL connection settings
- All configurable parameters with defaults

**`src/us_canslim_notifier/database.py`** - `DatabaseManager` class:
- SSH tunnel via paramiko for secure DB access
- PostgreSQL connection with psycopg2
- Schema initialization (positions, trade_history tables)

**`src/us_canslim_notifier/repository.py`** - `PositionRepository` class:
- Position CRUD operations
- Trade history tracking
- Performance summary (win rate, avg P/L, etc.)

**`src/us_canslim_notifier/backtest/`** - Backtesting module:
- `BacktestConfig`: Dataclass with environment variable support (BACKTEST_* in .env)
- `ONeilBacktester`: Simulation runner with CAGR reporting
- `run_backtest()`: Convenience function to run backtest

### Data Source
- US stocks: `yfinance` (price data + fundamentals via `Ticker.info`)

### CAN SLIM Implementation

**Fundamental Filters:**
- C: Quarterly EPS growth > 25%
- A: Annual EPS growth > 25%
- N: Near 52-week high (within 10%) and 50%+ above 52-week low
- S: Shares outstanding (not filtered)
- L: Relative strength vs SPY > 10%
- I: Institutional ownership > 10%
- M: Market direction (SPY above 50MA and 200MA)

**Technical Signal:**
- Pivot breakout: Price breaks 20-day high with 50%+ volume surge, within 5% of breakout level

### Runtime Data Files (gitignored)
- `watchlist.json` - Persisted watchlist `{"tickers": [...], "updated_at": "..."}`

### Database Tables
- `positions` - Open/closed positions with entry/exit prices, stop-loss, take-profit
- `trade_history` - Closed trade records for performance analysis

### Telegram Commands
`/scan`, `/check [ticker]`, `/positions`, `/close [ticker]`, `/performance`, `/add [ticker]`, `/remove [ticker]`, `/list`, `/status`, `/help`

## Key Patterns

- Scan operations run in separate threads to avoid blocking the command listener
- M (Market) filter blocks scans during market downtrends
- Positions auto-close at -8% stop-loss, +20% take-profit, or 30-day expiry
- Duplicate alerts are prevented when position already exists for a ticker
- SSH tunnel is used for secure remote PostgreSQL access
