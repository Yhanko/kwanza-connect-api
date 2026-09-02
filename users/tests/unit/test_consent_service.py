from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework import status
from users.services.consent_service import DataPrivacyConsentService
from users.models import DataPrivacyConsent

User = get_user_model()


class TestDataPrivacyConsent(TestCase):

    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            email='consent_user@kwanzaconnect.ao',
            password='Password123!',
            full_name='Consent User',
            is_active=True
        )
        self.client.force_authenticate(user=self.user)

    def test_record_consent_service(self):
        consent = DataPrivacyConsentService.record_consent(
            user=self.user,
            ip_address='197.149.200.5',
            user_agent='Mozilla/5.0 TestBrowser'
        )
        assert consent.is_active is True
        assert consent.terms_version == 'v1.2-sandbox-bna'
        assert consent.privacy_policy_version == 'v1.2-apd-lei2211'
        assert len(consent.terms_content_hash) == 64

        status_info = DataPrivacyConsentService.get_user_consent_status(self.user)
        assert status_info['has_consent'] is True
        assert status_info['is_current'] is True

    def test_api_consent_endpoints(self):
        # 1. GET status sem consentimento inicial
        res_get1 = self.client.get('/api/users/consent/me/')
        assert res_get1.status_code == status.HTTP_200_OK
        assert res_get1.data['data']['has_consent'] is False

        # 2. POST registrar consentimento
        res_post = self.client.post('/api/users/consent/', {
            'terms_version': 'v1.2-sandbox-bna',
            'privacy_policy_version': 'v1.2-apd-lei2211'
        }, format='json')
        assert res_post.status_code == status.HTTP_200_OK
        assert res_post.data['data']['has_consent'] is True
        assert res_post.data['data']['is_current'] is True

        # 3. GET status após consentimento
        res_get2 = self.client.get('/api/users/consent/me/')
        assert res_get2.status_code == status.HTTP_200_OK
        assert res_get2.data['data']['has_consent'] is True
