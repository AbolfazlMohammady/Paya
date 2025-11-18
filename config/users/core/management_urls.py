"""
URL patterns برای بخش مدیریت (Management)
این URL ها فقط برای admin و staff قابل دسترسی هستند
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from users.core.audit_views import AuditLogViewSet

# Router برای audit logs در بخش management
router = DefaultRouter()
router.register(r'audit-logs', AuditLogViewSet, basename='management-auditlog')

urlpatterns = [
    path('', include(router.urls)),  # شامل audit-logs endpoints
]



