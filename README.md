# Loyalty Integration 整合專案｜繁體中文技術文件

一個以 **FastAPI** 建構的 Loyalty / Point API 整合專案，用來示範外部系統如何透過統一的 Python Client 整合 Laravel Loyalty API。

本專案本身**不是 Loyalty 後端**，而是位於外部系統與 Laravel Loyalty API 之間的**整合層（Integration Layer）**，負責 API 整合、認證、工作流程（Workflow）編排、錯誤處理、`Idempotency-Key` 傳遞與 API 契約（API Contract）驗證。

> **核心責任邊界：FastAPI 負責整合（Integration）；Laravel 負責 Loyalty 領域（Loyalty Domain）。**

---

# 專案重點

* 單一真相來源（Single Source of Truth）：Laravel 擁有 Loyalty 狀態與業務邏輯
* 明確責任邊界：FastAPI 為整合層、Laravel 為 Loyalty 領域
* 領域 Client 模式（Domain Client Pattern）：Customer、Point、Coupon、Reward
* 工作流程編排：POS Checkout、Mixed Payment
* 路由契約驗證：`verify_routes.py`
* Idempotency-Key 傳遞：由 FastAPI 傳遞，冪等性狀態由 Laravel 管理
* 失敗邊界設計：不實作虛假的 Rollback
* 刻意的架構取捨：不使用 Repository、不提前導入 Saga、不重複實作領域邏輯

---

# 1. 專案概述

本專案模擬企業外部系統整合 Loyalty 平台的情境，可能的外部系統包括：

* POS 系統
* 網站
* 手機應用程式
* 電商平台
* CRM 系統
* 第三方會員系統

## 整體架構圖

```text
Vue Frontend / External System

      │
      ▼
┌────────────────────────────┐
│ FastAPI Integration Layer  │
│                            │
│  REST Integration          │
│   ├─ CustomerClient        │
│   ├─ PointClient           │
│   ├─ CouponClient          │
│   ├─ RewardClient          │
│   └─ Workflow              │
│                            │
│  Realtime Integration      │
│   └─ WebSocket Gateway     │
│       ├─ Reverb Client     │
│       └─ Frontend Endpoint │
└─────────────┬──────────────┘
      │
      ▼
┌────────────────────────────┐
│ Laravel Loyalty API        │
│                            │
│  Loyalty Domain Logic      │
│  Laravel Reverb WebSocket  │
└────────────────────────────┘
```

## 即時事件流程（Realtime Event Flow）

```text
Laravel Loyalty
      │
      │ Broadcast PointsUpdated
      ▼
Laravel Reverb
      │
      │ WebSocket Pusher Protocol
      ▼
FastAPI Reverb Client
      │
      │ Internal Forwarding
      ▼
FastAPI WebSocket Endpoint (/ws/points/{tenant_id}/{member_id})
      │
      ▼
Vue Frontend
```

### 元件職責說明：
- **Laravel Loyalty**: 負責產生 Loyalty 領域事件 (`PointsUpdated`)
- **Laravel Reverb**: 負責 WebSocket 廣播，實作 Pusher 協定
- **FastAPI Reverb Client**: 作為 WebSocket 用戶端連接 Reverb，接收即時事件
- **FastAPI WebSocket Endpoint**: 提供前端連線，轉發事件給對應的使用者
- **Vue Frontend**: 接收即時更新，更新 UI 顯示最新積分狀態
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

## 層級責任說明

| 層級 | 責任說明 |
| --------------- | ----------------------------------- |
| External System | 外部業務情境與使用者流程 |
| FastAPI Router | HTTP API 契約 |
| Domain Client | Laravel API 通訊 |
| Workflow | 跨領域流程編排（Cross-domain Orchestration） |
| Laravel API | Loyalty 領域業務邏輯 |
| Tests | 回歸測試保護 / 契約驗證 |

---

# 2. 為什麼需要整合層？

外部系統理論上可以直接呼叫 Laravel Loyalty API，但如果每個外部系統都自行整合，會逐漸產生重複的整合關注點（Integration Concerns）：

* JWT 認證
* Token 自動刷新
* HTTP 錯誤處理
* 逾時處理
* API 契約映射
* `Idempotency-Key` 傳遞
* 跨領域工作流程
* 整合測試

如果每個外部系統都重複實作這些邏輯，會形成：

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

這些重複的整合邏輯可以集中到單一整合層，讓所有外部系統共享：

```text
External Systems

       │
       ▼

Integration Layer

       │
       ▼

Laravel Loyalty API
```

整合層的目的不是重新實作 Loyalty 領域邏輯，而是提供一個穩定一致的整合邊界，讓外部系統不需要直接依賴 Laravel API 的整合細節。

---

# 3. 核心架構原則

## 3.1 單一真相來源

Laravel 是 Loyalty 領域唯一的業務邏輯擁有者，以下規則完全由 Laravel 負責：

* 點數餘額計算
* 點數交易管理
* 點數到期處理
* 優惠券資格判斷
* 優惠券兌換邏輯
* 獎勵資格判斷
* 獎勵發放邏輯
* 冪等性狀態管理
* 所有 Loyalty 狀態儲存

FastAPI 不會複製這些領域規則。

## 3.2 整合層不成為第二個領域

FastAPI 可以執行的操作：

* 呼叫 Laravel API
* 組合多個 API 呼叫
* 映射請求 / 回應格式
* 傳遞 `Idempotency-Key`
* 處理整合層級錯誤
* 編排跨領域工作流程

FastAPI 不應執行的操作：

* 重新計算 Loyalty 業務規則
* 自行維護點數餘額
* 自行判斷優惠券資格
* 自行建立第二套冪等性狀態
* 假裝擁有 Laravel 資料庫交易（Database Transaction）

> 核心原則：整合層可以負責整合工作，但不能成為 Loyalty 領域的第二個真相來源。

---

# 4. 架構責任邊界

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

簡化責任對應：

```text
Router       → HTTP 契約
Client       → API 通訊
Workflow     → 跨領域流程編排
Laravel      → Loyalty 業務邏輯
Tests        → 回歸測試保護
```

---

# 5. 技術棧

## 整合層技術

* Python 3.13+
* FastAPI
* Uvicorn
* HTTPX
* Pydantic
* pytest
* pytest-asyncio
* python-dotenv

## 後端技術

* Laravel
* JWT 認證
* REST API

---

# 6. 專案結構

```text
loyalty-integration/
├── app/
│   ├── client/
│   │   ├── base.py
│   │   ├── customer.py
│   │   ├── point.py
│   │   ├── coupon.py
│   │   └── reward.py
│   ├── core/
│   │   └── dependencies.py
│   ├── routers/
│   │   ├── auth.py
│   │   ├── customers.py
│   │   ├── points.py
│   │   ├── coupons.py
│   │   ├── rewards.py
│   │   └── workflows.py
│   ├── workflows/
│   │   └── pos_checkout.py
│   ├── config.py
│   └── main.py
├── tests/
│   ├── __init__.py
│   ├── conftest.py
│   ├── unit/
│   │   └── test_client_auth.py
│   └── integration/
│       ├── test_reward_grants.py
│       └── test_point_transaction_create.py
├── scripts/
│   └── integration/
│       ├── explore_*.py
│       └── explore_valid_campaigns.py
├── list_all_routes.py
├── verify_routes.py
├── pytest.ini
├── requirements.txt
└── README.md
```

---

# 7. 核心元件說明

## 7.1 Client Layer（領域 Client）

`app/client` 負責封裝 Laravel API 通訊，架構為：

```text
LaravelClient
    ├── CustomerClient
    ├── PointClient
    ├── CouponClient
    └── RewardClient
```

### Base Client 責任

`LaravelClient` 集中處理共用的 Laravel API 整合議題，例如：

* HTTP 請求發送
* JWT 認證管理
* 認證狀態維護
* 請求逾時處理
* 通用 HTTP 錯誤處理
* `Idempotency-Key` 等共用請求處理

### Domain Client 責任

各領域 Client 負責特定領域的：

* Endpoint 映射
* 請求酬載處理
* 查詢參數處理
* 回應格式處理

範例：

```python
await point_client.create_transaction(
    customer_id=customer_id,
    transaction_type="earn",
    points=100,
)
```

內部 Python 使用語義化命名，但對外維持 Laravel API 契約不變：

```json
{
    "type": "earn",
    "points": 100
}
```

> 原則：內部命名可改善語義，但不應任意修改外部 API 契約。

---

## 7.2 Router Layer（API 路由器）

`app/routers` 負責 FastAPI HTTP 契約，主要責任：

1. 接收 HTTP 請求
2. 驗證請求資料
3. 呼叫領域 Client 或工作流程
4. 回傳 API 回應

處理流程：

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

Router 不應重新實作 Loyalty 業務邏輯。

---

## 7.3 Workflow Layer（工作流程編排）

`app/workflows` 負責跨領域 API 的流程編排，以 POS Checkout 為例：

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

工作流程的責任是**決定 API 操作的執行順序與整合結果**，但不負責：

* 點數計算邏輯
* 優惠券資格判斷
* 獎勵發放規則
* 任何 Loyalty 狀態管理

這些仍完全由 Laravel API 負責。

---

## 7.4 Application Factory

FastAPI 使用應用程式工廠模式：

```python
app = create_app()
```

目的是讓不同執行環境使用一致的應用程式初始化流程：

* Uvicorn 生產 / 開發環境
* TestClient 測試環境
* pytest 測試框架
* 路由驗證工具

路由器註冊集中於應用程式建立流程，避免不同啟動方式產生不一致的路由狀態。

---

# 8. API 領域清單

## 8.1 身份驗證（Authentication）

```text
POST /auth/login
GET  /auth/me
POST /auth/refresh
POST /auth/logout
```

## 8.2 會員管理（Customers）

```text
GET /customers
GET /customers/{customer_id}
GET /customers/{customer_id}/membership
POST /customers/identify
GET /customers/{customer_id}/qr-code
```

## 8.3 點數管理（Points）

```text
GET  /customers/{customer_id}/points
GET  /customers/{customer_id}/point-transactions
POST /customers/{customer_id}/point-transactions
GET  /customers/{customer_id}/point-transactions/expiring
GET  /customers/{customer_id}/point-transactions/{transaction_id}
POST /points/earn
POST /points/redeem
```

交易查詢範例：

```text
GET /customers/{customer_id}/point-transactions?type=earn

GET /customers/{customer_id}/point-transactions?type=redeem
```

## 8.4 優惠券管理（Coupons）

```text
GET  /customers/{customer_id}/coupons
GET  /customers/{customer_id}/coupons/{user_coupon_id}
GET  /customers/{customer_id}/coupon-redemptions
POST /coupons/claim
POST /customers/{customer_id}/coupons/claim
POST /coupons/redeem
```

## 8.5 獎勵管理（Rewards）

```text
GET  /customers/{customer_id}/reward-grants
POST /customers/{customer_id}/rewards/grant
```

## 8.6 工作流程（Workflows）

```text
POST /workflows/pos-checkout
POST /payments/mixed
```

工作流程端點用於將多個 Loyalty API 操作組合成完整業務流程。

## 8.7 健康檢查（Health）

```text
GET /health
```

---

# 9. 冪等性（Idempotency）

涉及可能重複執行的變更請求（Mutation Request），可透過以下標頭傳遞唯一請求鍵：

```http
Idempotency-Key: order-20260924-001
```

整合層的責任僅為：

```text
接收 Key
    ↓
轉發 Key
    ↓
由 Laravel 處理冪等性
```

不會自行建立冪等性狀態。

如果呼叫端提供穩定的 `Idempotency-Key`，整合層會將其轉發給 Laravel，讓 Laravel 在重試時識別相同的變更操作。

若呼叫端未提供 Key，整合層只會為當次請求自動產生一個 Key：

```text
第一次請求     → generated-key-A
稍後重試請求   → generated-key-B
```

自動產生的 Key 不會跨請求持久化，因此只能保護當次請求，無法提供跨重試的端對端冪等性（End-to-End Idempotency）。

需要安全重試時，呼叫端必須提供穩定的 Key。

## 目前冪等性限制

目前架構支援**單一變更操作的冪等性傳遞與處理**，但 POS Checkout 工作流程本身不提供**端對端冪等性**。

工作流程中的每個變更步驟可能使用不同的 `Idempotency-Key`。

`order_reference` 是業務追蹤編號；`Idempotency-Key` 是重複變更防護機制，兩者責任不同，不可互相取代。

## 冪等性架構圖

```text
External System

      │
      │ Idempotency-Key
      ▼

FastAPI

      │
      │ 完整轉發（Forward unchanged）
      ▼

Laravel API

      │
      ▼

Idempotency Handling
```

---

# 10. 為什麼冪等性狀態放在 Laravel？

如果 FastAPI 與 Laravel 各自維護冪等性狀態：

```text
FastAPI Idempotency State

          +

Laravel Idempotency State
```

可能產生狀態不一致的問題：

```text
FastAPI → 此請求已處理過

Laravel → 此請求是新的
```

因此冪等性的權威狀態必須保留在 Laravel，FastAPI 只負責：

* 接收請求中的 Key
* 正確轉發 Key
* 正確處理 Laravel 回應

這符合原則：

> `State ownership should remain with the system that owns the business mutation.`

---

# 11. 錯誤處理

`LaravelClient` 統一處理 Laravel API 通訊場景：

* 認證失敗
* HTTP 錯誤回應
* 請求逾時
* 連線失敗
* 無效回應格式
* 缺少認證 Token

HTTP 狀態碼解讀遵循 Laravel API 契約：

```text
2xx → 操作成功
4xx → 客戶端 / 請求 / 業務驗證錯誤
5xx → 伺服器端錯誤
```

領域 Client 不應將業務失敗視為成功，例如：

```text
Laravel API
     │
     │ 回傳 422
     ▼
Domain Client
     │
     ▼
回傳業務失敗
     │
     ▼
Workflow 不得回報成功
```

---

# 12. 逾時與連線失敗處理

必須區分各種失敗類型：

```text
HTTP 4xx 錯誤

HTTP 5xx 錯誤

Timeout 逾時

Connection Failure 連線失敗

Invalid Response 無效回應

Authentication Failure 認證失敗
```

尤其對於變更請求（Mutation Request），`Timeout` 不代表 Laravel 一定沒有執行成功，可能存在以下場景：

```text
FastAPI

   │
   │ 送出請求
   ▼

Laravel

   │
   ├── 操作已完成
   │
   └── 回應遺失
   │
   X

FastAPI 觸發逾時
```

因此不能簡單地在發生錯誤時就重試：

```python
# 不安全的做法
if error:
    retry()
```

變更操作的重試必須先考慮冪等性機制。

---

# 13. 失敗處理與一致性

跨系統工作流程最重要的問題不是「API 能不能呼叫」，而是：

> **當工作流程中間失敗時，誰負責一致性？**

以 POS Checkout 為例，工作流程步驟：

```text
1. 驗證會員身份
2. 累積點數
3. 兌換優惠券
```

假設執行結果：

```text
Validate Customer → Success

Earn Points       → Success

Redeem Coupon     → Failure
```

FastAPI 不會假裝自己可以安全地 Rollback 前面已經在 Laravel 執行成功的操作。

目前的處理策略：

1. 回傳明確的工作流程失敗
2. 不在 FastAPI 建立第二套交易系統
3. 不維護第二套 Loyalty 狀態
4. 依賴 Laravel 冪等性保護單一步驟的重複變更；目前工作流程本身不保證端對端冪等性
5. 如果業務要求真正的原子操作（Atomic Operation），應優先由 Laravel 提供複合式 API

## 部分失敗場景

```text
Earn Points   → Success

Redeem Coupon → Failure
               ↓
          工作流程失敗
```

此時累積點數的操作可能已經在 Laravel 生效。

工作流程不會假裝 Rollback、不自行補償，呼叫端也不能假設工作流程失敗代表所有先前的變更操作都沒有發生。

> 關鍵概念：**工作流程失敗 ≠ 所有先前的變更操作都會自動 Rollback。**

---

# 14. 工作流程層級冪等性現況

目前 POS Checkout 工作流程不提供端對端冪等性。

每個變更步驟的冪等性由 Laravel Loyalty API 負責，因此需要區分：

* **單一操作冪等性**：由 Laravel 處理
* **工作流程級冪等性**：目前不保證

如果呼叫端重新執行整個工作流程，由於各步驟可能產生新的 `Idempotency-Key`，先前已成功的步驟可能再次執行。

目前工作流程不自行實作：

* Rollback 機制
* 補償交易（Compensation）
* 工作流程冪等性儲存區
* 分散式交易

如果未來業務要求整個 Checkout 具備端對端冪等性，可以由呼叫端提供穩定的工作流程冪等性 Key，讓各變更步驟使用可重現的衍生 Key。

如果需要真正的原子化 Checkout，則應由 Laravel 提供複合式 Checkout API，讓完整流程在 Loyalty 領域自己的交易邊界內完成。

---

# 15. 工作流程失敗策略

目前工作流程採取的策略：

```text
編排流程
    ↓
偵測失敗
    ↓
回傳明確失敗
```

而不是：

```text
編排流程
    ↓
發生失敗
    ↓
假裝 Rollback
    ↓
假設一致性
```

這代表單一步驟的重複請求可以依賴 Laravel 的冪等性處理，但整筆工作流程重試不保證不會重複執行先前已成功的步驟。

---

# 16. 重要架構決策

| 領域 | 決策 |
| ------------- | ------------------- |
| 領域擁有者 | Laravel Loyalty API |
| 整合層實作 | FastAPI |
| 業務邏輯擁有者 | Laravel |
| 狀態擁有者 | Laravel |
| 冪等性狀態擁有者 | Laravel |
| 工作流程模式 | 流程編排（Orchestration） |
| Repository 模式 | 未使用 |
| 重複領域服務 | 避免實作 |
| 抽象工廠模式 | 延後實作 |
| Saga 模式 | 延後實作 |
| 分散式交易 | 未使用 |
| 契約驗證機制 | `verify_routes.py` |
| 測試策略 | 單元測試 + 整合測試 |

本專案優先保持責任清晰與單一真相來源，而非提前導入不必要的抽象層。

---

# 17. 刻意做出的設計取捨

## 17.1 不使用 Repository Layer

目前主要的資料來源只有 Laravel API，因此：

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

會增加不必要的間接層，但無法解決實際問題。

只有在未來出現多個後端提供者、多個資料來源時，才考慮導入 Repository 或其他適合的抽象。

## 17.2 不建立重複的領域服務

不在 FastAPI 重寫任何 Loyalty 領域規則：

* 點數規則
* 餘額計算規則
* 優惠券規則
* 獎勵規則
* 冪等性規則

避免形成兩套可能逐漸分歧的領域邏輯：

```text
Laravel Business Rules

        +

FastAPI Business Rules
```

## 17.3 不使用抽象工廠模式

目前每個領域只有一種 Client 實作，既有的 `PointClient`、`CouponClient`、`RewardClient` 已經足夠。

在沒有實際需求前，不建立多餘的介面、工廠、抽象工廠或提供者註冊表。

## 17.4 不在 FastAPI 建立冪等性儲存區

冪等性狀態屬於 Laravel 的變更狀態，因此保持由 Laravel 管理，整合層不重複儲存。

## 17.5 不提前導入 Saga 模式

目前工作流程的複雜度尚未需要分散式補償機制，因此不提前加入：

* Saga 框架
* 工作流程持久化
* 補償引擎
* 分散式交易框架

這些能力應由實際的業務需求與系統複雜度驅動。

---

# 18. 架構能力邊界：何時目前架構會不足？

目前架構適用於：

```text
External System
      ↓
FastAPI Integration Layer
      ↓
Laravel Loyalty API
```

但當需求演進時，需要重新評估架構。

## 18.1 多後端提供者場景

如果需要整合多個 Loyalty 提供者：

```text
FastAPI

 ├── Laravel Loyalty
 ├── Another Loyalty Provider
 └── External Coupon Provider
```

此時才需要導入：

* 提供者介面
* Adapter
* Factory
* Provider Registry

## 18.2 長時間執行的工作流程

如果工作流程變得複雜且可能持續數秒或數分鐘：

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

可能需要加入：

* Queue
* Async Job
* 持久化工作流程狀態
* Event
* Compensation
* Saga 風格的流程編排

## 18.3 高流量整合場景

當整合層成為大量流量的中央閘道時，才考慮加入：

* 流量限制（Rate Limiting）
* 重試策略（Retry Policy）
* 斷路器（Circuit Breaker）
* 指標收集（Metrics）
* 分散式追蹤（Distributed Tracing）
* 集中式日誌（Centralized Logging）

這些能力不在目前 demo 階段預先加入。

---

# 19. 程式碼規範

## 19.1 領域 Client 規範

Domain Client 只負責對應 Laravel API：

```python
await point_client.create_transaction(
    customer_id=customer_id,
    transaction_type="earn",
    points=100,
)
```

內部映射保持 API 契約不變：

```python
{
    "type": transaction_type,
    "points": points,
}
```

原則：Python 內部命名保持語義清楚，但 Laravel API 契約維持不變，不因 Python 慣例任意修改外部契約。

---

## 19.2 Router 規範

Router 的處理流程：

```text
Request
  ↓
Validation
  ↓
Client / Workflow
  ↓
Response
```

不要在 Router 中重新實作 Loyalty 業務邏輯。

---

## 19.3 Workflow 規範

工作流程的處理流程：

```text
Router
  ↓
Workflow
  ↓
Domain Clients
  ↓
Laravel API
```

工作流程只負責流程編排，不負責 Loyalty 領域規則。

---

# 20. API 契約原則

本專案與 Laravel Loyalty API 之間存在明確的契約。

任何以下修改：

* Endpoint
* HTTP Method
* Query Parameter
* Request Body
* Response Structure
* Authentication 行為
* Error Handling

都應同步確認整個鏈路的一致性：

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

避免只修改單一層造成整合回歸（Integration Regression）。

---

# 21. 測試策略

測試分為兩大類：

```text
tests/

├── unit/
└── integration/
```

## 21.1 單元測試（Unit Tests）

不需要連接實際的 Laravel API，適合測試：

* Client 認證行為
* 請求映射邏輯
* 本地應用程式邏輯
* 錯誤處理邏輯

執行指令：

```bash
python -m pytest -q -m "not integration"
```

## 21.2 整合測試（Integration Tests）

需要實際可用的 Laravel API。

正式 pytest 目前涵蓋：

* Point API
* Point Transaction
* Idempotency
* Reward Grant
* 驗證邏輯
* 會員查詢 Fixture

`scripts/integration/explore_*.py` 是開發用的探索腳本，不屬於正式 pytest suite，也不納入 CI 的 pass/fail 結果。

執行整合測試：

```bash
python -m pytest -q -m integration
```

指定特定測試檔案：

```bash
python -m pytest tests/integration/test_reward_grants.py -q -m integration
```

指定測試函數：

```bash
python -m pytest tests/integration/test_reward_grants.py::test_list_reward_grants_returns_response -q -m integration
```

## 21.3 測試覆蓋缺口

目前尚未納入正式 pytest coverage 的項目包括：

* Authentication API
* Coupon API
* POS Checkout
* Mixed Payment
* Customer API 行為

已知的測試缺口：

* POS Checkout 部分失敗場景：尚未有穩定資料建立「累積點數成功、兌換優惠券失敗」的情境
* Reward Mutation：需要尚未領取指定 reward 的會員 Fixture；目前 demo 環境的 reward 可能已全部發放，因此相關變更測試會跳過
* 不同 Idempotency-Key 的 Reward 測試：需要兩組可發放的會員 / 獎勵 Fixture
* Tenant 隔離測試：需要兩組 tenant 憑證與契約定義的 403 / 404 測試資料

---

# 22. 路由契約驗證

`verify_routes.py` 用於驗證 FastAPI 最終註冊的 OpenAPI 路由與 HTTP 方法。

執行：

```bash
python verify_routes.py
```

驗證內容：

1. 建立完整的 FastAPI 應用程式
2. 讀取 OpenAPI 路由定義
3. 列出目前所有端點
4. 驗證核心 API 路徑是否存在
5. 驗證 HTTP 方法是否正確
6. 發現契約回歸時以非零結束代碼退出

## 提交前品質閘門

所有修改在提交前至少應通過下列驗證：

```bash
# 語法編譯檢查
python -m compileall -q app tests

# 執行單元測試
python -m pytest -q -m "not integration"

# 驗證路由契約一致性
python verify_routes.py

# 執行整合測試
python -m pytest -q -m integration

# 檢查提交格式錯誤
git diff --check
```

`verify_routes.py` 的特性：

* 不啟動應用程式生命週期
* 不呼叫 Laravel API
* 不需要 Laravel 憑證

---

# 23. 路由清單工具

`list_all_routes.py` 用於列出完整的路由清單。

與 `verify_routes.py` 不同，它會啟動 FastAPI 生命週期，因此適用於：

**完整應用程式啟動驗證**

兩者用途不同：

| 工具 | 用途 |
| -------------------- | ---------------------------- |
| `verify_routes.py` | OpenAPI 路由與 HTTP Method 契約驗證 |
| `list_all_routes.py` | 完整應用程式啟動與路由清單檢查 |

---

# 24. 環境設定

建立 `.env` 檔案：

```env
LARAVEL_API_BASE_URL=http://127.0.0.1:8088/api/v1

LARAVEL_EMAIL=admin@example.com
LARAVEL_PASSWORD=password

DEFAULT_TIMEOUT=30
```

實際環境請依 Laravel API 設定調整。

不要將實際的 `.env` 或憑證提交至 Git。

---

# 25. 安裝步驟

建立虛擬環境：

```bash
python -m venv venv
```

Windows 啟動虛擬環境：

```bash
venv\Scripts\activate
```

Linux / macOS 啟動虛擬環境：

```bash
source venv/bin/activate
```

安裝相依套件：

```bash
pip install -r requirements.txt
```

---

# 26. 啟動應用程式

```bash
uvicorn app.main:app --reload
```

預設位址：

```text
http://127.0.0.1:8000
```

Swagger UI：

```text
http://127.0.0.1:8000/docs
```

健康檢查端點：

```text
GET /health
```

---

# 27. CI 驗證

GitHub Actions 工作流程位於：

```text
.github/workflows/ci.yml
```

在以下情況執行：

* Push 到 `main` 分支
* Push 到 `develop` 分支
* Pull Request 目標為 `main`
* Pull Request 目標為 `develop`

CI 不需要：

* Laravel API URL
* Laravel 憑證
* GitHub Secrets

CI 主要驗證整合應用程式本身：

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

# 28. 開發驗證流程

修改應用程式程式碼後，建議依序執行：

```bash
python -m compileall -q app tests

python -m pytest -q -m "not integration"

python verify_routes.py

git diff --check
```

| 檢查項目 | 目的 |
| ------------------ | ------------- |
| `compileall` | Python 語法驗證 |
| `pytest` | 自動化回歸測試 |
| `verify_routes.py` | API 路由契約驗證 |
| `git diff --check` | 修補檔與空白字元完整性檢查 |

---

# 29. 整合環境設定

整合測試使用 `tests/conftest.py` 提供 Laravel API Fixture，並使用 `@pytest.mark.integration` 標記。

本機啟動 Laravel API 後，請在 `.env` 中設定：

```env
LARAVEL_API_BASE_URL=
LARAVEL_EMAIL=
LARAVEL_PASSWORD=
```

使用 Coffee Tenant 的測試另外需要設定：

```env
LARAVEL_COFFEE_EMAIL=
LARAVEL_COFFEE_PASSWORD=
LARAVEL_COFFEE_CAMPAIGN_REWARD_ID=1
```

`LARAVEL_COFFEE_CAMPAIGN_REWARD_ID` 為選擇性設定，預設值為 `1`。

---

# 30. 驗證狀態與限制

## 30.1 最近一次驗證結果

```text
✅ compileall：PASS

✅ Unit Tests：2 passed

✅ Route Contract Verification：28 routes verified

✅ Integration Tests：7 passed, 3 skipped
```

上述結果代表目前已完成的驗證狀態，不代表所有 API 領域或所有工作流程情境都已完整覆蓋。

## 30.2 驗證流程

完整驗證：

```bash
python -m compileall -q app tests

python -m pytest -q -m "not integration"

python verify_routes.py

python -m pytest -q -m integration

git diff --check
```

上述驗證可以確認：

* Python 原始碼可以正常編譯
* 本地測試套件可以執行
* FastAPI 應用程式可以正常建立
* API 路由正確註冊
* 核心 API 契約存在
* Git 修補檔沒有空白字元錯誤

整合測試則需要額外可用的 Laravel Loyalty API。

## 30.3 SKIPPED 的意義

`SKIPPED` 主要代表目前 demo 環境缺少特定測試資料或 Fixture。

例如：

* 指定 reward 已經發放
* 缺少特定 tenant 測試帳號
* 缺少可重現的部分失敗資料

因此：

> **SKIPPED 不等於測試失敗，也不等於該功能已被完整驗證。**

---

# 31. 設計原則

## 31.1 保持責任清晰

```text
Router       → HTTP 契約

Client       → API 通訊

Workflow     → 跨領域流程編排

Laravel      → Loyalty 業務邏輯

Tests        → 回歸測試保護
```

## 31.2 保持一致性

相同類型的元件：

* 領域 Client
* Router
* Workflow
* 測試案例

應採用一致的命名與結構。

## 31.3 避免不必要的抽象

不要因為「未來可能會需要」就提前建立抽象，應遵循：

> **先解決實際的變化，再抽象實際存在的變化。**

## 31.4 維持單一真相來源

```text
Loyalty 業務規則      → Laravel

Loyalty 狀態          → Laravel

冪等性狀態            → Laravel

整合流程編排          → FastAPI
```

## 31.5 讓變更可驗證

任何 API 行為變更都應同步確認：

```text
實作程式碼
      ↓
測試案例
      ↓
路由契約
      ↓
文件
```

---

# 32. 開發理念

這個專案不以「增加更多抽象」作為工程品質的目標。

核心目標是：

> **讓下一個維護這個專案的人，可以快速理解每一層負責什麼、為什麼這樣設計，以及修改後應該如何驗證。**

因此優先考量：

* 清楚的命名
* 一致的結構
* 明確的責任邊界
* 穩定的 API 契約
* 可重現的測試
* 清楚的失敗邊界
* 與程式碼同步的文件
* 由實際需求驅動的抽象

而不是：

* 為了架構而架構（Architecture for Architecture's Sake）
* 過早抽象（Premature Abstraction）
* 重複的業務邏輯
* 不必要的基礎設施

---

# 33. 架構總結

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
                 │ Reward Domain           │
                 │                         │
                 │ Business Rules          │
                 │ Idempotency             │
                 │ Persistence             │
                 └─────────────────────────┘
```

整個架構可以濃縮成兩句話：

> **FastAPI 負責整合（Integration）。**

> **Laravel 負責 Loyalty 領域（Loyalty Domain）。**

FastAPI 可以：

* 呼叫 API
* 組合 API
* 映射 API 契約
* 傳遞 `Idempotency-Key`
* 統一整合錯誤處理
* 編排跨領域工作流程

但不應：

* 複製 Loyalty 業務規則
* 建立第二套 Loyalty 狀態
* 假裝擁有 Laravel 資料庫交易
* 為了預期中的未來需求建立大量抽象

當需求真正跨越目前架構的能力邊界，再引入：

* 提供者架構
* Adapter
* Factory
* Queue
* 持久化工作流程
* 補償交易
* Saga 模式
* 彈性性基礎設施

如此可以保持：

> **簡單的地方保持簡單；真正複雜的地方才引入複雜度。**

這也是本專案最核心的 Engineering Philosophy。