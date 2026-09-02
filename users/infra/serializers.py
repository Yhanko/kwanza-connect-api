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
#  Denúncias e Arbitragem
# ─────────────────────────────────────────────

class ReportCreateSerializer(serializers.Serializer):
    reported_to_id = serializers.UUIDField(required=True)
    room_id = serializers.UUIDField(required=False, allow_null=True)
    reason = serializers.CharField(max_length=1000, required=True)
    
    def validate_reason(self, value):
        if len(value.strip()) < 10:
            raise serializers.ValidationError('O motivo da denúncia é demasiado curto. Por favor justifique melhor.')
        return value


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
    email            = serializers.EmailField()
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
    average_rating = serializers.SerializerMethodField()
    reviews_count = serializers.SerializerMethodField()
    recent_reviews = serializers.SerializerMethodField()

    class Meta:
        model  = User
        fields = [
            'id', 'full_name', 'username', 'email', 'phone', 'country_code', 'city', 'province', 'municipality', 'neighborhood',
            'bio', 'avatar', 'is_available', 'is_verified',
            'preferred_give_currency', 'preferred_want_currency',
            'date_joined', 'average_rating', 'reviews_count', 'recent_reviews'
        ]
        read_only_fields = fields

    def get_avatar(self, obj):
        avatar = getattr(obj, 'avatar', None)
        if not avatar:
            return None
        if isinstance(avatar, str):
            return avatar
        
        avatar_str = str(avatar)
        if avatar_str.startswith('http'):
            return avatar_str
            
        try:
            return avatar.url
        except Exception:
            return None

    def get_average_rating(self, obj):
        from django.db.models import Avg
        from transactions.models import TransactionReview
        try:
            avg = TransactionReview.objects.filter(reviewed_id=obj.id).aggregate(Avg('rating'))['rating__avg']
            return round(avg, 1) if avg else 0.0
        except Exception:
            return 0.0

    def get_reviews_count(self, obj):
        from transactions.models import TransactionReview
        try:
            return TransactionReview.objects.filter(reviewed_id=obj.id).count()
        except Exception:
            return 0

    def get_recent_reviews(self, obj):
        from transactions.models import TransactionReview
        try:
            reviews = TransactionReview.objects.filter(reviewed_id=obj.id).select_related('reviewer').order_by('-created_at')[:3]
            return [
                {
                    'id': str(r.id),
                    'rating': r.rating,
                    'comment': r.comment,
                    'reviewer_name': r.reviewer.full_name,
                    'created_at': r.created_at
                } for r in reviews
            ]
        except Exception:
            return []



class UserProfileSerializer(serializers.ModelSerializer):
    """Perfil completo — apenas para o próprio utilizador."""
    avatar = serializers.SerializerMethodField()
    two_factor_enabled = serializers.SerializerMethodField()

    class Meta:
        model  = User
        fields = [
            'id', 'email', 'username', 'full_name', 'phone', 'country_code', 'province', 'municipality', 'neighborhood',
            'city', 'address', 'occupation', 'bio', 'avatar',
            'is_active', 'is_verified', 'is_available', 'is_staff',
            'verification_status', 'two_factor_enabled', 'preferred_give_currency',
            'preferred_want_currency', 'last_seen', 'date_joined',
            'suspended_until', 'restricted_pages'
        ]
        read_only_fields = [
            'id', 'email', 'username', 'is_active', 'is_verified', 'is_staff',
            'verification_status', 'two_factor_enabled', 'last_seen', 'date_joined',
            'suspended_until', 'restricted_pages'
        ]

    def get_two_factor_enabled(self, obj) -> bool:
        security = getattr(obj, 'security', None)
        return bool(security.two_factor_enabled) if security else False


    def get_avatar(self, obj):
        avatar = getattr(obj, 'avatar', None)
        if not avatar:
            return None
        if isinstance(avatar, str):
            return avatar
            
        avatar_str = str(avatar)
        if avatar_str.startswith('http'):
            return avatar_str
            
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
            
        file_str = str(file_field)
        if file_str.startswith('http'):
            return file_str
            
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


# ─────────────────────────────────────────────
#  Autenticação de Dois Fatores (2FA / TOTP)
# ─────────────────────────────────────────────

class TwoFactorSetupResponseSerializer(serializers.Serializer):
    secret      = serializers.CharField(help_text='Chave secreta em formato Base32 para introdução manual no autenticador.')
    qr_code     = serializers.CharField(help_text='Imagem do QR Code em formato Base64 Data URI (PNG) para leitura com a câmara.')
    otpauth_url = serializers.CharField(help_text='URI padrão otpauth:// para clientes TOTP.')


class TwoFactorEnableSerializer(serializers.Serializer):
    code = serializers.CharField(
        max_length=8,
        min_length=6,
        required=True,
        help_text='Código de 6 dígitos gerado pelo Google Authenticator ou Authy.'
    )

    def validate_code(self, value):
        cleaned = value.strip().replace(' ', '').replace('-', '')
        if not cleaned.isdigit() or len(cleaned) != 6:
            raise serializers.ValidationError('O código deve conter exatamente 6 dígitos numéricos.')
        return cleaned


class TwoFactorDisableSerializer(serializers.Serializer):
    password = serializers.CharField(
        write_only=True,
        required=True,
        style={'input_type': 'password'},
        help_text='Senha atual da conta para confirmação de segurança.'
    )
    code = serializers.CharField(
        max_length=12,
        required=True,
        help_text='Código TOTP de 6 dígitos do autenticador ou código de recuperação (Backup Code).'
    )


class TwoFactorVerifyLoginSerializer(serializers.Serializer):
    pre_auth_token = serializers.CharField(
        required=True,
        help_text='Token temporário de desafio 2FA retornado no primeiro passo do login.'
    )
    code = serializers.CharField(
        max_length=12,
        required=True,
        help_text='Código TOTP de 6 dígitos do autenticador ou Código de Recuperação (Backup Code).'
    )

