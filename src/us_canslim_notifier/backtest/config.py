"""Backtest configuration loaded from BACKTEST_* environment variables."""

import os
from dataclasses import dataclass, field
from typing import List

from ..settings import settings  # noqa: F401  (loads .env via load_dotenv)

DEFAULT_TICKERS = [
    "AAPL", "MSFT", "NVDA", "GOOGL", "AMZN",
    "META", "TSLA", "AVGO", "AMD", "NFLX",
    "COST", "LLY", "UNH", "V", "MA",
    "CRM", "ADBE", "NOW", "PANW", "ANET",
]


def _env_str(key: str, default: str) -> str:
    return os.getenv(key, default)


def _env_float(key: str, default: float) -> float:
    return float(os.getenv(key, str(default)))


def _env_int(key: str, default: int) -> int:
    return int(os.getenv(key, str(default)))


def _env_tickers() -> List[str]:
    raw = os.getenv("BACKTEST_TICKERS", "")
    tickers = [t.strip().upper() for t in raw.split(",") if t.strip()]
    return tickers or list(DEFAULT_TICKERS)


@dataclass
class BacktestConfig:
    """Backtest parameters. Unset fields fall back to environment variables."""

    # Period & capital
    start_date: str = field(
        default_factory=lambda: _env_str("BACKTEST_START_DATE", "2020-01-01")
    )
    end_date: str = field(
        default_factory=lambda: _env_str("BACKTEST_END_DATE", "2024-12-31")
    )
    initial_capital: float = field(
        default_factory=lambda: _env_float("BACKTEST_INITIAL_CAPITAL", 100000.0)
    )
    position_size_pct: float = field(
        default_factory=lambda: _env_float("BACKTEST_POSITION_SIZE_PCT", 0.1)
    )
    us_tickers: List[str] = field(default_factory=_env_tickers)

    # CAN SLIM fundamentals (percent values, shared with the live bot settings)
    market_index_ticker: str = field(
        default_factory=lambda: _env_str("MARKET_INDEX_TICKER", "SPY")
    )
    min_qtr_eps_growth: float = field(
        default_factory=lambda: _env_float("MIN_QTR_EPS_GROWTH", 25.0)
    )
    min_annual_eps_growth: float = field(
        default_factory=lambda: _env_float("MIN_ANNUAL_EPS_GROWTH", 25.0)
    )
    min_inst_ownership_pct: float = field(
        default_factory=lambda: _env_float("MIN_INST_OWNERSHIP_PCT", 10.0)
    )
    min_rs_vs_index_perf: float = field(
        default_factory=lambda: _env_float("MIN_RS_VS_INDEX_PERF", 10.0)
    )

    # Technical parameters
    volume_avg_days: int = field(
        default_factory=lambda: _env_int("BACKTEST_VOLUME_AVG_DAYS", 50)
    )
    pivot_lookback_days: int = field(
        default_factory=lambda: _env_int("BACKTEST_PIVOT_LOOKBACK_DAYS", 20)
    )
    volume_surge_pct: float = field(
        default_factory=lambda: _env_float("VOLUME_SURGE_MIN", 50.0)
    )  # percent above average volume
    breakout_pct_max: float = field(
        default_factory=lambda: _env_float("BREAKOUT_MAX", 5.0)
    )  # percent above pivot
    near_52w_high_pct: float = field(
        default_factory=lambda: _env_float("BACKTEST_NEAR_52W_HIGH_PCT", 0.10)
    )  # fraction below 52w high
    above_52w_low_pct: float = field(
        default_factory=lambda: _env_float("BACKTEST_ABOVE_52W_LOW_PCT", 1.50)
    )  # multiplier of 52w low

    # Risk management (fractions)
    stop_loss_pct: float = field(
        default_factory=lambda: _env_float("BACKTEST_STOP_LOSS_PCT", 0.08)
    )
    take_profit_pct: float = field(
        default_factory=lambda: _env_float("BACKTEST_TAKE_PROFIT_PCT", 0.20)
    )
    holding_days_max: int = field(
        default_factory=lambda: _env_int("BACKTEST_HOLDING_DAYS_MAX", 30)
    )


default_config = BacktestConfig()
