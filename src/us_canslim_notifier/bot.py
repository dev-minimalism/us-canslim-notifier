"""
CAN SLIM Bot - William O'Neil's Breakout Detection System

Features:
- M: Market Direction (SPY 50/200MA) filter
- C,A,N,S,L,I: US stock fundamental filters
- /check [ticker] command for factor lookup
- Pivot point breakout pattern detection
- Telegram command-based stock management
- Position management with stop-loss/take-profit (DB-backed)
"""

import json
import os
import threading
import time
import warnings
from datetime import datetime, timedelta, time as dt_time
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
import requests
import yfinance as yf

from .settings import settings
from .database import init_db, get_db, close_db
from .repository import position_repo

warnings.filterwarnings("ignore")


class CANSLIMDetector:
    """CAN SLIM breakout pattern detection class."""

    def __init__(
        self,
        telegram_token: str,
        chat_id: str,
        watchlist_file: str = "watchlist.json",
        use_db: bool = True,
    ):
        """
        Initialize the detector.

        Args:
            telegram_token: Telegram bot token
            chat_id: Telegram chat ID
            watchlist_file: Watchlist storage file
            use_db: Use database for position management
        """
        self.telegram_token = telegram_token
        self.chat_id = chat_id
        self.base_url = f"https://api.telegram.org/bot{telegram_token}"
        self.watchlist_file = watchlist_file
        self.use_db = use_db
        self.last_update_id = 0

        # Concurrent scan prevention lock
        self.scan_lock = threading.Lock()
        self.is_scanning = False

        # CAN SLIM parameters from settings
        self.MARKET_INDEX_TICKER = settings.MARKET_INDEX_TICKER
        self.MIN_QTR_EPS_GROWTH = settings.MIN_QTR_EPS_GROWTH
        self.MIN_ANNUAL_EPS_GROWTH = settings.MIN_ANNUAL_EPS_GROWTH
        self.MIN_INST_OWNERSHIP_PCT = settings.MIN_INST_OWNERSHIP_PCT
        self.MIN_RS_VS_INDEX_PERF = settings.MIN_RS_VS_INDEX_PERF

        # Load watchlist
        self.watchlist = self.load_watchlist()
        print("✅ Watchlist loaded")
        print(f"   🇺🇸 Stocks: {len(self.watchlist)}")

        # Initialize database if configured
        if self.use_db and settings.is_db_configured():
            print("\n🔌 Connecting to database...")
            if init_db():
                positions = position_repo.get_open_positions()
                print(f"✅ Positions loaded from DB: {len(positions)}")
            else:
                print("⚠️  Database connection failed, falling back to file-based storage")
                self.use_db = False
        else:
            self.use_db = False
            print("⚠️  Database not configured, using file-based storage")

    # ========================================
    # Watchlist Management
    # ========================================

    def load_watchlist(self) -> List[str]:
        """Load watchlist from file."""
        if os.path.exists(self.watchlist_file):
            try:
                with open(self.watchlist_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    # Support both old format {"us": [...]} and new format {"tickers": [...]}
                    if "tickers" in data:
                        return data.get("tickers", [])
                    elif "us" in data:
                        return data.get("us", [])
            except Exception as e:
                print(f"⚠️  Failed to load watchlist: {e}")

        # Default watchlist
        return ["AAPL", "MSFT", "GOOGL", "NVDA", "TSLA", "AMD", "META"]

    def save_watchlist(self) -> bool:
        """Save watchlist to file."""
        try:
            data = {
                "tickers": self.watchlist,
                "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            }
            with open(self.watchlist_file, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            print(f"❌ Failed to save watchlist: {e}")
            return False

    def add_stock(self, ticker: str) -> str:
        """Add stock to watchlist."""
        ticker = ticker.upper().strip()
        if ticker in self.watchlist:
            return f"⚠️  {ticker} is already being monitored."

        self.watchlist.append(ticker)
        if self.save_watchlist():
            return f"✅ {ticker} added!\nCurrent stocks: {len(self.watchlist)}"
        else:
            self.watchlist.remove(ticker)
            return "❌ Save failed"

    def remove_stock(self, ticker: str) -> str:
        """Remove stock from watchlist."""
        ticker = ticker.upper().strip()
        if ticker not in self.watchlist:
            return f"⚠️  {ticker} is not in watchlist."

        self.watchlist.remove(ticker)
        if self.save_watchlist():
            return f"✅ {ticker} removed!\nCurrent stocks: {len(self.watchlist)}"
        else:
            self.watchlist.append(ticker)
            return "❌ Save failed"

    def list_watchlist(self) -> str:
        """Get watchlist display string."""
        msg = f"📊 <b>Watchlist</b> ({len(self.watchlist)} stocks)\n\n"

        if self.watchlist:
            msg += ", ".join(self.watchlist)
        else:
            msg += "No stocks"

        return msg

    # ========================================
    # Position Management (DB-backed)
    # ========================================

    def get_positions(self) -> List[Dict]:
        """Get open positions from database."""
        if self.use_db:
            return position_repo.get_open_positions()
        return []

    def add_position(
        self, ticker: str, entry_price: float, pattern: str, signal: Dict
    ):
        """Add new position to database."""
        if self.use_db:
            position_id = position_repo.add_position(
                ticker=ticker,
                entry_price=entry_price,
                pattern=pattern,
                signal=signal,
            )
            if position_id:
                print(f"  📝 Position added (DB): {ticker} @ ${entry_price:.2f}")
            else:
                print(f"  ❌ Failed to add position: {ticker}")
        else:
            print(f"  ⚠️  Database not available, position not saved: {ticker}")

    def close_position(self, ticker: str, exit_price: float, reason: str) -> bool:
        """Close position in database."""
        if not self.use_db:
            print(f"  ⚠️  Database not available")
            return False

        result = position_repo.close_position(ticker, exit_price, reason)
        if result:
            profit_pct = result["profit_pct"]
            holding_days = result["holding_days"]
            entry_price = result["entry_price"]
            pattern = result.get("pattern", "N/A")

            msg = f"""
🇺🇸 <b>[Position Closed]</b>

🏢 Ticker: <b>{ticker}</b>
📊 Pattern: {pattern}
💰 Entry: ${entry_price:.2f}
💵 Exit: ${exit_price:.2f}
{'📈' if profit_pct > 0 else '📉'} P/L: {profit_pct:+.2f}%
📅 Holding: {holding_days} days

🔔 Reason: {reason}

⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
            self.send_telegram_message(msg)
            print(f"  ❌ Position closed: {ticker} ({reason}) {profit_pct:+.2f}%")
            return True
        return False

    def check_positions(self):
        """Check and manage open positions."""
        positions = self.get_positions()
        if not positions:
            return

        print(f"\n📊 Checking positions... ({len(positions)})")

        for pos in positions:
            ticker = pos["ticker"]
            entry_price = float(pos["entry_price"])
            entry_date = pos["entry_date"]
            stop_loss = float(pos["stop_loss"])
            take_profit = float(pos["take_profit"])
            holding_days = (datetime.now() - entry_date).days

            try:
                df = self.get_stock_data(ticker, period="5d")

                if df is None or len(df) == 0:
                    continue

                current_price = df["Close"].iloc[-1]
                profit_pct = ((current_price - entry_price) / entry_price) * 100

                print(
                    f"  🔍 {ticker}: ${current_price:.2f} ({profit_pct:+.2f}%)",
                    end="",
                )

                if current_price <= stop_loss:
                    print(" ⚠️ Stop loss!")
                    self.close_position(ticker, current_price, "Stop loss (-8%)")
                elif current_price >= take_profit:
                    print(" ✅ Take profit!")
                    self.close_position(ticker, current_price, "Take profit (+20%)")
                elif holding_days >= 30:
                    print(" ⏰ Time exit!")
                    self.close_position(
                        ticker, current_price, f"Holding period expired ({holding_days} days)"
                    )
                else:
                    print(" ⚪")

                time.sleep(1)

            except Exception as e:
                print(f" ❌ Error: {e}")

    def list_positions(self) -> str:
        """Get positions display string."""
        positions = self.get_positions()
        if not positions:
            return "📊 <b>Current Positions</b>\n\nNo open positions."

        msg = f"📊 <b>Current Positions</b> ({len(positions)})\n\n"

        for i, pos in enumerate(positions, 1):
            ticker = pos["ticker"]
            entry_price = float(pos["entry_price"])
            entry_date = pos["entry_date"]
            stop_loss = float(pos["stop_loss"])
            take_profit = float(pos["take_profit"])
            holding_days = (datetime.now() - entry_date).days

            try:
                df = self.get_stock_data(ticker, period="5d")

                if df is not None and len(df) > 0:
                    current_price = df["Close"].iloc[-1]
                    profit_pct = ((current_price - entry_price) / entry_price) * 100
                    profit_icon = "📈" if profit_pct > 0 else "📉"
                    current_info = f"${current_price:.2f} ({profit_icon}{profit_pct:+.2f}%)"
                else:
                    current_info = "Query failed"
            except:
                current_info = "Query failed"

            msg += f"""
{i}. <b>{ticker}</b>
   Entry: ${entry_price:.2f}
   Current: {current_info}
   Pattern: {pos.get('pattern', 'N/A')}
   Holding: {holding_days} days
   Stop: ${stop_loss:.2f}
   Target: ${take_profit:.2f}
"""

        return msg

    def get_performance(self) -> str:
        """Get trading performance summary."""
        if not self.use_db:
            return "📊 <b>Performance</b>\n\nDatabase not configured."

        perf = position_repo.get_performance_summary()

        if perf["total_trades"] == 0:
            return "📊 <b>Performance</b>\n\nNo closed trades yet."

        return f"""
📊 <b>Trading Performance</b>

📈 Total Trades: {perf['total_trades']}
✅ Winning: {perf['winning_trades']} ({perf['win_rate']}%)
❌ Losing: {perf['losing_trades']}

💰 Avg P/L: {perf['avg_profit_pct']:+.2f}%
💵 Total P/L: {perf['total_profit_pct']:+.2f}%
🎯 Best Trade: {perf['max_profit_pct']:+.2f}%
📉 Worst Trade: {perf['max_loss_pct']:+.2f}%

📅 Avg Holding: {perf['avg_holding_days']:.1f} days
"""

    # ========================================
    # Market Status
    # ========================================

    def is_market_open(self) -> bool:
        """Check if US market is open (Korean time: 22:30-06:00)."""
        now = datetime.now()
        current_time = now.time()
        weekday = now.weekday()

        is_weekend = weekday >= 5

        # US market (Korean time): 22:30 - 06:00 next day
        us_open_night = dt_time(22, 30)
        us_close_morning = dt_time(6, 0)

        if is_weekend:
            return False

        if current_time >= us_open_night:
            return True
        elif current_time <= us_close_morning:
            return True

        return False

    def get_market_status(self) -> str:
        """Get market status message."""
        now = datetime.now()
        is_open = self.is_market_open()

        msg = "📊 <b>Market Status</b>\n\n"
        msg += f"⏰ Current time: {now.strftime('%H:%M:%S')}\n\n"

        if is_open:
            msg += "🇺🇸 US market <b>OPEN</b> (22:30-06:00 KST)\n"
            msg += f"   Monitoring: {len(self.watchlist)} stocks\n"
        else:
            msg += "🇺🇸 US market <b>CLOSED</b>\n"

        if self.is_scanning:
            msg += "\n🔄 Scan in progress..."

        return msg

    # ========================================
    # Telegram
    # ========================================

    def send_telegram_message(self, message: str):
        """Send message via Telegram."""
        try:
            payload = {"chat_id": self.chat_id, "text": message, "parse_mode": "HTML"}
            response = requests.post(f"{self.base_url}/sendMessage", data=payload)
            if response.status_code == 200:
                print("✅ Telegram message sent")
            else:
                print(f"❌ Telegram send failed: {response.status_code}")
        except Exception as e:
            print(f"❌ Telegram error: {e}")

    def process_command(self, message: str) -> Optional[str]:
        """Process Telegram command."""
        parts = message.strip().split()
        if not parts:
            return None

        command = parts[0].lower()

        if command == "/help" or command == "/start":
            return f"""
🤖 <b>CAN SLIM Bot Commands</b>

<b>Fundamental Check:</b>
/check [ticker] - Check CAN SLIM factors
  e.g. /check NVDA

<b>Scan:</b>
/scan - Scan all stocks

<b>Position Management:</b>
/positions - View current positions
/close [ticker] - Close position manually
  e.g. /close AAPL
/performance - View trading performance

<b>Watchlist:</b>
/add [ticker] - Add stock
  e.g. /add AAPL
/remove [ticker] - Remove stock
  e.g. /remove AAPL
/list - View watchlist

<b>Other:</b>
/status - Market status
/help - This message

<b>CAN SLIM Filters:</b>
  M: Market direction ({self.MARKET_INDEX_TICKER})
  C: Quarterly growth (>{self.MIN_QTR_EPS_GROWTH}%)
  A: Annual growth (>{self.MIN_ANNUAL_EPS_GROWTH}%)
  I: Institutional (>{self.MIN_INST_OWNERSHIP_PCT}%)
  L: Relative strength (>{self.MIN_RS_VS_INDEX_PERF}% vs SPY)
  N: Near 52-week high
"""

        elif command == "/add":
            if len(parts) < 2:
                return "❌ Usage: /add [ticker]\ne.g. /add AAPL"
            return self.add_stock(parts[1])

        elif command == "/remove":
            if len(parts) < 2:
                return "❌ Usage: /remove [ticker]\ne.g. /remove AAPL"
            return self.remove_stock(parts[1])

        elif command == "/list":
            return self.list_watchlist()

        elif command == "/status":
            return self.get_market_status()

        elif command == "/scan":
            return "SCAN"

        elif command == "/positions":
            return self.list_positions()

        elif command == "/close":
            if len(parts) < 2:
                return "❌ Usage: /close [ticker]\ne.g. /close AAPL"

            ticker = parts[1].upper()
            if not position_repo.has_open_position(ticker):
                return f"❌ Position not found: {ticker}"

            try:
                df = self.get_stock_data(ticker, period="5d")

                if df is not None and len(df) > 0:
                    current_price = df["Close"].iloc[-1]
                    self.close_position(ticker, current_price, "Manual close")
                    return f"✅ {ticker} position closed."
                else:
                    return f"❌ Failed to get current price for {ticker}"
            except Exception as e:
                return f"❌ Error closing position: {e}"

        elif command == "/performance":
            return self.get_performance()

        elif command == "/check":
            if len(parts) < 2:
                return "❌ Usage: /check [ticker]\ne.g. /check NVDA"

            ticker = parts[1].upper()
            self.send_telegram_message(f"🔍 Checking CAN SLIM factors for {ticker}...")

            def check_task():
                is_pass, factors = self.get_can_slim_factors(ticker)
                if "error" in factors:
                    self.send_telegram_message(
                        f"❌ Failed to check {ticker}: {factors['error']}"
                    )
                    return

                msg = f"🇺🇸 <b>{ticker} CAN SLIM Analysis</b>\n\n"
                msg += f"<b>Overall: {'✅ Pass' if is_pass else '❌ Fail'}</b>\n\n"

                passes = factors.get("passes", {})

                def fmt_val(val):
                    if isinstance(val, float):
                        return f"{val:.1f}"
                    if val == "N/A":
                        return "N/A"
                    return str(val)

                def pass_fail(key):
                    return "✅" if passes.get(key, False) else "❌"

                msg += f"{pass_fail('C')} <b>C (Quarterly)</b>: {fmt_val(factors['C_QtrGrowth'])}% (min: >{self.MIN_QTR_EPS_GROWTH}%)\n"
                msg += f"{pass_fail('A')} <b>A (Annual)</b>: {fmt_val(factors['A_AnnualGrowth'])}% (min: >{self.MIN_ANNUAL_EPS_GROWTH}%)\n"
                msg += f"{pass_fail('N')} <b>N (New High)</b>: ${factors['N_CurrentPrice']:.2f} (within 10% of high)\n"
                msg += f"{pass_fail('I')} <b>I (Institutional)</b>: {fmt_val(factors['I_InstOwnPct'])}% (min: >{self.MIN_INST_OWNERSHIP_PCT}%)\n"
                msg += f"{pass_fail('L')} <b>L (Leader)</b>: {fmt_val(factors['L_RS_vs_Index'])}% (min: >{self.MIN_RS_VS_INDEX_PERF}% vs SPY)\n"

                self.send_telegram_message(msg)

            check_thread = threading.Thread(target=check_task, daemon=True)
            check_thread.start()
            return None

        return None

    def _execute_scan_in_thread(self):
        """Execute scan in separate thread."""
        if self.is_scanning:
            self.send_telegram_message(
                "⚠️  Scan already in progress. Please wait for it to complete."
            )
            return

        if not self.scan_lock.acquire(blocking=False):
            self.send_telegram_message(
                "⚠️  Another scan is in progress. Please try again later."
            )
            return

        try:
            self.is_scanning = True
            print("\n🔔 Scan command received - starting scan")
            self.run_scan()
            self.send_telegram_message("✅ Scan complete!")
        except Exception as e:
            print(f"❌ Scan error: {e}")
            self.send_telegram_message(f"❌ Scan error: {str(e)}")
        finally:
            self.is_scanning = False
            self.scan_lock.release()

    def check_telegram_updates(self):
        """Check for Telegram updates and process commands."""
        try:
            url = f"{self.base_url}/getUpdates"
            params = {"offset": self.last_update_id + 1, "timeout": 10}
            response = requests.get(url, params=params, timeout=15)

            if response.status_code == 200:
                data = response.json()
                if data.get("ok") and data.get("result"):
                    for update in data["result"]:
                        self.last_update_id = update["update_id"]

                        if "message" in update and "text" in update["message"]:
                            message_text = update["message"]["text"]
                            chat_id = str(update["message"]["chat"]["id"])

                            if chat_id == str(self.chat_id):
                                reply = self.process_command(message_text)

                                if reply == "SCAN":
                                    self.send_telegram_message(
                                        "🇺🇸 Starting scan..."
                                    )
                                    scan_thread = threading.Thread(
                                        target=self._execute_scan_in_thread,
                                        daemon=True,
                                    )
                                    scan_thread.start()

                                elif reply:
                                    self.send_telegram_message(reply)
        except Exception as e:
            print(f"⚠️  Telegram update error: {e}")

    def start_command_listener(self):
        """Start background Telegram command listener."""

        def listener_loop():
            while True:
                try:
                    self.check_telegram_updates()
                    time.sleep(2)
                except Exception as e:
                    print(f"⚠️  Listener error: {e}")
                    time.sleep(5)

        thread = threading.Thread(target=listener_loop, daemon=True)
        thread.start()
        print("✅ Telegram command listener started")

    # ========================================
    # Stock Data & Pattern Detection
    # ========================================

    def get_stock_data(self, ticker: str, period: str = "6mo") -> Optional[pd.DataFrame]:
        """Get stock data from yfinance."""
        try:
            stock_obj = yf.Ticker(ticker)
            df = stock_obj.history(period=period)
            if df.empty:
                return None
            return df
        except Exception as e:
            print(f"❌ {ticker} data query failed: {e}")
            return None

    def detect_pivot_breakout(self, df: pd.DataFrame, ticker: str) -> Optional[Dict]:
        """Detect pivot point breakout."""
        if df is None or len(df) < 30:
            return None

        try:
            recent = df.tail(30).copy()
            avg_volume = recent["Volume"].iloc[:-1].mean()
            current_volume = recent["Volume"].iloc[-1]
            volume_surge = (current_volume / avg_volume - 1) * 100

            close = recent["Close"].values
            current_price = close[-1]
            resistance = np.max(close[-20:-1])

            breakout = current_price > resistance
            breakout_pct = ((current_price - resistance) / resistance) * 100

            if breakout and volume_surge >= settings.VOLUME_SURGE_MIN and 0 < breakout_pct <= settings.BREAKOUT_MAX:
                signal = {
                    "ticker": ticker,
                    "pattern": "CAN SLIM Pivot Breakout",
                    "resistance": resistance,
                    "current_price": current_price,
                    "breakout_pct": round(breakout_pct, 2),
                    "volume_surge": round(volume_surge, 2),
                }
                return signal
        except Exception:
            pass

        return None

    def get_can_slim_factors(self, ticker_str: str) -> Tuple[bool, Dict]:
        """Get CAN SLIM fundamental factors."""
        factors = {}
        passes = {}
        try:
            ticker = yf.Ticker(ticker_str)
            info = ticker.info

            # C (Current Earnings)
            qtr_growth = info.get("earningsQuarterlyGrowth")
            factors["C_QtrGrowth"] = (
                (qtr_growth * 100) if qtr_growth is not None else "N/A"
            )
            passes["C"] = (
                factors["C_QtrGrowth"] != "N/A"
                and factors["C_QtrGrowth"] >= self.MIN_QTR_EPS_GROWTH
            )

            # A (Annual Earnings)
            annual_growth = info.get("earningsGrowth")
            factors["A_AnnualGrowth"] = (
                (annual_growth * 100) if annual_growth is not None else "N/A"
            )
            passes["A"] = (
                factors["A_AnnualGrowth"] != "N/A"
                and factors["A_AnnualGrowth"] >= self.MIN_ANNUAL_EPS_GROWTH
            )

            # N (New High)
            high_52w = info.get("fiftyTwoWeekHigh", 0)
            low_52w = info.get("fiftyTwoWeekLow", 0)
            current_price = info.get("regularMarketPrice", info.get("currentPrice", 0))

            factors["N_CurrentPrice"] = current_price
            factors["N_52wHigh"] = high_52w
            is_near_high = False
            if high_52w > 0 and current_price > 0 and low_52w > 0:
                is_near_high = (current_price > (high_52w * 0.9)) and (
                    current_price > (low_52w * 1.5)
                )
            passes["N"] = is_near_high

            # S (Supply)
            shares = info.get("sharesOutstanding", 0)
            factors["S_SharesOutstanding"] = shares

            # I (Institutional)
            inst_own = info.get("heldPercentInstitutions", 0)
            factors["I_InstOwnPct"] = (inst_own * 100) if inst_own is not None else 0
            passes["I"] = factors["I_InstOwnPct"] >= self.MIN_INST_OWNERSHIP_PCT

            # L (Leader)
            end = datetime.now()
            start = end - timedelta(days=365)

            stock_hist = yf.download(ticker_str, start=start, end=end, progress=False)
            index_hist = yf.download(
                self.MARKET_INDEX_TICKER, start=start, end=end, progress=False
            )

            # Handle MultiIndex columns from yfinance 0.2.x
            stock_close = stock_hist["Close"]
            if isinstance(stock_close, pd.DataFrame):
                stock_close = stock_close.iloc[:, 0]
            index_close = index_hist["Close"]
            if isinstance(index_close, pd.DataFrame):
                index_close = index_close.iloc[:, 0]

            stock_perf = (
                float(stock_close.iloc[-1]) - float(stock_close.iloc[0])
            ) / float(stock_close.iloc[0])
            index_perf = (
                float(index_close.iloc[-1]) - float(index_close.iloc[0])
            ) / float(index_close.iloc[0])

            factors["L_StockPerf_1Y"] = stock_perf * 100
            factors["L_IndexPerf_1Y"] = index_perf * 100
            rs_perf = (stock_perf - index_perf) * 100
            factors["L_RS_vs_Index"] = rs_perf
            passes["L"] = rs_perf >= self.MIN_RS_VS_INDEX_PERF

            is_pass_all = all(passes.values())
            factors["passes"] = passes

            return is_pass_all, factors

        except Exception as e:
            print(f"  ❌ {ticker_str} CAN SLIM factor query failed: {e}")
            return False, {"error": str(e)}

    def check_market_direction(self) -> Tuple[bool, str]:
        """Check M (Market) direction."""
        try:
            index_data = yf.Ticker(self.MARKET_INDEX_TICKER).history(period="1y")
            if index_data.empty:
                return True, "Index data query failed, proceeding with scan"

            ma50 = index_data["Close"].rolling(window=50).mean().iloc[-1]
            ma200 = index_data["Close"].rolling(window=200).mean().iloc[-1]
            current_price = index_data["Close"].iloc[-1]

            status = []

            is_above_50 = current_price > ma50
            is_above_200 = current_price > ma200
            is_uptrend = is_above_50 and is_above_200

            status.append(f"Price > 50MA: {'✅' if is_above_50 else '❌'}")
            status.append(f"Price > 200MA: {'✅' if is_above_200 else '❌'}")
            status.append(f"50MA > 200MA: {'✅' if ma50 > ma200 else '❌'}")

            msg = (
                f"📈 M ({self.MARKET_INDEX_TICKER}): ${current_price:.2f} | "
                + ", ".join(status)
            )

            return is_uptrend, msg

        except Exception as e:
            return True, f"Index check error: {e}, proceeding with scan"

    def analyze_stock(self, ticker: str) -> Optional[Dict]:
        """Analyze stock with CAN SLIM filters."""
        is_pass, factors = self.get_can_slim_factors(ticker)

        if not is_pass:
            fail_reasons = [k for k, v in factors.get("passes", {}).items() if not v]
            print(f"(CAN SLIM fail: {', '.join(fail_reasons)})")
            return None

        print("(CAN SLIM pass) ✅", end=" ")

        df = self.get_stock_data(ticker)
        if df is None:
            return None

        signal = self.detect_pivot_breakout(df, ticker)

        if signal:
            signal["can_slim_factors"] = factors

        return signal

    # ========================================
    # Message Formatting
    # ========================================

    def format_signal_message(self, signal: Dict) -> str:
        """Format signal as Telegram message."""
        ticker = signal["ticker"]

        msg = f"""
🇺🇸 <b>[CAN SLIM Pivot Breakout!]</b>

🏢 Ticker: <b>{ticker}</b>
💰 Current: ${signal['current_price']:.2f}
🎯 Breakout: ${signal['resistance']:.2f}
📈 Breakout %: {signal['breakout_pct']}%

📊 Volume surge: +{signal['volume_surge']}%
"""

        factors = signal.get("can_slim_factors")
        if factors:
            msg += "\n<b>CAN SLIM Factors (Pass):</b>\n"
            passes = factors.get("passes", {})

            def fmt_val(val):
                if isinstance(val, float):
                    return f"{val:.1f}"
                return str(val)

            def pass_fail(key):
                return "✅" if passes.get(key, False) else "❌"

            msg += f" {pass_fail('C')} C (Quarterly): {fmt_val(factors['C_QtrGrowth'])}%\n"
            msg += f" {pass_fail('A')} A (Annual): {fmt_val(factors['A_AnnualGrowth'])}%\n"
            msg += f" {pass_fail('N')} N (New High): ${factors['N_CurrentPrice']:.2f}\n"
            msg += f" {pass_fail('I')} I (Institutional): {fmt_val(factors['I_InstOwnPct'])}%\n"
            msg += f" {pass_fail('L')} L (Leader): +{fmt_val(factors['L_RS_vs_Index'])}% (vs SPY)\n"

        msg += f"""
✅ Strong buy signal!
⛔ Stop loss: Entry -7~8%

⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
        return msg

    # ========================================
    # Scanning
    # ========================================

    def run_scan(self) -> List[Dict]:
        """Run scan on watchlist."""
        print(f"\n{'=' * 60}")
        print("🔍 CAN SLIM Scan")
        print(f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

        is_market_uptrend, market_status_msg = self.check_market_direction()
        print(f"\n{market_status_msg}\n")

        if not is_market_uptrend:
            print("⚠️ M (Market) fail: Market in downtrend, skipping scan")
            self.send_telegram_message("⚠️ M (Market) fail: Market in downtrend, skipping scan")
            return []

        print(f"🇺🇸 Stocks: {len(self.watchlist)}")
        print(f"{'=' * 60}\n")

        self.check_positions()

        all_signals = []

        if self.watchlist:
            print("🇺🇸 Scanning stocks (CAN SLIM filters)...\n")
            for ticker in self.watchlist:
                try:
                    print(f"  🔍 {ticker}...", end=" ")
                    signal = self.analyze_stock(ticker)
                    if signal:
                        # Skip if position already exists (avoid duplicate alerts)
                        if position_repo.has_open_position(ticker):
                            print("⚪ (already in position)")
                            continue

                        all_signals.append(signal)
                        msg = self.format_signal_message(signal)
                        self.send_telegram_message(msg)

                        self.add_position(
                            ticker=ticker,
                            entry_price=signal["current_price"],
                            pattern=signal["pattern"],
                            signal=signal,
                        )
                        print("✅ Signal!")
                        time.sleep(1)
                    else:
                        print("⚪")
                except Exception as e:
                    print(f"❌ Error: {e}")
            print()

        if all_signals:
            print(f"📊 {len(all_signals)} signals found")
        else:
            print("⚪ No signals")

        print(f"\n{'=' * 60}\n")

        scan_time_str = datetime.now().strftime("%H:%M:%S")

        if all_signals:
            summary_msg = f"✅ [Scan Complete] Found {len(all_signals)} buy signal(s)!"
        else:
            summary_msg = "⚪ [Scan Complete] No new buy signals"

        self.send_telegram_message(f"{summary_msg}\n⏰ ({scan_time_str})")

        return all_signals

    def run_scheduled_scan(self) -> List[Dict]:
        """Run scheduled scan based on market hours."""
        if self.is_scanning:
            print("\n⏸️  Manual scan in progress. Skipping this cycle...\n")
            return []

        if not self.is_market_open():
            print(f"\n⏸️  US market closed. Waiting for next session...")
            self.check_positions()
            return []

        return self.run_scan()
