from rest_framework import status, views
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken

from users.core.models import User, OTP
from users.core.utils.utils import _code
from .serializer import ValidationPhoneSerializer,ValidationPhoneAndCodeSerializer



class LoginRegisterApiView(views.APIView):
    def post(self, request):
        serializer = ValidationPhoneSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        phone = serializer.validated_data['phone']

        otp = OTP.objects.filter(phone=phone).first()

        if otp and otp.is_valid():
            code = otp.code
        else:
            code = _code(4)
            otp, created = OTP.objects.update_or_create(phone=phone, defaults={'code': code})

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
            return Response({'detail': 'There is no matching phone number or code.'}, status=status.HTTP_400_BAD_REQUEST)

        if not otp.is_valid():
            return Response({'detail': 'The code is expired or incorrect.'}, status=status.HTTP_400_BAD_REQUEST)

        user, created = User.objects.get_or_create(phone=phone)
        refresh = RefreshToken.for_user(user)
        otp.delete()

        return Response({
            'refresh': str(refresh),
            'access': str(refresh.access_token),
        }, status=status.HTTP_200_OK)
