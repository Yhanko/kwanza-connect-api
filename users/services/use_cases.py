"""
Use cases do módulo users.
Orquestra repositórios e lógica de negócio operando sobre Entidades.
"""
import secrets
import hashlib
import uuid
from datetime import timedelta
from typing import Optional, Dict, Any

# Nota: As exceções ainda podem ser as do DRF para facilitar o Controller, 
# mas em uma arquitetura 100% pura, usaríamos exceções de domínio e converteríamos no controller.
from rest_framework.exceptions import AuthenticationFailed, ValidationError, NotFound

from ..domain.entities import UserEntity, UserSecurityEntity, IdentityDocumentEntity, ReportEntity
from ..domain.interfaces import IUserRepository
from notifications.services.notification_service import NotificationService
from notifications.models import NotificationType
from ..infra.email_service import IEmailService
from app.services.storage import IStorageService

import re

def validate_angolan_bi(bi_number: str) -> None:
    if not bi_number:
        return
    # Regex: 9 digits, 2 letters (províncias válidas), 3 digits
    province_codes = "BE|BG|BI|CB|CC|CN|CS|CU|CE|HA|HL|IB|LA|LN|LS|ML|MO|ME|NB|UG|ZR"
    pattern = rf'^\d{{9}}({province_codes})\d{{3}}$'
    if not re.match(pattern, bi_number, re.IGNORECASE):
        raise ValidationError({'doc_number': 'O número de BI angolano é inválido ou a província não existe. Ex: 002367037LA033'})

from audit.domain.interfaces import IAuditRepository
from audit.services.use_cases import RegisterAuditLogUseCase

class RegisterUserUseCase:
    def __init__(self, repository: IUserRepository, audit_repo: IAuditRepository, email_service: IEmailService = None, storage_service: IStorageService = None):
        self.repository = repository
        self.audit_service = RegisterAuditLogUseCase(audit_repo)
        self.email_service = email_service
        self.storage_service = storage_service

    def _generate_username(self, full_name: str, doc_number: str = None) -> str:
        import unicodedata
        import random
        
        base = 'user'
        if full_name:
            parts = full_name.split()
            if len(parts) > 1:
                base = f"{parts[0].lower()}{parts[-1].lower()}"
            else:
                base = parts[0].lower()
                
        base = unicodedata.normalize('NFKD', base).encode('ascii', 'ignore').decode('ascii')
        base = re.sub(r'[^a-z0-9]', '', base)
        if not base:
            base = 'user'
            
        suffix = ""
        if doc_number:
            nums = re.findall(r'\d+', doc_number)
            if nums:
                suffix = "".join(nums)[-3:]
                
        if not suffix:
            suffix = str(secrets.randbelow(900) + 100)
            
        username = f"{base}{suffix}"
        
        original_username = username
        counter = 1
        while self.repository.exists_by_username(username):
            username = f"{original_username}{counter}"
            counter += 1
            
        return username

    def execute(self, email: str, password: str, full_name: str, **kwargs) -> dict:
        if self.repository.exists_by_email(email):
            raise ValidationError({'email': 'Este email já está registado.'})

        # Filtragem de kwargs para evitar TypeError na UserEntity
        valid_user_fields = {
            'phone', 'country_code', 'city', 'address', 'occupation', 
            'bio', 'avatar', 'preferred_give_currency', 'preferred_want_currency',
            'province', 'municipality', 'neighborhood'
        }
        user_kwargs = {k: v for k, v in kwargs.items() if k in valid_user_fields}

        # Criação da entidade
        user_id = uuid.uuid4()
        
        # Gerar username
        doc_num = kwargs.get('doc_number')
        generated_username = self._generate_username(full_name, doc_number=doc_num)
        
        user = UserEntity(
            id=user_id,
            email=email,
            username=generated_username,
            full_name=full_name,
            password=password,
            is_active=True,
            **user_kwargs
        )
        
        # O hashing de senha deve ser tratado ou pelo repositório ou por um serviço de segurança.
        # Aqui, como estamos no Django, o ideal é que o repositório use create_user do Manager
        # ou que passemos um PasswordHasher injetado.
        
        # Salvamento inicial (o repositório cuidará de criar o registro no banco)
        user = self.repository.save(user)
        
        # Lógica de KYC (Identidade) se fornecida durante o registo
        doc_type    = kwargs.get('doc_type')
        doc_number  = kwargs.get('doc_number')
        front_image = kwargs.get('front_image')
        back_image  = kwargs.get('back_image')

        if doc_type and doc_number:
            if doc_type == 'bi':
                validate_angolan_bi(doc_number)
                doc_number = doc_number.upper()

            # Upload das imagens se fornecidas (buffer ou arquivo vindo da view)
            front_url = ""
            back_url  = ""
            if self.storage_service:
                if front_image:
                    # Garantir leitura dos bytes se for um objeto de arquivo
                    img_content = front_image.read() if hasattr(front_image, 'read') else front_image
                    front_url = self.storage_service.upload(img_content, f"kyc-{user.id}-front", folder="kyc")
                if back_image:
                    # Garantir leitura dos bytes se for um objeto de arquivo
                    img_content = back_image.read() if hasattr(back_image, 'read') else back_image
                    back_url = self.storage_service.upload(img_content, f"kyc-{user.id}-back", folder="kyc")

            doc = IdentityDocumentEntity(
                id=uuid.uuid4(),
                user_id=user.id,
                doc_type=doc_type,
                doc_number=doc_number,
                doc_country=kwargs.get('country_code', 'AO'),
                status='pending',
                front_image=front_url or front_image,
                back_image=back_url or back_image
            )
            self.repository.save_kyc_document(doc)
            user.verification_status = 'submitted'
            self.repository.save(user)
        
        # Lógica de segurança (Segurança de Email)
        security = self.repository.get_security_by_user_id(user.id)
        if not security:
             security = UserSecurityEntity(id=uuid.uuid4(), user_id=user.id)
        
        token = secrets.token_urlsafe(32)
        security.email_token = hashlib.sha256(token.encode()).hexdigest()
        self.repository.update_security(security)

        if self.email_service:
            self.email_service.send_email(
                subject="Ative a sua conta — KwanzaConnect",
                body=f"Olá {user.full_name},\n\nUtilize este link para ativar a sua conta: http://localhost:8000/api/auth/verify-email/{token}/",
                recipient=user.email
            )

        # ── Auditoria ──────────────────────────────────────────────────
        self.audit_service.execute(
            action='user_registered',
            resource='user',
            user_id=user.id,
            resource_id=str(user.id),
            metadata={'email': email, 'kyc': 'submitted' if doc_type else 'pending'}
        )

        # Notificar admins
        NotificationService.notify_admins(
            notification_type=NotificationType.NEW_USER_REGISTRATION,
            actor=user
        )

        return {
            'id': str(user.id),
            'email': user.email,
            'message': 'Conta criada. Verifique o seu email para activar a conta.',
        }

class LoginUseCase:
    def __init__(self, repository: IUserRepository, audit_repo: IAuditRepository, auth_service=None):
        self.repository = repository
        self.audit_service = RegisterAuditLogUseCase(audit_repo)
        self.auth_service = auth_service # TODO: Interface para autenticação

    def execute(self, email: str, password: str) -> dict:
        user = self.repository.get_by_email(email)
        if not user:
            raise AuthenticationFailed('Credenciais inválidas.')

        security = self.repository.get_security_by_user_id(user.id)
        if security and security.is_locked():
            raise AuthenticationFailed(
                'Conta bloqueada por excesso de tentativas. Tente novamente em 15 minutos.',
                code='account_locked_bruteforce'
            )

        if not user.is_active:
            if security and not security.email_verified:
                raise AuthenticationFailed(
                    'Conta não activada. Verifique o seu email.',
                    code='account_inactive'
                )
            else:
                raise AuthenticationFailed(
                    'A conta encontra-se bloqueada, contacte o admin.',
                    code='account_blocked'
                )

        # AUTENTICAÇÃO DE SENHA E VERIFICAÇÃO EM TEMPO CONSTANTE:
        # O authenticate() do Django lê o hash Argon2 armazenado, extrai o salt do utilizador,
        # gera o hash da senha informada e compara em tempo constante para evitar timing attacks.
        from django.contrib.auth import authenticate
        django_user = authenticate(username=email, password=password)
        
        if not django_user:
            if security:
                # PROTEÇÃO CONTRA ATAQUES DE FORÇA BRUTA (LOCKOUT DE CONTA):
                # Regista tentativas consecutivas de login falhadas e bloqueia a conta por 15 minutos após 5 falhas.
                security.failed_login_attempts += 1
                if security.failed_login_attempts >= 5:
                    from datetime import datetime, timedelta
                    security.locked_until = datetime.now() + timedelta(minutes=15)
                self.repository.update_security(security)
                
            raise AuthenticationFailed('Credenciais inválidas.')

        # Reset falhas ao sucesso
        if security:
            security.failed_login_attempts = 0
            security.locked_until = None
            self.repository.update_security(security)

        # Atualiza atividade
        user.update_last_seen()
        self.repository.save(user)

        # Se o utilizador tiver 2FA activo, emite token temporário de 5 minutos assinado
        sec = self.repository.get_security_by_user_id(user.id)
        if sec and sec.two_factor_enabled:
            import jwt
            from django.conf import settings
            from datetime import timedelta
            from django.utils import timezone
            
            pre_auth_payload = {
                'user_id': str(user.id),
                'action': '2fa_pre_auth',
                'exp': timezone.now() + timedelta(minutes=5),
                'iat': timezone.now()
            }
            pre_auth_token = jwt.encode(pre_auth_payload, settings.SECRET_KEY, algorithm='HS256')
            return {
                'two_factor_required': True,
                'pre_auth_token': pre_auth_token,
                'message': 'Autenticação de 2 fatores necessária. Introduza o código do seu autenticador.'
            }


        # ── Auditoria ──────────────────────────────────────────────────
        if hasattr(self, 'audit_service') and self.audit_service:
            self.audit_service.execute(
                action='user_logged_in',
                resource='auth',
                user_id=user.id,
                metadata={'method': 'jwt'}
            )

        # EMISSÃO DE TOKENS JWT NO LOGIN BEM-SUCEDIDO:
        # Utiliza o SimpleJWT para criar um par de tokens para o utilizador autenticado:
        # 1. access_token: Usado no cabeçalho 'Authorization: Bearer <token>' em todas as requisições autenticadas (expira em 60m).
        # 2. refresh_token: Usado para obter um novo par de tokens quando o access token expirar (expira em 7d).
        from rest_framework_simplejwt.tokens import RefreshToken
        refresh = RefreshToken.for_user(django_user)
        return {
            'access': str(refresh.access_token),
            'refresh': str(refresh),
            'user': django_user,
            'two_factor_required': False
        }


class VerifyEmailUseCase:
    def __init__(self, repository: IUserRepository):
        self.repository = repository

    def execute(self, token: str) -> None:
        hashed = hashlib.sha256(token.encode()).hexdigest()
        security = self.repository.get_security_by_email_token(hashed)
        
        if not security:
            raise ValidationError('Token de verificação inválido ou já utilizado.')

        if security.email_verified:
            raise ValidationError('O email já foi verificado.')

        from django.utils import timezone
        security.email_verified = True
        security.email_token = ''
        security.email_verified_at = timezone.now()
        self.repository.update_security(security)

        user = self.repository.get_by_id(security.user_id)
        if user:
            user.is_active = True
            self.repository.save(user)

class ChangePasswordUseCase:
    def __init__(self, repository: IUserRepository):
        self.repository = repository

    def execute(self, user_id: uuid.UUID, current_password: str, new_password: str) -> None:
        # Precisamos do model do Django para check_password / set_password
        # Numa arquitetura pura, o PasswordHasher seria injetado.
        from ..models import User
        django_user = User.objects.get(id=user_id)
        
        # VERIFICAÇÃO E RE-HASHING DE SENHA:
        # check_password() valida a senha actual contra o hash Argon2 armazenado utilizando avaliação em tempo constante.
        if not django_user.check_password(current_password):
            raise ValidationError({'current_password': 'Senha actual incorrecta.'})
        if current_password == new_password:
            raise ValidationError({'new_password': 'A nova senha deve ser diferente da actual.'})
            
        # set_password() criptografa a nova senha utilizando Argon2id com um novo salt aleatório.
        django_user.set_password(new_password)
        django_user.save(update_fields=['password'])

        security = self.repository.get_security_by_user_id(user_id)
        if security:
            from django.utils import timezone
            security.password_changed_at = timezone.now()
            self.repository.update_security(security)

class UpdateProfileUseCase:
    def __init__(self, repository: IUserRepository, storage_service: IStorageService = None):
        self.repository = repository
        self.storage_service = storage_service

    def execute(self, user_id: uuid.UUID, **fields) -> UserEntity:
        user = self.repository.get_by_id(user_id)
        if not user:
            raise NotFound('Utilizador não encontrado.')
            
        allowed = {
            'full_name', 'phone', 'city', 'address', 'province', 'municipality', 'neighborhood', 'occupation',
            'bio', 'avatar', 'preferred_give_currency',
            'preferred_want_currency', 'is_available',
        }
        update = {k: v for k, v in fields.items() if k in allowed}
        
        # Upload de avatar se fornecido
        if 'avatar' in update and update['avatar'] and self.storage_service:
            # Se for string (URL), ignoramos o upload. Se for bytes/file, fazemos upload.
            if not isinstance(update['avatar'], str):
                avatar_url = self.storage_service.upload(
                    update['avatar'].read() if hasattr(update['avatar'], 'read') else update['avatar'],
                    f"avatar-{user.id}",
                    folder="avatars"
                )
                update['avatar'] = avatar_url

        for attr, val in update.items():
            setattr(user, attr, val)
            
        saved_user = self.repository.save(user)
        
        # Notificar admins
        NotificationService.notify_admins(
            notification_type=NotificationType.USER_PROFILE_UPDATED,
            actor=saved_user
        )
        
        return saved_user

class SubmitKYCUseCase:
    def __init__(self, repository: IUserRepository, storage_service: IStorageService = None):
        self.repository = repository
        self.storage_service = storage_service

    def execute(self, user_id: uuid.UUID, doc_data: dict) -> None:
        user = self.repository.get_by_id(user_id)
        if not user:
            raise NotFound('Utilizador não encontrado.')
            
        if user.is_kyc_complete():
            raise ValidationError({'detail': 'Os documentos já foram aprovados e não podem ser reenviados.'})

        # Upload de fotos se presentes em doc_data
        if self.storage_service:
            if 'front_image' in doc_data and doc_data['front_image'] and not isinstance(doc_data['front_image'], str):
                 doc_data['front_image'] = self.storage_service.upload(
                     doc_data['front_image'].read() if hasattr(doc_data['front_image'], 'read') else doc_data['front_image'],
                     f"kyc-{user_id}-front",
                     folder="kyc"
                 )
            if 'back_image' in doc_data and doc_data['back_image'] and not isinstance(doc_data['back_image'], str):
                 doc_data['back_image'] = self.storage_service.upload(
                     doc_data['back_image'].read() if hasattr(doc_data['back_image'], 'read') else doc_data['back_image'],
                     f"kyc-{user_id}-back",
                     folder="kyc"
                 )

        # Validação do BI angolano
        doc_type = doc_data.get('doc_type', '')
        doc_number = doc_data.get('doc_number', '')
        if doc_type == 'bi':
            validate_angolan_bi(doc_number)
            doc_data['doc_number'] = doc_number.upper()

        # Criação/Atualização da entidade de documento
        existing_doc = self.repository.get_kyc_document_by_user_id(user_id)
        if existing_doc:
            for k, v in doc_data.items():
                setattr(existing_doc, k, v)
            self.repository.save_kyc_document(existing_doc)
        else:
            new_doc = IdentityDocumentEntity(
                id=uuid.uuid4(),
                user_id=user_id,
                doc_type=doc_data.get('doc_type', ''),
                doc_number=doc_data.get('doc_number', ''),
                doc_country=doc_data.get('doc_country', 'AO'),
                status='pending',
                front_image=doc_data.get('front_image'),
                back_image=doc_data.get('back_image'),
                pdf_file=doc_data.get('pdf_file'),
            )
            self.repository.save_kyc_document(new_doc)

        user.verification_status = 'submitted'
        self.repository.save(user)
        
        # Notificar admins
        NotificationService.notify_admins(
            notification_type=NotificationType.KYC_SUBMITTED,
            actor=user
        )

class ForgotPasswordUseCase:
    def __init__(self, repository: IUserRepository, email_service: IEmailService = None):
        self.repository = repository
        # Email service ignored for MVP bypass

    def execute(self, email: str) -> None:
        user = self.repository.get_by_email(email)
        if not user:
            raise ValidationError({'email': 'Este e-mail não está registado na plataforma.'})
        # For this MVP, we just confirm the email exists so the frontend can proceed.

class ResetPasswordUseCase:
    def __init__(self, repository: IUserRepository):
        self.repository = repository

    def execute(self, email: str, new_password: str) -> None:
        user = self.repository.get_by_email(email)
        if not user:
             raise ValidationError('Conta não encontrada.')

        # Atualizar senha no model Django
        from ..models import User
        django_user = User.objects.get(id=user.id)
        django_user.set_password(new_password)
        django_user.save(update_fields=['password'])

        from django.utils import timezone
        security = self.repository.get_security_by_user_id(user.id)
        if security:
            security.password_changed_at = timezone.now()
            self.repository.update_security(security)


class SubmitReportUseCase:
    """Submete uma queixa/denúncia sobre outro utilizador no contexto de uma sala."""
    def __init__(self, user_repo: IUserRepository):
        self.user_repo = user_repo
        
    def execute(self, reporter_id: uuid.UUID, reported_to_id: uuid.UUID, reason: str, room_id: Optional[uuid.UUID] = None) -> Any:
        if reporter_id == reported_to_id:
            raise ValidationError("Não podes denunciar-te a ti próprio.")
            
        reported_user = self.user_repo.get_by_id(reported_to_id)
        if not reported_user:
            raise NotFound("O utilizador que tentas denunciar não existe.")
            
        report = ReportEntity(
            id=uuid.uuid4(),
            reporter_id=reporter_id,
            reported_to_id=reported_to_id,
            room_id=room_id,
            reason=reason,
            status='pending',
            admin_notes=''
        )
        saved_report = self.user_repo.save_report(report)
        
        # Notificar os admins
        NotificationService.notify_admins(
            notification_type='USER_REPORTED',
            payload={
                'reason_preview': reason[:50] + "..." if len(reason) > 50 else reason,
                'reporter_name': self.user_repo.get_by_id(reporter_id).full_name,
                'reported_name': reported_user.full_name
            }
        )
        
        return saved_report


# ─────────────────────────────────────────────
#  Casos de Uso de Autenticação de 2 Fatores (2FA)
# ─────────────────────────────────────────────

class Setup2FAUseCase:
    """
    Inicia a configuração do 2FA para o utilizador autenticado.
    Gera chave secreta Base32, URI otpauth e imagem QR Code em Base64 Data URI.
    """
    def __init__(self, repository: IUserRepository):
        self.repository = repository

    def execute(self, user_id: uuid.UUID) -> dict:
        import pyotp
        import qrcode
        import io
        import base64

        user = self.repository.get_by_id(user_id)
        if not user:
            raise NotFound('Utilizador não encontrado.')

        security = self.repository.get_security_by_user_id(user_id)
        if not security:
            raise NotFound('Registo de segurança não encontrado.')

        # Gera segredo base32 aleatório (160 bits de entropia)
        secret = pyotp.random_base32()

        # Gera o URI padrão TOTP
        totp = pyotp.TOTP(secret)
        otpauth_url = totp.provisioning_uri(
            name=user.email,
            issuer_name='KwanzaConnect'
        )

        # Gera a imagem do QR Code em Base64 PNG
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_M,
            box_size=8,
            border=2
        )
        qr.add_data(otpauth_url)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        
        buffer = io.BytesIO()
        img.save(buffer, format="PNG")
        qr_base64 = f"data:image/png;base64,{base64.b64encode(buffer.getvalue()).decode('utf-8')}"

        # Guarda a chave secreta temporariamente (two_factor_enabled permanece False até confirmação)
        security.two_factor_secret = secret
        self.repository.update_security(security)

        return {
            'secret': secret,
            'qr_code': qr_base64,
            'otpauth_url': otpauth_url
        }


class Enable2FAUseCase:
    """
    Confirma e ativa o 2FA mediante validação do primeiro código TOTP digitado.
    Gera e devolve 8 códigos de recuperação (Backup Codes) criptografados com SHA-256.
    """
    def __init__(self, repository: IUserRepository, audit_repo: IAuditRepository):
        self.repository = repository
        self.audit_service = RegisterAuditLogUseCase(audit_repo)

    def execute(self, user_id: uuid.UUID, code: str) -> dict:
        import pyotp

        security = self.repository.get_security_by_user_id(user_id)
        if not security or not security.two_factor_secret:
            raise ValidationError('Configuração de 2FA não iniciada. Execute o setup primeiro.')

        # Validação do código de 6 dígitos com janela de tolerância de tempo (±30s)
        totp = pyotp.TOTP(security.two_factor_secret)
        if not totp.verify(code.strip(), valid_window=1):
            raise ValidationError('Código de verificação de 2 fatores inválido ou expirado.')

        # Ativa o 2FA, gera códigos de recuperação e persiste no repositório
        security.two_factor_enabled = True
        backup_codes = security.generate_backup_codes(count=8)
        self.repository.update_security(security)

        # Regista auditoria
        self.audit_service.execute(
            action='2FA_ENABLED',
            resource='users',
            user_id=user_id,
            resource_id=str(user_id),
            status='SUCCESS',
            severity='INFO'
        )

        return {
            'message': 'Autenticação de 2 fatores ativada com sucesso.',
            'two_factor_enabled': True,
            'backup_codes': backup_codes
        }


class Disable2FAUseCase:
    """
    Desativa o 2FA exigindo validação prévia de senha e código de autenticação (ou backup code).
    """
    def __init__(self, repository: IUserRepository, audit_repo: IAuditRepository):
        self.repository = repository
        self.audit_service = RegisterAuditLogUseCase(audit_repo)

    def execute(self, user_id: uuid.UUID, password: str, code: str) -> dict:
        import pyotp
        from django.contrib.auth import authenticate

        user = self.repository.get_by_id(user_id)
        if not user:
            raise NotFound('Utilizador não encontrado.')

        security = self.repository.get_security_by_user_id(user_id)
        if not security or not security.two_factor_enabled:
            raise ValidationError('A autenticação de 2 fatores não está ativa nesta conta.')

        # Confirmação da senha atual
        django_user = authenticate(username=user.email, password=password)
        if not django_user:
            raise ValidationError('Senha incorreta.')

        # Validação do código TOTP ou código de recuperação
        totp = pyotp.TOTP(security.two_factor_secret)
        is_totp_valid = totp.verify(code.strip(), valid_window=1)
        is_backup_valid = False
        if not is_totp_valid:
            is_backup_valid = security.verify_and_consume_backup_code(code)

        if not is_totp_valid and not is_backup_valid:
            raise ValidationError('Código de 2 fatores ou código de recuperação inválido.')

        # Desativa 2FA
        security.two_factor_enabled = False
        security.two_factor_secret = ''
        security.two_factor_backup_codes = []
        self.repository.update_security(security)

        # Regista auditoria de segurança
        self.audit_service.execute(
            action='2FA_DISABLED',
            resource='users',
            user_id=user_id,
            resource_id=str(user_id),
            status='SUCCESS',
            severity='WARNING'
        )

        return {
            'message': 'Autenticação de 2 fatores desativada com sucesso.',
            'two_factor_enabled': False
        }


class Verify2FALoginUseCase:
    """
    Conclui o login de 2 fatores validando o pre_auth_token e o código TOTP ou Backup Code.
    Emite os tokens JWT finais (access e refresh).
    """
    def __init__(self, repository: IUserRepository, audit_repo: IAuditRepository):
        self.repository = repository
        self.audit_service = RegisterAuditLogUseCase(audit_repo)

    def execute(self, pre_auth_token: str, code: str) -> dict:
        import jwt
        import pyotp
        from django.conf import settings
        from rest_framework.exceptions import AuthenticationFailed
        from rest_framework_simplejwt.tokens import RefreshToken
        from users.models import User as DjangoUser

        try:
            payload = jwt.decode(pre_auth_token, settings.SECRET_KEY, algorithms=['HS256'])
            if payload.get('action') != '2fa_pre_auth':
                raise AuthenticationFailed('Token de autenticação temporário inválido.')
            user_id = payload.get('user_id')
        except jwt.ExpiredSignatureError:
            raise AuthenticationFailed('A sessão de autenticação de 2 fatores expirou. Faça login novamente.')
        except Exception:
            raise AuthenticationFailed('Token de autenticação temporário inválido.')

        try:
            django_user = DjangoUser.objects.get(id=user_id)
        except DjangoUser.DoesNotExist:
            raise AuthenticationFailed('Utilizador não encontrado.')

        security = self.repository.get_security_by_user_id(uuid.UUID(str(user_id)))
        if not security or not security.two_factor_enabled:
            raise AuthenticationFailed('2FA não configurado nesta conta.')

        # Valida código TOTP ou código de recuperação
        totp = pyotp.TOTP(security.two_factor_secret)
        is_totp_valid = totp.verify(code.strip(), valid_window=1)
        is_backup_valid = False
        if not is_totp_valid:
            is_backup_valid = security.verify_and_consume_backup_code(code)
            if is_backup_valid:
                self.repository.update_security(security)

        if not is_totp_valid and not is_backup_valid:
            self.audit_service.execute(
                action='2FA_LOGIN_FAILURE',
                resource='auth',
                user_id=django_user.id,
                resource_id=str(django_user.id),
                status='FAILURE',
                severity='WARNING',
                metadata={'email': django_user.email}
            )
            raise AuthenticationFailed('Código de autenticação de 2 fatores inválido.')

        # Sucesso no 2FA
        django_user.update_last_seen()
        self.audit_service.execute(
            action='2FA_LOGIN_SUCCESS',
            resource='auth',
            user_id=django_user.id,
            resource_id=str(django_user.id),
            status='SUCCESS',
            severity='INFO',
            metadata={'method': 'backup_code' if is_backup_valid else 'totp', 'email': django_user.email}
        )

        refresh = RefreshToken.for_user(django_user)
        return {
            'access': str(refresh.access_token),
            'refresh': str(refresh),
            'user': django_user,
            'two_factor_required': False
        }


