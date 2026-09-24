# Loyalty Integration

Python 外部整合系統，用於驗證與演示 **Multi-Tenant Loyalty Platform**（Laravel）的 API 整合能力。

本專案模擬真實 POS / CRM / E-commerce 等外部系統，透過 HTTP API 安全串接 Laravel Loyalty Platform，重點展示：

* JWT Authentication
* Multi-Tenant Tenant Isolation
* Customer Management
* Point Earn / Redeem
* Point Transaction Query
* Idempotency 防重送 / 防重複扣點
* POS 完整結帳流程
* Coupon Claim / Query / Redeem
* Mixed Payment（點數折抵）
* Reward Grant
* QR Code 會員識別
* QR Code 取得
* FastAPI Integration Layer
* Swagger / ReDoc API 文件

### Known Limitations

* production 使用單一 shared `LaravelClient` 與 JWT token；`/auth/login`、`/auth/refresh`、`/auth/logout` 會改變整個 integration process 的 token，不是每個呼叫者各自的 session。因此目前適合單一 Laravel service account，不代表已完成多使用者 authentication isolation。
* `POSCheckoutWorkflow` 會依序執行查詢、earn、redeem；目前 endpoint 沒有接收 workflow-level `Idempotency-Key`，也沒有跨 API 的補償交易。重送 workflow 可能再次執行子交易，呼叫端應自行避免重送或使用直接的 domain endpoint。
* Laravel business rules、tenant isolation、rate limit 與資料一致性由外部 Laravel API 決定；Python layer 不會自行 retry、refresh token 或模擬資料庫 rollback。

> 設計原則：Python 只負責「決策與編排」，所有點數與優惠券的一致性、交易鎖定、FIFO、餘額計算、Coupon 狀態及 Idempotency 皆由 Laravel Loyalty Platform 負責。

---

## 專案架構

```text
Multi-Tenant Loyalty Platform
        Laravel API
             ▲
             │ REST API + JWT
             │
    Loyalty Integration
          FastAPI
             │
      ┌──────┼──────┐
      ▼      ▼      ▼
     POS    CRM   E-commerce
```

Python Integration Layer 不重新實作 Loyalty Business Logic，而是模擬外部系統如何呼叫 Laravel API。

---

## 專案結構

```text
loyalty-integration/
├── app/
│   ├── core/
│   │   └── dependencies.py         # application 共用 dependency / Laravel Client
│   ├── routers/                     # FastAPI HTTP/API contract
│   │   ├── auth.py
│   │   ├── customers.py
│   │   ├── points.py
│   │   ├── coupons.py
│   │   ├── rewards.py
│   │   └── workflows.py
│   ├── client/                      # Laravel API communication
│   │   ├── base.py                 # 核心 HTTP Client（JWT + Idempotency-Key）
│   │   ├── customer.py             # Customer API
│   │   ├── point.py                # Point API
│   │   ├── coupon.py               # Coupon API
│   │   └── reward.py               # Reward API
│   │
│   ├── workflows/
│   │   └── pos_checkout.py          # POS 完整結帳流程
│   │
│   ├── config.py                   # 環境設定
│   └── main.py                     # FastAPI Integration Layer
│
├── tests/
│   ├── __init__.py
│   ├── conftest.py
│   ├── find_valid_campaigns.py
│   ├── test_login.py
│   ├── test_customer_point.py
│   ├── test_idempotency.py
│   ├── test_pos_checkout.py
│   ├── test_coupon.py
│   ├── test_coupon_redeem.py
│   ├── test_coupon_claim.py
│   ├── test_mixed_payment.py
│   ├── test_point_transactions.py
│   ├── test_point_transaction_create.py
│   ├── test_simple_idempotency.py
│   └── test_reward_grants.py
├── .env
└── README.md
```

---

# Architecture / Refactoring

目前的 FastAPI application 已完成 router 結構化重構。實際結構如下：

```text
app/
├── main.py
├── core/
│   └── dependencies.py
├── client/
├── routers/
│   ├── auth.py
│   ├── customers.py
│   ├── points.py
│   ├── coupons.py
│   ├── rewards.py
│   └── workflows.py
└── workflows/
```

各層責任如下：

| Layer | 責任 |
| --- | --- |
| `app.main` | 由 `create_app()` 建立 FastAPI application、設定 lifespan、錯誤處理與 router registration。 |
| `app.core` | 提供 application 共用 dependency；目前由 `dependencies.py` 管理共用的 `laravel_client`。 |
| `app.routers` | 暴露 HTTP endpoint、解析 path/query/header/body、建立 API contract；不實作 Laravel business logic。 |
| `app.schemas` | 使用 Pydantic 定義 request schema 與欄位驗證。 |
| `app.client` | 集中處理 Laravel API communication、JWT、`Idempotency-Key` 與 Laravel API error。 |
| `app.workflows` | 集中處理跨多個 API 的流程編排，例如 POS checkout。 |

`create_app()` 會註冊 `auth_router`、`customers_router`、`points_router`、`coupons_router`、`rewards_router` 與 `workflows_router`。application module 仍提供 `app = create_app()` 作為 Uvicorn 啟動入口；測試與診斷則可以直接呼叫 `create_app()` 建立獨立 instance。

Router 不應自行建立沒有 application lifecycle 狀態的 `LaravelClient`。目前 router 使用 `app.core.dependencies.laravel_client`，各 domain client（例如 `CustomerClient`、`PointClient`）只包裝這個 shared Laravel client。服務啟動時由 lifespan 執行一次 login，讓各 router 使用一致的 JWT token，也避免重複建立未登入的 HTTP client。測試 fixture 若需要隔離測試狀態，則可以另外建立測試用 client；這不改變 production application 的 shared-client contract。

## Refactoring Changes

### Router decomposition

原本集中在單一入口的 API endpoint 已依功能拆分為：

* `auth.py`：Login、Me、Refresh、Logout
* `customers.py`：Customer、Membership、QR Code 與 QR identification
* `points.py`：Balance、Point Transactions、Earn、Redeem
* `coupons.py`：Coupon query、Claim、Redeem、Redemption history、Mixed Payment
* `rewards.py`：Reward Grants 與 Grant Reward
* `workflows.py`：POS checkout workflow

這個拆分讓 HTTP contract 與 domain client 的責任更容易定位，也讓 route inventory 可以逐個 router 檢查是否遺失或重複註冊 endpoint。

### Application factory

```python
from app.main import create_app

app = create_app()
```

`create_app()` 負責建立完整 FastAPI application 並註冊所有 routers。application factory 的目的包括：

* 避免 application initialization 順序問題
* 讓 `TestClient` 可以建立獨立 app instance
* 讓測試明確建立完整 application
* 降低 module import side effect 對測試的影響
* 讓 production 與 test environment 使用相同的 app construction path

`lifespan` 會在 application 啟動時呼叫 shared Laravel client 的 login；若 Laravel authentication 失敗，啟動會失敗，而不是把未驗證的 application 當成已就緒服務。

### Shared Laravel Client

所有 router 都從 `app.core.dependencies` 使用同一個 `laravel_client`，router module 不應直接建立自己的：

```python
LaravelClient()
```

共享 client 的原因是：

* JWT token 必須一致
* 避免 router 使用尚未登入的 client
* 避免重複建立 HTTP client state
* lifecycle login 後，所有 router 都使用同一個 authenticated client

`app.client.base.LaravelClient` 負責 JWT header、request、`Idempotency-Key`、response status 與 `LaravelAPIError`；`app.main` 再將該錯誤轉換成 FastAPI JSON error response。

### Diagnostic tooling

以下腳本是 route/application regression 的診斷工具，不是 production code：

| Script | 用途 |
| --- | --- |
| `list_all_routes.py` | 透過 `TestClient` 觸發 lifecycle，列出 OpenAPI paths，檢查 Points、Coupons、Rewards 與各 router 的 route registration。 |
| `verify_routes.py` | 建立 `create_app()`，列出 route inventory，並檢查一組關鍵 path 是否存在。 |
| `tests/test_client_verification.py` | 驗證 `create_app()`、TestClient initialization、OpenAPI、`/health` 與 `/auth/me`。 |

---

# 安裝與環境

目前 `requirements.txt` 使用 exact pins，runtime 與 test dependency 都由同一份檔案管理：

* Python 3.10+
* FastAPI `0.141.1`
* Uvicorn `0.53.0`
* HTTPX `0.28.1`
* Pydantic `2.13.5`
* Pydantic Settings `2.15.0`
* python-dotenv `1.2.3`
* Rich `15.0.0`
* pytest `9.1.1`
* pytest-asyncio `1.4.0`

測試依賴已列在 `requirements.txt`，不需要另外安裝。

```bash
python -m venv venv

# Windows PowerShell
venv\Scripts\Activate.ps1

pip install -r requirements.txt
```

本次驗證環境的實際版本為：FastAPI `0.141.1`、Pydantic `2.13.5`、HTTPX `0.28.1`、pytest `9.1.1`、pytest-asyncio `1.4.0`。這些是本次環境輸出，不代表 requirements 的 pinned version。

`.env` 必須提供 `app.config.Settings` 所需的 Laravel 設定：

```env
LARAVEL_API_BASE_URL=http://localhost:8088/api/v1
LARAVEL_EMAIL=your-test-account@example.com
LARAVEL_PASSWORD=your-password
```

`LARAVEL_EMAIL` 與 `LARAVEL_PASSWORD` 沒有程式內預設值；沒有有效設定時，import/application startup verification 會失敗。

---

# Testing & Verification

重構後的驗收不只檢查 Python syntax，而是分成 application construction、route contract、pytest collection/regression 與 Laravel integration 四層。建議在已啟動、可登入且有測試資料的 Laravel API 環境執行下列命令。

## 1. Python import verification

```bash
python -c "import app.main; print('IMPORT OK')"
```

此命令確認 `app.main` 可正常 import、module dependencies 沒有 circular import，並會執行目前 module-level `app = create_app()` 的 application construction。它不會執行 lifespan login。

本次結果：`IMPORT OK`。

## 2. Application creation verification

```bash
python -c "from app.main import create_app; app = create_app(); print('CREATE_APP OK'); print('OPENAPI PATHS', len(app.openapi()['paths']))"
```

確認 factory 可以建立完整 application，且 OpenAPI 可以取得所有已註冊 paths。本次結果為 `CREATE_APP OK`、`OPENAPI PATHS 27`。實際啟動時的 Laravel login 則由 TestClient/lifespan verification 另行確認。

## 3. Route inventory / API contract

```bash
python verify_routes.py
python list_all_routes.py
```

route inventory 應檢查：

* Auth routes
* Customer routes
* Point routes
* Coupon routes
* Reward routes
* Workflow routes
* HTTP method、path 與 router registration

`verify_routes.py` 本次檢查的 18 個關鍵 paths 全部存在；`list_all_routes.py` 本次列出 27 個 OpenAPI paths，Points、Coupons、Rewards 三組驗證均為 `PASS`。同一路徑支援多個 HTTP method 時，path 數與 operation 數不同；本次 route inventory 共 28 個 HTTP operations。

API contract 以目前 application OpenAPI / route inventory 為準，實際 endpoint 如下：

| Domain | Method / Path |
| --- | --- |
| Auth | `POST /auth/login`、`GET /auth/me`、`POST /auth/refresh`、`POST /auth/logout` |
| Customers | `GET /customers`、`GET /customers/{customer_id}`、`GET /customers/{customer_id}/membership`、`GET /customers/{customer_id}/qr-code`、`POST /customers/identify` |
| Points | `GET /customers/{customer_id}/points`、`GET/POST /customers/{customer_id}/point-transactions`、`GET /customers/{customer_id}/point-transactions/expiring`、`GET /customers/{customer_id}/point-transactions/{transaction_id}`、`POST /points/earn`、`POST /points/redeem` |
| Coupons | `GET /customers/{customer_id}/coupons`、`GET /customers/{customer_id}/coupons/{user_coupon_id}`、`GET /customers/{customer_id}/coupon-redemptions`、`POST /customers/{customer_id}/coupons/claim`、`POST /coupons/claim`、`POST /coupons/redeem`、`POST /payments/mixed` |
| Rewards | `GET /customers/{customer_id}/reward-grants`、`POST /customers/{customer_id}/rewards/grant` |
| Workflows | `POST /workflows/pos-checkout` |
| Service | `GET /`、`GET /health` |

## 4. Pytest

```bash
python -m pytest --collect-only -q
python -m pytest -q
```

`--collect-only` 只確認測試是否被 pytest 完整收集，不會執行 Laravel API request；`pytest` 才會執行目前測試 suite。pytest 設定使用 `asyncio_mode = auto`，目前 collection 包含 `tests/test_point_transaction_create.py` 的 5 個測試與 `tests/test_reward_grants.py` 的 7 個測試。

本次實際結果：`12 passed, 2 warnings in 15.61s`。warning 是 FastAPI/Starlette TestClient 對目前 HTTPX 與 AnyIO 使用方式的 deprecation warning，不影響本次 exit code。`tests/` 中其他 `test_*.py` 是 standalone integration scripts，並不會因為 `pytest` collection 自動納入本次 12 個測試。

---

# Functional Verification Matrix

下表區分「目前程式碼與 route contract 已確認」及「本次命令實際驗證」。沒有在本次命令中執行的 standalone script，不標示為 PASS。

| Domain | 程式碼 / route contract | 本次實際驗證 |
| --- | --- | --- |
| Authentication | Login、Me、Refresh、Logout；lifespan 使用 Laravel login | `test_client_verification.py` 的 application login 與 `/auth/me` PASS；pytest 未涵蓋全部 auth methods |
| Customers | List、Detail、Membership、QR Code、QR identify | router inventory PASS；本次未以 customer standalone script 逐項執行 |
| Points | Balance、Transactions query/create、Expiring、Detail、Earn、Redeem | route inventory PASS；pytest 的 point transaction tests 12 測試中的 5 個 PASS；其他 point endpoints 未在本次 pytest 中逐項執行 |
| Point idempotency | Point transaction create 傳遞 `Idempotency-Key` | `test_point_transaction_create.py` 相關 pytest PASS |
| Coupons | List、Detail、Claim、Redeem、Redemption history、Mixed Payment | route inventory PASS；本次未以 coupon standalone scripts 逐項執行 |
| Rewards | Reward Grants query、Grant Reward、Idempotency、validation、unauthorized、tenant isolation | route inventory PASS；`test_reward_grants.py` 7 個 pytest PASS |
| POS | `POST /workflows/pos-checkout` 編排 Customer、Balance、Earn、Redeem、final balance | workflow route 存在；本次未執行 POS standalone script |
| API Contract | HTTP method、path、request schema、OpenAPI registration | `create_app()`、`verify_routes.py`、`list_all_routes.py` PASS；OpenAPI 27 paths / 28 operations |
| Router registration | 六個功能 router 正確 include | `list_all_routes.py` 各 router 檢查 PASS |
| Application startup | Factory、TestClient、lifespan、Laravel authentication | `test_client_verification.py` PASS |

這個 matrix 不把「route 存在」等同於「Laravel business logic 正確」。後者仍需在有效帳號、tenant 與對應 demo data 下執行 integration test。

---

# Laravel Integration Verification

本專案不是獨立 mock API；`LaravelClient` 會實際呼叫 Laravel Loyalty API：

```text
Python Integration API
            ↓
Laravel Loyalty API
            ↓
Laravel database / business rules
```

驗證應分成兩個層次：

| Verification layer | 驗證內容 |
| --- | --- |
| Integration Layer Verification | FastAPI 可以 import、建立 application、註冊 route、處理 schema、啟動 lifecycle，並把 request 交給 Laravel client。 |
| Business API Verification | Laravel authentication、JWT、customer data、points、coupons、rewards、idempotency 與 tenant-aware behaviour 的實際 response、資料變化與錯誤。 |

因此 Python API 回傳 HTTP 200 只能證明該 integration request 取得成功 response，不能單獨證明 Laravel 的點數一致性、Coupon 狀態、Reward grant 或 tenant isolation 正確。後者應搭配對應 pytest 或 standalone integration script 驗證 response 與資料結果。

可先用下列命令確認 Laravel authentication 與 application lifecycle：

```bash
python tests/test_login.py
python tests/test_client_verification.py
```

本次 `test_client_verification.py` 已確認 Laravel login、TestClient initialization、27 個 OpenAPI paths、`/health` 與 `/auth/me`；本次沒有把所有 standalone domain scripts 的結果寫成 PASS。

---

# Refactoring Acceptance Criteria

重構完成的判定標準如下：

## Application

* application 可以正常 import
* `create_app()` 可以正常建立
* lifespan 可以正常啟動
* Laravel client 可以正常 authentication

## Router

* 所有 router 正確註冊
* HTTP method 正確
* API path 正確
* 沒有遺失 endpoint
* 沒有重複 endpoint

## Client

* Router 不自行建立 production `LaravelClient`
* shared client 正常使用
* JWT token 可以正常傳遞
* Laravel API error 可以由 `LaravelAPIError` 轉換成 FastAPI error response

## Tests

* pytest 可以正常 collection
* async tests 正常執行
* regression tests 通過
* route inventory 通過
* integration endpoints 可以正常呼叫

## Documentation

* README 描述目前實際架構
* README 提供安裝方式
* README 提供測試方式
* README 提供 regression verification 方法
* README 說明重構內容

本次可判定為通過的項目包括 import、factory、route inventory、TestClient/lifespan/authentication，以及 12 個 pytest 測試。`verify_routes.py` 會檢查關鍵路徑與 HTTP method，發現 mismatch 時以非零 exit code 結束；`list_all_routes.py` 則是完整 route inventory 與人工診斷輸出，不取代 business API 測試。

---

# Regression Testing

每次修改 Router、Client、Workflow 或 application initialization 後，至少執行：

```bash
python -m pytest --collect-only -q
python -m pytest -q
python verify_routes.py
python list_all_routes.py
```

若修改會影響 application startup 或 Laravel authentication，再執行：

```bash
python tests/test_client_verification.py
python tests/test_login.py
```

需要驗證特定 Laravel domain 時，使用目前已存在的 standalone scripts，例如 `python tests/test_point_transaction_create.py`、`python tests/test_reward_grants.py`、`python tests/test_pos_checkout.py`、`python tests/test_coupon_claim.py` 或 `python tests/test_mixed_payment.py`。這些腳本會修改或依賴 Laravel demo data，執行前應確認測試 tenant、customer、coupon、reward 與帳號狀態。

---

# Development Workflow

建議後續開發者固定使用以下 regression workflow：

```text
修改程式碼
      ↓
python import / syntax verification
      ↓
pytest --collect-only
      ↓
pytest
      ↓
route inventory
      ↓
API integration verification
      ↓
git diff / git diff --check
      ↓
更新 README（若 architecture / testing flow 有變）
```

其中 `pytest --collect-only` 是 collection check，不能取代完整 pytest；route inventory 也不能取代 Laravel business API verification。每次驗收都應記錄實際輸出的 `PASS`、`FAIL`、`SKIPPED`、`NOT RUN`，不要把未執行或因 demo data 不足而跳過的項目標示為 PASS。

本次文件補強後應執行：

```bash
git diff --check
```

---

# 快速開始

## 1. 環境需求

* Python 3.10+
* Laravel Loyalty API 已啟動
* 可用的 Laravel 測試帳號
* Laravel API 預設：

```text
http://localhost:8088/api/v1
```

---

## 2. 安裝

建立 Python Virtual Environment：

```bash
python -m venv venv
```

### Windows

```bash
venv\Scripts\activate
```

### macOS / Linux

```bash
source venv/bin/activate
```

安裝依賴：

```bash
pip install fastapi uvicorn httpx pydantic pydantic-settings python-dotenv rich pytest pytest-asyncio
```

---

## 3. 設定環境變數

建立或編輯 `.env`：

```env
LARAVEL_API_BASE_URL=http://localhost:8088/api/v1
LARAVEL_EMAIL=your-test-account@example.com
LARAVEL_PASSWORD=your-password
```

---

## 4. 驗證 Laravel API 登入

```bash
python tests/test_login.py
```

成功後應看到類似：

```text
✓ Login successful as your-test-account@example.com

Login successful!
Token: eyJ0eXAiOiJKV1QiLCJhbGci...
```

---

# 啟動 FastAPI 整合層

## 啟動服務

```bash
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

上方才是要輸入終端機的命令。服務成功啟動後，Uvicorn 會輸出類似以下訊息；這段文字是啟動結果，不要再貼回終端機執行：

```text
INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
```

FastAPI 啟動時會透過 Laravel API 進行 JWT Login，之後由 Integration Layer 使用取得的 Token 呼叫 Laravel API。

---

## API 文件

| 用途 | 網址 |
| ------------ | ---------------------------- |
| Swagger UI | <http://localhost:8000/docs> |
| ReDoc | <http://localhost:8000/redoc> |
| Health Check | <http://localhost:8000/health> |
| Root | <http://localhost:8000/> |

---

# FastAPI Integration API

目前 FastAPI 對外提供的主要能力：

| Method | Endpoint                                                   | 說明               |
| ------ | ---------------------------------------------------------- | ---------------- |
| GET    | `/`                                                        | 服務狀態             |
| GET    | `/health`                                                  | Health Check     |
| GET    | `/customers`                                               | Customer 列表      |
| GET    | `/customers/{customer_id}`                                 | Customer 詳細資料    |
| POST   | `/customers/identify`                                      | QR Code 識別會員     |
| GET    | `/customers/{customer_id}/membership`                      | Membership 詳細資料  |
| GET    | `/customers/{customer_id}/qr-code`                         | 取得會員 QR Code     |
| GET    | `/customers/{customer_id}/points`                          | 查詢點數餘額           |
| GET    | `/customers/{customer_id}/point-transactions`              | 查詢點數交易           |
| POST   | `/customers/{customer_id}/point-transactions`              | 建立點數交易           |
| GET    | `/customers/{customer_id}/point-transactions/expiring`     | 查詢即將到期交易       |
| GET    | `/customers/{customer_id}/point-transactions/{transaction_id}` | 查詢單筆交易       |
| POST   | `/points/earn`                                              | 發放點數             |
| POST   | `/points/redeem`                                            | 兌換點數             |
| GET    | `/customers/{customer_id}/coupons`                         | 查詢優惠券            |
| GET    | `/customers/{customer_id}/coupons/{user_coupon_id}`         | 查詢單張優惠券         |
| POST   | `/customers/{customer_id}/coupons/claim`                   | 領取優惠券            |
| POST   | `/coupons/claim`                                            | 以 request body 領券    |
| GET    | `/customers/{customer_id}/coupon-redemptions`              | 查詢優惠券核銷紀錄        |
| POST   | `/coupons/redeem`                                           | 核銷優惠券            |
| POST   | `/payments/mixed`                                           | 混合支付             |
| GET    | `/customers/{customer_id}/reward-grants`                   | 查詢 Reward Grants |
| POST   | `/customers/{customer_id}/rewards/grant`                   | 發放 Reward        |
| POST   | `/workflows/pos-checkout`                                  | POS 完整結帳流程       |

實際 Laravel API 路由仍以 Laravel Loyalty Platform 的 `/api/v1` Route 定義為 Single Source of Truth。

---

# Idempotency

本專案目前已將外部 `Idempotency-Key` 支援整合至需要冪等性的交易 API。

支援：

* Point Transaction Create
* Point Redeem
* Coupon Claim
* Coupon Redeem
* Mixed Payment
* Reward Grant

外部系統可以自行產生並傳入：

```http
Idempotency-Key: order-20260923-001
```

Python Integration Layer 不會自行處理交易冪等邏輯，而是將 Key 原樣傳遞給 Laravel API。

例如：

```bash
curl -X POST http://localhost:8000/customers/1/points/redeem \
  -H "Content-Type: application/json" \
  -H "Idempotency-Key: order-20260923-001" \
  -d '{
    "amount": 10
  }'
```

同一個 `Idempotency-Key` 重送相同交易時，由 Laravel Idempotency Middleware 保證不會再次執行相同交易。

> Python 的責任是傳遞 Idempotency-Key；真正的冪等性保證由 Laravel Core 實作。

---

# Coupon

目前已支援完整的 Coupon Integration Flow：

```text
Coupon Template
      │
      ▼
Coupon Claim
      │
      ▼
User Coupon
      │
      ▼
Coupon Redeem
      │
      ▼
Coupon Redemption
```

FastAPI Integration Layer 提供：

```text
GET  /customers/{customer_id}/coupons
POST /customers/{customer_id}/coupons/claim
GET  /customers/{customer_id}/coupon-redemptions
POST /coupons/redeem
POST /payments/mixed
```

Coupon Claim 同樣支援外部：

```http
Idempotency-Key
```

因此外部系統可以安全重送領券請求。

---

# Reward Grant

Reward Integration 支援：

```text
GET  /customers/{customer_id}/reward-grants
POST /customers/{customer_id}/rewards/grant
```

Reward Grant 支援：

* Campaign Reward
* Quantity
* Reference
* Description
* Idempotency-Key

例如：

```bash
curl -X POST http://localhost:8000/customers/10/rewards/grant \
  -H "Content-Type: application/json" \
  -H "Idempotency-Key: reward-order-001" \
  -d '{
    "campaign_reward_id": 1,
    "quantity": 1,
    "reference": "POS-ORDER-001",
    "description": "POS Reward Grant"
  }'
```

相同 Key 重送時，Laravel 會回傳原始交易結果，而不會建立第二筆 Reward Grant。

---

# POS 完整結帳流程

FastAPI 提供 POS Workflow：

```text
POS
 │
 ├── Customer Identify
 │
 ├── Query Customer
 │
 ├── Query Point Balance
 │
 ├── Earn Points
 │
 ├── Redeem Points
 │
 └── Verify Final Balance
```

執行：

```bash
python tests/test_pos_checkout.py
```

或透過 FastAPI：

```bash
curl -X POST http://localhost:8000/workflows/pos-checkout \
  -H "Content-Type: application/json" \
  -d '{
    "customer_id": 1,
    "earn_amount": 50,
    "redeem_amount": 20
  }'
```

Python Workflow 只負責 orchestration，實際點數餘額與交易一致性由 Laravel 處理。

---

# QR Code 會員識別

QR Code Integration 模擬真實 POS 掃碼流程：

```text
會員中心
   │
   ▼
GET /customers/{customer_id}/qr-code
   │
   ▼
取得 QR Token
   │
   ▼
POS 掃描
   │
   ▼
POST /customers/identify
   │
   ▼
取得 Customer
```

取得 QR Code：

```bash
curl http://localhost:8000/customers/1/qr-code
```

使用 QR Token：

```bash
curl -X POST http://localhost:8000/customers/identify \
  -H "Content-Type: application/json" \
  -d '{
    "qr_token": "your-qr-token"
  }'
```

---

# 核心演示腳本

除了 FastAPI HTTP API，也可以直接執行 CLI Integration Tests。

| 腳本 | 驗證內容 |
| ---------------------------------- | -------------------- |
| `tests/test_login.py` | JWT Authentication |
| `tests/test_customer_point.py` | Customer / Point 查詢 |
| `tests/test_point_transactions.py` | Point Transaction 查詢 |
| `tests/test_point_transaction_create.py` | Point Transaction 建立 |
| `tests/test_idempotency.py` | Point Idempotency |
| `tests/test_simple_idempotency.py` | 基本 Idempotency 驗證 |
| `tests/test_pos_checkout.py` | POS 完整結帳 |
| `tests/test_coupon.py` | Coupon Query |
| `tests/test_coupon_claim.py` | Coupon Claim |
| `tests/test_coupon_redeem.py` | Coupon Redeem |
| `tests/test_coupon_queries.py` | Coupon Query |
| `tests/test_mixed_payment.py` | Mixed Payment |
| `tests/test_reward_grants.py` | Reward Grant |

---

# 最重要的演示：Idempotency

執行：

```bash
python tests/test_idempotency.py
```

核心驗證流程：

```text
第一次 Request
      │
      ▼
Laravel 執行交易
      │
      ▼
成功扣點
      │
      ▼
使用相同 Idempotency-Key 重送
      │
      ▼
Laravel Middleware Replay
      │
      ▼
不建立第二筆交易
```

驗證重點：

1. 第一次請求成功
2. 第二次使用相同 `Idempotency-Key`
3. Laravel 回傳原始交易結果
4. 不會重複扣點
5. 最終餘額維持正確

---

# API Coverage Audit

目前已完成 Laravel API 與 Python Integration Layer 的 Coverage Audit。

| 狀態 | 數量 |
| ------------ | -------: |
| Covered | 26 |
| Partial | 0 |
| Missing | 0 |
| N/A | 0 |
| **Coverage** | **100%** |

目前 Integration Layer 已涵蓋 Laravel Loyalty Platform 的核心 API 能力，包括：

* Authentication
* Customer
* Point
* Coupon
* Reward
* Mixed Payment
* QR Code
* Idempotency

> Coverage 代表 API 對應與 Integration Layer 已建立，不代表每一個 Endpoint 都有完整的自動化測試案例。

---

# 已驗證能力

* [x] JWT Authentication
* [x] Customer Query
* [x] Point Balance Query
* [x] Point Transaction Query
* [x] Point Earn
* [x] Point Redeem
* [x] Idempotency
* [x] External `Idempotency-Key`
* [x] POS Checkout
* [x] Coupon Query
* [x] Coupon Claim
* [x] Coupon Redeem
* [x] Coupon Redemption Query
* [x] Mixed Payment
* [x] Reward Grant
* [x] Reward Grant Idempotency
* [x] QR Code Member Identification
* [x] QR Code Retrieval
* [x] FastAPI Integration Layer
* [x] Swagger / ReDoc
* [x] Laravel API Coverage Audit

---

# Laravel Core 與 Python Integration Layer 的責任分工

| Laravel Core                 | Python Integration Layer |
| ---------------------------- | ------------------------ |
| JWT Authentication           | JWT Login / Token 管理     |
| Tenant Isolation             | 傳遞認證資訊並呼叫 API            |
| Customer Business Logic      | API Orchestration        |
| Point Balance                | API 呼叫                   |
| Point Transaction            | API 呼叫                   |
| Point Lot / FIFO             | 不實作                      |
| Transaction Locking          | 不實作                      |
| Idempotency Middleware       | 傳遞 `Idempotency-Key`     |
| Coupon State Machine         | API 呼叫                   |
| Coupon Claim / Redeem        | API Orchestration        |
| Reward Grant                 | API 呼叫                   |
| Mixed Payment Business Logic | API Orchestration        |
| Database Transaction         | 不實作                      |
| Redis / Lock                 | 不實作                      |

因此：

> Laravel Loyalty Platform 是 Business Logic 與 Data Consistency 的 Single Source of Truth。

Python Integration Layer 則模擬：

> **POS / CRM / E-commerce 等外部系統如何使用 Loyalty API。**

---

# 設計原則

## Python 負責

* 取得與管理 JWT
* HTTP API 呼叫
* 傳遞 `Idempotency-Key`
* 編排業務流程
* POS Workflow
* FastAPI HTTP Integration Layer
* 整合測試與驗證

## Python 不負責

* 修改點數餘額
* 實作 Point Lot / FIFO
* 實作交易 Lock
* 實作 Coupon State Machine
* 實作 Idempotency Persistence
* 實作 Database Transaction
* 實作 Redis Lock
* 直接操作 Laravel Database

所有核心交易狀態由 Laravel Loyalty Platform 管理。

---

# 建議演示順序

### 1. 啟動 Laravel Loyalty API

確認：

```text
http://localhost:8088/api/v1
```

可以正常使用。

### 2. 啟動 FastAPI Integration Layer

```bash
uvicorn app.main:app --reload --port 8000
```

### 3. 開啟 Swagger UI

```text
http://localhost:8000/docs
```

### 4. QR Code 會員識別

```text
GET /customers/{customer_id}/qr-code
        ↓
POST /customers/identify
```

模擬：

```text
POS 掃描會員 QR Code
        ↓
取得 Customer
```

### 5. 查詢會員點數

```text
GET /customers/{customer_id}/points
```

### 6. 執行 POS Checkout

```text
POST /workflows/pos-checkout
```

驗證：

```text
Customer
 → Point Balance
 → Earn
 → Redeem
 → Final Balance
```

### 7. 演示 Coupon

```text
GET  /customers/{customer_id}/coupons
POST /customers/{customer_id}/coupons/claim
POST /coupons/redeem
```

### 8. 演示 Reward Grant

```text
POST /customers/{customer_id}/rewards/grant
```

### 9. 演示 Idempotency

```bash
python tests/test_idempotency.py
```

並使用相同 `Idempotency-Key` 重送交易。

---

# 測試狀態

目前 Integration Layer 已完成多個真實 Laravel API Integration Tests。

已驗證範圍包含：

* Authentication
* Customer / Point
* Point Transaction
* Point Redeem
* Idempotency
* POS Checkout
* Coupon Query
* Coupon Redeem
* Mixed Payment
* Reward Grant
* Reward Grant Idempotency

部分測試會因 Laravel Demo Data 是否存在特定 Coupon Template / Reward / Customer 而需要對應測試資料。

因此 README 不將資料不足造成的 `SKIPPED` 視為 `PASS`。

測試結果應以實際執行時輸出的：

```text
PASS
FAIL
SKIPPED
NOT RUN
```

為準。

---

# 未來可擴充方向

* Integration Layer API Authentication
* API Key / Service Authentication
* CI 自動化 Integration Tests
* Docker Compose 一鍵啟動 Laravel + FastAPI
* POS / CRM / E-commerce 不同 Integration Client Demo
* Webhook / Event Integration
* 定期資料同步
* Integration Monitoring / Logging

---

# 總結

本專案是一個 **Laravel Multi-Tenant Loyalty Platform 的外部系統 Integration Demo**。

它不是另一套 Loyalty Business Logic，而是模擬：

```text
POS / CRM / E-commerce
          │
          │ REST API
          ▼
   FastAPI Integration
          │
          │ JWT + Idempotency-Key
          ▼
Laravel Loyalty Platform
          │
          ├── Customer
          ├── Points
          ├── Point Transactions
          ├── Coupon
          ├── Reward
          ├── Mixed Payment
          ├── Idempotency
          ├── Tenant Isolation
          └── Transaction Consistency
```

目前已完成的核心 Integration 能力包括：

* JWT Authentication
* Multi-Tenant API Integration
* Customer Management
* Point Earn / Redeem
* Point Transaction
* Idempotency
* External `Idempotency-Key`
* POS Checkout
* Coupon Claim / Query / Redeem
* Mixed Payment
* Reward Grant
* Reward Grant Idempotency
* QR Code Member Identification
* FastAPI Integration Layer
* Swagger / ReDoc
* Laravel API Coverage Audit

核心設計原則保持不變：

> **Python 負責 Integration 與 Workflow Orchestration；Laravel 負責所有 Loyalty Business Logic、交易一致性與資料安全。**
