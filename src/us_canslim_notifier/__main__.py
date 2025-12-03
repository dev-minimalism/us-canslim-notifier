"""Entry point for running the bot as a module: python -m us_canslim_notifier"""

import sys
import time
from datetime import datetime, timedelta

from .bot import CANSLIMDetector
from .settings import settings


def run_bot():
    """Run the Telegram bot."""
    if not settings.is_configured():
        print("⚠️  To configure .env file:")
        print("   1. Copy .env.example to .env")
        print("   2. Edit .env and set TELEGRAM_TOKEN and CHAT_ID")
        print("\nExiting.\n")
        return

    print("✅ Settings loaded from .env\n")

    # Initialize bot
    detector = CANSLIMDetector(settings.TELEGRAM_TOKEN, settings.CHAT_ID)

    # Start Telegram command listener
    detector.start_command_listener()

    # Start message
    is_open = detector.is_market_open()
    status_text = "🇺🇸 US market OPEN" if is_open else "⏸️  US market closed"

    start_msg = f"""
🤖 <b>CAN SLIM Bot Started</b>

📊 Watchlist: {len(detector.watchlist)} stocks
📍 Open positions: {len(detector.get_positions())}
⏰ Scan interval: {settings.SCAN_INTERVAL // 60} min
🕐 Status: {status_text}

📈 Auto scan: US market (22:30-06:00 KST)

🎯 Auto position tracking:
   • Auto-record on buy signal
   • Stop loss (-8%), Take profit (+20%), 30-day expiry

💬 Commands:
   /check [ticker] - Check CAN SLIM factors
   /scan - Scan all stocks
   /positions - View positions
   /help - All commands

Start time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
    detector.send_telegram_message(start_msg)
    print(start_msg)

    # Main loop
    try:
        while True:
            detector.run_scheduled_scan()

            next_scan = datetime.now() + timedelta(seconds=settings.SCAN_INTERVAL)
            print(f"⏰ Next scan: {next_scan.strftime('%Y-%m-%d %H:%M:%S')}")
            print(f"💤 Waiting {settings.SCAN_INTERVAL // 60} min...\n")
            time.sleep(settings.SCAN_INTERVAL)

    except KeyboardInterrupt:
        print("\n\n⛔ Shutting down")
        detector.send_telegram_message("⛔ CAN SLIM Bot stopped")


def run_backtest():
    """Run backtesting with settings from .env."""
    from .backtest import run_backtest as _run_backtest

    print("🧪 Starting backtest with .env settings...\n")
    _run_backtest()


def main():
    """Main entry point."""
    if len(sys.argv) > 1:
        command = sys.argv[1].lower()
        if command == "backtest":
            run_backtest()
            return
        elif command in ("--help", "-h", "help"):
            print("Usage: python -m us_canslim_notifier [command]")
            print()
            print("Commands:")
            print("  (none)     Run Telegram bot")
            print("  backtest   Run backtesting")
            print("  help       Show this message")
            return
        else:
            print(f"Unknown command: {command}")
            print("Use 'help' for available commands.")
            return

    run_bot()


if __name__ == "__main__":
    main()
