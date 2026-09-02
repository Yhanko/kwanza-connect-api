from django.urls import path
from .controllers.compliance_views import (
    UserKYCLimitsView,
    SuspiciousActivityReportListView,
    ResolveSuspiciousActivityReportView,
    InfraSecurityStatusView,
    BCPDRPStatusView,
    TriggerBackupView,
    RunDRDrillView,
)

urlpatterns = [
    # Consultar limites do próprio utilizador (Tier KYC, saldo disponível, consumido)
    path('compliance/limits/me/', UserKYCLimitsView.as_view(), name='compliance-my-limits'),
    
    # Listagem de relatórios de atividades suspeitas (SAR/DOS) para administradores/compliance
    path('compliance/reports/', SuspiciousActivityReportListView.as_view(), name='compliance-reports-list'),
    
    # Resolver ou escalar relatório SAR para a UIF
    path('compliance/reports/<uuid:report_id>/resolve/', ResolveSuspiciousActivityReportView.as_view(), name='compliance-report-resolve'),

    # Auditoria de Infraestrutura e Redes Seguras (Sandbox BNA)
    path('compliance/infra-security/', InfraSecurityStatusView.as_view(), name='compliance-infra-security'),

    # Continuidade de Negócio e Recuperação de Desastres (BCP / DRP)
    path('compliance/bcp-drp/', BCPDRPStatusView.as_view(), name='compliance-bcp-drp-status'),
    path('compliance/bcp-drp/trigger-backup/', TriggerBackupView.as_view(), name='compliance-bcp-drp-trigger-backup'),
    path('compliance/bcp-drp/run-drill/', RunDRDrillView.as_view(), name='compliance-bcp-drp-run-drill'),
]


