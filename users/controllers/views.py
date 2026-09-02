"""
Controllers (Views) do módulo users.
Responsabilidade única: HTTP ↔ Use Cases.
"""
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework_simplejwt.tokens import RefreshToken
from drf_spectacular.utils import extend_schema, OpenApiParameter
import uuid

from app.exceptions import success_response, created_response
from app.permissions import IsSelf
from ..infra.serializers import (
    RegisterSerializer, LoginSerializer, ChangePasswordSerializer,
    ForgotPasswordSerializer, ResetPasswordSerializer,
    UserProfileSerializer, UpdateProfileSerializer, IdentityDocumentSerializer,
    PublicUserSerializer, ReportCreateSerializer,
)
from ..services.use_cases import (
    RegisterUserUseCase, LoginUseCase, VerifyEmailUseCase,
    ChangePasswordUseCase, ForgotPasswordUseCase, ResetPasswordUseCase,
    UpdateProfileUseCase, SubmitKYCUseCase, SubmitReportUseCase,
)
from ..infra.repositories import DjangoUserRepository
from ..infra.email_service import TerminalEmailService
from audit.infra.repositories import DjangoAuditRepository
from app.services.cloudinary_storage import CloudinaryStorageService
from ..models import User
from app.audit_service import audit_log


# ─────────────────────────────────────────────
#  Autenticação
# ─────────────────────────────────────────────

class RegisterView(APIView):
    permission_classes = [AllowAny]
    throttle_scope = 'auth_register'

    @extend_schema(request=RegisterSerializer, tags=['Autenticação'])
    def post(self, request):
        repo = DjangoUserRepository()
        email_service = TerminalEmailService()
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        email = serializer.validated_data.get('email')
        
        # Log de tentativa
        audit_log(action='USER_REGISTER_ATTEMPT', resource='users', metadata={'email': email}, request=request)
        
        try:
            audit_repo = DjangoAuditRepository()
            storage_service = CloudinaryStorageService()
            result = RegisterUserUseCase(repo, audit_repo, email_service, storage_service).execute(**serializer.validated_data)
            
            # Log de Sucesso
            audit_log(
                action='USER_REGISTER_SUCCESS', 
                resource='users', 
                resource_id=result['id'], 
                metadata={'email': result['email']},
                request=request
            )
            
            return created_response(data=result, message='Conta criada com sucesso. Verifique o seu email.')
            
        except Exception as e:
            # Log de Falha
            audit_log(
                action='USER_REGISTER_FAILURE', 
                resource='users', 
                metadata={'email': email, 'error': str(e)},
                request=request
            )
            raise e


class LoginView(APIView):
    permission_classes = [AllowAny]
    throttle_scope = 'auth_login'

    @extend_schema(request=LoginSerializer, tags=['Autenticação'])
    def post(self, request):
        repo = DjangoUserRepository()
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        email = serializer.validated_data['email']
        password = serializer.validated_data['password']
        
        # Log de tentativa (Visível no terminal)
        audit_log(
            action='USER_LOGIN_ATTEMPT', 
            resource='users', 
            metadata={'email': email},
            request=request
        )
        
        try:
            audit_repo = DjangoAuditRepository()
            tokens = LoginUseCase(repo, audit_repo).execute(email=email, password=password)
            
            # Serialize the user to include profile fields
            user_model = tokens.pop('user')
            tokens['user'] = UserProfileSerializer(user_model).data

            # Log de Sucesso
            audit_log(
                action='USER_LOGIN_SUCCESS', 
                resource='users', 
                metadata={'email': email},
                request=request
            )
            
            return success_response(data=tokens, message='Login realizado com sucesso.')
            
        except Exception as e:
            # Log de Falha
            audit_log(
                action='USER_LOGIN_FAILURE', 
                resource='users', 
                metadata={'email': email, 'error': str(e)},
                request=request
            )
            raise e


class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=['Autenticação'])
    def post(self, request):
        refresh_token = request.data.get('refresh')
        if not refresh_token:
            from rest_framework.exceptions import ValidationError
            raise ValidationError({'refresh': 'O token de refresh é obrigatório.'})
        try:
            # INVALIDAÇÃO DE TOKEN JWT (BLACKLIST NO LOGOUT):
            # Adiciona o refresh_token enviado à lista negra (tabela BlacklistedToken na BD).
            # Impede que o token de refresh seja reutilizado futuramente para gerar novos tokens de acesso.
            token = RefreshToken(refresh_token)
            token.blacklist()
        except Exception:
            pass  # token já inválido — não expor detalhes
            
        # Auditoria
        audit_log(action='USER_LOGOUT', resource='users', request=request)
        
        return success_response(message='Sessão terminada com sucesso.')


class VerifyEmailView(APIView):
    permission_classes = [AllowAny]
    throttle_scope = 'auth_verify_email'

    @extend_schema(tags=['Autenticação'])
    def get(self, request, token: str):
        repo = DjangoUserRepository()
        # Log de tentativa
        audit_log(action='USER_VERIFY_EMAIL_ATTEMPT', resource='users', metadata={'token': token}, request=request)
        
        try:
            VerifyEmailUseCase(repo).execute(token=token)
            # Log de Sucesso
            audit_log(action='USER_VERIFY_EMAIL_SUCCESS', resource='users', metadata={'token': token}, request=request)
            return success_response(message='Email verificado com sucesso. Já pode fazer login.')
        except Exception as e:
            # Log de Falha
            audit_log(action='USER_VERIFY_EMAIL_FAILURE', resource='users', metadata={'token': token, 'error': str(e)}, request=request)
            raise e


class ForgotPasswordView(APIView):
    permission_classes = [AllowAny]
    throttle_scope = 'auth_password_reset'

    @extend_schema(request=ForgotPasswordSerializer, tags=['Autenticação'])
    def post(self, request):
        repo = DjangoUserRepository()
        email_service = TerminalEmailService()
        serializer = ForgotPasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        ForgotPasswordUseCase(repo, email_service).execute(email=serializer.validated_data['email'])
        
        # Auditoria
        audit_log(action='USER_FORGOT_PASSWORD', resource='users', metadata={'email': serializer.validated_data['email']}, request=request)
        # O UseCase já lança ValidationError se o email não existir neste MVP
        return success_response(
            message='E-mail confirmado. Pode inserir a sua nova senha agora.'
        )


class ResetPasswordView(APIView):
    permission_classes = [AllowAny]
    throttle_scope = 'auth_password_reset'

    @extend_schema(request=ResetPasswordSerializer, tags=['Autenticação'])
    def post(self, request):
        repo = DjangoUserRepository()
        serializer = ResetPasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data['email']
        
        # Log de tentativa
        audit_log(action='USER_RESET_PASSWORD_ATTEMPT', resource='users', metadata={'email': email}, request=request)
        
        try:
            ResetPasswordUseCase(repo).execute(
                email=email,
                new_password=serializer.validated_data['new_password'],
            )
            # Log de Sucesso
            audit_log(action='USER_RESET_PASSWORD_SUCCESS', resource='users', metadata={'email': email}, request=request)
            return success_response(message='Senha alterada com sucesso. Já pode fazer login.')
        except Exception as e:
            # Log de Falha
            audit_log(action='USER_RESET_PASSWORD_FAILURE', resource='users', metadata={'email': email, 'error': str(e)}, request=request)
            raise e


# ─────────────────────────────────────────────
#  Perfil
# ─────────────────────────────────────────────

class MeView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes     = [MultiPartParser, FormParser, JSONParser]

    @extend_schema(tags=['Perfil'])
    def get(self, request):
        serializer = UserProfileSerializer(request.user)
        return success_response(data=serializer.data)

    @extend_schema(request=UpdateProfileSerializer, tags=['Perfil'])
    def patch(self, request):
        repo = DjangoUserRepository()
        serializer = UpdateProfileSerializer(request.user, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        
        fields = list(serializer.validated_data.keys())
        # Log de tentativa
        audit_log(action='USER_UPDATE_PROFILE_ATTEMPT', resource='users', metadata={'fields': fields}, request=request)
        
        try:
            storage_service = CloudinaryStorageService()
            updated_user = UpdateProfileUseCase(repo, storage_service).execute(
                user_id=request.user.id, 
                **serializer.validated_data
            )
            # Log de Sucesso
            audit_log(action='USER_UPDATE_PROFILE_SUCCESS', resource='users', metadata={'fields': fields}, request=request)
            return success_response(
                data=UserProfileSerializer(updated_user).data,
                message='Perfil actualizado com sucesso.'
            )
        except Exception as e:
            # Log de Falha
            audit_log(action='USER_UPDATE_PROFILE_FAILURE', resource='users', metadata={'fields': fields, 'error': str(e)}, request=request)
            raise e


class ChangePasswordView(APIView):
    permission_classes = [IsAuthenticated]
    throttle_scope = 'auth_password_reset'

    @extend_schema(request=ChangePasswordSerializer, tags=['Perfil'])
    def post(self, request):
        repo = DjangoUserRepository()
        serializer = ChangePasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        ChangePasswordUseCase(repo).execute(
            user_id=request.user.id,
            current_password=serializer.validated_data['current_password'],
            new_password=serializer.validated_data['new_password'],
        )
        
        # Auditoria
        audit_log(action='USER_CHANGE_PASSWORD', resource='users', request=request)
        
        return success_response(message='Senha alterada com sucesso.')


class PublicProfileView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=['Perfil'])
    def get(self, request, user_id: str):
        repo = DjangoUserRepository()
        user_entity = repo.get_by_id(uuid.UUID(user_id))
        if not user_entity or not user_entity.is_active:
            from rest_framework.exceptions import NotFound
            raise NotFound('Utilizador não encontrado.')
        
        # O Serializer do DRF ainda espera um Model ou um objeto com os mesmos atributos.
        # Como as nossas entidades têm os mesmos nomes de atributos, deve funcionar.
        serializer = PublicUserSerializer(user_entity)
        return success_response(data=serializer.data)


# ─────────────────────────────────────────────
#  KYC
# ─────────────────────────────────────────────

class KYCSubmitView(APIView):
    permission_classes = [IsAuthenticated]
    throttle_scope = 'kyc_upload'
    parser_classes     = [MultiPartParser, FormParser]

    @extend_schema(request=IdentityDocumentSerializer, tags=['KYC'])
    def post(self, request):
        repo = DjangoUserRepository()
        storage_service = CloudinaryStorageService()
        serializer = IdentityDocumentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        SubmitKYCUseCase(repo, storage_service).execute(user_id=request.user.id, doc_data=serializer.validated_data)
        
        # Auditoria
        audit_log(
            action='USER_SUBMIT_KYC', 
            resource='users', 
            metadata={'doc_type': serializer.validated_data.get('doc_type')},
            request=request
        )
        
        return success_response(message='Documentos enviados. A análise demora até 48 horas.')


class KYCStatusView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=['KYC'])
    def get(self, request):
        data = {
            'verification_status': request.user.verification_status,
            'is_verified':         request.user.is_verified,
        }
        if hasattr(request.user, 'identity_document'):
            doc = request.user.identity_document
            from ..infra.serializers import IdentityDocumentSerializer
            data['document'] = IdentityDocumentSerializer(doc).data
        return success_response(data=data)


class UserLocationsView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=['Users'])
    def get(self, request):
        qs = User.objects.filter(is_active=True)\
                 .exclude(province__isnull=True).exclude(province='')\
                 .exclude(municipality__isnull=True).exclude(municipality='')
        
        locations = qs.values('province', 'municipality').distinct()
        
        grouped = {}
        for loc in locations:
            prov = loc['province']
            mun = loc['municipality']
            if prov not in grouped:
                grouped[prov] = set()
            grouped[prov].add(mun)
            
        result = [
            {"name": prov, "municipalities": sorted(list(muns))}
            for prov, muns in grouped.items()
        ]
        
        result.sort(key=lambda x: x["name"])
        return success_response(data=result)


# ─────────────────────────────────────────────
#  Moderação (Reports)
# ─────────────────────────────────────────────

class ReportUserView(APIView):
    permission_classes = [IsAuthenticated]
    throttle_scope = 'user_reports'

    @extend_schema(request=ReportCreateSerializer, tags=['Moderação'])
    def post(self, request):
        repo = DjangoUserRepository()
        serializer = ReportCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        SubmitReportUseCase(repo).execute(
            reporter_id=request.user.id,
            reported_to_id=serializer.validated_data['reported_to_id'],
            reason=serializer.validated_data['reason'],
            room_id=serializer.validated_data.get('room_id')
        )
        
        audit_log(
            action='USER_SUBMIT_REPORT', 
            resource='users', 
            metadata={'reported_to_id': str(serializer.validated_data['reported_to_id'])},
            request=request
        )
        
        return success_response(message='Denúncia enviada com sucesso. A equipa de moderação irá analisar o caso brevemente.')
