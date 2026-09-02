from rest_framework.views import APIView
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema
from users.models import User
from users.infra.serializers import LoginSerializer, RegisterSerializer, UserProfileSerializer
from app.exceptions import success_response
from rest_framework.exceptions import ValidationError
from rest_framework_simplejwt.tokens import RefreshToken
from django.conf import settings
from django.contrib.auth import authenticate

ADMIN_SECRET_KEY = getattr(settings, 'ADMIN_SECRET_KEY', 'KWANZA_ADMIN_SECURE_2026')

class AdminLoginView(APIView):
    permission_classes = [] # Public route
    throttle_scope = 'admin_auth'

    @extend_schema(tags=['Admin - Auth'], request=LoginSerializer)
    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        email = serializer.validated_data['email'].lower()
        password = serializer.validated_data['password']
        
        user = authenticate(request, email=email, password=password)
        
        if not user:
            raise ValidationError('Credenciais inválidas.')
            
        if not user.is_staff:
            raise ValidationError('Acesso negado. A sua conta não tem privilégios de administrador.')
            
        refresh = RefreshToken.for_user(user)
        
        return success_response(data={
            'access': str(refresh.access_token),
            'refresh': str(refresh),
            'user': UserProfileSerializer(user).data
        })

class AdminRegisterView(APIView):
    permission_classes = [] # Public route
    throttle_scope = 'admin_auth'

    @extend_schema(tags=['Admin - Auth'])
    def post(self, request):
        # Read key dynamically from settings at runtime
        expected_secret = getattr(settings, 'ADMIN_SECRET_KEY', 'KWANZA_ADMIN_SECURE_2026')
        secret_key = request.data.get('admin_secret_key')
        
        if not secret_key or secret_key != expected_secret:
            raise ValidationError('Chave secreta de administração inválida.')
            
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        user = serializer.save()
        
        # Promote to staff and superuser
        user.is_staff = True
        user.is_superuser = True
        user.is_active = True
        user.save()
        
        refresh = RefreshToken.for_user(user)
        
        return success_response(
            message='Conta de administrador criada com sucesso.',
            data={
                'access': str(refresh.access_token),
                'refresh': str(refresh),
                'user': UserProfileSerializer(user).data
            }
        )
