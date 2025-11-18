#!/usr/bin/env python
"""
اسکریپت برای تولید کلید رمزنگاری امن
استفاده: python generate_encryption_key.py
"""
import secrets
import base64
import sys

def generate_encryption_key():
    """
    تولید کلید رمزنگاری 32 بایتی (256 بیت) و تبدیل به base64
    """
    # تولید کلید 32 بایتی (256 بیت)
    key_bytes = secrets.token_bytes(32)
    
    # تبدیل به base64 برای ذخیره‌سازی راحت‌تر
    key_base64 = base64.b64encode(key_bytes).decode('utf-8')
    
    # همچنین یک نسخه hex برای استفاده مستقیم
    key_hex = key_bytes.hex()
    
    return key_base64, key_hex, key_bytes


if __name__ == '__main__':
    print("=" * 60)
    print("تولید کلید رمزنگاری برای ENCRYPTION_KEY")
    print("=" * 60)
    print()
    
    key_base64, key_hex, key_bytes = generate_encryption_key()
    
    print("✅ کلید تولید شد!")
    print()
    print("📋 برای استفاده در .env یا environment variable:")
    print(f"ENCRYPTION_KEY={key_base64}")
    print()
    print("📋 یا به صورت hex (32 کاراکتر):")
    print(f"ENCRYPTION_KEY={key_hex}")
    print()
    print("⚠️  نکات مهم:")
    print("1. این کلید را در جای امن نگه دارید")
    print("2. هرگز در Git commit نکنید")
    print("3. اگر کلید را گم کنید، داده‌های رمزنگاری شده قابل بازیابی نیستند")
    print("4. در production حتماً از environment variable استفاده کنید")
    print()
    print("=" * 60)
    
    # کپی به clipboard (اختیاری - فقط در صورت وجود pyperclip)
    try:
        import pyperclip
        pyperclip.copy(key_base64)
        print("✅ کلید به clipboard کپی شد!")
    except ImportError:
        pass



