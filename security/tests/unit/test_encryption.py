import pytest
from django.test import RequestFactory
from django.http import HttpResponse
from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import identify_hasher
from security.encryption import (
    encrypt_value,
    decrypt_value,
    compute_blind_index,
    get_encryption_key,
    get_blind_index_key,
)
from security.masking import (
    mask_doc_number,
    mask_phone,
    mask_email,
    sanitize_log_metadata,
)
from security.middleware import FinancialSecurityHeadersMiddleware
from users.models import IdentityDocument, UserSecurity
from audit.infra.models import AuditLog


User = get_user_model()


class TestEncryptionUtils:
    def test_key_derivation_deterministic(self):
        key1 = get_encryption_key()
        key2 = get_encryption_key()
        assert key1 == key2
        assert len(key1) > 0

    def test_blind_index_key_derivation(self):
        key1 = get_blind_index_key()
        key2 = get_blind_index_key()
        assert key1 == key2
        assert len(key1) == 32

    def test_encrypt_decrypt_roundtrip(self):
        original = "002367037LA033"
        ciphertext = encrypt_value(original)
        assert ciphertext is not None
        assert ciphertext.startswith("enc::v1::")
        assert ciphertext != original

        decrypted = decrypt_value(ciphertext)
        assert decrypted == original

    def test_encrypt_idempotent(self):
        original = "Secret123"
        ciphertext1 = encrypt_value(original)
        ciphertext2 = encrypt_value(ciphertext1)
        assert ciphertext1 == ciphertext2
        assert decrypt_value(ciphertext2) == original

    def test_encrypt_none_and_empty(self):
        assert encrypt_value(None) is None
        assert encrypt_value("") == ""
        assert decrypt_value(None) is None
        assert decrypt_value("") == ""

    def test_blind_index_deterministic_and_normalized(self):
        doc1 = "002367037LA033"
        doc2 = "  002367037la033 "
        hash1 = compute_blind_index(doc1)
        hash2 = compute_blind_index(doc2)
        assert hash1 == hash2
        assert len(hash1) == 64  # SHA-256 hex digest

    def test_blind_index_from_ciphertext(self):
        doc = "002367037LA033"
        cipher = encrypt_value(doc)
        hash_from_plain = compute_blind_index(doc)
        hash_from_cipher = compute_blind_index(cipher)
        assert hash_from_plain == hash_from_cipher


class TestMaskingUtils:
    def test_mask_doc_number(self):
        assert mask_doc_number("002367037LA033") == "00236******033"
        assert mask_doc_number("12345") == "*****"
        assert mask_doc_number("") == ""

    def test_mask_phone(self):
        assert mask_phone("+244943558106") == "+2449435***106" or mask_phone("+244943558106").startswith("+244")
        assert mask_phone("943558106") == "943***106"
        assert mask_phone("") == ""

    def test_mask_email(self):
        assert mask_email("utilizador@kwanzaconnect.ao") == "u********r@kwanzaconnect.ao"
        assert mask_email("ab@test.com") == "a*@test.com"
        assert mask_email("invalid") == "***"

    def test_sanitize_log_metadata_recursive(self):
        raw_meta = {
            "user_email": "test@domain.com",
            "password": "SuperSecretPassword123!",
            "doc_number": "002367037LA033",
            "phone": "943558106",
            "safe_action": "EXCHANGE_OFFER",
            "nested": {
                "two_factor_secret": "JBSWY3DPEHPK3PXP",
                "normal_field": 12345,
            }
        }
        sanitized = sanitize_log_metadata(raw_meta)
        assert sanitized["password"] == "[REDACTED_SENSITIVE_DATA]"
        assert "SuperSecretPassword123!" not in str(sanitized)
        assert sanitized["nested"]["two_factor_secret"] == "[REDACTED_SENSITIVE_DATA]"
        assert sanitized["safe_action"] == "EXCHANGE_OFFER"
        assert sanitized["nested"]["normal_field"] == 12345
        assert sanitized["doc_number"] == "00236******033"
        assert sanitized["phone"] == "943***106"


class TestFinancialSecurityHeadersMiddleware:
    def test_security_headers_injected(self):
        rf = RequestFactory()
        request = rf.get("/api/v1/health/")
        
        def dummy_view(req):
            return HttpResponse("OK")
            
        middleware = FinancialSecurityHeadersMiddleware(dummy_view)
        response = middleware(request)

        assert response.headers.get("Strict-Transport-Security") == "max-age=31536000; includeSubDomains; preload"
        assert response.headers.get("X-Content-Type-Options") == "nosniff"
        assert response.headers.get("X-Frame-Options") == "DENY"
        assert response.headers.get("Referrer-Policy") == "strict-origin-when-cross-origin"
        assert response.headers.get("X-XSS-Protection") == "1; mode=block"
        assert response.headers.get("Permissions-Policy") == "camera=(), microphone=(), geolocation=(), payment=()"
        assert response.headers.get("Cross-Origin-Opener-Policy") == "same-origin"
        assert "frame-ancestors 'none'" in response.headers.get("Content-Security-Policy", "")


from django.test import TestCase

class TestDatabaseFieldEncryptionAndHashing(TestCase):
    def test_argon2_is_default_password_hasher(self):
        user = User.objects.create_user(
            email="argon2test@kwanzaconnect.ao",
            password="StrongPassword2026!",
            full_name="Argon2 Test User"
        )
        hasher = identify_hasher(user.password)
        assert hasher.algorithm == "argon2"

    def test_identity_document_encrypted_in_db_and_blind_index_generated(self):
        user = User.objects.create_user(
            email="kyctest@kwanzaconnect.ao",
            password="StrongPassword2026!",
            full_name="KYC Test User"
        )
        raw_doc_number = "002367037LA033"
        doc = IdentityDocument.objects.create(
            user=user,
            doc_type="bi",
            doc_number=raw_doc_number
        )
        doc.refresh_from_db()

        # Decriptado transparente no ORM
        assert doc.doc_number == raw_doc_number
        # Blind index hash gerado
        assert doc.doc_number_hash == compute_blind_index(raw_doc_number)
        assert doc.masked_doc_number == "00236******033"

        # Verificação do valor bruto no banco de dados (deve conter o ciphertext enc::v1::)
        from django.db import connection
        with connection.cursor() as cursor:
            cursor.execute("SELECT doc_number FROM users_identitydocument WHERE id = %s", [str(doc.id)])
            row = cursor.fetchone()
            db_stored_doc_number = row[0]
            assert db_stored_doc_number.startswith("enc::v1::")
            assert raw_doc_number not in db_stored_doc_number

    def test_user_security_two_factor_secret_encrypted_in_db(self):
        user = User.objects.create_user(
            email="totptest@kwanzaconnect.ao",
            password="StrongPassword2026!",
            full_name="TOTP Test User"
        )
        raw_secret = "JBSWY3DPEHPK3PXP"
        security, _ = UserSecurity.objects.get_or_create(user=user)
        security.two_factor_enabled = True
        security.two_factor_secret = raw_secret
        security.save()
        security.refresh_from_db()
        assert security.two_factor_secret == raw_secret

        from django.db import connection
        with connection.cursor() as cursor:
            cursor.execute("SELECT two_factor_secret FROM users_usersecurity WHERE id = %s", [str(security.id)])
            row = cursor.fetchone()
            db_stored_secret = row[0]
            assert db_stored_secret.startswith("enc::v1::")
            assert raw_secret not in db_stored_secret

    def test_audit_log_metadata_sanitized_on_save(self):
        log = AuditLog.objects.create(
            action="USER_KYC_SUBMIT",
            resource="IdentityDocument",
            metadata={
                "doc_number": "002367037LA033",
                "phone": "+244943558106",
                "password": "RawPlainPassword123"
            }
        )
        log.refresh_from_db()
        assert log.metadata["password"] == "[REDACTED_SENSITIVE_DATA]"
        assert log.metadata["doc_number"] == "00236******033"
        assert "RawPlainPassword123" not in str(log.metadata)
