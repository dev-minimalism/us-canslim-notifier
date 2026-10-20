# US CAN SLIM Notifier

[![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&logoColor=white)](https://www.python.org)
[![yfinance](https://img.shields.io/badge/yfinance-410093)](https://pypi.org/project/yfinance/)
[![Telegram](https://img.shields.io/badge/Telegram-Bot-26A5E4?logo=telegram&logoColor=white)](https://core.telegram.org/bots)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

William O'Neil의 CAN SLIM 투자 전략을 기반으로 한 미국 주식 매매 신호 탐지 시스템입니다.

## Features

- **CAN SLIM 펀더멘털 필터**
  - C: 분기 EPS 성장률 > 25%
  - A: 연간 EPS 성장률 > 25%
  - N: 52주 신고가 근접 (10% 이내) + 52주 저가 대비 50% 이상
  - S: 유통 주식 수
  - L: 상대 강도 (SPY 대비 > 10%)
  - I: 기관 보유율 > 10%
  - M: 시장 방향성 (SPY 50/200일 이평선)

- **기술적 신호 탐지**
  - 피벗 포인트 돌파 (20일 고점 돌파 + 거래량 50%+ 급증, 돌파폭 5% 이내)

- **자동 포지션 관리**
  - 매수 신호 발생 시 포지션 자동 기록
  - 손절 -8%, 익절 +20%, 30일 만료

- **텔레그램 봇 연동**
  - 실시간 알림
  - 명령어로 종목 관리

## Installation

```bash
# 저장소 클론
git clone https://github.com/dev-minimalism/us-canslim-notifier.git
cd us-canslim-notifier

# 가상환경 생성 및 활성화
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# 패키지 설치
pip install -e .

# 환경 설정
cp .env.example .env
# .env 파일에서 TELEGRAM_TOKEN과 CHAT_ID 설정
```

## Usage

### 봇 실행

```bash
# 모듈로 실행
python -m us_canslim_notifier

# 또는 CLI 명령어
us-canslim-notifier
```

### 백그라운드 실행 (서버)

```bash
nohup python -m us_canslim_notifier > bot.log 2>&1 &
```

설명:
- `nohup` - 터미널 종료해도 계속 실행
- `> bot.log` - stdout을 bot.log에 저장
- `2>&1` - stderr도 같은 파일에 저장
- `&` - 백그라운드 실행

날짜별 로그 파일:
```bash
mkdir -p logs
nohup python -u -m us_canslim_notifier > logs/bot_$(date +%Y%m%d).log 2>&1 &
```

> 자동 스캔은 미국 장 시간(한국 시간 22:30-06:00, 주말 제외)에만 실행되며, 서버의 로컬 시간이 KST라고 가정합니다. 서머타임과 미국 휴장일은 반영되지 않습니다.
>
> `watchlist.json`과 `positions.json`은 봇을 실행한 디렉토리에 생성되므로, 항상 같은 디렉토리에서 실행하세요.

유용한 명령어:
```bash
# 실행 확인
ps aux | grep us_canslim_notifier

# 로그 실시간 확인
tail -f bot.log

# 프로세스 종료
pkill -f us_canslim_notifier
```

### 텔레그램 명령어

| 명령어 | 설명 |
|--------|------|
| `/scan` | 전체 스캔 |
| `/check NVDA` | 종목 CAN SLIM 팩터 조회 |
| `/positions` | 현재 포지션 보기 |
| `/close NVDA` | 포지션 수동 청산 |
| `/add AAPL` | 종목 추가 |
| `/remove AAPL` | 종목 제거 |
| `/list` | 감시 종목 목록 |
| `/status` | 시장 상태 확인 |
| `/help` | 도움말 |

### 백테스트

```bash
# CLI로 실행 (.env 설정 사용)
python -m us_canslim_notifier backtest

# 또는
us-canslim-notifier backtest
```

Python 코드에서 직접 실행:

```python
from us_canslim_notifier.backtest import run_backtest, BacktestConfig

# .env 설정으로 실행
run_backtest()

# 커스텀 설정
config = BacktestConfig(
    start_date="2020-01-01",
    end_date="2024-12-31",
    initial_capital=100000.0,
    us_tickers=["AAPL", "MSFT", "NVDA", "GOOGL"],
)
run_backtest(config)
```

## Configuration

`.env` 파일에서 설정:

```env
# 필수 (봇 실행 시)
TELEGRAM_TOKEN=your_bot_token
CHAT_ID=your_chat_id

# CAN SLIM 파라미터 (선택)
SCAN_INTERVAL=1800
MARKET_INDEX_TICKER=SPY
MIN_QTR_EPS_GROWTH=25.0
MIN_ANNUAL_EPS_GROWTH=25.0
MIN_INST_OWNERSHIP_PCT=10.0
MIN_RS_VS_INDEX_PERF=10.0

# 패턴 감지 (선택)
VOLUME_SURGE_MIN=50   # 거래량 급증 기준 (%)
BREAKOUT_MAX=5        # 돌파 허용 최대폭 (%)

# 백테스트 설정 (선택)
BACKTEST_START_DATE=2020-01-01
BACKTEST_END_DATE=2024-12-31
BACKTEST_INITIAL_CAPITAL=100000
BACKTEST_POSITION_SIZE_PCT=0.1
# BACKTEST_TICKERS=AAPL,MSFT,NVDA  # 미지정 시 기본 20개 종목
BACKTEST_STOP_LOSS_PCT=0.08
BACKTEST_TAKE_PROFIT_PCT=0.20
BACKTEST_HOLDING_DAYS_MAX=30
```

전체 설정 항목은 `.env.example`을 참고하세요.

> 실시간 봇의 손절/익절/보유기간(-8% / +20% / 30일)은 코드에 고정되어 있으며, `BACKTEST_*` 리스크 설정은 백테스트에만 적용됩니다.

## Development

```bash
pip install -e ".[dev]"

pytest
black src/
ruff check src/
mypy src/
```

## Project Structure

```
us-canslim-notifier/
├── src/us_canslim_notifier/
│   ├── __main__.py      # 진입점
│   ├── bot.py           # 메인 봇 클래스
│   ├── settings.py      # 환경 설정
│   └── backtest/        # 백테스트 모듈
├── tests/
├── .env.example
├── pyproject.toml
└── README.md
```

## Data Source

- **미국 주식**: yfinance (가격 + 펀더멘털)

## License

MIT
