from decimal import Decimal
from django.test import TestCase
from django.contrib.auth import get_user_model
from security.services.spread_monitor import BNASpreadMonitor
from security.services.aml_engine import AMLEngine
from security.models import SuspiciousActivityReport

User = get_user_model()


class TestBNASpreadMonitor(TestCase):

    def setUp(self):
        self.user = User.objects.create_user(
            email='trader@kwanzaconnect.ao',
            password='Password123!',
            full_name='Trader Teste',
            is_active=True,
            verification_status='approved'
        )

    def test_normal_spread_passes_without_warning(self):
        is_valid, is_warning, dev_pct, msg = BNASpreadMonitor.check_exchange_rate_spread(
            offered_rate=Decimal('980.00'),
            from_currency='USD',
            to_currency='AOA'
        )
        assert is_valid is True
        assert is_warning is False
        assert dev_pct < 10.0

    def test_moderate_spread_triggers_warning_sar(self):
        is_valid, is_warning, dev_pct, msg = BNASpreadMonitor.check_exchange_rate_spread(
            offered_rate=Decimal('1300.00'),
            from_currency='USD',
            to_currency='AOA'
        )
        assert is_valid is True
        assert is_warning is True
        assert dev_pct > 30.0

        result = AMLEngine.evaluate_transaction_risk(
            user=self.user,
            amount_aoa=Decimal('100000.00'),
            currency_code='USD',
            rate_snapshot=Decimal('1300.00')
        )
        assert result.is_blocked is False
        assert 'RATE_OUTLIER' in result.rules_triggered
        assert SuspiciousActivityReport.objects.filter(user=self.user, rule_code='RATE_OUTLIER').exists()

    def test_excessive_spread_is_blocked_immediately(self):
        is_valid, is_warning, dev_pct, msg = BNASpreadMonitor.check_exchange_rate_spread(
            offered_rate=Decimal('2000.00'),
            from_currency='USD',
            to_currency='AOA'
        )
        assert is_valid is False
        assert is_warning is True
        assert dev_pct > 60.0

        result = AMLEngine.evaluate_transaction_risk(
            user=self.user,
            amount_aoa=Decimal('100000.00'),
            currency_code='USD',
            rate_snapshot=Decimal('2000.00')
        )
        assert result.is_blocked is True
        assert 'RATE_OUTLIER' in result.rules_triggered
        sar = SuspiciousActivityReport.objects.filter(user=self.user, rule_code='RATE_OUTLIER', severity='CRITICAL').first()
        assert sar is not None
