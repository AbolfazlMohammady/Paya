from rest_framework import serializers
from phonenumber_field.serializerfields import PhoneNumberField

class ValidationPhoneSerializer(serializers.Serializer):
    phone = PhoneNumberField(region='IR')  

    def validate_phone(self, value):
        return str(value)


class ValidationPhoneAndCodeSerializer(serializers.Serializer):
    phone = PhoneNumberField(region='IR')  
    code = serializers.CharField()

    def validate_phone(self, value):
        return str(value)