# راهنمای شارژ کیف پول از طریق درگاه پرداخت

## تنظیمات اولیه

### 1. تنظیم Merchant ID زرین‌پال

در فایل `config/settings.py` اضافه کنید:

```python
# تنظیمات درگاه پرداخت زرین‌پال
ZARINPAL_MERCHANT_ID = 'your-merchant-id-here'
ZARINPAL_SANDBOX = True  # برای تست از True استفاده کنید
BASE_URL = 'http://localhost:8000'  # یا آدرس سرور شما
```

### 2. نصب کتابخانه requests

اگر نصب نیست:
```bash
pip install requests
```

### 3. اجرای Migrations

```bash
python manage.py migrate wallet
```

## نحوه استفاده

### مرحله 1: درخواست شارژ از درگاه

**Endpoint**: `POST /api/wallet/charge-gateway/`

**Headers**:
```
Authorization: Bearer <access_token>
```

**Request Body**:
```json
{
  "amount": 100000,
  "description": "شارژ کیف پول",
  "gateway": "zarinpal",
  "callback_url": "https://yourapp.com/payment/callback"  // اختیاری
}
```

**Response (201 Created)**:
```json
{
  "request_id": "req_abc123def456",
  "payment_url": "https://sandbox.zarinpal.com/pg/StartPay/Authority123",
  "authority": "A00000000000000000000000000000000000",
  "amount": 100000,
  "gateway": "zarinpal",
  "expires_at": "2024-01-15T13:00:00Z"
}
```

### مرحله 2: هدایت کاربر به درگاه

کاربر را به `payment_url` هدایت کنید تا پرداخت را انجام دهد.

### مرحله 3: Callback از درگاه

بعد از پرداخت، درگاه کاربر را به `callback_url` هدایت می‌کند.

**Endpoint**: `POST /api/wallet/payment-callback/`

این endpoint به صورت خودکار:
- پرداخت را verify می‌کند
- کیف پول را شارژ می‌کند
- تراکنش را ثبت می‌کند

### مرحله 4: بررسی وضعیت پرداخت

**Endpoint**: `GET /api/wallet/payment-status/{request_id}/`

**Headers**:
```
Authorization: Bearer <access_token>
```

**Response (200 OK)**:
```json
{
  "request_id": "req_abc123def456",
  "amount": 100000,
  "status": "completed",
  "gateway": "zarinpal",
  "authority": "A00000000000000000000000000000000000",
  "ref_id": "123456789",
  "transaction_id": "txn_abc123",
  "balance_after": 100000,
  "created_at": "2024-01-15T12:30:00Z",
  "updated_at": "2024-01-15T12:32:00Z"
}
```

## مثال کامل (Frontend)

```javascript
// 1. درخواست شارژ
const response = await fetch('/api/wallet/charge-gateway/', {
  method: 'POST',
  headers: {
    'Authorization': `Bearer ${token}`,
    'Content-Type': 'application/json'
  },
  body: JSON.stringify({
    amount: 100000,
    description: 'شارژ کیف پول'
  })
});

const data = await response.json();

// 2. هدایت کاربر به درگاه
if (data.payment_url) {
  window.location.href = data.payment_url;
}

// 3. بعد از بازگشت از درگاه، بررسی وضعیت
const statusResponse = await fetch(`/api/wallet/payment-status/${data.request_id}/`, {
  headers: {
    'Authorization': `Bearer ${token}`
  }
});

const statusData = await statusResponse.json();
console.log('Payment status:', statusData.status);
```

## تست با زرین‌پال Sandbox

برای تست، از Merchant ID تست استفاده کنید:
- Merchant ID تست: `xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx`
- در حالت Sandbox، پرداخت‌ها واقعی نیستند

## نکات مهم

1. **Callback URL**: باید یک URL عمومی باشد که درگاه بتواند به آن دسترسی داشته باشد
2. **HTTPS**: در production حتماً از HTTPS استفاده کنید
3. **Error Handling**: همیشه خطاها را handle کنید
4. **Idempotency**: درخواست‌های تکراری را handle کنید
5. **Timeout**: درخواست‌های پرداخت بعد از 30 دقیقه منقضی می‌شوند

## عیب‌یابی

### مشکل: "ZARINPAL_MERCHANT_ID is not configured"
**راه حل**: Merchant ID را در settings.py تنظیم کنید

### مشکل: "Payment verification failed"
**راه حل**: 
- بررسی کنید که authority درست است
- بررسی کنید که مبلغ پرداخت شده با مبلغ درخواستی یکسان است
- در حالت Sandbox، از Merchant ID تست استفاده کنید

### مشکل: "Wallet is not active"
**راه حل**: کیف پول باید در وضعیت 'active' باشد

