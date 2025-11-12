# Generated manually for transaction transfer metadata updates
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('wallet', '0002_paymentrequest_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='transaction',
            name='transfer_method',
            field=models.CharField(blank=True, choices=[('phone', 'انتقال با شماره موبایل'), ('contact', 'انتقال به مخاطب ذخیره‌شده'), ('wallet', 'انتقال به کیف پول انتخابی'), ('qr', 'انتقال با QR Code'), ('iban', 'انتقال با شماره شبا'), ('card', 'انتقال با شماره کارت'), ('link', 'انتقال با لینک پرداخت')], max_length=30, null=True, verbose_name='روش انتقال'),
        ),
        migrations.AddField(
            model_name='transaction',
            name='metadata',
            field=models.JSONField(blank=True, default=dict, verbose_name='اطلاعات اضافی'),
        ),
        migrations.AddIndex(
            model_name='transaction',
            index=models.Index(fields=['transfer_method'], name='transaction_transfer__d40fe0_idx'),
        ),
        migrations.AlterField(
            model_name='paymentrequest',
            name='gateway',
            field=models.CharField(default='mock', max_length=50, verbose_name='درگاه'),
        ),
    ]



