"""
Módulo de Anonimização e Mascaramento de Dados Sensíveis (PII Masking)
KwanzaConnect API — Em conformidade com a Lei de Proteção de Dados e Sandbox BNA.

Funções utilitárias para mascarar documentos de identidade, números de telefone,
e-mails e higienizar metadados antes de persistir em logs de auditoria.
"""

from typing import Any, Dict, List, Union


SENSITIVE_KEYS = {
    'password', 'password1', 'password2', 'secret', 'token', 'access_token',
    'refresh_token', 'two_factor_secret', 'pin', 'bi', 'doc_number', 'phone',
    'iban', 'account_number', 'card_number', 'cvv', 'authorization', 'x-api-key',
    'front_image', 'back_image', 'pdf_file', 'selfie',
}


def mask_doc_number(doc: str) -> str:
    """
    Mascara um número de documento (BI / Passaporte).
    Exemplo: '002367037LA033' -> '00236*****033'
    """
    if not doc:
        return ""
    doc_str = str(doc).strip()
    length = len(doc_str)
    if length <= 6:
        return "*" * length
    prefix = doc_str[:5]
    suffix = doc_str[-3:]
    return f"{prefix}{'*' * (length - 8)}{suffix}"


def mask_phone(phone: str) -> str:
    """
    Mascara um número de telefone.
    Exemplo: '+244943558106' -> '+244 943***106'
    Exemplo: '943558106' -> '943***106'
    """
    if not phone:
        return ""
    phone_str = str(phone).strip()
    if phone_str.startswith('+244') and len(phone_str) >= 13:
        prefix = phone_str[:8] # '+244 943' approx
        suffix = phone_str[-3:]
        return f"{prefix}***{suffix}"
    if len(phone_str) == 9:
        return f"{phone_str[:3]}***{phone_str[-3:]}"
    if len(phone_str) > 4:
        return f"{phone_str[:2]}***{phone_str[-2:]}"
    return "***"


def mask_email(email: str) -> str:
    """
    Mascara um endereço de e-mail.
    Exemplo: 'utilizador@exemplo.com' -> 'u***r@exemplo.com'
    """
    if not email or '@' not in email:
        return "***"
    local, domain = email.split('@', 1)
    if len(local) <= 2:
        masked_local = f"{local[0]}*" if local else "*"
    else:
        masked_local = f"{local[0]}{'*' * (len(local) - 2)}{local[-1]}"
    return f"{masked_local}@{domain}"


def sanitize_log_metadata(data: Any) -> Any:
    """
    Sanitiza recursivamente dicionários e listas de metadados para auditoria/logs,
    substituindo valores de chaves sensíveis por versões mascaradas ou redacted.
    """
    if isinstance(data, dict):
        sanitized = {}
        for key, value in data.items():
            key_lower = str(key).lower()
            if any(s_key in key_lower for s_key in SENSITIVE_KEYS):
                if 'phone' in key_lower:
                    sanitized[key] = mask_phone(str(value))
                elif any(d_key in key_lower for d_key in ('doc', 'bi', 'passport')):
                    sanitized[key] = mask_doc_number(str(value))
                elif 'email' in key_lower:
                    sanitized[key] = mask_email(str(value))
                else:
                    sanitized[key] = "[REDACTED_SENSITIVE_DATA]"
            else:
                sanitized[key] = sanitize_log_metadata(value)
        return sanitized
    elif isinstance(data, list):
        return [sanitize_log_metadata(item) for item in data]
    return data
