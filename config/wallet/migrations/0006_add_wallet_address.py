# Generated manually for adding wallet_address field
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('wallet', '0005_walletqrcode_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='wallet',
            name='wallet_address',
            field=models.CharField(max_length=24, null=True, unique=True, db_index=True, verbose_name='آدرس کیف پول (24 رقمی)'),
        ),
        migrations.AddIndex(
            model_name='wallet',
            index=models.Index(fields=['wallet_address'], name='wallets_wallet__idx'),
        ),
    ]

