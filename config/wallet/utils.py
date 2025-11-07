"""
ابزارهای کمکی برای سرویس کیف پول
"""
from django.db import transaction as db_transaction
from django.utils import timezone
from django.core.cache import cache
from django.db.models import F, Q, Sum
from decimal import Decimal
from datetime import timedelta

from .models import Wallet, Transaction, WalletLimit


# قوانین کسب‌وکار
MIN_TRANSFER_AMOUNT = Decimal('10000')  # حداقل موجودی برای انتقال
MAX_DAILY_TRANSFER_AMOUNT = Decimal('5000000')  # حداکثر انتقال در روز
MAX_DAILY_TRANSFER_COUNT = 10  # حداکثر تعداد انتقال در روز


def get_or_create_wallet_limit(wallet, date=None):
    """دریافت یا ایجاد محدودیت روزانه"""
    if date is None:
        date = timezone.now().date()
    
    limit, created = WalletLimit.objects.get_or_create(
        wallet=wallet,
        date=date,
        defaults={
            'total_transfer_amount': Decimal('0'),
            'transfer_count': 0
        }
    )
    return limit


def check_transfer_limits(wallet, amount):
    """بررسی محدودیت‌های انتقال"""
    today_limit = get_or_create_wallet_limit(wallet)
    
    # بررسی حداکثر مبلغ روزانه
    if today_limit.total_transfer_amount + amount > MAX_DAILY_TRANSFER_AMOUNT:
        return False, "Daily transfer limit exceeded"
    
    # بررسی حداکثر تعداد انتقال روزانه
    if today_limit.transfer_count >= MAX_DAILY_TRANSFER_COUNT:
        return False, "Daily transfer count limit exceeded"
    
    return True, None


def update_transfer_limits(wallet, amount):
    """به‌روزرسانی محدودیت‌های انتقال"""
    today_limit = get_or_create_wallet_limit(wallet)
    WalletLimit.objects.filter(id=today_limit.id).update(
        total_transfer_amount=F('total_transfer_amount') + amount,
        transfer_count=F('transfer_count') + 1
    )


def get_wallet_lock_key(wallet_id):
    """کلید cache برای lock کردن کیف پول"""
    return f"wallet_lock_{wallet_id}"


def acquire_wallet_lock(wallet_id, timeout=30):
    """قفل کردن کیف پول برای جلوگیری از race condition"""
    lock_key = get_wallet_lock_key(wallet_id)
    return cache.add(lock_key, True, timeout)


def release_wallet_lock(wallet_id):
    """آزاد کردن قفل کیف پول"""
    lock_key = get_wallet_lock_key(wallet_id)
    cache.delete(lock_key)


@db_transaction.atomic
def charge_wallet(wallet, amount, description='', payment_method=None, payment_id=None):
    """
    شارژ کیف پول
    """
    # قفل کردن کیف پول
    if not acquire_wallet_lock(wallet.id):
        raise Exception("Wallet is currently being processed. Please try again.")
    
    try:
        # دریافت آخرین موجودی
        wallet.refresh_from_db()
        balance_before = wallet.balance
        balance_after = balance_before + amount
        
        # ایجاد تراکنش
        transaction = Transaction.objects.create(
            transaction_id=Transaction.generate_transaction_id(),
            wallet=wallet,
            type='charge',
            amount=amount,
            balance_before=balance_before,
            balance_after=balance_after,
            description=description or 'شارژ کیف پول',
            status='completed',
            payment_method=payment_method,
            payment_id=payment_id
        )
        
        # به‌روزرسانی موجودی
        wallet.balance = balance_after
        wallet.save(update_fields=['balance', 'updated_at'])
        
        return transaction
    finally:
        release_wallet_lock(wallet.id)


@db_transaction.atomic
def debit_wallet(wallet, amount, description='', reference_id=None):
    """
    برداشت از کیف پول
    """
    # قفل کردن کیف پول
    if not acquire_wallet_lock(wallet.id):
        raise Exception("Wallet is currently being processed. Please try again.")
    
    try:
        # بررسی موجودی
        wallet.refresh_from_db()
        if wallet.balance < amount:
            raise ValueError("Insufficient balance")
        
        if wallet.status != 'active':
            raise ValueError("Wallet is not active")
        
        balance_before = wallet.balance
        balance_after = balance_before - amount
        
        # ایجاد تراکنش
        transaction = Transaction.objects.create(
            transaction_id=Transaction.generate_transaction_id(),
            wallet=wallet,
            type='debit',
            amount=amount,
            balance_before=balance_before,
            balance_after=balance_after,
            description=description or 'برداشت از کیف پول',
            status='completed',
            reference_id=reference_id
        )
        
        # به‌روزرسانی موجودی
        wallet.balance = balance_after
        wallet.save(update_fields=['balance', 'updated_at'])
        
        return transaction
    finally:
        release_wallet_lock(wallet.id)


@db_transaction.atomic
def transfer_money(sender_wallet, recipient_wallet, amount, description=''):
    """
    انتقال وجه بین دو کیف پول
    """
    # قفل کردن هر دو کیف پول (به ترتیب ID برای جلوگیری از deadlock)
    wallet_ids = sorted([sender_wallet.id, recipient_wallet.id])
    
    locks_acquired = []
    try:
        for wallet_id in wallet_ids:
            if not acquire_wallet_lock(wallet_id):
                raise Exception("Wallet is currently being processed. Please try again.")
            locks_acquired.append(wallet_id)
        
        # بررسی موجودی فرستنده
        sender_wallet.refresh_from_db()
        if sender_wallet.balance < amount:
            raise ValueError("Insufficient balance")
        
        if sender_wallet.status != 'active':
            raise ValueError("Sender wallet is not active")
        
        if recipient_wallet.status != 'active':
            raise ValueError("Recipient wallet is not active")
        
        # بررسی محدودیت‌های انتقال
        can_transfer, error_msg = check_transfer_limits(sender_wallet, amount)
        if not can_transfer:
            raise ValueError(error_msg)
        
        # محاسبه موجودی‌ها
        sender_balance_before = sender_wallet.balance
        sender_balance_after = sender_balance_before - amount
        
        recipient_wallet.refresh_from_db()
        recipient_balance_before = recipient_wallet.balance
        recipient_balance_after = recipient_balance_before + amount
        
        # ایجاد تراکنش فرستنده
        sender_transaction = Transaction.objects.create(
            transaction_id=Transaction.generate_transaction_id(),
            wallet=sender_wallet,
            type='transfer_out',
            amount=amount,
            balance_before=sender_balance_before,
            balance_after=sender_balance_after,
            description=description or 'انتقال وجه',
            status='completed',
            recipient_wallet=recipient_wallet
        )
        
        # ایجاد تراکنش دریافت‌کننده
        recipient_transaction = Transaction.objects.create(
            transaction_id=Transaction.generate_transaction_id(),
            wallet=recipient_wallet,
            type='transfer_in',
            amount=amount,
            balance_before=recipient_balance_before,
            balance_after=recipient_balance_after,
            description=description or 'دریافت انتقال وجه',
            status='completed',
            related_transaction=sender_transaction
        )
        
        # لینک کردن تراکنش‌ها
        sender_transaction.related_transaction = recipient_transaction
        sender_transaction.save(update_fields=['related_transaction'])
        
        # به‌روزرسانی موجودی‌ها
        sender_wallet.balance = sender_balance_after
        sender_wallet.save(update_fields=['balance', 'updated_at'])
        
        recipient_wallet.balance = recipient_balance_after
        recipient_wallet.save(update_fields=['balance', 'updated_at'])
        
        # به‌روزرسانی محدودیت‌های انتقال
        update_transfer_limits(sender_wallet, amount)
        
        return sender_transaction, recipient_transaction
    finally:
        # آزاد کردن قفل‌ها
        for wallet_id in locks_acquired:
            release_wallet_lock(wallet_id)

