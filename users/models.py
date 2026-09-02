from django.db import models
import uuid
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.contrib.auth.password_validation import validate_password
from django.utils import timezone
from security.encryption import EncryptedCharField, compute_blind_index
from security.masking import mask_doc_number, mask_phone


class UserManager(BaseUserManager):

    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError('O email é obrigatório.')
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        if password:
            validate_password(password, user=user)
            user.set_password(password)
        else:
            user.set_unusable_password()
        user.save(using=self._db)
        return user


    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_active', True)
        extra_fields.setdefault('is_verified', True)
        return self.create_user(email, password, **extra_fields)


def avatar_upload_path(instance, filename):
    ext = filename.split('.')[-1]
    return f'avatars/{instance.id}.{ext}'


class User(AbstractBaseUser, PermissionsMixin):

    VERIFICATION_STATUS = [
        ('pending',  'Pendente'),
        ('submitted','Documentos enviados'),
        ('approved', 'Verificado'),
        ('rejected', 'Rejeitado'),
    ]

    id                  = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # --- Credenciais ---
    email               = models.EmailField(unique=True)
    username            = models.CharField(max_length=150, unique=True, null=True, blank=True)

    # --- Dados pessoais ---
    full_name           = models.CharField(max_length=150)
    phone               = models.CharField(max_length=20, blank=True)
    country_code        = models.CharField(max_length=5, default='AO')   # ISO 3166-1 alpha-2
    city                = models.CharField(max_length=100, blank=True)
    address             = models.CharField(max_length=255, blank=True)
    province            = models.CharField(max_length=100, blank=True)
    municipality        = models.CharField(max_length=100, blank=True)
    neighborhood        = models.CharField(max_length=255, blank=True)
    occupation          = models.CharField(max_length=100, blank=True)
    bio                 = models.TextField(max_length=300, blank=True)
    avatar              = models.ImageField(upload_to=avatar_upload_path, null=True, blank=True, max_length=500)


    # --- Estado da conta ---
    is_active           = models.BooleanField(default=False)   # activado por email
    is_staff            = models.BooleanField(default=False)
    is_verified         = models.BooleanField(default=False)   # KYC aprovado
    is_available        = models.BooleanField(default=False)   # disponível p/ trocar
    verification_status = models.CharField(
        max_length=10, choices=VERIFICATION_STATUS, default='pending'
    )

    # --- Actividade ---
    last_seen           = models.DateTimeField(null=True, blank=True)
    date_joined         = models.DateTimeField(default=timezone.now)

    # --- Sanções e Arbitragem (Admin) ---
    suspended_until     = models.DateTimeField(null=True, blank=True)
    restricted_until    = models.DateTimeField(null=True, blank=True)
    restricted_pages    = models.JSONField(default=list, blank=True)

    # --- Moedas preferenciais (para filtros rápidos) ---
    preferred_give_currency = models.CharField(max_length=10, blank=True)  # ex: AOA
    preferred_want_currency = models.CharField(max_length=10, blank=True)  # ex: USD

    objects = UserManager()

    USERNAME_FIELD  = 'email'
    REQUIRED_FIELDS = ['full_name']

    class Meta:
        verbose_name = 'Utilizador'
        verbose_name_plural = 'Utilizadores'
        ordering = ['-date_joined']

    def __str__(self):
        return f'{self.full_name} <{self.email}>'

    def update_last_seen(self):
        self.last_seen = timezone.now()
        self.save(update_fields=['last_seen'])

    @property
    def is_kyc_complete(self):
        return self.verification_status == 'approved'


# ─────────────────────────────────────────────
#  Documentos de identidade (KYC)
# ─────────────────────────────────────────────

def doc_upload_path(instance, filename):
    ext = filename.split('.')[-1]
    return f'documents/{instance.user_id}/{filename}'


class IdentityDocument(models.Model):

    DOC_TYPE = [
        ('bi',        'Bilhete de Identidade'),
        ('passport',  'Passaporte'),
        ('residence', 'Autorização de Residência'),
    ]

    STATUS = [
        ('pending',   'Aguardando revisão'),
        ('approved',  'Aprovado'),
        ('rejected',  'Rejeitado'),
    ]

    id           = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user         = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name='identity_document'
    )
    doc_type     = models.CharField(max_length=15, choices=DOC_TYPE)
    doc_number   = EncryptedCharField(max_length=100, blank=True, null=True)
    doc_number_hash = models.CharField(max_length=64, unique=True, null=True, blank=True, db_index=True)
    doc_country  = models.CharField(max_length=5, default='AO')

    # Imagens ou PDF — obrigatório pelo menos frente + verso OU pdf
    front_image  = models.ImageField(upload_to=doc_upload_path, null=True, blank=True, max_length=500)
    back_image   = models.ImageField(upload_to=doc_upload_path, null=True, blank=True, max_length=500)
    pdf_file     = models.FileField(upload_to=doc_upload_path, null=True, blank=True, max_length=500)


    status       = models.CharField(max_length=10, choices=STATUS, default='pending')
    rejection_reason = models.TextField(blank=True)

    submitted_at = models.DateTimeField(auto_now_add=True)
    reviewed_at  = models.DateTimeField(null=True, blank=True)
    reviewed_by  = models.ForeignKey(
        User, null=True, blank=True,
        on_delete=models.SET_NULL, related_name='reviewed_documents'
    )

    class Meta:
        verbose_name = 'Documento de identidade'

    def save(self, *args, **kwargs):
        if self.doc_number:
            self.doc_number_hash = compute_blind_index(self.doc_number)
        super().save(*args, **kwargs)

    @property
    def masked_doc_number(self) -> str:
        return mask_doc_number(self.doc_number)

    def clean(self):
        super().clean()
        has_images = self.front_image and self.back_image
        has_pdf    = bool(self.pdf_file)
        if not has_images and not has_pdf:
            from django.core.exceptions import ValidationError
            raise ValidationError(
                'Envie frente + verso do documento OU um ficheiro PDF.'
            )

    def __str__(self):
        return f'{self.get_doc_type_display()} — {self.user.full_name}'


# ─────────────────────────────────────────────
#  Segurança e autenticação
# ─────────────────────────────────────────────

class UserSecurity(models.Model):

    id                   = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user                 = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name='security'
    )

    # Verificação de email
    email_token          = models.CharField(max_length=64, blank=True)
    email_verified       = models.BooleanField(default=False)
    email_verified_at    = models.DateTimeField(null=True, blank=True)

    # OTP de telemóvel
    phone_otp            = models.CharField(max_length=6, blank=True)
    phone_otp_expires_at = models.DateTimeField(null=True, blank=True)
    phone_verified       = models.BooleanField(default=False)

    # Protecção contra brute-force
    failed_login_attempts = models.PositiveSmallIntegerField(default=0)
    locked_until         = models.DateTimeField(null=True, blank=True)

    # 2FA (TOTP — Google Authenticator)
    two_factor_enabled      = models.BooleanField(default=False)
    two_factor_secret       = EncryptedCharField(max_length=128, blank=True)
    two_factor_backup_codes = models.JSONField(default=list, blank=True)

    # Auditoria de senha
    password_changed_at  = models.DateTimeField(null=True, blank=True)

    # Token de reset de senha
    password_reset_token   = models.CharField(max_length=64, blank=True)
    password_reset_expires = models.DateTimeField(null=True, blank=True)

    def generate_backup_codes(self, count=8):
        """
        Gera uma lista de códigos de recuperação alfanuméricos de uso único.
        Armazena os hashes SHA-256 no banco e retorna os códigos em texto claro.
        """
        import secrets
        import hashlib
        plain_codes = []
        hashed_codes = []
        for _ in range(count):
            part1 = secrets.token_hex(2).upper()
            part2 = secrets.token_hex(2).upper()
            code = f"{part1}-{part2}"
            plain_codes.append(code)
            hashed_codes.append(hashlib.sha256(code.encode()).hexdigest())

        self.two_factor_backup_codes = hashed_codes
        self.save()
        return plain_codes


    def verify_and_consume_backup_code(self, raw_code: str) -> bool:
        """
        Verifica se o código de recuperação fornecido é válido.
        Se for válido, consome-o imediatamente (de uso único) e retorna True.
        """
        import hashlib
        if not raw_code:
            return False
        normalized_code = raw_code.strip().upper()
        code_hash = hashlib.sha256(normalized_code.encode()).hexdigest()

        if self.two_factor_backup_codes and code_hash in self.two_factor_backup_codes:
            updated_codes = [c for c in self.two_factor_backup_codes if c != code_hash]
            self.two_factor_backup_codes = updated_codes
            self.save(update_fields=['two_factor_backup_codes'])
            return True
        return False


    class Meta:
        verbose_name = 'Segurança do utilizador'

    def __str__(self):
        return f'Segurança — {self.user.email}'

    @property
    def is_locked(self):
        if self.locked_until and self.locked_until > timezone.now():
            return True
        return False

    def register_failed_login(self):
        self.failed_login_attempts += 1
        if self.failed_login_attempts >= 5:
            from datetime import timedelta
            self.locked_until = timezone.now() + timedelta(minutes=15)
        self.save(update_fields=['failed_login_attempts', 'locked_until'])

    def reset_failed_logins(self):
        self.failed_login_attempts = 0
        self.locked_until = None
        self.save(update_fields=['failed_login_attempts', 'locked_until'])


# ─────────────────────────────────────────────
#  Denúncias entre utilizadores
# ─────────────────────────────────────────────

class UserReport(models.Model):

    REASONS = [
        ('spam',        'Spam'),
        ('fraud',       'Tentativa de fraude'),
        ('fake',        'Perfil falso'),
        ('harassment',  'Assédio ou ameaça'),
        ('other',       'Outro'),
    ]

    STATUS = [
        ('open',       'Em aberto'),
        ('reviewing',  'Em revisão'),
        ('resolved',   'Resolvido'),
        ('dismissed',  'Arquivado'),
    ]

    id          = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    reporter    = models.ForeignKey(User, on_delete=models.CASCADE, related_name='reports_made')
    reported    = models.ForeignKey(User, on_delete=models.CASCADE, related_name='reports_received')
    reason      = models.CharField(max_length=20, choices=REASONS)
    description = models.TextField(max_length=1000, blank=True)
    status      = models.CharField(max_length=10, choices=STATUS, default='open')
    created_at  = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Denúncia'
        unique_together = [['reporter', 'reported']]  # 1 denúncia por par

    def __str__(self):
        return f'{self.reporter} denunciou {self.reported} — {self.get_reason_display()}'

class Report(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    reporter = models.ForeignKey(User, related_name='submitted_reports', on_delete=models.CASCADE)
    reported_to = models.ForeignKey(User, related_name='received_reports', on_delete=models.CASCADE)
    room_id = models.UUIDField(null=True, blank=True)
    reason = models.TextField(max_length=1500)
    status = models.CharField(max_length=20, default='pending')
    admin_notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']


# ─────────────────────────────────────────────
#  Consentimento de Privacidade & APD (Lei n.º 22/11)
# ─────────────────────────────────────────────

class DataPrivacyConsent(models.Model):
    """
    Registo auditável e imutável de consentimento do utilizador para tratamento de dados pessoais,
    em conformidade com a Lei n.º 22/11 (Lei de Protecção de Dados Pessoais de Angola) e directrizes do BNA.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='privacy_consents', db_index=True)
    terms_version = models.CharField(max_length=50, default='v1.2-sandbox-bna')
    privacy_policy_version = models.CharField(max_length=50, default='v1.2-apd-lei2211')
    terms_content_hash = models.CharField(max_length=64, help_text="Hash SHA-256 do conteúdo integral dos termos aceites")
    
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    
    consented_at = models.DateTimeField(default=timezone.now, db_index=True)
    revoked_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-consented_at']
        verbose_name = 'Consentimento de Privacidade (APD)'
        verbose_name_plural = 'Consentimentos de Privacidade (APD)'

    def __str__(self):
        return f"Consentimento {self.terms_version} - {self.user.email} [{self.consented_at.strftime('%Y-%m-%d %H:%M')}]"


# ─────────────────────────────────────────────
#  Histórico de Acessos & Detecção de Anomalias
# ─────────────────────────────────────────────

class UserLoginHistory(models.Model):
    """
    Registo de histórico de logins para detecção de anomalias de acesso,
    viagens impossíveis (Impossible Travel) e dispositivos não autorizados.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='login_history', db_index=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True, db_index=True)
    user_agent = models.TextField(blank=True)
    device_fingerprint = models.CharField(max_length=64, blank=True, db_index=True)
    
    country_code = models.CharField(max_length=5, default='AO')
    city = models.CharField(max_length=100, blank=True)
    is_anomalous = models.BooleanField(default=False, db_index=True)
    anomaly_reasons = models.JSONField(default=list, blank=True)
    
    login_at = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        ordering = ['-login_at']
        verbose_name = 'Histórico de Login'
        verbose_name_plural = 'Históricos de Login'

    def __str__(self):
        return f"Login {self.user.email} - IP: {self.ip_address} [{self.login_at.strftime('%Y-%m-%d %H:%M')}]"