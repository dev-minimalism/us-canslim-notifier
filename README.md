# US CAN SLIM Notifier

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

- **자동 포지션 관리 (DB 기반)**
  - PostgreSQL + SSH 터널 지원
  - 손절 -8%, 익절 +20%, 30일 만료
  - 트레이딩 성과 추적

- **텔레그램 봇 연동**
  - 실시간 알림 (중복 알림 방지)
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
| `/close AAPL` | 포지션 수동 종료 |
| `/performance` | 트레이딩 성과 보기 |
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
MIN_QTR_EPS_GROWTH=25.0
MIN_ANNUAL_EPS_GROWTH=25.0
MIN_INST_OWNERSHIP_PCT=10.0
MIN_RS_VS_INDEX_PERF=10.0

# 백테스트 설정 (선택)
BACKTEST_START_DATE=2020-01-01
BACKTEST_END_DATE=2024-12-31
BACKTEST_INITIAL_CAPITAL=100000
BACKTEST_POSITION_SIZE_PCT=0.1
# BACKTEST_TICKERS=AAPL,MSFT,NVDA  # 미지정 시 기본 20개 종목
BACKTEST_STOP_LOSS_PCT=0.08
BACKTEST_TAKE_PROFIT_PCT=0.20
BACKTEST_HOLDING_DAYS_MAX=30

# PostgreSQL 설정 (포지션 관리용)
SSH_HOST=your_ssh_host
SSH_PORT=22
SSH_USER=your_ssh_user
SSH_KEY_PATH=~/.ssh/id_rsa
DB_HOST=localhost
DB_PORT=5432
DB_NAME=us_canslim_notifier_db
DB_USER=your_db_user
DB_PASSWORD=your_db_password
```

## Database Setup

PostgreSQL을 사용한 포지션 관리를 위해 DB 설정이 필요합니다.

```bash
# 1. DB 생성 (서버에서 직접 또는 스크립트로)
python scripts/init_db.py

# 2. 연결 테스트
python scripts/test_db.py
```

DB 스키마:
- `positions` - 열린/닫힌 포지션 저장
- `trade_history` - 종료된 거래 이력 (성과 분석용)

> DB 설정이 없으면 포지션 관리 기능이 비활성화됩니다.

## Project Structure

```
us-canslim-notifier/
├── src/us_canslim_notifier/
│   ├── __main__.py      # 진입점
│   ├── bot.py           # 메인 봇 클래스
│   ├── settings.py      # 환경 설정
│   ├── database.py      # SSH 터널 + DB 연결
│   ├── repository.py    # 포지션 CRUD
│   └── backtest/        # 백테스트 모듈
├── scripts/
│   ├── init_db.py       # DB 생성 스크립트
│   └── test_db.py       # 연결 테스트
├── tests/
├── .env.example
├── pyproject.toml
└── README.md
```

## Data Source

- **미국 주식**: yfinance (가격 + 펀더멘털)

## License

MIT
