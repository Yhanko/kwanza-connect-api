"""
Módulo de Gestão de Consentimento e Protecção de Dados Pessoais (Lei n.º 22/11 - APD Angola).
Objetivo: Garantir a comprovação inequívoca e auditável do consentimento livre, informado e
específico dos utilizadores para o tratamento de dados cadastrais e financeiros na KwanzaConnect.
"""
import hashlib
from typing import Dict, Any, Optional
from django.utils import timezone
from users.models import DataPrivacyConsent


class DataPrivacyConsentService:
    """
    Serviço para registro, validação e auditoria de consentimento de privacidade conforme a Lei n.º 22/11.
    """
    CURRENT_TERMS_VERSION = 'v1.2-sandbox-bna'
    CURRENT_PRIVACY_POLICY_VERSION = 'v1.2-apd-lei2211'
    STANDARD_TERMS_TEXT = (
        "Termos de Uso e Política de Privacidade da KwanzaConnect — Participação no Sandbox Regulatório "
        "do Banco Nacional de Angola (BNA / LISPA), autorização de validação KYC conforme a Lei n.º 05/20 "
        "e tratamento de dados nos termos da Lei n.º 22/11 de Protecção de Dados Pessoais de Angola."
    )

    @classmethod
    def compute_terms_hash(cls, terms_content: Optional[str] = None) -> str:
        text = terms_content or cls.STANDARD_TERMS_TEXT
        return hashlib.sha256(text.encode('utf-8')).hexdigest()

    @classmethod
    def record_consent(
        cls,
        user,
        ip_address: Optional[str] = None,
        user_agent: str = '',
        terms_version: Optional[str] = None,
        privacy_policy_version: Optional[str] = None,
        terms_content: Optional[str] = None
    ) -> DataPrivacyConsent:
        """
        Registra ou atualiza o consentimento formal e imutável do utilizador.
        """
        terms_ver = terms_version or cls.CURRENT_TERMS_VERSION
        privacy_ver = privacy_policy_version or cls.CURRENT_PRIVACY_POLICY_VERSION
        terms_hash = cls.compute_terms_hash(terms_content)

        # Desativa consentimentos antigos
        DataPrivacyConsent.objects.filter(user=user, is_active=True).update(
            is_active=False,
            revoked_at=timezone.now()
        )

        consent = DataPrivacyConsent.objects.create(
            user=user,
            terms_version=terms_ver,
            privacy_policy_version=privacy_ver,
            terms_content_hash=terms_hash,
            ip_address=ip_address,
            user_agent=user_agent or 'Unknown',
            is_active=True,
            consented_at=timezone.now()
        )
        return consent

    @classmethod
    def get_user_consent_status(cls, user) -> Dict[str, Any]:
        """
        Retorna o status de consentimento do utilizador.
        """
        active_consent = DataPrivacyConsent.objects.filter(user=user, is_active=True).first()
        if not active_consent:
            return {
                'has_consent': False,
                'is_current': False,
                'terms_version': None,
                'privacy_policy_version': None,
                'consented_at': None,
                'legal_framework': 'Lei n.º 22/11 (Protecção de Dados Pessoais - APD Angola)'
            }

        is_current = (
            active_consent.terms_version == cls.CURRENT_TERMS_VERSION and
            active_consent.privacy_policy_version == cls.CURRENT_PRIVACY_POLICY_VERSION
        )

        return {
            'has_consent': True,
            'is_current': is_current,
            'terms_version': active_consent.terms_version,
            'privacy_policy_version': active_consent.privacy_policy_version,
            'terms_content_hash': active_consent.terms_content_hash,
            'consented_at': active_consent.consented_at.isoformat(),
            'ip_address': active_consent.ip_address,
            'legal_framework': 'Lei n.º 22/11 (Protecção de Dados Pessoais - APD Angola)'
        }
