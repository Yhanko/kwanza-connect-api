import secrets
import hashlib
import uuid
from decimal import Decimal
from django.db import models
from django.conf import settings
from django.utils import timezone


class APIKey(models.Model):
    """
    Representa uma chave de acesso para clientes da API (Frontend, Mobile, etc).
    A chave real não é armazenada; apenas o seu hash SHA-256.
    """
    name       = models.CharField(max_length=100, unique=True, help_text="Nome do cliente/serviço (ex: Mobile App)")
    prefix     = models.CharField(max_length=16, unique=True, editable=False)
    hashed_key = models.CharField(max_length=64, editable=False)
    
    is_active  = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    last_used  = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "Chave de API"
        verbose_name_plural = "Chaves de API"

    def __str__(self):
        return f"{self.name} ({self.prefix}...)"

    @classmethod
    def generate(cls, name, expires_at=None):
        """Gera uma nova chave e retorna (object, raw_key)."""
        prefix  = secrets.token_hex(4) # 8 chars
        secret  = secrets.token_urlsafe(32)
        raw_key = f"kc_{prefix}.{secret}"
        
        hashed  = hashlib.sha256(raw_key.encode()).hexdigest()
        
        obj = cls.objects.create(
            name=name,
            prefix=prefix,
            hashed_key=hashed,
            expires_at=expires_at
        )
        return obj, raw_key

    def verify(self, raw_key):
        """Verifica se a chave fornecida é válida."""
        if not self.is_active:
            return False
        if self.expires_at and self.expires_at < timezone.now():
            return False
        
        match = hashlib.sha256(raw_key.encode()).hexdigest() == self.hashed_key
        if match:
            self.last_used = timezone.now()
            self.save(update_fields=['last_used'])
        return match


# ─────────────────────────────────────────────
#  Gestão de Riscos & PCBC/FT (Lei n.º 05/20 / BNA)
# ─────────────────────────────────────────────

class UserRiskProfile(models.Model):
    """
    Perfil contínuo de risco e conformidade do utilizador perante o BNA e UIF.
    """
    TIERS = [
        ('TIER_0_UNVERIFIED', 'Tier 0 - Não Verificado (Sem Acesso Monetário)'),
        ('TIER_1_BASIC', 'Tier 1 - Básico (Em Análise / Limite Baixo)'),
        ('TIER_2_VERIFIED', 'Tier 2 - Verificado Completo (BI + Selfie)'),
        ('TIER_3_BUSINESS', 'Tier 3 - Empresarial / PME (Alta Capacidade)'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='risk_profile')
    risk_tier = models.CharField(max_length=30, choices=TIERS, default='TIER_0_UNVERIFIED', db_index=True)
    risk_score = models.PositiveIntegerField(default=10, help_text="Score de 0 a 100")
    
    is_pep = models.BooleanField(default=False, help_text="Pessoa Exposta Politicamente")
    is_sanctioned = models.BooleanField(default=False, help_text="Listas de Sanções Internacionais/Nacionais")
    is_high_risk = models.BooleanField(default=False)
    
    total_completed_volume_aoa = models.DecimalField(max_digits=18, decimal_places=2, default=Decimal('0.00'))
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Perfil de Risco do Utilizador"
        verbose_name_plural = "Perfis de Risco dos Utilizadores"

    def __str__(self):
        return f"{self.user.email} - {self.get_risk_tier_display()} (Score: {self.risk_score})"


class SuspiciousActivityReport(models.Model):
    """
    Registo de Atividade Suspeita (SAR / Declaração de Operação Suspeita - DOS).
    Conforme as obrigações da Lei n.º 05/20 para reporte à Unidade de Informação Financeira (UIF).
    """
    RULE_CODES = [
        ('STRUCTURING_SMURFING', 'Fracionamento / Smurfing de Valores'),
        ('HIGH_VELOCITY', 'Pico de Velocidade / Frequência Anômala'),
        ('LARGE_VALUE_ALERT', 'Operação de Grande Volume (LVTR)'),
        ('RATE_OUTLIER', 'Desvio Cambial Excessivo da Taxa BNA'),
        ('TIER_LIMIT_EXCEEDED', 'Tentativa de Exceder Limite de KYC'),
        ('HIGH_RISK_USER', 'Utilizador com Múltiplas Denúncias/Alto Risco'),
        ('SUSPICIOUS_PATTERN', 'Padrão Suspeito Indefinido'),
    ]

    SEVERITY_LEVELS = [
        ('LOW', 'Baixa'),
        ('MEDIUM', 'Média'),
        ('HIGH', 'Alta'),
        ('CRITICAL', 'Crítica'),
    ]

    STATUS_CHOICES = [
        ('PENDING_REVIEW', 'Pendente de Revisão'),
        ('UNDER_INVESTIGATION', 'Em Investigação'),
        ('ESCALATED_TO_UIF', 'Reportado à UIF (Unidade de Informação Financeira)'),
        ('DISMISSED_FALSE_POSITIVE', 'Arquivado / Falso Positivo'),
        ('RESOLVED_BLOCKED', 'Resolvido com Bloqueio de Conta'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='aml_reports', db_index=True)
    related_offer_id = models.UUIDField(null=True, blank=True, db_index=True)
    related_transaction_id = models.UUIDField(null=True, blank=True, db_index=True)

    rule_code = models.CharField(max_length=40, choices=RULE_CODES, db_index=True)
    severity = models.CharField(max_length=15, choices=SEVERITY_LEVELS, default='MEDIUM', db_index=True)
    risk_score = models.PositiveIntegerField(default=50)
    amount_aoa = models.DecimalField(max_digits=18, decimal_places=2, default=Decimal('0.00'))

    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default='PENDING_REVIEW', db_index=True)
    details = models.JSONField(default=dict, blank=True)

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    resolved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='resolved_aml_reports'
    )
    resolution_notes = models.TextField(blank=True)
    reported_to_uif_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Relatório de Atividade Suspeita (SAR/DOS)'
        verbose_name_plural = 'Relatórios de Atividades Suspeitas (SAR/DOS)'

    def __str__(self):
        return f"SAR-{self.id.hex[:8].upper()} | [{self.severity}] {self.get_rule_code_display()} - {self.user.email}"


# ─────────────────────────────────────────────
# 🔄 Continuidade de Negócio & DRP (Sandbox BNA)
# ─────────────────────────────────────────────

class DatabaseBackupLog(models.Model):
    """
    Registo de Auditoria de Backups e Continuidade de Negócio (BCP / DRP).
    Em conformidade com as diretrizes de RPO <= 15m e RTO <= 30m do Sandbox BNA.
    """
    STATUS_CHOICES = [
        ('PENDING', 'Em Execução'),
        ('SUCCESS', 'Concluído com Sucesso'),
        ('VERIFIED', 'Verificado & Testado'),
        ('FAILED', 'Falha na Execução'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    filename = models.CharField(max_length=255, unique=True, db_index=True)
    file_size_bytes = models.BigIntegerField(default=0)
    sha256_checksum = models.CharField(max_length=64, help_text="Hash SHA-256 para integridade à prova de adulteração")
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING', db_index=True)
    encrypted_with = models.CharField(max_length=50, default='AES-256-Fernet')
    storage_location = models.CharField(max_length=255, default='local_encrypted_storage')
    
    duration_seconds = models.FloatField(default=0.0, help_text="Tempo de execução do backup")
    
    is_dr_tested = models.BooleanField(default=False, help_text="Se passou no teste de recuperação de desastres")
    dr_test_at = models.DateTimeField(null=True, blank=True)
    dr_test_rto_seconds = models.FloatField(null=True, blank=True, help_text="Tempo real medido para restauração (RTO)")
    dr_test_notes = models.TextField(blank=True)
    
    triggered_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='triggered_backups'
    )
    error_message = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Registo de Backup / DRP'
        verbose_name_plural = 'Registos de Backup / DRP'

    def __str__(self):
        return f"BACKUP-{self.created_at.strftime('%Y%m%d_%H%M%S')} [{self.status}] ({self.file_size_bytes} bytes)"


