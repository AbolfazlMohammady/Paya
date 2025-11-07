from django.contrib import admin
from .models import Wallet, Transaction, WalletLimit, PaymentRequest


@admin.register(Wallet)
class WalletAdmin(admin.ModelAdmin):
    list_display = ['id', 'user', 'balance', 'currency', 'status', 'created_at']
    list_filter = ['status', 'currency', 'created_at']
    search_fields = ['user__phone', 'user__fullname']
    readonly_fields = ['created_at', 'updated_at']
    ordering = ['-created_at']


@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = [
        'transaction_id', 'wallet', 'type', 'amount', 
        'balance_after', 'status', 'created_at'
    ]
    list_filter = ['type', 'status', 'created_at']
    search_fields = ['transaction_id', 'wallet__user__phone', 'reference_id']
    readonly_fields = [
        'transaction_id', 'created_at', 'updated_at',
        'balance_before', 'balance_after'
    ]
    ordering = ['-created_at']
    date_hierarchy = 'created_at'


@admin.register(WalletLimit)
class WalletLimitAdmin(admin.ModelAdmin):
    list_display = ['wallet', 'date', 'total_transfer_amount', 'transfer_count']
    list_filter = ['date']
    search_fields = ['wallet__user__phone']
    ordering = ['-date', '-total_transfer_amount']


@admin.register(PaymentRequest)
class PaymentRequestAdmin(admin.ModelAdmin):
    list_display = [
        'request_id', 'wallet', 'amount', 'gateway', 
        'status', 'authority', 'created_at'
    ]
    list_filter = ['status', 'gateway', 'created_at']
    search_fields = ['request_id', 'authority', 'wallet__user__phone']
    readonly_fields = ['request_id', 'created_at', 'updated_at']
    ordering = ['-created_at']
    date_hierarchy = 'created_at'

