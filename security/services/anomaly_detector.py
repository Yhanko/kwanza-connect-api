"""
Módulo de Detecção de Anomalias de Acesso & Viagem Impossível (Impossible Travel).
Objetivo: Proteger contas financeiras contra sequestro de sessão, credential stuffing
e acessos não autorizados a partir de locais/dispositivos anômalos (Diretrizes BNA & OWASP).
"""
import hashlib
from datetime import timedelta
from typing import Dict, Any, List, Tuple
from django.utils import timezone
from django.conf import settings
from users.models import UserLoginHistory
from audit.infra.models import AuditLog


class LoginAnomalyDetector:
    """
    Analisa o histórico recente de logins do utilizador para identificar padrões suspeitos:
    1. IMPOSSIBLE_TRAVEL: Mudança repentina de localização geográfica/país em intervalo temporal inviável.
    2. SUSPICIOUS_IP_HOP: Mudança drástica de endereço IP/provedor em menos de 10 minutos.
    3. UNRECOGNIZED_DEVICE: Primeiro acesso a partir de um novo dispositivo/User-Agent.
    """

    @classmethod
    def compute_device_fingerprint(cls, user_agent: str, ip_address: str) -> str:
        raw = f"{user_agent}|{ip_address.split('.')[0] if '.' in ip_address else ip_address}"
        return hashlib.sha256(raw.encode('utf-8')).hexdigest()[:32]

    @classmethod
    def analyze_and_record_login(
        cls,
        user,
        ip_address: str,
        user_agent: str = '',
        country_code: str = 'AO',
        city: str = ''
    ) -> Tuple[bool, List[str], UserLoginHistory]:
        """
        Analisa a nova tentativa de login e armazena o histórico de acessos.
        Retorna (is_anomalous, anomaly_reasons, login_record).
        """
        now = timezone.now()
        device_fp = cls.compute_device_fingerprint(user_agent, ip_address)
        reasons: List[str] = []

        # Busca o último login bem-sucedido
        last_login = UserLoginHistory.objects.filter(user=user).order_by('-login_at').first()

        if last_login:
            time_diff = now - last_login.login_at

            # 1. Checagem de Impossible Travel (País diferente em menos de 3 horas)
            if last_login.country_code != country_code and time_diff < timedelta(hours=3):
                reasons.append('IMPOSSIBLE_TRAVEL')

            # 2. Checagem de Salto Rápido de IP (IP diferente em menos de 5 minutos)
            if last_login.ip_address != ip_address and time_diff < timedelta(minutes=5):
                reasons.append('SUSPICIOUS_IP_HOP')

            # 3. Dispositivo Desconhecido (se nunca usou esse device_fingerprint antes)
            known_devices = UserLoginHistory.objects.filter(
                user=user,
                device_fingerprint=device_fp
            ).exists()
            if not known_devices:
                reasons.append('NEW_DEVICE_DETECTED')

        is_anomalous = len(reasons) > 0

        # Cria o registo de histórico
        record = UserLoginHistory.objects.create(
            user=user,
            ip_address=ip_address or '127.0.0.1',
            user_agent=user_agent or 'Unknown',
            device_fingerprint=device_fp,
            country_code=country_code or 'AO',
            city=city or '',
            is_anomalous=is_anomalous,
            anomaly_reasons=reasons,
            login_at=now
        )

        # Se houver anomalia, regista evento no AuditLog de Segurança
        if is_anomalous:
            AuditLog.objects.create(
                user=user,
                actor_email=user.email,
                action='SECURITY_LOGIN_ANOMALY',
                ip_address=ip_address,
                user_agent=user_agent,
                status='WARNING',
                metadata={
                    'anomaly_reasons': reasons,
                    'current_ip': ip_address,
                    'previous_ip': last_login.ip_address if last_login else None,
                    'country': country_code,
                    'login_history_id': str(record.id)
                }
            )

        return is_anomalous, reasons, record
