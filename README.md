# Loyalty Integration

Python 外部整合系統，用於驗證與演示 **Multi-Tenant Loyalty Platform**（Laravel）的 API 整合能力。

本專案模擬真實 POS / CRM 系統如何安全地串接 Laravel Loyalty API，重點展示：

- JWT 認證
- 租戶隔離
- 點數交易（earn / redeem）
- **Idempotency（防重送、防重複扣點）**
- POS 完整結帳流程
- 優惠券核銷
- 混合支付（點數折抵）
- QR Code 會員識別
- QR Code 取得
- **FastAPI 整合層（可被其他系統透過 HTTP 呼叫）**

> 設計原則：Python 只負責「決策與編排」，所有點數與優惠券的一致性、鎖定、FIFO、餘額正確性，全部交由 Laravel 核心處理。

---

## 專案結構

```text
loyalty-integration/
├── app/
│   ├── client/
│   │   ├── base.py          # 核心 Client（JWT + Idempotency-Key）
│   │   ├── customer.py      # 會員相關 API
│   │   ├── point.py         # 點數相關 API
│   │   └── coupon.py        # 優惠券相關 API
│   ├── workflows/
│   │   └── pos_checkout.py  # POS 完整結帳流程
│   ├── config.py            # 環境設定
│   └── main.py              # FastAPI 入口
├── test_login.py
├── test_customer_point.py
├── test_idempotency.py      # 最重要的演示
├── test_pos_checkout.py
├── test_coupon.py
├── test_coupon_redeem.py
├── test_mixed_payment.py
├── .env
└── README.md
```

---

## 快速開始

### 1. 環境需求

- Python 3.10+
- 本機 Laravel Loyalty API 已啟動（預設 `http://localhost:8088/api/v1`）
- 可用的測試帳號

### 2. 安裝

```bash
python -m venv venv

# Windows
venv\Scripts\activate

# macOS / Linux
source venv/bin/activate

pip install fastapi uvicorn httpx pydantic pydantic-settings python-dotenv rich pytest pytest-asyncio
```

### 3. 設定環境變數

編輯 `.env`：

```env
LARAVEL_API_BASE_URL=http://localhost:8088/api/v1
LARAVEL_EMAIL=your-test-account@example.com
LARAVEL_PASSWORD=your-password
```

### 4. 驗證登入

```bash
python test_login.py
```

成功會看到：

```text
✓ Login successful as your-test-account@example.com
Login successful!
Token: eyJ0eXAiOiJKV1QiLCJhbGci...
```

---

## 啟動 FastAPI 整合層

### 啟動服務

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

啟動成功後會看到類似訊息：

```text
✓ Login successful as admin-r@example.com
Laravel API 登入成功，服務準備就緒
Uvicorn running on http://0.0.0.0:8000
```

### 可用網址

| 用途                   | 網址                         |
| ---------------------- | ---------------------------- |
| Swagger UI（互動文件） | http://localhost:8000/docs   |
| ReDoc                  | http://localhost:8000/redoc  |
| 健康檢查               | http://localhost:8000/health |
| 服務根路徑             | http://localhost:8000/       |

### FastAPI 端點一覽

| 方法 | 路徑                               | 說明                  |
| ---- | ---------------------------------- | --------------------- |
| GET  | `/`                                | 服務狀態              |
| GET  | `/health`                          | 健康檢查              |
| GET  | `/customers`                       | 會員列表              |
| GET  | `/customers/{customer_id}`         | 單一會員              |
| GET  | `/customers/{customer_id}/points`  | 點數餘額              |
| GET  | `/customers/{customer_id}/qr-code` | 取得會員 QR Code      |
| POST | `/customers/identify`              | 使用 QR Code 識別會員 |
| POST | `/points/earn`                     | 發放點數              |
| POST | `/points/redeem`                   | 兌換點數              |
| POST | `/workflows/pos-checkout`          | POS 完整結帳流程      |
| GET  | `/customers/{customer_id}/coupons` | 優惠券列表            |
| POST | `/coupons/redeem`                  | 核銷優惠券            |
| POST | `/payments/mixed`                  | 混合支付（點數折抵）  |

### 快速測試範例

```bash
# 健康檢查
curl http://localhost:8000/health

# 取得會員 QR Code（模擬會員中心產生 QR Code）
curl http://localhost:8000/customers/1/qr-code

# 使用 QR Token 識別會員（模擬 POS 掃碼）
# 將 your-qr-token 替換為上方取得的 qr_token
curl -X POST http://localhost:8000/customers/identify \
  -H "Content-Type: application/json" \
  -d "{\"qr_token\": \"your-qr-token\"}"

# 識別成功後查詢會員點數
curl http://localhost:8000/customers/1/points

# 兌換點數
curl -X POST http://localhost:8000/points/redeem \
  -H "Content-Type: application/json" \
  -d "{\"customer_id\": 1, \"amount\": 10}"

# 執行 POS 結帳流程
curl -X POST http://localhost:8000/workflows/pos-checkout \
  -H "Content-Type: application/json" \
  -d "{\"customer_id\": 1, \"earn_amount\": 50, \"redeem_amount\": 20}"
```

也可直接開啟 http://localhost:8000/docs 使用 Swagger UI 互動測試。

---

## 核心演示腳本（CLI）

除了 FastAPI，也可以直接執行測試腳本：

| 腳本 / 能力              | 目的               | 驗證重點                            | 類型         |
| ------------------------ | ------------------ | ----------------------------------- | ------------ |
| `test_login.py`          | 登入取得 JWT       | 認證是否正常                        | CLI 測試     |
| `test_customer_point.py` | 查詢會員與點數     | 基本讀取能力                        | CLI 測試     |
| `test_idempotency.py`    | **冪等性重送測試** | 同一個 Idempotency-Key 不會重複扣點 | CLI 測試     |
| `test_pos_checkout.py`   | POS 完整結帳       | 發點 → 兌換 → 餘額正確              | CLI 測試     |
| `test_coupon.py`         | 查詢優惠券         | 優惠券列表                          | CLI 測試     |
| `test_coupon_redeem.py`  | 核銷優惠券         | 狀態從 available → used             | CLI 測試     |
| `test_mixed_payment.py`  | 混合支付           | 點數折抵訂單金額                    | CLI 測試     |
| QR Code 會員識別         | POS 掃碼識別會員   | 掃碼 → 識別流程正確                 | FastAPI 端點 |
| QR Code 取得             | 產生會員 QR Code   | 可取得有效的 QR Token               | FastAPI 端點 |

### 最重要的演示：Idempotency

```bash
python test_idempotency.py
```

預期結果：

1. 第一次請求成功扣點
2. 用**同一個 Idempotency-Key** 重送
3. 點數**不會被重複扣除**
4. 最終餘額正確

這直接證明 Laravel 核心交易設計具備企業級安全性。

### POS 完整流程

```bash
python test_pos_checkout.py
```

流程包含：

1. 查詢會員
2. 查詢目前餘額
3. 消費發點（earn）
4. 兌換點數（redeem）
5. 再次查詢餘額並驗證計算正確

---

## 設計原則

### Python 端負責

- 取得與管理 JWT
- 產生並傳遞 `Idempotency-Key`
- 編排業務流程（POS 結帳、混合支付等）
- 對外提供 HTTP API（FastAPI）

### Python 端**不負責**

- 修改點數餘額
- 實作 FIFO / Point Lot
- 處理優惠券狀態機
- 實作 Redis Lock 或資料庫交易
- 保證交易一致性

所有關鍵狀態變更都由 Laravel Loyalty API 完成，確保單一事實來源（Single Source of Truth）。

---

## 已驗證的能力

- [x] JWT Authentication
- [x] 會員查詢
- [x] 點數餘額與交易紀錄查詢
- [x] 點數發放（earn）
- [x] 點數兌換（redeem）
- [x] Idempotency（防重送）
- [x] POS 結帳完整流程
- [x] 優惠券查詢與核銷
- [x] 混合支付（點數折抵）
- [x] QR Code 會員識別
- [x] QR Code 取得
- [x] FastAPI 整合層（HTTP API + Swagger）

---

## 與 Laravel 核心的對應關係

| Laravel 能力                  | 本專案如何驗證                                                     |
| ----------------------------- | ------------------------------------------------------------------ |
| JWT Auth                      | `test_login.py` / FastAPI 啟動時自動登入                           |
| Tenant Isolation              | 所有請求都在登入使用者所屬租戶下執行                               |
| Point Transaction + Locking   | `test_pos_checkout.py`、`test_idempotency.py`                      |
| Idempotency Middleware        | `test_idempotency.py`                                              |
| Coupon Redeem                 | `test_coupon_redeem.py`                                            |
| Mixed Payment                 | `test_mixed_payment.py`                                            |
| QR Code Member Identification | FastAPI `/customers/{customer_id}/qr-code` + `/customers/identify` |
| 外部系統整合                  | FastAPI `app/main.py`                                              |

---

## 建議演示順序

1. 啟動 Laravel Loyalty API
2. 啟動 FastAPI 整合層：`uvicorn app.main:app --reload --port 8000`
3. 開啟 http://localhost:8000/docs（Swagger UI）
4. `GET /customers/{customer_id}/qr-code` - 取得會員 QR Code
5. `POST /customers/identify` - 使用取得的 QR Token 識別會員（模擬 POS 掃碼）
6. 使用識別結果取得會員資訊：`GET /customers/{customer_id}`
7. `GET /customers/{customer_id}/points` - 查詢點數餘額
8. 執行 `POST /workflows/pos-checkout` - 完成 POS 結帳流程（發點/兌換）
9. 再次查詢點數餘額，驗證餘額變動正確
10. （進階）執行 `python test_idempotency.py` 展示防重送能力

> 真實 POS 流程概念：`掃描會員 QR Code → 識別會員 → 查詢點數 → 結帳 → 發點 / 兌換 → 驗證餘額`

---

## 未來可擴充方向

- 為整合層加上 API Key 或簡易認證
- 允許呼叫端自行傳入 Idempotency-Key
- 排程任務（定期同步、報表）
- CI 自動化測試

---

## 總結

本專案證明：

> Laravel Multi-Tenant Loyalty Platform 不只是 CRUD API，  
> 而是可以被 POS、CRM、電商等外部系統安全整合的交易核心，  
> 並具備完整的冪等性、一致性與租戶隔離能力。

目前已完整整合的能力包括：

- JWT 認證
- Multi-Tenant 租戶隔離
- 會員管理（Customer）
- 點數交易（Points）
- Idempotency 防重送機制
- POS Checkout 完整結帳流程
- 優惠券管理（Coupon）
- 混合支付（Mixed Payment）
- QR Code 會員識別
- FastAPI 對外整合層
