from django.test import TestCase, override_settings
from django.core.checks import run_checks, Tags
from django.core.management import call_command
from io import StringIO

from security.checks import check_infrastructure_security


class TestInfrastructureSecurityChecks(TestCase):

    @override_settings(
        SECRET_KEY="a-very-long-strong-production-secret-key-32-chars!",
        CORS_ALLOW_ALL_ORIGINS=False
    )
    def test_check_passes_on_valid_environment(self):
        issues = check_infrastructure_security(None)
        errors = [i for i in issues if i.is_serious()]
        assert len(errors) == 0

    @override_settings(DEBUG=False, SECRET_KEY="short", CORS_ALLOW_ALL_ORIGINS=False)
    def test_check_fails_on_short_secret_key_in_production(self):
        issues = check_infrastructure_security(None)
        error_ids = [i.id for i in issues if i.is_serious()]
        assert "security.E001" in error_ids

    @override_settings(
        DEBUG=False,
        SECRET_KEY="django-insecure-abcdefghijklmnopqrstuvwxyz1234567890",
        CORS_ALLOW_ALL_ORIGINS=False
    )
    def test_check_fails_on_django_insecure_key_in_production(self):
        issues = check_infrastructure_security(None)
        error_ids = [i.id for i in issues if i.is_serious()]
        assert "security.E002" in error_ids

    @override_settings(
        SECRET_KEY="a-very-long-strong-production-secret-key-32-chars!",
        CORS_ALLOW_ALL_ORIGINS=False,
        PASSWORD_HASHERS=['django.contrib.auth.hashers.PBKDF2PasswordHasher']
    )
    def test_check_warns_on_non_argon2_primary_hasher(self):
        issues = check_infrastructure_security(None)
        warning_ids = [i.id for i in issues if not i.is_serious()]
        assert "security.W001" in warning_ids

    @override_settings(
        SECRET_KEY="a-very-long-strong-production-secret-key-32-chars!",
        CORS_ALLOW_ALL_ORIGINS=False,
        MIDDLEWARE=[]
    )
    def test_check_fails_on_missing_financial_headers_middleware(self):
        issues = check_infrastructure_security(None)
        error_ids = [i.id for i in issues if i.is_serious()]
        assert "security.E004" in error_ids

    @override_settings(
        SECRET_KEY="a-very-long-strong-production-secret-key-32-chars!",
        CORS_ALLOW_ALL_ORIGINS=False
    )
    def test_management_command_check_infra_security_runs_successfully(self):
        out = StringIO()
        call_command('check_infra_security', stdout=out)
        output = out.getvalue()
        assert "AUDITORIA" in output
        assert "INFRAESTRUTURA APROVADA" in output

    @override_settings(
        SECRET_KEY="a-very-long-strong-production-secret-key-32-chars!",
        CORS_ALLOW_ALL_ORIGINS=False
    )
    def test_api_infra_security_status_endpoint(self):
        from rest_framework.test import APIClient
        from rest_framework import status
        from django.contrib.auth import get_user_model
        User = get_user_model()
        admin_user = User.objects.create_superuser(
            email="infra_compliance@kwanzaconnect.ao",
            password="StrongPassword2026!",
            full_name="Infra Compliance Admin"
        )
        client = APIClient()
        client.force_authenticate(user=admin_user)
        response = client.get('/api/compliance/infra-security/')
        assert response.status_code == status.HTTP_200_OK
        data = response.data['data']
        assert data['overall_status'] in ['COMPLIANT', 'NON_COMPLIANT']
        assert data['summary']['total_checks'] == 5
        assert len(data['checks']) == 5
        check_ids = [c['id'] for c in data['checks']]
        assert 'encryption_rest' in check_ids
        assert 'password_hashing' in check_ids
        assert 'security_headers' in check_ids
        assert 'network_waf' in check_ids


