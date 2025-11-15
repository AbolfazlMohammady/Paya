from decimal import Decimal

from django.db.models.signals import post_save
from django.dispatch import receiver

from users.core.models import User
from wallet.models import Wallet


@receiver(post_save, sender=User)
def create_user_wallet(sender, instance: User, created: bool, **kwargs):
    """
    ایجاد خودکار کیف پول پس از ساخت کاربر.
    """
    if not created:
        return

    wallet, created = Wallet.objects.get_or_create(
        user=instance,
        defaults={
            'balance': Decimal('0'),
            'currency': 'IRR',
            'status': 'active',
            'wallet_address': Wallet.generate_wallet_address(),
        }
    )
    
    # اگر کیف پول از قبل وجود داشت اما wallet_address نداشت، آن را اضافه می‌کنیم
    if not created and not wallet.wallet_address:
        wallet.wallet_address = Wallet.generate_wallet_address()
        wallet.save(update_fields=['wallet_address'])


