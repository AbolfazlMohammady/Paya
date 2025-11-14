from rest_framework import serializers
from phonenumber_field.serializerfields import PhoneNumberField
from decimal import Decimal

from .models import Wallet, Transaction, WalletLimit
from .utils import validate_iranian_iban
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
    method = serializers.ChoiceField(
        choices=[choice[0] for choice in Transaction.TRANSFER_METHOD_CHOICES],
        default='phone'
    )
    recipient_phone = PhoneNumberField(region='IR', required=False)
    recipient_wallet_id = serializers.IntegerField(required=False)
    amount = serializers.DecimalField(
        max_digits=15, 
        decimal_places=2,
        min_value=Decimal('10000'),
        required=False
    )
    description = serializers.CharField(max_length=500, required=False, allow_blank=True)
    metadata = serializers.JSONField(required=False, default=dict)
    
    def validate_amount(self, value):
        if value < 10000:
            raise serializers.ValidationError("Minimum transfer amount is 10,000 IRR")
        return value
    
    def validate_metadata(self, value):
        if value is None:
            return {}
        if not isinstance(value, dict):
            raise serializers.ValidationError("Metadata must be a valid object")
        return value
    
    def validate(self, attrs):
        method = attrs.get('method', 'phone')
        metadata = attrs.get('metadata') or {}
        
        amount = attrs.get('amount')

        if method == 'qr':
            qr_payload = metadata.get('qr_payload') or metadata.get('payload')
            if not qr_payload:
                raise serializers.ValidationError({
                    'metadata': "qr_payload is required for QR transfers"
                })
            attrs['metadata'] = metadata
            # amount می‌تواند خالی باشد و بعداً از QR تنظیم شود
            if amount is not None and amount < Decimal('10000'):
                raise serializers.ValidationError({
                    'amount': "Minimum transfer amount is 10,000 IRR"
                })
            attrs['metadata'] = metadata
            return attrs
        
        if method == 'iban':
            iban = metadata.get('iban')
            if not iban:
                raise serializers.ValidationError({
                    'metadata': "iban is required for IBAN transfers"
                })
            
            # اعتبارسنجی شبا
            is_valid, error_msg = validate_iranian_iban(iban)
            if not is_valid:
                raise serializers.ValidationError({
                    'metadata': f"Invalid IBAN: {error_msg}"
                })
            
            # مقدار شبا را normalize می‌کنیم (حذف فاصله و تبدیل به حروف بزرگ)
            normalized_iban = iban.replace(' ', '').replace('-', '').upper()
            metadata['iban'] = normalized_iban
            attrs['metadata'] = metadata
            
            if amount is None:
                raise serializers.ValidationError({'amount': 'Amount is required for IBAN transfers'})
            
            if amount < Decimal('10000'):
                raise serializers.ValidationError({
                    'amount': "Minimum transfer amount is 10,000 IRR"
                })
            
            return attrs
        
        if amount is None:
            raise serializers.ValidationError({'amount': 'This field is required'})

        phone = attrs.get('recipient_phone') or metadata.get('phone') or metadata.get('recipient_phone')
        wallet_id = attrs.get('recipient_wallet_id') or metadata.get('wallet_id') or metadata.get('recipient_wallet_id')
        
        if not phone and not wallet_id:
            raise serializers.ValidationError("Recipient phone or wallet_id is required")
        
        if phone:
            attrs['recipient_phone'] = str(phone)
        if wallet_id is not None:
            try:
                attrs['recipient_wallet_id'] = int(wallet_id)
            except (TypeError, ValueError):
                raise serializers.ValidationError("recipient_wallet_id must be an integer")
        
        attrs['metadata'] = metadata
        return attrs


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
            'transfer_method', 'metadata',
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
    recipient = serializers.DictField(required=False, allow_null=True)
    balance_after = serializers.DecimalField(max_digits=15, decimal_places=2)
    status = serializers.CharField()
    created_at = serializers.DateTimeField()
    method = serializers.CharField()
    metadata = serializers.JSONField()
    iban = serializers.CharField(required=False, allow_null=True)
    message = serializers.CharField(required=False, allow_null=True)


class GatewayChargeSerializer(serializers.Serializer):
    """Serializer برای شارژ از طریق درگاه پرداخت"""
    amount = serializers.DecimalField(
        max_digits=15,
        decimal_places=2,
        min_value=Decimal('1000')
    )
    description = serializers.CharField(max_length=500, required=False, allow_blank=True)
    callback_url = serializers.URLField(required=False, allow_blank=True)
    
    def validate_amount(self, value):
        if value <= 0:
            raise serializers.ValidationError("Amount must be greater than zero")
        return value

    def validate(self, attrs):
        return attrs


class GatewayChargeResponseSerializer(serializers.Serializer):
    """Serializer برای پاسخ درخواست شارژ از درگاه"""
    request_id = serializers.CharField()
    payment_url = serializers.URLField()
    authority = serializers.CharField()
    amount = serializers.DecimalField(max_digits=15, decimal_places=2)
    gateway = serializers.CharField()
    expires_at = serializers.DateTimeField()


class QRGenerateSerializer(serializers.Serializer):
    """Serializer برای ایجاد QR"""
    amount = serializers.DecimalField(
        max_digits=15,
        decimal_places=2,
        min_value=Decimal('10000'),
        required=False
    )
    description = serializers.CharField(max_length=255, required=False, allow_blank=True)
    expires_in = serializers.IntegerField(required=False, min_value=60, max_value=86400)
    metadata = serializers.JSONField(required=False, default=dict)

    def validate_metadata(self, value):
        if value is None:
            return {}
        if not isinstance(value, dict):
            raise serializers.ValidationError("Metadata must be a valid object")
        return value


class QRGenerateResponseSerializer(serializers.Serializer):
    qr_payload = serializers.CharField()
    qr_content = serializers.CharField()
    qr_url = serializers.CharField()
    deeplink = serializers.CharField()
    amount = serializers.DecimalField(max_digits=15, decimal_places=2, allow_null=True, required=False)
    description = serializers.CharField(allow_blank=True, required=False)
    expires_at = serializers.DateTimeField()
    status = serializers.CharField()


class QRPayloadSerializer(serializers.Serializer):
    qr_payload = serializers.CharField()


class QRInfoSerializer(serializers.Serializer):
    qr_payload = serializers.CharField()
    status = serializers.CharField()
    expires_at = serializers.DateTimeField()
    amount = serializers.DecimalField(max_digits=15, decimal_places=2, allow_null=True, required=False)
    description = serializers.CharField(allow_blank=True, required=False)
    qr_content = serializers.CharField()
    owner = serializers.DictField()
    metadata = serializers.JSONField()

