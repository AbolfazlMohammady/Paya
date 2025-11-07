"""
سرویس یکپارچه‌سازی با درگاه‌های پرداخت
"""
import requests
from django.conf import settings
from decimal import Decimal
import uuid


class PaymentGatewayService:
    """سرویس برای ارتباط با درگاه‌های پرداخت"""
    
    # تنظیمات درگاه‌ها (باید در settings.py تنظیم شود)
    ZARINPAL_MERCHANT_ID = getattr(settings, 'ZARINPAL_MERCHANT_ID', '')
    ZARINPAL_SANDBOX = getattr(settings, 'ZARINPAL_SANDBOX', True)
    
    # URLهای زرین‌پال
    ZARINPAL_REQUEST_URL = 'https://api.zarinpal.com/pg/v4/payment/request.json'
    ZARINPAL_VERIFY_URL = 'https://api.zarinpal.com/pg/v4/payment/verify.json'
    ZARINPAL_START_PAY_URL = 'https://www.zarinpal.com/pg/StartPay/'
    
    # برای حالت sandbox - URLها به صورت دینامیک تنظیم می‌شوند
    @classmethod
    def _get_urls(cls):
        """دریافت URLهای مناسب بر اساس حالت Sandbox"""
        if cls.ZARINPAL_SANDBOX:
            return {
                'request': 'https://sandbox.zarinpal.com/pg/v4/payment/request.json',
                'verify': 'https://sandbox.zarinpal.com/pg/v4/payment/verify.json',
                'start_pay': 'https://sandbox.zarinpal.com/pg/StartPay/'
            }
        else:
            return {
                'request': 'https://api.zarinpal.com/pg/v4/payment/request.json',
                'verify': 'https://api.zarinpal.com/pg/v4/payment/verify.json',
                'start_pay': 'https://www.zarinpal.com/pg/StartPay/'
            }
    
    @classmethod
    def create_payment_request(cls, amount, description, callback_url, user_phone=None, user_email=None):
        """
        ایجاد درخواست پرداخت در زرین‌پال
        
        Args:
            amount: مبلغ به تومان
            description: توضیحات
            callback_url: آدرس بازگشت بعد از پرداخت
            user_phone: شماره تلفن کاربر (اختیاری)
            user_email: ایمیل کاربر (اختیاری)
        
        Returns:
            dict: شامل authority و payment_url
        """
        if not cls.ZARINPAL_MERCHANT_ID:
            raise ValueError("ZARINPAL_MERCHANT_ID is not configured")
        
        # تبدیل مبلغ به تومان (زرین‌پال مبلغ را به تومان می‌خواهد)
        amount_toman = int(amount)
        
        data = {
            "merchant_id": cls.ZARINPAL_MERCHANT_ID,
            "amount": amount_toman,
            "description": description,
            "callback_url": callback_url,
        }
        
        # اضافه کردن metadata در صورت وجود
        metadata = {}
        if user_phone:
            metadata["mobile"] = str(user_phone)
        if user_email:
            metadata["email"] = user_email
        
        if metadata:
            data["metadata"] = metadata
        
        try:
            urls = cls._get_urls()
            response = requests.post(urls['request'], json=data, timeout=10)
            response.raise_for_status()
            result = response.json()
            
            if result.get('data') and result['data'].get('code') == 100:
                authority = result['data']['authority']
                urls = cls._get_urls()
                payment_url = f"{urls['start_pay']}{authority}"
                
                return {
                    'success': True,
                    'authority': authority,
                    'payment_url': payment_url,
                    'gateway': 'zarinpal'
                }
            else:
                error_message = result.get('errors', {}).get('message', 'Payment request failed')
                return {
                    'success': False,
                    'error': error_message
                }
        except requests.exceptions.RequestException as e:
            return {
                'success': False,
                'error': f'Connection error: {str(e)}'
            }
        except Exception as e:
            return {
                'success': False,
                'error': f'Unexpected error: {str(e)}'
            }
    
    @classmethod
    def verify_payment(cls, authority, amount):
        """
        بررسی و تایید پرداخت در زرین‌پال
        
        Args:
            authority: کد authority از زرین‌پال
            amount: مبلغ پرداخت شده
        
        Returns:
            dict: شامل ref_id در صورت موفقیت
        """
        if not cls.ZARINPAL_MERCHANT_ID:
            raise ValueError("ZARINPAL_MERCHANT_ID is not configured")
        
        amount_toman = int(amount)
        
        data = {
            "merchant_id": cls.ZARINPAL_MERCHANT_ID,
            "authority": authority,
            "amount": amount_toman
        }
        
        try:
            urls = cls._get_urls()
            response = requests.post(urls['verify'], json=data, timeout=10)
            response.raise_for_status()
            result = response.json()
            
            if result.get('data') and result['data'].get('code') == 100:
                ref_id = result['data'].get('ref_id')
                return {
                    'success': True,
                    'ref_id': ref_id,
                    'gateway': 'zarinpal'
                }
            else:
                error_code = result.get('data', {}).get('code', 'unknown')
                error_message = result.get('errors', {}).get('message', 'Payment verification failed')
                return {
                    'success': False,
                    'error': error_message,
                    'error_code': error_code
                }
        except requests.exceptions.RequestException as e:
            return {
                'success': False,
                'error': f'Connection error: {str(e)}'
            }
        except Exception as e:
            return {
                'success': False,
                'error': f'Unexpected error: {str(e)}'
            }

