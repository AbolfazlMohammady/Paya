"""
Viewهای مربوط به callback پرداخت
"""
from rest_framework import status, views
from rest_framework.response import Response
from django.db import transaction as db_transaction
from django.utils import timezone

from .models import PaymentRequest, Wallet
from .payment_gateway import PaymentGatewayService
from .utils import charge_wallet


class PaymentCallbackView(views.APIView):
    """
    View برای دریافت callback از درگاه پرداخت
    این endpoint باید public باشد (نیاز به authentication ندارد)
    """
    permission_classes = []  # Public endpoint
    
    def post(self, request):
        """
        دریافت callback از درگاه پرداخت
        POST /api/wallet/payment-callback/
        """
        # دریافت authority از درخواست
        authority = request.data.get('Authority') or request.query_params.get('Authority')
        status_code = request.data.get('Status') or request.query_params.get('Status')
        
        if not authority:
            return Response(
                {'detail': 'Authority is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # یافتن درخواست پرداخت
        try:
            payment_request = PaymentRequest.objects.get(
                authority=authority,
                status='pending'
            )
        except PaymentRequest.DoesNotExist:
            return Response(
                {'detail': 'Payment request not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # بررسی وضعیت از درگاه
        if status_code != 'OK':
            payment_request.status = 'failed'
            payment_request.save()
            return Response(
                {'detail': 'Payment was cancelled or failed'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # تایید پرداخت از درگاه
        verify_result = PaymentGatewayService.verify_payment(
            authority=authority,
            amount=payment_request.amount
        )
        
        if not verify_result.get('success'):
            payment_request.status = 'failed'
            payment_request.save()
            return Response(
                {'detail': verify_result.get('error', 'Payment verification failed')},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # شارژ کیف پول
        try:
            with db_transaction.atomic():
                # شارژ کیف پول
                transaction = charge_wallet(
                    wallet=payment_request.wallet,
                    amount=payment_request.amount,
                    description=payment_request.description or 'شارژ کیف پول از درگاه',
                    payment_method=payment_request.gateway,
                    payment_id=payment_request.request_id
                )
                
                # به‌روزرسانی درخواست پرداخت
                payment_request.status = 'completed'
                payment_request.ref_id = verify_result.get('ref_id')
                payment_request.transaction = transaction
                payment_request.save()
            
            return Response({
                'status': 'success',
                'request_id': payment_request.request_id,
                'transaction_id': transaction.transaction_id,
                'amount': transaction.amount,
                'balance_after': transaction.balance_after,
                'message': 'Payment completed successfully'
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            payment_request.status = 'failed'
            payment_request.save()
            return Response(
                {'detail': f'Error charging wallet: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def get(self, request):
        """
        GET callback (برای درگاه‌هایی که GET استفاده می‌کنند)
        """
        return self.post(request)


class PaymentStatusView(views.APIView):
    """
    View برای بررسی وضعیت درخواست پرداخت
    """
    from rest_framework import permissions as drf_permissions
    permission_classes = [drf_permissions.IsAuthenticated]
    
    def get(self, request, request_id):
        """
        بررسی وضعیت درخواست پرداخت
        GET /api/wallet/payment-status/{request_id}/
        """
        try:
            payment_request = PaymentRequest.objects.get(
                request_id=request_id,
                wallet__user=request.user
            )
        except PaymentRequest.DoesNotExist:
            return Response(
                {'detail': 'Payment request not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        response_data = {
            'request_id': payment_request.request_id,
            'amount': payment_request.amount,
            'status': payment_request.status,
            'gateway': payment_request.gateway,
            'authority': payment_request.authority,
            'ref_id': payment_request.ref_id,
            'created_at': payment_request.created_at,
            'updated_at': payment_request.updated_at
        }
        
        if payment_request.transaction:
            response_data['transaction_id'] = payment_request.transaction.transaction_id
            response_data['balance_after'] = payment_request.transaction.balance_after
        
        return Response(response_data, status=status.HTTP_200_OK)

