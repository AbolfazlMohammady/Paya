"""
Views برای مشاهده و مدیریت لاگ‌های امنیتی
طبق الزامات کاشف: ممیزی امنیت (لاگ)
"""
from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.utils import timezone
from django.db.models import Q
from django.core.paginator import Paginator
from datetime import timedelta

from users.core.models import AuditLog
from users.core.serializers import AuditLogSerializer, AuditLogListSerializer
from users.core.permissions import CanViewAuditLogs


class AuditLogViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet برای مشاهده لاگ‌های امنیتی
    فقط خواندن مجاز است (طبق الزامات کاشف)
    """
    queryset = AuditLog.objects.all()
    permission_classes = [IsAuthenticated, CanViewAuditLogs]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['event_type', 'event_description', 'user_phone', 'username', 'ip_address', 'request_path']
    ordering_fields = ['created_at', 'event_type', 'result']
    ordering = ['-created_at']
    
    def get_serializer_class(self):
        if self.action == 'list':
            return AuditLogListSerializer
        return AuditLogSerializer
    
    def get_queryset(self):
        """فیلتر کردن queryset بر اساس پارامترهای درخواست"""
        queryset = AuditLog.objects.all()
        
        # فیلتر بر اساس نوع رویداد
        event_type = self.request.query_params.get('event_type')
        if event_type:
            queryset = queryset.filter(event_type=event_type)
        
        # فیلتر بر اساس نتیجه
        result = self.request.query_params.get('result')
        if result:
            queryset = queryset.filter(result=result)
        
        # فیلتر بر اساس کاربر
        user_id = self.request.query_params.get('user_id')
        if user_id:
            queryset = queryset.filter(user_id=user_id)
        
        # فیلتر بر اساس شماره تلفن
        user_phone = self.request.query_params.get('user_phone')
        if user_phone:
            queryset = queryset.filter(user_phone__icontains=user_phone)
        
        # فیلتر بر اساس IP
        ip_address = self.request.query_params.get('ip_address')
        if ip_address:
            queryset = queryset.filter(ip_address=ip_address)
        
        # فیلتر بر اساس تاریخ شروع
        start_date = self.request.query_params.get('start_date')
        if start_date:
            try:
                start_datetime = timezone.datetime.fromisoformat(start_date.replace('Z', '+00:00'))
                queryset = queryset.filter(created_at__gte=start_datetime)
            except ValueError:
                pass
        
        # فیلتر بر اساس تاریخ پایان
        end_date = self.request.query_params.get('end_date')
        if end_date:
            try:
                end_datetime = timezone.datetime.fromisoformat(end_date.replace('Z', '+00:00'))
                queryset = queryset.filter(created_at__lte=end_datetime)
            except ValueError:
                pass
        
        # فیلتر بر اساس request_id
        request_id = self.request.query_params.get('request_id')
        if request_id:
            queryset = queryset.filter(request_id=request_id)
        
        return queryset
    
    def list(self, request, *args, **kwargs):
        """لیست لاگ‌ها با pagination"""
        queryset = self.filter_queryset(self.get_queryset())
        
        # Pagination
        page = int(request.query_params.get('page', 1))
        page_size = int(request.query_params.get('page_size', 50))
        page_size = min(page_size, 100)  # حداکثر 100 رکورد در هر صفحه
        
        paginator = Paginator(queryset, page_size)
        page_obj = paginator.get_page(page)
        
        serializer = self.get_serializer(page_obj.object_list, many=True)
        
        return Response({
            'count': paginator.count,
            'next': page_obj.next_page_number() if page_obj.has_next() else None,
            'previous': page_obj.previous_page_number() if page_obj.has_previous() else None,
            'results': serializer.data
        })
    
    @action(detail=False, methods=['get'])
    def statistics(self, request):
        """آمار لاگ‌ها"""
        queryset = self.get_queryset()
        
        # فیلتر بر اساس بازه زمانی (پیش‌فرض: 30 روز گذشته)
        days = int(request.query_params.get('days', 30))
        start_date = timezone.now() - timedelta(days=days)
        queryset = queryset.filter(created_at__gte=start_date)
        
        # آمار بر اساس نوع رویداد
        event_type_stats = {}
        for event_type, _ in AuditLog.EVENT_TYPE_CHOICES:
            count = queryset.filter(event_type=event_type).count()
            if count > 0:
                event_type_stats[event_type] = count
        
        # آمار بر اساس نتیجه
        result_stats = {}
        for result, _ in AuditLog.RESULT_CHOICES:
            count = queryset.filter(result=result).count()
            if count > 0:
                result_stats[result] = count
        
        # تعداد کل
        total_count = queryset.count()
        
        # تعداد رویدادهای ناموفق
        failed_count = queryset.filter(result='failed').count()
        
        # تعداد رویدادهای امنیتی
        security_events = queryset.filter(
            event_type__in=['auth_failed', 'access_denied', 'security_event', 'system_error']
        ).count()
        
        return Response({
            'total_count': total_count,
            'failed_count': failed_count,
            'security_events': security_events,
            'event_type_stats': event_type_stats,
            'result_stats': result_stats,
            'period_days': days,
        })
    
    @action(detail=False, methods=['get'])
    def recent_failures(self, request):
        """لاگ‌های ناموفق اخیر"""
        queryset = self.get_queryset().filter(result='failed')
        
        # محدود به 100 رکورد آخر
        queryset = queryset[:100]
        
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def security_events(self, request):
        """رویدادهای امنیتی"""
        queryset = self.get_queryset().filter(
            event_type__in=['auth_failed', 'access_denied', 'security_event', 'system_error']
        )
        
        # Pagination
        page = int(request.query_params.get('page', 1))
        page_size = int(request.query_params.get('page_size', 50))
        
        paginator = Paginator(queryset, page_size)
        page_obj = paginator.get_page(page)
        
        serializer = self.get_serializer(page_obj.object_list, many=True)
        
        return Response({
            'count': paginator.count,
            'next': page_obj.next_page_number() if page_obj.has_next() else None,
            'previous': page_obj.previous_page_number() if page_obj.has_previous() else None,
            'results': serializer.data
        })


