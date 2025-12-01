# CAN SLIM Bot

William O'Neil의 CAN SLIM 투자 전략을 기반으로 한 미국 주식 매매 신호 탐지 시스템입니다.

## Features

- **CAN SLIM 펀더멘털 필터**
  - C: 분기 EPS 성장률 > 25%
  - A: 연간 EPS 성장률 > 25%
  - N: 52주 신고가 근접 (10% 이내)
  - S: 유통 주식 수
  - L: 상대 강도 (SPY 대비 > 10%)
  - I: 기관 보유율 > 10%
  - M: 시장 방향성 (SPY 50/200일 이평선)

- **기술적 신호 탐지**
  - 피벗 포인트 돌파 (20일 고점 + 거래량 50%+ 급증)

- **자동 포지션 관리**
  - 손절 -8%, 익절 +20%, 30일 만료

- **텔레그램 봇 연동**
  - 실시간 알림
  - 명령어로 종목 관리

## Installation

```bash
# 저장소 클론
git clone https://github.com/dev-minimalism/can-slim-bot.git
cd can-slim-bot

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
python -m can_slim_bot

# 또는 CLI 명령어
can-slim-bot
```

### 텔레그램 명령어

| 명령어 | 설명 |
|--------|------|
| `/scan` | 전체 스캔 |
| `/check NVDA` | 종목 CAN SLIM 팩터 조회 |
| `/positions` | 현재 포지션 보기 |
| `/add AAPL` | 종목 추가 |
| `/remove AAPL` | 종목 제거 |
| `/list` | 감시 종목 목록 |
| `/status` | 시장 상태 확인 |
| `/help` | 도움말 |

### 백테스트

```python
from can_slim_bot.backtest import run_backtest, BacktestConfig

# 기본 설정으로 실행
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
# 필수
TELEGRAM_TOKEN=your_bot_token
CHAT_ID=your_chat_id

# 선택 (기본값)
SCAN_INTERVAL=1800
MIN_QTR_EPS_GROWTH=25.0
MIN_ANNUAL_EPS_GROWTH=25.0
MIN_INST_OWNERSHIP_PCT=10.0
MIN_RS_VS_INDEX_PERF=10.0
```

## Project Structure

```
can-slim-bot/
├── src/can_slim_bot/
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
