# Loyalty Integration Demo

一個以 **FastAPI** 建立的 Loyalty / Point API Integration Demo，用來示範外部系統如何透過統一的 Python Client 整合 Laravel Loyalty API。

此專案本身不是 Loyalty 後端，而是位於外部系統與 Laravel Loyalty API 之間的 Integration Layer，負責：

* Laravel API 認證與 Token 管理
* Customer API 整合
* Point API 整合
* Coupon API 整合
* Reward API 整合
* POS Checkout Workflow
* Mixed Payment Workflow
* Idempotency-Key 傳遞
* API Contract 驗證
* Integration Test

---

## 1. Project Overview

```text
External System
      │
      ▼
┌──────────────────────────┐
│ FastAPI Integration Demo │
│                          │
│  CustomerClient          │
│  PointClient             │
│  CouponClient             │
│  RewardClient             │
│  Workflow                │
└────────────┬─────────────┘
             │ JWT
             │ REST API
             ▼
┌──────────────────────────┐
│ Laravel Loyalty API      │
│                          │
│ Customer                 │
│ Points                   │
│ Coupons                  │
│ Rewards                  │
└──────────────────────────┘
```

主要設計原則：

1. Laravel API 負責 Loyalty domain business logic。
2. FastAPI 負責 Integration Layer 與 workflow orchestration。
3. Domain Client 負責封裝 Laravel API endpoint。
4. Workflow 負責跨多個 API 的業務流程。
5. Router 負責 HTTP API contract。
6. 測試集中於 `tests/`。

---

## 2. Technology Stack

* Python 3.13+
* FastAPI
* Uvicorn
* HTTPX
* Pydantic
* pytest
* pytest-asyncio
* python-dotenv

Laravel Loyalty API：

* Laravel
* JWT Authentication
* REST API

---

## 3. Project Structure

```text
loyalty-integration/
│
├── app/
│   ├── client/
│   │   ├── base.py
│   │   ├── customer.py
│   │   ├── point.py
│   │   ├── coupon.py
│   │   └── reward.py
│   │
│   ├── core/
│   │   └── dependencies.py
│   │
│   ├── routers/
│   │   ├── auth.py
│   │   ├── customers.py
│   │   ├── points.py
│   │   ├── coupons.py
│   │   ├── rewards.py
│   │   └── workflows.py
│   │
│   ├── workflows/
│   │   └── pos_checkout.py
│   │
│   ├── config.py
│   └── main.py
│
├── tests/
│   ├── __init__.py
│   ├── conftest.py
│   ├── find_valid_campaigns.py
│   ├── unit/
│   │   └── test_client_auth.py
│   └── integration/
│       ├── test_client_verification.py
│       ├── test_coupon*.py
│       ├── test_customer_*.py
│       ├── test_idempotency.py
│       ├── test_login.py
│       ├── test_mixed_payment.py
│       ├── test_point_*.py
│       ├── test_pos_checkout.py
│       ├── test_reward_grants.py
│       └── test_simple_idempotency.py
│
├── list_all_routes.py
├── verify_routes.py
├── pytest.ini
├── requirements.txt
└── README.md
```

### Directory Responsibilities

#### `app/client`

封裝 Laravel API 通訊。

```text
LaravelClient
    │
    ├── CustomerClient
    ├── PointClient
    ├── CouponClient
    └── RewardClient
```

`LaravelClient` 負責：

* HTTP request
* JWT authentication
* Token handling
* Common error handling
* Request timeout

Domain Client 則負責各自 domain 的 endpoint 與 payload。

---

#### `app/routers`

FastAPI HTTP endpoints。

Router 的主要責任是：

* 接收 request
* 驗證 request data
* 呼叫 Domain Client
* 回傳 API response

Router 不應承擔 Loyalty business logic。

---

#### `app/workflows`

負責跨 Domain API 的流程編排。

例如 POS Checkout：

```text
Customer
   │
   ├── Validate Customer
   │
   ├── Earn Points
   │
   ├── Redeem Coupon
   │
   └── Return Checkout Result
```

---

#### `tests`

所有測試與 integration verification code 集中於此；不需要外部服務的測試位於 `tests/unit/`，需要 Laravel API 的測試與 scripts 位於 `tests/integration/`。

---

## 4. Configuration

建立 `.env`：

```env
LARAVEL_API_BASE_URL=http://127.0.0.1:8088/api/v1
LARAVEL_EMAIL=admin@example.com
LARAVEL_PASSWORD=password
DEFAULT_TIMEOUT=30
```

實際環境請依 Laravel API 設定調整。

不要將實際 `.env` 提交到 Git。

---

## 5. Installation

建立 virtual environment：

```bash
python -m venv venv
```

Windows：

```bash
venv\Scripts\activate
```

Linux / macOS：

```bash
source venv/bin/activate
```

安裝 dependencies：

```bash
pip install -r requirements.txt
```

---

## 6. Run Application

啟動 FastAPI：

```bash
uvicorn app.main:app --reload
```

預設可以透過：

```text
http://127.0.0.1:8000
```

確認 Health Check：

```text
GET /health
```

---

## 7. Application Architecture

### Application Factory

FastAPI 使用 `create_app()` 建立 application instance：

```python
app = create_app()
```

這樣可以讓：

* Uvicorn
* TestClient
* pytest
* route verification

使用一致的 application initialization。

Router registration 集中於 application creation process，避免不同啟動方式取得不同的 route state。

---

## 8. API Domains

### Authentication

```text
POST /auth/login
GET  /auth/me
POST /auth/refresh
POST /auth/logout
```

---

### Customers

```text
GET /customers
GET /customers/{customer_id}
GET /customers/{customer_id}/membership
```

---

### Points

```text
GET  /customers/{customer_id}/points

GET  /customers/{customer_id}/point-transactions
POST /customers/{customer_id}/point-transactions

GET /customers/{customer_id}/point-transactions/expiring

GET /customers/{customer_id}/point-transactions/{transaction_id}

POST /points/earn
POST /points/redeem
```

Point transaction query：

```text
GET /customers/{customer_id}/point-transactions?type=earn
GET /customers/{customer_id}/point-transactions?type=redeem
```

Python Client 內部使用較明確的 `transaction_type` 命名，但對外 Laravel API contract 仍使用 `type`。

---

### Coupons

```text
GET  /customers/{customer_id}/coupons
GET  /customers/{customer_id}/coupons/{user_coupon_id}

GET  /customers/{customer_id}/coupon-redemptions

POST /coupons/claim
POST /customers/{customer_id}/coupons/claim

POST /coupons/redeem
```

---

### Rewards

```text
GET  /customers/{customer_id}/reward-grants
POST /customers/{customer_id}/rewards/grant
```

---

### Workflows

```text
POST /workflows/pos-checkout
POST /payments/mixed
```

Workflow endpoint 用於將多個 Loyalty API 操作組合成完整業務流程。

---

## 9. Idempotency

涉及可能重複執行的 mutation request，可透過：

```text
Idempotency-Key
```

傳遞唯一 request key。

例如：

```http
Idempotency-Key: order-20260924-001
```

Integration Layer 不自行修改 Laravel API 的 idempotency semantics，而是將 key 傳遞至 Laravel API。

相同 idempotency key 與相同 request payload 應由 Laravel API 負責處理重複請求。

---

## 10. Error Handling

`LaravelClient` 統一處理 Laravel API communication。

主要情境包括：

* Authentication failure
* HTTP error response
* Timeout
* Connection failure
* Invalid response
* Missing authentication token

未認證狀態下呼叫需要 authentication 的 API 時，Client 會拒絕 request，而不是送出沒有 token 的請求。

HTTP status 應依 Laravel API contract 解讀：

```text
2xx → successful operation
4xx → client/request/business validation error
5xx → server-side error
```

Domain Client 不應將 business failure 視為成功。

---

## 11. Testing

測試分為兩層：

```text
tests/
├── unit/        # 不需要 Laravel API
└── integration/ # 需要實際 Laravel API
```

### Local / Unit Tests

GitHub CI 執行不需要 Laravel API 的測試與 application checks：

```bash
python -m compileall -q app tests
python -m pytest -q -m "not integration"
python verify_routes.py
git diff --check
```

`verify_routes.py` 只檢查 FastAPI application 的 routes/OpenAPI contract，不啟動 lifespan，也不呼叫 Laravel API。

只收集測試：

```bash
python -m pytest --collect-only -q
```

執行指定測試：

```bash
python -m pytest tests/integration/test_reward_grants.py -q -m integration
```

執行指定測試 function：

```bash
python -m pytest tests/integration/test_reward_grants.py::test_1_list_reward_grants -q -m integration
```

### CI

GitHub Actions workflow 位於 `.github/workflows/ci.yml`，會在 push 到 `main` 或 `develop`，以及 Pull Request 目標為這兩個分支時執行。

CI 不需要 Laravel API URL、Laravel credentials 或 GitHub Secrets。

### Laravel Integration Tests

Integration tests 會使用 `tests/conftest.py` 的 live API fixture，並以 `@pytest.mark.integration` 標記。它們不屬於 GitHub CI 的 standalone verification。

本機有可用 Laravel API 時，設定 `.env` 後執行：

```bash
python -m pytest -q -m integration
```

需要的環境變數為 `LARAVEL_API_BASE_URL`、`LARAVEL_EMAIL`、`LARAVEL_PASSWORD`；使用 coffee tenant 的測試另外需要 `LARAVEL_COFFEE_EMAIL` 與 `LARAVEL_COFFEE_PASSWORD`。

---

## 12. Test Scope

目前測試涵蓋：

* Authentication
* Customer API
* Point API
* Point Transaction
* Point Idempotency
* Coupon API
* Coupon Claim
* Coupon Redemption
* Reward Grant
* POS Checkout
* Mixed Payment
* Client integration
* API route contract

`tests/integration/` 中的 pytest tests 與可直接執行的 verification scripts 都需要實際 Laravel API；`tests/unit/` 則不需要外部服務。

---

## 13. Route Verification

`verify_routes.py` 用於檢查 FastAPI 最終註冊的 OpenAPI routes 與 HTTP methods：

```bash
python verify_routes.py
```

它會：

1. 建立完整 FastAPI application。
2. 讀取 OpenAPI route definitions。
3. 列出目前所有 endpoint。
4. 驗證核心 API path 與 HTTP method。
5. 發現 contract regression 時以非零 exit code 結束。

`list_all_routes.py` 則會啟動 FastAPI lifespan 並列出 route inventory，適合在 Laravel API 可用時進行完整啟動驗證。

---

## 14. Development Verification

修改 application code 後，建議依序執行：

```bash
python -m compileall -q app tests
```

```bash
python -m pytest -q -m "not integration"
```

```bash
python verify_routes.py
```

```bash
git diff --check
```

這四個檢查分別確認：

| Check                | Purpose                      |
| -------------------- | ---------------------------- |
| `compileall`         | Python syntax                |
| `pytest`             | Automated tests              |
| `list_all_routes.py` | API route contract           |
| `git diff --check`   | Patch / whitespace integrity |

---

## 15. Code Conventions

### Domain Client

Domain Client 只負責對應 Laravel API。

例如：

```python
await point_client.create_transaction(
    customer_id=customer_id,
    transaction_type="earn",
    points=100,
)
```

HTTP contract 仍由 Client mapping：

```python
{
    "type": transaction_type,
    "points": points,
}
```

因此：

* Python internal naming 優先保持語意清楚。
* Laravel API contract 保持與後端一致。
* 不因 Python naming convention 任意修改外部 API contract。

---

### Router

Router 負責 HTTP contract：

```text
Request
   ↓
Router
   ↓
Domain Client
   ↓
Laravel API
```

不要在 Router 中重新實作 Loyalty business logic。

---

### Workflow

Workflow 負責多個 API operation 的 orchestration。

```text
Router
  ↓
Workflow
  ↓
Domain Clients
  ↓
Laravel API
```

Workflow 不應取代 Laravel backend 的 domain logic。

---

## 16. API Contract Principle

本專案與 Laravel Loyalty API 之間存在明確的 contract。

修改 endpoint、HTTP method、query parameter、request body 或 response handling 時，應同步確認：

```text
FastAPI Router
      ↓
Domain Client
      ↓
Laravel API
      ↓
Tests
      ↓
README / API documentation
```

避免只修改其中一層造成 integration regression。

---

## 17. Design Principles

本專案遵循幾個簡單原則：

### Keep Responsibilities Clear

```text
Router       → HTTP contract
Client       → API communication
Workflow     → Cross-domain orchestration
Laravel      → Loyalty business logic
Tests        → Regression protection
```

### Prefer Consistency

相同類型的 Domain Client、Router 與測試應採用一致的命名與結構。

### Avoid Unnecessary Abstraction

目前不刻意增加：

* Repository layer
* Service abstraction
* Abstract Factory
* 額外 Interface hierarchy

只有在實際需求出現時才增加抽象層。

### Make Changes Verifiable

任何 API behavior change 都應至少同步確認：

* implementation
* test
* route contract
* documentation

---

## 18. Current Verification Status

目前專案的基本驗證流程：

```bash
python -m compileall -q app tests
python -m pytest -q -m "not integration"
python verify_routes.py
git diff --check
```

完成上述驗證後，可以確認：

* Python source 可正常編譯
* pytest test suite 可正常執行
* FastAPI application 可以正常建立
* API routes 正確註冊
* 核心 API contract 存在
* Git patch 沒有 whitespace error

---

## 19. Development Philosophy

這個專案不以「增加更多 abstraction」作為工程品質的目標。

核心原則是：

> **讓下一個維護這個專案的人，可以快速理解每一層負責什麼，以及修改後應該如何驗證。**

因此優先考量：

* 清楚的命名
* 一致的結構
* 明確的責任邊界
* 穩定的 API contract
* 可重現的測試
* 與程式碼同步的文件

而不是為了架構而架構。
