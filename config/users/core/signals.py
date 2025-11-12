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

    Wallet.objects.get_or_create(
        user=instance,
        defaults={
            'balance': Decimal('0'),
            'currency': 'IRR',
            'status': 'active',
        }
    )


