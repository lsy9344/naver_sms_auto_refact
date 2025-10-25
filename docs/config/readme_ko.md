# 설정 관리

네이버 SMS 자동화 시스템 설정에 대한 완벽 가이드.

## 빠른 시작

### 로컬 개발 환경 설정

1. **환경 변수 설정:**

```bash
export NAVER_USERNAME="your_naver_username"
export NAVER_PASSWORD="your_naver_password"
export SENS_ACCESS_KEY="your_sens_access_key"
export SENS_SECRET_KEY="your_sens_secret_key"
export SENS_SERVICE_ID="your_sens_service_id"
export TELEGRAM_BOT_TOKEN="your_telegram_bot_token"
export TELEGRAM_CHAT_ID="your_telegram_chat_id"
# 로컬 개발 전용 - 프로덕션에서는 Secrets Manager 사용
export SLACK_ENABLED="true"
export SLACK_WEBHOOK_URL="https://hooks.slack.com/services/T1234567890/B1234567890/XXXXXXXXXXXXXXXXXXXX"
```

2. **또는 `.env.local` 파일 생성:**

```bash
NAVER_USERNAME=your_naver_username
NAVER_PASSWORD=your_naver_password
SENS_ACCESS_KEY=your_sens_access_key
SENS_SECRET_KEY=your_sens_secret_key
SENS_SERVICE_ID=your_sens_service_id
TELEGRAM_BOT_TOKEN=your_telegram_bot_token
TELEGRAM_CHAT_ID=your_telegram_chat_id
# 로컬 개발 전용 - 프로덕션에서는 Secrets Manager 사용
SLACK_ENABLED=true
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/T1234567890/B1234567890/XXXXXXXXXXXXXXXXXXXX
```

그 다음 `python-dotenv`를 설치하세요:

```bash
pip install python-dotenv
```

3. **코드에서 설정 로드:**

```python
from src.config.settings import get_settings

settings = get_settings()  # 첫 호출 시 캐시됨
print(f"AWS Region: {settings.aws_region}")
print(f"Stores configured: {len(settings.stores)}")
```

## 설정 소스 (우선순위)

설정은 다음 우선순위 (높음에서 낮음)로 로드됩니다:

### 1. 환경 변수 (가장 높은 우선순위)

다른 모든 소스를 재정의하려면 다음 환경 변수를 설정하세요:

```bash
# Naver 자격 증명
NAVER_USERNAME=username
NAVER_PASSWORD=password

# SENS 자격 증명
SENS_ACCESS_KEY=access_key
SENS_SECRET_KEY=secret_key
SENS_SERVICE_ID=service_id

# Telegram 자격 증명
TELEGRAM_BOT_TOKEN=token
TELEGRAM_CHAT_ID=chat_id

# Slack 설정 (선택 사항 - 기본적으로 비활성화됨)
# 프로덕션용: AWS Secrets Manager에 웹훅 URL 저장
# 로컬 개발용: config/my_slack_webhook.yaml 사용 또는 아래 SLACK_WEBHOOK_URL 설정
SLACK_ENABLED=true
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/T1234567890/B1234567890/XXXXXXXXXXXXXXXXXXXX

# AWS 설정 (선택 사항 - 기본값은 ap-northeast-2)
AWS_REGION=ap-northeast-2
DYNAMODB_TABLE_SMS=sms
DYNAMODB_TABLE_SESSION=session
```

### 2. AWS Secrets Manager

프로덕션 환경에서는 AWS Secrets Manager에 기본 이름으로 자격 증명을 저장합니다:

- `naver-sms-automation/naver-credentials`
- `naver-sms-automation/sens-credentials`
- `naver-sms-automation/telegram-credentials`

**예시 생성:**

```bash
# Naver 자격 증명
aws secretsmanager create-secret \
  --name naver-sms-automation/naver-credentials \
  --secret-string '{
    "username": "your_username",
    "password": "your_password"
  }' \
  --region ap-northeast-2

# SENS 자격 증명
aws secretsmanager create-secret \
  --name naver-sms-automation/sens-credentials \
  --secret-string '{
    "access_key": "your_access_key",
    "secret_key": "your_secret_key",
    "service_id": "your_service_id"
  }' \
  --region ap-northeast-2

# Telegram 자격 증명
aws secretsmanager create-secret \
  --name naver-sms-automation/telegram-credentials \
  --secret-string '{
    "bot_token": "your_bot_token",
    "chat_id": "your_chat_id"
  }' \
  --region ap-northeast-2

# Slack 자격 증명
aws secretsmanager create-secret \
  --name naver-sms-automation/slack-credentials \
  --secret-string '{
    "webhook_url": "https://hooks.slack.com/services/YOUR/WEBHOOK/URL"
  }' \
  --region ap-northeast-2
```

### 3. 로컬 개발 대체 파일

**`.env.local` 파일:**

```bash
# 필요: pip install python-dotenv
NAVER_USERNAME=your_username
NAVER_PASSWORD=your_password
SENS_ACCESS_KEY=your_access_key
SENS_SECRET_KEY=your_secret_key
SENS_SERVICE_ID=your_service_id
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_CHAT_ID=your_chat_id
```

**또는 `config/local-secrets.json` 파일:**

```json
{
  "naver": {
    "username": "your_username",
    "password": "your_password"
  },
  "sens": {
    "access_key": "your_access_key",
    "secret_key": "your_secret_key",
    "service_id": "your_service_id"
  },
  "telegram": {
    "bot_token": "your_bot_token",
    "chat_id": "your_chat_id"
  },
  "slack": {
    "webhook_url": "https://hooks.slack.com/services/T1234567890/B1234567890/XXXXXXXXXXXXXXXXXXXX"
  }
}
```

로컬 secrets 파일을 사용하려면 다음을 설정하세요:

```bash
export USE_LOCAL_SECRETS_FILE=true
export LOCAL_SECRETS_FILE_PATH=config/local-secrets.json
```

### 4. YAML 설정 파일

**`config/stores.yaml`:**

```yaml
default:
  fromNumber: "01055814318"

stores:
  "1051707":
    name: "다비스튜디오 화성점"
    fromNumber: "01055814318"
    templates:
      guide: "1051707"
  
  "867589":
    name: "다비스튜디오 안산 초지점"
    fromNumber: "01022392673"
    templates:
      guide: "867589"
```

**`config/sms_templates.yaml`:**

```yaml
templates:
  confirmation:
    subject: "예약 확정 안내"
    type: "LMS"
    content: |
      다비스튜디오를 찾아주신 고객님, 안녕하세요
      예약 확정되어 이용 안내 드립니다.

  guide_1051707:
    subject: "이용 상세 안내"
    type: "LMS"
    content: |
      다비스튜디오를 찾아주신 고객님, 안녕하세요
      이용 상세 안내 드립니다.
```

**`config/my_slack_webhook.yaml` (Slack 설정 - 로컬 개발):**

```yaml
# https://api.slack.com/messaging/webhooks 에서 웹훅 URL 가져오기
slack webhook url: "https://hooks.slack.com/services/T1234567890/B1234567890/XXXXXXXXXXXXXXXXXXXX"
```

**`config/slack_templates.yaml` (Slack 메시지 템플릿):**

```yaml
templates:
  expert_correction_digest:
    blocks:
      - type: "section"
        text:
          type: "mrkdwn"
          text: |
            🔔 *Expert Correction Digest*
            {{ message }}
            
            Date: {{ today_date }}
```

### 5. 기본값

다른 곳에서 설정되지 않은 경우, 기본값이 사용됩니다:

```python
# AWS 설정
aws_region = "ap-northeast-2"
dynamodb_table_sms = "sms"
dynamodb_table_session = "session"

# 비즈니스 설정
option_keywords = ["네이버", "인스타", "원본"]
rules = []
```

## 설정 필드

### AWS 설정

| 필드 | 타입 | 설명 | 기본값 | 예시 |
|-------|------|-------------|---------|---------|
| `aws_region` | str | AWS 리전 | `ap-northeast-2` | `ap-northeast-2` |
| `dynamodb_table_sms` | str | DynamoDB SMS 테이블 | `sms` | `sms` |
| `dynamodb_table_session` | str | DynamoDB 세션 테이블 | `session` | `session` |

### Naver 자격 증명

| 필드 | 타입 | 설명 | 소스 | 필수 |
|-------|------|-------------|--------|----------|
| `naver_username` | str | Naver 계정 사용자 이름 | Env/Secrets | 예 |
| `naver_password` | str | Naver 계정 비밀번호 | Env/Secrets | 예 |

### SENS 자격 증명

| 필드 | 타입 | 설명 | 소스 | 필수 |
|-------|------|-------------|--------|----------|
| `sens_access_key` | str | SENS API 액세스 키 | Env/Secrets | 예 |
| `sens_secret_key` | str | SENS API 비밀 키 | Env/Secrets | 예 |
| `sens_service_id` | str | SENS 서비스 ID | Env/Secrets | 예 |

### Telegram 자격 증명

| 필드 | 타입 | 설명 | 소스 | 필수 |
|-------|------|-------------|--------|----------|
| `telegram_bot_token` | str | Telegram 봇 토큰 | Env/Secrets | 예 |
| `telegram_chat_id` | str | Telegram 채팅 ID | Env/Secrets | 예 |

### Slack 설정 (스토리 6.2)

| 필드 | 타입 | 설명 | 소스 | 필수 |
|-------|------|-------------|--------|----------|
| `slack_enabled` | bool | Slack 알림 활성화/비활성화 | Env (SLACK_ENABLED) | 아니요 |
| `slack_webhook_url` | str | Slack 수신 웹훅 URL | **Secrets Manager** (권장) / 파일 / Env | 아니요* |

*`slack_enabled=true`인 경우에만 필요합니다. **프로덕션 환경에서는 AWS Secrets Manager에 저장하는 것을 권장합니다.**

### Slack 메시지 템플릿

| 필드 | 타입 | 설명 | 소스 |
|-------|------|-------------|--------|
| `templates` | Dict[str, Template] | Slack 메시지 템플릿 | YAML (config/slack_templates.yaml) |

**템플릿 구조:**

```python
# 템플릿은 Jinja2 템플릿을 지원합니다.
# 예시 변수: {{ message }}, {{ today_date }}, {% for item in items %}
template = {
    "blocks": [  # Slack Block Kit 포맷
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": "Message content with {{ variable }}"
            }
        }
    ]
}
```

### 비즈니스 설정

| 필드 | 타입 | 설명 | 소스 |
|-------|------|-------------|--------|
| `stores` | Dict[str, Store] | 스토어 설정 | YAML |
| `option_keywords` | List[str] | 옵션 감지를 위한 키워드 | YAML/기본값 |
| `rules` | List[Dict] | 규칙 설정 | YAML |

**스토어 구조:**

```python
@dataclass
class Store:
    id: str                    # 스토어 ID (예: "1051707")
    name: str                  # 스토어 이름 (한글)
    fromNumber: str            # SMS 발송 전화번호
    templates: Dict[str, str]  # 템플릿 매핑 (예: {"guide": "1051707"})
```

## 설정 추가 방법

### 새로운 설정 필드 추가

1. **Settings 데이터클래스에 정의** (`src/config/settings.py`):

```python
@dataclass
class Settings:
    # ... 기존 필드 ...
    
    # 새로운 필드
    my_new_setting: str = "default_value"
```

2. **설정 소스에서 로드:**

```python
@staticmethod
def load() -> "Settings":
    settings = Settings()
    # ... 기존 로드 코드 ...
    
    # 환경 또는 YAML에서 새 필드 로드
    if os.getenv("MY_NEW_SETTING"):
        settings.my_new_setting = os.getenv("MY_NEW_SETTING")
    
    return settings
```

3. **이 README에 문서화**

4. `tests/unit/test_config.py`에 **테스트 추가**

### Secrets Manager에 새로운 비밀 추가

1. **Secrets Manager에서 생성:**

```bash
aws secretsmanager create-secret \
  --name naver-sms-automation/my-new-secret \
  --secret-string '{"key": "value"}' \
  --region ap-northeast-2
```

2. **Settings 클래스를 업데이트하여 로드:**

```python
@staticmethod
def _load_credentials_from_env_or_secrets() -> Dict[str, str]:
    credentials = {}
    
    # 새로운 비밀 로드
    try:
        my_secret = Settings._get_secret_value("naver-sms-automation/my-new-secret")
        credentials["my_new_secret"] = my_secret
    except ConfigurationError:
        pass
    
    return credentials
```

3. **Settings 모델에 추가**

4. **테스트 업데이트**

### 새로운 YAML 설정 추가

1. `config/` 디렉토리에 **YAML 파일 생성**:

```bash
# config/my_config.yaml
my_settings:
  key1: value1
  key2: value2
```

2. Settings에 **로더 메서드 추가**:

```python
@staticmethod
def _load_my_config() -> Dict[str, Any]:
    """YAML에서 my_config를 로드합니다."""
    return Settings._load_yaml_file("my_config.yaml")
```

3. **Settings.load() 업데이트**:

```python
@staticmethod
def load() -> "Settings":
    settings = Settings()
    # ... 기존 코드 ...
    
    # 새로운 설정 로드
    my_config_data = Settings._load_my_config()
    # 처리 및 저장...
    
    return settings
```

4. **README에 문서화**

5. **유효성 검사를 위한 테스트 추가**

## Slack 웹훅 설정 (스토리 6.2)

### Slack 웹훅 URL 가져오기

**중요:** `SLACK_WEBHOOK_URL`은 플레이스홀더가 아닌 실제 Slack 인커밍 웹훅 URL이어야 합니다.

**웹훅 URL을 가져오는 단계:**

1. https://api.slack.com/messaging/webhooks 로 이동합니다.
2. "Create New App"을 클릭하거나 기존 앱을 선택합니다.
3. "Incoming Webhooks"를 활성화합니다.
4. "Add New Webhook to Workspace"를 클릭합니다.
5. 대상 채널을 선택하고 승인합니다.
6. 웹훅 URL을 복사합니다 (예시: `https://hooks.slack.com/services/T1234567890/B1234567890/XXXXXXXXXXXXXXXXXXXX`)

**예시 웹훅 URL:**
```
https://hooks.slack.com/services/T1234567890/B1234567890/XXXXXXXXXXXXXXXXXXXX
https://hooks.slack.com/services/TXXXXXXXXXX/BXXXXXXXXXX/YYYYYYYYYYYYYYYYYYYYYY
```

**참고:** 항상 `https://hooks.slack.com/services/`로 시작하며, 그 뒤에 ID와 비밀 토큰이 옵니다.

### 개요

Slack 통합을 통해 규칙 엔진은 Slack 웹훅을 통해 알림을 보낼 수 있습니다. 알림은 규칙 조건이 일치할 때(예: "전문가 수정" 키워드 감지) 트리거됩니다.

### 설정 소스 (우선순위)

Slack 웹훅 URL은 다음 우선순위로 로드됩니다:

1. **AWS Secrets Manager** `naver-sms-automation/slack-credentials` (프로덕션 - 권장)
2. **`config/my_slack_webhook.yaml`** (로컬 개발)
3. **`SLACK_WEBHOOK_URL` 환경 변수** (비상 재정의 전용)

### Slack 알림 활성화/비활성화

Slack 알림은 **기본적으로 비활성화**되어 있습니다. 명시적으로 활성화하세요:

#### 옵션 1: 환경 변수 (프로덕션에는 권장하지 않음)

⚠️ **경고:** 환경 변수는 **로컬 개발**에만 사용하세요. 프로덕션 환경에서는 Secrets Manager를 사용하세요 (옵션 3).

```bash
export SLACK_ENABLED=true
# 실제 웹훅 URL로 대체하세요: https://api.slack.com/messaging/webhooks
export SLACK_WEBHOOK_URL="https://hooks.slack.com/services/T1234567890/B1234567890/XXXXXXXXXXXXXXXXXXXX"
```

#### 옵션 2: 로컬 설정 파일 (로컬 개발)

`config/my_slack_webhook.yaml` 생성:

```yaml
# https://api.slack.com/messaging/webhooks 에서 웹훅 URL 가져오기
slack webhook url: "https://hooks.slack.com/services/T1234567890/B1234567890/XXXXXXXXXXXXXXXXXXXX"
```

그런 다음 활성화:

```bash
export SLACK_ENABLED=true
```

#### 옵션 3: AWS Secrets Manager (프로덕션에 권장) ✅

**이것은 프로덕션에서 Slack 웹훅 URL을 안전하게 저장하는 방법입니다.**

Secrets Manager에서 비밀 생성:

```bash
aws secretsmanager create-secret \
  --name naver-sms-automation/slack-credentials \
  --secret-string '{
    "webhook_url": "https://hooks.slack.com/services/T1234567890/B1234567890/XXXXXXXXXXXXXXXXXXXX"
  }' \
  --region ap-northeast-2
```

**참고:** https://api.slack.com/messaging/webhooks 에서 웹훅 URL을 가져오세요.

그런 다음 Lambda 환경에서 활성화:

```bash
export SLACK_ENABLED=true
```

**장점:**
- ✅ 웹훅 URL은 AWS에서 저장 시 암호화됩니다.
- ✅ CloudTrail을 통해 액세스 로깅됩니다.
- ✅ 재배포 없이 자격 증명을 쉽게 교체할 수 있습니다.
- ✅ Lambda 역할 권한이 액세스를 제어합니다.
- ✅ 코드나 환경 변수에 비밀이 없습니다.

### Slack 메시지 템플릿

메시지 템플릿은 `config/slack_templates.yaml`에 **Jinja2 변수 대체**가 적용된 **Slack Block Kit** 형식으로 정의됩니다:

```yaml
templates:
  expert_correction_digest:
    blocks:
      - type: "section"
        text:
          type: "mrkdwn"
          text: |
            🔔 *Expert Correction Digest*
            
            {{ message }}
            
            Total items: {{ item_count }}
            Date: {{ today_date }}
  
  validation_alert:
    blocks:
      - type: "section"
        text:
          type: "mrkdwn"
          text: |
            ⚠️ *Validation Alert*
            
            Failures: {{ failure_count }}/{{ total_tests }}
            Pass rate: {{ pass_rate }}%
```

### 템플릿 사용 방법

1. **규칙 설정에 정의:**

```yaml
rules:
  - name: "expert_correction_notification"
    conditions:
      - type: "keyword_detected"
        keywords: ["expert correction"]
    actions:
      - type: "send_slack"
        template_name: "expert_correction_digest"
        variables:
          message: "Expert correction detected in booking"
          item_count: 5
```

2. **템플릿 로더가 Jinja2 변수를 처리하고 Slack으로 렌더링합니다.**

3. **웹훅 클라이언트가 렌더링된 메시지를 보냅니다.**

### Slack 실패 처리

Slack 배달 실패는 **치명적이지 않습니다** - 규칙 실행을 차단하지 않습니다:

- **네트워크 오류**: 선형 백오프를 통해 최대 3회 자동으로 재시도합니다.
- **속도 제한** (HTTP 429): `Retry-After` 헤더를 준수합니다.
- **잘못된 웹훅**: 경고로 기록되고 규칙은 계속됩니다.
- **웹훅 비활성화**: `SLACK_ENABLED=false`인 경우 정상적으로 건너뜁니다.

모든 실패는 디버깅을 위한 구조화된 컨텍스트와 함께 기록됩니다.

### Slack 설정 테스트

```bash
# 웹훅 상태를 프로그래밍 방식으로 확인
python -c "
from src.notifications.slack_service import SlackWebhookClient
client = SlackWebhookClient()
print(client.get_webhook_status())
"

# 테스트 알림 보내기
python -c "
from src.notifications.slack_service import SlackWebhookClient
client = SlackWebhookClient()
client.send_slack_webhook_test(webhook_url_masked='https://hooks.slack.com/...', status='success')
"
```

## 문제 해결

### "설정 소스를 찾을 수 없습니다"

이 오류는 어떤 소스에서도 자격 증명을 찾을 수 없음을 의미합니다. 해결 방법:

1. **환경 변수 확인:**

```bash
env | grep -E 'NAVER_|SENS_|TELEGRAM_'
```

2. **로컬 파일 존재 여부 확인:**

```bash
# .env.local의 경우
ls -la .env.local

# local-secrets.json의 경우
ls -la config/local-secrets.json
```

3. **Secrets Manager 액세스 확인:**

```bash
aws secretsmanager get-secret-value \
  --secret-id naver-sms-automation/naver-credentials \
  --region ap-northeast-2
```

4. **AWS 자격 증명 확인:**

```bash
aws sts get-caller-identity
```

### "설정 파일을 찾을 수 없습니다: config/stores.yaml"

이 오류는 stores.yaml 파일이 없음을 의미합니다. 해결 방법:

1. **stores.yaml 생성:**

```bash
mkdir -p config
touch config/stores.yaml
```

2. **유효한 YAML 내용 추가:**

```yaml
stores:
  "1051707":
    name: "테스트 스토어"
    fromNumber: "01055814318"
    templates:
      guide: "1051707"
```

### "stores.yaml의 YAML이 유효하지 않습니다"

YAML 파일에 구문 오류가 있습니다. 해결 방법:

```bash
# YAML 구문 유효성 검사
python -m yaml config/stores.yaml
```

일반적인 문제:
- 탭과 공백 혼용 (공백만 사용)
- 잘못된 들여쓰기
- 키 뒤에 콜론 누락
- 닫히지 않은 따옴표

### 자격 증명이 로드되지 않음

1. **우선순위 확인** - 환경 변수가 모든 것을 재정의합니다:

```bash
# 이들이 우선순위를 갖습니다.
export NAVER_USERNAME=test
```

2. **Secrets Manager 권한 확인** - Lambda 역할에 필요:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "secretsmanager:GetSecretValue"
      ],
      "Resource": "arn:aws:secretsmanager:ap-northeast-2:*:secret:naver-sms-automation/*"
    }
  ]
}
```

3. **KMS 권한 확인** - 비밀이 암호화된 경우:

```json
{
  "Effect": "Allow",
  "Action": [
    "kms:Decrypt"
  ],
  "Resource": "arn:aws:kms:ap-northeast-2:*:key/*"
}
}
```

### "로그에 민감한 필드가 수정되지 않았습니다"

수정 필터가 초기화되었는지 확인하세요:

```python
from src.config.settings import setup_logging_redaction
import logging

# 애플리케이션 시작 시 일찍 호출
setup_logging_redaction()

# 이제 로그 메시지에 자격 증명이 수정되어 표시됩니다.
logger = logging.getLogger(__name__)
logger.info(f"Loaded settings: {settings}")  # 비밀번호는 ****로 표시됩니다.
```

### "Slack 웹훅 URL이 설정되지 않았습니다"

웹훅 URL을 찾을 수 없는 경우 Slack 알림이 비활성화됩니다. 해결 방법:

1. **Slack이 활성화되었는지 확인:**

```bash
echo $SLACK_ENABLED
```

2. **환경 변수 확인:**

```bash
echo $SLACK_WEBHOOK_URL
```

3. **로컬 설정 파일 확인:**

```bash
ls -la config/my_slack_webhook.yaml
cat config/my_slack_webhook.yaml
```

4. **Secrets Manager 확인:**

```bash
aws secretsmanager get-secret-value \
  --secret-id naver-sms-automation/slack-credentials \
  --region ap-northeast-2
```

5. **웹훅 URL 형식 확인:**

```bash
# 유효한 Slack 웹훅 URL은 다음으로 시작해야 합니다:
https://hooks.slack.com/services/
```

## 보안 모범 사례

### 1. 자격 증명을 커밋하지 마세요

`.gitignore`에 추가:

```bash
# .gitignore
.env.local
config/local-secrets.json
config/*-secrets.json
```

### 2. 프로덕션에서 IAM 역할 사용

자격 증명을 하드코딩하는 대신:

```python
# Lambda는 실행 역할을 자동으로 사용합니다.
# 코드에 자격 증명이 필요하지 않습니다.
settings = get_settings()
```

### 3. 비밀을 정기적으로 교체하세요

Secrets Manager에서 비밀을 주기적으로 업데이트하세요:

```bash
aws secretsmanager update-secret \
  --secret-id naver-sms-automation/naver-credentials \
  --secret-string '{"username": "new_user", "password": "new_pass"}'
```

### 4. 설정 액세스 감사

CloudTrail을 활성화하여 Secrets Manager 액세스를 모니터링하세요:

```bash
# Secrets Manager에 대한 CloudTrail 로깅 활성화
aws cloudtrail start-logging --trail-name my-trail
```

### 5. 최소 권한 사용

Lambda 역할에 최소한의 필요한 권한을 부여하세요:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "secretsmanager:GetSecretValue"
      ],
      "Resource": "arn:aws:secretsmanager:ap-northeast-2:ACCOUNT:secret:naver-sms-automation/*",
      "Condition": {
        "StringEquals": {
          "secretsmanager:resource/AllowRotationLambdaArn": "arn:aws:lambda:ap-northeast-2:ACCOUNT:function:my-function"
        }
      }
    }
  ]
}
```

## 설정 예시

### 예시 1: 로컬 개발

**`.env.local` 파일:**

```bash
NAVER_USERNAME=dltnduf4318
NAVER_PASSWORD=MyPassword123
SENS_ACCESS_KEY=my_access_key
SENS_SECRET_KEY=my_secret_key
SENS_SERVICE_ID=ncp:sms:kr:service123
TELEGRAM_BOT_TOKEN=123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11
TELEGRAM_CHAT_ID=987654321
SLACK_ENABLED=true
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/T1234567890/B1234567890/XXXXXXXXXXXXXXXXXXXX
```

**`config/stores.yaml`:**

```yaml
default:
  fromNumber: "01055814318"

stores:
  "1051707":
    name: "다비스튜디오 화성점"
    fromNumber: "01055814318"
    templates:
      guide: "1051707"
  
  "951291":
    name: "다비스튜디오 안산 당곡점"
    fromNumber: "01055814318"
    templates:
      guide: "951291"
```

### 예시 2: Secrets Manager를 사용한 프로덕션

모든 자격 증명은 AWS Secrets Manager에 있습니다:

```bash
# 모든 비밀 생성
aws secretsmanager create-secret --name naver-sms-automation/naver-credentials ...
aws secretsmanager create-secret --name naver-sms-automation/sens-credentials ...
aws secretsmanager create-secret --name naver-sms-automation/telegram-credentials ...
aws secretsmanager create-secret --name naver-sms-automation/slack-credentials \
  --secret-string '{"webhook_url": "https://hooks.slack.com/services/..."}'

# Lambda 환경: Slack 활성화
export SLACK_ENABLED=true

# Lambda 역할은 모든 비밀을 읽을 권한이 있습니다.
# 하드코딩된 값이나 .env.local 파일이 없습니다.
# 설정은 안전하고 감사됩니다.
```

### 예시 3: 혼합 설정

```bash
# 환경: 환경 변수에서 중요한 자격 증명
export NAVER_USERNAME=production_user
export NAVER_PASSWORD=secure_password
export SLACK_ENABLED=true
export SLACK_WEBHOOK_URL=https://hooks.slack.com/services/T1234567890/B1234567890/XXXXXXXXXXXXXXXXXXXX

# Secrets Manager: 중요도가 낮은 자격 증명
aws secretsmanager create-secret --name naver-sms-automation/sens-credentials ...
aws secretsmanager create-secret --name naver-sms-automation/telegram-credentials ...

# YAML: 비즈니스 설정
# config/stores.yaml은 모든 스토어를 포함합니다.
# config/slack_templates.yaml은 Slack 메시지 템플릿을 포함합니다.
```

## API 참조

### 설정 로드

```python
from src.config.settings import get_settings, Settings

# 싱글턴 인스턴스 가져오기 (캐시됨)
settings = get_settings()

# 또는 새로운 인스턴스 로드
settings = Settings.load()

# 다시 로드 (주로 테스트용)
from src.config.settings import reload_settings
new_settings = reload_settings()
```

### 설정 액세스

```python
settings = get_settings()

# AWS 설정
region = settings.aws_region
sms_table = settings.dynamodb_table_sms

# 자격 증명
username = settings.naver_username
api_key = settings.sens_access_key

# 비즈니스 설정
for store_id, store in settings.stores.items():
    print(f"Store {store_id}: {store.name}")

# 키워드
for keyword in settings.option_keywords:
    print(keyword)
```

### 수정이 포함된 로깅

수정 필터가 초기화되었는지 확인하세요:

```python
from src.config.settings import setup_logging_redaction
import logging

setup_logging_redaction()
logger = logging.getLogger(__name__)

# 로그에 자격 증명이 수정된 설정이 표시됩니다.
logger.info(f"Configuration loaded: {settings}")
# 출력: Configuration loaded: Settings(naver_password=****, ...)
```

## 참조

- [설정 데이터클래스 문서](../../src/config/settings.py)
- [Slack 서비스 문서](../../src/notifications/slack_service.py)
- [Slack 통합 테스트](../../tests/integration/test_slack_integration.py)
- [Slack 통합 가이드](../testing/slack-integration.md)
- [스토리 6.2: Slack 통합 추가](../stories/6.2.add-slack-integration.md)
- [의존성 주입 가이드](./INTEGRATION.md)
- [AWS Secrets Manager 문서](https://docs.aws.com/secretsmanager/)
- [Slack 인커밍 웹훅](https://api.slack.com/messaging/webhooks)
- [Slack 블록 키트](https://api.slack.com/block-kit)