"""
Viewهای مربوط به callback پرداخت
"""
from rest_framework import status, views
from rest_framework.response import Response
from django.db import transaction as db_transaction

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
        # دریافت داده‌ها از درخواست
        data = request.query_params.dict()
        if hasattr(request.data, 'dict'):
            data.update(request.data.dict())
        else:
            data.update(request.data)
        authority = data.get('Authority') or data.get('authority')
        invoice_id = data.get('invoiceid') or data.get('InvoiceID') or data.get('InvoiceId') or data.get('request_id')
        
        payment_request = None
        
        if authority:
            payment_request = PaymentRequest.objects.filter(
                authority=authority,
                status='pending'
            ).first()
        
        # جستجو با InvoiceID عددی (از metadata)
        if payment_request is None and invoice_id:
            # ابتدا با request_id جستجو می‌کنیم
            payment_request = PaymentRequest.objects.filter(
                request_id=str(invoice_id),
                status='pending'
            ).first()
            
            # اگر پیدا نشد، با InvoiceID عددی از metadata جستجو می‌کنیم
            if payment_request is None:
                payment_request = PaymentRequest.objects.filter(
                    metadata__invoice_id=str(invoice_id),
                    status='pending'
                ).first()
        
        if payment_request is None:
            return Response(
                {'detail': 'Payment request not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        resp_code = data.get('respcode') or data.get('RespCode') or data.get('status') or data.get('Status')
        if str(resp_code) not in {'0', '00', '000', 'ok', 'OK'}:
            payment_request.status = 'failed'
            payment_request.metadata = {
                **(payment_request.metadata or {}),
                'callback_payload': data
            }
            payment_request.save(update_fields=['status', 'metadata', 'updated_at'])
            return Response(
                {'detail': 'Payment was cancelled or failed'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # تایید پرداخت از درگاه
        verification_metadata = {}
        digital_receipt = data.get('digitalreceipt') or data.get('DigitalReceipt')
        if not digital_receipt:
            payment_request.status = 'failed'
            payment_request.metadata = {
                **(payment_request.metadata or {}),
                'callback_payload': data,
                'error': 'digital_receipt missing'
            }
            payment_request.save(update_fields=['status', 'metadata', 'updated_at'])
            return Response(
                {'detail': 'digital receipt is required for verification'},
                status=status.HTTP_400_BAD_REQUEST
            )
        payment_extra = (payment_request.metadata or {}).get('gateway_extra', {})
        verification_metadata = {
            'digital_receipt': digital_receipt,
            'terminal_id': payment_extra.get('terminal_id'),
            'invoice_id': invoice_id or payment_extra.get('invoice_id'),
        }
        authority_for_verify = payment_request.authority or digital_receipt

        verify_result = PaymentGatewayService.verify_payment(
            authority=authority_for_verify,
            amount=payment_request.amount,
            metadata=verification_metadata
        )
        
        if not verify_result.get('success'):
            payment_request.status = 'failed'
            updated_metadata = payment_request.metadata or {}
            updated_metadata.setdefault('callback_payload', data)
            updated_metadata['verification_error'] = verify_result.get('error')
            payment_request.metadata = updated_metadata
            payment_request.save(update_fields=['status', 'metadata', 'updated_at'])
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
                updated_metadata = payment_request.metadata or {}
                updated_metadata.setdefault('callback_payload', data)
                if verify_result.get('extra'):
                    updated_metadata['verification_extra'] = verify_result['extra']
                payment_request.metadata = updated_metadata
                payment_request.save(update_fields=['status', 'ref_id', 'transaction', 'metadata', 'updated_at'])
            
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
            updated_metadata = payment_request.metadata or {}
            updated_metadata.setdefault('callback_payload', data)
            updated_metadata['internal_error'] = str(e)
            payment_request.metadata = updated_metadata
            payment_request.save(update_fields=['status', 'metadata', 'updated_at'])
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

