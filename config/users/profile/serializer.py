from rest_framework import serializers

from users.core.models import User


class GetProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['fullname','phone','image','national_code','city']


class UpdateProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['fullname','image','national_code','city']
