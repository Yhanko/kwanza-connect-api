"""
Motor de Prevenção ao Branqueamento de Capitais e Gestão de Riscos (AML / PCBC Engine).
KwanzaConnect API — Em estrita conformidade com a Lei n.º 05/20 e Sandbox Regulatório do BNA.
"""

import uuid
from decimal import Decimal
from typing import Optional, Dict, Any, Tuple, List
from dataclasses import dataclass, field
from datetime import timedelta
from django.utils import timezone
from django.db.models import Sum
from django.conf import settings
from rest_framework.exceptions import ValidationError

from ..models import SuspiciousActivityReport, UserRiskProfile
from audit.tasks import log_audit_event


# ─────────────────────────────────────────────
# 📊 Tabela Regulamentar de Limites BNA por Tier de KYC
# ─────────────────────────────────────────────

TIER_LIMITS: Dict[str, Dict[str, Any]] = {
    'TIER_0_UNVERIFIED': {
        'name': 'Tier 0 — Não Verificado',
        'max_per_operation_aoa': Decimal('0.00'),
        'max_daily_aoa': Decimal('0.00'),
        'max_monthly_aoa': Decimal('0.00'),
        'description': 'Acesso monetário bloqueado. Submeta a verificação KYC para iniciar transações.',
    },
    'TIER_1_BASIC': {
        'name': 'Tier 1 — KYC Básico (Em Análise)',
        'max_per_operation_aoa': Decimal('100000.00'),
        'max_daily_aoa': Decimal('500000.00'),
        'max_monthly_aoa': Decimal('200000.00'),
        'description': 'Limite inicial enquanto os documentos estão em análise pelo compliance.',
    },
    'TIER_2_VERIFIED': {
        'name': 'Tier 2 — Verificado Completo (BI + Selfie)',
        'max_per_operation_aoa': Decimal('2000000.00'),
        'max_daily_aoa': Decimal('5000000.00'),
        'max_monthly_aoa': Decimal('20000000.00'),
        'description': 'Limite padrão do Sandbox Regulatório do BNA com KYC aprovado.',
    },
    'TIER_3_BUSINESS': {
        'name': 'Tier 3 — Empresarial / PME (Alta Capacidade)',
        'max_per_operation_aoa': Decimal('10000000.00'),
        'max_daily_aoa': Decimal('25000000.00'),
        'max_monthly_aoa': Decimal('100000000.00'),
        'description': 'Entidades corporativas e comerciantes verificados com alta capacidade.',
    },
}

LARGE_VALUE_THRESHOLD_AOA = Decimal('1000000.00')  # Limiar de Reporte de Grandes Operações (LVTR)


@dataclass
class AMLRiskResult:
    is_blocked: bool = False
    block_reason: str = ""
    risk_score: int = 10
    rules_triggered: List[str] = field(default_factory=list)
    reports_created: List[SuspiciousActivityReport] = field(default_factory=list)


class AMLEngine:
    """
    Motor central de inteligência de conformidade, limites regulatórios e detecção de fraude cambial.
    """

    @classmethod
    def get_user_kyc_tier(cls, user) -> str:
        """
        Determina o Tier de KYC do utilizador com base no seu status de validação documental.
        """
        if not user or not user.is_authenticated:
            return 'TIER_0_UNVERIFIED'

        if getattr(user, 'is_staff', False) or getattr(user, 'is_superuser', False):
            return 'TIER_3_BUSINESS'

        # Verifica se há perfil de risco explícito
        if hasattr(user, 'risk_profile'):
            profile_tier = user.risk_profile.risk_tier
            if profile_tier:
                return profile_tier

        verification_status = getattr(user, 'verification_status', 'pending')
        if verification_status == 'approved':
            return 'TIER_2_VERIFIED'
        elif verification_status == 'submitted':
            return 'TIER_1_BASIC'
        return 'TIER_0_UNVERIFIED'

    @classmethod
    def get_or_create_risk_profile(cls, user) -> UserRiskProfile:
        tier = cls.get_user_kyc_tier(user)
        profile, created = UserRiskProfile.objects.get_or_create(
            user=user,
            defaults={'risk_tier': tier, 'risk_score': 10}
        )
        if not created and profile.risk_tier != tier:
            profile.risk_tier = tier
            profile.save(update_fields=['risk_tier'])
        return profile

    @classmethod
    def convert_to_aoa(cls, amount: Decimal, currency_code: str, rate_snapshot: Optional[Decimal] = None) -> Decimal:
        """
        Converte qualquer montante para o seu contravalor em Kwanzas (AOA) para cálculo de limites regulatórios.
        """
        if not amount:
            return Decimal('0.00')
        code = (currency_code or '').upper().strip()
        if code == 'AOA':
            return Decimal(str(amount))

        if rate_snapshot and rate_snapshot > Decimal('0'):
            # Se a taxa informada for AOA por unidade estrangeira (ex: 950 AOA por 1 USD)
            if rate_snapshot > Decimal('1.0'):
                return Decimal(str(amount)) * rate_snapshot
            else:
                return Decimal(str(amount)) / rate_snapshot

        # Fallback para taxa padrão aproximada de referência (ex: USD=950, EUR=1050)
        fallback_rates = {'USD': Decimal('950.0'), 'EUR': Decimal('1050.0'), 'GBP': Decimal('1200.0'), 'BRL': Decimal('170.0')}
        rate = fallback_rates.get(code, Decimal('950.0'))
        return Decimal(str(amount)) * rate

    @classmethod
    def get_accumulated_volumes(cls, user) -> Tuple[Decimal, Decimal]:
        """
        Calcula o volume transacionado acumulado pelo utilizador nas últimas 24h e nos últimos 30 dias.
        """
        now = timezone.now()
        day_ago = now - timedelta(days=1)
        month_ago = now - timedelta(days=30)

        daily_sum = Decimal('0.00')
        monthly_sum = Decimal('0.00')

        # Soma das transações confirmadas
        try:
            from transactions.models import Transaction
            from offers.models import Offer

            # Transações onde foi criador ou comprador
            user_txs_day = Transaction.objects.filter(
                models_q(buyer=user) | models_q(offer__owner=user),
                created_at__gte=day_ago,
                status__in=['completed', 'confirmed', 'in_escrow']
            )
            for tx in user_txs_day:
                give_aoa = cls.convert_to_aoa(tx.give_amount, getattr(tx.give_currency, 'code', 'AOA'))
                daily_sum += give_aoa

            user_txs_month = Transaction.objects.filter(
                models_q(buyer=user) | models_q(offer__owner=user),
                created_at__gte=month_ago,
                status__in=['completed', 'confirmed', 'in_escrow']
            )
            for tx in user_txs_month:
                give_aoa = cls.convert_to_aoa(tx.give_amount, getattr(tx.give_currency, 'code', 'AOA'))
                monthly_sum += give_aoa

            # Soma também ofertas ativas criadas hoje para evitar bypass criando várias ofertas simultâneas
            active_offers_today = Offer.objects.filter(
                owner=user,
                status='active',
                created_at__gte=day_ago
            )
            for off in active_offers_today:
                give_aoa = cls.convert_to_aoa(off.give_amount, getattr(off.give_currency, 'code', 'AOA'))
                daily_sum += give_aoa

        except Exception:
            pass

        return daily_sum, monthly_sum

    @classmethod
    def check_tier_limits(cls, user, amount_aoa: Decimal) -> Tuple[bool, str, Dict[str, Any]]:
        """
        Valida se o montante da operação respeita os limites por operação, diário e mensal do Tier de KYC.
        """
        tier = cls.get_user_kyc_tier(user)
        tier_cfg = TIER_LIMITS.get(tier, TIER_LIMITS['TIER_0_UNVERIFIED'])

        if tier == 'TIER_0_UNVERIFIED':
            return False, "Operação bloqueada: É necessário submeter a verificação de identidade (KYC) conforme as diretrizes do BNA.", {
                'tier': tier,
                'tier_name': tier_cfg['name'],
                'available_daily_aoa': Decimal('0.00'),
            }

        # 1. Limite por operação individual
        max_op = tier_cfg['max_per_operation_aoa']
        if amount_aoa > max_op:
            msg = (
                f"O valor de {amount_aoa:,.2f} AOA excede o limite máximo permitido por operação para o seu nível "
                f"({tier_cfg['name']}: {max_op:,.2f} AOA). Complete o KYC para aumentar seus limites."
            )
            return False, msg, {'tier': tier, 'tier_name': tier_cfg['name']}

        # 2. Limite diário acumulado (24h)
        daily_used, monthly_used = cls.get_accumulated_volumes(user)
        max_daily = tier_cfg['max_daily_aoa']
        if (daily_used + amount_aoa) > max_daily:
            available_daily = max(Decimal('0.00'), max_daily - daily_used)
            msg = (
                f"Esta transação excede o seu limite diário regulamentar no BNA de {max_daily:,.2f} AOA. "
                f"Limite diário restante: {available_daily:,.2f} AOA."
            )
            return False, msg, {'tier': tier, 'available_daily_aoa': available_daily}

        # 3. Limite mensal acumulado (30 dias)
        max_monthly = tier_cfg['max_monthly_aoa']
        if (monthly_used + amount_aoa) > max_monthly:
            available_monthly = max(Decimal('0.00'), max_monthly - monthly_used)
            msg = (
                f"Esta transação excede o seu limite mensal regulamentar no BNA de {max_monthly:,.2f} AOA. "
                f"Limite mensal restante: {available_monthly:,.2f} AOA."
            )
            return False, msg, {'tier': tier, 'available_monthly_aoa': available_monthly}

        return True, "", {
            'tier': tier,
            'tier_name': tier_cfg['name'],
            'daily_used_aoa': daily_used,
            'monthly_used_aoa': monthly_used,
            'available_daily_aoa': max_daily - (daily_used + amount_aoa),
        }

    @classmethod
    def evaluate_transaction_risk(
        cls,
        user,
        amount_aoa: Decimal,
        currency_code: str,
        rate_snapshot: Optional[Decimal] = None,
        offer_id: Optional[uuid.UUID] = None,
        transaction_id: Optional[uuid.UUID] = None,
        context_data: Optional[Dict[str, Any]] = None
    ) -> AMLRiskResult:
        """
        Avalia integralmente os riscos de Prevenção ao Branqueamento de Capitais (PCBC/FT) em tempo real.
        """
        result = AMLRiskResult()
        profile = cls.get_or_create_risk_profile(user)
        tier = cls.get_user_kyc_tier(user)
        tier_cfg = TIER_LIMITS.get(tier, TIER_LIMITS['TIER_0_UNVERIFIED'])

        # ── REGRA 0: Triagem de Listas de Sanções e PEPs (Lei n.º 05/20 Art. 19 e 20) ───
        if profile.is_sanctioned:
            result.is_blocked = True
            result.block_reason = "Operação bloqueada preventivamente em cumprimento à Lei n.º 05/20 (Lista Restritiva / Sanções)."
            result.rules_triggered.append('SANCTION_MATCH')
            result.risk_score = 100

            sar = SuspiciousActivityReport.objects.create(
                user=user,
                related_offer_id=offer_id,
                related_transaction_id=transaction_id,
                rule_code='SANCTION_MATCH',
                severity='CRITICAL',
                risk_score=100,
                amount_aoa=amount_aoa,
                status='UNDER_INVESTIGATION',
                details={
                    'reason': 'Utilizador listado em lista restritiva ou de sanções internacionais/nacionais.',
                    'legal_basis': 'Lei n.º 05/20 Art. 20 (Medidas Restritivas Obrigatórias)',
                    'amount_aoa': str(amount_aoa),
                    'timestamp': timezone.now().isoformat()
                }
            )
            result.reports_created.append(sar)
            return result

        if profile.is_pep:
            result.rules_triggered.append('PEP_ENHANCED_DUE_DILIGENCE')
            result.risk_score = max(result.risk_score, 60)
            sar = SuspiciousActivityReport.objects.create(
                user=user,
                related_offer_id=offer_id,
                related_transaction_id=transaction_id,
                rule_code='PEP_ENHANCED_DUE_DILIGENCE',
                severity='HIGH',
                risk_score=60,
                amount_aoa=amount_aoa,
                status='PENDING_REVIEW',
                details={
                    'reason': 'Operação envolvendo Pessoa Exposta Politicamente (PEP) sujeita a Diligência Reforçada (EDD).',
                    'legal_basis': 'Lei n.º 05/20 Art. 19 (Pessoas Expostas Politicamente)',
                    'amount_aoa': str(amount_aoa),
                    'timestamp': timezone.now().isoformat()
                }
            )
            result.reports_created.append(sar)

        # ── REGRA 1: Validação Estrita de Limite por Tier de KYC ─────────
        is_valid_tier, tier_msg, _ = cls.check_tier_limits(user, amount_aoa)
        if not is_valid_tier:
            result.is_blocked = True
            result.block_reason = tier_msg
            result.rules_triggered.append('TIER_LIMIT_EXCEEDED')
            result.risk_score = 90

            # Registar SAR regulatório de tentativa de violação de limites
            sar = SuspiciousActivityReport.objects.create(
                user=user,
                related_offer_id=offer_id,
                related_transaction_id=transaction_id,
                rule_code='TIER_LIMIT_EXCEEDED',
                severity='MEDIUM',
                risk_score=90,
                amount_aoa=amount_aoa,
                status='PENDING_REVIEW',
                details={
                    'reason': tier_msg,
                    'tier': tier,
                    'amount_aoa': str(amount_aoa),
                    'timestamp': timezone.now().isoformat()
                }
            )
            result.reports_created.append(sar)
            return result


        # ── REGRA 2: Detecção de Fracionamento / Smurfing ──────────────────
        # Múltiplas transações logo abaixo do limite por operação (ex: >= 80% do limite máximo) nas últimas 24h
        max_op = tier_cfg['max_per_operation_aoa']
        if max_op > Decimal('0') and amount_aoa >= (max_op * Decimal('0.80')):
            now = timezone.now()
            recent_count = SuspiciousActivityReport.objects.filter(
                user=user,
                rule_code='STRUCTURING_SMURFING',
                created_at__gte=now - timedelta(hours=24)
            ).count()

            if recent_count >= 2:
                # Terceira transação consecutiva de valor no limite
                result.rules_triggered.append('STRUCTURING_SMURFING')
                result.risk_score = max(result.risk_score, 85)
                sar = SuspiciousActivityReport.objects.create(
                    user=user,
                    related_offer_id=offer_id,
                    related_transaction_id=transaction_id,
                    rule_code='STRUCTURING_SMURFING',
                    severity='HIGH',
                    risk_score=85,
                    amount_aoa=amount_aoa,
                    status='PENDING_REVIEW',
                    details={
                        'pattern': 'Múltiplas transações consecutivas próximas ao limite máximo permitido (padrão de fracionamento/smurfing).',
                        'amount_aoa': str(amount_aoa),
                        'max_per_op': str(max_op),
                        'recent_count': recent_count + 1
                    }
                )
                result.reports_created.append(sar)

        # ── REGRA 3: Detecção de Frequência Anômala / Velocity Check ───────
        now = timezone.now()
        ten_mins_ago = now - timedelta(minutes=10)
        from audit.infra.models import AuditLog
        recent_activity_count = AuditLog.objects.filter(
            user=user,
            action__in=['OFFER_CREATE', 'TRANSACTION_CONFIRM', 'EXCHANGE_INITIATE'],
            timestamp__gte=ten_mins_ago
        ).count()

        if recent_activity_count >= 4:
            result.rules_triggered.append('HIGH_VELOCITY')
            result.risk_score = max(result.risk_score, 75)
            sar = SuspiciousActivityReport.objects.create(
                user=user,
                related_offer_id=offer_id,
                related_transaction_id=transaction_id,
                rule_code='HIGH_VELOCITY',
                severity='MEDIUM',
                risk_score=75,
                amount_aoa=amount_aoa,
                status='PENDING_REVIEW',
                details={
                    'pattern': f'{recent_activity_count} operações financeiras disparadas em menos de 10 minutos.',
                    'amount_aoa': str(amount_aoa)
                }
            )
            result.reports_created.append(sar)

        # ── REGRA 4: Alerta de Grande Volume (LVTR) ────────────────────────
        if amount_aoa >= LARGE_VALUE_THRESHOLD_AOA:
            result.rules_triggered.append('LARGE_VALUE_ALERT')
            sar = SuspiciousActivityReport.objects.create(
                user=user,
                related_offer_id=offer_id,
                related_transaction_id=transaction_id,
                rule_code='LARGE_VALUE_ALERT',
                severity='LOW' if tier in ['TIER_2_VERIFIED', 'TIER_3_BUSINESS'] else 'HIGH',
                risk_score=60,
                amount_aoa=amount_aoa,
                status='PENDING_REVIEW',
                details={
                    'pattern': f'Operação atinge ou excede o limiar de grande volume do BNA ({LARGE_VALUE_THRESHOLD_AOA:,.2f} AOA).',
                    'amount_aoa': str(amount_aoa),
                    'tier': tier
                }
            )
            result.reports_created.append(sar)

        # ── REGRA 5: Desvio Cambial Excessivo da Taxa BNA (RATE_OUTLIER) ───
        if rate_snapshot and rate_snapshot > Decimal('0') and currency_code:
            from security.services.spread_monitor import BNASpreadMonitor
            is_valid_spread, is_warning_spread, dev_pct, spread_msg = BNASpreadMonitor.check_exchange_rate_spread(
                offered_rate=rate_snapshot,
                from_currency=currency_code,
                to_currency='AOA'
            )

            if not is_valid_spread:
                result.is_blocked = True
                result.block_reason = spread_msg
                result.rules_triggered.append('RATE_OUTLIER')
                result.risk_score = 95
                sar = SuspiciousActivityReport.objects.create(
                    user=user,
                    related_offer_id=offer_id,
                    related_transaction_id=transaction_id,
                    rule_code='RATE_OUTLIER',
                    severity='CRITICAL',
                    risk_score=95,
                    amount_aoa=amount_aoa,
                    status='UNDER_INVESTIGATION',
                    details={
                        'pattern': 'Tentativa de operação com taxa cambial excessivamente fora da banda regulamentar BNA.',
                        'offered_rate': str(rate_snapshot),
                        'currency_code': currency_code,
                        'deviation_percent': round(dev_pct, 2),
                        'amount_aoa': str(amount_aoa),
                        'reason': spread_msg
                    }
                )
                result.reports_created.append(sar)
            elif is_warning_spread:
                result.rules_triggered.append('RATE_OUTLIER')
                result.risk_score = max(result.risk_score, 70)
                sar = SuspiciousActivityReport.objects.create(
                    user=user,
                    related_offer_id=offer_id,
                    related_transaction_id=transaction_id,
                    rule_code='RATE_OUTLIER',
                    severity='MEDIUM',
                    risk_score=70,
                    amount_aoa=amount_aoa,
                    status='PENDING_REVIEW',
                    details={
                        'pattern': 'Operação com desvio cambial em relação à taxa de referência oficial do BNA.',
                        'offered_rate': str(rate_snapshot),
                        'currency_code': currency_code,
                        'deviation_percent': round(dev_pct, 2),
                        'amount_aoa': str(amount_aoa),
                        'reason': spread_msg
                    }
                )
                result.reports_created.append(sar)

        # Atualiza o score do perfil de risco se houve alertas
        if result.rules_triggered:
            profile.risk_score = min(100, profile.risk_score + len(result.rules_triggered) * 15)
            profile.save(update_fields=['risk_score'])

        return result


    @classmethod
    def get_user_limits_summary(cls, user) -> Dict[str, Any]:
        """
        Retorna o sumário consolidado de limites do utilizador para exibição na UI/Frontend.
        """
        tier = cls.get_user_kyc_tier(user)
        tier_cfg = TIER_LIMITS.get(tier, TIER_LIMITS['TIER_0_UNVERIFIED'])
        daily_used, monthly_used = cls.get_accumulated_volumes(user)

        max_op = tier_cfg['max_per_operation_aoa']
        max_daily = tier_cfg['max_daily_aoa']
        max_monthly = tier_cfg['max_monthly_aoa']

        return {
            'tier': tier,
            'tier_name': tier_cfg['name'],
            'description': tier_cfg['description'],
            'max_per_operation_aoa': float(max_op),
            'max_daily_aoa': float(max_daily),
            'max_monthly_aoa': float(max_monthly),
            'daily_used_aoa': float(daily_used),
            'monthly_used_aoa': float(monthly_used),
            'available_daily_aoa': float(max(Decimal('0.00'), max_daily - daily_used)),
            'available_monthly_aoa': float(max(Decimal('0.00'), max_monthly - monthly_used)),
            'is_monetary_access_allowed': tier != 'TIER_0_UNVERIFIED',
        }


def models_q(**kwargs):
    """Helper para construir Q queries dinamicamente evitando imports circulares."""
    from django.db.models import Q
    return Q(**kwargs)
