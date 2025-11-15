from django.db import models
from django.contrib.auth.models import AbstractUser, UserManager
from django.core.validators import MinLengthValidator, MaxLengthValidator
from django.utils.translation import gettext_lazy as _
from phonenumber_field.modelfields import PhoneNumberField
from django.utils import timezone
from datetime import timedelta
from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes.fields import GenericForeignKey

from users.core.utils.utils import path_image_or_file
from users.core.encryption import get_encryption_service

class CustomUserManager(UserManager):
    def create_user(self, phone , password=None, **extra_fields):
        if not phone:
            raise ValueError(_('The phone must be set'))
        
        user = self.model(phone=phone, password=password,**extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user
    
    def create_superuser(self, phone , password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)

        if extra_fields.get('is_staff') is not True:
            raise ValueError(_('Superuser must have is_staff=True.'))
        if extra_fields.get('is_superuser') is not True:
            raise ValueError(_('Superuser must have is_superuser=True.'))
        return self.create_user(phone ,password, **extra_fields)


class User(AbstractUser):
    ROLE_CHOICES = [
        ('user', 'کاربر عادی'),
        ('admin', 'مدیر'),
        ('staff', 'کارمند'),
        ('auditor', 'ممیزی'),
    ]
    
    username =None
    first_name =None
    last_name = None
    email = None
    fullname = models.CharField(_("نام, نام خانوادگی"),max_length=255,blank=True, null=True)
    phone = PhoneNumberField(_("شماره تلفن "),unique=True)
    image = models.ImageField(_("عکس پروفایل"),upload_to=path_image_or_file, blank=True, null=True)
    national_code = models.CharField(_("کدملی"),validators=[(MaxLengthValidator(10))],blank=True, null=True, max_length=10)
    city = models.CharField(_("شهر"),max_length=255,blank=True, null=True)
    role = models.CharField(
        max_length=20,
        choices=ROLE_CHOICES,
        default='user',
        verbose_name=_('نقش کاربر')
    )

    objects= CustomUserManager()

    REQUIRED_FIELDS= []
    USERNAME_FIELD = "phone"
    EMAIL_FIELD = ""

    def __str__(self):
        return str(self.phone)
    
    def save(self,*args, **kwargs):
        if self.pk and self.image:
            old_instance = self.__class__.objects.filter(pk=self.pk).only('image').first()
            if old_instance and old_instance.image and old_instance.image != self.image:
                old_instance.image.delete(save=False)
        
        # رمزنگاری کد ملی در صورت وجود
        if self.national_code:
            try:
                enc_service = get_encryption_service()
                # فقط در صورت تغییر رمزنگاری می‌کنیم
                if not self.national_code.startswith('enc:'):
                    self.national_code = 'enc:' + enc_service.encrypt(self.national_code)
            except Exception:
                # در صورت خطا در رمزنگاری، بدون رمزنگاری ذخیره می‌کنیم
                pass
        
        super().save(*args, **kwargs)
    
    def get_national_code(self):
        """دریافت کد ملی رمزگشایی شده"""
        if not self.national_code:
            return None
        if self.national_code.startswith('enc:'):
            try:
                enc_service = get_encryption_service()
                return enc_service.decrypt(self.national_code[4:])
            except Exception:
                return None
        return self.national_code

    def delete(self,*args, **kwargs):
        if self.image:
            self.image.delete(save=False)

        super().delete(*args, **kwargs)


class OTP(models.Model):
    phone = models.CharField(max_length=13)
    code = models.CharField(max_length=4)
    created_at = models.DateTimeField(auto_now_add=True)
    expire_at = models.DateTimeField()

    def save(self, *args, **kwargs):
        if not self.expire_at:
            self.expire_at = timezone.now() + timedelta(minutes=2)
        super().save(*args, **kwargs)

    def is_valid(self) -> bool:
        return timezone.now() <= self.expire_at
    
    def __str__(self):
        return f'phone {self.phone} --> {self.code}'


class AuditLog(models.Model):
    """
    مدل لاگ امنیتی برای ثبت تمام رویدادهای مهم سیستم
    طبق الزامات کاشف: ممیزی امنیت (لاگ)
    """
    
    EVENT_TYPE_CHOICES = [
        ('auth_success', 'احراز هویت موفق'),
        ('auth_failed', 'احراز هویت ناموفق'),
        ('auth_logout', 'خروج از سیستم'),
        ('user_create', 'ایجاد کاربر'),
        ('user_update', 'به‌روزرسانی کاربر'),
        ('user_delete', 'حذف کاربر'),
        ('user_activate', 'فعال‌سازی کاربر'),
        ('user_deactivate', 'غیرفعال‌سازی کاربر'),
        ('transaction_create', 'ایجاد تراکنش'),
        ('transaction_update', 'به‌روزرسانی تراکنش'),
        ('wallet_create', 'ایجاد کیف پول'),
        ('wallet_update', 'به‌روزرسانی کیف پول'),
        ('wallet_suspend', 'تعلیق کیف پول'),
        ('wallet_activate', 'فعال‌سازی کیف پول'),
        ('config_change', 'تغییر پیکربندی'),
        ('security_event', 'رویداد امنیتی'),
        ('access_denied', 'دسترسی رد شد'),
        ('data_export', 'خروج اطلاعات'),
        ('admin_action', 'اقدام مدیریتی'),
        ('system_error', 'خطای سیستم'),
        ('session_start', 'شروع نشست'),
        ('session_end', 'پایان نشست'),
        ('password_change', 'تغییر رمز عبور'),
        ('permission_change', 'تغییر دسترسی'),
        ('other', 'سایر'),
    ]
    
    RESULT_CHOICES = [
        ('success', 'موفق'),
        ('failed', 'ناموفق'),
        ('pending', 'در انتظار'),
        ('cancelled', 'لغو شده'),
    ]
    
    # اطلاعات اصلی رویداد
    event_type = models.CharField(
        max_length=50,
        choices=EVENT_TYPE_CHOICES,
        verbose_name=_('نوع رویداد')
    )
    event_description = models.TextField(
        verbose_name=_('توضیحات رویداد')
    )
    result = models.CharField(
        max_length=20,
        choices=RESULT_CHOICES,
        default='success',
        verbose_name=_('نتیجه')
    )
    
    # اطلاعات کاربر و نشست
    user = models.ForeignKey(
        'User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='audit_logs',
        verbose_name=_('کاربر')
    )
    username = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        verbose_name=_('نام کاربری')
    )
    user_phone = models.CharField(
        max_length=20,
        blank=True,
        null=True,
        verbose_name=_('شماره تلفن کاربر')
    )
    
    # اطلاعات درخواست
    ip_address = models.GenericIPAddressField(
        null=True,
        blank=True,
        verbose_name=_('آدرس IP')
    )
    user_agent = models.TextField(
        blank=True,
        null=True,
        verbose_name=_('User Agent')
    )
    request_method = models.CharField(
        max_length=10,
        blank=True,
        null=True,
        verbose_name=_('روش درخواست')
    )
    request_path = models.CharField(
        max_length=500,
        blank=True,
        null=True,
        verbose_name=_('مسیر درخواست')
    )
    request_id = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        db_index=True,
        verbose_name=_('شناسه درخواست')
    )
    
    # اطلاعات اضافی
    metadata = models.JSONField(
        default=dict,
        blank=True,
        verbose_name=_('اطلاعات اضافی')
    )
    
    # اطلاعات امنیتی
    integrity_hash = models.CharField(
        max_length=64,
        blank=True,
        null=True,
        db_index=True,
        verbose_name=_('Hash صحت')
    )
    
    # Generic Foreign Key برای ارتباط با سایر مدل‌ها
    content_type = models.ForeignKey(
        ContentType,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    object_id = models.PositiveIntegerField(null=True, blank=True)
    related_object = GenericForeignKey('content_type', 'object_id')
    
    # زمان‌بندی
    created_at = models.DateTimeField(
        auto_now_add=True,
        db_index=True,
        verbose_name=_('تاریخ و زمان')
    )
    
    class Meta:
        db_table = 'audit_logs'
        ordering = ['-created_at']
        verbose_name = _('لاگ امنیتی')
        verbose_name_plural = _('لاگ‌های امنیتی')
        indexes = [
            models.Index(fields=['-created_at', 'event_type']),
            models.Index(fields=['user', '-created_at']),
            models.Index(fields=['ip_address', '-created_at']),
            models.Index(fields=['event_type', 'result']),
            models.Index(fields=['request_id']),
        ]
    
    def __str__(self):
        return f"{self.event_type} - {self.user_phone or self.username} - {self.created_at}"
    
    def save(self, *args, **kwargs):
        """
        محاسبه hash صحت قبل از ذخیره
        """
        # محاسبه hash برای تشخیص تغییرات
        from users.core.encryption import EncryptionService
        hash_data = f"{self.event_type}{self.user_id}{self.ip_address}{self.created_at}{self.event_description}"
        self.integrity_hash = EncryptionService.hash_data(hash_data)
        
        super().save(*args, **kwargs)
    
    @classmethod
    def create_log(cls, event_type, event_description, user=None, request=None, 
                   result='success', metadata=None, related_object=None):
        """
        متد کمکی برای ایجاد لاگ
        """
        log_data = {
            'event_type': event_type,
            'event_description': event_description,
            'result': result,
            'metadata': metadata or {},
        }
        
        if user:
            log_data['user'] = user
            log_data['username'] = str(user.phone) if hasattr(user, 'phone') else str(user)
            log_data['user_phone'] = str(user.phone) if hasattr(user, 'phone') else None
        
        if request:
            log_data['ip_address'] = cls._get_client_ip(request)
            log_data['user_agent'] = request.META.get('HTTP_USER_AGENT', '')
            log_data['request_method'] = request.method
            log_data['request_path'] = request.path
            log_data['request_id'] = getattr(request, 'request_id', None)
        
        if related_object:
            log_data['content_type'] = ContentType.objects.get_for_model(related_object)
            log_data['object_id'] = related_object.pk
        
        log = cls.objects.create(**log_data)
        return log
    
    @staticmethod
    def _get_client_ip(request):
        """استخراج IP address از request"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip


