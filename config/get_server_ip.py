#!/usr/bin/env python
"""
اسکریپت برای دریافت IP عمومی سرور
این اسکریپت IP عمومی سرور را دریافت می‌کند تا برای ثبت در درگاه پرداخت استفاده شود
"""
import requests
import sys

def get_public_ip():
    """دریافت IP عمومی سرور از چند منبع"""
    services = [
        'https://api.ipify.org',
        'https://ifconfig.me',
        'https://ipinfo.io/ip',
        'https://icanhazip.com',
    ]
    
    for service in services:
        try:
            response = requests.get(service, timeout=5)
            if response.status_code == 200:
                ip = response.text.strip()
                if ip and len(ip.split('.')) == 4:  # بررسی فرمت IP
                    return ip
        except Exception as e:
            continue
    
    return None

if __name__ == '__main__':
    print("در حال دریافت IP عمومی سرور...")
    ip = get_public_ip()
    
    if ip:
        print(f"\n✅ IP عمومی سرور: {ip}")
        print("\n" + "="*60)
        print("📧 ایمیل برای پشتیبانی درگاه پرداخت سپهر:")
        print("="*60)
        print(f"\nTo: ipg3@sepehrpay.com")
        print(f"Subject: ثبت IP برای ترمینال 98743989")
        print(f"\nسلام")
        print(f"\nلطفاً IP زیر را برای ترمینال 98743989 در دیتابیس ثبت کنید:")
        print(f"\nشماره ترمینال: 98743989")
        print(f"IP سرور: {ip}")
        print(f"\nبا تشکر")
        print("="*60)
    else:
        print("❌ خطا: نتوانستیم IP عمومی سرور را دریافت کنیم")
        print("لطفاً به صورت دستی IP سرور را دریافت کنید:")
        print("  - curl ifconfig.me")
        print("  - curl ipinfo.io/ip")
        sys.exit(1)

