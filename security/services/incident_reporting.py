"""
Módulo de Gestão e Notificação de Incidentes de Cibersegurança ao Banco Nacional de Angola (BNA).
Base Regulamentar: Aviso n.º 02/2021 e Instrutivo n.º 14/2020 do BNA (Governança de TI e Cibersegurança).
Exigência: Notificação obrigatória de incidentes classificados como Alto/Crítico ao Gabinete de
Cibersegurança do BNA e LISPA no prazo máximo de 24 horas após a detecção.
"""
import uuid
import hashlib
from datetime import timedelta
from typing import Dict, Any, List, Optional
from django.utils import timezone
from django.conf import settings
from security.models import CyberIncidentReport


class CyberIncidentService:
    """
    Serviço central de registro, triagem e elaboração de relatórios formais
    de notificação de incidentes cibernéticos ao BNA.
    """

    @classmethod
    def generate_incident_number(cls) -> str:
        """Gera protocolo padronizado: BNA-INC-YYYYMMDD-XXXX"""
        date_str = timezone.now().strftime('%Y%m%d')
        unique_suffix = uuid.uuid4().hex[:4].upper()
        return f"BNA-INC-{date_str}-{unique_suffix}"

    @classmethod
    def create_incident(
        cls,
        title: str,
        incident_type: str,
        severity: str,
        impact_summary: str,
        remediation_actions: str,
        reported_by=None,
        affected_systems: str = 'KwanzaConnect API / Infraestrutura',
        detected_at=None,
        root_cause: str = ''
    ) -> CyberIncidentReport:
        incident_number = cls.generate_incident_number()
        incident = CyberIncidentReport.objects.create(
            incident_number=incident_number,
            title=title,
            incident_type=incident_type,
            severity=severity,
            impact_summary=impact_summary,
            remediation_actions=remediation_actions,
            affected_systems=affected_systems,
            root_cause=root_cause,
            reported_by=reported_by,
            detected_at=detected_at or timezone.now(),
            status='DETECTED'
        )
        return incident

    @classmethod
    def generate_bna_notification_dossier(cls, incident: CyberIncidentReport) -> Dict[str, Any]:
        """
        Gera o dossiê formal de comunicação para o BNA (Gabinete de Cibersegurança / LISPA).
        """
        now = timezone.now()
        deadline_24h = incident.detected_at + timedelta(hours=24)
        is_deadline_met = now <= deadline_24h

        raw_content = f"{incident.incident_number}|{incident.incident_type}|{incident.severity}|{incident.detected_at.isoformat()}|{incident.impact_summary}"
        integrity_hash = hashlib.sha256(raw_content.encode('utf-8')).hexdigest()

        dossier = {
            'bna_notification_header': {
                'recipient': 'Banco Nacional de Angola — Gabinete de Cibersegurança & LISPA',
                'regulatory_framework': 'Aviso n.º 02/2021 e Instrutivo n.º 14/2020 do BNA',
                'reporting_entity': 'KwanzaConnect FinTech — Participante Sandbox Regulatório',
                'protocol_number': incident.incident_number,
                'submission_date': now.isoformat(),
                'notification_deadline_24h': deadline_24h.isoformat(),
                'is_24h_deadline_compliant': is_deadline_met,
                'integrity_sha256': integrity_hash
            },
            'incident_classification': {
                'title': incident.title,
                'incident_type': incident.incident_type,
                'incident_type_display': incident.get_incident_type_display(),
                'severity': incident.severity,
                'severity_display': incident.get_severity_display(),
                'current_status': incident.status,
                'current_status_display': incident.get_status_display(),
                'affected_systems': incident.affected_systems
            },
            'chronology': {
                'detected_at': incident.detected_at.isoformat(),
                'contained_at': incident.contained_at.isoformat() if incident.contained_at else None,
                'resolved_at': incident.resolved_at.isoformat() if incident.resolved_at else None,
                'bna_notified_at': incident.bna_notified_at.isoformat() if incident.bna_notified_at else None,
            },
            'technical_assessment': {
                'impact_summary': incident.impact_summary,
                'root_cause': incident.root_cause or 'Em processo de análise forense aprofundada.',
                'remediation_measures_applied': incident.remediation_actions,
            },
            'contact_point': {
                'focal_point_name': 'Romeu Cajamba',
                'role': 'Responsável de Tecnologia / CISO',
                'email': 'ciberseguranca@kwanzaconnect.ao',
                'emergency_phone': '+244 9XX XXX XXX'
            }
        }
        return dossier

    @classmethod
    def mark_as_reported_to_bna(
        cls,
        incident: CyberIncidentReport,
        protocol_number: str = '',
        notes: str = ''
    ) -> CyberIncidentReport:
        incident.status = 'REPORTED_TO_BNA'
        incident.bna_notified_at = timezone.now()
        incident.bna_protocol_number = protocol_number or f"BNA-ACK-{timezone.now().strftime('%Y%m%d%H%M%S')}"
        incident.bna_notification_notes = notes
        incident.save(update_fields=['status', 'bna_notified_at', 'bna_protocol_number', 'bna_notification_notes'])
        return incident
