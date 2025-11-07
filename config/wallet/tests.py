from django.test import TestCase
from django.contrib.auth import get_user_model
from decimal import Decimal
from .models import Wallet, Transaction
from .utils import charge_wallet, debit_wallet, transfer_money

User = get_user_model()


class WalletModelTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(phone='09123456789', password='testpass123')
        self.wallet = Wallet.objects.create(
            user=self.user,
            balance=Decimal('100000'),
            currency='IRR',
            status='active'
        )
    
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
        self.wallet = Wallet.objects.create(
            user=self.user,
            balance=Decimal('100000'),
            currency='IRR'
        )
    
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
        self.wallet1 = Wallet.objects.create(
            user=self.user1,
            balance=Decimal('100000'),
            currency='IRR',
            status='active'
        )
        self.wallet2 = Wallet.objects.create(
            user=self.user2,
            balance=Decimal('50000'),
            currency='IRR',
            status='active'
        )
    
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
            description='Test transfer'
        )
        self.wallet1.refresh_from_db()
        self.wallet2.refresh_from_db()
        self.assertEqual(self.wallet1.balance, Decimal('70000'))
        self.assertEqual(self.wallet2.balance, Decimal('80000'))
        self.assertEqual(sender_transaction.type, 'transfer_out')
        self.assertEqual(recipient_transaction.type, 'transfer_in')

