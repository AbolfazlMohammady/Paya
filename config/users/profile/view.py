from rest_framework import status, views, viewsets, permissions
from rest_framework.response import Response

from users.core.models import User
from .serializer import GetProfileSerializer,UpdateProfileSerializer

class ProfileViewSet(viewsets.ViewSet):
    permission_classes= [permissions.IsAuthenticated]

    def retrive(self, request):
        user_id = request.user.id
        try:
            query = User.objects.get(id=user_id)
        except User.DoesNotExist:
            return Response({'detail':'User Not found'} , status=status.HTTP_400_BAD_REQUEST)

        seiralizer = GetProfileSerializer(query)
        
        return Response(seiralizer.data, status=status.HTTP_200_OK)

    def update(self, request):
        user_id = request.user.id
        try:
            query = User.objects.get(id=user_id)
        except User.DoesNotExist:
            return Response({'detail':'User Not found'} , status=status.HTTP_400_BAD_REQUEST)

        serializer = UpdateProfileSerializer(query, data=request.data,  partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_200_OK)
        return Response(serializer.errors , status=status.HTTP_400_BAD_REQUEST)
