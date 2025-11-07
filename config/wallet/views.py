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
        
        recipient_phone = serializer.validated_data['recipient_phone']
        amount = serializer.validated_data['amount']
        description = serializer.validated_data.get('description', '')
        
        # بررسی اینکه کاربر به خودش پول نزند
        if str(request.user.phone) == recipient_phone:
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
            sender_transaction, recipient_transaction = transfer_money(
                sender_wallet=sender_wallet,
                recipient_wallet=recipient_wallet,
                amount=amount,
                description=description
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
                'created_at': sender_transaction.created_at
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
        gateway = serializer.validated_data.get('gateway', 'zarinpal')
        callback_url = serializer.validated_data.get('callback_url', '')
        
        # اگر callback_url داده نشده، از تنظیمات استفاده می‌کنیم
        if not callback_url:
            base_url = getattr(settings, 'BASE_URL', 'http://localhost:8000')
            callback_url = f"{base_url}/api/wallet/payment-callback/"
        
        # ایجاد درخواست پرداخت
        payment_result = PaymentGatewayService.create_payment_request(
            amount=amount,
            description=description,
            callback_url=callback_url,
            user_phone=str(request.user.phone),
            user_email=None
        )
        
        if not payment_result.get('success'):
            return Response(
                {'detail': payment_result.get('error', 'Payment gateway error')},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # ذخیره درخواست پرداخت
        payment_request = PaymentRequest.objects.create(
            request_id=PaymentRequest.generate_request_id(),
            wallet=wallet,
            amount=amount,
            description=description,
            gateway=gateway,
            authority=payment_result['authority'],
            callback_url=callback_url,
            status='pending'
        )
        
        # محاسبه زمان انقضا (30 دقیقه)
        expires_at = timezone.now() + timezone.timedelta(minutes=30)
        
        response_data = {
            'request_id': payment_request.request_id,
            'payment_url': payment_result['payment_url'],
            'authority': payment_result['authority'],
            'amount': amount,
            'gateway': gateway,
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

