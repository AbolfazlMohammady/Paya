from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.utils.translation import gettext_lazy as _

from .models import User, OTP, AuditLog



admin.site.register(OTP)


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    fieldsets = (
        (None, {"fields": ("phone", "password")}),
        (_("Personal info"), {"fields": ("fullname", "national_code", "city",'image')}),
        (_("Role"), {"fields": ("role",)}),
        (
            _("Permissions"),
            {
                "fields": (
                    "is_active",
                    "is_staff",
                    "is_superuser",
                    "groups",
                    "user_permissions",
                ),
            },
        ),
        (_("Important dates"), {"fields": ("last_login", "date_joined")}),
    )
    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": ("phone", "password1", "password2"),
            },
        ),
    )
    list_display = ("phone", "fullname", "national_code", "city", "role", "is_staff")
    list_filter = ("is_staff", "is_superuser", "is_active", "role", "groups")
    search_fields = ("phone", "national_code", "fullname")
    ordering = ()


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    """
    Admin برای AuditLog
    فقط خواندن مجاز است (read-only)
    """
    list_display = ('event_type', 'user_phone', 'ip_address', 'result', 'created_at')
    list_filter = ('event_type', 'result', 'created_at', 'ip_address')
    search_fields = ('user_phone', 'username', 'ip_address', 'event_description', 'request_id')
    readonly_fields = (
        'event_type', 'event_description', 'result', 'user', 'username', 'user_phone',
        'ip_address', 'user_agent', 'request_method', 'request_path', 'request_id',
        'metadata', 'integrity_hash', 'content_type', 'object_id', 'created_at'
    )
    ordering = ('-created_at',)
    date_hierarchy = 'created_at'
    
    def has_add_permission(self, request):
        """غیرفعال کردن امکان افزودن از admin"""
        return False
    
    def has_change_permission(self, request, obj=None):
        """غیرفعال کردن امکان تغییر از admin"""
        return False
    
    def has_delete_permission(self, request, obj=None):
        """غیرفعال کردن امکان حذف از admin"""
        return False

