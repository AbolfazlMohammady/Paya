# راهنمای کامل: تنظیم ENCRYPTION_KEY

## مشکل فعلی

```
ModuleNotFoundError: No module named 'cryptography'
```

## راه حل

### مرحله 1: نصب cryptography

```bash
# نصب cryptography در Docker
docker compose exec django pip install cryptography

# یا نصب تمام requirements (cryptography در requirements.txt اضافه شده)
docker compose exec django pip install -r requirements.txt
```

### مرحله 2: تولید کلید رمزنگاری

#### روش 1: استفاده از Python در Docker (ساده‌ترین)

```bash
docker compose exec django python -c "import secrets, base64; print(base64.b64encode(secrets.token_bytes(32)).decode())"
```

خروجی چیزی شبیه این خواهد بود:
```
xK9mP2vQ7wR4tY8uI0oP3aS6dF1gH5jK8lM2nB9vC4xZ7=
```

#### روش 2: استفاده از اسکریپت

```bash
# کپی فایل generate_encryption_key.py به داخل container
docker compose exec django python /app/generate_encryption_key.py
```

#### روش 3: استفاده از OpenSSL (اگر نصب است)

```bash
openssl rand -base64 32
```

### مرحله 3: اضافه کردن کلید به .env

فایل `.env` در پوشه `config/` را باز کنید و این خط را اضافه کنید:

```env
ENCRYPTION_KEY=xK9mP2vQ7wR4tY8uI0oP3aS6dF1gH5jK8lM2nB9vC4xZ7=
```

**⚠️ مهم**: کلید بالا فقط یک مثال است! باید کلید خودتان را تولید کنید.

### مرحله 4: Restart کردن Container

```bash
docker compose restart django
```

### مرحله 5: تست

```bash
# بررسی اینکه کلید خوانده می‌شود
docker compose exec django python manage.py shell -c "from django.conf import settings; print('ENCRYPTION_KEY:', settings.ENCRYPTION_KEY[:10] + '...')"

# اجرای migration
docker compose exec django python manage.py makemigrations
docker compose exec django python manage.py migrate
```

## مثال کامل (Copy & Paste)

```bash
# 1. نصب cryptography
docker compose exec django pip install cryptography

# 2. تولید کلید
KEY=$(docker compose exec -T django python -c "import secrets, base64; print(base64.b64encode(secrets.token_bytes(32)).decode())")

# 3. نمایش کلید
echo "کلید تولید شده:"
echo $KEY

# 4. اضافه کردن به .env (دستور زیر را اجرا کنید)
echo "ENCRYPTION_KEY=$KEY" >> config/.env

# 5. بررسی .env
cat config/.env | grep ENCRYPTION_KEY

# 6. Restart
docker compose restart django
```

## بررسی نهایی

```bash
# بررسی import
docker compose exec django python -c "from users.core.encryption import get_encryption_service; print('✅ OK')"

# تست رمزنگاری
docker compose exec django python manage.py shell
>>> from users.core.encryption import get_encryption_service
>>> enc = get_encryption_service()
>>> encrypted = enc.encrypt("test")
>>> print(enc.decrypt(encrypted))
test
```

## نکات مهم

1. ✅ کلید را در `.env` نگه دارید (در `.gitignore` است)
2. ❌ هرگز کلید را در Git commit نکنید
3. ✅ در production از environment variable استفاده کنید
4. ⚠️ اگر کلید را گم کنید، داده‌های رمزنگاری شده قابل بازیابی نیستند

## ساختار فایل .env

```env
# سایر تنظیمات...
SECRET_KEY=your-secret-key
DEBUG=False

# کلید رمزنگاری (تولید شده)
ENCRYPTION_KEY=xK9mP2vQ7wR4tY8uI0oP3aS6dF1gH5jK8lM2nB9vC4xZ7=
```

## اگر هنوز خطا می‌دهد

1. بررسی کنید که cryptography نصب شده:
   ```bash
   docker compose exec django pip list | grep cryptography
   ```

2. بررسی کنید که .env خوانده می‌شود:
   ```bash
   docker compose exec django python -c "from django.conf import settings; print(hasattr(settings, 'ENCRYPTION_KEY'))"
   ```

3. Rebuild container (در صورت نیاز):
   ```bash
   docker compose build django
   docker compose up -d django
   ```






