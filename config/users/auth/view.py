from rest_framework import status, views
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken
from django.utils import timezone
from datetime import timedelta

from users.core.models import User, OTP, AuditLog
from users.core.utils.utils import _code
from .serializer import ValidationPhoneSerializer,ValidationPhoneAndCodeSerializer



class LoginRegisterApiView(views.APIView):
    def post(self, request):
        serializer = ValidationPhoneSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        phone = serializer.validated_data['phone']
        code = _code(4)

        otp, created = OTP.objects.update_or_create(
            phone=phone,
            defaults={
                'code': code,
                'expire_at': timezone.now() + timedelta(minutes=2)
            }
        )

        # ثبت لاگ برای درخواست OTP
        AuditLog.create_log(
            event_type='auth_success' if created else 'other',
            event_description=f'درخواست کد OTP برای شماره {phone}',
            request=request,
            result='success',
            metadata={'action': 'otp_request'}
        )

        return Response({'code': str(code)}, status=status.HTTP_200_OK)


class VerifyApiView(views.APIView):
    def post(self, request):
        serializer = ValidationPhoneAndCodeSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        phone = serializer.validated_data['phone']
        code = serializer.validated_data['code']


        otp = OTP.objects.filter(phone=phone, code=code).first()

        if not otp:
            # ثبت لاگ برای احراز هویت ناموفق
            AuditLog.create_log(
                event_type='auth_failed',
                event_description=f'تلاش ناموفق احراز هویت - کد OTP نامعتبر برای شماره {phone}',
                request=request,
                result='failed',
                metadata={'reason': 'invalid_code', 'phone': phone}
            )
            return Response({'detail': 'There is no matching phone number or code.'}, status=status.HTTP_400_BAD_REQUEST)

        if not otp.is_valid():
            # ثبت لاگ برای کد منقضی شده
            AuditLog.create_log(
                event_type='auth_failed',
                event_description=f'تلاش ناموفق احراز هویت - کد OTP منقضی شده برای شماره {phone}',
                request=request,
                result='failed',
                metadata={'reason': 'expired_code', 'phone': phone}
            )
            return Response({'detail': 'The code is expired or incorrect.'}, status=status.HTTP_400_BAD_REQUEST)

        user, created = User.objects.get_or_create(phone=phone)
        refresh = RefreshToken.for_user(user)
        otp.delete()

        # ثبت لاگ برای احراز هویت موفق
        AuditLog.create_log(
            event_type='auth_success',
            event_description=f'احراز هویت موفق برای کاربر {phone}',
            user=user,
            request=request,
            result='success',
            metadata={'action': 'login', 'user_created': created}
        )

        return Response({
            'refresh': str(refresh),
            'access': str(refresh.access_token),
        }, status=status.HTTP_200_OK)
