# راهنمای تست شارژ کیف پول با درگاه سپهر

در این سند فرایند کامل تست درگاه «پرداخت الکترونیک سپهر (بانک صادرات)» در محیط توسعه تشریح می‌شود.

---

## 🔧 پیکربندی محیط

```env
BASE_URL=http://localhost:8000             # آدرس سرور شما برای callback
PAYMENT_GATEWAY_DEFAULT=sepehr             # ثابت روی سپهر
SEPEHR_ENABLED=True
SEPEHR_TERMINAL_ID=YOUR_TERMINAL_ID        # از بانک دریافت می‌شود
SEPEHR_TOKEN_URL=https://sepehr.shaparak.ir/Rest/V1/PeymentApi/GetToken
SEPEHR_PAYMENT_URL=https://sepehr.shaparak.ir/Payment/Pay
SEPEHR_ADVICE_URL=https://sepehr.shaparak.ir/Rest/V1/PeymentApi/Advice
SEPEHR_ROLLBACK_URL=https://sepehr.shaparak.ir/Rest/V1/PeymentApi/Rollback
SEPEHR_TIMEOUT=10
SEPEHR_DEFAULT_PAYLOAD=
```

> اگر درگاه واقعی هنوز آماده نیست، می‌توانید callback و پاسخ Advice را به صورت دستی شبیه‌سازی کنید (در ادامه توضیح داده شده است).

---

## 🧪 فلو کامل تست شارژ

### مرحله 1: لاگین و دریافت Token

```bash
# لاگین
POST http://localhost:8000/api/core/login/
{
  "phone": "09123456789"
}

# Verify
POST http://localhost:8000/api/core/verify/
{
  "phone": "09123456789",
  "code": "1234"
}
```

### مرحله 2: ایجاد کیف پول (اگر ندارید)

```bash
POST http://localhost:8000/api/wallet/create/
Authorization: Bearer <access_token>
{
  "currency": "IRR"
}
```

### مرحله 3: درخواست شارژ از طریق Mock

```bash
POST http://localhost:8000/api/wallet/charge-gateway/
Authorization: Bearer <access_token>
Content-Type: application/json

{
  "amount": 1000,
  "description": "تست شارژ کیف پول"
}
```

**پاسخ موفق (سپهر):**

```json
{
  "request_id": "req_abc123def456",
  "payment_url": "https://sepehr.shaparak.ir/Payment/Pay?token=ACCESS_TOKEN&terminalId=12345678",
  "authority": "ACCESS_TOKEN",
  "amount": 1000,
  "gateway": "sepehr",
  "expires_at": "2025-01-01T13:00:00Z"
}
```

### مرحله 4: هدایت کاربر به صفحه پرداخت

آدرس `payment_url` را در مرورگر باز کنید. برای تست نیاز است که دسترسی اینترنتی و اطلاعات کارت آزمایشی بانک در اختیار باشد.

### مرحله 5: دریافت و شبیه‌سازی Callback

در محیط لوکال بهتر است از ابزارهایی مانند ngrok استفاده شود تا درگاه بتواند پاسخ را به `/api/wallet/payment-callback/` ارسال کند. در صورت عدم دسترسی می‌توانید پاسخ را به صورت دستی پست کنید:

```bash
POST http://localhost:8000/api/wallet/payment-callback/
Content-Type: application/json

{
  "respcode": "0",
  "invoiceid": "req_abc123def456",
  "digitalreceipt": "824b3098-7035-4e61-ab09-51f07e22aebd",
  "Authority": "ACCESS_TOKEN"
}
```

> مقدارهای `digitalreceipt` و `invoiceid` باید با پاسخ واقعی سپهر همخوانی داشته باشند. در حالت شبیه‌سازی می‌توانید مقادیر ساختگی یکتا ارسال کنید.

### مرحله 6: بررسی وضعیت پرداخت

```bash
GET http://localhost:8000/api/wallet/payment-status/{request_id}/
Authorization: Bearer <access_token>
```

**پاسخ نمونه:**

```json
{
  "request_id": "req_abc123def456",
  "amount": 1000,
  "status": "completed",
  "gateway": "sepehr",
  "authority": "ACCESS_TOKEN",
  "ref_id": "824b3098-7035-4e61-ab09-51f07e22aebd",
  "transaction_id": "txn_abc123",
  "balance_after": 1000,
  "created_at": "...",
  "updated_at": "..."
}
```

### مرحله 7: بررسی موجودی

```bash
GET http://localhost:8000/api/wallet/balance/
Authorization: Bearer <access_token>
```

---

## 🧪 تست انتقال وجه (هفت روش)

Endpoint مشترک: `POST /api/wallet/transfer/`

Headers:
```
Authorization: Bearer <access_token>
Content-Type: application/json
```

| مقدار `method` | توضیح سناریو | کلیدهای مهم در بدنه |
| --- | --- | --- |
| `phone` | انتقال به شماره موبایل آزاد | `recipient_phone` |
| `contact` | انتقال به مخاطب ذخیره‌شده (همان موبایل با متادیتا) | `recipient_phone`, `metadata.contact_id` |
| `wallet` | انتقال به شناسه کیف پول مشخص | `recipient_wallet_id` |
| `qr` | انتقال با QR Code | `metadata.qr_payload` یا `metadata.qr_id` |
| `iban` | انتقال به شماره شبا داخلی | `metadata.iban` |
| `card` | انتقال به شماره کارت داخلی | `metadata.card_number` |
| `link` | انتقال از طریق لینک پرداخت داخلی | `metadata.payment_link_id` |

### نمونه درخواست‌ها

**1. انتقال با شماره موبایل (phone)**
```json
{
  "method": "phone",
  "recipient_phone": "+989121234567",
  "amount": 50000,
  "description": "بازپرداخت قرض",
  "metadata": {
    "note": "انتقال سریع"
  }
}
```

**2. انتقال به مخاطب (contact)**
```json
{
  "method": "contact",
  "recipient_phone": "+989121234567",
  "amount": 75000,
  "metadata": {
    "contact_id": "cnt_42",
    "note": "انتقال به مخاطب ذخیره‌شده"
  }
}
```

**3. انتقال به شناسه کیف پول (wallet)**
```json
{
  "method": "wallet",
  "recipient_wallet_id": 123,
  "amount": 150000,
  "description": "تسویه داخلی"
}
```

**4. انتقال با QR (qr)**
```json
{
  "method": "qr",
  "amount": 90000,
  "metadata": {
    "qr_payload": "QR_CODE_RAW_DATA"
  }
}
```

**5. انتقال با شماره شبا (iban)**
```json
{
  "method": "iban",
  "amount": 200000,
  "metadata": {
    "iban": "IR820540102680020817909002",
    "note": "انتقال به شبا داخلی"
  }
}
```

**6. انتقال با شماره کارت (card)**
```json
{
  "method": "card",
  "amount": 120000,
  "metadata": {
    "card_number": "5022291234567890",
    "note": "انتقال کارت به کارت داخلی"
  }
}
```

**7. انتقال با لینک پرداخت (link)**
```json
{
  "method": "link",
  "amount": 300000,
  "metadata": {
    "payment_link_id": "pl_9812",
    "note": "تسویه از طریق لینک"
  }
}
```

### بررسی پاسخ

برای همه روش‌ها پاسخ استاندارد به شکل زیر است:
```json
{
  "transaction_id": "txn_123abc",
  "amount": 50000,
  "recipient": {
    "phone": "09121234567",
    "fullname": "کاربر دریافت‌کننده"
  },
  "balance_after": 1250000,
  "status": "completed",
  "created_at": "2025-01-01T10:45:12Z",
  "method": "phone",
  "metadata": {
    "direction": "outgoing",
    "recipient_wallet_id": 123,
    "note": "انتقال سریع"
  }
}
```

پس از هر انتقال، می‌توانید با `GET /api/wallet/transactions/` فهرست تراکنش‌ها را مشاهده کرده و ستون `method` و `metadata` را برای صحت تست بررسی کنید.

---

## 🐛 عیب‌یابی

### خطا: "Sepehr gateway is disabled"

- مقدار `SEPEHR_ENABLED=True` نیست یا تنظیمات در `PAYMENT_GATEWAYS` ناقص است.

### خطا: "Unsupported payment gateway"

- احتمالاً درخواست قدیمی با فیلد `gateway` ارسال شده است. فیلد را حذف کنید تا درگاه سپهر به صورت پیش‌فرض استفاده شود.

### خطا: "Payment request failed" یا "Payment verification failed"

- صحت `SEPEHR_TERMINAL_ID`، آدرس‌های سرویس و مقادیر `invoiceid`, `digitalreceipt` را بررسی کنید.
- مطمئن شوید درخواست Advice با JSON صحیح ارسال شده است.

### خطا: Callback کار نمی‌کند

- در محیط لوکال برای سپهر باید از ngrok یا سرویس مشابه استفاده کنید یا داده را به صورت دستی POST نمایید (همان‌طور که در مرحله ۵ توضیح داده شد).

---

## 🔄 تست خودکار (نمونه اسکریپت Python)

```env
PAYMENT_GATEWAY_DEFAULT=sepehr
```

```python
import requests

BASE_URL = "http://localhost:8000"
TOKEN = "your-access-token"

# درخواست شارژ
response = requests.post(
    f"{BASE_URL}/api/wallet/charge-gateway/",
    headers={"Authorization": f"Bearer {TOKEN}"},
    json={
        "amount": 1000,
        "description": "تست"
    }
)

data = response.json()
print(f"Payment URL: {data['payment_url']}")
print(f"Request ID: {data['request_id']}")

# بعد از پرداخت، بررسی وضعیت
status_response = requests.get(
    f"{BASE_URL}/api/wallet/payment-status/{data['request_id']}/",
    headers={"Authorization": f"Bearer {TOKEN}"}
)

print(status_response.json())
```

## ✅ چک‌لیست تست

- [ ] `SEPEHR_TERMINAL_ID` و سایر تنظیمات در `.env` مقداردهی شده‌اند.
- [ ] کیف پول ایجاد شده
- [ ] درخواست شارژ موفق است
- [ ] payment_url درست است
- [ ] Callback (واقعی یا شبیه‌سازی‌شده) به درستی ارسال می‌شود
- [ ] کیف پول شارژ می‌شود
- [ ] تراکنش ثبت می‌شود
