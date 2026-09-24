# Loyalty Integration Demo｜Loyalty 整合展示專案

一個以 **FastAPI** 建立的 Loyalty / Point API Integration Demo，用來示範外部系統如何透過統一的 Python Client 整合 Laravel Loyalty API。

本專案本身**不是 Loyalty Backend**，而是位於外部系統與 Laravel Loyalty API 之間的 **Integration Layer**，負責 API 整合、認證、Workflow Orchestration、錯誤處理、Idempotency-Key 傳遞與 API Contract 驗證。

> **FastAPI 負責 Integration；Laravel 負責 Loyalty Domain。**

這是本專案最重要的責任邊界。

---

# 1. 專案概述｜Project Overview

本專案模擬企業外部系統整合 Loyalty Platform 的情境。

可能的外部系統包括：

* POS
* Website
* Mobile App
* E-commerce
* CRM
* 第三方會員系統

整體架構：

```text
External System
      │
      ▼
┌────────────────────────────┐
│ FastAPI Integration Layer  │
│                            │
│  CustomerClient            │
│  PointClient               │
│  CouponClient              │
│  RewardClient              │
│  Workflow                  │
└─────────────┬──────────────┘
              │
              │ REST API
              │ JWT
              │ Idempotency-Key
              ▼
┌────────────────────────────┐
│ Laravel Loyalty API        │
│                            │
│  Customer                  │
│  Points                    │
│  Coupons                   │
│  Rewards                   │
│  Business Rules            │
│  Idempotency               │
│  Persistence               │
└────────────────────────────┘
```

本專案的核心不是增加更多 Layer，而是建立清楚的責任邊界：

| Layer           | Responsibility                                |
| --------------- | --------------------------------------------- |
| External System | 外部業務情境與使用者流程                                  |
| FastAPI Router  | HTTP API Contract                             |
| Domain Client   | Laravel API Communication                     |
| Workflow        | Cross-domain Orchestration                    |
| Laravel API     | Loyalty Domain Business Logic                 |
| Tests           | Regression Protection / Contract Verification |

---

# 2. 為什麼需要 Integration Layer｜Why This Integration Layer Exists

外部系統理論上可以直接呼叫 Laravel Loyalty API。

但如果每一個外部系統都自行整合，會逐漸產生重複的 Integration Concerns：

* JWT Authentication
* Token Refresh
* HTTP Error Handling
* Timeout Handling
* API Contract Mapping
* Idempotency-Key 傳遞
* Cross-domain Workflow
* Integration Testing

例如：

```text
POS
 ├── JWT Login
 ├── Customer API
 ├── Point API
 ├── Coupon API
 └── Error Handling

Website
 ├── JWT Login
 ├── Customer API
 ├── Point API
 ├── Coupon API
 └── Error Handling

CRM
 ├── JWT Login
 ├── Customer API
 ├── Point API
 ├── Coupon API
 └── Error Handling
```

這些重複的 Integration Logic 可以集中到：

```text
External Systems
       │
       ▼
Integration Layer
       │
       ▼
Laravel Loyalty API
```

Integration Layer 的目的不是重新實作 Loyalty Domain。

它的目的，是提供一個穩定且一致的整合邊界，讓外部系統不需要直接依賴 Laravel API 的整合細節。

---

# 3. 核心架構原則｜Core Architecture Principles

本專案遵循幾個核心原則。

## 3.1 單一真相來源｜Single Source of Truth

Laravel 是 Loyalty Domain 的唯一 Business Logic Owner。

以下規則由 Laravel 負責：

* Point Balance
* Point Transaction
* Point Expiration
* Coupon Eligibility
* Coupon Redemption
* Reward Eligibility
* Reward Grant
* Idempotency
* Loyalty State

FastAPI 不複製這些規則。

---

## 3.2 Integration Layer 不成為第二個 Domain｜No Duplicate Domain Logic

FastAPI 可以：

* 呼叫 API
* 組合 API
* Mapping Request / Response
* 傳遞 Idempotency-Key
* 處理 Integration Error
* 編排跨 Domain Workflow

FastAPI 不應：

* 重新計算 Loyalty Business Rules
* 自行維護 Point Balance
* 自行判斷 Coupon Eligibility
* 自行建立第二套 Idempotency State
* 假裝擁有 Laravel Database Transaction

核心原則：

> **Integration Layer 可以負責 Integration，但不能成為 Loyalty Domain 的第二個真相來源。**

---

# 4. 架構責任邊界｜Architecture & Responsibility Boundary

整個系統可以簡化成：

```text
External System
      │
      ▼
┌──────────────────────────┐
│ Router                   │
│ HTTP Contract            │
└────────────┬─────────────┘
             │
             ▼
┌──────────────────────────┐
│ Workflow                 │
│ Cross-domain Orchestration│
└────────────┬─────────────┘
             │
             ▼
┌──────────────────────────┐
│ Domain Client            │
│ API Communication        │
└────────────┬─────────────┘
             │
             ▼
┌──────────────────────────┐
│ Laravel Loyalty API      │
│ Domain Logic             │
│ State / Transaction      │
└──────────────────────────┘
```

可以用一句話描述：

```text
Router       → HTTP Contract
Client       → API Communication
Workflow     → Cross-domain Orchestration
Laravel      → Loyalty Business Logic
Tests        → Regression Protection
```

---

# 5. 技術棧｜Technology Stack

## Integration Layer

* Python 3.13+
* FastAPI
* Uvicorn
* HTTPX
* Pydantic
* pytest
* pytest-asyncio
* python-dotenv

## Backend

* Laravel
* JWT Authentication
* REST API

---

# 6. 專案結構｜Project Structure

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
│   │
│   ├── unit/
│   │   └── test_client_auth.py
│   │
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

---

# 7. Client Layer｜Domain Client

`app/client` 負責封裝 Laravel API 通訊。

架構：

```text
LaravelClient
    │
    ├── CustomerClient
    ├── PointClient
    ├── CouponClient
    └── RewardClient
```

## Base Client

`LaravelClient` 負責共用 Integration Concerns：

* HTTP Request
* JWT Authentication
* Token Management
* Request Timeout
* Common Error Handling
* Authentication State

## Domain Client

Domain Client 負責特定 Domain 的：

* Endpoint Mapping
* Request Payload
* Query Parameters
* Response Handling

例如：

```python
await point_client.create_transaction(
    customer_id=customer_id,
    transaction_type="earn",
    points=100,
)
```

Python 內部使用：

```text
transaction_type
```

Laravel API Contract 則維持：

```json
{
    "type": "earn",
    "points": 100
}
```

也就是：

> **Internal Naming 可以改善語意，但不應因此任意修改 External API Contract。**

---

# 8. Router Layer｜API Router

`app/routers` 負責 FastAPI HTTP Contract。

Router 主要責任：

1. 接收 Request
2. 驗證 Request Data
3. 呼叫 Domain Client 或 Workflow
4. 回傳 API Response

流程：

```text
HTTP Request
     │
     ▼
Router
     │
     ▼
Client / Workflow
     │
     ▼
Laravel API
```

Router 不應重新實作 Loyalty Business Logic。

---

# 9. Workflow Layer｜Workflow Orchestration

`app/workflows` 負責跨 Domain API 的流程編排。

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

Workflow 的責任是：

> **決定 API Operation 的執行順序與整合結果。**

Workflow 不負責：

* Point Calculation
* Coupon Eligibility
* Reward Rules
* Loyalty State

這些仍由 Laravel API 負責。

---

# 10. Application Factory｜Application Factory

FastAPI 使用 Application Factory：

```python
app = create_app()
```

目的在於讓不同 execution context 使用一致的 Application Initialization：

* Uvicorn
* TestClient
* pytest
* Route Verification

Router Registration 集中於 Application Creation Process，避免不同啟動方式產生不同的 Route State。

---

# 11. API Domains｜API 領域

## Authentication｜身份驗證

```text
POST /auth/login
GET  /auth/me
POST /auth/refresh
POST /auth/logout
```

---

## Customers｜會員

```text
GET /customers
GET /customers/{customer_id}
GET /customers/{customer_id}/membership
```

---

## Points｜點數

```text
GET  /customers/{customer_id}/points
GET  /customers/{customer_id}/point-transactions
POST /customers/{customer_id}/point-transactions

GET  /customers/{customer_id}/point-transactions/expiring

GET  /customers/{customer_id}/point-transactions/{transaction_id}

POST /points/earn
POST /points/redeem
```

Transaction Query：

```text
GET /customers/{customer_id}/point-transactions?type=earn

GET /customers/{customer_id}/point-transactions?type=redeem
```

Python Client 使用：

```text
transaction_type
```

對外 Laravel API Contract 維持：

```text
type
```

由 Domain Client 負責 Mapping。

---

## Coupons｜優惠券

```text
GET  /customers/{customer_id}/coupons
GET  /customers/{customer_id}/coupons/{user_coupon_id}
GET  /customers/{customer_id}/coupon-redemptions

POST /coupons/claim
POST /customers/{customer_id}/coupons/claim
POST /coupons/redeem
```

---

## Rewards｜獎勵

```text
GET  /customers/{customer_id}/reward-grants
POST /customers/{customer_id}/rewards/grant
```

---

## Workflows｜工作流程

```text
POST /workflows/pos-checkout
POST /payments/mixed
```

Workflow Endpoint 用於將多個 Loyalty API Operation 組合成完整業務流程。

---

# 12. Idempotency｜冪等性

涉及可能重複執行的 Mutation Request，可以透過：

```http
Idempotency-Key: order-20260924-001
```

傳遞唯一 Request Key。

Integration Layer 的責任是：

```text
Receive Key
    ↓
Forward Key
    ↓
Laravel Handles Idempotency
```

而不是自行建立 Idempotency State。

架構：

```text
External System
      │
      │ Idempotency-Key
      ▼
FastAPI
      │
      │ Forward unchanged
      ▼
Laravel API
      │
      ▼
Idempotency Handling
```

---

# 13. 為什麼 Idempotency State 放在 Laravel｜Why Idempotency State Belongs to Laravel

如果 FastAPI 與 Laravel 各自維護 Idempotency：

```text
FastAPI Idempotency State
          +
Laravel Idempotency State
```

可能產生：

```text
FastAPI → Request already processed
Laravel → Request is new
```

形成兩套不一致的 State。

因此 Idempotency 的 authoritative state 留在 Laravel。

FastAPI 只負責：

* 接收
* 傳遞
* 正確處理 Laravel 回應

這符合：

> **State ownership should remain with the system that owns the business mutation.**

---

# 14. Error Handling｜錯誤處理

`LaravelClient` 統一處理 Laravel API Communication。

主要情境：

* Authentication Failure
* HTTP Error Response
* Timeout
* Connection Failure
* Invalid Response
* Missing Authentication Token

HTTP Status 依 Laravel API Contract 解讀：

```text
2xx → Successful Operation

4xx → Client / Request / Business Validation Error

5xx → Server-side Error
```

Domain Client 不應將 Business Failure 視為成功。

例如：

```text
Laravel API
     │
     │ 422
     ▼
Domain Client
     │
     ▼
Business Failure
     │
     ▼
Workflow must not report success
```

---

# 15. Authentication Failure｜身份驗證失敗

如果 Client 沒有有效 Token：

```text
Client
  │
  ├── No Token
  │
  ▼
Reject Request
```

而不是：

```text
Client
  │
  ├── No Token
  │
  ▼
Send Request
  │
  ▼
Laravel
```

Integration Layer 應避免主動送出明知缺少必要 Authentication Context 的 Request。

---

# 16. Timeout & Connection Failure｜逾時與連線失敗

需要區分：

```text
HTTP 4xx
HTTP 5xx
Timeout
Connection Failure
Invalid Response
Authentication Failure
```

尤其對 Mutation Request：

```text
Timeout
```

不代表 Laravel 一定沒有執行成功。

可能存在：

```text
FastAPI
   │
   │ Request
   ▼
Laravel
   │
   ├── Operation completed
   │
   └── Response lost
   │
   X
FastAPI timeout
```

因此不能簡單採用：

```python
if error:
    retry()
```

Mutation Retry 必須考慮 Idempotency。

---

# 17. Failure & Consistency｜失敗處理與一致性

跨系統 Workflow 最重要的問題不是「API 能不能呼叫」，而是：

> **當 Workflow 中間失敗時，誰負責一致性？**

以 POS Checkout 為例：

```text
1. Validate Customer
2. Earn Points
3. Redeem Coupon
```

假設：

```text
Validate Customer → Success
Earn Points        → Success
Redeem Coupon      → Failure
```

FastAPI 不會假設自己可以安全地 Rollback 前面的 Laravel Operation。

目前策略：

1. 回傳明確 Workflow Failure。
2. 不在 FastAPI 建立第二套 Transaction System。
3. 不維護第二套 Loyalty State。
4. 依賴 Laravel Idempotency 保護可安全重試的 Mutation。
5. 如果業務要求真正 Atomic Operation，應優先由 Laravel 提供 Composite API。

---

# 18. Workflow Failure Strategy｜Workflow 失敗策略

目前 Workflow 採取：

```text
Orchestrate
    ↓
Detect Failure
    ↓
Return Explicit Failure
```

而不是：

```text
Orchestrate
    ↓
Failure
    ↓
Fake Rollback
    ↓
Assume Consistency
```

如果未來需要真正的 Atomic Checkout，可以考慮由 Laravel 提供：

```text
POST /checkout
```

由 Laravel 在自己的 Transaction Boundary 中處理：

```text
Validate Customer
      ↓
Redeem Coupon
      ↓
Earn Points
      ↓
Commit
```

這樣 Transaction Ownership 仍然位於真正擁有 Loyalty State 的系統。

---

# 19. Deliberate Design Trade-offs｜刻意做出的設計取捨

## 不使用 Repository Layer｜No Repository Layer

目前主要 Data Source 只有：

```text
FastAPI
   ↓
Laravel API
```

因此：

```text
Router
  ↓
Service
  ↓
Repository
  ↓
Client
  ↓
Laravel
```

會增加間接層，但沒有解決實際問題。

只有在未來出現：

* Multiple Backend Provider
* Multiple Data Source
* Provider-specific Persistence

等實際需求時，才考慮 Repository。

---

## 不建立 Duplicate Domain Service｜No Duplicate Domain Service

不在 FastAPI 重寫：

* Point Rules
* Balance Rules
* Coupon Rules
* Reward Rules
* Idempotency Rules

避免：

```text
Laravel Business Rules
        +
FastAPI Business Rules
```

形成兩套可能逐漸 Diverge 的 Domain Logic。

---

## 不使用 Abstract Factory｜No Abstract Factory

目前每個 Domain 只有一種 Client Implementation。

因此：

```text
PointClient
CouponClient
RewardClient
```

已經足夠。

沒有實際需求時，不建立：

```text
Interface
Factory
Abstract Factory
Provider Registry
```

---

## 不在 FastAPI 建立 Idempotency Store｜No FastAPI Idempotency Store

Idempotency State 屬於 Laravel 的 Mutation State，因此保持由 Laravel 管理。

---

## 不提前導入 Saga｜No Premature Saga

目前 Workflow 尚未達到需要 Distributed Compensation 的複雜度。

因此不提前加入：

* Saga Framework
* Workflow Persistence
* Compensation Engine
* Distributed Transaction Framework

等基礎設施。

---

# 20. 架構能力邊界｜When This Architecture Stops Being Enough

目前架構適合：

```text
External System
      ↓
FastAPI Integration Layer
      ↓
Laravel Loyalty API
```

但當需求演進時，需要重新評估架構。

---

## Multiple Backend Providers｜多後端 Provider

例如：

```text
FastAPI
 ├── Laravel Loyalty
 ├── Another Loyalty Provider
 └── External Coupon Provider
```

此時才可能需要：

* Provider Interface
* Adapter
* Factory
* Provider Registry

---

## Long-running Workflows｜長時間工作流程

如果 Workflow 變成：

```text
Payment
   ↓
Loyalty
   ↓
Coupon
   ↓
Notification
   ↓
CRM
```

並且可能持續數秒甚至數分鐘，可能需要：

* Queue
* Async Job
* Persistent Workflow State
* Event
* Compensation
* Saga-style Orchestration

---

## High-volume Integration｜高流量整合

當 Integration Layer 成為大量流量的 Central Gateway，才考慮：

* Rate Limiting
* Retry Policy
* Circuit Breaker
* Metrics
* Distributed Tracing
* Centralized Logging

這些能力不在目前 Demo 階段預先加入。

---

# 21. Code Conventions｜程式碼規範

## Domain Client｜Domain Client

Domain Client 只負責對應 Laravel API。

```python
await point_client.create_transaction(
    customer_id=customer_id,
    transaction_type="earn",
    points=100,
)
```

內部 Mapping：

```python
{
    "type": transaction_type,
    "points": points,
}
```

原則：

* Python Internal Naming 保持語意清楚。
* Laravel API Contract 保持一致。
* 不因 Python Convention 任意修改 External Contract。

---

## Router｜Router

Router：

```text
Request
  ↓
Validation
  ↓
Client / Workflow
  ↓
Response
```

不要在 Router 中重新實作 Loyalty Business Logic。

---

## Workflow｜Workflow

Workflow：

```text
Router
  ↓
Workflow
  ↓
Domain Clients
  ↓
Laravel API
```

Workflow 負責 Orchestration，不負責 Loyalty Domain Rules。

---

# 22. API Contract Principle｜API Contract 原則

本專案與 Laravel Loyalty API 之間存在明確 Contract。

任何以下修改：

* Endpoint
* HTTP Method
* Query Parameter
* Request Body
* Response Structure
* Authentication Behaviour
* Error Handling

都應同步確認：

```text
FastAPI Router
      ↓
Domain Client
      ↓
Laravel API
      ↓
Tests
      ↓
Documentation
```

避免只修改單一層造成 Integration Regression。

---

# 23. 測試策略｜Testing Strategy

測試分為：

```text
tests/
├── unit/
└── integration/
```

---

## Unit Tests｜單元測試

不需要 Laravel API。

適合測試：

* Client Authentication Behaviour
* Request Mapping
* Local Application Logic
* Error Handling

執行：

```bash
python -m pytest -q -m "not integration"
```

---

## Integration Tests｜整合測試

需要實際 Laravel API。

涵蓋：

* Authentication
* Customer API
* Point API
* Point Transaction
* Idempotency
* Coupon API
* Coupon Claim
* Coupon Redemption
* Reward Grant
* POS Checkout
* Mixed Payment
* Client Integration

執行：

```bash
python -m pytest -q -m integration
```

指定測試：

```bash
python -m pytest tests/integration/test_reward_grants.py -q -m integration
```

指定 Test Function：

```bash
python -m pytest tests/integration/test_reward_grants.py::test_1_list_reward_grants -q -m integration
```

---

# 24. Route Contract Verification｜Route Contract 驗證

`verify_routes.py` 用於驗證 FastAPI 最終註冊的 OpenAPI Routes 與 HTTP Methods。

執行：

```bash
python verify_routes.py
```

驗證內容：

1. 建立完整 FastAPI Application。
2. 讀取 OpenAPI Route Definitions。
3. 列出目前 Endpoint。
4. 驗證核心 API Path。
5. 驗證 HTTP Method。
6. 發現 Contract Regression 時以 Non-zero Exit Code 結束。

`verify_routes.py`：

* 不啟動 Application Lifespan
* 不呼叫 Laravel API
* 不需要 Laravel Credentials

---

# 25. Route Inventory｜Route Inventory

`list_all_routes.py` 用於列出完整 Route Inventory。

與 `verify_routes.py` 不同，它會啟動 FastAPI Lifespan。

因此適合用於：

> **完整 Application Startup Verification**

---

# 26. Configuration｜環境設定

建立 `.env`：

```env
LARAVEL_API_BASE_URL=http://127.0.0.1:8088/api/v1

LARAVEL_EMAIL=admin@example.com
LARAVEL_PASSWORD=password

DEFAULT_TIMEOUT=30
```

實際環境請依 Laravel API 設定調整。

不要將實際 `.env` 或 Credentials 提交至 Git。

---

# 27. Installation｜安裝

建立 Virtual Environment：

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

安裝 Dependencies：

```bash
pip install -r requirements.txt
```

---

# 28. Run Application｜啟動應用程式

```bash
uvicorn app.main:app --reload
```

預設：

```text
http://127.0.0.1:8000
```

Health Check：

```text
GET /health
```

---

# 29. CI Verification｜CI 驗證

GitHub Actions Workflow 位於：

```text
.github/workflows/ci.yml
```

在以下情況執行：

* Push 到 `main`
* Push 到 `develop`
* Pull Request 目標為 `main`
* Pull Request 目標為 `develop`

CI 不需要：

* Laravel API URL
* Laravel Credentials
* GitHub Secrets

CI 主要驗證 Integration Application 本身：

```text
Compile
   ↓
Test
   ↓
Application Creation
   ↓
Route Verification
   ↓
Repository Checks
```

---

# 30. Development Verification｜開發驗證

修改 Application Code 後，建議依序執行：

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

| Check              | Purpose                      |
| ------------------ | ---------------------------- |
| `compileall`       | Python Syntax Validation     |
| `pytest`           | Automated Regression Tests   |
| `verify_routes.py` | API Route Contract           |
| `git diff --check` | Patch / Whitespace Integrity |

---

# 31. Integration Environment｜Laravel Integration Environment

Integration Tests 使用：

```text
tests/conftest.py
```

提供 Live Laravel API Fixture。

使用：

```python
@pytest.mark.integration
```

標記。

本機啟動 Laravel API 後，設定：

```env
LARAVEL_API_BASE_URL=
LARAVEL_EMAIL=
LARAVEL_PASSWORD=
```

使用 Coffee Tenant 的測試另外需要：

```env
LARAVEL_COFFEE_EMAIL=
LARAVEL_COFFEE_PASSWORD=
```

執行：

```bash
python -m pytest -q -m integration
```

---

# 32. 目前驗證狀態｜Current Verification Status

目前 Standalone Verification Flow：

```bash
python -m compileall -q app tests

python -m pytest -q -m "not integration"

python verify_routes.py

git diff --check
```

上述驗證可以確認：

* Python Source 可以正常 Compile
* Local Test Suite 可以執行
* FastAPI Application 可以正常建立
* API Routes 正確註冊
* Core API Contract 存在
* Git Patch 沒有 Whitespace Error

Integration Tests 則需要額外可用的 Laravel Loyalty API。

---

# 33. 刻意不做的事情｜What We Deliberately Avoid

本專案目前刻意不增加：

* Repository Layer
* Duplicate Domain Service
* Abstract Factory
* 額外 Interface Hierarchy
* FastAPI-side Idempotency Store
* FastAPI-side Loyalty Business Rules
* 複雜 Saga Framework
* 不必要的 Persistence Layer

原因不是這些技術不好。

而是：

> **目前的需求沒有證明它們是必要的。**

架構演進應由實際需求驅動。

只有當系統真的出現：

* 第二個 Backend Provider
* 多個 External Service
* Long-running Workflow
* Compensation Requirement
* Persistent Workflow State
* High-volume Resilience Requirement

才引入對應的 Abstraction 或 Infrastructure。

---

# 34. 設計原則｜Design Principles

## 保持責任清晰｜Keep Responsibilities Clear

```text
Router       → HTTP Contract

Client       → API Communication

Workflow     → Cross-domain Orchestration

Laravel      → Loyalty Business Logic

Tests        → Regression Protection
```

---

## 保持一致性｜Prefer Consistency

相同類型的：

* Domain Client
* Router
* Workflow
* Test

應採用一致的命名與結構。

---

## 避免不必要的抽象｜Avoid Unnecessary Abstraction

不要因為「未來可能會需要」就提前建立抽象。

應遵循：

> **先解決實際的變化，再抽象實際存在的變化。**

---

## 維持單一真相來源｜Keep One Source of Truth

```text
Loyalty Business Rules
        ↓
Laravel

Loyalty State
        ↓
Laravel

Idempotency State
        ↓
Laravel

Integration Orchestration
        ↓
FastAPI
```

---

## 讓變更可驗證｜Make Changes Verifiable

任何 API Behaviour Change 都應同步確認：

```text
Implementation
      ↓
Tests
      ↓
Route Contract
      ↓
Documentation
```

---

# 35. 開發理念｜Development Philosophy

這個專案不以「增加更多 Abstraction」作為工程品質的目標。

核心目標是：

> **讓下一個維護這個專案的人，可以快速理解每一層負責什麼、為什麼這樣設計，以及修改後應該如何驗證。**

因此優先考量：

* 清楚的命名
* 一致的結構
* 明確的責任邊界
* 穩定的 API Contract
* 可重現的測試
* 清楚的 Failure Boundary
* 與程式碼同步的文件
* 由實際需求驅動的 Abstraction

而不是：

* Architecture for Architecture's Sake
* Premature Abstraction
* Duplicate Business Logic
* 不必要的 Infrastructure

---

# 36. 架構總結｜Architecture Summary

```text
                         External Systems
                                │
                                ▼
                  ┌─────────────────────────┐
                  │ FastAPI Integration     │
                  │                         │
                  │ Router                  │
                  │    ↓                    │
                  │ Workflow                │
                  │    ↓                    │
                  │ Domain Clients          │
                  └────────────┬────────────┘
                               │
                               │ REST / JWT
                               │ Idempotency-Key
                               ▼
                  ┌─────────────────────────┐
                  │ Laravel Loyalty API     │
                  │                         │
                  │ Customer Domain         │
                  │ Point Domain            │
                  │ Coupon Domain           │
                  │ Reward Domain            │
                  │                         │
                  │ Business Rules          │
                  │ Idempotency             │
                  │ Persistence             │
                  └─────────────────────────┘
```

整個架構可以濃縮成兩句話：

> **FastAPI 負責 Integration。**

> **Laravel 負責 Loyalty。**

FastAPI 可以：

* 呼叫 API
* 組合 API
* Mapping API Contract
* 傳遞 Idempotency-Key
* 統一 Integration Error Handling
* 編排 Cross-domain Workflow

但不應：

* 複製 Loyalty Business Rules
* 建立第二套 Loyalty State
* 假裝擁有 Laravel Database Transaction
* 為了預期中的未來需求建立大量抽象

當需求真正跨越目前架構的能力邊界，再引入：

* Provider Architecture
* Adapter
* Queue
* Persistent Workflow
* Compensation
* Saga
* Resilience Infrastructure

如此可以保持：

> **簡單的地方保持簡單；真正複雜的地方才引入複雜度。**

這也是本專案最核心的 Engineering Philosophy。
