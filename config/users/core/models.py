from django.db import models
from django.contrib.auth.models import AbstractUser, UserManager
from django.core.validators import MinLengthValidator, MaxLengthValidator
from django.utils.translation import gettext_lazy as _
from phonenumber_field.modelfields import PhoneNumberField
from django.utils import timezone
from datetime import timedelta

from users.core.utils.utils import path_image_or_file

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
    username =None
    first_name =None
    last_name = None
    email = None
    fullname = models.CharField(_("نام, نام خانوادگی"),max_length=255,blank=True, null=True)
    phone = PhoneNumberField(_("شماره تلفن "),unique=True)
    image = models.ImageField(_("عکس پروفایل"),upload_to=path_image_or_file, blank=True, null=True)
    national_code = models.CharField(_("کدملی"),validators=[(MaxLengthValidator(10))],blank=True, null=True, max_length=10)
    city = models.CharField(_("شهر"),max_length=255,blank=True, null=True)

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
        super().save(*args, **kwargs)

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

