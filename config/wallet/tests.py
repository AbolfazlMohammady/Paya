from django.test import TestCase
from django.contrib.auth import get_user_model
from decimal import Decimal
from unittest.mock import patch, Mock
from .models import Wallet, Transaction, PaymentRequest
from .utils import charge_wallet, debit_wallet, transfer_money
from .payment_gateway import PaymentGatewayService

User = get_user_model()


class WalletModelTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(phone='09123456789', password='testpass123')
        self.wallet = self.user.wallet
        self.wallet.balance = Decimal('100000')
        self.wallet.currency = 'IRR'
        self.wallet.status = 'active'
        self.wallet.save(update_fields=['balance', 'currency', 'status', 'updated_at'])
    
    def test_wallet_creation(self):
        self.assertEqual(self.wallet.user, self.user)
        self.assertEqual(self.wallet.balance, Decimal('100000'))
        self.assertEqual(self.wallet.currency, 'IRR')
        self.assertEqual(self.wallet.status, 'active')
    
    def test_can_transfer(self):
        self.assertTrue(self.wallet.can_transfer(Decimal('50000')))
        self.assertFalse(self.wallet.can_transfer(Decimal('150000')))
    
    def test_get_formatted_balance(self):
        formatted = self.wallet.get_formatted_balance()
        self.assertIn('100,000', formatted)


class TransactionModelTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(phone='09123456789', password='testpass123')
        self.wallet = self.user.wallet
        self.wallet.balance = Decimal('100000')
        self.wallet.currency = 'IRR'
        self.wallet.save(update_fields=['balance', 'currency', 'updated_at'])
    
    def test_transaction_creation(self):
        transaction = Transaction.objects.create(
            transaction_id=Transaction.generate_transaction_id(),
            wallet=self.wallet,
            type='charge',
            amount=Decimal('50000'),
            balance_before=Decimal('100000'),
            balance_after=Decimal('150000'),
            status='completed'
        )
        self.assertEqual(transaction.wallet, self.wallet)
        self.assertEqual(transaction.amount, Decimal('50000'))
        self.assertEqual(transaction.type, 'charge')


class WalletUtilsTest(TestCase):
    def setUp(self):
        self.user1 = User.objects.create_user(phone='09123456789', password='testpass123')
        self.user2 = User.objects.create_user(phone='09123456780', password='testpass123')
        self.wallet1 = self.user1.wallet
        self.wallet2 = self.user2.wallet
        self.wallet1.balance = Decimal('100000')
        self.wallet1.currency = 'IRR'
        self.wallet1.status = 'active'
        self.wallet1.save(update_fields=['balance', 'currency', 'status', 'updated_at'])
        self.wallet2.balance = Decimal('50000')
        self.wallet2.currency = 'IRR'
        self.wallet2.status = 'active'
        self.wallet2.save(update_fields=['balance', 'currency', 'status', 'updated_at'])
    
    def test_charge_wallet(self):
        transaction = charge_wallet(
            wallet=self.wallet1,
            amount=Decimal('50000'),
            description='Test charge'
        )
        self.wallet1.refresh_from_db()
        self.assertEqual(self.wallet1.balance, Decimal('150000'))
        self.assertEqual(transaction.type, 'charge')
        self.assertEqual(transaction.status, 'completed')
    
    def test_debit_wallet(self):
        transaction = debit_wallet(
            wallet=self.wallet1,
            amount=Decimal('30000'),
            description='Test debit'
        )
        self.wallet1.refresh_from_db()
        self.assertEqual(self.wallet1.balance, Decimal('70000'))
        self.assertEqual(transaction.type, 'debit')
        self.assertEqual(transaction.status, 'completed')
    
    def test_debit_insufficient_balance(self):
        with self.assertRaises(ValueError):
            debit_wallet(
                wallet=self.wallet1,
                amount=Decimal('150000'),
                description='Test debit'
            )
    
    def test_transfer_money(self):
        sender_transaction, recipient_transaction = transfer_money(
            sender_wallet=self.wallet1,
            recipient_wallet=self.wallet2,
            amount=Decimal('30000'),
            description='Test transfer',
            method='phone',
            metadata={'note': 'friends'}
        )
        self.wallet1.refresh_from_db()
        self.wallet2.refresh_from_db()
        self.assertEqual(self.wallet1.balance, Decimal('70000'))
        self.assertEqual(self.wallet2.balance, Decimal('80000'))
        self.assertEqual(sender_transaction.type, 'transfer_out')
        self.assertEqual(recipient_transaction.type, 'transfer_in')
        self.assertEqual(sender_transaction.transfer_method, 'phone')
        self.assertEqual(recipient_transaction.transfer_method, 'phone')
        self.assertEqual(sender_transaction.metadata.get('direction'), 'outgoing')
        self.assertEqual(recipient_transaction.metadata.get('direction'), 'incoming')
        self.assertEqual(sender_transaction.metadata.get('note'), 'friends')
        self.assertEqual(recipient_transaction.metadata.get('note'), 'friends')


class WalletSignalTest(TestCase):
    def test_wallet_created_on_user_creation(self):
        phone = '09120001111'
        user = User.objects.create_user(phone=phone, password='testpass123')
        self.assertTrue(hasattr(user, 'wallet'))
        self.assertEqual(user.wallet.balance, Decimal('0'))
        self.assertEqual(user.wallet.currency, 'IRR')
        self.assertEqual(user.wallet.status, 'active')


class PaymentGatewayTest(TestCase):
    """تست درخواست شارژ از طریق درگاه پرداخت"""
    
    def setUp(self):
        self.user = User.objects.create_user(phone='09123456789', password='testpass123')
        self.wallet = self.user.wallet
        self.wallet.status = 'active'
        self.wallet.save()
    
    def test_invoice_id_is_numeric(self):
        """تست اینکه InvoiceID برای درگاه عددی است"""
        invoice_id = PaymentRequest.generate_invoice_id_for_gateway()
        # باید فقط عدد باشد (نه req_xxx)
        self.assertTrue(invoice_id.isdigit(), f"InvoiceID باید عددی باشد، اما {invoice_id} است")
        # باید حداکثر 20 رقم باشد
        self.assertLessEqual(len(invoice_id), 20, f"InvoiceID باید حداکثر 20 رقم باشد")
        # باید حداقل 10 رقم باشد (timestamp)
        self.assertGreaterEqual(len(invoice_id), 10, f"InvoiceID باید حداقل 10 رقم باشد")
    
    @patch('wallet.payment_gateway.requests.post')
    def test_gateway_request_with_numeric_invoice_id(self, mock_post):
        """تست ارسال درخواست به درگاه با InvoiceID عددی"""
        # شبیه‌سازی پاسخ موفق از درگاه
        mock_response = Mock()
        mock_response.json.return_value = {
            'Status': 0,
            'Accesstoken': 'TEST_TOKEN_12345',
            'Message': 'Success'
        }
        mock_response.raise_for_status = Mock()
        mock_post.return_value = mock_response
        
        # تولید InvoiceID عددی
        invoice_id = PaymentRequest.generate_invoice_id_for_gateway()
        
        # ایجاد درخواست پرداخت
        result = PaymentGatewayService.create_payment_request(
            amount=Decimal('100000'),
            description='تست شارژ',
            callback_url='https://example.com/callback',
            metadata={
                'invoice_id': invoice_id,
                'wallet_id': self.wallet.id,
                'user_id': self.user.id,
            }
        )
        
        # بررسی‌ها
        self.assertTrue(result.get('success'), "درخواست باید موفق باشد")
        self.assertIsNotNone(result.get('payment_url'), "payment_url باید وجود داشته باشد")
        self.assertIn('sepehr.shaparak.ir', result.get('payment_url', ''), "payment_url باید به درگاه سپهر اشاره کند")
        
        # بررسی اینکه InvoiceID عددی به درگاه ارسال شده
        call_args = mock_post.call_args
        request_body = call_args[1]['json']  # json parameter
        self.assertTrue(str(request_body['InvoiceID']).isdigit(), 
                       f"InvoiceID باید عددی باشد، اما {request_body['InvoiceID']} است")
        self.assertEqual(request_body['InvoiceID'], invoice_id, 
                        "InvoiceID ارسالی باید با InvoiceID تولید شده یکسان باشد")
    
    @patch('wallet.payment_gateway.SepehrPaymentGateway._is_mock_mode')
    @patch('wallet.payment_gateway.requests.post')
    def test_gateway_charge_viewset_integration(self, mock_post, mock_is_mock_mode):
        """تست یکپارچه ViewSet برای درخواست شارژ"""
        from rest_framework.test import APIClient
        from rest_framework_simplejwt.tokens import RefreshToken
        
        # فعال کردن Mock Mode
        mock_is_mock_mode.return_value = True
        
        # شبیه‌سازی پاسخ موفق از درگاه (برای حالت غیر Mock)
        mock_response = Mock()
        mock_response.json.return_value = {
            'Status': 0,
            'Accesstoken': 'TEST_TOKEN_12345',
            'Message': 'Success'
        }
        mock_response.raise_for_status = Mock()
        mock_post.return_value = mock_response
        
        # دریافت token
        refresh = RefreshToken.for_user(self.user)
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f'Bearer {refresh.access_token}')
        
        # ارسال درخواست
        response = client.post('/api/wallet/charge-gateway/', {
            'amount': '100000',
            'description': 'تست شارژ'
        }, format='json')
        
        # بررسی پاسخ
        self.assertEqual(response.status_code, 201, 
                       f"کد وضعیت باید 201 باشد، اما {response.status_code} است. پاسخ: {response.data}")
        data = response.json()
        self.assertIn('payment_url', data, "پاسخ باید شامل payment_url باشد")
        self.assertIn('authority', data, "پاسخ باید شامل authority باشد")
        self.assertIn('request_id', data, "پاسخ باید شامل request_id باشد")
        
        # بررسی اینکه PaymentRequest ایجاد شده
        payment_request = PaymentRequest.objects.get(request_id=data['request_id'])
        self.assertIsNotNone(payment_request.metadata.get('invoice_id'), 
                           "metadata باید شامل invoice_id باشد")
        invoice_id = payment_request.metadata['invoice_id']
        self.assertTrue(str(invoice_id).isdigit(), 
                      f"invoice_id در metadata باید عددی باشد: {invoice_id}")


