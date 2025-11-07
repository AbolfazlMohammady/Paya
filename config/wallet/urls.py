from django.urls import path
from .views import WalletViewSet, TransactionViewSet
from .payment_views import PaymentCallbackView, PaymentStatusView

# تعریف viewها به صورت دستی برای مطابقت با مستندات
wallet_create = WalletViewSet.as_view({'post': 'create'})
wallet_me = WalletViewSet.as_view({'get': 'retrieve'})
wallet_balance = WalletViewSet.as_view({'get': 'balance'})
wallet_charge = WalletViewSet.as_view({'post': 'charge'})
wallet_charge_gateway = WalletViewSet.as_view({'post': 'charge_gateway'})
wallet_debit = WalletViewSet.as_view({'post': 'debit'})
wallet_transfer = WalletViewSet.as_view({'post': 'transfer'})
wallet_transactions = WalletViewSet.as_view({'get': 'transactions'})
transaction_detail = TransactionViewSet.as_view({'get': 'retrieve'})

urlpatterns = [
    path('create/', wallet_create, name='wallet-create'),
    path('me/', wallet_me, name='wallet-me'),
    path('balance/', wallet_balance, name='wallet-balance'),
    path('charge/', wallet_charge, name='wallet-charge'),
    path('charge-gateway/', wallet_charge_gateway, name='wallet-charge-gateway'),
    path('debit/', wallet_debit, name='wallet-debit'),
    path('transfer/', wallet_transfer, name='wallet-transfer'),
    path('transactions/', wallet_transactions, name='wallet-transactions'),
    path('transactions/<str:pk>/', transaction_detail, name='transaction-detail'),
    # Payment callback and status
    path('payment-callback/', PaymentCallbackView.as_view(), name='payment-callback'),
    path('payment-status/<str:request_id>/', PaymentStatusView.as_view(), name='payment-status'),
]

