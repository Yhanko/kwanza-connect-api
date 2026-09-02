import pytest
import uuid
import pyotp
import jwt
from unittest.mock import Mock, patch
from django.conf import settings
from rest_framework.exceptions import ValidationError, AuthenticationFailed
from users.domain.entities import UserEntity, UserSecurityEntity
from users.services.use_cases import (
    Setup2FAUseCase, Enable2FAUseCase, Disable2FAUseCase,
    Verify2FALoginUseCase, LoginUseCase
)

@pytest.fixture
def mock_user_and_security():
    user_id = uuid.uuid4()
    security_id = uuid.uuid4()
    
    user = UserEntity(
        id=user_id,
        email='usuario@kwanzaconnect.ao',
        full_name='Romeu Cajamba',
        is_active=True
    )
    
    security = UserSecurityEntity(
        id=security_id,
        user_id=user_id,
        two_factor_enabled=False,
        two_factor_secret=''
    )
    
    return user, security

def test_2fa_setup_generates_secret_and_qr_code(mock_user_and_security):
    """Testa se o Setup2FA gera segredo base32 válido, URL otpauth e imagem QR Code em Base64."""
    user, security = mock_user_and_security
    mock_repo = Mock()
    mock_repo.get_by_id.return_value = user
    mock_repo.get_security_by_user_id.return_value = security
    
    use_case = Setup2FAUseCase(mock_repo)
    result = use_case.execute(user_id=user.id)
    
    assert 'secret' in result
    assert len(result['secret']) == 32
    assert 'qr_code' in result
    assert result['qr_code'].startswith('data:image/png;base64,')
    assert 'otpauth_url' in result
    assert 'otpauth://totp/KwanzaConnect:usuario%40kwanzaconnect.ao' in result['otpauth_url']
    assert mock_repo.update_security.called

@patch('users.models.UserSecurity.objects.get')
def test_2fa_enable_with_valid_code(mock_django_security_get, mock_user_and_security):
    """Testa a ativação do 2FA com código TOTP válido e geração de Backup Codes."""
    user, security = mock_user_and_security
    secret = pyotp.random_base32()
    security.two_factor_secret = secret
    
    mock_repo = Mock()
    mock_repo.get_security_by_user_id.return_value = security
    mock_audit = Mock()
    
    mock_django_security = Mock()
    mock_django_security.generate_backup_codes.return_value = ['A1B2-C3D4', 'E5F6-G7H8']
    mock_django_security_get.return_value = mock_django_security
    
    # Gera código válido atual
    totp = pyotp.TOTP(secret)
    valid_code = totp.now()
    
    use_case = Enable2FAUseCase(mock_repo, mock_audit)
    result = use_case.execute(user_id=user.id, code=valid_code)
    
    assert result['two_factor_enabled'] is True
    assert len(result['backup_codes']) == 2
    assert mock_django_security.generate_backup_codes.called
    assert mock_audit.save.called

def test_2fa_enable_with_invalid_code_raises_error(mock_user_and_security):
    """Testa se código inválido lança ValidationError na ativação do 2FA."""
    user, security = mock_user_and_security
    security.two_factor_secret = pyotp.random_base32()
    
    mock_repo = Mock()
    mock_repo.get_security_by_user_id.return_value = security
    mock_audit = Mock()
    
    use_case = Enable2FAUseCase(mock_repo, mock_audit)
    with pytest.raises(ValidationError) as exc_info:
        use_case.execute(user_id=user.id, code='000000')
    
    assert 'inválido ou expirado' in str(exc_info.value)

@patch('django.contrib.auth.authenticate')
def test_login_flow_with_2fa_enabled(mock_auth, mock_user_and_security):
    """Testa se utilizador com 2FA activo recebe desafio com pre_auth_token em vez de tokens JWT."""
    user, security = mock_user_and_security
    security.two_factor_enabled = True
    security.two_factor_secret = pyotp.random_base32()
    
    mock_repo = Mock()
    mock_repo.get_by_email.return_value = user
    mock_repo.get_security_by_user_id.return_value = security
    mock_audit = Mock()
    
    mock_django_user = Mock()
    mock_auth.return_value = mock_django_user
    
    use_case = LoginUseCase(mock_repo, mock_audit)
    result = use_case.execute(email='usuario@kwanzaconnect.ao', password='MinhaSenha123!')
    
    assert result['two_factor_required'] is True
    assert 'pre_auth_token' in result
    
    # Valida que o token temporário foi assinado com a secret key
    payload = jwt.decode(result['pre_auth_token'], settings.SECRET_KEY, algorithms=['HS256'])
    assert payload['user_id'] == str(user.id)
    assert payload['action'] == '2fa_pre_auth'

@patch('users.models.User.objects.get')
@patch('users.models.UserSecurity.objects.get')
@patch('rest_framework_simplejwt.tokens.RefreshToken.for_user')
def test_verify_2fa_login_with_valid_totp(mock_refresh_for_user, mock_django_sec_get, mock_django_user_get, mock_user_and_security):
    """Testa a conclusão do login com código TOTP de 6 dígitos."""
    user, security = mock_user_and_security
    secret = pyotp.random_base32()
    
    mock_django_user = Mock(id=user.id, email=user.email)
    mock_django_user_get.return_value = mock_django_user
    
    mock_django_security = Mock(two_factor_enabled=True, two_factor_secret=secret)
    mock_django_security.verify_and_consume_backup_code.return_value = False
    mock_django_sec_get.return_value = mock_django_security
    
    mock_refresh = Mock()
    mock_refresh.access_token = 'jwt_access_final_token'
    mock_refresh_for_user.return_value = mock_refresh
    
    # Gera o pre_auth_token válido
    pre_auth_payload = {
        'user_id': str(user.id),
        'action': '2fa_pre_auth'
    }
    pre_auth_token = jwt.encode(pre_auth_payload, settings.SECRET_KEY, algorithm='HS256')
    
    valid_code = pyotp.TOTP(secret).now()
    
    mock_repo = Mock()
    mock_audit = Mock()
    use_case = Verify2FALoginUseCase(mock_repo, mock_audit)
    result = use_case.execute(pre_auth_token=pre_auth_token, code=valid_code)
    
    assert result['two_factor_required'] is False
    assert result['access'] == 'jwt_access_final_token'
    assert mock_audit.save.called

@patch('users.models.User.objects.get')
@patch('users.models.UserSecurity.objects.get')
def test_verify_2fa_login_with_invalid_code_raises_auth_failed(mock_django_sec_get, mock_django_user_get, mock_user_and_security):
    """Testa se código 2FA incorreto falha o login e dispara log de falha de segurança."""
    user, security = mock_user_and_security
    secret = pyotp.random_base32()
    
    mock_django_user = Mock(id=user.id, email=user.email)
    mock_django_user_get.return_value = mock_django_user
    
    mock_django_security = Mock(two_factor_enabled=True, two_factor_secret=secret)
    mock_django_security.verify_and_consume_backup_code.return_value = False
    mock_django_sec_get.return_value = mock_django_security
    
    pre_auth_token = jwt.encode({'user_id': str(user.id), 'action': '2fa_pre_auth'}, settings.SECRET_KEY, algorithm='HS256')
    
    mock_repo = Mock()
    mock_audit = Mock()
    use_case = Verify2FALoginUseCase(mock_repo, mock_audit)
    
    with pytest.raises(AuthenticationFailed) as exc_info:
        use_case.execute(pre_auth_token=pre_auth_token, code='999999')
    
    assert 'inválido' in str(exc_info.value)
    assert mock_audit.save.called
