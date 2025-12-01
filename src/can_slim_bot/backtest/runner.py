"""
CAN SLIM Strategy Backtester

Features:
- SettingWithCopyWarning fixed (.copy() added)
- FutureWarning fixed (auto_adjust=True)
- CAGR (Compound Annual Growth Rate) report
"""

import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from typing import Dict, List, Optional

import pandas as pd
import yfinance as yf

from .config import BacktestConfig, default_config


class ONeilBacktester:
    """CAN SLIM strategy backtester."""

    def __init__(self, config: Optional[BacktestConfig] = None):
        """Initialize backtester with configuration."""
        self.config = config or default_config
        self.price_data: Dict[str, pd.DataFrame] = {}
        self.trades_log: List[Dict] = []
        self.open_positions: Dict[str, Dict] = {}
        self.capital = self.config.initial_capital
        self.position_size = self.config.initial_capital * self.config.position_size_pct

        print("📈 CAN SLIM Backtester initialized")
        print(f"   - Period: {self.config.start_date} ~ {self.config.end_date}")
        print(f"   - Initial capital: ${self.config.initial_capital:,.2f}")
        print(f"   - Position size: ${self.position_size:,.2f}")
        print("-" * 40)

    def load_all_data(self, tickers: List[str]) -> bool:
        """Load backtest period + 1 year data and calculate indicators."""
        print("⏳ Loading data (including 1 year lookback)...")

        start_load_date = (
            datetime.strptime(self.config.start_date, "%Y-%m-%d") - timedelta(days=365)
        ).strftime("%Y-%m-%d")

        all_tickers = list(set(tickers + [self.config.market_index_ticker]))

        try:
            data = yf.download(
                all_tickers,
                start=start_load_date,
                end=self.config.end_date,
                progress=False,
                auto_adjust=True,
            )

            if data.empty:
                print("❌ Data load failed. Check tickers or date range.")
                return False

            print("✅ Data loaded. Calculating indicators...")

            for ticker in all_tickers:
                if len(all_tickers) > 1:
                    df = data.loc[:, (slice(None), ticker)].copy()
                    df.columns = df.columns.droplevel(1)
                else:
                    df = data.copy()

                if df.empty or df["Close"].isnull().all():
                    print(f"   ⚠️ {ticker} data is empty, excluding")
                    continue

                # Calculate indicators
                df["MA50"] = df["Close"].rolling(window=50).mean()
                df["MA200"] = df["Close"].rolling(window=200).mean()

                # N (New High)
                df["52w_High"] = df["High"].rolling(window=252).max()
                df["52w_Low"] = df["Low"].rolling(window=252).min()

                # L (Leader)
                df["1Y_Return"] = df["Close"].pct_change(252)

                # Pivot (Technical)
                df["Avg_Volume"] = df["Volume"].rolling(
                    window=self.config.volume_avg_days
                ).mean()
                df["Pivot_Resist"] = (
                    df["High"].shift(1).rolling(window=self.config.pivot_lookback_days).max()
                )

                self.price_data[ticker] = df.dropna()

            return True

        except Exception as e:
            print(f"❌ Data load error: {e}")
            return False

    def pre_screen_tickers(self) -> List[str]:
        """Pre-screen tickers by C, A, I factors (current point-in-time)."""
        print(
            f"🔬 Pre-screening C, A, I fundamentals ({len(self.config.us_tickers)} tickers)..."
        )

        screened_tickers = []

        def check_ticker(ticker_str: str) -> Optional[str]:
            try:
                ticker = yf.Ticker(ticker_str)
                info = ticker.info

                # C: Quarterly EPS growth
                qtr_growth = info.get("earningsQuarterlyGrowth", 0) or 0
                pass_c = (qtr_growth * 100) >= self.config.min_qtr_eps_growth

                # A: Annual EPS growth
                annual_growth = info.get("earningsGrowth", 0) or 0
                pass_a = (annual_growth * 100) >= self.config.min_annual_eps_growth

                # I: Institutional ownership
                inst_own = info.get("heldPercentInstitutions", 0) or 0
                pass_i = (inst_own * 100) >= self.config.min_inst_ownership_pct

                if pass_c and pass_a and pass_i:
                    print(
                        f"  ✅ {ticker_str} pass (C:{qtr_growth * 100:.1f}%, A:{annual_growth * 100:.1f}%, I:{inst_own * 100:.1f}%)"
                    )
                    return ticker_str
                else:
                    print(f"  ❌ {ticker_str} fail (C:{pass_c}, A:{pass_a}, I:{pass_i})")
                    return None
            except Exception as e:
                print(f"  ⚠️ {ticker_str} fundamental query failed: {e}")
                return None

        with ThreadPoolExecutor(max_workers=5) as executor:
            results = executor.map(check_ticker, self.config.us_tickers)

        screened_tickers = [res for res in results if res is not None]

        print(
            f"✅ Pre-screening complete: {len(screened_tickers)} / {len(self.config.us_tickers)} passed"
        )
        print("-" * 40)
        return screened_tickers

    def check_entry_signal(self, ticker: str, date) -> Optional[Dict]:
        """Check M, L, N, Pivot signals for entry."""
        try:
            stock_data = self.price_data[ticker].loc[date]
            market_data = self.price_data[self.config.market_index_ticker].loc[date]
        except KeyError:
            return None

        # M (Market)
        if not (
            market_data["Close"] > market_data["MA50"]
            and market_data["Close"] > market_data["MA200"]
        ):
            return None

        # L (Leader)
        stock_1y_ret = stock_data["1Y_Return"]
        market_1y_ret = market_data["1Y_Return"]
        if (stock_1y_ret - market_1y_ret) * 100 < self.config.min_rs_vs_index_perf:
            return None

        # N (New High)
        is_near_high = stock_data["Close"] > (
            stock_data["52w_High"] * (1 - self.config.near_52w_high_pct)
        )
        is_above_low = stock_data["Close"] > (
            stock_data["52w_Low"] * self.config.above_52w_low_pct
        )
        if not (is_near_high and is_above_low):
            return None

        # Pivot (Technical Breakout)
        resistance = stock_data["Pivot_Resist"]
        current_close = stock_data["Close"]
        current_volume = stock_data["Volume"]
        avg_volume = stock_data["Avg_Volume"]

        volume_surge = ((current_volume - avg_volume) / avg_volume) * 100
        pass_volume = volume_surge >= self.config.volume_surge_pct

        breakout_pct = ((current_close - resistance) / resistance) * 100
        pass_breakout = (current_close > resistance) and (
            0 < breakout_pct <= self.config.breakout_pct_max
        )

        if pass_volume and pass_breakout:
            return {
                "entry_price": current_close,
                "signal_type": "Pivot",
                "volume_surge": volume_surge,
                "breakout_pct": breakout_pct,
            }

        return None

    def open_position(self, ticker: str, date, signal: Dict):
        """Open new position."""
        entry_price = signal["entry_price"]

        self.open_positions[ticker] = {
            "entry_date": date,
            "entry_price": entry_price,
            "stop_loss": entry_price * (1 - self.config.stop_loss_pct),
            "take_profit": entry_price * (1 + self.config.take_profit_pct),
            "holding_days_max": date + timedelta(days=self.config.holding_days_max),
        }

        print(f"  📈 [BUY] {date.date()} | {ticker} | Price: ${entry_price:,.2f}")

    def close_position(self, ticker: str, date, exit_price: float, reason: str):
        """Close position."""
        pos = self.open_positions.pop(ticker)
        entry_price = pos["entry_price"]

        profit_pct = (exit_price - entry_price) / entry_price
        profit_amt = self.position_size * profit_pct

        self.capital += profit_amt

        self.trades_log.append(
            {
                "ticker": ticker,
                "entry_date": pos["entry_date"].date(),
                "exit_date": date.date(),
                "entry_price": entry_price,
                "exit_price": exit_price,
                "profit_pct": profit_pct * 100,
                "profit_amt": profit_amt,
                "reason": reason,
            }
        )

        icon = "✅" if profit_pct > 0 else "🔻"
        print(
            f"  {icon} [SELL] {date.date()} | {ticker} | {reason} | P/L: {profit_pct * 100:+.2f}%"
        )

    def run_simulation(self, screened_tickers: List[str]):
        """Run main simulation loop."""
        if not screened_tickers:
            print("❌ No tickers to backtest.")
            return

        market_dates = self.price_data[self.config.market_index_ticker].loc[
            self.config.start_date : self.config.end_date
        ].index

        if market_dates.empty:
            print("❌ No market data for simulation period.")
            return

        print(f"\n🚀 Starting simulation ({len(market_dates)} trading days)...")

        start_time = time.time()

        for date in market_dates:
            # 1. Check position exits
            for ticker in list(self.open_positions.keys()):
                pos = self.open_positions[ticker]

                try:
                    today_data = self.price_data[ticker].loc[date]
                except KeyError:
                    continue

                if today_data["Low"] <= pos["stop_loss"]:
                    self.close_position(ticker, date, pos["stop_loss"], "Stop Loss")
                elif today_data["High"] >= pos["take_profit"]:
                    self.close_position(ticker, date, pos["take_profit"], "Take Profit")
                elif date > pos["holding_days_max"]:
                    self.close_position(ticker, date, today_data["Open"], "Time Exit")

            # 2. Check new entries
            for ticker in screened_tickers:
                if ticker in self.open_positions:
                    continue

                signal = self.check_entry_signal(ticker, date)

                if signal:
                    self.open_position(ticker, date, signal)

        end_time = time.time()
        print(f"\n✅ Simulation complete! (Duration: {end_time - start_time:.2f}s)")
        print("-" * 40)

    def print_report(self):
        """Print backtest results report."""
        if not self.trades_log:
            print("📊 Final Report: No trades executed.")
            return

        report_df = pd.DataFrame(self.trades_log)

        total_trades = len(report_df)
        wins = report_df[report_df["profit_pct"] > 0]
        losses = report_df[report_df["profit_pct"] <= 0]

        win_rate = (len(wins) / total_trades) * 100 if total_trades > 0 else 0

        avg_profit = wins["profit_pct"].mean() if len(wins) > 0 else 0
        avg_loss = losses["profit_pct"].mean() if len(losses) > 0 else 0

        if losses["profit_pct"].sum() == 0:
            profit_factor = float("inf") if wins["profit_pct"].sum() > 0 else 1.0
        else:
            profit_factor = wins["profit_pct"].sum() / abs(losses["profit_pct"].sum())

        total_pnl_amt = report_df["profit_amt"].sum()
        final_capital = self.config.initial_capital + total_pnl_amt
        total_return_pct = (total_pnl_amt / self.config.initial_capital) * 100

        # CAGR calculation
        start_dt = datetime.strptime(self.config.start_date, "%Y-%m-%d")
        end_dt = datetime.strptime(self.config.end_date, "%Y-%m-%d")
        total_days = (end_dt - start_dt).days

        annualized_return_pct = 0.0
        if total_days > 0:
            num_years = total_days / 365.25
            total_return_multiplier = final_capital / self.config.initial_capital

            if total_return_multiplier > 0:
                annualized_return_decimal = (total_return_multiplier ** (1 / num_years)) - 1
                annualized_return_pct = annualized_return_decimal * 100
            else:
                annualized_return_pct = -100.0
        elif total_days == 0:
            annualized_return_pct = total_return_pct

        print("\n📊 === BACKTEST FINAL REPORT ===")
        print(
            f"  - Period: {self.config.start_date} ~ {self.config.end_date} ({total_days} days)"
        )
        print(f"  - Initial capital: ${self.config.initial_capital:,.2f}")
        print(f"  - Final capital: ${final_capital:,.2f}")
        print("-" * 40)
        print("Performance Summary:")
        print(f"  - Total Return: {total_return_pct:+.2f}%")
        print(f"  - CAGR: {annualized_return_pct:+.2f}%")
        print(f"  - Total trades: {total_trades}")
        print(f"  - Win rate: {win_rate:.2f}% ({len(wins)}W / {len(losses)}L)")
        print(f"  - Avg win: {avg_profit:+.2f}%")
        print(f"  - Avg loss: {avg_loss:.2f}%")
        print(f"  - Profit factor: {profit_factor:.2f}")
        print("-" * 40)
        print("Recent trades (last 10):")
        print(report_df.tail(10).to_string(index=False, float_format="%.2f"))


def run_backtest(config: Optional[BacktestConfig] = None):
    """Convenience function to run backtest."""
    backtester = ONeilBacktester(config)

    # 1. Pre-screen fundamentals
    screened_tickers = backtester.pre_screen_tickers()

    if not screened_tickers:
        print("❌ No tickers passed C/A/I fundamental screening. Exiting.")
        return

    # 2. Load data and calculate indicators
    if backtester.load_all_data(screened_tickers):
        # 3. Run simulation
        backtester.run_simulation(screened_tickers)

        # 4. Print report
        backtester.print_report()
