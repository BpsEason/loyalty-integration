# Architecture Guide - 架構設計指南

本文檔深入說明 Loyalty Integration Layer 的架構設計理念、責任邊界定義，以及為什麼做出這些設計決策。

---

## 核心架構圖

```text
External System (POS/電商/CRM)
       ↓
FastAPI Integration Layer
       ↓
Laravel Loyalty API
       ↓
Laravel Domain / State
```

這是一個單層的整合架構，FastAPI 僅作為 Laravel 的閘道與協調者，不承擔任何領域責任。

---

## 狀態所有權（State Ownership）

### Laravel 是唯一的 Loyalty 狀態擁有者
這是本整合層最重要的設計原則：**Laravel 擁有且僅有 Laravel 擁有所有 Loyalty 領域的狀態**。

這意味著：
- FastAPI 從不維護任何會員的點數餘額、優惠券狀態、交易記錄
- 所有查詢操作都即時呼叫 Laravel API，不做任何快取
- 所有修改操作都直接轉發給 Laravel，冪等性由 Laravel 保證
- 永遠不會出現「FastAPI 顯示的狀態與 Laravel 不一致」的問題

### 為什麼這麼設計？
避免狀態分裂（State Split）是整合系統的首要任務。如果有兩個系統都維護同一套狀態，總有一天它們會不一致，而且很難除錯。整合層的職責就是轉發與協調，不是成為另一個狀態來源。

---

## 領域邊界（Domain Boundary）

### FastAPI 不進入 Loyalty 領域
Loyalty 領域包含：
- 點數計算規則
- 優惠券兌換資格
- 會員等級升級條件
- 促銷活動的參與條件
- 任何與 Loyalty 業務相關的規則

所有這些都由 Laravel 實作與維護，FastAPI 的程式碼中永遠不會出現這些邏輯。

### FastAPI 的領域是「整合」
FastAPI 唯一的領域是「整合流程」，包含：
- 如何依序呼叫多個 Laravel API 來完成一個工作流程
- 如何處理網路層級的錯誤與重試
- 如何將外部系統的輸入格式映射為 Laravel 需要的格式
- 如何將 Laravel 的輸出格式轉換為外部系統期望的格式
- 如何轉發認證標頭與上下文資訊

---

## 整合邊界（Integration Boundary）

### 整合層的責任就是「整合」，不要做更多
本服務只解決整合場景會遇到的問題，不試圖解決 Laravel 領域內的問題。如果一個問題在只有 Laravel 時不會存在，只有在整合多個外部系統時才會存在，那才是 FastAPI 該處理的問題。

例如：
- ✅ 多個外部系統都需要同樣的 JWT 認證邏輯 → FastAPI 統一處理
- ✅ 多個外部系統都需要同樣的 POS 結帳流程 → FastAPI 統一實作
- ✅ 每個外部系統的輸入格式都不一樣，但 Laravel 要求統一格式 → FastAPI 做映射
- ❌ Laravel 本身的點數計算錯誤 → 應該在 Laravel 修復，不是在 FastAPI 補 workaround

---

## Idempotency 所有權

### Laravel 是 Idempotency Owner
與狀態所有權一樣，冪等性的保證責任也完全在 Laravel 身上。FastAPI 只做一件事：**將外部系統提供的 Idempotency-Key 原封不動地轉發給 Laravel**。

FastAPI 不：
- 自行生成跨請求的冪等性 key
- 維護任何已執行操作的記錄來防止重複
- 實作任何冪等性檢查邏輯

這些都交由 Laravel 處理，因為 Laravel 才是狀態的擁有者，只有它能真正保證操作的冪等性。

---

## Workflow 編排責任

### FastAPI 只做簡單的流程編排
目前支援的工作流程（如 POS Checkout）都是**同步、線性、依序執行**的簡單編排：
```text
Customer validation → Earn Points → Redeem Coupon
```

任何步驟失敗，立即中斷整個流程，不做任何自動復原或重試（除了底層 HTTP 客戶端的安全重試）。

### 不做複雜的流程引擎
本服務目前不實作：
- 非同步工作流程
- 並行執行的步驟
- 條件分支的複雜邏輯
- 工作流程狀態的持久化
- 失敗步驟的自動重試
- 補償交易（Compensating Transaction）

如果業務需要這些複雜的流程協調，應該引入專業的工作流程引擎，而不是在 FastAPI 中自己實作。

---

## 部分失敗的責任邊界（Partial Failure）

### 最常被詢問的設計決策：為什麼不 Rollback？

典型的部分失敗場景（POS Checkout）：
```text
Customer validation     ✅ SUCCESS
Earn Points             ✅ SUCCESS  → 已在 Laravel 生效
Redeem Coupon           ❌ FAILURE  → 工作流程中斷
```

當發生這種部分失敗時，FastAPI **不會嘗試去 Rollback 已經成功的 Earn Points 操作**。

### 為什麼不實作自動 Rollback？
1. **誰能保證 Rollback 一定成功？**如果 Rollback 的請求也失敗了，怎麼辦？只會讓狀態更混亂
2. **Rollback 本身也是一個變更操作**，需要自己的 Idempotency-Key，需要自己的錯誤處理，會引入更多複雜度
3. **Laravel 才是領域專家**，如果有一個操作需要原子性地執行，應該由 Laravel 提供一個複合式的 API，讓整個操作在 Laravel 的資料庫交易邊界內完成
4. **保持簡單**：明確告訴呼叫端「工作流程失敗不代表所有步驟都未執行，請查詢 Laravel 狀態」，比隱藏複雜性、試圖「自動修復」更負責任

### 正確的處理方式
當需要原子性的跨領域操作時，推動 Laravel 提供這樣的 API：
```http
POST /api/pos-checkout
{
  "customer_id": "123",
  "amount": 1000,
  "coupon_id": "456"
}
```
讓整個流程在 Laravel 內部的資料庫交易中執行，要麼全部成功，要麼全部失敗。這才是正確的解決方案，整合層不應該試圖實作分散式交易。

---

## 為什麼沒有 Repository 模式？

在許多後端專案中常見的 Repository 模式，在本服務中沒有被採用。原因很簡單：不需要。

Repository 模式的存在價值是「隔離領域層與資料存取層」，讓同一個領域邏輯可以切換不同的資料庫。但本服務不是領域層，它只是一個整合層，所有的「資料存取」都是呼叫同一個 Laravel API，沒有切換儲存層的需求。

引入 Repository 只會增加不必要的抽象層，沒有任何實質好處。保持簡單：直接使用 Domain Client。

---

## 為什麼不在 FastAPI 重建 Domain Service？

有些整合專案會在整合層中重新實作一套領域服務，試圖「聚合」多個後端系統的領域邏輯。本服務明確禁止這種做法。

如果需要 Loyalty 領域服務，那本就該在 Laravel 中實作。FastAPI 的存在不是為了重建另一套領域層，而是為了連接現有的 Laravel 領域層與外部系統。

---

## 為什麼目前沒有 Saga / Distributed Transaction？

分散式交易與 Saga 模式是處理跨服務原子性的經典解法，但本服務目前刻意不實作，原因：

### 1. 需求還不存在
目前的工作流程複雜度還不需要這麼強大的機制。YAGNI（You Ain't Gonna Need It）原則：只有當實際業務需要時才引入複雜度。

### 2. Saga 帶來的複雜度很高
實作一個正確的 Saga 需要：
- 工作流程狀態的持久化
- 每個步驟的補償交易
- 失敗重試機制
- 觀測性支援
- 大量的測試來保證正確性

這些複雜度的導入需要有相應的業務價值來 justify。

### 3. 有更簡單的解決方案
如果真的需要原子性的跨領域操作，優先推動 Laravel 提供複合式 API，讓整個操作在單一資料庫交易中完成。這比實作分散式交易簡單得多，也可靠得多。

### 未來什麼情況才需要引入 Saga？
只有當下列條件都滿足時，才會考慮引入 Saga 模式：
1. 業務確實需要跨多個獨立服務的原子性操作
2. 這些服務無法修改以提供複合式 API
3. 無法使用兩階段提交（2PC）等傳統分散式交易方案
4. 部分失敗帶來的業務損失大於實作 Saga 的成本

---

## 認證邊界（Authentication Boundary）

### FastAPI 代理 Laravel 的認證
FastAPI 本身不處理使用者認證，所有的認證都是代理 Laravel 的 JWT 機制：
- FastAPI 以服務帳號登入 Laravel，取得 JWT token
- 所有對 Laravel 的請求都攜帶這個 token
- token 過期時自動刷新
- 並發鎖防止多個請求同時刷新 token 造成問題

外部系統呼叫 FastAPI 時的認證（如果有）是另一層獨立的機制，與 Laravel 的認證分開。

---

## 租戶上下文（Tenant Context）

### X-Tenant-ID 的傳遞
多租戶的支援非常簡單：外部系統在呼叫 FastAPI 時必須在標頭中帶入 `X-Tenant-ID`，FastAPI 會將這個標頭原封不動地轉發給所有對 Laravel 的請求。

- FastAPI 本身不驗證租戶 ID 的有效性，這是 Laravel 的責任
- FastAPI 不會修改或生成租戶 ID
- 所有對 Laravel 的請求都必須攜帶這個標頭
- 租戶資料的隔離完全由 Laravel 保證

---

## API 契約（API Contract）

### 嚴格的契約一致性要求
FastAPI 與 Laravel 之間的 API 契約是強耦合的，任何 Laravel API 的變更都必須同步更新 FastAPI 的對應程式碼：

```text
FastAPI Router
      ↓
Domain Client
      ↓
Laravel API
      ↓
Integration Tests
      ↓
Documentation
```

這個鏈路中的任何一個環節改變，其他環節都必須跟進。這就是為什麼有 `verify_routes.py` 工具來檢查路由的一致性，為什麼整合測試需要連接真實的 Laravel API。

### 契約漂移（Contract Drift）是本服務最大的風險
如果 Laravel 修改了 API，但 FastAPI 的 Domain Client 未同步更新，會導致難以除錯的執行時錯誤。所有的開發人員都必須理解：修改 Laravel API 時，必須一並修改 FastAPI 的對應程式碼與測試。

---

## 核心工程原則回顧

> 簡單的地方保持簡單；真正複雜的地方才引入複雜度。

本架構的所有設計決策都圍繞著這個原則：
- 清楚地劃分責任邊界，誰的問題誰來解決
- 只在整合層解決整合的問題，不搶奪其他系統的責任
- 保持簡單，不引入過度設計的複雜架構
- 所有的設計決策都有實際的業務需求支撐
- 讓任何接手的工程師都能快速理解這套系統的邊界與限制