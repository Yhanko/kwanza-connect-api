"""
Testes Unitários para Triagem de PEPs e Sanções no Motor AML (Lei n.º 05/20 Art. 19/20).
KwanzaConnect API — Sandbox BNA.
"""

from decimal import Decimal
from django.test import TestCase
from django.contrib.auth import get_user_model

from security.models import UserRiskProfile, SuspiciousActivityReport
from security.services.aml_engine import AMLEngine

User = get_user_model()


class TestPEPAndSanctionsAML(TestCase):

    def setUp(self):
        self.sanctioned_user = User.objects.create_user(
            email="sanctioned@kwanzaconnect.ao",
            password="StrongPassword2026!",
            full_name="Sanctioned Individual"
        )
        self.sanctioned_profile = UserRiskProfile.objects.create(
            user=self.sanctioned_user,
            risk_tier='TIER_2_VERIFIED',
            is_sanctioned=True
        )

        self.pep_user = User.objects.create_user(
            email="pep_politician@kwanzaconnect.ao",
            password="StrongPassword2026!",
            full_name="PEP Official"
        )
        self.pep_profile = UserRiskProfile.objects.create(
            user=self.pep_user,
            risk_tier='TIER_2_VERIFIED',
            is_pep=True
        )

    def test_sanctioned_user_is_blocked_immediately(self):
        result = AMLEngine.evaluate_transaction_risk(
            user=self.sanctioned_user,
            amount_aoa=Decimal('50000.00'),
            currency_code='AOA'
        )
        assert result.is_blocked is True
        assert 'SANCTION_MATCH' in result.rules_triggered
        assert result.risk_score == 100
        assert "Lista Restritiva / Sanções" in result.block_reason

        sar = SuspiciousActivityReport.objects.filter(
            user=self.sanctioned_user,
            rule_code='SANCTION_MATCH'
        ).first()
        assert sar is not None
        assert sar.severity == 'CRITICAL'
        assert sar.risk_score == 100

    def test_pep_user_triggers_enhanced_due_diligence(self):
        result = AMLEngine.evaluate_transaction_risk(
            user=self.pep_user,
            amount_aoa=Decimal('50000.00'),
            currency_code='AOA'
        )
        assert result.is_blocked is False  # Não bloqueia imediatamente, mas dispara EDD
        assert 'PEP_ENHANCED_DUE_DILIGENCE' in result.rules_triggered
        assert result.risk_score >= 60

        sar = SuspiciousActivityReport.objects.filter(
            user=self.pep_user,
            rule_code='PEP_ENHANCED_DUE_DILIGENCE'
        ).first()
        assert sar is not None
        assert sar.severity == 'HIGH'
        assert sar.status == 'PENDING_REVIEW'
