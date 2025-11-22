# راهنمای سرویس کیف پول و درگاه پرداخت

این سند نحوه پیکربندی و استفاده از سرویس کیف پول را با درگاه «پرداخت الکترونیک سپهر (صادرات)» توضیح می‌دهد. علاوه بر شارژ، هفت روش انتقال وجه داخلی که در طراحی UI آمده‌اند نیز در این نسخه پشتیبانی می‌شوند.

---

## ۱. تنظیمات محیط

در فایل `.env` یا متغیرهای محیطی موارد زیر را مقداردهی کنید:

```env
# آدرس پایه سیستم (برای callback)
BASE_URL=http://localhost:8000

# درگاه پرداخت سپهر
PAYMENT_GATEWAY_DEFAULT=sepehr

# تنظیمات درگاه سپهر
SEPEHR_ENABLED=True
SEPEHR_TERMINAL_ID=98743989
SEPEHR_TOKEN_URL=https://sepehr.shaparak.ir:8081/V1/PeymentApi/GetToken
SEPEHR_PAYMENT_URL=https://sepehr.shaparak.ir:8080/Pay
SEPEHR_ADVICE_URL=https://sepehr.shaparak.ir:8081/V1/PeymentApi/Advice
SEPEHR_ROLLBACK_URL=https://sepehr.shaparak.ir/Rest/V1/PeymentApi/Rollback
SEPEHR_TIMEOUT=10
SEPEHR_DEFAULT_PAYLOAD=
```

---

## ۲. جریان شارژ با درگاه سپهر

### ۲.۱ درخواست توکن
Endpoint: `POST /api/wallet/charge-gateway/`

```json
{
  "amount": 100000,
  "description": "شارژ کیف پول",
  "callback_url": "https://example.com/payment/callback"
}
```

پاسخ موفق:
```json
{
  "request_id": "req_abcd1234",
  "payment_url": "https://sepehr.shaparak.ir:8080/Pay?token=...&TerminalID=...&getMethod=1",
  "payment_form": {
    "action_url": "https://sepehr.shaparak.ir:8080/Pay",
    "terminal_id": "98743989",
    "token": "AccessTokenFromSepehr",
    "get_method": "1",
    "method": "POST"
  },
  "authority": "AccessTokenFromSepehr",
  "amount": 100000,
  "gateway": "sepehr",
  "expires_at": "2025-01-01T12:30:00Z"
}
```

### ۲.۲ هدایت کاربر به صفحه پرداخت
کاربر را به `payment_url` هدایت کنید (GET). صفحه سپهر باز می‌شود.

### ۲.۳ دریافت Callback
`POST /api/wallet/payment-callback/`

در حالت سپهر، بدنه‌ی callback شامل `respcode`, `invoiceid`, `digitalreceipt` و ... است. سرویس:
- صحت respcode را بررسی می‌کند.
- سرویس Advice سپهر را با `digitalreceipt` صدا می‌زند.
- در صورت موفقیت، کیف پول را شارژ کرده و پاسخ موفق می‌دهد.

### ۲.۴ بررسی وضعیت
`GET /api/wallet/payment-status/{request_id}/`

پاسخ نمونه:
```json
{
  "request_id": "req_abcd1234",
  "amount": 100000,
  "status": "completed",
  "gateway": "sepehr",
  "authority": "AccessTokenFromSepehr",
  "ref_id": "SepehrDigitalReceipt",
  "transaction_id": "txn_a1b2c3",
  "balance_after": 150000,
  "created_at": "...",
  "updated_at": "..."
}
```

---

## ۳. هفت روش انتقال وجه (طبق طراحی)

Endpoint مشترک: `POST /api/wallet/transfer/`

| مقدار `method` | توضیح | کلیدهای ورودی مهم |
| --- | --- | --- |
| `phone` | انتقال به شماره موبایل آزاد | `recipient_phone` |
| `contact` | انتقال به مخاطب ذخیره‌شده | `recipient_phone` و متادیتای مخاطب |
| `wallet` | انتقال به شناسه کیف پول منتخب | `recipient_wallet_id` |
| `qr` | انتقال با اسکن QR | `metadata.qr_payload` |
| `iban` | انتقال به شماره شبا | `metadata.iban` |
| `card` | انتقال به شماره کارت | `metadata.card_number` |
| `link` | انتقال از طریق لینک پرداخت داخلی | `metadata.payment_link_id` |

### نمونه درخواست (انتقال با شماره موبایل)
```json
{
  "method": "phone",
  "recipient_phone": "+989121234567",
  "amount": 250000,
  "description": "بازپرداخت قرض",
  "metadata": {
    "note": "حواله فوری"
  }
}
```

### نمونه درخواست (انتقال به کیف پول انتخابی)
```json
{
  "method": "wallet",
  "recipient_wallet_id": 42,
  "amount": 500000,
  "description": "تسویه کیف پول"
}
```

### پاسخ موفق
```json
{
  "transaction_id": "txn_123abc",
  "amount": 250000,
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
    "recipient_wallet_id": 42,
    "note": "حواله فوری"
  }
}
```

> برای همه روش‌ها فیلد `description` اختیاری است و در صورت ارسال، داخل تراکنش ذخیره می‌شود.

---

## ۴. ساخت خودکار کیف پول

از این نسخه به بعد، به محض ایجاد کاربر جدید (ثبت‌نام / import)، با سیگنال `post_save` یک کیف پول با وضعیت `active` و موجودی صفر ساخته می‌شود. لذا در لایه اپلیکیشن فقط کافی است کاربر ایجاد شود؛ نیازی به API جداگانه نیست مگر برای تغییر ارز یا وضعیت.

---

## ۵. نکات عیب‌یابی

- **respcode != 0 (سپهر)**: تراکنش از سمت درگاه لغو شده است. اطلاعات callback در فیلد `metadata` ذخیره می‌شود.
- **عدم وجود digitalreceipt**: بررسی کنید callback را با متد POST دریافت می‌کنید. می‌توانید برای تست لوکال داده‌های درگاه را شبیه‌سازی کرده و این فیلد را به صورت دستی ارسال کنید.
- **Selected gateway is currently disabled**: اطمینان حاصل کنید `ENABLED=True` و مقادیر مرچنت/ترمینال تنظیم شده‌اند.
- **Wallet already exists**: از آنجا که کیف پول خودکار ساخته می‌شود، در تست‌ها و seedها به جای `Wallet.objects.create` از `user.wallet` استفاده کنید.

---

## ۶. چک‌لیست نهایی قبل از تحویل

- [ ] `PAYMENT_GATEWAY_DEFAULT` و مقادیر مرچنت در `.env` تنظیم شده است.
- [ ] کاربر جدید → کیف پول فعال به صورت خودکار ساخته می‌شود.
- [ ] شارژ از طریق درگاه سپهر با مسیر Token → Pay → Callback → Advice موفق است.
- [ ] انتقال وجه برای هر هفت روش، با متادیتای مرتبط تست شده است.
- [ ] مستندات فرانت و QA به‌روز شده‌اند (لیست متدها و فیلدهای لازم).

---

در صورت نیاز به نمونه‌هایی برای roll-back یا سرویس‌های دیگر سپهر، فایل `taxi/راهنماي_راه_اندازي_درگاه_پرداخت_اينترنتي_پرداخت_الکترونیک_سپهر_4.txt` شامل جزئیات کامل وب‌سرویس‌ها است.
