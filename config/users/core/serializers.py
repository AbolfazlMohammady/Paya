"""
Serializers برای AuditLog
"""
from rest_framework import serializers
from users.core.models import AuditLog


class AuditLogSerializer(serializers.ModelSerializer):
    """Serializer برای AuditLog"""
    
    user_phone_display = serializers.SerializerMethodField()
    event_type_display = serializers.CharField(source='get_event_type_display', read_only=True)
    result_display = serializers.CharField(source='get_result_display', read_only=True)
    
    class Meta:
        model = AuditLog
        fields = [
            'id',
            'event_type',
            'event_type_display',
            'event_description',
            'result',
            'result_display',
            'user',
            'username',
            'user_phone',
            'user_phone_display',
            'ip_address',
            'user_agent',
            'request_method',
            'request_path',
            'request_id',
            'metadata',
            'integrity_hash',
            'created_at',
        ]
        read_only_fields = fields
    
    def get_user_phone_display(self, obj):
        """نمایش شماره تلفن کاربر"""
        return obj.user_phone or obj.username or 'Unknown'


class AuditLogListSerializer(serializers.ModelSerializer):
    """Serializer ساده برای لیست لاگ‌ها"""
    
    event_type_display = serializers.CharField(source='get_event_type_display', read_only=True)
    result_display = serializers.CharField(source='get_result_display', read_only=True)
    
    class Meta:
        model = AuditLog
        fields = [
            'id',
            'event_type',
            'event_type_display',
            'event_description',
            'result',
            'result_display',
            'user_phone',
            'ip_address',
            'request_method',
            'request_path',
            'created_at',
        ]
        read_only_fields = fields


