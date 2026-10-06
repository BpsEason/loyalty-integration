# Operations & Failure Playbook

這是本整合層的生產維運手冊，詳述所有可能的失敗模式、處理流程、維運調查步驟，是處理生產事件的核心依據。

---

## Timeout / Retry / Idempotency 核心判斷

這是本整合層最重要的安全機制。**絕不盲目重試任何變更操作**。

### 重試判斷表

| 情境 | 是否可自動重試 | 原因 |
|------|-------------|------|
| GET + Connection Timeout | ✅ 可重試 | 查詢操作無副作用 |
| GET + Laravel 5xx | ✅ 可重試（最多3次） | 非變更操作，伺服器暫時故障 |
| GET + Laravel 4xx | ❌ 不可重試 | 客戶端錯誤，重試也不會成功 |
| POST/PUT/PATCH/DELETE + 有穩定 Idempotency-Key + Connection Timeout | ✅ 可重試 | Laravel 保證冪等，重試安全 |
| POST/PUT/PATCH/DELETE + 無 Idempotency-Key + Timeout | ❌ 絕對不可重試 | Laravel 可能已成功執行，重試會造成重複變更 |
| POST/PUT/PATCH/DELETE + 有 Idempotency-Key + Laravel 4xx | ❌ 不可重試 | 業務驗證失敗，重試無效 |
| POST/PUT/PATCH/DELETE + 有 Idempotency-Key + Laravel 5xx | ✅ 可重試（最多3次） | 指數退避策略，符合冪等性保證 |

### 現有重試實作限制
- 目前程式碼中僅實作了基礎的指數退避重試（初始2秒，最大10秒）
- 只有列在 `RETRYABLE_EXCEPTIONS` 中的網路例外才會觸發重試
- 修改操作必須提供 `Idempotency-Key` 才會進入重試邏輯
- 401 錯誤僅自動重試一次（刷新 token 後），避免無限循環

---

## 失敗模式處理手冊

本章節列出所有生產環境可能遇到的失敗情境，以及本服務的處理行為、維運人員應採取的動作。

---

### 1. Laravel API 回傳 4xx 錯誤
**發生場景**：參數錯誤、權限不足、業務規則驗證失敗（如餘額不足無法兌換）
- **FastAPI 行為**：立即中斷流程，包裝錯誤後回傳給呼叫端
- **是否可重試**：除非修正請求內容，否則不可重試
- **是否可能造成重複變更**：不可能，4xx 代表 Laravel 拒絕執行
- **狀態擁有者**：Laravel，所有變更操作均未生效
- **維運查詢位置**：FastAPI 日誌中的錯誤 payload、Laravel 的 HTTP 狀態碼
- **修復位置**：呼叫端的請求參數，或 Laravel 的權限設定

---

### 2. Laravel API 回傳 5xx 錯誤
**發生場景**：Laravel 伺服器內部錯誤、服務暫時無法處理
- **FastAPI 行為**：符合重試條件的請求會依指數退避重試，超過次數後回傳錯誤
- **是否可自動重試**：參考上方判斷表
- **是否可能造成重複變更**：若符合冪等性條件則不會
- **狀態擁有者**：Laravel，需查詢 Laravel 狀態才能確認操作是否執行
- **維運查詢位置**：Laravel 應用程式日誌、FastAPI 的重試次數日誌
- **修復位置**：Laravel 伺服器本身的問題

---

### 3. Connection Refused
**發生場景**：Laravel 服務未啟動、防火牆阻擋、網路中斷
- **FastAPI 行為**：立即拋出 502 錯誤，符合條件的請求進入重試
- **是否可自動重試**：僅 GET 或有 Idempotency-Key 的修改操作
- **是否可能造成重複變更**：不可能，連線未建立，請求未送達
- **狀態擁有者**：無，請求從未送達 Laravel
- **維運查詢位置**：網路連線測試、Laravel 服務狀態
- **修復位置**：Laravel 服務可用性、網路連通性

---

### 4. Connection Timeout
**發生場景**：TCP 三次握手超時、無法建立連線
- **FastAPI 行為**：同 Connection Refused
- **風險與處理**：與 Connection Refused 相同，請求未實際送達

---

### 5. Read Timeout
**發生場景**：連線已建立，但 Laravel 未在逾時時間內回應
- **FastAPI 行為**：拋出 504 錯誤，這是最危險的失敗模式
- **是否可自動重試**：嚴格遵循判斷表，無 Idempotency-Key 的修改操作絕不重試
- **是否可能造成重複變更**：高度可能！Laravel 可能正在執行但回應遺失
- **狀態擁有者**：Laravel，必須手動查詢 Laravel 狀態才能確認
- **維運查詢位置**：Laravel 的交易記錄、日誌
- **修復位置**：Laravel 的效能問題，或考慮調高超時時間

> ⚠️ **關鍵提醒**：Timeout 不代表 Laravel 沒有執行！對於金額、點數相關的修改操作，任何逾時後都必須先查詢 Laravel 狀態，再決定是否重送。

---

### 6. Invalid JSON / Invalid Response
**發生場景**：Laravel 回傳非 JSON 格式的內容（如 HTML 錯誤頁面、空回應）
- **FastAPI 行為**：立即中斷，包裝為解析錯誤回傳
- **是否可重試**：僅 GET 操作可手動重試，修改操作需先查詢狀態
- **狀態擁有者**：Laravel，需手動確認操作是否執行
- **維運查詢位置**：FastAPI 日誌中記錄的 raw 回應內容
- **修復位置**：Laravel 的錯誤處理邏輯，不應在API錯誤時回傳HTML

---

### 7. JWT 過期
**發生場景**：存取 token 過期，無法自動刷新
- **FastAPI 行為**：拋出 401 錯誤，需要重新登入
- **是否可重試**：重新取得有效 token 後可重試
- **是否可能造成重複變更**：不會，token 無效時請求會被 Laravel 拒絕
- **維運查詢位置**：FastAPI 的認證日誌
- **修復位置**：檢查 Laravel 的 token 有效期設定，或帳號狀態

---

### 8. Authentication Failure
**發生場景**：帳密錯誤、權限不足、無法登入 Laravel
- **FastAPI 行為**：啟動失敗或立即拋出 503 錯誤
- **維運處理**：立即檢查 .env 中的 Laravel 憑證是否正確

---

### 9. Laravel 成功執行但 FastAPI 沒收到 Response
**發生場景**：網路中斷導致回應包遺失，與 Read Timeout 類似
- **FastAPI 行為**：視為 Timeout 處理
- **核心風險**：這是最容易產生重複交易的場景，必須依賴 Idempotency-Key
- **唯一安全做法**：若呼叫端未提供穩定的 Idempotency-Key，絕不自動重試

---

### 10. Workflow 中途部分失敗（Partial Failure）
**典型場景（POS Checkout）**：
```text
Customer validation     ✅ SUCCESS
Earn Points             ✅ SUCCESS  → 這個步驟可能已在 Laravel 生效
Redeem Coupon           ❌ FAILURE  → 工作流程中斷
```
- **FastAPI 行為**：立即中斷工作流程，回傳明確的失敗錯誤
- **FastAPI 不做什麼**：
  - 不嘗試自動 Rollback 已成功的 Earn Points 操作
  - 不維護任何交易狀態來追蹤需要復原的步驟
  - 不向呼叫端隱瞞部分失敗的事實
- **狀態說明**：Earn Points 可能已成功寫入 Laravel，呼叫端不能假設「工作流程失敗等於所有操作都未發生」
- **未來改善方向**：若需要原子性的 POS Checkout，應由 Laravel 提供複合式 API，讓整個流程在 Laravel 的資料庫交易邊界內執行

---

### 11. Idempotency-Key 不一致或遺失
**發生場景**：呼叫端重送請求時使用了不同的 key，或未提供 key
- **FastAPI 行為**：若呼叫端未提供，會自動生成一個新的 key 給當次請求
- **風險**：自動生成的 key 不會跨請求持久化，因此無法防止重複執行
- **是否能防禦**：僅能保護當次請求的重試，無法保護呼叫端層級的重送
- **正確做法**：需要安全重試的呼叫端必須提供穩定、業務層級唯一的 Idempotency-Key

---

### 12. Tenant Header 錯誤或遺失
**發生場景**：未正確設定 `X-Tenant-ID`，或租戶ID不存在
- **FastAPI 行為**：Laravel 會回傳 403/404 錯誤，本服務直接轉發
- **可能影響**：跨租戶資料存取失敗，或租戶資料隔離失敗
- **維運查詢**：請求標頭中的 X-Tenant-ID 是否正確傳遞

---

### 13. Reverb 斷線
**發生場景**：WebSocket 連線中斷，無法接收 Laravel 廣播的事件
- **FastAPI 行為**：自動嘗試重新連線，最多重試10次
- **影響**：前端無法接收即時的點數更新、狀態變更事件
- **是否影響交易一致性**：不會，WebSocket 僅做事件通知，核心交易仍依賴 HTTP API

---

### 14. 外部系統重複送出相同請求
**發生場景**：呼叫端因為超時，重送了同一筆交易
- **本服務的保護能力**：
  - 若有傳遞相同的 Idempotency-Key：Laravel 會保證冪等，不會重複執行
  - 若未傳遞或傳遞不同的 key：無法防禦，會產生重複交易
- **責任歸屬**：冪等性的最終保護依賴 Laravel 的實作，本服務僅負責轉發 key

---

### 15. Laravel API Contract 改變
**發生場景**：Laravel 端修改了 API 路徑、參數格式、回應結構
- **本服務的保護機制**：
  - 整合測試會在連接真實 Laravel 時偵測到此類問題
  - 路由契約驗證工具可檢查 FastAPI 自身的路由一致性
- **維運處理**：任何 Laravel API 的變更都必須同步更新本服務的 Domain Client 與對應測試

---

## Dependency Failure：Laravel 掛了怎麼辦？

Laravel 是本服務的唯一核心依賴，當 Laravel 發生下列狀況時，本服務的行為如下：

### Laravel Down (無法連線)
- 所有需要呼叫 Laravel 的請求都會回傳 502 Bad Gateway
- 僅 `/health` 端點會回傳服務狀態為不健康
- 無任何請求會被排隊或持久化，全部直接失敗
- WebSocket 轉發功能也無法正常運作，因為需要 Laravel 的認證

### Laravel Slow (回應時間超過逾時)
- 所有請求都會在 30 秒（預設）後逾時
- 符合重試條件的請求會進入重試流程
- 同樣可能面臨 Read Timeout 的所有風險

### Laravel 持續回傳 500
- 符合條件的請求會自動重試3次，隨後失敗
- 短時間內大量500會導致本服務的錯誤率上升
- 本服務目前未實作 Circuit Breaker，不會主動切斷流量

### Laravel 認證持續失敗
- 本服務會在啟動或需要刷新 token 時失敗
- 所有需要認證的請求都會回傳 401 錯誤

---

## Incident Investigation：如何追查問題？

當客戶回報「POS 扣點失敗，但不知道到底有沒有扣成功？」，可以依以下資訊追查：

### 目前可追蹤的欄位
| 欄位 | 是否存在 | 記錄位置 |
|------|---------|----------|
| Customer ID | ✅ 存在 | 所有請求的路徑參數、日誌 |
| Tenant ID | ✅ 存在 | 請求標頭、日誌 |
| API Endpoint | ✅ 存在 | 日誌記錄呼叫的 Laravel 路徑 |
| HTTP Status | ✅ 存在 | 所有 API 回應的狀態碼都有記錄 |
| Laravel Response Payload | ✅ 存在 | 錯誤時會記錄完整的回應內容 |
| Workflow Step | ✅ 存在 | POS Checkout 的每個步驟都有日誌 |
| Error Type | ✅ 存在 | 例外類型會被記錄 |
| Idempotency-Key | ✅ 存在 | 所有修改操作的 key 都有記錄 |
| Request ID / Correlation ID | ❌ 不存在 | 目前的可觀測性缺口 |

### 標準追查步驟
1. 取得客戶的 Customer ID 與交易時間
2. 查詢 FastAPI 日誌中是否有對應的工作流程執行記錄
3. 檢查工作流程在哪一個步驟失敗
4. 若失敗在 Redeem 步驟，查詢 Laravel 中該 Customer 的點數交易記錄，確認 Earn 步驟是否已寫入
5. 使用日誌中的 Idempotency-Key 在 Laravel 中查詢是否有重複的交易記錄

---

## 變更風險分級

維護者在修改程式碼前，應了解不同修改的風險等級：

### Low Risk（低風險）
- 新增單純的 GET 查詢端點
- 調整回應格式的映射邏輯（不變更欄位語義）
- 新增單純的輸入驗證規則
- 修改日誌輸出的格式或内容
- 新增非核心的輔助工具腳本

### Medium Risk（中風險）
- 修改認證相關的邏輯（JWT 刷新、token 處理）
- 調整全域的 Timeout 設定
- 修改錯誤處理與例外映射邏輯
- 新增新的 Domain Client
- 修改 Tenant Header 的處理邏輯

### High Risk（高風險）
- 修改 Idempotency-Key 的產生或傳遞邏輯
- 變更 Retry 策略或判斷條件
- 修改 POS Checkout 工作流程的執行順序
- 變更任何 Laravel API 契約相關的映射
- 修改 Reverb WebSocket 的事件轉發邏輯
- 調整工作流程的錯誤處理行為