# 네이버 SMS 자동화 리팩토링 프로젝트

네이버 플레이스 크롤링을 통해 예약 정보를 가져와서 자동으로 SMS를 발송하는 AWS Lambda 기반 시스템입니다.

## 프로젝트 개요

이 프로젝트는 다비스튜디오의 네이버 플레이스 예약 시스템을 자동화하여 고객에게 예약 확정 및 안내 SMS를 자동으로 발송하는 시스템입니다.

### 주요 기능

- 네이버 플레이스 예약 정보 크롤링
- 예약 확정 SMS 자동 발송
- 예약 2시간 전 안내 SMS 발송
- 옵션 이벤트 SMS 발송
- AWS DynamoDB를 통한 발송 이력 관리
- 텔레그램 봇을 통한 알림

## 프로젝트 구조

```
naver_sms_auto_refact/
├── original_code/
│   ├── lambda_function.py    # 메인 Lambda 함수
│   └── sens_sms.py          # 네이버 클라우드 SENS SMS API 모듈
├── current_lambda_inform.md # AWS Lambda 설정 정보
└── README.md               # 프로젝트 문서
```

## 기술 스택

- **Python 3.7+**
- **AWS Lambda** - 서버리스 실행 환경
- **AWS DynamoDB** - 데이터 저장
- **Selenium** - 웹 크롤링
- **네이버 클라우드 SENS** - SMS 발송
- **텔레그램 봇** - 알림

## 설치 및 설정

### 1. AWS Lambda 설정

- Python 3.7 런타임 사용
- 메모리: 512MB
- 타임아웃: 5분
- 레이어: ChromeDriver, Selenium

### 2. 환경 변수 설정

다음 환경 변수들을 Lambda 함수에 설정해야 합니다:

```bash
# AWS 설정
AWS_ACCESS_KEY_ID=your_access_key
AWS_SECRET_ACCESS_KEY=your_secret_key

# 네이버 클라우드 SENS 설정
SENS_ACCESS_KEY=your_sens_access_key
SENS_SECRET_KEY=your_sens_secret_key

# 텔레그램 봇 설정
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_CHAT_ID=your_chat_id

# 네이버 로그인 정보
NAVER_USERID=your_naver_id
NAVER_PASSWORD=your_naver_password
```

### 3. DynamoDB 테이블 생성

다음 테이블들을 생성해야 합니다:

- `sms` - SMS 발송 이력 저장
- `session` - 네이버 로그인 세션 저장

## 사용법

### Lambda 함수 배포

1. 프로젝트 파일들을 ZIP으로 압축
2. AWS Lambda 콘솔에서 함수 생성
3. 코드 업로드 및 환경 변수 설정
4. EventBridge를 통한 20분마다 실행 설정

### 주요 함수

- `lambda_handler()` - 메인 핸들러 함수
- `reservation_check()` - 예약 확인 및 SMS 발송
- `option_sms_check()` - 옵션 이벤트 SMS 발송
- `send_sms()` - SMS 발송 함수

## SMS 템플릿

### 예약 확정 SMS
- 예약 확정 안내
- 이용 방법 및 주의사항
- 제공 서비스 안내

### 안내 SMS (2시간 전)
- 도어락 비밀번호
- 와이파이 정보
- 주차 안내
- 이용 매뉴얼 링크

### 옵션 이벤트 SMS
- 리뷰 이벤트 안내
- 네이버/인스타그램 리뷰 방법

## 보안 주의사항

⚠️ **중요**: 이 프로젝트에는 민감한 정보가 포함되어 있습니다:

- AWS 계정 정보
- 네이버 로그인 정보
- API 키 및 토큰
- 전화번호 매핑 정보

프로덕션 환경에서는 반드시 환경 변수나 AWS Secrets Manager를 사용하여 보안을 강화하세요.

## 라이선스

이 프로젝트는 개인 사용 목적으로 개발되었습니다.

## 문의

프로젝트에 대한 문의사항이 있으시면 이슈를 생성해 주세요.
