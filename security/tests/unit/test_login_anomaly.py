from django.test import TestCase
from django.contrib.auth import get_user_model
from security.services.anomaly_detector import LoginAnomalyDetector
from users.models import UserLoginHistory
from audit.infra.models import AuditLog

User = get_user_model()


class TestLoginAnomalyDetector(TestCase):

    def setUp(self):
        self.user = User.objects.create_user(
            email='security_user@kwanzaconnect.ao',
            password='Password123!',
            full_name='Security User',
            is_active=True
        )

    def test_first_login_records_history_without_anomaly(self):
        is_anomalous, reasons, record = LoginAnomalyDetector.analyze_and_record_login(
            user=self.user,
            ip_address='197.149.200.10',
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
            country_code='AO',
            city='Luanda'
        )
        assert is_anomalous is False
        assert len(reasons) == 0
        assert record.country_code == 'AO'
        assert record.city == 'Luanda'
        assert UserLoginHistory.objects.filter(user=self.user).count() == 1

    def test_impossible_travel_detected_on_rapid_country_change(self):
        # 1. Primeiro login em Luanda
        LoginAnomalyDetector.analyze_and_record_login(
            user=self.user,
            ip_address='197.149.200.10',
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
            country_code='AO',
            city='Luanda'
        )

        # 2. Segundo login 5 minutos depois a partir de Portugal (PT)
        is_anomalous, reasons, record = LoginAnomalyDetector.analyze_and_record_login(
            user=self.user,
            ip_address='85.240.10.20',
            user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)',
            country_code='PT',
            city='Lisboa'
        )

        assert is_anomalous is True
        assert 'IMPOSSIBLE_TRAVEL' in reasons
        assert 'NEW_DEVICE_DETECTED' in reasons

        # Verifica se o AuditLog de anomalia foi registrado
        audit_entry = AuditLog.objects.filter(user=self.user, action='SECURITY_LOGIN_ANOMALY').first()
        assert audit_entry is not None
        assert 'IMPOSSIBLE_TRAVEL' in audit_entry.metadata['anomaly_reasons']
