from django.db import models
from django.db import transaction as db_transaction
from django.core.validators import MinValueValidator
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
from django.db.models import F, Q
import uuid
import time
from datetime import timedelta

from users.core.models import User


class Wallet(models.Model):
    STATUS_CHOICES = [
        ('active', 'فعال'),
        ('suspended', 'تعلیق شده'),
        ('closed', 'بسته شده'),
    ]
    
    user = models.OneToOneField(
        User, 
        on_delete=models.CASCADE, 
        related_name='wallet',
        verbose_name=_('کاربر')
    )
    balance = models.DecimalField(
        max_digits=15, 
        decimal_places=2, 
        default=0,
        validators=[MinValueValidator(0)],
        verbose_name=_('موجودی')
    )
    currency = models.CharField(
        max_length=3, 
        default='IRR',
        verbose_name=_('ارز')
    )
    status = models.CharField(
        max_length=20, 
        choices=STATUS_CHOICES, 
        default='active',
        verbose_name=_('وضعیت')
    )
    wallet_address = models.CharField(
        max_length=24,
        unique=True,
        db_index=True,
        null=True,
        blank=True,
        verbose_name=_('آدرس کیف پول (24 رقمی)')
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name=_('تاریخ ایجاد'))
    updated_at = models.DateTimeField(auto_now=True, verbose_name=_('تاریخ به‌روزرسانی'))
    
    class Meta:
        db_table = 'wallets'
        verbose_name = _('کیف پول')
        verbose_name_plural = _('کیف پول‌ها')
        indexes = [
            models.Index(fields=['user']),
            models.Index(fields=['status']),
        ]
    
    def __str__(self):
        return f"Wallet {self.user.phone} - {self.balance} {self.currency}"
    
    @classmethod
    def generate_wallet_address(cls):
        """تولید آدرس 24 رقمی کیف پول (PAYA + 20 رقم)"""
        prefix = "PAYA"
        # تولید 20 رقم تصادفی
        random_part = uuid.uuid4().hex[:20].upper()
        wallet_address = f"{prefix}{random_part}"
        
        # بررسی یکتایی
        counter = 0
        while cls.objects.filter(wallet_address=wallet_address).exists():
            counter += 1
            # اگر تکراری بود، یک رقم آخر را تغییر می‌دهیم
            random_part = uuid.uuid4().hex[:20].upper()
            wallet_address = f"{prefix}{random_part}"
            if counter > 100:  # جلوگیری از حلقه بی‌نهایت
                raise Exception("Unable to generate unique wallet address")
        
        return wallet_address
    
    def can_transfer(self, amount):
        """بررسی امکان انتقال مبلغ"""
        return self.status == 'active' and self.balance >= amount
    
    def get_formatted_balance(self):
        """دریافت موجودی فرمت شده"""
        return f"{self.balance:,.0f} تومان"


class Transaction(models.Model):
    TYPE_CHOICES = [
        ('charge', 'شارژ'),
        ('debit', 'برداشت'),
        ('transfer_in', 'دریافت انتقال'),
        ('transfer_out', 'ارسال انتقال'),
        ('refund', 'بازگشت وجه'),
    ]

    TRANSFER_METHOD_CHOICES = [
        ('phone', 'انتقال با شماره موبایل'),
        ('contact', 'انتقال به مخاطب ذخیره‌شده'),
        ('wallet_address', 'انتقال به آدرس کیف پول (24 رقمی)'),
        ('qr', 'انتقال با QR Code'),
        ('special_code', 'انتقال با کد اختصاصی'),
        ('link', 'انتقال با لینک پرداخت'),
        ('nfc', 'انتقال با NFC'),
    ]
    
    STATUS_CHOICES = [
        ('pending', 'در انتظار'),
        ('completed', 'تکمیل شده'),
        ('failed', 'ناموفق'),
        ('cancelled', 'لغو شده'),
    ]
    
    transaction_id = models.CharField(
        max_length=50, 
        unique=True,
        verbose_name=_('شناسه تراکنش')
    )
    wallet = models.ForeignKey(
        Wallet, 
        on_delete=models.CASCADE, 
        related_name='transactions',
        verbose_name=_('کیف پول')
    )
    type = models.CharField(
        max_length=20, 
        choices=TYPE_CHOICES,
        verbose_name=_('نوع تراکنش')
    )
    transfer_method = models.CharField(
        max_length=30,
        choices=TRANSFER_METHOD_CHOICES,
        blank=True,
        null=True,
        verbose_name=_('روش انتقال')
    )
    amount = models.DecimalField(
        max_digits=15, 
        decimal_places=2,
        validators=[MinValueValidator(0)],
        verbose_name=_('مبلغ')
    )
    balance_before = models.DecimalField(
        max_digits=15, 
        decimal_places=2,
        verbose_name=_('موجودی قبل')
    )
    balance_after = models.DecimalField(
        max_digits=15, 
        decimal_places=2,
        verbose_name=_('موجودی بعد')
    )
    description = models.TextField(
        blank=True,
        verbose_name=_('توضیحات')
    )
    status = models.CharField(
        max_length=20, 
        choices=STATUS_CHOICES, 
        default='pending',
        verbose_name=_('وضعیت')
    )
    reference_id = models.CharField(
        max_length=100, 
        blank=True, 
        null=True,
        verbose_name=_('شناسه مرجع')
    )
    payment_method = models.CharField(
        max_length=50, 
        blank=True, 
        null=True,
        verbose_name=_('روش پرداخت')
    )
    payment_id = models.CharField(
        max_length=100, 
        blank=True, 
        null=True,
        verbose_name=_('شناسه پرداخت')
    )
    # برای تراکنش‌های انتقال
    related_transaction = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='related_transactions',
        verbose_name=_('تراکنش مرتبط')
    )
    recipient_wallet = models.ForeignKey(
        Wallet,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='received_transactions',
        verbose_name=_('کیف پول دریافت‌کننده')
    )
    metadata = models.JSONField(
        default=dict,
        blank=True,
        verbose_name=_('اطلاعات اضافی')
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name=_('تاریخ ایجاد'))
    updated_at = models.DateTimeField(auto_now=True, verbose_name=_('تاریخ به‌روزرسانی'))
    
    class Meta:
        db_table = 'transactions'
        ordering = ['-created_at']
        verbose_name = _('تراکنش')
        verbose_name_plural = _('تراکنش‌ها')
        indexes = [
            models.Index(fields=['wallet', '-created_at']),
            models.Index(fields=['transaction_id']),
            models.Index(fields=['status']),
            models.Index(fields=['type']),
            models.Index(fields=['transfer_method']),
            models.Index(fields=['created_at']),
        ]
    
    def __str__(self):
        method = f" ({self.transfer_method})" if self.transfer_method else ""
        return f"{self.transaction_id} - {self.type}{method} - {self.amount}"
    
    @classmethod
    def generate_transaction_id(cls):
        """تولید شناسه یکتا برای تراکنش"""
        return f"txn_{uuid.uuid4().hex[:12]}"


class WalletLimit(models.Model):
    """مدل برای ذخیره محدودیت‌های روزانه کاربر"""
    wallet = models.ForeignKey(
        Wallet,
        on_delete=models.CASCADE,
        related_name='limits',
        verbose_name=_('کیف پول')
    )
    date = models.DateField(
        default=timezone.now,
        verbose_name=_('تاریخ')
    )
    total_transfer_amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=0,
        verbose_name=_('مجموع مبلغ انتقال')
    )
    transfer_count = models.IntegerField(
        default=0,
        verbose_name=_('تعداد انتقال')
    )
    
    class Meta:
        db_table = 'wallet_limits'
        unique_together = ['wallet', 'date']
        verbose_name = _('محدودیت کیف پول')
        verbose_name_plural = _('محدودیت‌های کیف پول')
        indexes = [
            models.Index(fields=['wallet', 'date']),
        ]
    
    def __str__(self):
        return f"{self.wallet.user.phone} - {self.date}"


class PaymentRequest(models.Model):
    """مدل برای ذخیره درخواست‌های پرداخت برای شارژ کیف پول"""
    STATUS_CHOICES = [
        ('pending', 'در انتظار'),
        ('completed', 'تکمیل شده'),
        ('failed', 'ناموفق'),
        ('cancelled', 'لغو شده'),
    ]
    
    request_id = models.CharField(max_length=50, unique=True, verbose_name=_('شناسه درخواست'))
    wallet = models.ForeignKey(
        Wallet,
        on_delete=models.CASCADE,
        related_name='payment_requests',
        verbose_name=_('کیف پول')
    )
    amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        verbose_name=_('مبلغ')
    )
    description = models.TextField(blank=True, verbose_name=_('توضیحات'))
    gateway = models.CharField(max_length=50, default='sepehr', verbose_name=_('درگاه'))
    authority = models.CharField(max_length=100, blank=True, null=True, verbose_name=_('Authority'))
    ref_id = models.CharField(max_length=100, blank=True, null=True, verbose_name=_('Ref ID'))
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending',
        verbose_name=_('وضعیت')
    )
    transaction = models.OneToOneField(
        Transaction,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='payment_request',
        verbose_name=_('تراکنش')
    )
    callback_url = models.URLField(blank=True, null=True, verbose_name=_('آدرس بازگشت'))
    metadata = models.JSONField(default=dict, blank=True, verbose_name=_('اطلاعات اضافی'))
    created_at = models.DateTimeField(auto_now_add=True, verbose_name=_('تاریخ ایجاد'))
    updated_at = models.DateTimeField(auto_now=True, verbose_name=_('تاریخ به‌روزرسانی'))
    
    class Meta:
        db_table = 'payment_requests'
        ordering = ['-created_at']
        verbose_name = _('درخواست پرداخت')
        verbose_name_plural = _('درخواست‌های پرداخت')
        indexes = [
            models.Index(fields=['request_id']),
            models.Index(fields=['authority']),
            models.Index(fields=['status']),
        ]
    
    def __str__(self):
        return f"{self.request_id} - {self.amount} - {self.status}"
    
    @classmethod
    def generate_request_id(cls):
        """تولید شناسه یکتا برای درخواست"""
        return f"req_{uuid.uuid4().hex[:12]}"

    @classmethod
    def generate_invoice_id_for_gateway(cls):
        """
        تولید InvoiceID عددی مطابق الزامات درگاه سپهر
        حداکثر طول مجاز 20 رقم و باید یکتا باشد
        """
        # ترکیب timestamp ثانیه‌ای + 6 رقم تصادفی (uuid) => حداکثر 16 رقم
        timestamp = int(time.time())
        random_part = uuid.uuid4().int % 1000000  # عدد 6 رقمی
        invoice_id = f"{timestamp}{random_part:06d}"
        # در صورت نیاز truncate به 20 رقم
        if len(invoice_id) > 20:
            invoice_id = invoice_id[:20]
        return invoice_id


class WalletQRCode(models.Model):
    """مدل برای ذخیره QR های پرداخت/انتقال"""

    STATUS_CHOICES = [
        ('active', 'فعال'),
        ('used', 'استفاده شده'),
        ('expired', 'منقضی شده'),
        ('cancelled', 'لغو شده'),
    ]

    qr_payload = models.CharField(max_length=64, unique=True, verbose_name=_('شناسه QR'))
    wallet = models.ForeignKey(
        Wallet,
        on_delete=models.CASCADE,
        related_name='qr_codes',
        verbose_name=_('کیف پول صادرکننده')
    )
    amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name=_('مبلغ ثابت')
    )
    currency = models.CharField(max_length=3, default='IRR', verbose_name=_('ارز'))
    description = models.CharField(max_length=255, blank=True, verbose_name=_('توضیحات'))
    metadata = models.JSONField(default=dict, blank=True, verbose_name=_('اطلاعات اضافی'))
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active', verbose_name=_('وضعیت'))
    expires_at = models.DateTimeField(verbose_name=_('تاریخ انقضا'))
    used_at = models.DateTimeField(null=True, blank=True, verbose_name=_('تاریخ استفاده'))
    created_at = models.DateTimeField(auto_now_add=True, verbose_name=_('تاریخ ایجاد'))
    updated_at = models.DateTimeField(auto_now=True, verbose_name=_('تاریخ به‌روزرسانی'))
    usage_metadata = models.JSONField(default=dict, blank=True, verbose_name=_('اطلاعات استفاده'))

    class Meta:
        db_table = 'wallet_qr_codes'
        ordering = ['-created_at']
        verbose_name = _('QR پرداخت')
        verbose_name_plural = _('QR های پرداخت')
        indexes = [
            models.Index(fields=['qr_payload']),
            models.Index(fields=['wallet', 'status']),
            models.Index(fields=['expires_at']),
        ]

    def __str__(self):
        return f"{self.qr_payload} - {self.wallet.user.phone}"

    @staticmethod
    def generate_unique_payload(prefix='qr_', length=12):
        base = prefix + uuid.uuid4().hex[:length].upper()
        counter = 0
        payload = base
        while WalletQRCode.objects.filter(qr_payload=payload).exists():
            counter += 1
            payload = f"{base}{counter}"
        return payload

    @classmethod
    def create_qr(cls, wallet, amount=None, description='', expires_in=300, metadata=None):
        metadata = metadata or {}
        payload = cls.generate_unique_payload()
        expires_at = timezone.now() + timedelta(seconds=expires_in)
        qr = cls.objects.create(
            qr_payload=payload,
            wallet=wallet,
            amount=amount,
            description=description or '',
            metadata=metadata,
            expires_at=expires_at,
        )
        return qr

    def is_expired(self):
        return timezone.now() >= self.expires_at

    def mark_used(self, usage_metadata=None):
        usage_metadata = usage_metadata or {}
        self.status = 'used'
        self.used_at = timezone.now()
        if usage_metadata:
            merged = self.usage_metadata or {}
            merged.update(usage_metadata)
            self.usage_metadata = merged
        self.save(update_fields=['status', 'used_at', 'usage_metadata', 'updated_at'])

    def cancel(self):
        self.status = 'cancelled'
        self.save(update_fields=['status', 'updated_at'])


class PaymentLink(models.Model):
    """مدل برای ذخیره لینک‌های پرداخت"""
    
    STATUS_CHOICES = [
        ('active', 'فعال'),
        ('used', 'استفاده شده'),
        ('expired', 'منقضی شده'),
        ('cancelled', 'لغو شده'),
    ]
    
    link_id = models.CharField(max_length=64, unique=True, db_index=True, verbose_name=_('شناسه لینک'))
    wallet = models.ForeignKey(
        Wallet,
        on_delete=models.CASCADE,
        related_name='payment_links',
        verbose_name=_('کیف پول صادرکننده')
    )
    amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        verbose_name=_('مبلغ درخواستی')
    )
    currency = models.CharField(max_length=3, default='IRR', verbose_name=_('ارز'))
    description = models.CharField(max_length=255, blank=True, verbose_name=_('توضیحات'))
    metadata = models.JSONField(default=dict, blank=True, verbose_name=_('اطلاعات اضافی'))
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active', verbose_name=_('وضعیت'))
    expires_at = models.DateTimeField(verbose_name=_('تاریخ انقضا'))
    used_at = models.DateTimeField(null=True, blank=True, verbose_name=_('تاریخ استفاده'))
    used_by_wallet = models.ForeignKey(
        Wallet,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='used_payment_links',
        verbose_name=_('کیف پول استفاده‌کننده')
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name=_('تاریخ ایجاد'))
    updated_at = models.DateTimeField(auto_now=True, verbose_name=_('تاریخ به‌روزرسانی'))
    usage_metadata = models.JSONField(default=dict, blank=True, verbose_name=_('اطلاعات استفاده'))
    
    class Meta:
        db_table = 'payment_links'
        ordering = ['-created_at']
        verbose_name = _('لینک پرداخت')
        verbose_name_plural = _('لینک‌های پرداخت')
        indexes = [
            models.Index(fields=['link_id']),
            models.Index(fields=['wallet', 'status']),
            models.Index(fields=['expires_at']),
        ]
    
    def __str__(self):
        return f"{self.link_id} - {self.wallet.user.phone} - {self.amount}"
    
    @staticmethod
    def generate_unique_link_id(prefix='pl_', length=10):
        """
        تولید شناسه یکتا برای لینک پرداخت
        فرمت: pl_ + 10 کاراکتر (حروف و اعداد)
        مثال: pl_ECF4895E7B یا pl_84479XzQdL
        """
        import secrets
        import string
        
        # استفاده از حروف و اعداد برای تولید شناسه
        chars = string.ascii_letters + string.digits  # حروف کوچک و بزرگ + اعداد
        random_part = ''.join(secrets.choice(chars) for _ in range(length))
        base = prefix + random_part
        
        counter = 0
        link_id = base
        while PaymentLink.objects.filter(link_id=link_id).exists():
            counter += 1
            random_part = ''.join(secrets.choice(chars) for _ in range(length))
            link_id = prefix + random_part
            if counter > 1000:  # جلوگیری از حلقه بی‌نهایت
                raise Exception("Unable to generate unique link ID")
        return link_id
    
    @classmethod
    def create_link(cls, wallet, amount, description='', expires_in=3600, metadata=None):
        """ایجاد لینک پرداخت جدید"""
        metadata = metadata or {}
        link_id = cls.generate_unique_link_id()
        expires_at = timezone.now() + timedelta(seconds=expires_in)
        link = cls.objects.create(
            link_id=link_id,
            wallet=wallet,
            amount=amount,
            description=description or '',
            metadata=metadata,
            expires_at=expires_at,
        )
        return link
    
    def is_expired(self):
        return timezone.now() >= self.expires_at
    
    def mark_used(self, used_by_wallet, usage_metadata=None):
        """علامت‌گذاری لینک به عنوان استفاده شده"""
        usage_metadata = usage_metadata or {}
        self.status = 'used'
        self.used_at = timezone.now()
        self.used_by_wallet = used_by_wallet
        if usage_metadata:
            merged = self.usage_metadata or {}
            merged.update(usage_metadata)
            self.usage_metadata = merged
        self.save(update_fields=['status', 'used_at', 'used_by_wallet', 'usage_metadata', 'updated_at'])
    
    def cancel(self):
        self.status = 'cancelled'
        self.save(update_fields=['status', 'updated_at'])
    
    def get_payment_url(self, base_url=None):
        """دریافت URL کامل لینک پرداخت"""
        if base_url is None:
            from django.conf import settings
            base_url = getattr(settings, 'BASE_URL', 'https://paya.app')
        return f"{base_url}/pay/{self.link_id}"


class SpecialCode(models.Model):
    """مدل برای ذخیره کدهای اختصاصی رانندگان"""
    
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='special_code',
        verbose_name=_('کاربر (راننده)')
    )
    code = models.CharField(
        max_length=20,
        unique=True,
        db_index=True,
        verbose_name=_('کد اختصاصی')
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name=_('فعال')
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name=_('تاریخ ایجاد'))
    updated_at = models.DateTimeField(auto_now=True, verbose_name=_('تاریخ به‌روزرسانی'))
    
    class Meta:
        db_table = 'special_codes'
        verbose_name = _('کد اختصاصی')
        verbose_name_plural = _('کدهای اختصاصی')
        indexes = [
            models.Index(fields=['code']),
            models.Index(fields=['user', 'is_active']),
        ]
    
    def __str__(self):
        return f"{self.code} - {self.user.phone}"
    
    @staticmethod
    def generate_unique_code(length=5):
        """تولید کد اختصاصی یکتا (فقط اعداد)"""
        import random
        code = ''.join([str(random.randint(0, 9)) for _ in range(length)])
        
        # بررسی یکتایی
        counter = 0
        while SpecialCode.objects.filter(code=code).exists():
            counter += 1
            code = ''.join([str(random.randint(0, 9)) for _ in range(length)])
            if counter > 1000:  # جلوگیری از حلقه بی‌نهایت
                raise Exception("Unable to generate unique special code")
        
        return code
    
    @classmethod
    def create_for_user(cls, user, code=None):
        """ایجاد کد اختصاصی برای کاربر"""
        if code is None:
            code = cls.generate_unique_code()
        
        # بررسی اینکه کاربر قبلاً کد داشته باشد
        if hasattr(user, 'special_code'):
            existing = user.special_code
            existing.code = code
            existing.is_active = True
            existing.save(update_fields=['code', 'is_active', 'updated_at'])
            return existing
        
        return cls.objects.create(user=user, code=code)

