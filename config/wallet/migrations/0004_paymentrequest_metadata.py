# Generated manually: add metadata field to PaymentRequest
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('wallet', '0003_transaction_transfer_method'),
    ]

    operations = [
        migrations.AlterField(
            model_name='paymentrequest',
            name='gateway',
            field=models.CharField(default='sepehr', max_length=50, verbose_name='درگاه'),
        ),
        migrations.AddField(
            model_name='paymentrequest',
            name='metadata',
            field=models.JSONField(blank=True, default=dict, verbose_name='اطلاعات اضافی'),
        ),
    ]

