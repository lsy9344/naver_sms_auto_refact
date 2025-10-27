# Naver SMS Automation - Brownfield Architecture Document

## Introduction

This document captures the **CURRENT STATE** of the Naver SMS Automation system, including technical debt, hardcoded business logic, and real-world implementation patterns. It serves as a comprehensive reference for AI agents working on the planned refactoring and modernization efforts.

### Document Scope

**Focused on areas relevant to:**
1. **Flexible Rule Engine Refactoring**: Transforming hardcoded conditions/actions into configurable rule-based system
2. **AWS Lambda Modernization**: Migrating from Python 3.7 Lambda Layers to ECR container-based deployment
3. **Python 3.11+ Migration**: Upgrading from deprecated Python 3.7 runtime
4. **Modular Architecture**: Breaking down monolithic Lambda into maintainable modules

**Critical Preservation Requirements:**
- Naver platform login mechanism (cookie reuse strategy) - **MUST follow original code 100%**
- SENS SMS API integration
- Current SMS templates and formats
- Store list management
- All existing functionality must continue to work

### Change Log

| Date       | Version | Description                                    | Author   |
|------------|---------|------------------------------------------------|----------|
| 2025-10-18 | 1.0     | Initial brownfield analysis for refactoring    | Winston  |

---

## Quick Reference - Key Files and Entry Points

### Critical Files for Understanding the System

| File Path | Purpose | Lines of Code | Critical? |
|-----------|---------|---------------|-----------|
| `oroginal_code/lambda_function.py` | **Main Lambda handler** - Contains all business logic, Naver login, booking processing | ~449 | ⚠️ **CRITICAL** |
| `oroginal_code/sens_sms.py` | **SENS SMS API client** - SMS sending logic with store-specific templates | ~619 | ⚠️ **CRITICAL** |
| `requirements.txt` | Python dependencies | 3 | Required |
| `current_lambda_inform.md` | Current AWS Lambda configuration details | N/A | Reference |
| `requierment.md` | Enhancement requirements (Korean) | N/A | **Required Reading** |

### Key Entry Points

- **Lambda Handler**: `lambda_function.lambda_handler(event, context)` at line 405
- **Reservation Processing**: `lambda_function.reservation_check(user_data)` at line 131
- **Option SMS Processing**: `lambda_function.option_sms_check(user_data)` at line 176
- **SMS Sending**: `sens_sms.Sens_sms` class with methods:
  - `send_confirm_sms(phone, store_id)` at line 97
  - `send_guide_sms(store_id, phone)` at line 160
  - `send_event_sms(phone, store_id)` at line 580

### Enhancement Impact Areas (Planned Refactoring)

**Files That Will Be Modified:**
- `lambda_function.py` - Complete restructure into modules
- `sens_sms.py` - Refactor to use configurable templates

**New Modules Needed:**
- Rule engine (conditions + actions framework)
- Configuration management
- Notification abstraction (SMS, Slack, etc.)
- Store/booking domain models
- Container setup (Dockerfile, ECR deployment)

---

## High Level Architecture

### System Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                     AWS EventBridge (Trigger)                    │
│                    Every 20 minutes (Cron)                       │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                   AWS Lambda Function                            │
│              (Python 3.7 - DEPRECATED ⚠️)                        │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  1. Login to Naver (Selenium + Cookie Cache)             │  │
│  │  2. Fetch Bookings via Naver Booking API                 │  │
│  │  3. Process Conditions & Actions (HARDCODED)             │  │
│  │  4. Send SMS via SENS API                                │  │
│  │  5. Update DynamoDB                                      │  │
│  │  6. Send Telegram Notification                           │  │
│  └──────────────────────────────────────────────────────────┘  │
└───┬──────────────────┬──────────────────┬──────────────────┬───┘
    │                  │                  │                  │
    ▼                  ▼                  ▼                  ▼
┌─────────┐    ┌──────────────┐   ┌─────────────┐   ┌──────────┐
│DynamoDB │    │Naver Booking │   │ Naver Cloud │   │ Telegram │
│  Tables │    │     API      │   │  SENS SMS   │   │   Bot    │
│         │    │              │   │     API     │   │   API    │
│ - sms   │    └──────────────┘   └─────────────┘   └──────────┘
│ - session│
└─────────┘
```

### Current Execution Flow

```
EventBridge Trigger (Every 20 min)
    │
    ├─> lambda_handler()
    │       │
    │       ├─> session_get_db() - Get cached Naver cookies
    │       │       │
    │       │       ├─> [If cookies exist] -> login(cookies) -> Validate
    │       │       │                              │
    │       │       │                              ├─> [Valid] Continue
    │       │       │                              └─> [Invalid] Fresh login
    │       │       │
    │       │       └─> [No cookies] -> login(None) -> Fresh Selenium login
    │       │
    │       ├─> Convert Selenium session to requests.Session
    │       │
    │       ├─> get_complete_items() - Fetch RC08 (completed) bookings
    │       │       │
    │       │       └─> For each store in biz_list:
    │       │               └─> get_items(store, 'RC08', date_range)
    │       │
    │       ├─> For each store in biz_list:
    │       │       └─> get_items(store, 'RC03') - Fetch confirmed bookings
    │       │
    │       ├─> reservation_check(user_data)
    │       │       │
    │       │       └─> For each booking:
    │       │               ├─> Check DB for existing record
    │       │               ├─> [New booking] -> Send confirm SMS (type 1)
    │       │               │                 -> If within 2hrs: Send guide SMS (type 2)
    │       │               │
    │       │               └─> [Existing] -> If remind_sms=False AND <2hrs:
    │       │                                     -> Send guide SMS (type 2)
    │       │
    │       ├─> option_sms_check(user_complete_data)
    │       │       │
    │       │       └─> [Only if current hour == 20]
    │       │               └─> For each completed booking:
    │       │                       └─> If option_sms=False AND option=True:
    │       │                               -> Send event SMS (type 3)
    │       │
    │       └─> Send Telegram notification with results
    │
    └─> [Exception] -> Send Telegram error notification
```

---

## Technical Summary

### Actual Tech Stack

| Category | Technology | Version | Notes |
|----------|------------|---------|-------|
| **Runtime** | Python | 3.7 | ⚠️ **DEPRECATED** - Lambda warning active |
| **Execution** | AWS Lambda | N/A | 512MB RAM, 5min timeout |
| **Orchestration** | AWS EventBridge | N/A | 20-minute interval trigger |
| **Database** | AWS DynamoDB | N/A | Tables: `sms`, `session` |
| **Web Automation** | Selenium | 4.15.2 | Via Lambda Layer (chromedriver layer) |
| **ChromeDriver** | headless-chromium | N/A | Via Lambda Layer |
| **HTTP Client** | requests | 2.31.0 | For Naver API after Selenium login |
| **AWS SDK** | boto3 | 1.34.0 | DynamoDB operations |
| **SMS Provider** | Naver Cloud SENS | API v2 | REST API for SMS sending |
| **Notification** | Telegram Bot API | N/A | Results reporting |

### Lambda Configuration (Current)

From `current_lambda_inform.md`:

```yaml
Function Name: naverplace_send_inform
Runtime: python3.7  # ⚠️ DEPRECATED WARNING ACTIVE
Memory: 512MB
Timeout: 5min 0sec
Ephemeral Storage: 512MB
Layers:
  - chromedriver (ARN: arn:aws:lambda:ap-northeast-2:654654307503:layer:chromedriver:2)
  - selenium (ARN: arn:aws:lambda:ap-northeast-2:654654307503:layer:selenium:1)
Trigger: EventBridge (20-minute interval)
Region: ap-northeast-2 (Seoul)
```

### Known AWS Lambda Issues

1. **Python 3.7 Deprecated**: Active AWS warning - runtime no longer supported
2. **Lambda Layers Limitation**: Selenium + ChromeDriver dependencies difficult to manage
3. **Cold Start Performance**: Selenium initialization on cold starts is slow
4. **Size Constraints**: Lambda Layers have size limits

**Proposed Solution**: Migrate to **ECR-based Lambda container deployment**
- Better dependency management
- Newer Python versions (3.11+)
- Easier local development/testing
- No layer size constraints

---

## Source Tree and Module Organization

### Project Structure (Actual)

```text
naver_sms_automation_refactoring/
├── oroginal_code/               # Main application code (typo in folder name)
│   ├── lambda_function.py       # ⚠️ MONOLITHIC - All business logic here
│   └── sens_sms.py              # SMS sending with hardcoded templates
├── venv/                        # Python virtual environment
├── docs/                        # Documentation (this file)
├── requirements.txt             # Python dependencies
├── current_lambda_inform.md     # AWS Lambda config reference
├── requierment.md              # Enhancement requirements (Korean)
├── README.md                    # Project overview (Korean)
├── CLAUDE.md                    # Development partnership guidelines
├── .bmad-core/                  # BMAD framework files
├── agents/                      # AI agent definitions
├── teams/                       # Team configurations
└── expansion-packs/             # BMAD expansion packs
```

### Current Code Organization Problems

⚠️ **Technical Debt - Monolithic Structure:**

1. **lambda_function.py** (~449 lines) contains:
   - Selenium browser setup (global scope)
   - DynamoDB operations
   - Session management
   - Naver login logic
   - Booking data fetching
   - Business rule processing (hardcoded)
   - SMS sending orchestration
   - Date formatting utilities
   - Hardcoded credentials (lines 250-251)
   - Hardcoded store list (line 252)
   - Hardcoded option keywords (line 255)

2. **sens_sms.py** (~619 lines) contains:
   - SENS API authentication
   - 8 different SMS templates (hardcoded strings)
   - Store-to-phone mapping (hardcoded dict)
   - Template selection logic (if/elif chain)

3. **No separation of concerns** - everything mixed together
4. **No configuration management** - all values hardcoded
5. **No abstraction layers** - direct coupling to all external services

---

## Data Models and Persistence

### DynamoDB Tables

#### Table: `sms`

**Purpose**: Track SMS sending history to prevent duplicates

**Schema:**
```python
{
    'booking_num': str,      # Partition Key: "{biz_id}_{book_id}" format
    'phone': str,            # Sort Key: "010-XXXX-XXXX" format
    'name': str,             # Customer name
    'booking_time': str,     # Format: "YYYY-MM-DD HH:MM:SS"
    'confirm_sms': bool,     # Confirmation SMS sent flag
    'remind_sms': bool,      # Reminder SMS sent flag (2hrs before)
    'option_sms': bool,      # Event/option SMS sent flag
    'option_time': str       # Currently unused (empty string)
}
```

**Access Patterns:**
- `get_item(booking_num, phone)` - Check if SMS already sent
- `put_item()` - Create new booking record
- `update_item()` - Update specific SMS flag
- `scan(FilterExpression=Attr('option_sms').eq(False))` - Find bookings needing option SMS

**Indexes**: None (uses primary key only)

#### Table: `session`

**Purpose**: Cache Naver login cookies to avoid repeated Selenium logins

**Schema:**
```python
{
    'id': str,        # Partition Key: Always '1' (single record)
    'cookies': str    # JSON string of Selenium cookies
}
```

**Access Patterns:**
- `get_item(Key={'id': '1'})` - Retrieve cached cookies
- `put_item()` - Update cookies after fresh login

**Cookie Lifecycle:**
1. Lambda starts -> Check for cached cookies
2. If valid -> Reuse for 20-minute execution
3. If invalid/expired -> Fresh Selenium login -> Update cache

### Booking Data Model (In-Memory)

**Source**: Naver Booking API response (see `get_items()` at line 329)

```python
{
    'book_id': int,           # Naver booking ID
    'biz_id': str,            # Store ID (e.g., '1051707')
    'name': str,              # Customer name
    'phone': str,             # Format: "010-XXXX-XXXX"
    'option': bool,           # True if option keywords found in booking
    'reserve_at': datetime    # Reservation datetime (KST, +9hrs)
}
```

**Option Detection Logic** (lines 361-367):
```python
option_keyword_list = ['네이버', '인스타', '원본']
option_tf = False
for option in booking_options:
    for keyword in option_keyword_list:
        if keyword in option['name']:
            option_tf = True
```

### ⚠️ Future Data Field Expansion

**IMPORTANT PLANNING NOTE:**

The booking data fields retrieved from Naver Booking API **will expand in the future**. More customer information will be collected to enable richer business logic and analytics.

**Korean:** 네이버에 요청하는 예약자 데이터 항목은 늘어날 것입니다. 더 많은 정보를 수집할 예정입니다.

**Implications for Architecture:**

1. **Data Model Flexibility Required**
   - The refactored system MUST support dynamic field addition without code changes
   - Additional fields will be provided by the business team in future updates
   - Current 6-field model is minimal viable; expect 10-15+ fields eventually

2. **DynamoDB Schema Considerations**
   - NoSQL nature allows easy field addition
   - Consider if new fields should be indexed (GSI planning)
   - May need new attributes for rule conditions (e.g., customer age, visit count, etc.)

3. **Rule Engine Design Impact**
   - Condition evaluators must support arbitrary field checks
   - Example future conditions:
     - `customer_visit_count > 5` (loyalty customers)
     - `booking_amount > 100000` (high-value bookings)
     - `customer_age_group == '20s'` (demographic targeting)
     - `booking_source == 'mobile_app'` (channel-specific rules)

4. **Recommended Approach**
   - Design rule engine with generic field accessor: `context['booking'].get(field_name)`
   - Store field metadata in configuration (type, validation rules)
   - Add field mapping layer between Naver API and internal model
   - Plan for backward compatibility as fields are added

**Example Future Booking Model:**
```python
{
    # Current fields
    'book_id': int,
    'biz_id': str,
    'name': str,
    'phone': str,
    'option': bool,
    'reserve_at': datetime,

    # Future fields (TBD - to be provided by business team)
    'customer_id': str,           # Naver member ID
    'visit_count': int,           # Number of previous visits
    'booking_amount': int,        # Total booking cost
    'booking_source': str,        # 'web', 'mobile_app', 'phone'
    'customer_age_group': str,    # '10s', '20s', '30s', etc.
    'customer_gender': str,       # 'M', 'F', 'N'
    'special_requests': List[str], # Customer notes
    'payment_method': str,        # 'card', 'cash', 'npay'
    # ... more fields as business requirements evolve
}
```

**Action Item**: When new fields are provided, update:
- `src/domain/booking.py` data model
- `config/rules.yaml` to add new condition examples
- `docs/api-fields.md` field dictionary (create this)
- DynamoDB migration if indexed fields needed

---

## Hardcoded Business Logic Analysis

### Current Conditions (Implicit Rules)

The system currently has **12 hardcoded condition patterns** embedded in the code:

| ID | Condition | Location | Purpose |
|----|-----------|----------|---------|
| C1 | `db_response is None` | lambda_function.py:138 | Detect new booking (never processed) |
| C2 | `reserve_at - timedelta(hours=2) <= now < reserve_at` | lambda_function.py:139 | Within 2-hour window before reservation |
| C3 | `db_response['confirm_sms'] == False` | lambda_function.py:162 | Confirmation SMS not sent |
| C4 | `db_response['remind_sms'] == False` | lambda_function.py:160 | Reminder SMS not sent |
| C5 | `reserve_at > datetime.now()` | lambda_function.py:160 | Reservation in future |
| C6 | `reserve_at - now < timedelta(hours=2)` | lambda_function.py:161 | Less than 2 hours until reservation |
| C7 | `datetime.now().hour == 20` | lambda_function.py:177 | Current time is 8 PM |
| C8 | `db_response['option_sms'] == False` | lambda_function.py:189 | Event SMS not sent |
| C9 | `i['option'] == True` | lambda_function.py:189 | Customer selected special option |
| C10 | `booking_status == 'RC03'` | lambda_function.py:332 | Booking confirmed status |
| C11 | `booking_status == 'RC08'` | get_complete_items() | Booking completed status |
| C12 | Keywords in `option_keyword_list` | lambda_function.py:255, 364 | Option name contains ['네이버', '인스타', '원본'] |

### Current Actions (Implicit)

The system currently has **9 hardcoded action patterns**:

| ID | Action | Location | Purpose |
|----|--------|----------|---------|
| A1 | `send_sms(phone, 1)` | lambda_function.py:152,164 | Send booking confirmation SMS |
| A2 | `send_sms(phone, 2, biz_id)` | lambda_function.py:156,168 | Send 2-hour reminder SMS |
| A3 | `send_sms(phone, 3)` | lambda_function.py:191 | Send event/review SMS |
| A4 | `sms_table.put_item(Item=...)` | lambda_function.py:150 | Create DynamoDB record |
| A5 | `update_item(..., 'confirm_sms')` | lambda_function.py:163 | Mark confirmation sent |
| A6 | `update_item(..., 'remind_sms')` | lambda_function.py:167 | Mark reminder sent |
| A7 | `update_item(..., 'option_sms')` | lambda_function.py:190 | Mark event SMS sent |
| A8 | `results.append(message)` | lambda_function.py:153,157,173,192,195 | Log result for Telegram |
| A9 | `requests.post(telegram_url, ...)` | lambda_function.py:439,444 | Send Telegram notification |

### Current Condition-Action Combinations

**Rule 1: New Booking Handler**
```python
# Location: reservation_check() lines 138-158
IF db_response is None (C1):
    THEN:
        - Create DynamoDB record (A4)
        - Send confirmation SMS (A1)
        - IF within 2-hour window (C2):
            - Send reminder SMS (A2)
```

**Rule 2: Late Reminder Handler**
```python
# Location: reservation_check() lines 160-169
IF confirm_sms == False (C3) AND remind_sms == False (C4)
   AND reserve_at > now (C5) AND < 2 hours (C6):
    THEN:
        - Send confirmation SMS (A1)
        - Update confirm flag (A5)
        - Send reminder SMS (A2)
        - Update remind flag (A6)
```

**Rule 3: Event SMS Handler**
```python
# Location: option_sms_check() lines 177-196
IF current_hour == 20 (C7) AND booking_status == RC08 (C11)
   AND option_sms == False (C8) AND option == True (C9):
    THEN:
        - Send event SMS (A3)
        - Update option flag (A7)
```

---

## Critical Preservation Areas

### ⚠️ MUST PRESERVE 100% - Naver Login Mechanism

**Location**: `lambda_function.py` lines 260-301

**Why Critical**: Naver's login system is complex and this implementation works reliably in production. Cookie reuse strategy minimizes Selenium overhead.

**Key Implementation Details:**

```python
def login(cookies):
    if not cookies:
        # Fresh login via Selenium
        # 1. Navigate to login page
        # 2. Inject credentials via JavaScript (lines 274-276)
        # 3. Submit and wait for redirect
        # 4. Extract and save cookies to DynamoDB
    else:
        # Cookie reuse path
        # 1. Add cookies to driver
        # 2. Navigate to profile page
        # 3. Verify login success by checking URL
        # 4. If failed (URL contains 'login') -> Retry fresh login
```

**Critical Patterns:**
- **JavaScript credential injection** (lines 274-276) - Avoids bot detection
- **Random delays** using `uniform()` (lines 275-279) - Mimics human behavior
- **Cookie validation strategy** (line 298) - Check URL contains "login"
- **Recursive retry** (line 300) - `login(None)` if cookie login fails

**Selenium Configuration** (lines 229-248):
- Headless Chrome with specific user-agent
- `/tmp` directories for Lambda environment
- Specific ChromeDriver binary paths for Lambda

⚠️ **DO NOT MODIFY** this logic unless absolutely necessary. If refactoring, extract as-is into dedicated module.

### ⚠️ MUST PRESERVE - SENS SMS API Integration

**Location**: `sens_sms.py` entire file

**Critical Components:**

1. **Signature Generation** (lines 79-85):
```python
def make_signature(self):
    secret_key_bytes = bytes(self.secret_key, 'UTF-8')
    method = "POST"
    message = method + " " + self.uri + "\n" + self.timestamp + "\n" + self.access_key
    message = bytes(message, 'UTF-8')
    signingKey = base64.b64encode(hmac.new(secret_key_bytes, message, digestmod=hashlib.sha256).digest())
    return signingKey
```

2. **Request Headers** (lines 69-74):
```python
header = {
    "Content-Type": "application/json; charset=utf-8",
    "x-ncp-apigw-timestamp": self.timestamp,
    "x-ncp-iam-access-key": self.access_key,
    "x-ncp-apigw-signature-v2": self.make_signature()
}
```

3. **Store-to-Phone Mapping** (lines 15-24):
```python
_DEFAULT_FROM_MAP = {
    "1466783": "01055814318",
    "1051707": "01055814318",
    # ... etc
    "867589": "01022392673",  # 초지점 (different number)
}
```

**Must Preserve:**
- Signature algorithm
- Header structure
- API endpoint URLs
- Message format structure

**Can Refactor:**
- Template storage (move to config/database)
- Store mapping (move to config)
- Template selection logic (use rule engine)

### MUST PRESERVE - SMS Templates

**Location**: `sens_sms.py` lines 109-602

**Templates (8 store-specific guide templates + 2 common templates):**

1. `booking_confirm_template` (lines 109-140) - Common for all stores
2. `booking_guide_template_1051707` (lines 172-212)
3. `booking_guide_template_951291` (lines 214-248)
4. `booking_guide_template_867589` (lines 250-278)
5. `booking_guide_template_1120125` (lines 280-316)
6. `booking_guide_template_1285716` (lines 317-358)
7. `booking_guide_template_1462519` (lines 359-400)
8. `booking_guide_template_1473826` (lines 401-443)
9. `booking_guide_template_1466783` (lines 444-488)
10. `event_template` (lines 592-602) - Common for all stores

**Content Must Stay Identical** - These contain:
- Store addresses and parking info
- WiFi credentials
- Door lock passwords
- Operating instructions
- Customer service details

**Refactoring Approach:**
- Extract to JSON/YAML configuration
- Keep exact text content
- Add versioning for template changes

### MUST PRESERVE - Store List

**Location**: `lambda_function.py` line 252

```python
biz_list = ['1051707', '951291', '1120125', '1285716', '1462519', '1473826', '1466783', '867589']
```

**Store IDs Map to:**
- Business locations in Naver Booking system
- Specific SMS templates in `sens_sms.py`
- Specific phone numbers for SMS sending

**Refactoring Approach:**
- Move to configuration file/database
- Maintain exact IDs
- Add store metadata (name, address, etc.)

---

## Integration Points and External Dependencies

### External Services

| Service | Purpose | Integration Type | Authentication | Key Files |
|---------|---------|------------------|----------------|-----------|
| **Naver Login** | Access Booking API | Selenium WebDriver | Username/Password + Cookies | lambda_function.py:260-301 |
| **Naver Booking API** | Fetch reservation data | REST API (requests) | Session cookies from Selenium | lambda_function.py:303-388 |
| **Naver Cloud SENS** | Send SMS | REST API | API Key + Signature | sens_sms.py:63-74 |
| **AWS DynamoDB** | Data persistence | boto3 SDK | IAM Role (Lambda execution) | lambda_function.py:18-20 |
| **Telegram Bot** | Notifications | REST API | Bot Token | lambda_function.py:439,444 |

### Naver Booking API Details

**Base URL**: `https://partner.booking.naver.com`

**Endpoints Used:**

1. **Count Bookings** (line 321):
```
GET /v3.1/businesses/{biz_id}/bookings/count?
Params: booking status, date filters, etc.
Returns: {"count": int}
```

2. **Get Bookings** (line 356):
```
GET /api/businesses/{biz_id}/bookings?
Params:
  - bizItemTypes: 'STANDARD'
  - bookingStatusCodes: 'RC03' (confirmed) or 'RC08' (completed)
  - dateFilter: 'USEDATE'
  - page, size: Pagination
Returns: Array of booking objects
```

**Booking Status Codes:**
- `RC03` - Reservation Confirmed (main processing)
- `RC08` - Reservation Completed (for option SMS)

**Required Headers** (lines 305-317):
```python
headers = {
    'authority': 'partner.booking.naver.com',
    'referer': f'https://partner.booking.naver.com/bizes/{biz}/booking-list-view',
    'x-booking-naver-role': 'OWNER',
    # ... standard browser headers
}
```

**Authentication**: Uses cookies from Selenium login session

### API Response Processing

**Booking Object Structure** (extracted lines 358-383):
```python
booking = {
    'bookingId': int,
    'businessId': str,
    'name': str,
    'phone': str,              # Format: '01012345678' (no hyphens)
    'snapshotJson': {
        'startDateTime': str,  # ISO format: 'YYYY-MM-DDTHH:MM:SSZ'
        'bookingOptionJson': [
            {
                'name': str,   # Option name (checked for keywords)
                # ... other option fields
            }
        ]
    }
}
```

**Transformations Applied:**
- Phone format: `010XXXXYYYY` -> `010-XXXX-YYYY` (line 375)
- DateTime: UTC ISO string -> KST datetime + 9hrs (lines 369-372)
- Option detection: Keyword matching in option names (lines 361-367)

---

## Technical Debt and Known Issues

### Critical Technical Debt

#### 1. ⚠️ Hardcoded Credentials in Source Code

**Location**: `lambda_function.py` lines 250-251
```python
userid = 'dltnduf4318'      # ⚠️ SECURITY RISK
userpw = 'Doolim01!@'       # ⚠️ SECURITY RISK
```

**Location**: `sens_sms.py` lines 63-64
```python
self.access_key = "tpAFhfAWvpLqS5ve35Zw"
self.secret_key = "YrAgDCC20hiItoFrzrolbStsIwzyEWBFi4szm1Vh"
```

**Location**: `lambda_function.py` lines 439,444
```python
bot_token = " "
chat_id = " "
```

**Risk**: Credentials exposed in version control
**Fix Required**: Move to AWS Secrets Manager or Lambda environment variables

#### 2. ⚠️ Python 3.7 Runtime Deprecated

**Evidence**: `current_lambda_inform.md` line 23
```
"The python3.7 runtime is no longer supported.
We recommend that you migrate your functions that use python3.7
to a newer runtime as soon as possible"
```

**Impact**: Security updates no longer provided, eventual forced migration
**Fix Required**: Upgrade to Python 3.11+ (latest supported)

#### 3. ⚠️ Lambda Layer Size and Management Issues

**Current Setup**:
- ChromeDriver layer: 2GB+
- Selenium layer: ~50MB
- Difficult to update versions
- Deployment complexity

**Impact**: Slow cold starts, difficult maintenance
**Fix Required**: Migrate to ECR container-based Lambda

#### 4. ⚠️ Monolithic Code Structure

**Problem**: 449-line lambda_function.py contains:
- Browser automation
- Business logic
- Database operations
- API integrations
- Configuration
- No separation of concerns

**Impact**:
- Hard to test
- Hard to modify
- High coupling
- No reusability

**Fix Required**: Modular refactoring (see Enhancement Impact Analysis)

#### 5. ⚠️ Hardcoded Business Rules

**Problem**: All condition/action logic embedded in if/else statements

**Impact**:
- Cannot add new rules without code changes
- Cannot configure rules per store
- Violates requirement for "easily add/combine conditions and actions"

**Fix Required**: Rule engine architecture (see Enhancement Impact Analysis)

#### 6. No Error Handling Granularity

**Current**: Single try/except around entire Lambda handler (line 406,443)

```python
try:
    # Entire execution
except Exception as err:
    # Generic error notification
    requests.post(telegram_url, {'text': '요청중 오류 발생'})
```

**Impact**: Difficult to diagnose failures, no retry logic for specific errors
**Fix Required**: Granular error handling, specific error notifications

#### 7. No Logging Strategy

**Current**: Only `print()` statements

**Impact**: Difficult to debug production issues, no CloudWatch Logs structure
**Fix Required**: Structured logging (Python `logging` module)

#### 8. Selenium Global Scope Initialization

**Location**: `lambda_function.py` lines 229-256

```python
# Global scope - runs on every cold start
chrome_options = Options()
# ... 18 lines of configuration ...
driver = webdriver.Chrome(...)  # Initializes browser immediately
driver.get('https://new.smartplace.naver.com/')
```

**Impact**:
- Cold start penalty on every Lambda init
- Driver created even if cached cookies work
- Unnecessary Naver page load

**Fix Required**: Lazy initialization, only create driver when needed

#### 9. No Configuration Management

**Hardcoded Values Scattered Throughout:**
- Store IDs (line 252)
- Option keywords (line 255)
- Credentials (lines 250-251, sens_sms.py:63-64)
- Telegram tokens (lines 439,444)
- SMS templates (sens_sms.py:109-602)
- DynamoDB table names (lines 19-20)
- Phone number mappings (sens_sms.py:15-24)

**Impact**: Every config change requires code deployment
**Fix Required**: Centralized configuration (env vars, SSM, or DynamoDB)

#### 10. No Unit Tests

**Current**: No test files exist

**Impact**: Refactoring risk, regression potential
**Fix Required**: Test suite creation before refactoring

---

## Workarounds and Gotchas

### Gotcha 1: Date Format Conversion Complexity

**Location**: `lambda_function.py` lines 199-226

**Issue**: Naver API returns dates in Korean format, needs complex parsing

```python
# Input: "24. 10. 18.(금) 오후 02:30~04:00"
# Output: datetime object

# Requires:
- Korean day name translation (월화수목금토일 -> Mon/Tue/Wed/...)
- Korean AM/PM translation (오전/오후 -> AM/PM)
- Custom datetime format parsing
```

**Workaround**: `format_date()` function with translation dictionaries

**Why Not Change**: Naver API format is fixed, must be handled

### Gotcha 2: Time Zone Handling

**Location**: `lambda_function.py` lines 369-372

**Issue**: Naver API returns UTC times, need KST (+9 hours)

```python
reserve_at = datetime.strptime(booking_information['startDateTime'],
                               '%Y-%m-%dT%H:%M:%SZ') + timedelta(hours=9)
```

**Impact**: All time comparisons must account for timezone
**Gotcha**: No timezone-aware datetime objects used (naive datetimes only)

### Gotcha 3: Phone Number Format Inconsistency

**Naver API**: Returns `01012345678` (no hyphens)
**DynamoDB**: Stores `010-1234-5678` (with hyphens)
**SENS API**: Expects `01012345678` (no hyphens)

**Workaround**: Format conversion at boundaries (line 375, sens_sms.py:100,163,583)

### Gotcha 4: Booking Number Composite Key

**Location**: `lambda_function.py` line 135

```python
prefix = f"{i['biz_id']}_{i['book_id']}"
```

**Why**: Booking IDs are only unique per store, not globally
**Impact**: Must always use composite key for DynamoDB operations

### Gotcha 5: Lambda /tmp Directory Usage

**Location**: Chrome options (lines 234-242)

```python
'--user-data-dir=/tmp/user-data'
'--data-path=/tmp/data-path'
'--homedir=/tmp'
'--disk-cache-dir=/tmp/cache-dir'
```

**Why**: Lambda only allows writes to `/tmp` directory
**Gotcha**: `/tmp` is cleared between warm starts, max 512MB
**Impact**: Cannot persist browser data across invocations

### Gotcha 6: 20-Minute Event Window

**Trigger**: EventBridge every 20 minutes

**Impact**:
- Bookings created between triggers may miss 2-hour reminder window
- Must check both new and existing bookings every run
- 8 PM option SMS only works if Lambda runs at 8:00-8:19 PM

**Workaround**: Check all bookings every run (lines 160-169)

### Gotcha 7: DynamoDB Scan for Option SMS

**Location**: `lambda_function.py` lines 103-128

```python
response = sms_table.scan(
    FilterExpression=Attr('option_sms').eq(False)
)
```

**Issue**: Full table scan (expensive, slow)
**Why**: No secondary index on `option_sms` field
**Impact**: Performance degrades as table grows
**Future Fix**: Add GSI or use different query pattern

---

## Enhancement Impact Analysis

### Files That Will Need Modification

#### High Impact (Complete Restructure)

**1. `lambda_function.py`** → Will be split into multiple modules:

New structure:
```
src/
├── main.py                    # New Lambda handler (entry point)
├── auth/
│   └── naver_login.py        # Extract login() - PRESERVE 100%
├── api/
│   └── naver_booking.py      # Extract get_items(), count_items()
├── domain/
│   ├── booking.py            # Booking model (DESIGN FOR EXTENSIBILITY - fields will expand!)
│   └── store.py              # Store model
├── database/
│   ├── dynamodb_client.py    # DynamoDB operations
│   └── session_manager.py    # Session cookie management
├── rules/
│   ├── engine.py             # Rule engine core
│   ├── conditions.py         # Condition evaluators
│   └── actions.py            # Action executors
├── notifications/
│   ├── sms_service.py        # Refactored from sens_sms.py
│   └── telegram_service.py   # Telegram notifications
├── config/
│   ├── settings.py           # Configuration loader
│   └── rules.yaml            # Rule definitions
└── utils/
    ├── date_utils.py         # format_date()
    └── logger.py             # Structured logging
```

**Lines to Preserve Exactly:**
- Lines 260-301 (login function) - Move to `auth/naver_login.py` AS-IS
- Lines 229-248 (Chrome options) - Move to `auth/naver_login.py` AS-IS

**2. `sens_sms.py`** → Refactor to `notifications/sms_service.py`:

Changes:
- Move templates to `config/sms_templates.yaml`
- Move store-to-phone mapping to `config/stores.yaml`
- Keep SENS API logic intact (lines 79-85, 69-74)
- Replace if/elif template selection with config lookup

#### Medium Impact (Refactor but Keep Logic)

**3. Create New Files**:

**`config/rules.yaml`** - Rule definitions:
```yaml
rules:
  - name: "New Booking Confirmation"
    conditions:
      - type: "booking_not_in_db"
    actions:
      - type: "send_sms"
        template: "confirmation"
      - type: "create_db_record"
      - type: "check_two_hour_window"

  - name: "Two Hour Reminder"
    conditions:
      - type: "time_before_booking"
        hours: 2
      - type: "flag_not_set"
        flag: "remind_sms"
    actions:
      - type: "send_sms"
        template: "guide"
        store_specific: true
      - type: "update_flag"
        flag: "remind_sms"

  - name: "Evening Event SMS"
    conditions:
      - type: "current_hour"
        hour: 20
      - type: "booking_status"
        status: "RC08"
      - type: "flag_not_set"
        flag: "option_sms"
      - type: "has_option_keyword"
    actions:
      - type: "send_sms"
        template: "event"
      - type: "update_flag"
        flag: "option_sms"
```

**`config/stores.yaml`** - Store configuration:
```yaml
stores:
  - id: "1051707"
    name: "화성점"
    phone: "01055814318"
    sms_templates:
      guide: "template_1051707"
  - id: "951291"
    name: "안산점"
    phone: "01055814318"
    sms_templates:
      guide: "template_951291"
  # ... etc
```

**`Dockerfile`** - ECR container definition:
```dockerfile
FROM public.ecr.aws/lambda/python:3.11

# Install Chrome and ChromeDriver
RUN yum install -y wget unzip && \
    # Chrome installation
    # ChromeDriver installation

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY src/ ${LAMBDA_TASK_ROOT}/

CMD ["main.lambda_handler"]
```

#### Low Impact (New Infrastructure)

**4. AWS Infrastructure Changes**:

New resources needed:
- **ECR Repository** - For container images
- **Secrets Manager** - For credentials
- **CloudWatch Logs** - Structured logging
- **SSM Parameter Store** - For configuration (alternative to config files)

Updated resources:
- **Lambda Function** - Change to container-based deployment
- **IAM Role** - Add Secrets Manager permissions

---

### New Modules Needed

#### 1. Rule Engine Core (`src/rules/engine.py`)

**Purpose**: Evaluate conditions and execute actions dynamically

**Key Classes:**

```python
class RuleEngine:
    def __init__(self, rules_config: List[RuleConfig]):
        self.rules = rules_config
        self.condition_evaluators = {}  # Registry of condition handlers
        self.action_executors = {}      # Registry of action handlers

    def register_condition(self, name: str, evaluator: Callable):
        """Register custom condition evaluator"""

    def register_action(self, name: str, executor: Callable):
        """Register custom action executor"""

    def evaluate_rule(self, rule: RuleConfig, context: Dict) -> bool:
        """Check if all conditions are met"""

    def execute_rule(self, rule: RuleConfig, context: Dict):
        """Execute all actions for matched rule"""

    def process_booking(self, booking: Booking) -> List[ActionResult]:
        """Main entry point - process booking through all rules"""
```

**Example Usage:**
```python
engine = RuleEngine(load_rules_from_yaml())
engine.register_condition("booking_not_in_db", check_db_condition)
engine.register_action("send_sms", send_sms_action)

results = engine.process_booking(booking_data)
```

#### 2. Condition Evaluators (`src/rules/conditions.py`)

**Purpose**: Implement condition checking logic

**Functions Needed:**

```python
def booking_not_in_db(context: Dict) -> bool:
    """Check if booking exists in DynamoDB"""
    # Current logic from lambda_function.py:138

def time_before_booking(context: Dict, hours: int) -> bool:
    """Check if within X hours of booking time"""
    # Current logic from lambda_function.py:139, 161

def flag_not_set(context: Dict, flag: str) -> bool:
    """Check if DynamoDB flag is False"""
    # Current logic from lambda_function.py:160, 162, 189

def current_hour(context: Dict, hour: int) -> bool:
    """Check if current hour matches"""
    # Current logic from lambda_function.py:177

def booking_status(context: Dict, status: str) -> bool:
    """Check booking status code"""
    # Current logic from get_items() status parameter

def has_option_keyword(context: Dict) -> bool:
    """Check if booking has option keywords"""
    # Current logic from lambda_function.py:361-367
```

#### 3. Action Executors (`src/rules/actions.py`)

**Purpose**: Implement action execution logic

**Functions Needed:**

```python
async def send_sms(context: Dict, template: str, store_specific: bool = False):
    """Send SMS using SENS API"""
    # Current logic from lambda_function.py:84-99

async def create_db_record(context: Dict):
    """Create DynamoDB record"""
    # Current logic from lambda_function.py:150

async def update_flag(context: Dict, flag: str):
    """Update DynamoDB flag"""
    # Current logic from lambda_function.py:66-81

async def send_telegram(context: Dict, message: str):
    """Send Telegram notification"""
    # Current logic from lambda_function.py:439,444

async def send_slack(context: Dict, message: str):
    """NEW - Send Slack notification (future requirement)"""
```

#### 4. Configuration Loader (`src/config/settings.py`)

**Purpose**: Load configuration from environment/files/Secrets Manager

```python
class Settings:
    # AWS
    aws_region: str
    dynamodb_table_sms: str
    dynamodb_table_session: str

    # Naver (from Secrets Manager)
    naver_username: str
    naver_password: str

    # SENS (from Secrets Manager)
    sens_access_key: str
    sens_secret_key: str
    sens_service_id: str

    # Telegram (from Secrets Manager)
    telegram_bot_token: str
    telegram_chat_id: str

    # Business Config
    stores: List[Store]
    option_keywords: List[str]
    rules: List[RuleConfig]

    @classmethod
    def load(cls) -> 'Settings':
        """Load from env vars + Secrets Manager + config files"""
```

---

### Integration Considerations for Refactoring

#### 1. Preserving Naver Login Flow

**Critical**: The login mechanism MUST work exactly as current implementation

**Refactoring Approach:**

1. **Extract to Module** (`src/auth/naver_login.py`):
```python
# Copy lines 229-301 EXACTLY
class NaverAuthenticator:
    def __init__(self, username: str, password: str):
        self.username = username
        self.password = password
        self.driver = None

    def setup_driver(self):
        """Lines 229-248 - Chrome setup"""

    def login(self, cached_cookies: Optional[List[Dict]]) -> List[Dict]:
        """Lines 260-301 - Login logic"""
        # EXACT COPY - DO NOT MODIFY

    def get_session(self) -> requests.Session:
        """Convert Selenium cookies to requests.Session"""
```

2. **Integration Point** (new `main.py`):
```python
from auth.naver_login import NaverAuthenticator
from database.session_manager import SessionManager

session_mgr = SessionManager(dynamodb_client)
cached_cookies = session_mgr.get_cookies()

authenticator = NaverAuthenticator(username, password)
fresh_cookies = authenticator.login(cached_cookies)

if fresh_cookies != cached_cookies:
    session_mgr.save_cookies(fresh_cookies)

api_session = authenticator.get_session()
```

#### 2. Rule Engine Integration

**Replace Current Logic:**

**Before** (lambda_function.py:131-173):
```python
def reservation_check(user_data):
    for i in user_data:
        db_response = get_item(prefix, i['phone'])
        if db_response is None:
            # ... hardcoded logic
        else:
            if db_response['remind_sms'] == False and ...:
                # ... more hardcoded logic
```

**After** (new src/main.py):
```python
from rules.engine import RuleEngine

engine = RuleEngine(settings.rules)
setup_conditions(engine)  # Register all condition evaluators
setup_actions(engine)     # Register all action executors

def process_bookings(bookings: List[Booking]):
    results = []
    for booking in bookings:
        context = {
            'booking': booking,
            'db_record': dynamodb.get_item(booking.id, booking.phone),
            'current_time': datetime.now(),
        }
        rule_results = engine.process_booking(context)
        results.extend(rule_results)
    return results
```

**Benefits:**
- Add new rules without code changes (edit YAML only)
- Combine conditions flexibly
- Reuse condition/action logic
- Test rules independently

#### 3. SMS Template Management

**Replace Hardcoded Templates:**

**Before** (sens_sms.py:543-559):
```python
if store_id == "1051707":
    booking_guide_sms = booking_guide_template_1051707
elif store_id == "951291":
    booking_guide_sms = booking_guide_template_951291
# ... 6 more elif
```

**After** (new approach):

**config/sms_templates.yaml:**
```yaml
templates:
  confirmation:
    subject: "다비스튜디오 안내"
    type: "LMS"
    content: |
      다비스튜디오를 찾아주신 고객님, 안녕하세요
      예약 확정되어 이용 안내 드립니다.
      ...

  guide_1051707:
    subject: "다비스튜디오 안내"
    type: "LMS"
    content: |
      다비스튜디오를 찾아주신 고객님, 안녕하세요
      이용 상세 안내 드립니다.
      -도어락 비밀번호 : 5282*
      ...
```

**src/notifications/sms_service.py:**
```python
class SMSService:
    def __init__(self, templates: Dict, stores: Dict):
        self.templates = templates
        self.stores = stores
        self.sens_client = SENSClient()

    def send(self, template_name: str, phone: str, store_id: Optional[str] = None):
        template = self._get_template(template_name, store_id)
        from_number = self.stores[store_id]['phone'] if store_id else default
        self.sens_client.send(from_number, phone, template)

    def _get_template(self, name: str, store_id: Optional[str]) -> Template:
        if store_id:
            template_key = f"{name}_{store_id}"
            if template_key in self.templates:
                return self.templates[template_key]
        return self.templates[name]  # Fall back to common template
```

#### 4. ECR Container Migration

**Deployment Changes:**

**Before** (Lambda Layers):
```
1. Create Layer for ChromeDriver (manual binary download)
2. Create Layer for Selenium (pip install to folder, zip)
3. Upload layers to AWS
4. Attach layers to Lambda
5. Upload lambda_function.py code
```

**After** (ECR Container):
```
1. Build container image:
   docker build -t naver-sms-automation .

2. Tag and push to ECR:
   docker tag naver-sms-automation:latest {account}.dkr.ecr.{region}.amazonaws.com/naver-sms-automation:latest
   docker push {account}.dkr.ecr.{region}.amazonaws.com/naver-sms-automation:latest

3. Update Lambda to use image:
   aws lambda update-function-code --function-name naverplace_send_inform_v2 \
     --image-uri {account}.dkr.ecr.{region}.amazonaws.com/naver-sms-automation:latest
```

**Benefits:**
- Easier dependency management
- Faster updates (no layer management)
- Local testing with same environment
- Python 3.11+ support

**Dockerfile Structure:**
```dockerfile
FROM public.ecr.aws/lambda/python:3.11

# Install Chrome + ChromeDriver (exact versions)
RUN yum install -y wget unzip && \
    wget https://chrome-for-testing.storage.googleapis.com/.../chrome-linux64.zip && \
    unzip chrome-linux64.zip -d /opt && \
    wget https://chrome-for-testing.storage.googleapis.com/.../chromedriver-linux64.zip && \
    unzip chromedriver-linux64.zip -d /opt && \
    yum clean all

# Set binary paths
ENV CHROME_BIN=/opt/chrome-linux64/chrome
ENV CHROMEDRIVER_BIN=/opt/chromedriver-linux64/chromedriver

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY src/ ${LAMBDA_TASK_ROOT}/

# Lambda handler
CMD ["main.lambda_handler"]
```

---

### Migration Strategy (Recommended)

#### Phase 1: Infrastructure Setup (Week 1)
- [ ] Create ECR repository
- [ ] Set up Secrets Manager for credentials
- [ ] Create new DynamoDB tables (if schema changes needed)
- [ ] Set up CloudWatch Logs dashboards

#### Phase 2: Code Extraction (Week 2)
- [ ] Extract Naver login to `auth/naver_login.py` (NO CHANGES)
- [ ] Extract SENS API to `notifications/sms_service.py` (preserve logic)
- [ ] Extract DynamoDB ops to `database/` modules
- [ ] Create configuration loader
- [ ] Add structured logging

#### Phase 3: Rule Engine Implementation (Week 2-3)
- [ ] Implement rule engine core
- [ ] Implement condition evaluators (replicate current logic exactly)
- [ ] Implement action executors (replicate current logic exactly)
- [ ] Create `rules.yaml` matching current behavior
- [ ] Unit tests for rule engine

#### Phase 4: Integration & Testing (Week 3)
- [ ] Create new `main.py` Lambda handler
- [ ] Integrate all modules
- [ ] Integration tests (compare outputs with original)
- [ ] Build Docker container
- [ ] Test container locally with Lambda Runtime Interface Emulator

#### Phase 5: Deployment (Week 4)
- [ ] Deploy container to ECR
- [ ] Create new Lambda function (don't replace existing yet)
- [ ] Execute offline validation campaign (golden dataset replay + telemetry review)
- [ ] Compare results, fix discrepancies
- [ ] Switch EventBridge trigger to new Lambda after go/no-go approval
- [ ] Monitor for 1 week
- [ ] Decommission old Lambda

#### Phase 6: Enhancement (Week 5+)
- [ ] Add new rule examples (per requierment.md)
- [ ] Add Slack integration (action executor)
- [ ] Create rule management UI (future)
- [ ] Add rule validation
- [ ] Performance optimization

---

## Development and Deployment

### Local Development Setup (Current)

**Prerequisites:**
- Python 3.7 (for compatibility testing)
- AWS CLI configured
- Chrome/ChromeDriver installed locally

**Steps:**
```bash
# 1. Clone repository
git clone <repo-url>
cd naver_sms_automation_refactoring

# 2. Create virtual environment
python3.7 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Set environment variables
export AWS_ACCESS_KEY_ID=<your-key>
export AWS_SECRET_ACCESS_KEY=<your-secret>
# ... other vars

# 5. Test locally (WARNING: Will send real SMS!)
python oroginal_code/lambda_function.py
```

**Issues with Current Setup:**
- Must have Chrome installed locally
- ChromeDriver version must match
- Environment differs from Lambda (MacOS/Windows vs Amazon Linux)
- No way to test Lambda-specific behavior

### Local Development Setup (After ECR Migration)

**Prerequisites:**
- Docker Desktop
- AWS CLI configured
- Python 3.11+

**Steps:**
```bash
# 1. Clone repository
git clone <repo-url>
cd naver_sms_automation_refactoring

# 2. Create .env file (from .env.example)
cp .env.example .env
# Edit .env with actual values (NOT committed to git)

# 3. Build container
docker build -t naver-sms-automation .

# 4. Test locally with Lambda RIE
docker run --rm -p 9000:8080 \
  --env-file .env \
  naver-sms-automation:latest

# 5. Invoke function
curl -XPOST "http://localhost:9000/2015-03-31/functions/function/invocations" \
  -d '{"test": true}'

# 6. Run tests
pytest tests/
```

**Benefits:**
- Identical environment to production
- Easy dependency management
- Fast iteration cycle

### Deployment Process (Current)

**Manual Deployment:**
1. Zip code files:
   ```bash
   cd oroginal_code
   zip -r ../lambda_package.zip lambda_function.py sens_sms.py
   ```
2. Upload via AWS Console or CLI:
   ```bash
   aws lambda update-function-code \
     --function-name naverplace_send_inform_v2 \
     --zip-file fileb://lambda_package.zip
   ```
3. Test via AWS Console (Test button)

**Issues:**
- No CI/CD pipeline
- Manual process error-prone
- No automated testing
- No rollback strategy

### Deployment Process (After ECR Migration)

**Automated Deployment:**

**GitHub Actions Workflow** (`.github/workflows/deploy.yml`):
```yaml
name: Deploy to AWS Lambda

on:
  push:
    branches: [main]

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      - name: Configure AWS credentials
        uses: aws-actions/configure-aws-credentials@v2
        with:
          aws-access-key-id: ${{ secrets.AWS_ACCESS_KEY_ID }}
          aws-secret-access-key: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
          aws-region: ap-northeast-2

      - name: Login to Amazon ECR
        id: login-ecr
        uses: aws-actions/amazon-ecr-login@v1

      - name: Build, tag, and push image to Amazon ECR
        env:
          ECR_REGISTRY: ${{ steps.login-ecr.outputs.registry }}
          ECR_REPOSITORY: naver-sms-automation
          IMAGE_TAG: ${{ github.sha }}
        run: |
          docker build -t $ECR_REGISTRY/$ECR_REPOSITORY:$IMAGE_TAG .
          docker push $ECR_REGISTRY/$ECR_REPOSITORY:$IMAGE_TAG
          docker tag $ECR_REGISTRY/$ECR_REPOSITORY:$IMAGE_TAG $ECR_REGISTRY/$ECR_REPOSITORY:latest
          docker push $ECR_REGISTRY/$ECR_REPOSITORY:latest

      - name: Update Lambda function
        run: |
          aws lambda update-function-code \
            --function-name naverplace_send_inform_v2 \
            --image-uri ${{ steps.login-ecr.outputs.registry }}/naver-sms-automation:latest
```

---

## Testing Reality

### Current Test Coverage

**Unit Tests**: 0%
**Integration Tests**: 0%
**E2E Tests**: 0%

**Testing Method**: Manual testing in production

**Risks:**
- No confidence in refactoring
- Potential regressions undetected
- Production bugs caught by customers

### Recommended Test Strategy

#### Unit Tests (Target: 80% coverage)

**Test Files Structure:**
```
tests/
├── unit/
│   ├── test_rules_engine.py
│   ├── test_conditions.py
│   ├── test_actions.py
│   ├── test_sms_service.py
│   └── test_date_utils.py
├── integration/
│   ├── test_naver_login.py      # Uses real Naver (staging account)
│   ├── test_naver_api.py
│   └── test_dynamodb.py         # Uses local DynamoDB
└── e2e/
    └── test_lambda_handler.py   # Full flow with mocks
```

**Example Unit Test** (`tests/unit/test_conditions.py`):
```python
import pytest
from datetime import datetime, timedelta
from rules.conditions import time_before_booking

def test_time_before_booking_within_window():
    context = {
        'booking': {'reserve_at': datetime.now() + timedelta(hours=1)},
        'current_time': datetime.now()
    }
    assert time_before_booking(context, hours=2) == True

def test_time_before_booking_outside_window():
    context = {
        'booking': {'reserve_at': datetime.now() + timedelta(hours=3)},
        'current_time': datetime.now()
    }
    assert time_before_booking(context, hours=2) == False
```

**Example Integration Test** (`tests/integration/test_dynamodb.py`):
```python
import pytest
from database.dynamodb_client import DynamoDBClient

@pytest.fixture
def dynamodb_local():
    # Start local DynamoDB container
    # Return client connected to localhost:8000
    pass

def test_create_and_retrieve_booking(dynamodb_local):
    client = DynamoDBClient(dynamodb_local)
    booking_data = {
        'booking_num': '1051707_12345',
        'phone': '010-1234-5678',
        # ...
    }
    client.put_item(booking_data)
    retrieved = client.get_item('1051707_12345', '010-1234-5678')
    assert retrieved == booking_data
```

#### Comparison Testing Strategy

**Goal**: Ensure refactored code produces identical outputs

**Approach:**
1. Run old Lambda, capture all inputs/outputs for 1 week
2. Replay same inputs through new Lambda
3. Compare outputs (SMS sent, DynamoDB updates, Telegram messages)
4. Fix discrepancies until 100% match

**Implementation:**
```python
# tests/comparison/test_output_parity.py
def test_booking_processing_parity():
    """Compare old vs new implementation outputs"""

    # Load captured production data
    test_cases = load_test_cases('tests/fixtures/production_bookings.json')

    for test_case in test_cases:
        # Old implementation
        old_results = run_old_lambda(test_case['input'])

        # New implementation
        new_results = run_new_lambda(test_case['input'])

        # Compare
        assert old_results['sms_sent'] == new_results['sms_sent']
        assert old_results['db_updates'] == new_results['db_updates']
        assert old_results['telegram_messages'] == new_results['telegram_messages']
```

---

## Appendix - Useful Commands and Scripts

### Frequently Used Commands

**AWS Lambda:**
```bash
# View Lambda logs
aws logs tail /aws/lambda/naverplace_send_inform_v2 --follow

# Invoke Lambda manually
aws lambda invoke --function-name naverplace_send_inform_v2 \
  --payload '{}' response.json

# Update environment variables
aws lambda update-function-configuration \
  --function-name naverplace_send_inform_v2 \
  --environment "Variables={KEY=value}"
```

**DynamoDB:**
```bash
# Query sms table
aws dynamodb get-item --table-name sms \
  --key '{"booking_num": {"S": "1051707_12345"}, "phone": {"S": "010-1234-5678"}}'

# Scan for unsent option SMS
aws dynamodb scan --table-name sms \
  --filter-expression "option_sms = :false" \
  --expression-attribute-values '{":false": {"BOOL": false}}'

# Delete session cookie (force re-login)
aws dynamodb delete-item --table-name session \
  --key '{"id": {"S": "1"}}'
```

**ECR (After Migration):**
```bash
# Login to ECR
aws ecr get-login-password --region ap-northeast-2 | \
  docker login --username AWS --password-stdin {account}.dkr.ecr.ap-northeast-2.amazonaws.com

# Build and push
docker build -t naver-sms-automation .
docker tag naver-sms-automation:latest {account}.dkr.ecr.ap-northeast-2.amazonaws.com/naver-sms-automation:latest
docker push {account}.dkr.ecr.ap-northeast-2.amazonaws.com/naver-sms-automation:latest

# List images
aws ecr list-images --repository-name naver-sms-automation
```

### Debugging and Troubleshooting

**Common Issues:**

#### 1. "Login failed - cookie expired"

**Symptoms:** Telegram message "요청중 오류 발생"

**Diagnosis:**
```bash
# Check CloudWatch Logs for error
aws logs filter-log-events --log-group-name /aws/lambda/naverplace_send_inform_v2 \
  --filter-pattern "login" --max-items 10
```

**Fix:**
```bash
# Delete cached session to force fresh login
aws dynamodb delete-item --table-name session --key '{"id": {"S": "1"}}'
```

#### 2. "SMS not sending"

**Check SENS API response:**
```bash
# Add to sens_sms.py temporarily
print(f"SENS Response: {res.status_code} - {res.text}")

# Check logs
aws logs tail /aws/lambda/naverplace_send_inform_v2 --follow | grep "SENS"
```

**Common Causes:**
- Invalid signature (check timestamp)
- Wrong phone number format
- SENS account quota exceeded

#### 3. "Lambda timeout"

**Symptoms:** Execution stops at ~5 minutes

**Diagnosis:**
```bash
# Check execution duration
aws logs filter-log-events --log-group-name /aws/lambda/naverplace_send_inform_v2 \
  --filter-pattern "Duration" | grep "REPORT"
```

**Fix:**
- Increase timeout (max 15 minutes)
- Optimize Selenium login (use cached cookies)
- Reduce batch size

#### 4. "Booking data not fetched"

**Check Naver API response:**
```python
# Add debug logging
print(f"Naver API Response: {response.status_code}")
print(f"Booking count: {count}")
print(f"Bookings: {booking_info}")
```

**Common Causes:**
- Session cookie expired
- Naver API format changed
- Store ID no longer valid

### Performance Monitoring

**Key Metrics to Watch:**

```bash
# Lambda execution time
aws logs filter-log-events --log-group-name /aws/lambda/naverplace_send_inform_v2 \
  --filter-pattern "REPORT" \
  --start-time $(date -u -d '1 hour ago' +%s)000 \
  | jq '.events[].message' \
  | grep -oP 'Duration: \K[0-9.]+'

# DynamoDB consumed capacity
aws cloudwatch get-metric-statistics \
  --namespace AWS/DynamoDB \
  --metric-name ConsumedReadCapacityUnits \
  --dimensions Name=TableName,Value=sms \
  --start-time $(date -u -d '1 day ago' +%Y-%m-%dT%H:%M:%S) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
  --period 3600 \
  --statistics Sum
```

### Configuration Reference

**Environment Variables (Migrate to Secrets Manager):**

| Variable | Current Location | Future Location | Purpose |
|----------|-----------------|-----------------|---------|
| `NAVER_USERID` | Hardcoded (line 250) | Secrets Manager | Naver login username |
| `NAVER_PASSWORD` | Hardcoded (line 251) | Secrets Manager | Naver login password |
| `SENS_ACCESS_KEY` | Hardcoded (sens_sms.py:63) | Secrets Manager | SENS API key |
| `SENS_SECRET_KEY` | Hardcoded (sens_sms.py:64) | Secrets Manager | SENS secret |
| `SENS_SERVICE_ID` | Hardcoded (sens_sms.py:67) | Secrets Manager | SENS service ID |
| `TELEGRAM_BOT_TOKEN` | Hardcoded (line 439) | Secrets Manager | Telegram bot token |
| `TELEGRAM_CHAT_ID` | Hardcoded (line 439) | Secrets Manager | Telegram chat ID |
| `BIZ_LIST` | Hardcoded (line 252) | Config file/DynamoDB | Store IDs list |
| `OPTION_KEYWORDS` | Hardcoded (line 255) | Config file/DynamoDB | Option detection keywords |

---

## Summary and Next Steps

### Current State Summary

This AWS Lambda-based SMS automation system is **production-proven but architecturally constrained**. It successfully handles automated booking notifications for 8 Dabi Studio locations, but faces critical challenges:

**Technical Debt:**
- Python 3.7 runtime deprecated
- Lambda Layer complexity
- Monolithic code structure
- Hardcoded credentials
- No configuration management
- Zero test coverage

**Business Logic Constraints:**
- Cannot add new rules without code changes
- Store-specific logic scattered throughout code
- Difficult to combine conditions/actions
- Violates requirements for flexible rule system

### Enhancement Goals Alignment

Per `requierment.md`, the refactoring must:

1. ✅ **Enable easy condition/action composition** → Rule engine architecture
2. ✅ **Preserve all existing functionality** → Comparison testing strategy
3. ✅ **Keep Naver login mechanism 100%** → Extract as-is to dedicated module
4. ✅ **Maintain SENS API integration** → Preserve signature/request logic
5. ✅ **Upgrade Python runtime** → ECR migration to Python 3.11+
6. ✅ **Solve Lambda issues** → ECR container deployment

### Critical Preservation Checklist

When refactoring, **DO NOT MODIFY** these components:

- [ ] Naver login logic (lambda_function.py:260-301)
- [ ] Chrome options configuration (lambda_function.py:229-248)
- [ ] SENS signature generation (sens_sms.py:79-85)
- [ ] SENS request headers (sens_sms.py:69-74)
- [ ] SMS template content (sens_sms.py:109-602)
- [ ] Store-to-phone mapping (sens_sms.py:15-24)
- [ ] Date format conversion (lambda_function.py:199-226)

### Recommended First Steps

1. **Before Any Code Changes:**
   - Set up comprehensive logging
   - Capture production inputs/outputs for 1 week
   - Create baseline test cases

2. **Phase 1 (Infrastructure):**
   - Create ECR repository
   - Set up Secrets Manager
   - Migrate credentials out of code

3. **Phase 2 (Safe Extraction):**
   - Extract Naver login (no changes)
   - Extract SENS API (no changes)
   - **Design booking.py model for field extensibility** (future fields will be added!)
   - Add unit tests for utilities

4. **Phase 3 (Rule Engine):**
   - Implement rule engine
   - Replicate current logic exactly in rules
   - Comparison test against old implementation

5. **Phase 4 (Deployment):**
   - Build ECR container
   - Deploy validation-ready Lambda
   - Execute offline validation campaign
   - Cutover after validation

### Success Criteria

Refactoring is successful when:

- [ ] All existing SMS sent correctly (100% match)
- [ ] All DynamoDB updates identical
- [ ] Telegram notifications identical
- [ ] New rules can be added via YAML only
- [ ] **Data model supports future field expansion** (dynamic field handling)
- [ ] Python 3.11+ running in production
- [ ] ECR deployment working
- [ ] Credentials in Secrets Manager
- [ ] >80% test coverage
- [ ] Zero production incidents during migration

---

**Document Status:** Complete brownfield analysis for refactoring planning

**Last Updated:** 2025-10-18

**Next Review:** After Phase 1 completion
