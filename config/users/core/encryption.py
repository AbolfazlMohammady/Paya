"""
ماژول رمزنگاری برای داده‌های حساس
استفاده از AES-GCM برای رمزنگاری داده‌ها طبق الزامات کاشف
"""
import os
import base64
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.backends import default_backend
from django.conf import settings
import hashlib


class EncryptionService:
    """
    سرویس رمزنگاری با استفاده از AES-GCM
    طبق الزامات کاشف: AES-GCM با کلید 256 بیت
    """
    
    def __init__(self):
        # کلید رمزنگاری از environment variable یا settings
        key_str = getattr(settings, 'ENCRYPTION_KEY', None)
        if not key_str:
            # در production باید از environment variable استفاده شود
            key_str = os.environ.get('ENCRYPTION_KEY')
            if not key_str:
                raise ValueError("ENCRYPTION_KEY must be set in settings or environment")
        
        # تبدیل کلید به bytes (32 بایت = 256 بیت)
        if isinstance(key_str, str):
            # اگر کلید string است، از SHA-256 برای تبدیل به 32 بایت استفاده می‌کنیم
            key_bytes = hashlib.sha256(key_str.encode()).digest()
        else:
            key_bytes = key_str
        
        if len(key_bytes) != 32:
            raise ValueError("Encryption key must be 32 bytes (256 bits)")
        
        self.key = key_bytes
        self.aesgcm = AESGCM(self.key)
    
    def encrypt(self, plaintext: str) -> str:
        """
        رمزنگاری متن با AES-GCM
        Returns: base64 encoded string شامل nonce + ciphertext + tag
        """
        if not plaintext:
            return ""
        
        # تولید nonce یکتا (12 بایت برای AES-GCM)
        nonce = os.urandom(12)
        
        # رمزنگاری
        plaintext_bytes = plaintext.encode('utf-8')
        ciphertext = self.aesgcm.encrypt(nonce, plaintext_bytes, None)
        
        # ترکیب nonce + ciphertext (tag در ciphertext است)
        encrypted_data = nonce + ciphertext
        
        # تبدیل به base64 برای ذخیره‌سازی
        return base64.b64encode(encrypted_data).decode('utf-8')
    
    def decrypt(self, encrypted_data: str) -> str:
        """
        رمزگشایی متن رمزنگاری شده
        """
        if not encrypted_data:
            return ""
        
        try:
            # تبدیل از base64
            encrypted_bytes = base64.b64decode(encrypted_data.encode('utf-8'))
            
            # جدا کردن nonce (12 بایت اول) و ciphertext
            nonce = encrypted_bytes[:12]
            ciphertext = encrypted_bytes[12:]
            
            # رمزگشایی
            plaintext_bytes = self.aesgcm.decrypt(nonce, ciphertext, None)
            
            return plaintext_bytes.decode('utf-8')
        except Exception as e:
            raise ValueError(f"Decryption failed: {str(e)}")
    
    @staticmethod
    def hash_data(data: str) -> str:
        """
        Hash کردن داده با SHA-256
        """
        return hashlib.sha256(data.encode('utf-8')).hexdigest()
    
    @staticmethod
    def generate_key() -> str:
        """
        تولید کلید رمزنگاری جدید (32 بایت)
        برای استفاده در setup
        """
        key = os.urandom(32)
        return base64.b64encode(key).decode('utf-8')


# Singleton instance
_encryption_service = None

def get_encryption_service() -> EncryptionService:
    """دریافت instance سرویس رمزنگاری"""
    global _encryption_service
    if _encryption_service is None:
        _encryption_service = EncryptionService()
    return _encryption_service


