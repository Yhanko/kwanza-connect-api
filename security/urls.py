from django.urls import path
from .controllers.compliance_views import (
    UserKYCLimitsView,
    SuspiciousActivityReportListView,
    ResolveSuspiciousActivityReportView,
    InfraSecurityStatusView,
    BCPDRPStatusView,
    TriggerBackupView,
    RunDRDrillView,
    VulnerabilityScanView,
    TriggerVulnerabilityScanView,
    ValidateAngolanIBANView,
    ExportUIFSARReportView,
    AuditChainIntegrityView,
    CyberIncidentListView,
    ExportCyberIncidentBNAView,
    NotifyCyberIncidentBNAView,
)


urlpatterns = [
    # Consultar limites do próprio utilizador (Tier KYC, saldo disponível, consumido)
    path('compliance/limits/me/', UserKYCLimitsView.as_view(), name='compliance-my-limits'),
    
    # Listagem de relatórios de atividades suspeitas (SAR/DOS) para administradores/compliance
    path('compliance/reports/', SuspiciousActivityReportListView.as_view(), name='compliance-reports-list'),
    
    # Resolver ou escalar relatório SAR para a UIF
    path('compliance/reports/<uuid:report_id>/resolve/', ResolveSuspiciousActivityReportView.as_view(), name='compliance-report-resolve'),

    # Exportar formalmente relatório SAR para envio à UIF Angola (JSON / XML)
    path('compliance/reports/<uuid:report_id>/export-uif/', ExportUIFSARReportView.as_view(), name='compliance-report-export-uif'),

    # Validação oficial de IBAN angolano (AO06 - ISO 7064 MOD 97-10 e catálogo BNA/EMIS)
    path('compliance/validate-iban/', ValidateAngolanIBANView.as_view(), name='compliance-validate-iban'),

    # Ateste de Integridade Criptográfica da Trilha de Auditoria (Lei n.º 05/20 Art. 38)
    path('compliance/audit-chain/verify/', AuditChainIntegrityView.as_view(), name='compliance-audit-chain-verify'),

    # Auditoria de Infraestrutura e Redes Seguras (Sandbox BNA)
    path('compliance/infra-security/', InfraSecurityStatusView.as_view(), name='compliance-infra-security'),

    # Continuidade de Negócio e Recuperação de Desastres (BCP / DRP)
    path('compliance/bcp-drp/', BCPDRPStatusView.as_view(), name='compliance-bcp-drp-status'),
    path('compliance/bcp-drp/trigger-backup/', TriggerBackupView.as_view(), name='compliance-bcp-drp-trigger-backup'),
    path('compliance/bcp-drp/run-drill/', RunDRDrillView.as_view(), name='compliance-bcp-drp-run-drill'),

    # Gestão de Vulnerabilidades, SAST e OWASP Top 10 API Security
    path('compliance/vulnerabilities/', VulnerabilityScanView.as_view(), name='compliance-vulnerabilities-status'),
    path('compliance/vulnerabilities/scan/', TriggerVulnerabilityScanView.as_view(), name='compliance-vulnerabilities-trigger-scan'),

    # Gestão de Incidentes de Cibersegurança e Notificação ao BNA (Prazo 24h)
    path('compliance/incidents/', CyberIncidentListView.as_view(), name='compliance-incidents-list'),
    path('compliance/incidents/<uuid:incident_id>/export-bna/', ExportCyberIncidentBNAView.as_view(), name='compliance-incidents-export-bna'),
    path('compliance/incidents/<uuid:incident_id>/notify-bna/', NotifyCyberIncidentBNAView.as_view(), name='compliance-incidents-notify-bna'),
]





