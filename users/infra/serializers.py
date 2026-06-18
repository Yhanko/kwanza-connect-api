"""
Serializers do módulo users.
Validação de dados de entrada — nenhuma informação sensível é exposta nas saídas.
"""
from rest_framework import serializers
from ..models import User, IdentityDocument

import re
import re

def validate_angolan_name(value):
    if not re.match(r'^[A-Za-zÀ-ÖØ-öø-ÿ\s]+$', value):
        raise serializers.ValidationError('O nome deve conter apenas letras.')
    return value

def validate_angolan_phone(value):
    if not value:
        return value
    cleaned = value.replace(' ', '')
    if not re.match(r'^\+2449\d{8}$', cleaned):
        raise serializers.ValidationError('O número de telemóvel deve ser angolano, ex: +244 9XX XXX XXX.')
    return cleaned


# ─────────────────────────────────────────────
#  Registo e autenticação
# ─────────────────────────────────────────────

class RegisterSerializer(serializers.ModelSerializer):
    password         = serializers.CharField(write_only=True, min_length=8, style={'input_type': 'password'})
    password_confirm = serializers.CharField(write_only=True, style={'input_type': 'password'})

    # Campos opcionais para KYC durante o registo
    doc_type         = serializers.ChoiceField(choices=IdentityDocument.DOC_TYPE, required=False)
    doc_number       = serializers.CharField(required=False)
    front_image      = serializers.ImageField(required=False)
    back_image       = serializers.ImageField(required=False)

    class Meta:
        model  = User
        fields = [
            'email', 'full_name', 'phone', 'country_code',
            'province', 'municipality', 'neighborhood', 
            'password', 'password_confirm',
            'doc_type', 'doc_number', 'front_image', 'back_image'
        ]
        extra_kwargs = {
            'email':        {'required': True},
            'full_name':    {'required': True},
            'phone':        {'required': False},
            'province':     {'required': False},
            'municipality': {'required': False},
            'neighborhood': {'required': False},
            'country_code': {'required': False},
        }

    def validate_full_name(self, value):
        return validate_angolan_name(value)

    def validate_phone(self, value):
        return validate_angolan_phone(value)

    def validate_email(self, value):
        if User.objects.filter(email=value.lower()).exists():
            raise serializers.ValidationError('Este email já está registado.')
        return value.lower()

    def validate(self, data):
        if data['password'] != data.pop('password_confirm'):
            raise serializers.ValidationError({'password_confirm': 'As senhas não coincidem.'})
        return data

    def create(self, validated_data):
        return User.objects.create_user(**validated_data)


class LoginSerializer(serializers.Serializer):
    email    = serializers.EmailField()
    password = serializers.CharField(write_only=True, style={'input_type': 'password'})


class ChangePasswordSerializer(serializers.Serializer):
    current_password = serializers.CharField(write_only=True, style={'input_type': 'password'})
    new_password     = serializers.CharField(write_only=True, min_length=8, style={'input_type': 'password'})
    confirm_password = serializers.CharField(write_only=True, style={'input_type': 'password'})

    def validate(self, data):
        if data['new_password'] != data['confirm_password']:
            raise serializers.ValidationError({'confirm_password': 'As senhas não coincidem.'})
        return data


class ForgotPasswordSerializer(serializers.Serializer):
    email = serializers.EmailField()


class ResetPasswordSerializer(serializers.Serializer):
    token            = serializers.CharField()
    new_password     = serializers.CharField(write_only=True, min_length=8)
    confirm_password = serializers.CharField(write_only=True)

    def validate(self, data):
        if data['new_password'] != data['confirm_password']:
            raise serializers.ValidationError({'confirm_password': 'As senhas não coincidem.'})
        return data


# ─────────────────────────────────────────────
class PublicUserSerializer(serializers.ModelSerializer):
    """Perfil público — exposto a outros utilizadores."""
    avatar = serializers.SerializerMethodField()
    class Meta:
        model  = User
        fields = [
            'id', 'full_name', 'country_code', 'city', 'province', 'municipality', 'neighborhood',
            'bio', 'avatar', 'is_available', 'is_verified',
            'preferred_give_currency', 'preferred_want_currency',
            'date_joined',
        ]
        read_only_fields = fields

    def get_avatar(self, obj):
        # Suporta tanto Model (obj.avatar.url) como Entity (obj.avatar como string)
        avatar = getattr(obj, 'avatar', None)
        if not avatar:
            return None
        if isinstance(avatar, str):
            return avatar
        try:
            return avatar.url
        except Exception:
            return None



class UserProfileSerializer(serializers.ModelSerializer):
    """Perfil completo — apenas para o próprio utilizador."""
    avatar = serializers.SerializerMethodField()
    class Meta:
        model  = User
        fields = [
            'id', 'email', 'full_name', 'phone', 'country_code', 'province', 'municipality', 'neighborhood',
            'province', 'municipality', 'neighborhood',
            'city', 'address', 'occupation', 'bio', 'avatar',
            'is_active', 'is_verified', 'is_available',
            'verification_status', 'preferred_give_currency',
            'preferred_want_currency', 'last_seen', 'date_joined',
        ]
        read_only_fields = [
            'id', 'email', 'is_active', 'is_verified',
            'verification_status', 'last_seen', 'date_joined',
        ]

    def get_avatar(self, obj):
        avatar = getattr(obj, 'avatar', None)
        if not avatar:
            return None
        if isinstance(avatar, str):
            return avatar
        try:
            return avatar.url
        except Exception:
            return None



class UpdateProfileSerializer(serializers.ModelSerializer):
    def validate_full_name(self, value):
        return validate_angolan_name(value)

    def validate_phone(self, value):
        return validate_angolan_phone(value)

    class Meta:
        model  = User
        fields = [
            'full_name', 'phone', 'city', 'address', 'province', 'municipality', 'neighborhood',
            'occupation', 'bio', 'avatar',
            'preferred_give_currency', 'preferred_want_currency',
            'is_available',
        ]


# ─────────────────────────────────────────────
#  KYC — Documentos de identidade
# ─────────────────────────────────────────────

class IdentityDocumentSerializer(serializers.ModelSerializer):
    # Campos de escrita — aceitam o upload dos ficheiros
    front_image = serializers.ImageField(required=False, allow_null=True)
    back_image  = serializers.ImageField(required=False, allow_null=True)
    pdf_file    = serializers.FileField(required=False, allow_null=True)

    # Campos de leitura — devolvem a URL após upload
    front_image_url = serializers.SerializerMethodField(read_only=True)
    back_image_url  = serializers.SerializerMethodField(read_only=True)
    pdf_file_url    = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model  = IdentityDocument
        fields = [
            'id', 'doc_type', 'doc_number', 'doc_country',
            'front_image', 'back_image', 'pdf_file',
            'front_image_url', 'back_image_url', 'pdf_file_url',
            'status', 'rejection_reason', 'submitted_at',
        ]
        read_only_fields = ['id', 'status', 'rejection_reason', 'submitted_at']

    def _get_url(self, file_field):
        if not file_field:
            return None
        if isinstance(file_field, str):
            return file_field
        try:
            return file_field.url
        except Exception:
            return None

    def get_front_image_url(self, obj):
        return self._get_url(getattr(obj, 'front_image', None))

    def get_back_image_url(self, obj):
        return self._get_url(getattr(obj, 'back_image', None))

    def get_pdf_file_url(self, obj):
        return self._get_url(getattr(obj, 'pdf_file', None))

    def validate(self, data):
        has_images = data.get('front_image') and data.get('back_image')
        has_pdf    = bool(data.get('pdf_file'))
        if not has_images and not has_pdf:
            raise serializers.ValidationError(
                'Envie frente + verso do documento OU um ficheiro PDF.'
            )
        return data
