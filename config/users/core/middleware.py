"""
Middleware برای ثبت خودکار لاگ‌های امنیتی
طبق الزامات کاشف: ممیزی امنیت (لاگ)
"""
import uuid
import logging
from django.utils.deprecation import MiddlewareMixin
from django.utils import timezone
from users.core.models import AuditLog

logger = logging.getLogger(__name__)


class AuditLoggingMiddleware(MiddlewareMixin):
    """
    Middleware برای ثبت خودکار لاگ‌های امنیتی
    """
    
    # مسیرهایی که نیاز به لاگ ندارند
    EXCLUDED_PATHS = [
        '/static/',
        '/media/',
        '/favicon.ico',
        '/health/',
        '/metrics/',
    ]
    
    # متدهای HTTP که نیاز به لاگ دارند
    LOGGED_METHODS = ['GET', 'POST', 'PUT', 'PATCH', 'DELETE']
    
    def process_request(self, request):
        """افزودن request_id به request"""
        # تولید شناسه یکتا برای هر درخواست
        request.request_id = str(uuid.uuid4())
        return None
    
    def process_response(self, request, response):
        """ثبت لاگ برای درخواست‌ها"""
        # بررسی اینکه آیا نیاز به لاگ داریم
        if not self._should_log(request, response):
            return response
        
        try:
            # تعیین نوع رویداد
            event_type = self._get_event_type(request, response)
            
            # تعیین نتیجه
            result = 'success' if 200 <= response.status_code < 400 else 'failed'
            
            # ایجاد لاگ
            AuditLog.create_log(
                event_type=event_type,
                event_description=self._get_description(request, response),
                user=getattr(request, 'user', None) if hasattr(request, 'user') and request.user.is_authenticated else None,
                request=request,
                result=result,
                metadata={
                    'status_code': response.status_code,
                    'response_size': len(response.content) if hasattr(response, 'content') else 0,
                }
            )
        except Exception as e:
            # در صورت خطا در ثبت لاگ، فقط در لاگ سیستم ثبت می‌کنیم
            logger.error(f"Error creating audit log: {str(e)}", exc_info=True)
        
        return response
    
    def _should_log(self, request, response):
        """بررسی اینکه آیا نیاز به لاگ داریم"""
        # بررسی مسیر
        if any(request.path.startswith(path) for path in self.EXCLUDED_PATHS):
            return False
        
        # بررسی متد HTTP
        if request.method not in self.LOGGED_METHODS:
            return False
        
        # فقط لاگ برای API endpoints
        if not request.path.startswith('/api/'):
            return False
        
        return True
    
    def _get_event_type(self, request, response):
        """تعیین نوع رویداد بر اساس مسیر و متد"""
        path = request.path.lower()
        method = request.method
        
        # احراز هویت
        if '/login' in path or '/verify' in path:
            if response.status_code == 200:
                return 'auth_success'
            else:
                return 'auth_failed'
        
        # تراکنش‌ها
        if '/wallet/transfer' in path or '/wallet/charge' in path or '/wallet/debit' in path:
            return 'transaction_create'
        
        # کیف پول
        if '/wallet/create' in path:
            return 'wallet_create'
        if '/wallet/' in path and method in ['PUT', 'PATCH']:
            return 'wallet_update'
        
        # کاربر
        if '/user' in path or '/profile' in path:
            if method == 'POST':
                return 'user_create'
            elif method in ['PUT', 'PATCH']:
                return 'user_update'
            elif method == 'DELETE':
                return 'user_delete'
        
        # دسترسی رد شده
        if response.status_code == 403:
            return 'access_denied'
        
        # خطای سیستم
        if response.status_code >= 500:
            return 'system_error'
        
        # سایر
        return 'other'
    
    def _get_description(self, request, response):
        """تولید توضیحات برای لاگ"""
        method = request.method
        path = request.path
        
        description = f"{method} {path}"
        
        if response.status_code >= 400:
            description += f" - Status: {response.status_code}"
        
        return description


class RequestIDMiddleware(MiddlewareMixin):
    """
    Middleware برای افزودن request_id به header پاسخ
    """
    
    def process_response(self, request, response):
        """افزودن request_id به header"""
        if hasattr(request, 'request_id'):
            response['X-Request-ID'] = request.request_id
        return response


