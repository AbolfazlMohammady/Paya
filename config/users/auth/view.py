from rest_framework import status, views
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken

from users.core.models import User, OTP
from users.core.utils.utils import _code



class LoginRegisterApiView(views.APIView):
    def post(self, request):
        phone = request.data.get('phone')
        code_phone = '+98'

        if not phone:
            return Response({'detail': 'Phone number cannot be empty.'}, status=status.HTTP_400_BAD_REQUEST)

        full_phone = code_phone + phone
        otp = OTP.objects.filter(phone=full_phone).first()

        if otp and otp.is_valid():
            code = otp.code
        else:
            code = _code(4)
            otp, created = OTP.objects.update_or_create(phone=full_phone, defaults={'code': code})

        return Response({'code': str(code)}, status=status.HTTP_200_OK)


class VerifyApiView(views.APIView):
    def post(self, request):
        phone = request.data.get('phone')
        code = request.data.get('code')
        code_phone = '+98'

        if not phone:
            return Response({'detail': 'Phone number cannot be empty.'}, status=status.HTTP_400_BAD_REQUEST)

        if not code:
            return Response({'detail': 'OTP code cannot be empty.'}, status=status.HTTP_400_BAD_REQUEST)

        full_phone = code_phone + phone
        otp = OTP.objects.filter(phone=full_phone, code=code).first()

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
