"""Position repository for database operations."""

import json
from datetime import datetime
from typing import Dict, List, Optional

from .database import get_db


class PositionRepository:
    """Repository for position CRUD operations."""

    def get_open_positions(self) -> List[Dict]:
        """
        Get all open positions.

        Returns:
            List of position dicts
        """
        try:
            db = get_db()
            if db._connection is None:
                return []
            rows = db.execute(
                """
                SELECT id, ticker, entry_price, entry_date, pattern,
                       stop_loss, take_profit, signal_data, status
                FROM positions
                WHERE status = 'open'
                ORDER BY entry_date DESC
                """
            )
            return [self._row_to_dict(row) for row in rows]
        except Exception as e:
            print(f"  ❌ DB error (get_open_positions): {e}")
            return []

    def get_position_by_ticker(self, ticker: str) -> Optional[Dict]:
        """
        Get open position by ticker.

        Args:
            ticker: Stock ticker symbol

        Returns:
            Position dict or None
        """
        try:
            db = get_db()
            if db._connection is None:
                return None
            row = db.execute_one(
                """
                SELECT id, ticker, entry_price, entry_date, pattern,
                       stop_loss, take_profit, signal_data, status
                FROM positions
                WHERE ticker = %s AND status = 'open'
                """,
                (ticker.upper(),),
            )
            return self._row_to_dict(row) if row else None
        except Exception as e:
            print(f"  ❌ DB error (get_position_by_ticker): {e}")
            return None

    def add_position(
        self,
        ticker: str,
        entry_price: float,
        pattern: str,
        signal: Dict,
        stop_loss_pct: float = 0.08,
        take_profit_pct: float = 0.20,
    ) -> Optional[int]:
        """
        Add new position.

        Args:
            ticker: Stock ticker symbol
            entry_price: Entry price
            pattern: Pattern name
            signal: Signal data dict
            stop_loss_pct: Stop loss percentage (default 8%)
            take_profit_pct: Take profit percentage (default 20%)

        Returns:
            Position ID or None
        """
        try:
            db = get_db()
            if db._connection is None:
                print(f"  ⚠️  DB not connected, cannot add position for {ticker}")
                return None
            stop_loss = entry_price * (1 - stop_loss_pct)
            take_profit = entry_price * (1 + take_profit_pct)

            row = db.execute_one(
                """
                INSERT INTO positions (
                    ticker, entry_price, entry_date, pattern,
                    stop_loss, take_profit, signal_data, status
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, 'open')
                RETURNING id
                """,
                (
                    ticker.upper(),
                    entry_price,
                    datetime.now(),
                    pattern,
                    stop_loss,
                    take_profit,
                    json.dumps(signal),
                ),
            )
            return row["id"] if row else None
        except Exception as e:
            print(f"  ❌ DB error (add_position {ticker}): {e}")
            return None

    def close_position(
        self,
        ticker: str,
        exit_price: float,
        reason: str,
    ) -> Optional[Dict]:
        """
        Close position and record to trade history.

        Args:
            ticker: Stock ticker symbol
            exit_price: Exit price
            reason: Exit reason

        Returns:
            Closed position info or None
        """
        try:
            db = get_db()
            if db._connection is None:
                print(f"  ⚠️  DB not connected, cannot close position for {ticker}")
                return None

            # Get the position
            position = self.get_position_by_ticker(ticker)
            if not position:
                return None

            entry_price = float(position["entry_price"])
            profit_pct = ((exit_price - entry_price) / entry_price) * 100
            entry_date = position["entry_date"]
            exit_date = datetime.now()
            holding_days = (exit_date - entry_date).days

            # Update position to closed
            db.execute(
                """
                UPDATE positions
                SET status = 'closed',
                    exit_price = %s,
                    exit_date = %s,
                    exit_reason = %s,
                    profit_pct = %s,
                    holding_days = %s,
                    updated_at = %s
                WHERE id = %s
                """,
                (
                    exit_price,
                    exit_date,
                    reason,
                    profit_pct,
                    holding_days,
                    exit_date,
                    position["id"],
                ),
            )

            # Insert into trade history
            db.execute(
                """
                INSERT INTO trade_history (
                    position_id, ticker, entry_price, exit_price,
                    entry_date, exit_date, profit_pct, holding_days,
                    exit_reason, pattern
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    position["id"],
                    ticker.upper(),
                    entry_price,
                    exit_price,
                    entry_date,
                    exit_date,
                    profit_pct,
                    holding_days,
                    reason,
                    position.get("pattern"),
                ),
            )

            return {
                "ticker": ticker,
                "entry_price": entry_price,
                "exit_price": exit_price,
                "profit_pct": profit_pct,
                "holding_days": holding_days,
                "reason": reason,
                "pattern": position.get("pattern"),
            }
        except Exception as e:
            print(f"  ❌ DB error (close_position {ticker}): {e}")
            return None

    def has_open_position(self, ticker: str) -> bool:
        """
        Check if ticker has an open position.

        Args:
            ticker: Stock ticker symbol

        Returns:
            True if open position exists
        """
        try:
            db = get_db()
            if db._connection is None:
                return False
            row = db.execute_one(
                """
                SELECT COUNT(*) as cnt FROM positions
                WHERE ticker = %s AND status = 'open'
                """,
                (ticker.upper(),),
            )
            return row["cnt"] > 0 if row else False
        except Exception as e:
            print(f"  ❌ DB error (has_open_position {ticker}): {e}")
            return False

    def get_trade_history(
        self,
        limit: int = 50,
        ticker: Optional[str] = None,
    ) -> List[Dict]:
        """
        Get trade history.

        Args:
            limit: Max number of records
            ticker: Optional ticker filter

        Returns:
            List of trade history dicts
        """
        try:
            db = get_db()
            if db._connection is None:
                return []

            if ticker:
                rows = db.execute(
                    """
                    SELECT * FROM trade_history
                    WHERE ticker = %s
                    ORDER BY exit_date DESC
                    LIMIT %s
                    """,
                    (ticker.upper(), limit),
                )
            else:
                rows = db.execute(
                    """
                    SELECT * FROM trade_history
                    ORDER BY exit_date DESC
                    LIMIT %s
                    """,
                    (limit,),
                )

            return [dict(row) for row in rows]
        except Exception as e:
            print(f"  ❌ DB error (get_trade_history): {e}")
            return []

    def get_performance_summary(self) -> Dict:
        """
        Get overall trading performance summary.

        Returns:
            Performance summary dict
        """
        default_result = {
            "total_trades": 0,
            "winning_trades": 0,
            "losing_trades": 0,
            "win_rate": 0.0,
            "avg_profit_pct": 0.0,
            "total_profit_pct": 0.0,
            "max_profit_pct": 0.0,
            "max_loss_pct": 0.0,
            "avg_holding_days": 0,
        }

        try:
            db = get_db()
            if db._connection is None:
                return default_result

            row = db.execute_one(
                """
                SELECT
                    COUNT(*) as total_trades,
                    COUNT(CASE WHEN profit_pct > 0 THEN 1 END) as winning_trades,
                    COUNT(CASE WHEN profit_pct <= 0 THEN 1 END) as losing_trades,
                    COALESCE(AVG(profit_pct), 0) as avg_profit_pct,
                    COALESCE(SUM(profit_pct), 0) as total_profit_pct,
                    COALESCE(MAX(profit_pct), 0) as max_profit_pct,
                    COALESCE(MIN(profit_pct), 0) as max_loss_pct,
                    COALESCE(AVG(holding_days), 0) as avg_holding_days
                FROM trade_history
                """
            )

            if not row or row["total_trades"] == 0:
                return default_result

            total = row["total_trades"]
            winning = row["winning_trades"]
            win_rate = (winning / total * 100) if total > 0 else 0.0

            return {
                "total_trades": total,
                "winning_trades": winning,
                "losing_trades": row["losing_trades"],
                "win_rate": round(win_rate, 1),
                "avg_profit_pct": round(float(row["avg_profit_pct"]), 2),
                "total_profit_pct": round(float(row["total_profit_pct"]), 2),
                "max_profit_pct": round(float(row["max_profit_pct"]), 2),
                "max_loss_pct": round(float(row["max_loss_pct"]), 2),
                "avg_holding_days": round(float(row["avg_holding_days"]), 1),
            }
        except Exception as e:
            print(f"  ❌ DB error (get_performance_summary): {e}")
            return default_result

    def _row_to_dict(self, row: dict) -> Dict:
        """Convert database row to position dict."""
        if not row:
            return {}

        result = dict(row)

        # Parse signal_data JSON if present
        if "signal_data" in result and result["signal_data"]:
            if isinstance(result["signal_data"], str):
                result["signal_data"] = json.loads(result["signal_data"])

        return result


# Global repository instance
position_repo = PositionRepository()
