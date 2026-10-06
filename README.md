# Loyalty Integration - Laravel 會員積分平台整合層

一個專為 Laravel Loyalty API 建置的輕量級整合層，負責統一處理外部系統與多租戶會員積分平台的 API 通訊、認證、工作流程編排與即時事件轉發。**FastAPI 不持久化任何 Loyalty 領域狀態（Customer、Point、Coupon、Reward 等），僅維持運行時的連線狀態、token 狀態與應用程式狀態，負責整合流程的執行。**

---

## 這是什麼？

這是一個 FastAPI 實作的整合中間層，串接 POS 系統、電商平台、CRM 等外部系統與核心的 Laravel 會員積分平台。它解決了跨系統整合中的常見痛點：
- 統一的認證與 token 管理，前端不需要直接處理 Laravel 的 JWT
- 標準化的 API 契約，外部系統只需要面對一套統一的介面
- 內建的工作流程編排，將複雜的跨領域操作（如 POS 結帳）包裝成單一呼叫
- 即時事件轉發，將 Laravel 廣播的狀態變更即時推給前端 WebSocket 連線
- 成熟的失敗處理機制，避免因網路不穩定造成的重複交易

---

## 為什麼存在？

### 問題
Laravel 做為 Loyalty 領域的唯一狀態擁有者，直接對外暴露 API 會面臨幾個挑戰：
- 多個外部系統需要重複實作相同的認證、錯誤處理邏輯
- 複雜的跨資源工作流程（POS 結帳需要驗證會員、累積點數、兌換優惠券）重複在各端實作
- 無法統一監控所有對 Loyalty API 的呼叫
- 前端直接連接 Laravel 的 WebSocket 服務在某些網路環境下有困難

### 解決方案
本整合層做為唯一的對外閘道，承擔了這些重複性工作，讓各外部系統能以更簡單的方式使用 Loyalty 平台的能力，同時讓 Laravel 專注於它最擅長的領域業務處理。

---

## Laravel / FastAPI 分工

| 責任 | Laravel Loyalty API | FastAPI Integration Layer |
|------|-------------------|--------------------------|
| Loyalty 狀態擁有 | ✅ 唯一擁有者 | ❌ 從不持久化任何 Loyalty 領域狀態 |
| 業務規則實作 | ✅ 點數計算、資格驗證 | ❌ 不實作任何領域邏輯 |
| 冪等性保證 | ✅ 所有修改操作的冪等性由 Laravel 保證 | ✅ 僅負責轉發 Idempotency-Key |
| 認證處理 | ✅ 核發與驗證 JWT | ✅ 自動管理 token 生命週期、刷新 |
| API 閘道 | ❌ 不直接對外提供服務 | ✅ 唯一的外部存取入口 |
| 工作流程編排 | ❌ 僅提供原子級 API | ✅ 編排跨領域的複雜流程 |
| 即時事件轉發 | ✅ 透過 Reverb 廣播事件 | ✅ 轉發給前端 WebSocket 連線 |

**核心聲明：Laravel owns Loyalty state. FastAPI does not recreate the Loyalty domain. FastAPI orchestrates integration workflows.**

---

## Architecture Overview

```text
External Systems
      │
      ▼
┌─────────────────────────────┐
│ FastAPI Integration Layer   │
│                             │
│ ├─ JWT Lifecycle Management │
│ ├─ Exponential Backoff Retry│
│ ├─ POS Checkout Orchestration│
│ ├─ Multi-Tenant Context     │
│ ├─ Idempotency Forwarding    │
│ ├─ Error Translation        │
│ └─ Reverb Event Gateway     │
└──────────────┬──────────────┘
               │
               ▼
┌─────────────────────────────┐
│ Laravel Loyalty Platform    │
│                             │
│ ├─ Loyalty Domain Logic     │
│ ├─ Point Transaction State  │
│ ├─ Database Transaction    │
│ ├─ Idempotency Guarantees   │
│ └─ Domain Event Broadcasting│
└─────────────────────────────┘
```

10秒速覽：FastAPI 做為唯一的對外整合閘道，承載所有跨系統通訊的複雜性；Laravel 做為 Loyalty 領域的唯一狀態擁有者，專注於業務規則的實作。

完整的架構設計與責任邊界說明，請參考：
[Architecture Guide](docs/architecture.md)

---

## Engineering Features

本整合層採用 production-oriented integration patterns，針對認證、重試、冪等性、timeout、multi-tenant context 與 realtime integration 等問題進行設計與驗證，解決真實世界的整合痛點：

### JWT Lifecycle Management
- **問題**：多個並發請求同時遇到 token 過期時，會產生多餘的刷新請求，甚至刷新令牌競爭
- **解決方案**：Single Flight Pattern + 預先刷新機制，使用 asyncio.Lock 確保同一時間只有一個協程刷新 token，並在過期前30秒主動刷新
- 實作細節：JWT 過期時間解析、雙重檢查鎖避免重複刷新、401 自動恢復機制

### Idempotency-Aware Retry Policy
- **問題**：盲目重試修改操作可能導致重複交易，比如重複扣除點數
- **解決方案**：只有當修改操作（POST/PUT/PATCH/DELETE）攜帶有效 Idempotency-Key 時才允許重試，讀取操作可安全重試
- 實作細節：指數退避（2s→4s→8s，最大10秒）、最多3次重試、僅重試暫時性網路例外

### Shared HTTP Connection Pool
- **問題**：每個請求建立新的 TCP 連線會造成資源浪費，延遲累積
- **解決方案**：使用 HTTPX 的連接池复用機制，維護長連線，降低 TLS 握手開銷
- 實作細節：全域共享 AsyncClient 實例、連線限制配置、自動資源管理

### Multi-Tenant Header Propagation
- **問題**：多租戶架構下，租戶識別必須貫穿整個請求鏈，避免資料混淆
- **解決方案**：X-Tenant-ID 自動附加到所有 Laravel API 請求，租戶上下文在整合層邊界明確傳遞
- **實作細節**：LaravelClient 層級的 tenant_id 設定、所有 HTTP API 請求自動帶入 header、WebSocket 訂閱支援選用性的租戶參數（非強制隔離）

### Workflow Orchestration
- **問題**：外部系統需要呼叫多個 Laravel API 才能完成一個商業流程（如 POS 結帳）
- **解決方案**：將複雜的跨資源操作編排成單一 API 呼叫，簡化外部系統集成
- 實作細節：POS Checkout 流程自動化、工作流程失敗時記錄完整上下文、步驟執行順序保證

### Reverb Event Gateway
- **問題**：前端直接連接 Laravel Reverb 在某些網路環境下有困難，需要統一的事件轉發
- **解決方案**：接收 Laravel Reverb 廣播的域事件，驗證後轉發給對應的前端 WebSocket 客戶端
- 實作細節：頻道授權機制、前端連線管理、事件路由與轉發、斷線重連機制

### Error Translation
- **問題**：Laravel API 的錯誤格式不一致，外部系統需要處理多種錯誤表示方式
- **解決方案**：統一翻譯 Laravel 的 4xx/5xx 錯誤為標準化的例外格式，包含上下文資訊
- 實作細鍵：狀態碼映射、錯誤訊息標準化、額外上下文日誌記錄

---

## Engineering Highlights

- **Explicit domain ownership**：嚴格劃分狀態所有權，Laravel 是 Loyalty 狀態的唯一權威來源
- **Clear integration boundary**：FastAPI 從不複製或持久化任何 Loyalty 領域狀態，所有查詢即時請求 Laravel
- **Tenant context propagation**：X-Tenant-ID 貫穿所有 HTTP API 請求鏈，WebSocket 訂閱支援選用性的租戶參數
- **Idempotency-aware retry**：修改操作的重試必須滿足冪等性條件，從根源避免重複交易
- **Explicit timeout semantics**：區分不同類型的超時錯誤，讀取超時與伺服器失敗有完全不同的處理邏輯
- **Partial failure logging**：工作流程中途失敗時，記錄已完成步驟的完整上下文，方便後續除錯與狀態恢復
- **JWT lifecycle management**：Single Flight Pattern 解決並發刷新的競爭條件，預先刷新避免中斷請求
- **Realtime event forwarding**：統一的 WebSocket 閘道，抽象 Laravel Reverb 的連線複雜性
- **Contract-oriented testing**：從單元測試到整合測試，持續驗證 API 契約的一致性
- **Concurrency safety validation**：專門的並發測試驗證 token 刷新、多租戶隔離的協程安全性，避免競爭條件

---

## Failure Model

本系統從一開始就設計處理失敗場景，而非僅處理快樂路徑。核心失敗概念：

- **Timeout ≠ Server Failure**：Client Timeout 表示用戶端未在期限內收到完整回應，但不能單獨判定 Laravel 端的操作是否成功
- **Read Timeout ≠ Operation Did Not Happen**：讀取超時本身不會造成重複交易風險，但修改操作的超時必須謹慎處理，需先查詢 Laravel 狀態再決定是否重送
- **Workflow Failure ≠ Automatic Rollback**：工作流程失敗不會自動回滾，Laravel 是狀態的唯一擁有者
- **Retry Requires Idempotency Semantics**：任何修改操作的重試都必須有有效的 Idempotency-Key
- **Realtime Failure ≠ Domain Transaction Failure**：WebSocket 事件轉發失敗不代表領域事務失敗，兩者是分離的

完整的失敗處理手冊、維運流程、事件調查指引，請參考：
[Operations & Failure Playbook](docs/operations.md)



## 測試策略

本專案的測試分為五層，從單元測試到完整的 Laravel 整合測試，確保所有跨系統互動的正確性：

```text
Unit Tests
    ↓
Client / Contract Tests
    ↓
Laravel Integration Tests
    ↓
Concurrency Tests
    ↓
Realtime Integration Tests
```

測試重點不是單純追求 coverage，而是驗證 integration contract、failure semantics、tenant isolation、idempotency 與 concurrency behavior。完整的測試場景、缺口與規劃中的測試：
[Testing Strategy](docs/testing-strategy.md)

---

## 目前的核心限制

本服務刻意不實作許多企業系統常見的複雜功能，並非技術上做不到，而是出於責任邊界的考量：

### 不提供分散式交易（Distributed Transaction）
Loyalty 狀態的唯一權威來源是 Laravel。若需要原子性的複合操作，應由 Laravel 提供內建交易支援的 API，而不是由整合層實作分散式交易。

### 不提供自動 Rollback 或 Saga 模式
目前沒有足以 justify distributed compensation 的業務需求，因此刻意不引入 Saga 模式。任何需要原子性的複合操作，都應該在 Laravel 領域內部透過資料庫交易實作，整合層不應試圖修復已寫入 Laravel 的狀態。

### 不維護第二套 Loyalty State
刻意避免出現「FastAPI 顯示的餘額與 Laravel 不一致」的狀況。所有 Loyalty 領域查詢都即時呼叫 Laravel API，本服務從不持久化或快取任何會員領域狀態。

### 不實作過多的企業級基礎設施
Circuit Breaker、Metrics、Tracing、Queue 等功能，只有當實際的業務規模與流量需要時才會加入。目前階段保持簡單，避免引入不必要的複雜度。

---

## 未來演進方向

### Near-term (當前迭代優先)
- 完善 POS Checkout 的自動化測試覆蓋
- 加入 Request ID 追蹤，提升可觀測性
- 優化整合測試的執行速度

### 如果業務規模增長
- 若實際流量與錯誤率需要，引入基礎的 Circuit Breaker 機制
- 加入 Prometheus Metrics，支援生產環境監控告警
- 如果出現長時間執行的工作流程需求，實作非同步的工作流程持久化

### 如果分散式副作用出現
- 只有當實際出現分散式交易的強烈業務需求時，才考慮引入 Saga 模式
- 根據流量規模決定是否需要更複雜的流量控制與排程機制

---

## 快速上手

### 環境需求
- Python 3.11+
- 執行中的 Laravel Loyalty API（預設位置：http://localhost:8088）
- Laravel Reverb WebSocket 服務（可選，用於即時事件）

### 安裝與啟動
```bash
# 複製環境變數範本
cp .env.example .env
# 編輯 .env 填入 Laravel API 憑證與 Reverb 設定

# 建立虛擬環境並安裝依賴
python -m venv .venv
# Windows 啟用: .venv\Scripts\activate
# Linux/macOS 啟用: source .venv/bin/activate
pip install -e ".[dev]"

# 啟動 FastAPI 服務
uvicorn src.main:create_app --factory --reload --host 0.0.0.0 --port 8000
```

服務啟動後可訪問：
- API 文件：http://localhost:8000/docs
- ReDoc：http://localhost:8000/redoc
- 健康檢查：http://localhost:8000/health

---

## 開發與驗證指令

```bash
# 程式碼檢查與格式化
ruff check src/ tests/
ruff format src/ tests/

# 型別檢查
mypy .

# 執行單元測試（不需 Laravel）
pytest tests/unit/ -v

# 執行整合測試（需要啟動 Laravel API）
pytest tests/integration/ -v -m integration

# 驗證路由契約一致性
python verify_routes.py

# 列出所有已註冊的路由
python list_all_routes.py
```

### 提交前必須通過的檢查
```bash
# 語法編譯檢查
python -m compileall -q src tests

# 單元測試全部通過
python -m pytest -q -m "not integration"

# 路由契約驗證通過
python verify_routes.py
```

---

## 文件總覽

- [Architecture Guide](docs/architecture.md) - 深入的架構設計與責任邊界說明
- [Operations & Failure Playbook](docs/operations.md) - 生產環境維運手冊，包含所有失敗模式處理
- [Testing Strategy](docs/testing-strategy.md) - 完整的測試策略與驗證方法