from typing import Optional, List
import uuid
from django.db import transaction
from django.utils import timezone
from ..models import User as DjangoUser, UserSecurity as DjangoUserSecurity, IdentityDocument as DjangoIdentityDocument
from ..domain.entities import UserEntity, UserSecurityEntity, IdentityDocumentEntity, ReportEntity
from ..domain.interfaces import IUserRepository
from app.services.cloudinary_service import CloudinaryStorageService

class DjangoUserRepository(IUserRepository):
    def __init__(self, storage_service: CloudinaryStorageService = None):
        self.storage_service = storage_service or CloudinaryStorageService()
    
    def _to_entity(self, django_user: DjangoUser) -> UserEntity:

        security = None
        if hasattr(django_user, 'security'):
            security = self._security_to_entity(django_user.security)
            
        identity_document = None
        if hasattr(django_user, 'identity_document'):
            identity_document = self._identity_to_entity(django_user.identity_document)
            
        return UserEntity(
            id=django_user.id,
            email=django_user.email,
            username=django_user.username,
            full_name=django_user.full_name,
            is_active=django_user.is_active,
            is_staff=django_user.is_staff,
            is_verified=django_user.is_verified,
            is_available=django_user.is_available,
            verification_status=django_user.verification_status,
            phone=django_user.phone,
            country_code=django_user.country_code,
            city=django_user.city,
            address=django_user.address,
            province=django_user.province,
            municipality=django_user.municipality,
            neighborhood=django_user.neighborhood,
            occupation=django_user.occupation,
            bio=django_user.bio,
            avatar=self._get_absolute_url(django_user.avatar),
            last_seen=django_user.last_seen,

            date_joined=django_user.date_joined,
            preferred_give_currency=django_user.preferred_give_currency,
            preferred_want_currency=django_user.preferred_want_currency,
            security=security,
            identity_document=identity_document
        )

    def _security_to_entity(self, django_security: DjangoUserSecurity) -> UserSecurityEntity:
        return UserSecurityEntity(
            id=django_security.id,
            user_id=django_security.user_id,
            email_token=django_security.email_token,
            email_verified=django_security.email_verified,
            email_verified_at=django_security.email_verified_at,
            phone_otp=django_security.phone_otp,
            phone_otp_expires_at=django_security.phone_otp_expires_at,
            phone_verified=django_security.phone_verified,
            failed_login_attempts=django_security.failed_login_attempts,
            locked_until=django_security.locked_until,
            two_factor_enabled=django_security.two_factor_enabled,
            two_factor_secret=django_security.two_factor_secret,
            two_factor_backup_codes=django_security.two_factor_backup_codes or [],
            password_changed_at=django_security.password_changed_at,
            password_reset_token=django_security.password_reset_token,
            password_reset_expires=django_security.password_reset_expires
        )


    def _identity_to_entity(self, django_identity: DjangoIdentityDocument) -> IdentityDocumentEntity:
        return IdentityDocumentEntity(
            id=django_identity.id,
            user_id=django_identity.user_id,
            doc_type=django_identity.doc_type,
            doc_number=django_identity.doc_number,
            doc_country=django_identity.doc_country,
            status=django_identity.status,
            front_image=self._get_absolute_url(django_identity.front_image),
            back_image=self._get_absolute_url(django_identity.back_image),
            pdf_file=self._get_absolute_url(django_identity.pdf_file),
            rejection_reason=django_identity.rejection_reason,

            submitted_at=django_identity.submitted_at,
            reviewed_at=django_identity.reviewed_at,
            reviewed_by_id=django_identity.reviewed_by_id
        )

    def get_by_id(self, user_id: uuid.UUID) -> Optional[UserEntity]:
        try:
            django_user = DjangoUser.objects.get(id=user_id)
            return self._to_entity(django_user)
        except DjangoUser.DoesNotExist:
            return None

    # PROTEÇÃO CONTRA SQL INJECTION:
    # O Django ORM utiliza consultas SQL parametrizadas (Prepared Statements) por padrão.
    # As entradas do utilizador passadas para filter() ou objetos Q() são sanitizadas e escapadas com segurança pelo driver da base de dados.
    def search_users(self, filters: dict) -> List[UserEntity]:
        """Pesquisa genérica de utilizadores com base em filtros."""
        qs = DjangoUser.objects.all()
        
        if filters.get('search'):
            from django.db.models import Q
            s = filters['search']
            qs = qs.filter(Q(full_name__icontains=s) | Q(email__icontains=s))
            
        return [self._to_entity(u) for u in qs]

    def get_by_email(self, email: str) -> Optional[UserEntity]:
        try:
            django_user = DjangoUser.objects.get(email=email)
            return self._to_entity(django_user)
        except DjangoUser.DoesNotExist:
            return None

    def exists_by_email(self, email: str) -> bool:
        return DjangoUser.objects.filter(email=email).exists()

    def exists_by_username(self, username: str) -> bool:
        return DjangoUser.objects.filter(username=username).exists()

    def get_count(self) -> int:
        return DjangoUser.objects.count()

    def save_report(self, report: ReportEntity) -> ReportEntity:
        from ..models import Report as DjangoReport
        defaults = {
            'reporter_id': report.reporter_id,
            'reported_to_id': report.reported_to_id,
            'room_id': report.room_id,
            'reason': report.reason,
            'status': report.status,
            'admin_notes': report.admin_notes
        }
        django_report, created = DjangoReport.objects.update_or_create(
            id=report.id, defaults=defaults
        )
        report.created_at = django_report.created_at
        report.updated_at = django_report.updated_at
        return report

    def save(self, user_entity: UserEntity) -> UserEntity:
        with transaction.atomic():
            django_user, created = DjangoUser.objects.update_or_create(
                id=user_entity.id,
                defaults={
                    'email': user_entity.email,
                    'username': user_entity.username,
                    'full_name': user_entity.full_name,
                    'is_active': user_entity.is_active,
                    'is_staff': user_entity.is_staff,
                    'is_verified': user_entity.is_verified,
                    'is_available': user_entity.is_available,
                    'verification_status': user_entity.verification_status,
                    'phone': user_entity.phone,
                    'country_code': user_entity.country_code,
                    'city': user_entity.city,
                    'address': user_entity.address,
                    'province': user_entity.province,
                    'municipality': user_entity.municipality,
                    'neighborhood': user_entity.neighborhood,
                    'occupation': user_entity.occupation,
                    'bio': user_entity.bio,
                    'last_seen': user_entity.last_seen,
                    'preferred_give_currency': user_entity.preferred_give_currency,
                    'preferred_want_currency': user_entity.preferred_want_currency,
                    'avatar': user_entity.avatar if isinstance(user_entity.avatar, str) else None,
                }
            )

            # CRIPTOGRAFIA E HASHING DE SENHA:
            # Gera o hash da senha em texto limpo utilizando o hasher padrão configurado (Argon2id).
            # Cria um salt aleatório por utilizador e aplica derivação de chave de memória antes da persistência na BD.
            if user_entity.password and not user_entity.password.startswith(('pbkdf2_', 'argon2$', 'bcrypt$')):
                django_user.set_password(user_entity.password)

            # Persistência de arquivo (Upload para Cloudinary se for um novo arquivo)
            if user_entity.avatar and not isinstance(user_entity.avatar, str):
                try:
                    # Lê o conteúdo do arquivo
                    file_content = user_entity.avatar.read()
                    filename = f"avatar_{django_user.id}"
                    # Upload para a nuvem
                    cloud_url = self.storage_service.upload(file_content, filename, folder="avatars")
                    # Guardamos apenas o URL no campo char se for o caso, 
                    # mas o ImageField do Django espera um arquivo se for para salvar localmente.
                    # Para simplificar: se temos Cloudinary, burlamos o armazenamento local e guardamos o link.
                    # No entanto, ImageField precisa de um File. 
                    # Uma alternativa comum é usar um CharField para o avatar se for sempre remoto.
                    django_user.avatar = cloud_url # O Django permite atribuir string a ImageField, ele guarda o caminho.
                except Exception as e:
                    print(f"--- ERRO CLOUDINARY REPOSITORY (Avatar): {str(e)} ---")
                    # Em produção deveríamos usar um logger. Aqui mostramos no terminal para debug.

            
            django_user.save()


            if user_entity.security:
                self.update_security(user_entity.security)
                
            return self._to_entity(django_user)

    def update_security(self, security: UserSecurityEntity) -> None:
        DjangoUserSecurity.objects.update_or_create(
            user_id=security.user_id,
            defaults={
                'email_token': security.email_token,
                'email_verified': security.email_verified,
                'email_verified_at': security.email_verified_at,
                'phone_otp': security.phone_otp,
                'phone_otp_expires_at': security.phone_otp_expires_at,
                'phone_verified': security.phone_verified,
                'failed_login_attempts': security.failed_login_attempts,
                'locked_until': security.locked_until,
                'two_factor_enabled': security.two_factor_enabled,
                'two_factor_secret': security.two_factor_secret,
                'two_factor_backup_codes': security.two_factor_backup_codes,
                'password_changed_at': security.password_changed_at,
                'password_reset_token': security.password_reset_token,
                'password_reset_expires': security.password_reset_expires,
            }
        )

    def get_security_by_user_id(self, user_id: uuid.UUID) -> Optional[UserSecurityEntity]:
        try:
            django_security, _ = DjangoUserSecurity.objects.get_or_create(user_id=user_id)
            return self._security_to_entity(django_security)
        except Exception:
            return None


    def get_security_by_email_token(self, token: str) -> Optional[UserSecurityEntity]:
        try:
            django_security = DjangoUserSecurity.objects.get(email_token=token)
            return self._security_to_entity(django_security)
        except DjangoUserSecurity.DoesNotExist:
            return None

    def get_security_by_reset_token(self, token: str) -> Optional[UserSecurityEntity]:
        try:
            django_security = DjangoUserSecurity.objects.get(password_reset_token=token)
            return self._security_to_entity(django_security)
        except DjangoUserSecurity.DoesNotExist:
            return None

    def save_kyc_document(self, document: IdentityDocumentEntity) -> None:
        django_identity, _ = DjangoIdentityDocument.objects.update_or_create(
            id=document.id,
            defaults={
                'user_id': document.user_id,
                'doc_type': document.doc_type,
                'doc_number': document.doc_number,
                'doc_country': document.doc_country,
                'status': document.status,
                'reviewed_at': document.reviewed_at,
                'reviewed_by_id': document.reviewed_by_id,
            }
        )
        # Handle files — either upload raw file objects or persist existing Cloudinary URLs
        def upload_field(field_name, prefix):
            field_val = getattr(document, field_name)
            if not field_val:
                return
            if isinstance(field_val, str):
                # Already a Cloudinary URL — persist directly
                setattr(django_identity, field_name, field_val)
            else:
                # Raw file object — upload to Cloudinary
                try:
                    content = field_val.read() if hasattr(field_val, 'read') else field_val
                    url = self.storage_service.upload(content, f"{prefix}_{document.id}", folder="kyc")
                    setattr(django_identity, field_name, url)
                except Exception as e:
                    print(f"--- ERRO CLOUDINARY (KYC {field_name}): {e} ---")

        upload_field('front_image', 'kyc_front')
        upload_field('back_image', 'kyc_back')
        upload_field('pdf_file', 'kyc_pdf')

        django_identity.save()


    def get_kyc_document_by_user_id(self, user_id: uuid.UUID) -> Optional[IdentityDocumentEntity]:
        try:
            django_identity = DjangoIdentityDocument.objects.get(user_id=user_id)
            return self._identity_to_entity(django_identity)
        except DjangoIdentityDocument.DoesNotExist:
            return None
    def _get_absolute_url(self, file_field) -> Optional[str]:
        if not file_field:
            return None
        
        try:
            # Se for um URL externo gravado diretamente (ex: Cloudinary)
            if file_field.name and file_field.name.startswith(('http://', 'https://')):
                return file_field.name
                
            url = file_field.url
            # Fallback para ficheiros guardados localmente
            from django.conf import settings
            base_url = getattr(settings, 'SITE_URL', 'http://localhost:8000')
            return f"{base_url.rstrip('/')}{url}"
        except Exception:
            return None

