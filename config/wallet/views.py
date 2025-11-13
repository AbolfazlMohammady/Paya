from rest_framework import status, views, viewsets, permissions
from rest_framework.response import Response
from rest_framework.decorators import action
from django.utils import timezone
from django.db import transaction as db_transaction
from django.core.paginator import Paginator
from django.db.models import Q
from decimal import Decimal

from .models import Wallet, Transaction, PaymentRequest
from .serializers import (
    WalletSerializer, WalletCreateSerializer,
    ChargeSerializer, DebitSerializer, TransferSerializer,
    TransactionSerializer, TransactionDetailSerializer,
    BalanceSerializer, ChargeResponseSerializer,
    DebitResponseSerializer, TransferResponseSerializer,
    GatewayChargeSerializer, GatewayChargeResponseSerializer
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
        
        # ایجاد کیف پول
        wallet = Wallet.objects.create(
            user=request.user,
            currency=currency,
            balance=Decimal('0'),
            status='active'
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
                payment_id=serializer.validated_data.get('payment_id')
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
                reference_id=serializer.validated_data.get('reference_id')
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
        recipient_wallet_id = serializer.validated_data.get('recipient_wallet_id')
        amount = serializer.validated_data['amount']
        description = serializer.validated_data.get('description', '')
        
        recipient_user = None
        recipient_wallet = None
        
        if recipient_wallet_id:
            if sender_wallet.id == recipient_wallet_id:
                return Response(
                    {'detail': 'Cannot transfer to your own wallet'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            try:
                recipient_wallet = Wallet.objects.select_related('user').get(id=recipient_wallet_id)
                recipient_user = recipient_wallet.user
            except Wallet.DoesNotExist:
                return Response(
                    {'detail': 'Recipient wallet not found'},
                    status=status.HTTP_404_NOT_FOUND
                )
        else:
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
                metadata=transfer_metadata
            )
            
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

