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
            'id', 'balance', 'currency', 'status', 'wallet_address',
            'created_at', 'updated_at', 'formatted_balance'
        ]
        read_only_fields = ['id', 'balance', 'wallet_address', 'created_at', 'updated_at']
    
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
        
        if method == 'wallet_address':
            wallet_address = metadata.get('wallet_address')
            if not wallet_address:
                raise serializers.ValidationError({
                    'metadata': "wallet_address is required for wallet_address transfers"
                })
            
            # نرمال‌سازی آدرس
            wallet_address = wallet_address.replace(' ', '').replace('-', '').upper()
            
            if len(wallet_address) != 24:
                raise serializers.ValidationError({
                    'metadata': "Wallet address must be exactly 24 characters"
                })
            
            if not wallet_address.startswith('PAYA'):
                raise serializers.ValidationError({
                    'metadata': "Wallet address must start with PAYA"
                })
            
            metadata['wallet_address'] = wallet_address
            attrs['metadata'] = metadata
            
            if amount is None:
                raise serializers.ValidationError({'amount': 'Amount is required for wallet_address transfers'})
            
            if amount < Decimal('10000'):
                raise serializers.ValidationError({
                    'amount': "Minimum transfer amount is 10,000 IRR"
                })
            
            return attrs
        
        if method == 'special_code':
            special_code = metadata.get('special_code')
            if not special_code:
                raise serializers.ValidationError({
                    'metadata': "special_code is required for special_code transfers"
                })
            
            if amount is None:
                raise serializers.ValidationError({'amount': 'Amount is required for special_code transfers'})
            
            if amount < Decimal('10000'):
                raise serializers.ValidationError({
                    'amount': "Minimum transfer amount is 10,000 IRR"
                })
            
            return attrs
        
        if method == 'link':
            payment_link_id = metadata.get('payment_link_id') or metadata.get('link_id')
            if not payment_link_id:
                raise serializers.ValidationError({
                    'metadata': "payment_link_id is required for link transfers"
                })
            
            # amount ممکن است از link تعیین شود
            if amount is not None and amount < Decimal('10000'):
                raise serializers.ValidationError({
                    'amount': "Minimum transfer amount is 10,000 IRR"
                })
            
            return attrs
        
        if method == 'nfc':
            nfc_data = metadata.get('nfc_data') or metadata.get('nfc_token') or metadata.get('wallet_address')
            if not nfc_data:
                raise serializers.ValidationError({
                    'metadata': "nfc_data or wallet_address is required for NFC transfers"
                })
            
            if amount is None:
                raise serializers.ValidationError({'amount': 'Amount is required for NFC transfers'})
            
            if amount < Decimal('10000'):
                raise serializers.ValidationError({
                    'amount': "Minimum transfer amount is 10,000 IRR"
                })
            
            return attrs
        
        if amount is None:
            raise serializers.ValidationError({'amount': 'This field is required'})

        phone = attrs.get('recipient_phone') or metadata.get('phone') or metadata.get('recipient_phone')
        
        if not phone:
            raise serializers.ValidationError("Recipient phone is required")
        
        if phone:
            attrs['recipient_phone'] = str(phone)
        
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
    payment_form = serializers.DictField(required=False)  # اطلاعات فرم POST
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


class LinkGenerateSerializer(serializers.Serializer):
    """Serializer برای ایجاد لینک پرداخت"""
    amount = serializers.DecimalField(
        max_digits=15,
        decimal_places=2,
        min_value=Decimal('10000'),
        required=True
    )
    description = serializers.CharField(max_length=255, required=False, allow_blank=True)
    expires_in = serializers.IntegerField(required=False, min_value=60, max_value=86400 * 7)  # حداکثر 7 روز
    metadata = serializers.JSONField(required=False, default=dict)

    def validate_metadata(self, value):
        if value is None:
            return {}
        if not isinstance(value, dict):
            raise serializers.ValidationError("Metadata must be a valid object")
        return value


class LinkGenerateResponseSerializer(serializers.Serializer):
    link_id = serializers.CharField()
    link = serializers.CharField()  # لینک اختصاصی (شناسه کوتاه)
    amount = serializers.DecimalField(max_digits=15, decimal_places=2)
    description = serializers.CharField(allow_blank=True, required=False)
    expires_at = serializers.DateTimeField()
    status = serializers.CharField()


class TransactionReportSummarySerializer(serializers.Serializer):
    """Serializer برای خلاصه گزارش تراکنش‌ها"""
    total_payments = serializers.DecimalField(max_digits=15, decimal_places=2)
    total_receipts = serializers.DecimalField(max_digits=15, decimal_places=2)
    formatted_total_payments = serializers.CharField()
    formatted_total_receipts = serializers.CharField()


class TransactionReportChartDataSerializer(serializers.Serializer):
    """Serializer برای داده‌های نمودار گزارش تراکنش‌ها"""
    period = serializers.CharField()  # مثل "هفته ۱" یا "1403/05"
    payments = serializers.DecimalField(max_digits=15, decimal_places=2)
    receipts = serializers.DecimalField(max_digits=15, decimal_places=2)
    date = serializers.DateField()


class TransactionReportSerializer(serializers.Serializer):
    """Serializer برای گزارش کامل تراکنش‌ها"""
    summary = TransactionReportSummarySerializer()
    chart_data = TransactionReportChartDataSerializer(many=True)
    transactions = serializers.ListField(child=serializers.DictField(), required=False)
    total_transactions = serializers.IntegerField()
    has_more = serializers.BooleanField()

