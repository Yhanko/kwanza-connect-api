from decimal import Decimal
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework import status

from security.models import SuspiciousActivityReport, UserRiskProfile
from security.services.aml_engine import AMLEngine, TIER_LIMITS
from audit.infra.models import AuditLog


User = get_user_model()


class TestAMLEngine(TestCase):
    def setUp(self):
        self.user_unverified = User.objects.create_user(
            email="unverified@kwanzaconnect.ao",
            password="StrongPassword2026!",
            full_name="Unverified User",
            verification_status="pending"
        )
        self.user_basic = User.objects.create_user(
            email="basic@kwanzaconnect.ao",
            password="StrongPassword2026!",
            full_name="Basic Tier 1 User",
            verification_status="submitted"
        )
        self.user_verified = User.objects.create_user(
            email="verified@kwanzaconnect.ao",
            password="StrongPassword2026!",
            full_name="Verified Tier 2 User",
            verification_status="approved"
        )
        self.user_admin = User.objects.create_superuser(
            email="compliance_admin@kwanzaconnect.ao",
            password="StrongPassword2026!",
            full_name="Compliance Admin"
        )
        self.client = APIClient()

    def test_get_user_kyc_tier(self):
        assert AMLEngine.get_user_kyc_tier(self.user_unverified) == "TIER_0_UNVERIFIED"
        assert AMLEngine.get_user_kyc_tier(self.user_basic) == "TIER_1_BASIC"
        assert AMLEngine.get_user_kyc_tier(self.user_verified) == "TIER_2_VERIFIED"
        assert AMLEngine.get_user_kyc_tier(self.user_admin) == "TIER_3_BUSINESS"

    def test_tier_0_unverified_blocked_from_monetary_transactions(self):
        is_valid, msg, info = AMLEngine.check_tier_limits(self.user_unverified, Decimal("50000.00"))
        assert is_valid is False
        assert "KYC" in msg or "bloqueada" in msg
        assert info["tier"] == "TIER_0_UNVERIFIED"

    def test_tier_1_basic_per_operation_limit(self):
        # 50.000 AOA está dentro do limite de 100.000 AOA
        is_valid, _, _ = AMLEngine.check_tier_limits(self.user_basic, Decimal("50000.00"))
        assert is_valid is True

        # 150.000 AOA excede o limite de 100.000 AOA do Tier 1
        is_valid, msg, _ = AMLEngine.check_tier_limits(self.user_basic, Decimal("150000.00"))
        assert is_valid is False
        assert "excede o limite máximo permitido por operação" in msg

    def test_tier_2_verified_higher_limits(self):
        # 1.500.000 AOA é permitido no Tier 2 (máx 2.000.000 AOA)
        is_valid, _, _ = AMLEngine.check_tier_limits(self.user_verified, Decimal("1500000.00"))
        assert is_valid is True

        # 3.000.000 AOA excede o limite por operação de 2.000.000 AOA
        is_valid, msg, _ = AMLEngine.check_tier_limits(self.user_verified, Decimal("3000000.00"))
        assert is_valid is False
        assert "excede o limite máximo" in msg

    def test_evaluate_risk_unverified_generates_sar(self):
        result = AMLEngine.evaluate_transaction_risk(
            user=self.user_unverified,
            amount_aoa=Decimal("50000.00"),
            currency_code="AOA"
        )
        assert result.is_blocked is True
        assert "TIER_LIMIT_EXCEEDED" in result.rules_triggered
        assert len(result.reports_created) == 1
        assert result.reports_created[0].rule_code == "TIER_LIMIT_EXCEEDED"
        assert result.reports_created[0].user == self.user_unverified

    def test_evaluate_risk_large_value_alert_lvtr(self):
        # Transação de 1.200.000 AOA para Tier 2 (permitida, mas gera alerta LVTR >= 1M)
        result = AMLEngine.evaluate_transaction_risk(
            user=self.user_verified,
            amount_aoa=Decimal("1200000.00"),
            currency_code="AOA"
        )
        assert result.is_blocked is False
        assert "LARGE_VALUE_ALERT" in result.rules_triggered
        assert any(r.rule_code == "LARGE_VALUE_ALERT" for r in result.reports_created)

    def test_evaluate_risk_structuring_smurfing(self):
        # Cria 2 SARs prévios de smurfing para simular padrão repetido
        for _ in range(2):
            SuspiciousActivityReport.objects.create(
                user=self.user_basic,
                rule_code="STRUCTURING_SMURFING",
                severity="HIGH",
                amount_aoa=Decimal("95000.00"),
                status="PENDING_REVIEW"
            )

        # 3ª transação próxima ao limite de 100.000 (95.000 >= 80% de 100k)
        result = AMLEngine.evaluate_transaction_risk(
            user=self.user_basic,
            amount_aoa=Decimal("95000.00"),
            currency_code="AOA"
        )
        assert "STRUCTURING_SMURFING" in result.rules_triggered
        assert any(r.rule_code == "STRUCTURING_SMURFING" for r in result.reports_created)

    def test_api_get_my_kyc_limits(self):
        self.client.force_authenticate(user=self.user_verified)
        response = self.client.get("/api/compliance/limits/me/")
        assert response.status_code == status.HTTP_200_OK
        data = response.data["data"]
        assert data["tier"] == "TIER_2_VERIFIED"
        assert data["max_per_operation_aoa"] == float(TIER_LIMITS["TIER_2_VERIFIED"]["max_per_operation_aoa"])
        assert data["max_daily_aoa"] == float(TIER_LIMITS["TIER_2_VERIFIED"]["max_daily_aoa"])
        assert data["is_monetary_access_allowed"] is True

    def test_api_compliance_reports_list_admin_only(self):
        # Usuário normal não tem acesso
        self.client.force_authenticate(user=self.user_verified)
        res_forbidden = self.client.get("/api/compliance/reports/")
        assert res_forbidden.status_code == status.HTTP_403_FORBIDDEN

        # Administrador tem acesso total
        self.client.force_authenticate(user=self.user_admin)
        res_ok = self.client.get("/api/compliance/reports/")
        assert res_ok.status_code == status.HTTP_200_OK
        assert "data" in res_ok.data

    def test_api_resolve_sar_report_escalate_uif(self):
        sar = SuspiciousActivityReport.objects.create(
            user=self.user_basic,
            rule_code="LARGE_VALUE_ALERT",
            severity="HIGH",
            amount_aoa=Decimal("2500000.00"),
            status="PENDING_REVIEW"
        )

        self.client.force_authenticate(user=self.user_admin)
        payload = {
            "action": "ESCALATE_UIF",
            "notes": "Reportado formalmente à Unidade de Informação Financeira conforme Lei 05/20."
        }
        res = self.client.post(f"/api/compliance/reports/{sar.id}/resolve/", payload, format="json")
        assert res.status_code == status.HTTP_200_OK
        
        sar.refresh_from_db()
        assert sar.status == "ESCALATED_TO_UIF"
        assert sar.reported_to_uif_at is not None
        assert sar.resolved_by == self.user_admin
        assert "Unidade de Informação Financeira" in sar.resolution_notes
