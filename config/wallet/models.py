from django.db import models
from django.db import transaction as db_transaction
from django.core.validators import MinValueValidator
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
from django.db.models import F, Q
import uuid
import time

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
        ('wallet', 'انتقال به کیف پول انتخابی'),
        ('qr', 'انتقال با QR Code'),
        ('iban', 'انتقال با شماره شبا'),
        ('card', 'انتقال با شماره کارت'),
        ('link', 'انتقال با لینک پرداخت'),
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

