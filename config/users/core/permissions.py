"""
سیستم RBAC (Role-Based Access Control)
طبق الزامات کاشف: مدیریت امنیت
"""
from rest_framework import permissions
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType


class Role:
    """
    نقش‌های سیستم
    """
    ADMIN = 'admin'
    STAFF = 'staff'
    USER = 'user'
    AUDITOR = 'auditor'  # برای دسترسی به لاگ‌ها


class IsAdminOrReadOnly(permissions.BasePermission):
    """
    فقط admin می‌تواند تغییر دهد، سایرین فقط خواندن
    """
    
    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return True
        return request.user and request.user.is_staff


class IsAuditor(permissions.BasePermission):
    """
    دسترسی برای auditor (دسترسی به لاگ‌ها)
    """
    
    def has_permission(self, request, view):
        return (
            request.user and
            request.user.is_authenticated and
            (request.user.is_staff or hasattr(request.user, 'role') and request.user.role == Role.AUDITOR)
        )


class IsOwnerOrAdmin(permissions.BasePermission):
    """
    فقط صاحب یا admin می‌تواند دسترسی داشته باشد
    """
    
    def has_object_permission(self, request, view, obj):
        # Admin همیشه دسترسی دارد
        if request.user and request.user.is_staff:
            return True
        
        # بررسی مالکیت
        if hasattr(obj, 'user'):
            return obj.user == request.user
        elif hasattr(obj, 'wallet') and hasattr(obj.wallet, 'user'):
            return obj.wallet.user == request.user
        
        return False


class CanViewAuditLogs(permissions.BasePermission):
    """
    دسترسی برای مشاهده لاگ‌های امنیتی
    فقط admin و auditor می‌توانند لاگ‌ها را ببینند
    """
    
    def has_permission(self, request, view):
        if not (request.user and request.user.is_authenticated):
            return False
        
        # Superuser همیشه دسترسی دارد
        if request.user.is_superuser:
            return True
        
        # Admin و Auditor دسترسی دارند
        if hasattr(request.user, 'role'):
            return request.user.role in ['admin', 'auditor']
        
        # Fallback به is_staff
        return request.user.is_staff


class CanModifySecuritySettings(permissions.BasePermission):
    """
    دسترسی برای تغییر تنظیمات امنیتی
    """
    
    def has_permission(self, request, view):
        return (
            request.user and
            request.user.is_authenticated and
            request.user.is_superuser
        )

