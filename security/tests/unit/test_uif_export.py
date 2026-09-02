"""
Testes Unitários para o Exportador Oficial de Relatórios SAR/DOS para a UIF Angola.
KwanzaConnect API — Lei n.º 05/20 Art. 19, 20 e 38.
"""

from decimal import Decimal
from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework import status

from security.models import SuspiciousActivityReport, UserRiskProfile
from security.services.uif_export_service import UIFExportService
from audit.services.chain_verifier import AuditChainVerifier
from audit.infra.models import AuditLog

User = get_user_model()


class TestUIFExportAndAuditChain(TestCase):

    def setUp(self):
        self.admin = User.objects.create_superuser(
            email="uif_officer@kwanzaconnect.ao",
            password="StrongPassword2026!",
            full_name="Compliance Officer UIF"
        )
        self.suspect = User.objects.create_user(
            email="suspect_smurfer@kwanzaconnect.ao",
            password="StrongPassword2026!",
            full_name="Suspect John Doe"
        )
        self.profile = UserRiskProfile.objects.create(
            user=self.suspect,
            risk_tier='TIER_1_BASIC',
            is_pep=True,
            risk_score=75
        )
        self.sar = SuspiciousActivityReport.objects.create(
            user=self.suspect,
            rule_code='STRUCTURING_SMURFING',
            severity='HIGH',
            risk_score=85,
            amount_aoa=Decimal('99000.00'),
            status='UNDER_INVESTIGATION',
            details={'reason': 'Tentativas sucessivas de fracionamento de valores no limite.'}
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.admin)

    def test_generate_uif_payload(self):
        payload = UIFExportService.generate_uif_payload(self.sar)
        assert 'reporting_entity' in payload
        assert 'suspect_entity' in payload
        assert 'occurrence_details' in payload
        assert 'integrity_seal' in payload
        assert payload['suspect_entity']['is_pep'] is True
        assert payload['integrity_seal']['algorithm'] == 'SHA-256'
        assert len(payload['integrity_seal']['hash_digest']) == 64

    def test_export_as_json_and_xml(self):
        json_str = UIFExportService.export_as_json(self.sar)
        assert "KwanzaConnect P2P Exchange" in json_str
        assert "STRUCTURING_SMURFING" in json_str

        xml_str = UIFExportService.export_as_xml(self.sar)
        assert "<UIF_SuspiciousActivityReport" in xml_str
        assert "<rule_code>STRUCTURING_SMURFING</rule_code>" in xml_str

    def test_api_export_uif_json_endpoint(self):
        url = f"/api/compliance/reports/{self.sar.id}/export-uif/?format=json"
        response = self.client.get(url)
        assert response.status_code == status.HTTP_200_OK
        data = response.data['data']
        assert data['occurrence_details']['rule_code'] == 'STRUCTURING_SMURFING'

    def test_api_export_uif_xml_endpoint(self):
        url = f"/api/compliance/reports/{self.sar.id}/export-uif/?export_type=xml"
        response = self.client.get(url)
        assert response.status_code == status.HTTP_200_OK
        assert 'application/xml' in response['Content-Type']
        assert "attachment" in response['Content-Disposition']


    def test_audit_chain_verifier(self):
        # Cria logs de auditoria de teste
        AuditLog.objects.create(
            actor_email="admin@kwanzaconnect.ao",
            action="USER_LOGIN",
            resource="USER",
            status="SUCCESS",
            severity="INFO"
        )
        AuditLog.objects.create(
            actor_email="admin@kwanzaconnect.ao",
            action="KYC_VERIFY",
            resource="KYC_DOCUMENT",
            status="SUCCESS",
            severity="INFO"
        )

        report = AuditChainVerifier.verify_audit_trail_integrity()
        assert report['status'] == 'VERIFIED'
        assert report['is_chain_intact'] is True
        assert report['total_records_verified'] >= 2
        assert len(report['chain_root_hash']) == 64

    def test_api_audit_chain_verify_endpoint(self):
        response = self.client.get('/api/compliance/audit-chain/verify/')
        assert response.status_code == status.HTTP_200_OK
        assert response.data['data']['is_chain_intact'] is True
