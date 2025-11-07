from rest_framework import serializers
from phonenumber_field.serializerfields import PhoneNumberField
from decimal import Decimal

from .models import Wallet, Transaction, WalletLimit
from users.core.models import User


class WalletSerializer(serializers.ModelSerializer):
    """Serializer برای نمایش اطلاعات کیف پول"""
    formatted_balance = serializers.SerializerMethodField()
    
    class Meta:
        model = Wallet
        fields = [
            'id', 'balance', 'currency', 'status', 
            'created_at', 'updated_at', 'formatted_balance'
        ]
        read_only_fields = ['id', 'balance', 'created_at', 'updated_at']
    
    def get_formatted_balance(self, obj):
        return obj.get_formatted_balance()


class WalletCreateSerializer(serializers.Serializer):
    """Serializer برای ایجاد کیف پول"""
    currency = serializers.CharField(max_length=3, default='IRR', required=False)
    
    def validate_currency(self, value):
        if value not in ['IRR']:
            raise serializers.ValidationError("Currently only IRR currency is supported")
        return value


class ChargeSerializer(serializers.Serializer):
    """Serializer برای شارژ کیف پول"""
    amount = serializers.DecimalField(
        max_digits=15, 
        decimal_places=2,
        min_value=Decimal('1000')
    )
    description = serializers.CharField(max_length=500, required=False, allow_blank=True)
    payment_method = serializers.CharField(max_length=50, required=False, allow_blank=True)
    payment_id = serializers.CharField(max_length=100, required=False, allow_blank=True)
    
    def validate_amount(self, value):
        if value <= 0:
            raise serializers.ValidationError("Amount must be greater than zero")
        return value


class DebitSerializer(serializers.Serializer):
    """Serializer برای برداشت از کیف پول"""
    amount = serializers.DecimalField(
        max_digits=15, 
        decimal_places=2,
        min_value=Decimal('1000')
    )
    description = serializers.CharField(max_length=500, required=False, allow_blank=True)
    reference_id = serializers.CharField(max_length=100, required=False, allow_blank=True)
    
    def validate_amount(self, value):
        if value <= 0:
            raise serializers.ValidationError("Amount must be greater than zero")
        return value


class TransferSerializer(serializers.Serializer):
    """Serializer برای انتقال وجه"""
    recipient_phone = PhoneNumberField(region='IR')
    amount = serializers.DecimalField(
        max_digits=15, 
        decimal_places=2,
        min_value=Decimal('10000')
    )
    description = serializers.CharField(max_length=500, required=False, allow_blank=True)
    
    def validate_recipient_phone(self, value):
        return str(value)
    
    def validate_amount(self, value):
        if value < 10000:
            raise serializers.ValidationError("Minimum transfer amount is 10,000 IRR")
        return value


class TransactionSerializer(serializers.ModelSerializer):
    """Serializer برای نمایش تراکنش"""
    type_display = serializers.CharField(source='get_type_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    recipient_info = serializers.SerializerMethodField()
    
    class Meta:
        model = Transaction
        fields = [
            'id', 'transaction_id', 'type', 'type_display',
            'amount', 'balance_before', 'balance_after',
            'description', 'status', 'status_display',
            'reference_id', 'payment_method', 'payment_id',
            'recipient_info', 'created_at', 'updated_at'
        ]
        read_only_fields = fields
    
    def get_recipient_info(self, obj):
        """اطلاعات دریافت‌کننده برای تراکنش‌های انتقال"""
        if obj.type == 'transfer_out' and obj.recipient_wallet:
            return {
                'phone': str(obj.recipient_wallet.user.phone),
                'fullname': obj.recipient_wallet.user.fullname or ''
            }
        elif obj.type == 'transfer_in' and obj.related_transaction:
            sender_wallet = obj.related_transaction.wallet
            return {
                'phone': str(sender_wallet.user.phone),
                'fullname': sender_wallet.user.fullname or ''
            }
        return None


class TransactionDetailSerializer(TransactionSerializer):
    """Serializer برای جزئیات کامل تراکنش"""
    wallet_info = serializers.SerializerMethodField()
    
    class Meta(TransactionSerializer.Meta):
        fields = TransactionSerializer.Meta.fields + ['wallet_info']
    
    def get_wallet_info(self, obj):
        return {
            'id': obj.wallet.id,
            'user_phone': str(obj.wallet.user.phone),
            'user_fullname': obj.wallet.user.fullname or ''
        }


class BalanceSerializer(serializers.Serializer):
    """Serializer برای نمایش موجودی"""
    balance = serializers.DecimalField(max_digits=15, decimal_places=2)
    currency = serializers.CharField(max_length=3)
    formatted_balance = serializers.CharField()


class ChargeResponseSerializer(serializers.Serializer):
    """Serializer برای پاسخ شارژ"""
    transaction_id = serializers.CharField()
    amount = serializers.DecimalField(max_digits=15, decimal_places=2)
    balance_after = serializers.DecimalField(max_digits=15, decimal_places=2)
    status = serializers.CharField()
    created_at = serializers.DateTimeField()


class DebitResponseSerializer(serializers.Serializer):
    """Serializer برای پاسخ برداشت"""
    transaction_id = serializers.CharField()
    amount = serializers.DecimalField(max_digits=15, decimal_places=2)
    balance_after = serializers.DecimalField(max_digits=15, decimal_places=2)
    status = serializers.CharField()
    created_at = serializers.DateTimeField()


class TransferResponseSerializer(serializers.Serializer):
    """Serializer برای پاسخ انتقال"""
    transaction_id = serializers.CharField()
    amount = serializers.DecimalField(max_digits=15, decimal_places=2)
    recipient = serializers.DictField()
    balance_after = serializers.DecimalField(max_digits=15, decimal_places=2)
    status = serializers.CharField()
    created_at = serializers.DateTimeField()


class GatewayChargeSerializer(serializers.Serializer):
    """Serializer برای شارژ از طریق درگاه پرداخت"""
    amount = serializers.DecimalField(
        max_digits=15,
        decimal_places=2,
        min_value=Decimal('1000')
    )
    description = serializers.CharField(max_length=500, required=False, allow_blank=True)
    gateway = serializers.CharField(max_length=50, default='zarinpal', required=False)
    callback_url = serializers.URLField(required=False, allow_blank=True)
    
    def validate_amount(self, value):
        if value <= 0:
            raise serializers.ValidationError("Amount must be greater than zero")
        return value


class GatewayChargeResponseSerializer(serializers.Serializer):
    """Serializer برای پاسخ درخواست شارژ از درگاه"""
    request_id = serializers.CharField()
    payment_url = serializers.URLField()
    authority = serializers.CharField()
    amount = serializers.DecimalField(max_digits=15, decimal_places=2)
    gateway = serializers.CharField()
    expires_at = serializers.DateTimeField()

