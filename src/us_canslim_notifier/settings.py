"""Configuration settings loaded from environment variables."""

import os
from dotenv import load_dotenv

# Load .env file
load_dotenv()


class Settings:
    """Application settings from environment variables."""

    # Telegram
    TELEGRAM_TOKEN: str = os.getenv("TELEGRAM_TOKEN", "")
    CHAT_ID: str = os.getenv("CHAT_ID", "")

    # Scan settings
    SCAN_INTERVAL: int = int(os.getenv("SCAN_INTERVAL", "1800"))

    # CAN SLIM parameters
    MARKET_INDEX_TICKER: str = os.getenv("MARKET_INDEX_TICKER", "SPY")
    MIN_QTR_EPS_GROWTH: float = float(os.getenv("MIN_QTR_EPS_GROWTH", "25.0"))
    MIN_ANNUAL_EPS_GROWTH: float = float(os.getenv("MIN_ANNUAL_EPS_GROWTH", "25.0"))
    MIN_INST_OWNERSHIP_PCT: float = float(os.getenv("MIN_INST_OWNERSHIP_PCT", "10.0"))
    MIN_RS_VS_INDEX_PERF: float = float(os.getenv("MIN_RS_VS_INDEX_PERF", "10.0"))

    # Pattern detection
    VOLUME_SURGE_MIN: int = int(os.getenv("VOLUME_SURGE_MIN", "50"))
    BREAKOUT_MAX: int = int(os.getenv("BREAKOUT_MAX", "5"))

    # Risk management
    STOP_LOSS_PERCENT: float = float(os.getenv("STOP_LOSS_PERCENT", "-7.5"))

    # Data settings
    ANALYSIS_PERIOD_DAYS: int = int(os.getenv("ANALYSIS_PERIOD_DAYS", "120"))
    ANALYSIS_PERIOD: str = os.getenv("ANALYSIS_PERIOD", "6mo")

    # SSH Tunnel settings (for PostgreSQL connection)
    SSH_HOST: str = os.getenv("SSH_HOST", "")
    SSH_PORT: int = int(os.getenv("SSH_PORT", "22"))
    SSH_USER: str = os.getenv("SSH_USER", "")
    SSH_KEY_PATH: str = os.path.expanduser(os.getenv("SSH_KEY_PATH", "~/.ssh/id_rsa"))

    # PostgreSQL settings
    DB_HOST: str = os.getenv("DB_HOST", "localhost")
    DB_PORT: int = int(os.getenv("DB_PORT", "5432"))
    DB_NAME: str = os.getenv("DB_NAME", "")
    DB_USER: str = os.getenv("DB_USER", "")
    DB_PASSWORD: str = os.getenv("DB_PASSWORD", "")

    @classmethod
    def is_configured(cls) -> bool:
        """Check if required settings are configured."""
        return bool(
            cls.TELEGRAM_TOKEN
            and cls.TELEGRAM_TOKEN != "YOUR_BOT_TOKEN_HERE"
            and cls.CHAT_ID
        )

    @classmethod
    def is_db_configured(cls) -> bool:
        """Check if database settings are configured."""
        return bool(
            cls.SSH_HOST
            and cls.SSH_USER
            and cls.DB_NAME
            and cls.DB_USER
            and cls.DB_PASSWORD
        )


settings = Settings()
