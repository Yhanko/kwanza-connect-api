"""
Testes Unitários e de Integração para BCP / DRP (Continuidade de Negócio e Recuperação de Desastres).
KwanzaConnect API — Sandbox BNA.
"""

import os
import pytest
from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework import status

from security.models import DatabaseBackupLog
from security.services.backup_service import BackupService, RPO_TARGET_MINUTES, RTO_TARGET_MINUTES

User = get_user_model()


class TestBCPDisasterRecovery(TestCase):

    def setUp(self):
        self.admin = User.objects.create_superuser(
            email="bcp_admin@kwanzaconnect.ao",
            password="StrongPassword2026!",
            full_name="BCP DRP Admin"
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.admin)

    def test_create_database_backup_creates_valid_encrypted_file(self):
        backup_log = BackupService.create_database_backup(triggered_by=self.admin)

        assert backup_log.status == 'SUCCESS'
        assert backup_log.file_size_bytes > 0
        assert len(backup_log.sha256_checksum) == 64
        assert os.path.exists(backup_log.storage_location)
        assert backup_log.encrypted_with == 'AES-256-Fernet'

        # Valida integridade
        is_valid, msg = BackupService.verify_backup_integrity(backup_log)
        assert is_valid is True
        assert "Integridade confirmada" in msg

    def test_verify_backup_integrity_detects_tampered_file(self):
        backup_log = BackupService.create_database_backup()
        filepath = backup_log.storage_location

        # Adulterando o ficheiro intencionalmente
        with open(filepath, 'wb') as f:
            f.write(b"TAMPERED_MALICIOUS_BYTES_12345")

        is_valid, msg = BackupService.verify_backup_integrity(backup_log)
        assert is_valid is False
        assert "Violação de integridade" in msg or "Falha" in msg

    def test_run_disaster_recovery_drill_measures_rto_successfully(self):
        success, rto_seconds, notes = BackupService.run_disaster_recovery_drill()

        assert success is True
        assert rto_seconds > 0.0
        assert rto_seconds < (RTO_TARGET_MINUTES * 60)  # Menor que 30 minutos
        assert "DR Drill Aprovado" in notes

        latest_tested = DatabaseBackupLog.objects.filter(is_dr_tested=True).first()
        assert latest_tested is not None
        assert latest_tested.dr_test_rto_seconds == rto_seconds

    def test_get_bcp_drp_status_returns_complete_metrics(self):
        BackupService.create_database_backup()
        BackupService.run_disaster_recovery_drill()

        status_data = BackupService.get_bcp_drp_status()

        assert status_data['rpo_target_minutes'] == 15
        assert status_data['rto_target_minutes'] == 30
        assert status_data['rpo_status'] == 'OPTIMAL'
        assert status_data['current_rpo_minutes'] >= 0.0
        assert status_data['last_measured_rto_seconds'] > 0.0
        assert '6 Anos' in status_data['retention_policy']
        assert len(status_data['recent_backups']) >= 1

    def test_api_bcp_drp_status_endpoint(self):
        response = self.client.get('/api/compliance/bcp-drp/')
        assert response.status_code == status.HTTP_200_OK
        data = response.data['data']
        assert 'rpo_target_minutes' in data
        assert 'current_rpo_minutes' in data
        assert 'rto_target_minutes' in data

    def test_api_trigger_backup_endpoint(self):
        response = self.client.post('/api/compliance/bcp-drp/trigger-backup/')
        assert response.status_code == status.HTTP_201_CREATED
        data = response.data['data']
        assert 'filename' in data
        assert 'sha256_checksum' in data
        assert 'file_size_bytes' in data

    def test_api_run_dr_drill_endpoint(self):
        response = self.client.post('/api/compliance/bcp-drp/run-drill/')
        assert response.status_code == status.HTTP_200_OK
        data = response.data['data']
        assert data['is_success'] is True
        assert data['rto_seconds'] > 0.0
        assert data['rto_target_minutes'] == 30
