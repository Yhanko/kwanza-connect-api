"""
Módulo de Criptografia e Proteção de Dados em Repouso (Data at Rest)
KwanzaConnect API — Em conformidade com as diretrizes de Cibersegurança do BNA e Lei n.º 05/20.

Implementa:
- Field-Level Encryption (FLE) com AES-256 (Fernet)
- Blind Indexing com HMAC-SHA256 (para buscas indexadas e garantia de unicidade sem expor dados em claro)
- Campos customizados de Modelo Django (EncryptedCharField, EncryptedTextField)
"""

import base64
import hmac
import hashlib
from typing import Optional
from django.db import models
from django.conf import settings
from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives import hashes


_ENCRYPTION_PREFIX = "enc::v1::"


def get_encryption_key() -> bytes:
    """
    Obtém a chave Fernet (32 bytes base64 url-safe).
    Se FIELD_ENCRYPTION_KEY estiver configurada nas settings, usa-a.
    Caso contrário, deriva deterministicamente uma chave segura a partir de SECRET_KEY usando HKDF-SHA256.
    """
    configured_key = getattr(settings, 'FIELD_ENCRYPTION_KEY', None)
    if configured_key:
        if isinstance(configured_key, str):
            return configured_key.encode('utf-8')
        return configured_key

    # Derivação segura via HKDF a partir da SECRET_KEY
    secret = getattr(settings, 'SECRET_KEY', 'default-secret-key-fallback').encode('utf-8')
    hkdf = HKDF(
        algorithm=hashes.SHA256(),
        length=32,
        salt=b'KwanzaConnect-FieldEncryption-Salt-v1',
        info=b'KwanzaConnect-Field-Encryption-Key',
    )
    derived_key = hkdf.derive(secret)
    return base64.urlsafe_b64encode(derived_key)


def get_blind_index_key() -> bytes:
    """
    Obtém a chave para geração de Blind Index (HMAC-SHA256).
    """
    secret = getattr(settings, 'SECRET_KEY', 'default-secret-key-fallback').encode('utf-8')
    hkdf = HKDF(
        algorithm=hashes.SHA256(),
        length=32,
        salt=b'KwanzaConnect-BlindIndex-Salt-v1',
        info=b'KwanzaConnect-Blind-Index-HMAC-Key',
    )
    return hkdf.derive(secret)


def get_fernet_instance() -> Fernet:
    """Retorna uma instância Fernet inicializada."""
    return Fernet(get_encryption_key())


def encrypt_value(plain_text: Optional[str]) -> Optional[str]:
    """
    Encripta um valor em texto claro usando AES-256 (Fernet).
    Retorna com o prefixo 'enc::v1::' para fácil identificação e versionamento.
    Se o valor já estiver encriptado ou for None/vazio, lida de forma idempotente.
    """
    if plain_text is None:
        return None
    if not isinstance(plain_text, str):
        plain_text = str(plain_text)
    if not plain_text:
        return ""
    if plain_text.startswith(_ENCRYPTION_PREFIX):
        return plain_text  # Já encriptado

    fernet = get_fernet_instance()
    encrypted_bytes = fernet.encrypt(plain_text.encode('utf-8'))
    return f"{_ENCRYPTION_PREFIX}{encrypted_bytes.decode('utf-8')}"


def decrypt_value(cipher_text: Optional[str]) -> Optional[str]:
    """
    Decripta um ciphertext encriptado com Fernet.
    Se o valor não tiver o prefixo de encriptação, assume que é legado/texto claro e retorna-o intacto.
    """
    if cipher_text is None:
        return None
    if not isinstance(cipher_text, str):
        return str(cipher_text)
    if not cipher_text:
        return ""
    if not cipher_text.startswith(_ENCRYPTION_PREFIX):
        return cipher_text  # Não encriptado (compatibilidade)

    raw_cipher = cipher_text[len(_ENCRYPTION_PREFIX):]
    fernet = get_fernet_instance()
    try:
        decrypted_bytes = fernet.decrypt(raw_cipher.encode('utf-8'))
        return decrypted_bytes.decode('utf-8')
    except (InvalidToken, Exception) as e:
        # Em caso de falha de decriptação (ex: chave alterada), não crasha silenciosamente
        raise ValueError(f"Falha na decriptação de campo seguro: {e}") from e


def compute_blind_index(plain_text: Optional[str]) -> Optional[str]:
    """
    Gera um Blind Index determinístico via HMAC-SHA256 para permitir buscas exatas indexadas
    na base de dados sem expor nem decriptar o dado original.
    Normaliza o texto (espaços removidos e minúsculas) para buscas consistentes.
    """
    if plain_text is None:
        return None
    if not isinstance(plain_text, str):
        plain_text = str(plain_text)
    
    # Se o valor recebido por engano for um ciphertext, primeiro decripta para calcular o hash
    if plain_text.startswith(_ENCRYPTION_PREFIX):
        plain_text = decrypt_value(plain_text) or ""

    normalized = plain_text.strip().lower()
    if not normalized:
        return ""

    key = get_blind_index_key()
    h = hmac.new(key, normalized.encode('utf-8'), hashlib.sha256)
    return h.hexdigest()


class EncryptedCharField(models.CharField):
    """
    Campo CharField com encriptação transparente no banco de dados.
    No Python/código: manipulado como texto claro normal.
    No Banco de Dados: gravado como ciphertext AES-256 com prefixo 'enc::v1::'.
    """
    def __init__(self, *args, **kwargs):
        # Aumenta o max_length para acomodar o overhead da criptografia base64
        max_len = kwargs.get('max_length', 255)
        kwargs['max_length'] = max(max_len * 4, 512)
        super().__init__(*args, **kwargs)

    def from_db_value(self, value, expression, connection):
        if value is None:
            return value
        return decrypt_value(value)

    def to_python(self, value):
        if value is None:
            return value
        return decrypt_value(value)

    def get_prep_value(self, value):
        if value is None:
            return value
        return encrypt_value(value)


class EncryptedTextField(models.TextField):
    """
    Campo TextField com encriptação transparente no banco de dados.
    """
    def from_db_value(self, value, expression, connection):
        if value is None:
            return value
        return decrypt_value(value)

    def to_python(self, value):
        if value is None:
            return value
        return decrypt_value(value)

    def get_prep_value(self, value):
        if value is None:
            return value
        return encrypt_value(value)
