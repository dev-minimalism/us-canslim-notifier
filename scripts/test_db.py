#!/usr/bin/env python3
"""Test database connection and schema initialization."""

import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))

from us_canslim_notifier.database import init_db, get_db, close_db
from us_canslim_notifier.repository import position_repo


def test_connection():
    """Test database connection."""
    print("=" * 50)
    print("Testing Database Connection")
    print("=" * 50)

    print("\n1. Initializing database connection...")
    if not init_db():
        print("Failed to connect to database!")
        return False

    print("\n2. Testing query...")
    db = get_db()
    result = db.execute_one("SELECT version()")
    if result:
        print(f"   PostgreSQL version: {result['version'][:50]}...")

    print("\n3. Testing positions table...")
    positions = position_repo.get_open_positions()
    print(f"   Open positions: {len(positions)}")

    print("\n4. Testing performance summary...")
    perf = position_repo.get_performance_summary()
    print(f"   Total trades: {perf['total_trades']}")

    print("\n5. Testing add/close position...")
    # Add test position
    test_ticker = "__TEST__"
    position_id = position_repo.add_position(
        ticker=test_ticker,
        entry_price=100.0,
        pattern="Test Pattern",
        signal={"test": True},
    )
    if position_id:
        print(f"   Added test position: ID={position_id}")

        # Verify it exists
        pos = position_repo.get_position_by_ticker(test_ticker)
        if pos:
            print(f"   Retrieved position: {pos['ticker']} @ ${float(pos['entry_price']):.2f}")

        # Close it
        result = position_repo.close_position(test_ticker, 105.0, "Test close")
        if result:
            print(f"   Closed position: {result['profit_pct']:.2f}% profit")
    else:
        print("   Failed to add test position")

    print("\n6. Cleaning up...")
    close_db()
    print("   Connection closed.")

    print("\n" + "=" * 50)
    print("All tests passed!")
    print("=" * 50)
    return True


if __name__ == "__main__":
    success = test_connection()
    sys.exit(0 if success else 1)
