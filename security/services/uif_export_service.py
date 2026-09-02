"""
Exportador Oficial de Comunicações de Operações Suspeitas (SAR / DOS) para a UIF Angola.
KwanzaConnect API — Conformidade com a Lei n.º 05/20 Art. 19, 20 e 38 (PCBC/FT).
"""

import json
import hashlib
from xml.etree.ElementTree import Element, SubElement, tostring
import defusedxml.ElementTree as defused_ET
from datetime import datetime
from django.utils import timezone
from typing import Dict, Any


from ..models import SuspiciousActivityReport
from security.masking import mask_doc_number, mask_email, mask_phone



class UIFExportService:
    """
    Serviço de geração e exportação de Dossiês Formais de Comunicação de Atividade Suspeita
    para a Unidade de Informação Financeira (UIF) da República de Angola.
    """

    REPORTING_ENTITY = {
        'entity_name': 'KwanzaConnect P2P Exchange, Lda.',
        'entity_type': 'Plataforma de Troca de Moedas P2P (Sandbox Regulatório BNA)',
        'license_reference': 'BNA/LISPA/SANDBOX-2026',
        'country': 'Angola',
        'supervisory_body': 'Banco Nacional de Angola (BNA) & Unidade de Informação Financeira (UIF)',
    }

    @classmethod
    def generate_uif_payload(cls, sar: SuspiciousActivityReport) -> Dict[str, Any]:
        """
        Gera o dicionário estruturado do relatório SAR com todos os campos regulamentares.
        """
        user = sar.user
        profile = getattr(user, 'risk_profile', None)

        # Dados do Sujeito Suspeito
        suspect_data = {
            'user_id': str(user.id),
            'full_name': getattr(user, 'full_name', '') or getattr(user, 'name', '') or user.email,
            'email': mask_email(user.email),
            'phone': mask_phone(getattr(user, 'phone_number', '') or getattr(user, 'phone', '')),
            'kyc_tier': profile.risk_tier if profile else 'TIER_0_UNVERIFIED',
            'is_pep': profile.is_pep if profile else False,
            'is_sanctioned': profile.is_sanctioned if profile else False,
            'risk_score': sar.risk_score,
            'created_at': user.created_at.isoformat() if hasattr(user, 'created_at') else None,
        }

        # Detalhes da Ocorrência
        occurrence_data = {
            'report_id': str(sar.id),
            'rule_code': sar.rule_code,
            'severity': sar.severity,
            'amount_aoa': str(sar.amount_aoa),
            'currency': 'AOA',
            'status': sar.status,
            'detected_at': sar.created_at.isoformat(),
            'resolved_at': sar.resolved_at.isoformat() if sar.resolved_at else None,
            'reported_to_uif_at': sar.reported_to_uif_at.isoformat() if sar.reported_to_uif_at else timezone.now().isoformat(),
            'resolution_notes': sar.resolution_notes or "Dossiê encaminhado para averiguação da UIF.",
            'technical_details': sar.details,
            'related_offer_id': str(sar.related_offer_id) if sar.related_offer_id else None,
            'related_transaction_id': str(sar.related_transaction_id) if sar.related_transaction_id else None,
        }

        # Metadados Legais
        legal_metadata = {
            'legal_framework': 'Lei n.º 05/20 de 27 de Janeiro (PCBC/FT)',
            'articles_referenced': ['Artigo 19 (PEPs)', 'Artigo 20 (Sanções)', 'Artigo 38 (Conservação e Comunicação de Registos)'],
            'confidentiality_notice': 'DOCUMENTO CONFIDENCIAL BNA / UIF — SEGREDO PROFISSIONAL E FINANCEIRO OBRIGATÓRIO.',
            'generation_timestamp': timezone.now().isoformat(),
        }

        raw_document = {
            'reporting_entity': cls.REPORTING_ENTITY,
            'legal_framework': legal_metadata,
            'suspect_entity': suspect_data,
            'occurrence_details': occurrence_data,
        }

        # Assinatura Digital / Hash de Integridade SHA-256 do Dossiê
        doc_json_bytes = json.dumps(raw_document, sort_keys=True, default=str).encode('utf-8')
        integrity_hash = hashlib.sha256(doc_json_bytes).hexdigest()

        raw_document['integrity_seal'] = {
            'algorithm': 'SHA-256',
            'hash_digest': integrity_hash,
            'sealed_at': timezone.now().isoformat(),
        }

        return raw_document

    @classmethod
    def export_as_json(cls, sar: SuspiciousActivityReport) -> str:
        """Exporta o relatório formal em formato JSON formatado."""
        payload = cls.generate_uif_payload(sar)
        return json.dumps(payload, indent=2, ensure_ascii=False)

    @classmethod
    def export_as_xml(cls, sar: SuspiciousActivityReport) -> str:
        """Exporta o relatório formal no formato XML padronizado de comunicação à UIF."""
        payload = cls.generate_uif_payload(sar)

        root = Element("UIF_SuspiciousActivityReport", version="1.0", country="AO")

        def dict_to_xml(parent, data):
            for key, val in data.items():
                child = SubElement(parent, key)
                if isinstance(val, dict):
                    dict_to_xml(child, val)
                elif isinstance(val, list):
                    for item in val:
                        item_elem = SubElement(child, "item")
                        if isinstance(item, dict):
                            dict_to_xml(item_elem, item)
                        else:
                            item_elem.text = str(item)
                else:
                    child.text = str(val) if val is not None else ""

        dict_to_xml(root, payload)
        return tostring(root, encoding="utf-8", method="xml").decode("utf-8")

