from rest_framework import status, views, viewsets, permissions
from rest_framework.response import Response
from rest_framework.decorators import action
from django.utils import timezone
from django.db import transaction as db_transaction
from django.core.paginator import Paginator
from django.db.models import Q, Sum, Count
from django.db.models.functions import TruncWeek, TruncMonth, TruncDate
from django.http import HttpResponse
from decimal import Decimal
from io import BytesIO
import qrcode
from qrcode.constants import ERROR_CORRECT_M
from PIL import Image

from .models import Wallet, Transaction, PaymentRequest, WalletQRCode, PaymentLink, SpecialCode
from .serializers import (
    WalletSerializer, WalletCreateSerializer,
    ChargeSerializer, DebitSerializer, TransferSerializer,
    TransactionSerializer, TransactionDetailSerializer,
    BalanceSerializer, ChargeResponseSerializer,
    DebitResponseSerializer, TransferResponseSerializer,
    GatewayChargeSerializer, GatewayChargeResponseSerializer,
    QRGenerateSerializer, QRGenerateResponseSerializer,
    QRPayloadSerializer, QRInfoSerializer,
    LinkGenerateSerializer, LinkGenerateResponseSerializer,
    TransactionReportSerializer, TransactionReportSummarySerializer,
    TransactionReportChartDataSerializer
)
from .utils import (
    charge_wallet, debit_wallet, transfer_money,
    MIN_TRANSFER_AMOUNT
)
from .payment_gateway import PaymentGatewayService
from django.conf import settings
from users.core.models import User


class WalletViewSet(viewsets.ViewSet):
    """
    ViewSet برای مدیریت کیف پول
    """
    permission_classes = [permissions.IsAuthenticated]
    
    def create(self, request):
        """
        ایجاد کیف پول جدید
        POST /api/wallet/create/
        """
        # بررسی وجود کیف پول
        if hasattr(request.user, 'wallet'):
            return Response(
                {'detail': 'Wallet already exists for this user'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        serializer = WalletCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        currency = serializer.validated_data.get('currency', 'IRR')
        
        # ایجاد کیف پول با آدرس 24 رقمی
        wallet_address = Wallet.generate_wallet_address()
        wallet = Wallet.objects.create(
            user=request.user,
            currency=currency,
            balance=Decimal('0'),
            status='active',
            wallet_address=wallet_address
        )
        
        response_serializer = WalletSerializer(wallet)
        return Response(response_serializer.data, status=status.HTTP_201_CREATED)
    
    def retrieve(self, request):
        """
        دریافت اطلاعات کیف پول کاربر
        GET /api/wallet/me/
        """
        try:
            wallet = request.user.wallet
        except Wallet.DoesNotExist:
            return Response(
                {'detail': 'Wallet not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        serializer = WalletSerializer(wallet)
        return Response(serializer.data, status=status.HTTP_200_OK)
    
    @action(detail=False, methods=['get'], url_path='balance')
    def balance(self, request):
        """
        دریافت موجودی کیف پول
        GET /api/wallet/balance/
        """
        try:
            wallet = request.user.wallet
        except Wallet.DoesNotExist:
            return Response(
                {'detail': 'Wallet not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        data = {
            'balance': wallet.balance,
            'currency': wallet.currency,
            'formatted_balance': wallet.get_formatted_balance()
        }
        serializer = BalanceSerializer(data)
        return Response(serializer.data, status=status.HTTP_200_OK)
    
    @action(detail=False, methods=['post'], url_path='charge')
    def charge(self, request):
        """
        شارژ کیف پول
        POST /api/wallet/charge/
        """
        try:
            wallet = request.user.wallet
        except Wallet.DoesNotExist:
            return Response(
                {'detail': 'Wallet not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        if wallet.status != 'active':
            return Response(
                {'detail': 'Wallet is not active'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        serializer = ChargeSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            transaction = charge_wallet(
                wallet=wallet,
                amount=serializer.validated_data['amount'],
                description=serializer.validated_data.get('description', ''),
                payment_method=serializer.validated_data.get('payment_method'),
                payment_id=serializer.validated_data.get('payment_id'),
                request=request
            )
            
            response_data = {
                'transaction_id': transaction.transaction_id,
                'amount': transaction.amount,
                'balance_after': transaction.balance_after,
                'status': transaction.status,
                'created_at': transaction.created_at
            }
            response_serializer = ChargeResponseSerializer(response_data)
            return Response(response_serializer.data, status=status.HTTP_200_OK)
        except Exception as e:
            return Response(
                {'detail': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=False, methods=['post'], url_path='debit')
    def debit(self, request):
        """
        برداشت از کیف پول
        POST /api/wallet/debit/
        """
        try:
            wallet = request.user.wallet
        except Wallet.DoesNotExist:
            return Response(
                {'detail': 'Wallet not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        if wallet.status != 'active':
            return Response(
                {'detail': 'Wallet is not active'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        serializer = DebitSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            transaction = debit_wallet(
                wallet=wallet,
                amount=serializer.validated_data['amount'],
                description=serializer.validated_data.get('description', ''),
                reference_id=serializer.validated_data.get('reference_id'),
                request=request
            )
            
            response_data = {
                'transaction_id': transaction.transaction_id,
                'amount': transaction.amount,
                'balance_after': transaction.balance_after,
                'status': transaction.status,
                'created_at': transaction.created_at
            }
            response_serializer = DebitResponseSerializer(response_data)
            return Response(response_serializer.data, status=status.HTTP_200_OK)
        except ValueError as e:
            return Response(
                {'detail': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            return Response(
                {'detail': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['post'], url_path='transfer')
    def transfer(self, request):
        """
        انتقال وجه
        POST /api/wallet/transfer/
        """
        try:
            sender_wallet = request.user.wallet
        except Wallet.DoesNotExist:
            return Response(
                {'detail': 'Wallet not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        if sender_wallet.status != 'active':
            return Response(
                {'detail': 'Wallet is not active'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        serializer = TransferSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        method = serializer.validated_data.get('method', 'phone')
        metadata = serializer.validated_data.get('metadata', {})
        recipient_phone = serializer.validated_data.get('recipient_phone')
        amount = serializer.validated_data['amount']
        description = serializer.validated_data.get('description', '')
        
        recipient_user = None
        recipient_wallet = None
        qr_instance = None

        if method == 'qr':
            qr_payload = metadata.get('qr_payload') or metadata.get('payload')
            try:
                qr_instance = WalletQRCode.objects.select_related('wallet__user').get(qr_payload=qr_payload)
            except WalletQRCode.DoesNotExist:
                return Response(
                    {'detail': 'QR code not found'},
                    status=status.HTTP_404_NOT_FOUND
                )

            if qr_instance.status != 'active':
                return Response(
                    {'detail': 'QR code is not active'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            if qr_instance.is_expired():
                if qr_instance.status != 'expired':
                    qr_instance.status = 'expired'
                    qr_instance.save(update_fields=['status', 'updated_at'])
                return Response(
                    {'detail': 'QR code is expired'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            recipient_wallet = qr_instance.wallet
            recipient_user = recipient_wallet.user

            if sender_wallet.id == recipient_wallet.id:
                return Response(
                    {'detail': 'Cannot transfer to your own wallet'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            if recipient_wallet.status != 'active':
                return Response(
                    {'detail': 'Recipient wallet is not active'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            if amount is None:
                amount = qr_instance.amount
            if amount is None:
                return Response(
                    {'detail': 'Amount is required for this QR'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            if amount < Decimal('10000'):
                return Response(
                    {'detail': 'Minimum transfer amount is 10,000 IRR'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            if not description:
                description = qr_instance.description or 'پرداخت با QR'

            metadata = dict(metadata or {})
            metadata.setdefault('qr_payload', qr_instance.qr_payload)
            metadata.setdefault('qr_id', qr_instance.id)
            metadata.setdefault('qr_owner_wallet_id', recipient_wallet.id)
            metadata.setdefault('qr_owner_user_id', recipient_wallet.user_id)
            metadata.setdefault('qr_fixed_amount', bool(qr_instance.amount is not None))
        elif method == 'wallet_address':
            # انتقال با آدرس کیف پول (24 رقمی)
            wallet_address = metadata.get('wallet_address')
            if not wallet_address:
                return Response(
                    {'detail': 'wallet_address is required in metadata'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # نرمال‌سازی آدرس (حذف فاصله و تبدیل به حروف بزرگ)
            wallet_address = wallet_address.replace(' ', '').replace('-', '').upper()
            
            if len(wallet_address) != 24:
                return Response(
                    {'detail': 'Wallet address must be exactly 24 characters'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            if not wallet_address.startswith('PAYA'):
                return Response(
                    {'detail': 'Wallet address must start with PAYA'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            try:
                recipient_wallet = Wallet.objects.select_related('user').get(wallet_address=wallet_address)
                recipient_user = recipient_wallet.user
            except Wallet.DoesNotExist:
                return Response(
                    {'detail': 'Recipient wallet not found'},
                    status=status.HTTP_404_NOT_FOUND
                )
            
            if sender_wallet.id == recipient_wallet.id:
                return Response(
                    {'detail': 'Cannot transfer to your own wallet'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            if recipient_wallet.status != 'active':
                return Response(
                    {'detail': 'Recipient wallet is not active'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            metadata = dict(metadata or {})
            metadata.setdefault('wallet_address', wallet_address)
        elif method == 'special_code':
            # انتقال با کد اختصاصی (برای رانندگان)
            special_code = metadata.get('special_code')
            if not special_code:
                return Response(
                    {'detail': 'special_code is required in metadata'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # نرمال‌سازی کد (حذف فاصله)
            special_code = special_code.replace(' ', '').replace('-', '').strip()
            
            try:
                special_code_obj = SpecialCode.objects.select_related('user', 'user__wallet').get(
                    code=special_code,
                    is_active=True
                )
            except SpecialCode.DoesNotExist:
                return Response(
                    {'detail': 'Special code not found or inactive'},
                    status=status.HTTP_404_NOT_FOUND
                )
            
            # یافتن کیف پول دریافت‌کننده (راننده)
            recipient_user = special_code_obj.user
            try:
                recipient_wallet = recipient_user.wallet
            except Wallet.DoesNotExist:
                return Response(
                    {'detail': 'Recipient wallet not found'},
                    status=status.HTTP_404_NOT_FOUND
                )
            
            # بررسی اینکه کاربر به خودش پول نزند
            if sender_wallet.id == recipient_wallet.id:
                return Response(
                    {'detail': 'Cannot transfer to your own wallet'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            if recipient_wallet.status != 'active':
                return Response(
                    {'detail': 'Recipient wallet is not active'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            metadata = dict(metadata or {})
            metadata.setdefault('special_code', special_code)
            metadata.setdefault('driver_user_id', recipient_user.id)
            metadata.setdefault('driver_wallet_id', recipient_wallet.id)
        elif method == 'link':
            # انتقال با لینک پرداخت
            payment_link_id = metadata.get('payment_link_id') or metadata.get('link_id')
            if not payment_link_id:
                return Response(
                    {'detail': 'payment_link_id is required in metadata'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            try:
                payment_link = PaymentLink.objects.select_related('wallet', 'wallet__user').get(link_id=payment_link_id)
            except PaymentLink.DoesNotExist:
                return Response(
                    {'detail': 'Payment link not found'},
                    status=status.HTTP_404_NOT_FOUND
                )
            
            # بررسی انقضا
            if payment_link.is_expired():
                if payment_link.status != 'expired':
                    payment_link.status = 'expired'
                    payment_link.save(update_fields=['status', 'updated_at'])
                return Response(
                    {'detail': 'Payment link is expired'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # بررسی استفاده شده
            if payment_link.status == 'used':
                return Response(
                    {'detail': 'Payment link has already been used'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            if payment_link.status != 'active':
                return Response(
                    {'detail': 'Payment link is not active'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # یافتن کیف پول دریافت‌کننده (صاحب لینک)
            recipient_wallet = payment_link.wallet
            recipient_user = recipient_wallet.user
            
            # بررسی اینکه کاربر به خودش پول نزند
            if sender_wallet.id == recipient_wallet.id:
                return Response(
                    {'detail': 'Cannot transfer to your own wallet'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            if recipient_wallet.status != 'active':
                return Response(
                    {'detail': 'Recipient wallet is not active'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # استفاده از مبلغ لینک (اگر amount ارسال نشده باشد)
            if amount is None:
                amount = payment_link.amount
            elif amount != payment_link.amount:
                return Response(
                    {'detail': f'Amount must be exactly {payment_link.amount} as specified in the payment link'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            metadata = dict(metadata or {})
            metadata.setdefault('payment_link_id', payment_link_id)
            metadata.setdefault('link_owner_wallet_id', recipient_wallet.id)
            metadata.setdefault('link_owner_user_id', recipient_user.id)
        elif method == 'nfc':
            # انتقال با NFC
            # NFC data می‌تواند wallet_address یا phone باشد
            nfc_data = metadata.get('nfc_data') or metadata.get('nfc_token') or metadata.get('wallet_address')
            if not nfc_data:
                return Response(
                    {'detail': 'nfc_data or wallet_address is required in metadata'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # اگر wallet_address است، مستقیماً استفاده می‌کنیم
            if nfc_data.startswith('PAYA') and len(nfc_data) == 24:
                try:
                    recipient_wallet = Wallet.objects.select_related('user').get(wallet_address=nfc_data.upper())
                    recipient_user = recipient_wallet.user
                except Wallet.DoesNotExist:
                    return Response(
                        {'detail': 'Recipient wallet not found'},
                        status=status.HTTP_404_NOT_FOUND
                    )
            else:
                # اگر phone است، از phone استفاده می‌کنیم
                try:
                    recipient_user = User.objects.get(phone=nfc_data)
                    recipient_wallet = recipient_user.wallet
                except User.DoesNotExist:
                    return Response(
                        {'detail': 'Recipient user not found'},
                        status=status.HTTP_404_NOT_FOUND
                    )
                except Wallet.DoesNotExist:
                    return Response(
                        {'detail': 'Recipient wallet not found'},
                        status=status.HTTP_404_NOT_FOUND
                    )
            
            # بررسی اینکه کاربر به خودش پول نزند
            if sender_wallet.id == recipient_wallet.id:
                return Response(
                    {'detail': 'Cannot transfer to your own wallet'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            if recipient_wallet.status != 'active':
                return Response(
                    {'detail': 'Recipient wallet is not active'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            metadata = dict(metadata or {})
            metadata.setdefault('nfc_data', nfc_data)
        else:
            # روش‌های phone و contact
            # بررسی اینکه کاربر به خودش پول نزند
            if recipient_phone and str(request.user.phone) == recipient_phone:
                return Response(
                    {'detail': 'Cannot transfer to yourself'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # یافتن کاربر دریافت‌کننده
            try:
                recipient_user = User.objects.get(phone=recipient_phone)
            except User.DoesNotExist:
                return Response(
                    {'detail': 'Recipient user not found'},
                    status=status.HTTP_404_NOT_FOUND
                )
            
            # یافتن کیف پول دریافت‌کننده
            try:
                recipient_wallet = recipient_user.wallet
            except Wallet.DoesNotExist:
                return Response(
                    {'detail': 'Recipient wallet not found'},
                    status=status.HTTP_404_NOT_FOUND
                )

            if recipient_wallet.status != 'active':
                return Response(
                    {'detail': 'Recipient wallet is not active'},
                    status=status.HTTP_400_BAD_REQUEST
                )
        
        try:
            transfer_metadata = dict(metadata or {})
            transfer_metadata.setdefault('method', method)
            transfer_metadata.setdefault('initiator_user_id', request.user.id)
            
            sender_transaction, recipient_transaction = transfer_money(
                sender_wallet=sender_wallet,
                recipient_wallet=recipient_wallet,
                amount=amount,
                description=description,
                method=method,
                metadata=transfer_metadata,
                request=request
            )

            if qr_instance:
                qr_instance.mark_used({
                    'used_by_wallet_id': sender_wallet.id,
                    'used_by_user_id': request.user.id,
                    'amount': str(amount)
                })
            
            # اگر از لینک پرداخت استفاده شده، آن را علامت‌گذاری می‌کنیم
            if method == 'link':
                payment_link_id = transfer_metadata.get('payment_link_id')
                if payment_link_id:
                    try:
                        payment_link = PaymentLink.objects.get(link_id=payment_link_id)
                        payment_link.mark_used(
                            used_by_wallet=sender_wallet,
                            usage_metadata={
                                'used_by_user_id': request.user.id,
                                'amount': str(amount),
                                'transaction_id': sender_transaction.transaction_id
                            }
                        )
                    except PaymentLink.DoesNotExist:
                        pass  # لینک پیدا نشد، اما تراکنش انجام شده است
            
            response_data = {
                'transaction_id': sender_transaction.transaction_id,
                'amount': sender_transaction.amount,
                'recipient': {
                    'phone': str(recipient_user.phone),
                    'fullname': recipient_user.fullname or ''
                },
                'balance_after': sender_transaction.balance_after,
                'status': sender_transaction.status,
                'created_at': sender_transaction.created_at,
                'method': sender_transaction.transfer_method,
                'metadata': sender_transaction.metadata
            }
            response_serializer = TransferResponseSerializer(response_data)
            return Response(response_serializer.data, status=status.HTTP_200_OK)
        except ValueError as e:
            return Response(
                {'detail': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            return Response(
                {'detail': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=False, methods=['get'], url_path='transactions')
    def transactions(self, request):
        """
        دریافت تاریخچه تراکنش‌ها
        GET /api/wallet/transactions/
        """
        try:
            wallet = request.user.wallet
        except Wallet.DoesNotExist:
            return Response(
                {'detail': 'Wallet not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # فیلترها
        transaction_type = request.query_params.get('type')
        start_date = request.query_params.get('start_date')
        end_date = request.query_params.get('end_date')
        
        # Query
        queryset = Transaction.objects.filter(wallet=wallet)
        
        if transaction_type:
            queryset = queryset.filter(type=transaction_type)
        
        if start_date:
            queryset = queryset.filter(created_at__gte=start_date)
        
        if end_date:
            queryset = queryset.filter(created_at__lte=end_date)
        
        # Pagination
        page = int(request.query_params.get('page', 1))
        page_size = int(request.query_params.get('page_size', 20))
        
        paginator = Paginator(queryset, page_size)
        page_obj = paginator.get_page(page)
        
        serializer = TransactionSerializer(page_obj.object_list, many=True)
        
        return Response({
            'count': paginator.count,
            'next': page_obj.next_page_number() if page_obj.has_next() else None,
            'previous': page_obj.previous_page_number() if page_obj.has_previous() else None,
            'results': serializer.data
        }, status=status.HTTP_200_OK)
    
    @action(detail=False, methods=['post'], url_path='charge-gateway')
    def charge_gateway(self, request):
        """
        درخواست شارژ کیف پول از طریق درگاه پرداخت
        POST /api/wallet/charge-gateway/
        """
        try:
            wallet = request.user.wallet
        except Wallet.DoesNotExist:
            return Response(
                {'detail': 'Wallet not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        if wallet.status != 'active':
            return Response(
                {'detail': 'Wallet is not active'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        serializer = GatewayChargeSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        amount = serializer.validated_data['amount']
        description = serializer.validated_data.get('description', 'شارژ کیف پول')
        callback_url = serializer.validated_data.get('callback_url', '')
        
        # خواندن terminal_id از settings (قبل از استفاده)
        gateways_config = getattr(settings, 'PAYMENT_GATEWAYS', {})
        sepehr_config = gateways_config.get('sepehr', {})
        terminal_id_from_config = sepehr_config.get('TERMINAL_ID', 'N/A')
        
        # اگر callback_url داده نشده، از تنظیمات استفاده می‌کنیم
        if not callback_url:
            base_url = getattr(settings, 'BASE_URL', 'http://localhost:8000')
            callback_url = f"{base_url}/api/wallet/payment-callback/"
        
        # هشدار برای Callback URL محلی (درگاه نمی‌تواند به localhost دسترسی داشته باشد)
        if 'localhost' in callback_url or '127.0.0.1' in callback_url:
            # در حالت production این باید خطا بدهد، اما برای تست اجازه می‌دهیم
            pass
        
        payment_request_id = PaymentRequest.generate_request_id()
        # تولید InvoiceID عددی برای درگاه سپهر
        invoice_id_for_gateway = PaymentRequest.generate_invoice_id_for_gateway()
        gateway_metadata = {
            'invoice_id': invoice_id_for_gateway,  # InvoiceID عددی برای درگاه
            'request_id': payment_request_id,  # شناسه داخلی برای ردیابی
            'wallet_id': wallet.id,
            'user_id': request.user.id,
            'payload': ''
        }
        
        # ایجاد درخواست پرداخت
        payment_result = PaymentGatewayService.create_payment_request(
            amount=amount,
            description=description,
            callback_url=callback_url,
            user_phone=str(request.user.phone),
            user_email=None,
            metadata=gateway_metadata
        )
        
        # ذخیره درخواست پرداخت (حتی در صورت خطا برای دیباگ)
        resolved_gateway = payment_result.get('gateway') or 'sepehr'
        
        payment_request_metadata = {
            'gateway_extra': payment_result.get('extra') or {},
            'gateway_response': payment_result.get('raw_response') or {},
            'invoice_id': invoice_id_for_gateway,  # InvoiceID عددی برای درگاه
            'request_id': payment_request_id,  # شناسه داخلی
            'callback_url': callback_url,
            'request_body': {
                'amount': str(amount),
                'terminal_id': terminal_id_from_config,
            }
        }
        
        # اگر خطا داشت، درخواست را با status failed ذخیره می‌کنیم
        if not payment_result.get('success'):
            payment_request = PaymentRequest.objects.create(
                request_id=payment_request_id,
                wallet=wallet,
                amount=amount,
                description=description,
                gateway=resolved_gateway,
                authority=None,
                callback_url=callback_url,
                status='failed',
                metadata=payment_request_metadata
            )
            
            # اضافه کردن اطلاعات دیباگ بیشتر
            debug_info = dict(payment_result.get('raw_response') or {})
            
            # خواندن terminal_id از gateway_extra یا config
            gateway_extra = payment_result.get('extra') or {}
            terminal_id_debug = 'N/A'
            
            # اول از gateway_extra تلاش می‌کنیم
            if isinstance(gateway_extra, dict) and gateway_extra.get('terminal_id'):
                terminal_id_debug = gateway_extra.get('terminal_id')
            # سپس از payment_request_metadata
            elif isinstance(payment_request_metadata, dict):
                request_body = payment_request_metadata.get('request_body', {})
                if isinstance(request_body, dict) and request_body.get('terminal_id'):
                    terminal_id_debug = request_body.get('terminal_id')
            
            # اگر هنوز پیدا نشد، از terminal_id_from_config استفاده می‌کنیم
            if terminal_id_debug == 'N/A':
                terminal_id_debug = terminal_id_from_config
            
            debug_info.update({
                'invoice_id_sent': invoice_id_for_gateway,
                'invoice_id_length': len(str(invoice_id_for_gateway)),
                'invoice_id_is_numeric': str(invoice_id_for_gateway).isdigit(),
                'amount_sent': str(amount),
                'callback_url': callback_url,
                'terminal_id': terminal_id_debug,
            })
            
            return Response(
                {
                    'detail': payment_result.get('error', 'Payment gateway error'),
                    'request_id': payment_request_id,
                    'debug_info': debug_info
                },
                status=status.HTTP_400_BAD_REQUEST
            )
        
        payment_request = PaymentRequest.objects.create(
            request_id=payment_request_id,
            wallet=wallet,
            amount=amount,
            description=description,
            gateway=resolved_gateway,
            authority=payment_result.get('authority'),
            callback_url=callback_url,
            status='pending',
            metadata=payment_request_metadata
        )
        
        # محاسبه زمان انقضا (30 دقیقه)
        expires_at = timezone.now() + timezone.timedelta(minutes=30)
        
        response_data = {
            'request_id': payment_request.request_id,
            'payment_url': payment_result.get('payment_url'),
            'authority': payment_result.get('authority'),
            'amount': amount,
            'gateway': resolved_gateway,
            'expires_at': expires_at
        }
        
        response_serializer = GatewayChargeResponseSerializer(response_data)
        return Response(response_serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=['post'], url_path='qr/generate')
    def generate_qr(self, request):
        """
        ایجاد QR پرداخت / انتقال
        POST /api/wallet/qr/generate/
        """
        try:
            wallet = request.user.wallet
        except Wallet.DoesNotExist:
            return Response(
                {'detail': 'Wallet not found'},
                status=status.HTTP_404_NOT_FOUND
            )

        if wallet.status != 'active':
            return Response(
                {'detail': 'Wallet is not active'},
                status=status.HTTP_400_BAD_REQUEST
            )

        serializer = QRGenerateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        data = serializer.validated_data
        amount = data.get('amount')
        description = data.get('description', '')
        expires_in = data.get('expires_in', 300)
        metadata = data.get('metadata', {})

        qr = WalletQRCode.create_qr(
            wallet=wallet,
            amount=amount,
            description=description,
            expires_in=expires_in,
            metadata=metadata
        )

        base_url = getattr(settings, 'BASE_URL', 'http://localhost:8000')
        qr_content = f"PAYAQR:{qr.qr_payload}"
        qr_url = f"{base_url}/api/wallet/qr/lookup/"
        deeplink = f"paya://wallet/qr/{qr.qr_payload}"

        response_payload = {
            'qr_payload': qr.qr_payload,
            'qr_content': qr_content,
            'qr_url': qr_url,
            'deeplink': deeplink,
            'amount': qr.amount,
            'description': qr.description,
            'expires_at': qr.expires_at,
            'status': qr.status
        }

        response_serializer = QRGenerateResponseSerializer(response_payload)
        return Response(response_serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=['post'], url_path='qr/lookup')
    def lookup_qr(self, request):
        """
        دریافت اطلاعات QR
        POST /api/wallet/qr/lookup/
        """
        serializer = QRPayloadSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        payload = serializer.validated_data['qr_payload']
        try:
            qr = WalletQRCode.objects.select_related('wallet__user').get(qr_payload=payload)
        except WalletQRCode.DoesNotExist:
            return Response({'detail': 'QR code not found'}, status=status.HTTP_404_NOT_FOUND)

        if qr.status == 'active' and qr.is_expired():
            qr.status = 'expired'
            qr.save(update_fields=['status', 'updated_at'])

        owner_info = {
            'wallet_id': qr.wallet.id,
            'user_id': qr.wallet.user_id,
            'phone': str(qr.wallet.user.phone),
            'fullname': qr.wallet.user.fullname or ''
        }

        info_payload = {
            'qr_payload': qr.qr_payload,
            'status': qr.status,
            'expires_at': qr.expires_at,
            'amount': qr.amount,
            'description': qr.description,
            'qr_content': f"PAYAQR:{qr.qr_payload}",
            'owner': owner_info,
            'metadata': qr.metadata,
        }

        response_serializer = QRInfoSerializer(info_payload)
        return Response(response_serializer.data, status=status.HTTP_200_OK)

    @action(detail=False, methods=['get'], url_path='qr/image')
    def qr_image(self, request):
        """
        دریافت تصویر QR به‌صورت PNG
        GET /api/wallet/qr/image/?qr_payload=...
        """
        qr_payload = request.query_params.get('qr_payload') or request.query_params.get('payload')
        if not qr_payload:
            return Response(
                {'detail': 'qr_payload query parameter is required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            qr = WalletQRCode.objects.get(qr_payload=qr_payload)
        except WalletQRCode.DoesNotExist:
            return Response(
                {'detail': 'QR code not found'},
                status=status.HTTP_404_NOT_FOUND
            )

        if qr.status == 'active' and qr.is_expired():
            qr.status = 'expired'
            qr.save(update_fields=['status', 'updated_at'])
            return Response(
                {'detail': 'QR code is expired'},
                status=status.HTTP_400_BAD_REQUEST
            )

        size_param = request.query_params.get('size')
        target_size = None
        if size_param:
            try:
                target_size = int(size_param)
            except (TypeError, ValueError):
                return Response(
                    {'detail': 'size must be an integer'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            target_size = max(128, min(target_size, 1024))

        qr_content = f"PAYAQR:{qr.qr_payload}"

        qr_factory = qrcode.QRCode(
            version=None,
            error_correction=ERROR_CORRECT_M,
            box_size=10,
            border=4,
        )
        qr_factory.add_data(qr_content)
        qr_factory.make(fit=True)
        image = qr_factory.make_image(fill_color="black", back_color="white").convert("RGB")

        if target_size:
            image = image.resize((target_size, target_size), resample=Image.NEAREST)

        buffer = BytesIO()
        image.save(buffer, format='PNG')
        buffer.seek(0)

        response = HttpResponse(buffer.getvalue(), content_type='image/png')
        response['Content-Disposition'] = f'inline; filename="{qr.qr_payload}.png"'
        response['Cache-Control'] = 'max-age=300'
        response['X-QR-Status'] = qr.status
        return response

    @action(detail=False, methods=['get'], url_path='special-code/me')
    def get_special_code(self, request):
        """
        دریافت کد اختصاصی کاربر
        GET /api/wallet/special-code/me/
        """
        try:
            wallet = request.user.wallet
        except Wallet.DoesNotExist:
            return Response(
                {'detail': 'Wallet not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        try:
            special_code = request.user.special_code
            if not special_code.is_active:
                return Response(
                    {
                        'code': special_code.code,
                        'is_active': False,
                        'message': 'کد اختصاصی شما غیرفعال است'
                    },
                    status=status.HTTP_200_OK
                )
            
            return Response({
                'code': special_code.code,
                'is_active': special_code.is_active,
                'created_at': special_code.created_at,
                'updated_at': special_code.updated_at
            }, status=status.HTTP_200_OK)
        except SpecialCode.DoesNotExist:
            return Response(
                {'detail': 'Special code not found. Use POST /api/wallet/special-code/generate/ to create one.'},
                status=status.HTTP_404_NOT_FOUND
            )

    @action(detail=False, methods=['post'], url_path='special-code/generate')
    def generate_special_code(self, request):
        """
        تولید یا به‌روزرسانی کد اختصاصی
        POST /api/wallet/special-code/generate/
        
        Body (اختیاری):
        {
          "code": "12345"  // اگر ارسال نشود، کد به صورت خودکار تولید می‌شود
        }
        """
        try:
            wallet = request.user.wallet
        except Wallet.DoesNotExist:
            return Response(
                {'detail': 'Wallet not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        if wallet.status != 'active':
            return Response(
                {'detail': 'Wallet is not active'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # دریافت کد از درخواست (اختیاری)
        custom_code = request.data.get('code')
        
        # اعتبارسنجی کد سفارشی (اگر ارسال شده باشد)
        if custom_code:
            custom_code = custom_code.replace(' ', '').replace('-', '').strip()
            if not custom_code.isdigit():
                return Response(
                    {'detail': 'Special code must contain only digits'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            if len(custom_code) < 4 or len(custom_code) > 10:
                return Response(
                    {'detail': 'Special code must be between 4 and 10 digits'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            # بررسی یکتایی
            if SpecialCode.objects.filter(code=custom_code).exclude(user=request.user).exists():
                return Response(
                    {'detail': 'This code is already taken by another user'},
                    status=status.HTTP_400_BAD_REQUEST
                )
        
        try:
            # ایجاد یا به‌روزرسانی کد
            special_code = SpecialCode.create_for_user(
                user=request.user,
                code=custom_code if custom_code else None
            )
            
            return Response({
                'code': special_code.code,
                'is_active': special_code.is_active,
                'created_at': special_code.created_at,
                'updated_at': special_code.updated_at,
                'message': 'کد اختصاصی با موفقیت ایجاد شد'
            }, status=status.HTTP_201_CREATED)
        except Exception as e:
            return Response(
                {'detail': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=False, methods=['post'], url_path='link/generate')
    def generate_link(self, request):
        """
        ایجاد لینک پرداخت
        POST /api/wallet/link/generate/
        """
        try:
            wallet = request.user.wallet
        except Wallet.DoesNotExist:
            return Response(
                {'detail': 'Wallet not found'},
                status=status.HTTP_404_NOT_FOUND
            )

        if wallet.status != 'active':
            return Response(
                {'detail': 'Wallet is not active'},
                status=status.HTTP_400_BAD_REQUEST
            )

        serializer = LinkGenerateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        data = serializer.validated_data
        amount = data.get('amount')
        description = data.get('description', '')
        expires_in = data.get('expires_in', 3600)  # پیش‌فرض 1 ساعت
        metadata = data.get('metadata', {})

        # ایجاد لینک پرداخت
        payment_link = PaymentLink.create_link(
            wallet=wallet,
            amount=amount,
            description=description,
            expires_in=expires_in,
            metadata=metadata
        )

        # لینک اختصاصی (فقط شناسه - برای استفاده در اپلیکیشن)
        # اپلیکیشن می‌تواند از این شناسه برای ساخت deeplink استفاده کند
        response_data = {
            'link_id': payment_link.link_id,
            'link': payment_link.link_id,  # لینک اختصاصی (مثل: pl_ECF4895E7BB8)
            'amount': payment_link.amount,
            'description': payment_link.description,
            'expires_at': payment_link.expires_at,
            'status': payment_link.status
        }

        response_serializer = LinkGenerateResponseSerializer(response_data)
        return Response(response_serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=['get'], url_path='report')
    def report(self, request):
        """
        دریافت گزارش کامل تراکنش‌ها
        GET /api/wallet/report/
        
        Query Parameters:
        - period: بازه زمانی ('week', 'month') - پیش‌فرض: 'week'
        - weeks: تعداد هفته‌ها برای نمایش (برای period=week) - پیش‌فرض: 6
        - months: تعداد ماه‌ها برای نمایش (برای period=month) - پیش‌فرض: 6
        - start_date: تاریخ شروع (ISO format: YYYY-MM-DD)
        - end_date: تاریخ پایان (ISO format: YYYY-MM-DD)
        - transaction_type: نوع تراکنش ('all', 'charge', 'debit', 'transfer_in', 'transfer_out')
        - search: جستجو در توضیحات یا transaction_id
        - page: شماره صفحه - پیش‌فرض: 1
        - page_size: تعداد در هر صفحه - پیش‌فرض: 20
        """
        try:
            wallet = request.user.wallet
        except Wallet.DoesNotExist:
            return Response(
                {'detail': 'Wallet not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # دریافت پارامترهای جستجو
        period = request.query_params.get('period', 'week')  # 'week' یا 'month'
        weeks = int(request.query_params.get('weeks', 6))
        months = int(request.query_params.get('months', 6))
        start_date_param = request.query_params.get('start_date')
        end_date_param = request.query_params.get('end_date')
        transaction_type = request.query_params.get('transaction_type', 'all')
        search_query = request.query_params.get('search', '')
        page = int(request.query_params.get('page', 1))
        page_size = int(request.query_params.get('page_size', 20))
        
        # محاسبه بازه زمانی
        now = timezone.now()
        if start_date_param:
            try:
                start_date = timezone.datetime.fromisoformat(start_date_param.replace('Z', '+00:00'))
            except:
                start_date = now - timezone.timedelta(weeks=weeks)
        else:
            if period == 'week':
                start_date = now - timezone.timedelta(weeks=weeks)
            else:  # month
                start_date = now - timezone.timedelta(days=months * 30)
        
        if end_date_param:
            try:
                end_date = timezone.datetime.fromisoformat(end_date_param.replace('Z', '+00:00'))
            except:
                end_date = now
        else:
            end_date = now
        
        # فیلتر تراکنش‌ها
        queryset = Transaction.objects.filter(
            wallet=wallet,
            created_at__gte=start_date,
            created_at__lte=end_date
        )
        
        # فیلتر بر اساس نوع تراکنش
        if transaction_type != 'all':
            queryset = queryset.filter(type=transaction_type)
        
        # جستجو
        if search_query:
            queryset = queryset.filter(
                Q(description__icontains=search_query) |
                Q(transaction_id__icontains=search_query) |
                Q(reference_id__icontains=search_query)
            )
        
        # محاسبه خلاصه (کل پرداختی و کل دریافتی)
        # پرداختی: transfer_out + debit
        total_payments = queryset.filter(
            type__in=['transfer_out', 'debit']
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0')
        
        # دریافتی: transfer_in + charge + refund
        total_receipts = queryset.filter(
            type__in=['transfer_in', 'charge', 'refund']
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0')
        
        # فرمت کردن مبالغ
        def format_amount(amount):
            return f"{amount:,.0f} تومان"
        
        summary_data = {
            'total_payments': total_payments,
            'total_receipts': total_receipts,
            'formatted_total_payments': format_amount(total_payments),
            'formatted_total_receipts': format_amount(total_receipts)
        }
        
        # محاسبه داده‌های نمودار
        chart_data = []
        if period == 'week':
            # گروه‌بندی بر اساس هفته
            weekly_data = queryset.annotate(
                week_start=TruncWeek('created_at')
            ).values('week_start').annotate(
                payments=Sum('amount', filter=Q(type__in=['transfer_out', 'debit'])),
                receipts=Sum('amount', filter=Q(type__in=['transfer_in', 'charge', 'refund']))
            ).order_by('week_start')
            
            week_num = 1
            for item in weekly_data:
                chart_data.append({
                    'period': f"هفته {week_num}",
                    'payments': item['payments'] or Decimal('0'),
                    'receipts': item['receipts'] or Decimal('0'),
                    'date': item['week_start'].date()
                })
                week_num += 1
        else:  # month
            # گروه‌بندی بر اساس ماه
            monthly_data = queryset.annotate(
                month_start=TruncMonth('created_at')
            ).values('month_start').annotate(
                payments=Sum('amount', filter=Q(type__in=['transfer_out', 'debit'])),
                receipts=Sum('amount', filter=Q(type__in=['transfer_in', 'charge', 'refund']))
            ).order_by('month_start')
            
            for item in monthly_data:
                # فرمت تاریخ به صورت 1403/05
                month_date = item['month_start']
                chart_data.append({
                    'period': f"{month_date.year}/{month_date.month:02d}",
                    'payments': item['payments'] or Decimal('0'),
                    'receipts': item['receipts'] or Decimal('0'),
                    'date': month_date.date()
                })
        
        # دریافت لیست تراکنش‌ها (با pagination)
        paginator = Paginator(queryset.order_by('-created_at'), page_size)
        page_obj = paginator.get_page(page)
        
        transactions_serializer = TransactionSerializer(page_obj.object_list, many=True)
        
        # آماده‌سازی پاسخ
        report_data = {
            'summary': summary_data,
            'chart_data': chart_data,
            'transactions': transactions_serializer.data,
            'total_transactions': paginator.count,
            'has_more': page_obj.has_next()
        }
        
        serializer = TransactionReportSerializer(report_data)
        return Response(serializer.data, status=status.HTTP_200_OK)


class TransactionViewSet(viewsets.ViewSet):
    """
    ViewSet برای مدیریت تراکنش‌ها
    """
    permission_classes = [permissions.IsAuthenticated]
    
    def retrieve(self, request, pk=None):
        """
        دریافت جزئیات یک تراکنش
        GET /api/wallet/transactions/{transaction_id}/
        """
        try:
            wallet = request.user.wallet
        except Wallet.DoesNotExist:
            return Response(
                {'detail': 'Wallet not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        try:
            transaction = Transaction.objects.get(
                transaction_id=pk,
                wallet=wallet
            )
        except Transaction.DoesNotExist:
            return Response(
                {'detail': 'Transaction not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        serializer = TransactionDetailSerializer(transaction)
        return Response(serializer.data, status=status.HTTP_200_OK)

