# Testing Strategy

本專案的測試策略是為了確保整合層在與 Laravel API 互動時的可靠性與正確性。測試不僅是為了達成覆蓋率，更是為了防止會導致業務異常的回歸問題。

---

## 測試分層架構

```text
Unit Test（單元測試）
    ↓ 測試本機邏輯，Mock 所有外部依賴
Client Contract Test（客戶端契約測試）
    ↓ 驗證 Domain Client 的 API 契約一致性
Laravel Integration Test（Laravel 整合測試）
    ↓ 連接真實 Laravel API，測試端對端流程
Concurrency Test（並發測試）
    ↓ 驗證並行操作下的安全性
Reverb Integration Test（WebSocket 整合測試）
    ↓ 驗證即時事件轉發流程
```

### 測試堆疊
- **測試框架**：pytest
- **Mock 工具**：unittest.mock、pytest-mock
- **Async 測試**：pytest-asyncio
- **HTTP 模擬**：respx（用於 Unit Test 模擬 Laravel API）
- **型別檢查**：mypy
- **程式碼品質**：ruff

---

## 各層測試保護的場景

### 1. Unit Test（單元測試）
**執行時機**：每一次程式碼提交、CI 流程自動執行  
**是否需要 Laravel 執行**：不需要  
**測試對象**：所有本地業務邏輯、輸入驗證、錯誤處理

#### 驗證的場景
- Workflow 邏輯正確性：POS Checkout 的步驟執行順序
- 錯誤處理：各種 HTTP 狀態碼的例外映射是否正確
- 輸入驗證：FastAPI 模型的 Pydantic 驗證邏輯
- 參數映射：請求/回應的欄位轉換是否正確
- 依賴注入：FastAPI 的依賴解析是否正確

#### 測試原則
- 所有外部依賴（尤其是 LaravelClient）必須被 Mock
- 永遠不依賴外部服務狀態
- 測試隔離性，每個測試都是獨立的

---

### 2. Client Contract Test（客戶端契約測試）
**執行時機**：CI 流程、部署前驗證  
**是否需要 Laravel 執行**：不需要（使用 OpenAPI 規範驗證）  
**測試對象**：所有 Domain Client（PointClient、CustomerClient 等）

#### 驗證的場景
- API Endpoint 路徑是否符合 Laravel OpenAPI 規範
- HTTP Method 是否正確
- Query Parameters 是否符合 Laravel 預期
- Request Body 結構是否符合 Schema
- Response 結構解析是否正確
- 標頭附加邏輯（X-Tenant-ID、Authorization）是否正確

#### 工具支援
- `verify_routes.py`：自動驗證 FastAPI 註冊的所有路由
- OpenAPI Schema 比對：可與 Laravel 的 OpenAPI 文件自動比對

---

### 3. Laravel Integration Test（Laravel 整合測試）
**執行時機**：部署前、自動化整合測試流程  
**是否需要 Laravel 執行**：必須啟動並可存取  
**測試對象**：完整的端對端流程

#### 驗證的場景
- 認證流程：JWT 取得、刷新、過期處理是否正確
- 真實 API 呼叫：與實際 Laravel API 的通訊是否正常
- 多租戶隔離：不同 Tenant 的資料存取是否隔離
- 冪等性行為：相同 Idempotency-Key 不會重複執行
- 錯誤處理：Laravel 回傳的 4xx/5xx 錯誤是否正確轉換
- Workflow 完整流程：POS Checkout 從開始到結束的完整執行
- 跨領域操作：點數累積、優惠券兌換的連貫操作

#### 執行方式
```bash
pytest tests/integration/ -v -m integration
```

#### 測試資料準備
- 測試用的 Laravel 測試環境必須有隔離的測試資料庫
- 每個整合測試執行後必須清理測試資料，避免影響其他測試
- 使用 Laravel 的測試遷移與測試 seeder 建立乾淨的環境

---

### 4. Concurrency Test（並發測試）- 規劃中
**執行時機**：發布重大更新前、效能測試階段（規劃中）  
**是否需要 Laravel 執行**：必須  
**測試對象**：並行操作的安全性

#### 計畫驗證的場景
- 並發鎖機制：JWT 刷新時的並發安全是否正常
- 冪等性保證：多個相同請求同時送出是否只執行一次
- 點數併發：同一會員的多筆點數操作是否有競爭條件
- WebSocket 並發：多個前端同時訂閱事件是否正常

---

### 5. Reverb Integration Test（WebSocket 整合測試）- 部分實作
**執行時機**：部署前  
**是否需要 Laravel 執行**：必須，且 Reverb 服務需啟動  
**測試對象**：即時事件轉發流程

#### 已驗證的場景
- WebSocket 連線建立：與 Reverb 服務的連線是否正常
- 事件訂閱：正確訂閱對應的頻道
- 事件轉發：Laravel 廣播的事件是否正確轉發給前端
- 認證邏輯：WebSocket 連線的認證是否正確

#### 規劃驗證的場景
- 斷線重連：連線中斷後是否能自動重新連線（目前僅手動測試）

---

## 測試必須驗證的核心業務場景

### 認證與安全性
- [x] JWT token 過期自動刷新
- [x] 無效的認證資訊正確拋出 401
- [x] Tenant 標頭正確附加到所有請求
- [x] Idempotency-Key 正確傳遞給 Laravel

### 點數操作
- [x] 點數查詢返回正確的餘額
- [x] 點數累積操作成功寫入 Laravel
- [x] 點數兌換操作正確扣減餘額
- [x] 餘額不足時正確回傳業務錯誤

### 工作流程
- [x] POS Checkout 完整流程成功執行
- [x] 工作流程中途失敗時正確中斷
- [x] 部分失敗狀態正確回報給呼叫端
- [x] 輸入驗證失敗時阻止流程執行

### 錯誤處理
- [x] Laravel 422 驗證錯誤正確轉換
- [x] Laravel 500 錯誤符合條件時正確重試
- [x] 網路逾時依據判斷表決定是否重試
- [x] 無效的 JSON 回應正確處理與記錄

---

## 目前刻意 Skip 的測試場景與原因

有些場景目前自動化測試難以穩定實現，或在目前的流量規模下不需要自動化：

| 測試場景 | 狀態 | 原因 |
|---------|------|------|
| Reverb 斷線自動重連 | ⚠️ 手動測試為主 | WebSocket 斷線場景難以在自動化測試中穩定重現 |
| 極端並發衝突 | ⚠️ 手動壓測 | 需要大量並發用戶，僅在重大效能更新前手動驗證 |
| 完整的分散式失敗場景 | ⚠️ 手動測試 | 模擬各種網路分區、部分失敗的場景成本過高 |
| 長時間執行的記憶體洩漏 | ⚠️ 依賴監控 | 此類測試需要長時間執行，交給生產監控處理 |

---

## 目前的測試缺口與改進方向

### 測試覆蓋缺口
- [ ] POS Checkout 的部分失敗場景自動化測試不足
- [ ] 多租戶隔離的負面測試案例太少
- [ ] 各種失敗模式的自動化測試覆蓋不全
- [ ] JWT 刷新的並發鎖機制缺少專屬的並發測試
- [ ] Idempotency-Key 的重複送測試場景不完善

### 可觀測性缺口
- [ ] 測試覆蓋率報告尚未整合到 CI
- [ ] 整合測試的執行時間過長，需要優化
- [ ] 失敗測試的除錯資訊不足，需要更多的日誌輸出
- [ ] 缺乏性能基準測試，無法察覺效能回歸

---

## 提交前必須通過的檢查清單

任何程式碼提交前，必須在本機通過以下所有檢查：

```bash
# 1. 語法編譯檢查
python -m compileall -q src tests

# 2. 程式碼風格檢查
ruff check src/ tests/

# 3. 型別檢查
mypy .

# 4. 所有單元測試必須通過
python -m pytest -q -m "not integration"

# 5. 路由契約驗證必須通過
python verify_routes.py
```

### CI 流程自動執行的檢查
GitHub Actions 會自動執行：
- 程式碼風格與靜態分析
- 型別檢查
- 所有單元測試
- 路由契約驗證

整合測試僅在手動觸發或部署到測試環境時執行，避免過度依賴外部服務的可用性。

---

## 測試的工程哲學

> 測試不是為了證明程式碼「能運行」，而是為了讓修改者有信心「不會壞掉別人的東西」。

本專案的測試永遠專注在最容易出問題的地方：
- 跨系統邊界的 API 契約一致性
- 會導致金額/點數異常的業務邏輯
- 可能造成重複交易的失敗處理
- 破壞多租戶隔離的安全問題

與其寫一百個測試覆蓋不重要的程式碼，不如把精力放在保護那些一旦出錯就會造成業務損失的核心路徑。

---

## Planned Tests

以下是規劃中但尚未實作的自動化測試，按優先級排序：

### Token Refresh Race Test
→ 驗證多個 concurrent requests 同時遇到 expired token 時，不會產生不必要的 refresh race。
- 模擬100個並發請求同時觸發token刷新
- 驗證實際只執行一次refresh API呼叫
- 確保所有請求都獲得相同的新token
- 驗證雙重檢查鎖的有效性
- 目前狀態：規劃中，尚未實作自動化測試

### Retry Policy Enforcement Test
→ 驗證 retry 僅發生在允許 retry 的 failure conditions。
- 測試修改操作沒有Idempotency-Key時絕不重試
- 驗證非暫時性錯誤（如400、404）不會進入重試流程
- 確認指數退避延遲符合預期（2s→4s→8s）
- 驗證最大重試次數（3次）不會超過

### 401 Auto Recovery Test
→ 驗證 access token expiration 後的 recovery behavior。
- 模擬Laravel返回401未授權錯誤
- 驗證系統自動觸發token刷新
- 確保刷新後自動重試原請求
- 防止無限遞迴重試（僅重試一次401）

### Concurrent Token Refresh Test
→ 驗證高併發場景下token刷新機制的穩定性。
- 模擬500個並發請求同時需要刷新token
- 驗證沒有產生多餘的refresh API呼叫
- 確保所有請求都成功獲得有效token
- 監測記憶體與連接池使用情況

### Load Test Suite
→ 驗證 Integration Layer 在高併發 HTTP workload 下的行為。
- **100 concurrent requests**：基礎負載測試，驗證日常流量下的穩定性
- **500 concurrent requests**：峰值負載測試，驗證連接池的極限處理能力
- **1000 concurrent requests**：壓力測試，驗證極端流量下的降級行為

### Partial Failure Simulation Test
→ 自動化模擬工作流程中間步驟失敗的場景。
- POS Checkout流程中第二個步驟失敗
- 驗證部分成功狀態正確回報給呼叫端
- 確保沒有隱瞞已執行的步驟狀態
- 驗證錯誤訊息包含足夠的除錯資訊