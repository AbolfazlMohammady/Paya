# راهنمای تست شارژ کیف پول با زرین‌پال

## 🔧 تنظیمات اولیه برای تست

### 1. دریافت Merchant ID از زرین‌پال

برای تست، باید یک حساب کاربری در زرین‌پال داشته باشید:

1. به آدرس https://next.zarinpal.com/ بروید
2. ثبت‌نام کنید یا وارد شوید
3. در پنل کاربری، بخش "درگاه پرداخت" را باز کنید
4. Merchant ID خود را کپی کنید

**نکته مهم**: برای تست، می‌توانید از Merchant ID خود استفاده کنید. در حالت Sandbox، پرداخت‌ها واقعی نیستند.

### 2. تنظیم در settings.py

در فایل `config/config/settings.py` یا فایل `.env` اضافه کنید:

```python
# در settings.py
ZARINPAL_MERCHANT_ID = 'your-merchant-id-here'  # Merchant ID خود را وارد کنید
ZARINPAL_SANDBOX = True  # برای تست حتماً True باشد
BASE_URL = 'http://localhost:8000'  # آدرس سرور شما
```

یا در فایل `.env`:
```env
ZARINPAL_MERCHANT_ID=your-merchant-id-here
ZARINPAL_SANDBOX=True
BASE_URL=http://localhost:8000
```

### 3. نصب کتابخانه requests (اگر نصب نیست)

```bash
pip install requests
```

## 🧪 تست با Postman یا cURL

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

# پاسخ شامل access_token است
```

### مرحله 2: ایجاد کیف پول (اگر ندارید)

```bash
POST http://localhost:8000/api/wallet/create/
Authorization: Bearer <access_token>
{
  "currency": "IRR"
}
```

### مرحله 3: درخواست شارژ از درگاه

```bash
POST http://localhost:8000/api/wallet/charge-gateway/
Authorization: Bearer <access_token>
Content-Type: application/json

{
  "amount": 1000,
  "description": "تست شارژ کیف پول"
}
```

**پاسخ موفق:**
```json
{
  "request_id": "req_abc123def456",
  "payment_url": "https://sandbox.zarinpal.com/pg/StartPay/A00000000000000000000000000000000000",
  "authority": "A00000000000000000000000000000000000",
  "amount": 1000,
  "gateway": "zarinpal",
  "expires_at": "2024-01-15T13:00:00Z"
}
```

### مرحله 4: تست پرداخت

1. `payment_url` را در مرورگر باز کنید
2. در صفحه زرین‌پال Sandbox، می‌توانید:
   - **پرداخت موفق**: شماره کارت تست `6037-7997-9999-9999` را وارد کنید
   - **پرداخت ناموفق**: هر شماره کارت دیگری وارد کنید

**کارت‌های تست زرین‌پال:**
- کارت موفق: `6037-7997-9999-9999`
- CVV2: هر عدد 4 رقمی
- تاریخ انقضا: هر تاریخی در آینده

### مرحله 5: بررسی وضعیت پرداخت

بعد از پرداخت، می‌توانید وضعیت را بررسی کنید:

```bash
GET http://localhost:8000/api/wallet/payment-status/{request_id}/
Authorization: Bearer <access_token>
```

**پاسخ:**
```json
{
  "request_id": "req_abc123def456",
  "amount": 1000,
  "status": "completed",
  "gateway": "zarinpal",
  "authority": "A00000000000000000000000000000000000",
  "ref_id": "123456789",
  "transaction_id": "txn_abc123",
  "balance_after": 1000,
  "created_at": "2024-01-15T12:30:00Z",
  "updated_at": "2024-01-15T12:32:00Z"
}
```

### مرحله 6: بررسی موجودی

```bash
GET http://localhost:8000/api/wallet/balance/
Authorization: Bearer <access_token>
```

## 🐛 عیب‌یابی

### خطا: "ZARINPAL_MERCHANT_ID is not configured"

**راه حل:**
- Merchant ID را در settings.py یا .env تنظیم کنید
- مطمئن شوید که متغیر درست لود می‌شود

### خطا: "Payment request failed"

**راه حل:**
- بررسی کنید Merchant ID درست است
- بررسی کنید که ZARINPAL_SANDBOX = True است
- بررسی کنید که callback_url درست است

### خطا: "Payment verification failed"

**راه حل:**
- در حالت Sandbox، بعد از پرداخت، باید به callback_url برگردید
- بررسی کنید که authority درست است
- بررسی کنید که مبلغ پرداخت شده با مبلغ درخواستی یکسان است

### مشکل: Callback کار نمی‌کند

**راه حل:**
- در حالت localhost، باید از ngrok یا tunnel استفاده کنید
- یا callback_url را به یک URL عمومی تنظیم کنید
- در حالت Sandbox، می‌توانید به صورت دستی verify کنید

## 📝 نکات مهم

1. **در حالت Sandbox**: پرداخت‌ها واقعی نیستند و پول واقعی کسر نمی‌شود
2. **Callback URL**: باید یک URL عمومی باشد که درگاه بتواند به آن دسترسی داشته باشد
3. **HTTPS**: در production حتماً از HTTPS استفاده کنید
4. **Timeout**: درخواست‌های پرداخت بعد از 30 دقیقه منقضی می‌شوند

## 🔄 تست خودکار (برای توسعه)

می‌توانید یک script تست بنویسید:

```python
import requests

BASE_URL = "http://localhost:8000"
TOKEN = "your-access-token"

# درخواست شارژ
response = requests.post(
    f"{BASE_URL}/api/wallet/charge-gateway/",
    headers={"Authorization": f"Bearer {TOKEN}"},
    json={"amount": 1000, "description": "تست"}
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

- [ ] Merchant ID تنظیم شده
- [ ] ZARINPAL_SANDBOX = True
- [ ] کیف پول ایجاد شده
- [ ] درخواست شارژ موفق است
- [ ] payment_url درست است
- [ ] پرداخت در Sandbox انجام می‌شود
- [ ] Callback کار می‌کند
- [ ] کیف پول شارژ می‌شود
- [ ] تراکنش ثبت می‌شود

