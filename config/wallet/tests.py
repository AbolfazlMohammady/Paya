from django.test import TestCase
from django.contrib.auth import get_user_model
from decimal import Decimal
from .models import Wallet, Transaction
from .utils import charge_wallet, debit_wallet, transfer_money

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


