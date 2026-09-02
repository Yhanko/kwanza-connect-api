from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework import status
from security.models import CyberIncidentReport
from security.services.incident_reporting import CyberIncidentService

User = get_user_model()


class TestCyberIncidentManagement(TestCase):

    def setUp(self):
        self.client = APIClient()
        self.admin_user = User.objects.create_superuser(
            email='ciso@kwanzaconnect.ao',
            password='AdminPassword123!',
            full_name='CISO Admin'
        )
        self.client.force_authenticate(user=self.admin_user)

    def test_create_cyber_incident_service(self):
        incident = CyberIncidentService.create_incident(
            title='Tentativa de Ataque DDoS L7 na Rota de Cotações',
            incident_type='DDOS_ATTACK',
            severity='HIGH',
            impact_summary='Pico de 10.000 req/s mitigado pelo WAF Nginx.',
            remediation_actions='Rate limiting ativado e IPs atacantes bloqueados no firewall.',
            reported_by=self.admin_user
        )
        assert incident.incident_number.startswith('BNA-INC-')
        assert incident.status == 'DETECTED'
        assert incident.severity == 'HIGH'

    def test_generate_bna_notification_dossier(self):
        incident = CyberIncidentService.create_incident(
            title='Tentativa de Credential Stuffing',
            incident_type='BRUTE_FORCE_BURST',
            severity='MEDIUM',
            impact_summary='150 tentativas de login com senhas vazadas.',
            remediation_actions='Bloqueio por Argon2 lockout e IP throttle.',
            reported_by=self.admin_user
        )

        dossier = CyberIncidentService.generate_bna_notification_dossier(incident)
        header = dossier['bna_notification_header']
        assert header['protocol_number'] == incident.incident_number
        assert header['is_24h_deadline_compliant'] is True
        assert len(header['integrity_sha256']) == 64

    def test_api_cyber_incident_endpoints(self):
        # 1. POST criar incidente
        create_url = '/api/compliance/incidents/'
        payload = {
            'title': 'Indisponibilidade Parcial de Rede',
            'incident_type': 'SYSTEM_OUTAGE',
            'severity': 'MEDIUM',
            'impact_summary': 'Latência elevada de 2 minutos durante failover.',
            'remediation_actions': 'Reinicialização dos nós de cache Redis.'
        }
        res_create = self.client.post(create_url, payload, format='json')
        assert res_create.status_code == status.HTTP_201_CREATED
        incident_id = res_create.data['data']['id']

        # 2. GET listar incidentes
        res_list = self.client.get(create_url)
        assert res_list.status_code == status.HTTP_200_OK
        assert len(res_list.data['data']) >= 1

        # 3. GET exportar dossiê BNA
        export_url = f"/api/compliance/incidents/{incident_id}/export-bna/"
        res_export = self.client.get(export_url)
        assert res_export.status_code == status.HTTP_200_OK
        assert res_export.data['data']['bna_notification_header']['protocol_number'] is not None

        # 4. POST registrar protocolo de notificação ao BNA
        notify_url = f"/api/compliance/incidents/{incident_id}/notify-bna/"
        res_notify = self.client.post(notify_url, {'protocol_number': 'BNA-OFFICIAL-2026-9988', 'notes': 'Enviado por e-mail formal ao LISPA'}, format='json')
        assert res_notify.status_code == status.HTTP_200_OK
        assert res_notify.data['data']['bna_protocol_number'] == 'BNA-OFFICIAL-2026-9988'
