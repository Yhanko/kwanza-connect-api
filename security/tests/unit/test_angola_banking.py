"""
Testes Unitários para Validador de IBANs Angolanos (AO06 - ISO 7064 MOD 97-10).
KwanzaConnect API — Sandbox BNA.
"""

from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework import status

from security.services.angola_banking import AngolaBankingValidator

User = get_user_model()


class TestAngolaBankingValidator(TestCase):

    def setUp(self):
        self.user = User.objects.create_user(
            email="iban_tester@kwanzaconnect.ao",
            password="StrongPassword2026!",
            full_name="IBAN Test User"
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    def test_valid_bai_iban(self):
        valid_bai_iban = AngolaBankingValidator.generate_sample_iban(bank_code='0040', account_part='000012345678901')

        is_valid, bank_data, error = AngolaBankingValidator.validate_iban(valid_bai_iban)
        assert is_valid is True
        assert bank_data is not None
        assert bank_data['bank_code'] == '0040'
        assert bank_data['bank_short_name'] == 'BAI'
        assert bank_data['bank_name'] == 'Banco Angolano de Investimentos'
        assert error is None

    def test_valid_bfa_iban_with_spaces_and_dots(self):
        valid_bfa_clean = AngolaBankingValidator.generate_sample_iban(bank_code='0006', account_part='000098765432100')
        raw_bfa = f"{valid_bfa_clean[:4]}.{valid_bfa_clean[4:8]}.{valid_bfa_clean[8:12]}.{valid_bfa_clean[12:16]}.{valid_bfa_clean[16:]}"

        is_valid, bank_data, error = AngolaBankingValidator.validate_iban(raw_bfa)
        assert is_valid is True
        assert bank_data['bank_code'] == '0006'
        assert bank_data['bank_short_name'] == 'BFA'

    def test_invalid_length(self):
        is_valid, bank_data, error = AngolaBankingValidator.validate_iban("AO060040123")
        assert is_valid is False
        assert "25 caracteres" in error

    def test_invalid_country_prefix(self):
        is_valid, bank_data, error = AngolaBankingValidator.validate_iban("PT50004000001234567890124")
        assert is_valid is False
        assert "AO06" in error

    def test_invalid_mod97_checksum(self):
        # Troca os últimos 2 dígitos para forçar falha no MOD 97
        invalid_iban = "AO06004000001234567890199"
        is_valid, bank_data, error = AngolaBankingValidator.validate_iban(invalid_iban)
        assert is_valid is False
        assert "MOD 97" in error

    def test_api_validate_iban_endpoint(self):
        valid_atlantico_iban = AngolaBankingValidator.generate_sample_iban(bank_code='0055', account_part='000011223344556')

        response = self.client.post('/api/compliance/validate-iban/', {
            'iban': valid_atlantico_iban
        }, format='json')

        assert response.status_code == status.HTTP_200_OK
        data = response.data['data']
        assert data['bank_code'] == '0055'
        assert 'Atlântico' in data['bank_name']

