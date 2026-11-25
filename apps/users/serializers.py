from django.utils import timezone
from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from .models import CustomUser


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=8)
    password_confirm = serializers.CharField(write_only=True)

    class Meta:
        model = CustomUser
        fields = [
            'id', 'username', 'email', 'first_name', 'last_name',
            'university', 'preferred_language',
            'consent_given', 'password', 'password_confirm',
        ]
        # SECURITY: `role` is deliberately NOT accepted here. Self-registration always
        # creates a student; counsellors/admins are provisioned by an admin.
        extra_kwargs = {'email': {'required': True}}

    def validate_email(self, value):
        if CustomUser.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError('An account with this email already exists.')
        return value.lower()

    def validate(self, data):
        if data['password'] != data.pop('password_confirm'):
            raise serializers.ValidationError({'password_confirm': 'Passwords do not match.'})
        if not data.get('consent_given'):
            raise serializers.ValidationError({'consent_given': 'You must accept the privacy policy to register.'})
        validate_password(data['password'])
        return data

    def create(self, validated_data):
        password = validated_data.pop('password')
        user = CustomUser(**validated_data, role=CustomUser.Role.STUDENT)
        user.set_password(password)
        user.consent_given_at = timezone.now()
        user.save()
        return user


class UserProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomUser
        fields = [
            'id', 'username', 'email', 'first_name', 'last_name',
            'role', 'university', 'preferred_language', 'profile_photo',
            'is_anonymous_allowed', 'consent_given', 'created_at', 'phone_number',
        ]
        read_only_fields = ['id', 'role', 'created_at', 'consent_given']


class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    def validate(self, attrs):
        # Let people sign in with their email as well as their username.
        ident = attrs.get(self.username_field, '')
        if '@' in ident:
            match = CustomUser.objects.filter(email__iexact=ident).first()
            if match:
                attrs[self.username_field] = match.get_username()
        return super().validate(attrs)

    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        token['role'] = user.role
        token['university'] = user.university
        token['full_name'] = user.get_full_name()
        return token
